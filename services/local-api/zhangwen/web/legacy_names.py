"""Read-only aliases and bounded migrations for previously installed data.

Old strings are confined here. Historic message/artifact identifiers and content
are never rewritten merely to change the platform's current name.
"""
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import sys
import urllib.request
import webbrowser

TABLE_NAMES = {'mu_workspaces': 'zhangwen_workspaces', 'mu_code_metadata': 'zhangwen_code_metadata'}
AI_SOURCES = ('zhangwen_ai_code', 'mu_ai_code')


def migrate_tables(connection):
    """Rename existing tables atomically; never create a parallel project store."""
    with closing(connection), connection as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for old, new in TABLE_NAMES.items():
            if old in names and new in names:
                raise RuntimeError('检测到新旧工作区表同时存在，请保留数据并核对升级记录。')
        conn.execute('BEGIN IMMEDIATE')
        for old, new in TABLE_NAMES.items():
            if old in names:
                conn.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')


def settings_path(directory: Path):
    current, previous = directory / 'zhangwen-settings.json', directory / 'mu-settings.json'
    if previous.is_file() and not current.exists():
        previous.rename(current)
    return current


def environment_model(default):
    return os.environ.get('ZHANGWEN_MODEL', os.environ.get('ZHANGWEN_MU_MODEL', default))


def session_header(headers):
    return headers.get('x-zhangwen-session', headers.get('x-mu-session', ''))


def workspace_message(column='metadata_json'):
    # Callers supply fixed SQL column names, never model or browser input.
    return f"(json_extract({column}, '$.zhangwen')=1 OR json_extract({column}, '$.mu')=1)"


def artifact_id(conn, project_id, kind):
    current, previous = f'zhangwen_{kind}_{project_id}', f'mu_{kind}_{project_id}'
    rows = conn.execute('SELECT id FROM artifacts WHERE project_id=? AND id IN (?, ?)',
                        (project_id, current, previous)).fetchall()
    if len(rows) > 1:
        raise RuntimeError('检测到重复的项目历史，请保留数据并核对升级记录。')
    return rows[0][0] if rows else current


@contextmanager
def previous_service_lock(directory: Path, no_open: bool):
    """Keep an old launcher from writing this directory during an upgrade."""
    path = directory / '.mu-web.lock'
    if not path.exists():
        yield
        return
    with path.open('a+b') as lock:
        lock.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            for name in ['.zhangwen-web-address.json', '.mu-web-address.json']:
                try:
                    address = json.loads((directory / name).read_text(encoding='utf-8'))
                    port = address['port']
                    if type(port) is not int or not 1024 <= port <= 65535:
                        continue
                    url = f'http://127.0.0.1:{port}'
                    with urllib.request.urlopen(url + '/api/health', timeout=2) as response:
                        health = json.load(response)
                    if health.get('instanceId') == address['instanceId'] and health.get('transport') == 'web-serial':
                        if not no_open:
                            webbrowser.open(url)
                        print(f'掌问已运行 → {url}', flush=True)
                        raise SystemExit(0)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            raise SystemExit('此数据目录已有掌问服务运行。请使用已有浏览器入口。')
        # The lock is free; a prior process left this public marker behind.
        (directory / '.mu-web-address.json').unlink(missing_ok=True)
        try:
            yield
        finally:
            lock.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)
