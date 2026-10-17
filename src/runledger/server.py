"""Local dashboard. Binds to localhost and reads the same SQLite file as the CLI."""

from __future__ import annotations

import json
import platform
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from runledger import db, sampler, webhook

MAX_BODY = 1_000_000


def load_dashboard() -> bytes:
    path = Path(__file__).with_name("dashboard.html")
    if not path.is_file():
        html = (
            "<!doctype html><meta charset=utf-8><title>Run Ledger</title>"
            "<p>dashboard.html is missing from this install. "
            "Reinstall with <code>pip install -e .</code>.</p>"
        )
        return html.encode("utf-8")
    return path.read_bytes()


def machine_meta(db_path: Path) -> dict:
    present = sampler.nvidia_smi_path() is not None
    return {
        "hostname": platform.node() or "this machine",
        "platform": platform.system(),
        "python": platform.python_version(),
        "nvidia_smi": present,
        "sampler_note": "nvidia-smi on PATH" if present else "nvidia-smi not found",
        "db": str(db_path),
    }


def present_run(run: dict) -> dict:
    shown = dict(run)
    if run.get("ended_at"):
        shown["duration_sec"] = webhook.duration_sec(run)
    elif run.get("started_at"):
        try:
            started = datetime.fromisoformat(str(run["started_at"]))
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            shown["duration_sec"] = max(
                0.0, (datetime.now(timezone.utc) - started).total_seconds()
            )
        except ValueError:
            shown["duration_sec"] = None
    else:
        shown["duration_sec"] = None
    return shown


def validate_settings(body: dict) -> tuple[str, str, str]:
    url = str(body.get("webhook_url", "")).strip()
    fmt = str(body.get("webhook_format", "generic"))
    notify = str(body.get("notify_on", "both"))
    if url and not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    if fmt not in webhook.FORMATS:
        raise ValueError("format must be generic, wecom, dingtalk, or feishu")
    if notify not in webhook.NOTIFY:
        raise ValueError("notify must be both, finish, or crash")
    return url, fmt, notify


def make_handler(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                raise ValueError("body too large")
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path.rstrip("/") or "/"
                if path == "/":
                    self._send(200, load_dashboard(), "text/html; charset=utf-8")
                    return
                if path == "/api/meta":
                    self._json(200, machine_meta(db_path))
                    return
                if path == "/api/settings":
                    self._json(200, db.get_settings(db_path))
                    return
                if path == "/api/runs":
                    limit = 100
                    if parsed.query:
                        for part in parsed.query.split("&"):
                            if part.startswith("limit="):
                                try:
                                    limit = max(1, min(500, int(part.split("=", 1)[1])))
                                except ValueError:
                                    limit = 100
                    runs = [present_run(run) for run in db.list_runs(db_path, limit=limit)]
                    self._json(200, {"runs": runs, "meta": machine_meta(db_path)})
                    return
                if path.startswith("/api/runs/"):
                    id_text = path.removeprefix("/api/runs/")
                    if not id_text.isdigit():
                        self._json(404, {"error": "run not found"})
                        return
                    run = db.get_run(db_path, int(id_text))
                    if run is None:
                        self._json(404, {"error": "run not found"})
                        return
                    samples = db.get_samples(db_path, int(id_text))
                    gpus = sorted({sample["gpu_index"] for sample in samples})
                    self._json(
                        200,
                        {"run": present_run(run), "samples": samples, "gpus": gpus},
                    )
                    return
                self._json(404, {"error": "not found"})
            except Exception as exc:
                self._json(500, {"error": str(exc)})

        def do_POST(self) -> None:
            try:
                path = urlparse(self.path).path.rstrip("/") or "/"
                if path == "/api/settings":
                    url, fmt, notify = validate_settings(self._read_json())
                    saved = db.save_settings(
                        db_path,
                        webhook_url=url,
                        webhook_format=fmt,
                        notify_on=notify,
                    )
                    self._json(200, saved)
                    return
                if path == "/api/notify/test":
                    self._json(200, webhook.send_test(db_path))
                    return
                self._json(404, {"error": "not found"})
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid JSON"})
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:
                self._json(500, {"error": str(exc)})

    return Handler


def serve(
    host: str,
    port: int,
    db_path: Path,
    *,
    open_browser: bool = False,
    block: bool = True,
) -> ThreadingHTTPServer:
    db.init(db_path)
    httpd = ThreadingHTTPServer((host, port), make_handler(Path(db_path)))
    bound_host, bound_port = httpd.server_address[:2]
    visible_host = "127.0.0.1" if bound_host in ("0.0.0.0", "::") else bound_host
    url = f"http://{visible_host}:{bound_port}/"
    meta = machine_meta(db_path)
    print("Run Ledger")
    print(f"  dashboard   {url}")
    print(f"  database    {db_path}")
    print(f"  sampler     {meta['sampler_note']}")
    if open_browser:
        webbrowser.open(url)
    if not block:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return httpd
