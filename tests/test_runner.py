import sys

from runledger import db, runner


def test_display_command_stays_readable():
    assert runner.display_command(["python", "-c", "print('runledger-ok')"]) == "python -c print('runledger-ok')"
    shown = runner.display_command(["python3", "-c", "import time; print('hi')"])
    assert shown == 'python3 -c "import time; print(\'hi\')"'


def test_short_command_records_tail_and_sample(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    code = runner.execute(
        [sys.executable, "-c", "print('runledger-ok')"],
        db_path=db_path,
        echo=False,
    )
    assert code == 0
    run = db.list_runs(db_path)[0]
    assert run["status"] == "success"
    assert run["exit_code"] == 0
    assert "runledger-ok" in run["stdout_tail"]
    assert run["sampler"] in ("demo", "nvidia")
    samples = db.get_samples(db_path, run["id"])
    assert samples
    assert samples[0]["vram_used_mb"] is not None
    again = db.get_run(db_path, run["id"])
    assert again["command"]


def test_nonzero_exit_is_preserved(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    code = runner.execute(
        [sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); raise SystemExit(2)"],
        db_path=db_path,
        echo=False,
    )
    assert code == 2
    run = db.list_runs(db_path)[0]
    assert run["status"] == "failed"
    assert run["exit_code"] == 2
    assert "boom" in run["stderr_tail"]


def test_missing_command(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    code = runner.execute(["runledger-no-such-binary-xyz"], db_path=db_path, echo=False)
    assert code == 127
    run = db.list_runs(db_path)[0]
    assert run["status"] == "failed"
    assert "command not found" in run["stderr_tail"]


def test_tail_keeps_the_end(tmp_path):
    db_path = tmp_path / "runs.sqlite"
    script = "for i in range(400):\n print(f'line-{i}')\n"
    code = runner.execute([sys.executable, "-c", script], db_path=db_path, echo=False)
    assert code == 0
    tail = db.list_runs(db_path)[0]["stdout_tail"]
    assert "line-399" in tail
    assert "line-0\n" not in tail
