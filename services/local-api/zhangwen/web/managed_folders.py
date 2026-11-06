"""Explicit local project saving. Fixed project roots, no model/command capability."""
import base64
import ctypes
import hashlib
import json
import os
import re
import sys
import uuid
import unicodedata
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import Field, ValidationError, field_validator
from .models import Boundary
from .portable import export_project, ProjectSnapshot, SNAPSHOT_MAX_BYTES


def checksum(raw): return hashlib.sha256(raw).hexdigest()


def documents():
    override = os.environ.get('ZHANGWEN_PROJECTS_DIR')
    if override:
        path = Path(override)
        if not path.is_absolute(): raise HTTPException(503, '项目保存位置必须为完整路径。')
        return path
    if sys.platform == 'win32':
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) != 0:
            raise HTTPException(503, '无法读取文档目录，请检查系统文件夹设置。')
        return Path(buffer.value) / '掌问项目'
    return Path.home() / 'Documents' / '掌问项目'


def safe_part(value):
    return bool(value and len(value) <= 200 and value not in {'.', '..'} and not re.search(r'[<>:"/\\|?*\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]', value)
                and not value.endswith(('.', ' ')) and not re.match(r'(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', value))


def checked(path):
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise HTTPException(422, '请使用实际项目目录，不使用符号链接或联接。')
    return path


class FolderFile(Boundary):
    path: list[str] = Field(min_length=1, max_length=12)
    sha256: str = Field(pattern='^[a-f0-9]{64}$')
    content: str = Field(max_length=24*1024*1024)

    @field_validator('path')
    @classmethod
    def path_parts(cls, value):
        roots = {'代码', '结构', '硬件', '资料归档', '学习与验收', '成果档案', '教学设计', '作品说明', 'programs'}
        if not all(safe_part(p) for p in value) or len(value) < 2 or value[0] not in roots:
            raise ValueError('仅可保存项目清单内文件。')
        return value


class Sync(Boundary):
    snapshot: str = Field(max_length=SNAPSHOT_MAX_BYTES)
    expectedCheckpointHash: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')
    files: list[FolderFile] = Field(max_length=8000)


def router(repo):
    route = APIRouter()
    locations = repo.db.parent.parent / 'project-folder-locations.json'

    def mappings():
        checked(locations)
        return json.loads(locations.read_text(encoding='utf-8')) if locations.exists() else {}

    def persist(data):
        checked(locations)
        temp = locations.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, locations)

    def result(item):
        return {key: item.get(key) for key in ('path', 'name', 'checkpointHash', 'mainHash')}

    @route.get('/api/projects/{pid}/folder/managed')
    def get(pid: str):
        repo.get(pid)
        with repo.lock:
            item = mappings().get(pid)
            return result(item) if item else None

    @route.post('/api/projects/{pid}/folder/managed')
    def create(pid: str):
        project = repo.get(pid)
        with repo.lock:
            data = mappings()
            if pid in data: return result(data[pid])
            base = checked(documents())
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]', '_', project['name']).strip(' .')[:120].rstrip(' .') or '我的项目'
            if not safe_part(name): name = '_' + name
            base.mkdir(parents=True, exist_ok=True)
            # Check even empty folders and case/Unicode variants. Never adopt a different project's directory.
            normalize = lambda s: unicodedata.normalize('NFKC', s).casefold()
            occupied = {normalize(p.name) for p in base.iterdir()}
            for number in range(1, 10001):
                candidate = name if number == 1 else f'{name}（{number}）'
                if normalize(candidate) in occupied:
                    continue
                path = checked(base / candidate)
                try:
                    path.mkdir(exist_ok=False)
                    break
                except FileExistsError:
                    occupied.add(normalize(candidate))
            else:
                raise HTTPException(409, '同名项目文件夹过多，请修改项目名称或使用另存为。')
            data[pid] = {'path': str(path), 'name': path.name, 'checkpointHash': None, 'mainHash': None}
            persist(data)
            return result(data[pid])

    @route.post('/api/projects/{pid}/folder/managed/sync')
    def sync(pid: str, request: Sync):
        with repo.lock:
            data = mappings(); item = data.get(pid)
            if not item: raise HTTPException(409, '项目文件夹尚未建立，请先刷新保存位置。')
            path = checked(Path(item['path']))
            if request.expectedCheckpointHash != item['checkpointHash']:
                raise HTTPException(409, '文件夹已有更新，请刷新记录后再保存。')
            if len(request.snapshot.encode('utf-8')) > SNAPSHOT_MAX_BYTES: raise HTTPException(413, '项目备份超过容量。')
            try:
                snapshot = ProjectSnapshot.model_validate_json(request.snapshot).model_dump(exclude_none=True)
            except ValidationError as exc:
                raise HTTPException(422, '项目备份格式不完整，未写入文件夹。') from exc
            if snapshot != export_project(repo, pid): raise HTTPException(409, '项目已更新，未写入旧版本，请刷新后保存。')
            primary = 'chat-task.txt' if snapshot['project'].get('programmingMode') == 'chat-coding' else 'main.py'
            current = next(v for v in snapshot['versions'] if v['revision'] == snapshot['project']['revision'])
            raw = request.snapshot.encode('utf-8'); main = current['code'].encode('utf-8')
            targets = []; seen = set(); total = len(raw) + len(main)
            for f in request.files:
                key = '/'.join(f.path).casefold()
                if key in seen: raise HTTPException(422, '项目文件清单重复。')
                seen.add(key)
                try: content = base64.b64decode(f.content, validate=True)
                except ValueError as exc: raise HTTPException(422, '项目文件编码不完整。') from exc
                total += len(content)
                if total > 64*1024*1024: raise HTTPException(413, '本次项目保存超过64MiB，请精简资料。')
                if checksum(content) != f.sha256: raise HTTPException(422, '项目文件校验失败。')
                target = checked(path.joinpath(*f.path))
                if target.exists() and checksum(target.read_bytes()) != f.sha256:
                    raise HTTPException(409, '文件已在外部修改，未覆盖：' + '/'.join(f.path))
                targets.append((target, content))
            old_primary=item.get('mainFile','main.py')
            if primary!=old_primary and (path/primary).exists(): raise HTTPException(409, '新编程方式的文件已存在，未覆盖，请另存为。')
            for filename, previous in [('zhangwen.project.json', item['checkpointHash']), (old_primary, item['mainHash'])]:
                target = checked(path / filename)
                if target.exists() and (previous is None or checksum(target.read_bytes()) != previous):
                    raise HTTPException(409, filename + ' 已在外部修改，请通过打开文件夹项目读取或另存。')
                if not target.exists() and previous is not None: raise HTTPException(409, '原项目文件缺失，未自动重建或覆盖。')
            def write(target, content):
                checked(target.parent).mkdir(parents=True, exist_ok=True)
                temp = target.with_name('.' + target.name + '.' + uuid.uuid4().hex + '.tmp')
                try:
                    temp.write_bytes(content); os.replace(temp, target)
                    if checksum(target.read_bytes()) != checksum(content): raise HTTPException(503, '文件回读未通过，请检查保存位置。')
                finally:
                    if temp.exists(): temp.unlink()
            for target, content in targets:
                if not target.exists(): write(target, content)
            write(path / primary, main)
            write(path / 'zhangwen.project.json', raw)
            item['checkpointHash'], item['mainHash'] = checksum(raw), checksum(main)
            item['mainFile']=primary
            persist(data)
            return result(item)

    @route.post('/api/projects/{pid}/folder/managed/open')
    def open_folder(pid: str):
        repo.get(pid)
        with repo.lock:
            item = mappings().get(pid)
            if not item: raise HTTPException(404, '尚无默认项目文件夹，可先保存或另存为。')
            from .project_folder import verified_directory, reveal_directory
            with repo.connect() as conn:
                portable_id = conn.execute('SELECT COALESCE(portable_id, project_id) FROM zhangwen_workspaces WHERE project_id=?', (pid,)).fetchone()[0]
            if not item['checkpointHash']: raise HTTPException(409, '文件夹尚未完成保存，请先保存项目。')
            target = verified_directory(item['path'], item['checkpointHash'], portable_id)
            reveal_directory(target)
            return {'status': 'requested', 'path': str(target), 'name': target.name}

    return route
