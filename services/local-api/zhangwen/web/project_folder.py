"""Reveal only a user-selected, fingerprint-verified project directory.

No project files are written here, and paths never become commands or model tools.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import Field, field_validator

from .models import Boundary
from .portable import SNAPSHOT_MAX_BYTES
from . import folder_picker  # Include the fixed chooser in the deployment closure.


class OpenFolderInput(Boundary):
    checkpointHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    chooseAgain: bool = False

    @field_validator('path')
    @classmethod
    def clean_path(cls, value):
        if value is not None and (any(ord(c) < 32 or ord(c) == 127 for c in value) or value.startswith(('\\\\', '//'))):
            raise ValueError('请使用本机项目文件夹的完整路径。')
        return value


def choose_directory():
    try:
        if sys.platform == 'win32':
            assert folder_picker.__name__.endswith('.folder_picker')
            result = subprocess.run([sys.executable, '-m', folder_picker.__name__], capture_output=True,
                                    timeout=120, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return json.loads(result.stdout)['path'] or None
        if sys.platform == 'darwin':
            script = 'try\nreturn POSIX path of (choose folder with prompt "请选择同一个掌问项目文件夹")\non error number -128\nreturn ""\nend try'
            result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, timeout=120, check=True)
            return result.stdout.decode('utf-8').strip() or None
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        raise HTTPException(503, '系统文件夹选择器未完成。可展开“手动定位”，粘贴此项目文件夹的完整路径后打开。') from exc
    raise HTTPException(503, '请展开“手动定位”，粘贴此项目文件夹的完整路径后打开。')


def verified_directory(value, expected_hash, portable_id):
    path = Path(value)
    if (not path.is_absolute() or '..' in path.parts or value.startswith(('\\\\', '//'))
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise HTTPException(422, '请提供本机项目文件夹的完整路径。')
    try:
        # Do not follow symlink/junction redirects to another location.
        for part in [path, *path.parents]:
            if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
                raise HTTPException(422, '请直接选择实际项目文件夹，不使用符号链接或联接。')
        if not path.is_dir():
            raise HTTPException(422, '此路径不是可用的项目文件夹。')
        snapshot = path / 'zhangwen.project.json'
        if snapshot.is_symlink() or not snapshot.is_file() or snapshot.stat().st_size > SNAPSHOT_MAX_BYTES:
            raise HTTPException(422, '此文件夹没有可核对的掌问项目快照。')
        with snapshot.open('rb') as stream:
            content = stream.read(SNAPSHOT_MAX_BYTES + 1)
        if len(content) > SNAPSHOT_MAX_BYTES:
            raise HTTPException(413, '项目快照超过32MiB，未读取或打开。')
        value = json.loads(content)
        if (not isinstance(value, dict) or value.get('format') != 'zhangwen-project'
                or value.get('schemaVersion') != 1 or value.get('portableId') != portable_id):
            raise HTTPException(409, '所选文件夹不属于当前项目，请重新定位同一个项目文件夹。')
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise HTTPException(409, '文件夹快照与当前关联不一致。请先保存同步或重新加载该文件夹，再打开。')
        return path.resolve(strict=True)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(422, '无法核对项目文件夹。请确认路径、权限和项目快照完整。') from exc


def reveal_directory(path):
    try:
        if sys.platform == 'win32':
            os.startfile(str(path), 'explore')
        elif sys.platform == 'darwin':
            subprocess.run(['/usr/bin/open', str(path)], check=True, timeout=10, capture_output=True)
        else:
            subprocess.run(['/usr/bin/xdg-open', str(path)], check=True, timeout=10, capture_output=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(503, '系统未完成打开请求。可复制下方路径，在文件管理器中打开。') from exc


def router(repo):
    route = APIRouter()
    locations = {}
    lock = Lock()

    @route.post('/api/projects/{pid}/folder/open')
    def open_folder(pid: str, request: OpenFolderInput):
        repo.get(pid)
        with repo.connect() as conn:
            portable_id = conn.execute('SELECT COALESCE(portable_id, project_id) FROM zhangwen_workspaces WHERE project_id=?', (pid,)).fetchone()[0]
        if not lock.acquire(blocking=False):
            raise HTTPException(409, '已有文件夹定位正在进行，请先完成或取消。')
        try:
            value = choose_directory() if request.chooseAgain else request.path or locations.get(pid) or choose_directory()
            if value is None:
                return {'status': 'canceled'}
            path = verified_directory(value, request.checkpointHash, portable_id)
            reveal_directory(path)
            locations[pid] = str(path)
            return {'status': 'requested', 'path': str(path), 'name': path.name}
        finally:
            lock.release()

    from .managed_folders import router as managed_router
    route.include_router(managed_router(repo))
    return route
