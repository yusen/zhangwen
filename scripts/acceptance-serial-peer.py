"""Development-only COM522 transport for the shared TypeScript protocol acceptance.

No HTTP endpoint. The product continues to use browser Web Serial. pyserial is
isolated under .test-data/serial-runtime, never a production dependency.
"""
import base64
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".test-data/serial-runtime"))
import serial

port = None
closing = False
output_lock = threading.Lock()


def emit(value):
    with output_lock:
        print(json.dumps(value), flush=True)


def reader():
    while not closing and port and port.is_open:
        try:
            data = port.read(1024)
            if data:
                emit({"data": base64.b64encode(data).decode()})
        except Exception as exc:
            if not closing:
                emit({"fault": str(exc)})
            return


try:
    for line in sys.stdin:
        request = json.loads(line)
        try:
            if request["op"] == "open":
                port = serial.Serial(port=None, baudrate=115200, timeout=0.05, write_timeout=5)
                port.port = "COM522"
                port.dtr = False
                port.rts = False
                port.open()
                threading.Thread(target=reader, daemon=True).start()
            elif request["op"] == "write":
                port.write(base64.b64decode(request["data"]))
                port.flush()
            elif request["op"] == "close":
                closing = True
                port.close()
            else:
                raise ValueError("Unknown acceptance operation")
            emit({"id": request["id"], "ok": True})
        except Exception as exc:
            emit({"id": request["id"], "error": str(exc)})
finally:
    closing = True
    if port and port.is_open:
        port.close()
