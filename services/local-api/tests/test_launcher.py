from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def test_busy_port_is_not_replaced_and_does_not_initialize_database(tmp_path: Path):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        result = subprocess.run([sys.executable, "-m", "zhangwen.mu_web", "--no-open", "--port", str(port)],
            env={**os.environ, "ZHANGWEN_DATA_DIR": str(tmp_path), "PYTHONUTF8": "1"},
            capture_output=True, encoding="utf-8", timeout=20)
        assert result.returncode == 1
        assert "已占用" in result.stderr
        assert not (tmp_path / "projects/zhangwen.sqlite3").exists()
        assert busy.getsockname()[1] == port


def test_single_instance_and_restart_after_process_exit(tmp_path: Path):
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    argv = [sys.executable, "-m", "zhangwen.mu_web", "--no-open", "--port", str(port)]
    env = {**os.environ, "ZHANGWEN_DATA_DIR": str(tmp_path), "PYTHONUTF8": "1"}
    for _ in range(2):
        process = subprocess.Popen(argv, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 20
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                        assert response.status == 200
                        break
                except (OSError, urllib.error.URLError):
                    assert process.poll() is None, process.stderr.read().decode("utf-8")
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
            duplicate = subprocess.run(argv, env=env, capture_output=True, encoding="utf-8", timeout=15)
            assert duplicate.returncode == 1
            assert "已有掌问服务" in duplicate.stderr
        finally:
            process.terminate()
            process.wait(timeout=10)
            process.stderr.close()
