#!/usr/bin/env python3
"""掌控台本地服务 — 只绑 127.0.0.1（端口在 config.json）
GET /        → 返回最新仪表盘 HTML
GET /health  → ok
POST /run    → body {"prompt": "..."} → 开新 Terminal 窗口跑 claude "<prompt>"
POST /rerender → 立即重跑 render_console.py
"""
import json
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text())
HTML = Path(CFG["output"]).expanduser()
if not HTML.is_absolute():
    HTML = HERE / HTML
WORKDIR = str(Path(CFG.get("claude_workdir", "~")).expanduser())
LAUNCHER = HERE / "launch_claude.applescript"
PORT = CFG.get("port", 8765)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(200, "{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if HTML.exists():
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, '{"error":"仪表盘还没渲染过，先跑 render_console.py"}')
        elif self.path == "/health":
            self._send(200, '{"ok":true}')
        else:
            self._send(404, '{"error":"not found"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._send(400, '{"error":"bad json"}')
            return
        if self.path == "/run":
            prompt = (body.get("prompt") or "").strip()
            if not prompt:
                self._send(400, '{"error":"empty prompt"}')
                return
            r = subprocess.run(
                ["osascript", str(LAUNCHER), prompt, WORKDIR],
                capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                self._send(200, '{"ok":true}')
            else:
                self._send(500, json.dumps({"error": r.stderr.strip()[:300]},
                                           ensure_ascii=False))
        elif self.path == "/rerender":
            r = subprocess.run(
                ["/usr/bin/python3", str(HERE / "render_console.py")],
                capture_output=True, text=True, timeout=120)
            ok = r.returncode == 0
            self._send(200 if ok else 500,
                       json.dumps({"ok": ok, "out": (r.stdout + r.stderr)[-300:]},
                                  ensure_ascii=False))
        else:
            self._send(404, '{"error":"not found"}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
