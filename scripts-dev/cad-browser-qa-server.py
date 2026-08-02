"""Serve a generated GLB through the desktop Vite host for manual CAD QA."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys


if len(sys.argv) != 2:
    raise SystemExit("usage: cad-browser-qa-server.py <directory-containing-preview.glb>")

ROOT = Path(sys.argv[1]).resolve()
PREVIEW = ROOT / "preview.glb"
if not PREVIEW.is_file():
    raise SystemExit(f"preview.glb not found in {ROOT}")

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>CAD Viewer QA</title>
  <style>
    html, body, #root { width: 100%; height: 100%; margin: 0; }
    body { font-family: system-ui, sans-serif; overflow: hidden; }
    .model3d-viewer { display: grid; grid-template-rows: auto minmax(0, 1fr); height: 100%; }
    .model3d-toolbar { display: flex; justify-content: space-between; gap: 12px; padding: 8px; }
    .model3d-view-modes, .model3d-camera-actions { display: flex; gap: 6px; }
    .model3d-canvas { min-height: 0; }
    .model3d-canvas canvas { display: block; width: 100%; height: 100%; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module">
    import React from "http://localhost:5173/node_modules/.vite/deps/react.js";
    import ReactDomClient from "http://localhost:5173/node_modules/.vite/deps/react-dom_client.js";
    import RefreshRuntime from "http://localhost:5173/@react-refresh";
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => (type) => type;
    window.__vite_plugin_react_preamble_installed__ = true;
    const { Model3DViewer } = await import("http://localhost:5173/src/components/floating/Model3DViewer.tsx");
    const data = await fetch("/preview.glb").then((response) => response.arrayBuffer());
    ReactDomClient.createRoot(document.getElementById("root")).render(
      React.createElement(Model3DViewer, { data, fileName: "preview.glb" })
    );
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/preview.glb":
            payload = PREVIEW.read_bytes()
            content_type = "model/gltf-binary"
        else:
            payload = HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        _ = (format, args)


ThreadingHTTPServer(("127.0.0.1", 5199), Handler).serve_forever()
