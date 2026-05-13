#!/usr/bin/env python3
"""
Single-file cloud-ready web service.

Run:
    python app.py

Environment:
    HOST=0.0.0.0
    PORT=8000
    APP_NAME=Cloud Ops Console
"""

from __future__ import annotations

import html
import json
import os
import platform
import random
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.parse
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


APP_NAME = os.getenv("APP_NAME", "Cloud Ops Console")
APP_VERSION = "1.0.0"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
START_TIME = time.time()


INTERVIEW_DECK = [
    {
        "tag": "Linux",
        "question": "A server suddenly becomes slow. What is your first troubleshooting path?",
        "answer": "Confirm impact, then check CPU, memory, disk, IO, network, process state, service logs, and recent changes.",
    },
    {
        "tag": "Docker",
        "question": "A container keeps restarting. How do you locate the cause?",
        "answer": "Check docker ps -a, docker logs, container exit code, env/config, volume mounts, port conflicts, and dependency readiness.",
    },
    {
        "tag": "Nginx",
        "question": "The domain returns 502. What should you check?",
        "answer": "Check upstream health, port listening, firewall/security group, Nginx error log, upstream config, and backend response.",
    },
    {
        "tag": "CI/CD",
        "question": "How do you make a deployment safer?",
        "answer": "Use versioned artifacts, pre-checks, health checks, rollback plan, log observation, and small controlled release windows.",
    },
    {
        "tag": "Monitoring",
        "question": "What alerts matter most for a SaaS service?",
        "answer": "Availability, latency, error rate, saturation, disk pressure, queue backlog, certificate expiry, and deployment failure rate.",
    },
    {
        "tag": "Security",
        "question": "What should you avoid when operating production servers?",
        "answer": "Avoid blind deletion, root overuse, unreviewed config changes, exposed secrets, missing backups, and operations without rollback.",
    },
]


@dataclass
class ServiceState:
    requests_total: int = 0
    errors_total: int = 0
    notes: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_request(self) -> None:
        with self.lock:
            self.requests_total += 1

    def record_error(self) -> None:
        with self.lock:
            self.errors_total += 1

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "requests_total": self.requests_total,
                "errors_total": self.errors_total,
                "notes_total": len(self.notes),
            }

    def add_note(self, text: str) -> dict[str, Any]:
        note = {
            "id": int(time.time() * 1000),
            "text": text.strip()[:300],
            "created_at": iso_now(),
        }
        with self.lock:
            self.notes.insert(0, note)
            self.notes = self.notes[:30]
        return note

    def list_notes(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.notes)


STATE = ServiceState()


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)


def pretty_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def get_system_status() -> dict[str, Any]:
    disk = shutil.disk_usage(os.getcwd())
    load_avg = None
    if hasattr(os, "getloadavg"):
        try:
            load_avg = [round(v, 2) for v in os.getloadavg()]
        except OSError:
            load_avg = None

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "status": "ok",
        "time": iso_now(),
        "uptime_seconds": uptime_seconds(),
        "uptime": pretty_uptime(uptime_seconds()),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "load_avg": load_avg,
        "disk": {
            "total_gb": round(disk.total / 1024**3, 2),
            "used_gb": round(disk.used / 1024**3, 2),
            "free_gb": round(disk.free / 1024**3, 2),
            "used_percent": round(disk.used / disk.total * 100, 2),
        },
        **STATE.snapshot(),
    }


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    if length > 1024 * 1024:
        raise ValueError("request body too large")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


class AppHandler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/{APP_VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(
            json.dumps(
                {
                    "time": iso_now(),
                    "client": self.client_address[0],
                    "method": self.command,
                    "path": self.path,
                    "message": fmt % args,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        STATE.record_request()
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/":
                self.send_html(render_home())
            elif path == "/healthz":
                self.send_json({"status": "ok", "time": iso_now(), "uptime_seconds": uptime_seconds()})
            elif path == "/api/status":
                self.send_json(get_system_status())
            elif path == "/api/interview/random":
                self.send_json(random.choice(INTERVIEW_DECK))
            elif path == "/api/notes":
                self.send_json({"items": STATE.list_notes()})
            elif path == "/metrics":
                self.send_text(render_metrics(), content_type="text/plain; version=0.0.4; charset=utf-8")
            else:
                self.send_json({"error": "not_found", "path": path}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_exception(exc)

    def do_POST(self) -> None:
        STATE.record_request()
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/api/notes":
                payload = read_json(self)
                text = str(payload.get("text", "")).strip()
                if not text:
                    self.send_json({"error": "text is required"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self.send_json({"item": STATE.add_note(text)}, status=HTTPStatus.CREATED)
            elif path == "/api/echo":
                self.send_json({"received": read_json(self), "time": iso_now()})
            else:
                self.send_json({"error": "not_found", "path": path}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_exception(exc)

    def handle_exception(self, exc: Exception) -> None:
        STATE.record_error()
        traceback.print_exc()
        self.send_json(
            {"error": "internal_error", "message": str(exc), "time": iso_now()},
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, body: str, status: HTTPStatus = HTTPStatus.OK, content_type: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_text(body, status=status, content_type="text/html; charset=utf-8")


def render_metrics() -> str:
    status = get_system_status()
    disk = status["disk"]
    return "\n".join(
        [
            "# HELP app_uptime_seconds Application uptime in seconds.",
            "# TYPE app_uptime_seconds gauge",
            f"app_uptime_seconds {status['uptime_seconds']}",
            "# HELP app_requests_total Total HTTP requests.",
            "# TYPE app_requests_total counter",
            f"app_requests_total {status['requests_total']}",
            "# HELP app_errors_total Total internal errors.",
            "# TYPE app_errors_total counter",
            f"app_errors_total {status['errors_total']}",
            "# HELP app_disk_used_percent Current disk usage percent.",
            "# TYPE app_disk_used_percent gauge",
            f"app_disk_used_percent {disk['used_percent']}",
            "",
        ]
    )


def render_home() -> str:
    safe_name = html.escape(APP_NAME)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_name}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #101418;
      --panel: #171d23;
      --panel-2: #202832;
      --text: #edf2f7;
      --muted: #9aa7b5;
      --line: #2f3a46;
      --green: #38d996;
      --cyan: #5ec8f8;
      --yellow: #f5c85c;
      --red: #ff6b6b;
      --shadow: 0 18px 60px rgba(0, 0, 0, .28);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(135deg, rgba(56, 217, 150, .10), transparent 28%),
        linear-gradient(315deg, rgba(94, 200, 248, .12), transparent 26%),
        var(--bg);
      color: var(--text);
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 28px clamp(18px, 4vw, 54px);
      border-bottom: 1px solid rgba(255,255,255,.08);
      background: rgba(16, 20, 24, .72);
      backdrop-filter: blur(14px);
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    .brand {{ display: flex; align-items: center; gap: 14px; min-width: 0; }}
    .mark {{
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--green), var(--cyan));
      color: #071014;
      font-weight: 900;
      box-shadow: var(--shadow);
      flex: 0 0 auto;
    }}
    h1 {{ margin: 0; font-size: clamp(22px, 3vw, 34px); letter-spacing: 0; }}
    .subtitle {{ margin-top: 4px; color: var(--muted); font-size: 14px; }}
    .pill {{
      border: 1px solid rgba(56, 217, 150, .42);
      color: var(--green);
      background: rgba(56, 217, 150, .08);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      white-space: nowrap;
    }}
    main {{ padding: 32px clamp(18px, 4vw, 54px) 56px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 18px;
      max-width: 1180px;
      margin: 0 auto;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)), var(--panel);
      border: 1px solid rgba(255,255,255,.09);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .hero {{ grid-column: span 8; padding: 28px; min-height: 310px; display: flex; flex-direction: column; justify-content: space-between; }}
    .side {{ grid-column: span 4; padding: 22px; }}
    .wide {{ grid-column: span 7; padding: 22px; }}
    .api {{ grid-column: span 5; padding: 22px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }}
    .lead {{ max-width: 760px; color: #cfd8e3; font-size: clamp(17px, 2vw, 22px); line-height: 1.55; margin: 0; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 26px; }}
    .kpi {{ padding: 16px; background: var(--panel-2); border: 1px solid rgba(255,255,255,.07); border-radius: 8px; min-height: 92px; }}
    .kpi span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .kpi strong {{ display: block; margin-top: 10px; font-size: 22px; line-height: 1.1; overflow-wrap: anywhere; }}
    button, input {{
      font: inherit;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #0d1116;
      color: var(--text);
    }}
    button {{
      cursor: pointer;
      padding: 10px 13px;
      background: var(--panel-2);
    }}
    button.primary {{ background: linear-gradient(135deg, var(--green), var(--cyan)); color: #071014; border: 0; font-weight: 800; }}
    button:hover {{ filter: brightness(1.08); }}
    .stack {{ display: grid; gap: 12px; }}
    .endpoint {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.03); }}
    code {{ color: #b9f7d8; overflow-wrap: anywhere; }}
    .question {{ padding: 16px; border-radius: 8px; background: rgba(94, 200, 248, .08); border: 1px solid rgba(94, 200, 248, .22); line-height: 1.55; }}
    .question b {{ color: var(--cyan); }}
    .note-form {{ display: flex; gap: 10px; margin-bottom: 14px; }}
    .note-form input {{ flex: 1; min-width: 0; padding: 11px 12px; }}
    .notes {{ display: grid; gap: 10px; max-height: 260px; overflow: auto; }}
    .note {{ padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: rgba(255,255,255,.03); color: #d7e0ea; }}
    .note time {{ display: block; color: var(--muted); font-size: 12px; margin-top: 6px; }}
    footer {{ max-width: 1180px; margin: 22px auto 0; color: var(--muted); font-size: 13px; }}
    @media (max-width: 900px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      .hero, .side, .wide, .api {{ grid-column: 1 / -1; }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 560px) {{
      .kpis {{ grid-template-columns: 1fr; }}
      .note-form {{ flex-direction: column; }}
      .endpoint {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="mark">OPS</div>
      <div>
        <h1>{safe_name}</h1>
        <div class="subtitle">A production-minded Python web service in one file.</div>
      </div>
    </div>
    <div class="pill" id="live-pill">Checking...</div>
  </header>

  <main>
    <section class="grid">
      <div class="panel hero">
        <div>
          <h2>Runtime Dashboard</h2>
          <p class="lead">This service ships with a clean dashboard, health probes, JSON APIs, request counters, Prometheus metrics, structured logs, and zero third-party dependencies.</p>
        </div>
        <div class="kpis">
          <div class="kpi"><span>Status</span><strong id="status">--</strong></div>
          <div class="kpi"><span>Uptime</span><strong id="uptime">--</strong></div>
          <div class="kpi"><span>Requests</span><strong id="requests">--</strong></div>
          <div class="kpi"><span>Disk Used</span><strong id="disk">--</strong></div>
        </div>
      </div>

      <div class="panel side">
        <h2>Interview Drill</h2>
        <div class="stack">
          <div class="question" id="question">Loading...</div>
          <button class="primary" onclick="loadQuestion()">Next Question</button>
        </div>
      </div>

      <div class="panel wide">
        <h2>Scratch Notes</h2>
        <div class="note-form">
          <input id="note-input" maxlength="300" placeholder="Write a deployment note or interview keyword">
          <button class="primary" onclick="addNote()">Add</button>
        </div>
        <div class="notes" id="notes"></div>
      </div>

      <div class="panel api">
        <h2>API Surface</h2>
        <div class="stack">
          <div class="endpoint"><code>GET /healthz</code><span>Health probe</span></div>
          <div class="endpoint"><code>GET /api/status</code><span>Runtime status</span></div>
          <div class="endpoint"><code>GET /api/interview/random</code><span>Random question</span></div>
          <div class="endpoint"><code>GET /metrics</code><span>Prometheus metrics</span></div>
          <div class="endpoint"><code>POST /api/notes</code><span>JSON body: text</span></div>
        </div>
      </div>
    </section>
    <footer>Start with <code>HOST=0.0.0.0 PORT=8000 python app.py</code>. Put Nginx in front when exposing it to the internet.</footer>
  </main>

  <script>
    async function getJson(url, options) {{
      const res = await fetch(url, options);
      if (!res.ok) throw new Error(await res.text());
      return await res.json();
    }}

    async function refreshStatus() {{
      try {{
        const data = await getJson('/api/status');
        document.getElementById('status').textContent = data.status.toUpperCase();
        document.getElementById('uptime').textContent = data.uptime;
        document.getElementById('requests').textContent = data.requests_total;
        document.getElementById('disk').textContent = data.disk.used_percent + '%';
        document.getElementById('live-pill').textContent = data.hostname + ' online';
      }} catch (err) {{
        document.getElementById('live-pill').textContent = 'offline';
      }}
    }}

    async function loadQuestion() {{
      const item = await getJson('/api/interview/random');
      document.getElementById('question').innerHTML =
        '<b>' + escapeHtml(item.tag) + '</b><br>' +
        escapeHtml(item.question) + '<br><br>' +
        '<span>' + escapeHtml(item.answer) + '</span>';
    }}

    async function addNote() {{
      const input = document.getElementById('note-input');
      const text = input.value.trim();
      if (!text) return;
      await getJson('/api/notes', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{text}})
      }});
      input.value = '';
      await loadNotes();
      await refreshStatus();
    }}

    async function loadNotes() {{
      const data = await getJson('/api/notes');
      const root = document.getElementById('notes');
      if (!data.items.length) {{
        root.innerHTML = '<div class="note">No notes yet.</div>';
        return;
      }}
      root.innerHTML = data.items.map(item =>
        '<div class="note">' + escapeHtml(item.text) + '<time>' + escapeHtml(item.created_at) + '</time></div>'
      ).join('');
    }}

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, ch => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }}[ch]));
    }}

    document.getElementById('note-input').addEventListener('keydown', event => {{
      if (event.key === 'Enter') addNote();
    }});

    refreshStatus();
    loadQuestion();
    loadNotes();
    setInterval(refreshStatus, 5000);
  </script>
</body>
</html>"""


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(
        json.dumps(
            {
                "time": iso_now(),
                "event": "server_started",
                "app": APP_NAME,
                "version": APP_VERSION,
                "listen": f"http://{HOST}:{PORT}",
                "health": "/healthz",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
