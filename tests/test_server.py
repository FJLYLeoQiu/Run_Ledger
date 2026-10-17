import json
import sys
import urllib.error
import urllib.request

from runledger import cli, db, runner, server


def _start(db_path):
    httpd = server.serve("127.0.0.1", 0, db_path, block=False)
    port = httpd.server_address[1]
    return httpd, port


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as response:
        body = response.read()
        return response.status, response.headers.get("Content-Type", ""), body


def test_page_and_api_show_wrapped_run(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    code = runner.execute(
        [sys.executable, "-c", "print('runledger-ok')"],
        db_path=db_path,
        echo=False,
    )
    assert code == 0
    httpd, port = _start(db_path)
    try:
        status, content_type, body = _get(port, "/")
        html = body.decode("utf-8")
        assert status == 200
        assert "text/html" in content_type
        assert "Run Ledger" in html
        assert "fonts.googleapis" not in html
        assert "<script src=" not in html
        assert "stylesheet" not in html.lower() or "href=\"http" not in html

        status, _, body = _get(port, "/api/runs")
        payload = json.loads(body)
        assert status == 200
        assert payload["runs"]
        assert payload["runs"][0]["exit_code"] == 0
        assert "runledger-ok" in payload["runs"][0]["stdout_tail"]
        run_id = payload["runs"][0]["id"]

        status, _, body = _get(port, f"/api/runs/{run_id}")
        detail = json.loads(body)
        assert detail["samples"]
        assert detail["run"]["command"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_empty_ledger_and_settings(tmp_path):
    db_path = tmp_path / "empty.sqlite"
    httpd, port = _start(db_path)
    try:
        _, _, body = _get(port, "/api/runs")
        payload = json.loads(body)
        assert payload["runs"] == []
        assert "sampler_note" in payload["meta"]

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/settings",
            data=json.dumps(
                {
                    "webhook_url": "https://example.com/hook",
                    "webhook_format": "feishu",
                    "notify_on": "crash",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            saved = json.loads(response.read())
        assert saved["webhook_format"] == "feishu"
        assert db.get_settings(db_path)["notify_on"] == "crash"

        bad = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/settings",
            data=json.dumps(
                {"webhook_url": "ftp://nope", "webhook_format": "generic", "notify_on": "both"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad)
            raised = False
        except urllib.error.HTTPError as exc:
            raised = True
            assert exc.code == 400
        assert raised
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_demo_seed_keeps_real_wrap(tmp_path, monkeypatch):
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("RUNLEDGER_DB", str(db_path))
    assert cli.dispatch(["--", sys.executable, "-c", "print('kept')"]) == 0
    assert cli.dispatch(["demo"]) == 0
    assert cli.dispatch(["demo"]) == 0
    runs = db.list_runs(db_path, limit=20)
    wraps = [run for run in runs if run["origin"] == "wrap"]
    seeds = [run for run in runs if run["origin"] == "seed"]
    assert len(wraps) == 1
    assert "kept" in wraps[0]["stdout_tail"]
    assert len(seeds) == 4
    assert all(run["sampler_note"].startswith("Simulated example") for run in seeds)
    oom = next(run for run in seeds if run["status"] == "failed")
    assert "OutOfMemory" in oom["stderr_tail"]
    assert db.get_samples(db_path, oom["id"])


def test_cli_help_and_list(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "runs.sqlite"
    monkeypatch.setenv("RUNLEDGER_DB", str(db_path))
    assert cli.dispatch(["--help"]) == 0
    assert "runledger --" in capsys.readouterr().out
    assert cli.dispatch(["--", sys.executable, "-c", "print('from-cli')"]) == 0
    captured = capsys.readouterr()
    assert "from-cli" in captured.out
    assert "runledger #" in captured.err
    assert cli.dispatch(["list"]) == 0
    assert "success" in capsys.readouterr().out
    assert cli.dispatch(["show", "1"]) == 0
    shown = capsys.readouterr().out
    assert "from-cli" in shown
