"""Reopen an owned local page before opening Terminal. Standard library only.

The first service keeps its existing terminal and Ctrl+C shutdown behavior.
This helper never initializes a database, kills a process or changes settings.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path


def running_url(install_root: Path) -> str | None:
    # Match the same data-directory marker as the server's single-instance
    # check. Never infer ownership from the default port being occupied.
    for name in ('.zhangwen-web-address.json', '.mu-web-address.json'):
        try:
            marker = install_root / 'data' / name
            if marker.stat().st_size > 4096:
                continue
            address = json.loads(marker.read_bytes())
            port, instance = address['port'], address['instanceId']
            if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(instance, str) or not instance:
                continue
            url = f'http://127.0.0.1:{port}'
            # Loopback only: ignore proxy environment and reject redirects.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs):
                    return None
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            with opener.open(url + '/api/health', timeout=0.5) as response:
                content = response.read(4097)
                if response.status != 200 or len(content) > 4096:
                    continue
                health = json.loads(content)
            if health.get('instanceId') == instance and health.get('transport') == 'web-serial':
                return url
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return None


def open_page(url: str) -> None:
    subprocess.run(['/usr/bin/open', url], check=True, timeout=10)


def service_holds_lock(install_root: Path) -> bool:
    import fcntl
    for name in ('.zhangwen-web.lock', '.mu-web.lock'):
        try:
            # Do not create/remove a server lock or trust a stale lock file.
            with (install_root / 'data' / name).open('r+b') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
        except FileNotFoundError:
            pass
    return False


def launch(install_root: Path, *, timeout: float = 240) -> str:
    import fcntl  # macOS advisory lock, released automatically on process exit.

    install_root = install_root.resolve()
    command = install_root / '启动掌问.command'
    if not command.is_file():
        raise ValueError('启动入口不存在，请重新运行安装命令。')
    runtime = install_root / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with (runtime / 'app-launch.lock').open('a+b') as lock:
        while True:
            url = running_url(install_root)
            if url:
                open_page(url)
                return 'reopened'
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('掌问仍在启动，请查看已有终端窗口后重试。')
                time.sleep(0.2)
        # A competing launcher can become ready between the probe and lock.
        url = running_url(install_root)
        if url:
            open_page(url)
            return 'reopened'
        # A service started via .command/old .app can own the data lock before
        # publishing health. Wait for it rather than opening a redundant terminal.
        while service_holds_lock(install_root):
            url = running_url(install_root)
            if url:
                open_page(url)
                return 'reopened'
            if time.monotonic() >= deadline:
                raise RuntimeError('已有掌问服务正在启动或未响应，请查看原终端窗口。')
            time.sleep(0.2)
        subprocess.run(['/usr/bin/open', '-a', 'Terminal', str(command)], check=True, timeout=10)
        # The normal command opens the browser once ready. Hold the launcher
        # lock until then, so rapid clicks cannot open more terminal windows.
        while time.monotonic() < deadline:
            if running_url(install_root):
                return 'started'
            time.sleep(0.2)
        raise RuntimeError('掌问尚未启动成功。请查看已打开的终端，不要重复打开应用；处理错误后再重试。')


def main() -> None:
    parser = argparse.ArgumentParser(description='Open the existing ZhangWen page or start it once')
    parser.add_argument('--install-root', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(launch(args.install_root), flush=True)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Fixed AppleScript; paths and diagnostics are arguments, never code.
        message = str(exc)
        try:
            subprocess.run(['/usr/bin/osascript', '-e',
                            'on run argv\ndisplay alert "掌问启动提示" message (item 1 of argv)\nend run',
                            message], check=False, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
        parser.exit(1, message + '\n')


if __name__ == '__main__':
    main()
