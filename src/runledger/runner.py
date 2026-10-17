"""Start a command, keep its ending, and sample the GPU while it runs."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from runledger import db, sampler, webhook

TAIL_LINES = 160
TAIL_CHARS = 24_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def display_command(argv: list[str]) -> str:
    """A readable command line. The real argv is stored separately as JSON."""
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    parts: list[str] = []
    for arg in argv:
        if arg and all(ch not in arg for ch in " \t\n\"\\"):
            parts.append(arg)
        else:
            escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'"{escaped}"')
    return " ".join(parts)


def _tail(lines: list[str]) -> str:
    text = "".join(lines[-TAIL_LINES:])
    if len(text) > TAIL_CHARS:
        text = text[-TAIL_CHARS:]
    return text


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")


def summary_line(run: dict, elapsed: float) -> str:
    parts = [
        f"runledger #{run.get('id')}",
        str(run.get("status") or "done"),
        f"exit {run.get('exit_code')}",
        webhook.format_duration(elapsed),
    ]
    peak = run.get("peak_vram_mb")
    if peak is not None:
        parts.append(f"peak {peak / 1024:.1f} GB")
    if run.get("sampler") == "nvidia":
        if run.get("peak_power_w") is not None:
            parts.append(f"{run['peak_power_w']:.0f} W")
        if run.get("peak_temp_c") is not None:
            parts.append(f"{run['peak_temp_c']:.0f}°C")
    else:
        parts.append("demo sampler")
    return "  ".join(parts)


def execute(
    argv: list[str],
    *,
    db_path: Path,
    interval: float = 3.0,
    echo: bool = True,
) -> int:
    if not argv:
        raise ValueError("missing command")
    interval = max(0.05, float(interval))
    db_path = Path(db_path)
    db.init(db_path)

    probed = sampler.query_nvidia()
    if probed:
        mode, note = "nvidia", "measured with nvidia-smi"
    else:
        mode, note = "demo", sampler.fallback_note()

    started_at = utc_now()
    started_mono = time.monotonic()
    run_id = db.insert_run(
        db_path,
        command=display_command(argv),
        argv=list(argv),
        cwd=os.getcwd(),
        started_at=started_at,
        sampler=mode,
        sampler_note=note,
        origin="wrap",
    )
    if probed:
        db.insert_samples(db_path, run_id, utc_now(), probed)
    else:
        db.insert_samples(db_path, run_id, utc_now(), sampler.demo_gpus(0.0, run_id))

    if echo and mode == "demo":
        print(
            f"runledger: {note}. The GPU curve will be simulated and labeled "
            '"demo sampler" on the dashboard. Exit code and logs are still real.',
            file=sys.stderr,
        )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    lock = threading.Lock()

    def pump(pipe, bucket, echo_stream) -> None:
        try:
            while True:
                raw = pipe.readline()
                if not raw:
                    break
                text = _decode(raw)
                if echo and echo_stream is not None:
                    echo_stream.write(text)
                    echo_stream.flush()
                with lock:
                    bucket.append(text)
                    if len(bucket) > TAIL_LINES + 40:
                        del bucket[:-TAIL_LINES]
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    child_env = os.environ.copy()
    child_env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        proc = subprocess.Popen(
            argv,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=child_env,
        )
    except OSError as exc:
        message = f"runledger: command not found: {argv[0]}\n{exc}\n"
        if echo:
            print(message, file=sys.stderr, end="")
        db.finish_run(
            db_path,
            run_id,
            ended_at=utc_now(),
            exit_code=127,
            status="failed",
            stdout_tail="",
            stderr_tail=message,
        )
        run = db.get_run(db_path, run_id) or {}
        webhook.maybe_notify(db_path, run)
        if echo:
            print(summary_line(run, time.monotonic() - started_mono), file=sys.stderr)
        return 127

    threads = [
        threading.Thread(target=pump, args=(proc.stdout, stdout_lines, sys.stdout), daemon=True),
        threading.Thread(target=pump, args=(proc.stderr, stderr_lines, sys.stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()

    stop = threading.Event()

    def sample_loop() -> None:
        while not stop.is_set():
            if stop.wait(interval):
                break
            elapsed = time.monotonic() - started_mono
            reading = sampler.read_once(elapsed, run_id, prefer=mode)
            db.insert_samples(db_path, run_id, utc_now(), reading.samples)
            with lock:
                out = _tail(stdout_lines)
                err = _tail(stderr_lines)
            db.update_live(db_path, run_id, out, err)

    sampler_thread = threading.Thread(target=sample_loop, daemon=True)
    sampler_thread.start()

    status = "failed"
    exit_code = 1
    try:
        exit_code = int(proc.wait())
        status = "success" if exit_code == 0 else "failed"
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        status = "interrupted"
        exit_code = 130
    finally:
        stop.set()
        sampler_thread.join(timeout=interval + 2)
        for thread in threads:
            thread.join(timeout=2)
        elapsed = time.monotonic() - started_mono
        reading = sampler.read_once(elapsed, run_id, prefer=mode)
        db.insert_samples(db_path, run_id, utc_now(), reading.samples)
        with lock:
            out = _tail(stdout_lines)
            err = _tail(stderr_lines)
        db.finish_run(
            db_path,
            run_id,
            ended_at=utc_now(),
            exit_code=exit_code,
            status=status,
            stdout_tail=out,
            stderr_tail=err,
        )
        run = db.get_run(db_path, run_id) or {"id": run_id, "status": status, "exit_code": exit_code}
        try:
            webhook.maybe_notify(db_path, run)
        except Exception as exc:
            db.set_webhook_result(db_path, run_id, "error", str(exc))
        if echo:
            fresh = db.get_run(db_path, run_id) or run
            print(summary_line(fresh, elapsed), file=sys.stderr)
    return exit_code
