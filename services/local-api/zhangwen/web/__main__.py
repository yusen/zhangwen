"""python -m zhangwen.web — one loopback instance, build/run separated."""
from __future__ import annotations

import argparse
import errno
import json
import os
import secrets
import sys
import socket
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from zhangwen.web.app import ROOT, create_app
from .legacy_names import previous_service_lock


def bind_available_port(preferred: int) -> socket.socket:
    """Reserve a loopback socket, trying nearby ports before an OS assignment.

    Keep the successful socket open through database setup and server startup;
    probing and then reopening would allow another process to take the port.
    """
    candidates = [*range(preferred, min(preferred + 100, 65536)), 0]
    for port in candidates:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32":
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", port))
            listener.setblocking(False)
            return listener
        except OSError as exc:
            listener.close()
            # Windows excluded port ranges report access denied, not in use.
            unavailable = exc.errno in {errno.EADDRINUSE, errno.EACCES} or getattr(exc, 'winerror', None) in {10048, 10013}
            if port and unavailable:
                continue
            raise
    raise OSError("无法分配可用的本机端口")


def main() -> None:
    parser = argparse.ArgumentParser(description="掌问本地 Web 工作台")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--port", type=int, default=3080, help="首选端口（默认3080），不可用时自动切换")
    parser.add_argument("--dev", action="store_true", help="允许本机 Vite 5173 代理")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("端口须为 1024–65535")
    data_dir = Path(os.environ.get("ZHANGWEN_DATA_DIR", ROOT / ".data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".zhangwen-web.lock"
    address_path = data_dir / ".zhangwen-web-address.json"
    with previous_service_lock(data_dir, args.no_open), lock_path.open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Only open an instance that owns this data directory and matches
            # its random public health marker. Never open an unknown listener.
            try:
                address = json.loads(address_path.read_text(encoding="utf-8"))
                port = address["port"]
                if not isinstance(port, int) or not 1024 <= port <= 65535:
                    raise ValueError("invalid port")
                url = f"http://127.0.0.1:{port}"
                with urllib.request.urlopen(url + "/api/health", timeout=2) as response:
                    health = json.load(response)
                if health.get("instanceId") == address["instanceId"] and health.get("transport") == "web-serial":
                    if not args.no_open:
                        webbrowser.open(url)
                    print(f"掌问已运行 → {url}", flush=True)
                    return
            except (OSError, ValueError, KeyError, TypeError):
                pass
            parser.exit(1, "此数据目录已有掌问服务运行。请使用已有浏览器入口。\n")
        # Bind before initializing the database or opening a browser. Never kill
        # an unknown listener or accidentally open another service on this port.
        try:
            reserved = bind_available_port(args.port)
        except OSError:
            parser.exit(1, "无法绑定本机端口，请检查网络权限后重试。\n")
        with reserved as listener:
            port = listener.getsockname()[1]
            if port != args.port:
                print(f"端口 {args.port} 不可用，已自动切换到 {port}。", flush=True)
            app = create_app(data_dir, port=port, dev=args.dev)
            instance_id = secrets.token_hex(16)
            app.state.instance_id = instance_id
            address_path.write_text(json.dumps({"port": port, "instanceId": instance_id}), encoding="utf-8")
            url = f"http://127.0.0.1:{port}"
            if not args.no_open:
                def open_when_ready() -> None:
                    for _ in range(100):
                        try:
                            with urllib.request.urlopen(url + "/api/health", timeout=0.5) as response:
                                health = json.load(response)
                                if response.status == 200 and health.get('instanceId') == instance_id and health.get('transport') == 'web-serial':
                                    webbrowser.open(url)
                                    return
                        except OSError:
                            time.sleep(0.1)
                threading.Thread(target=open_when_ready, daemon=True).start()
            print(f"\n掌问本地 Web → {url}\n数据目录：{data_dir}\n按 Ctrl+C 停止服务。\n", flush=True)
            try:
                uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)).run(sockets=[listener])
            finally:
                address_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
