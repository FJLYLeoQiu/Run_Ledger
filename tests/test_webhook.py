import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from runledger import db, runner, webhook


def _run(**overrides):
    now = datetime.now(timezone.utc)
    base = {
        "id": 7,
        "command": "python train_lora.py --rank 64",
        "status": "failed",
        "exit_code": 1,
        "started_at": (now - timedelta(minutes=8)).isoformat(timespec="seconds"),
        "ended_at": now.isoformat(timespec="seconds"),
        "sampler": "demo",
        "origin": "wrap",
        "peak_vram_mb": 24000,
        "peak_power_w": 401,
        "peak_temp_c": 79,
        "peak_util_pct": 99,
        "stdout_tail": "",
        "stderr_tail": "torch.OutOfMemoryError: CUDA out of memory\n",
    }
    base.update(overrides)
    return base


def test_payload_shapes():
    run = _run()
    generic = webhook.build_payload("generic", run)
    assert generic["event"] == "run.crashed"
    assert generic["run"]["exit_code"] == 1
    assert generic["run"]["peaks"]["vram_mb"] == 24000

    wecom = webhook.build_payload("wecom", run)
    assert wecom["msgtype"] == "markdown"
    assert "exit 1" in wecom["markdown"]["content"]
    assert "OutOfMemory" in wecom["markdown"]["content"]

    dingtalk = webhook.build_payload("dingtalk", run)
    assert dingtalk["msgtype"] == "markdown"
    assert dingtalk["markdown"]["title"] == "Run Ledger"

    feishu = webhook.build_payload("feishu", run)
    assert feishu["msg_type"] == "interactive"
    assert feishu["card"]["header"]["template"] == "red"

    ok = webhook.build_payload("generic", _run(status="success", exit_code=0, stderr_tail=""))
    assert ok["event"] == "run.finished"


def test_duration_format():
    assert webhook.format_duration(4) == "4s"
    assert webhook.format_duration(125) == "2m 05s"
    assert webhook.format_duration(3700) == "1h 01m"


class _Catch(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        self.server.bodies.append(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args):
        return


@pytest.fixture
def catcher():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Catch)
    httpd.bodies = []
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_failed_run_posts_wecom(tmp_path, catcher):
    import sys

    db_path = tmp_path / "runs.sqlite"
    port = catcher.server_address[1]
    db.save_settings(
        db_path,
        webhook_url=f"http://127.0.0.1:{port}/hook",
        webhook_format="wecom",
        notify_on="both",
    )
    code = runner.execute(
        [sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); raise SystemExit(2)"],
        db_path=db_path,
        echo=False,
    )
    assert code == 2
    assert catcher.bodies
    body = catcher.bodies[0]
    assert body["msgtype"] == "markdown"
    assert "exit 2" in body["markdown"]["content"]
    assert "boom" in body["markdown"]["content"]
    stored = db.list_runs(db_path)[0]
    assert stored["webhook_status"] == "200"


def test_crash_only_skips_success(tmp_path, catcher):
    import sys

    db_path = tmp_path / "runs.sqlite"
    port = catcher.server_address[1]
    db.save_settings(
        db_path,
        webhook_url=f"http://127.0.0.1:{port}/hook",
        webhook_format="generic",
        notify_on="crash",
    )
    code = runner.execute(
        [sys.executable, "-c", "print('fine')"],
        db_path=db_path,
        echo=False,
    )
    assert code == 0
    assert catcher.bodies == []
    assert db.list_runs(db_path)[0]["webhook_status"] is None


def test_bad_url_does_not_change_exit_code(tmp_path):
    import sys

    db_path = tmp_path / "runs.sqlite"
    db.save_settings(
        db_path,
        webhook_url="http://127.0.0.1:1/nowhere",
        webhook_format="dingtalk",
        notify_on="both",
    )
    code = runner.execute(
        [sys.executable, "-c", "print('still-ok')"],
        db_path=db_path,
        echo=False,
    )
    assert code == 0
    stored = db.list_runs(db_path)[0]
    assert stored["webhook_status"] == "error"
    assert stored["webhook_error"]
