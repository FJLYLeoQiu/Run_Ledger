"""Command line for wrapping jobs, reading the ledger, and opening the page."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from runledger import __version__, db, demo_data, runner, server, webhook

HELP = """\
Run Ledger — flight recorder for the GPU on your desk.

  runledger -- <command> [args...]
      Run a command and record the ending: time, exit code, log tail, GPU curve.
  runledger serve [--host 127.0.0.1] [--port 8765] [--open]
      Open the local dashboard. Nothing is loaded from the internet.
  runledger list
      Recent runs in the terminal.
  runledger show <id>
      One run, including the log tail.
  runledger notify <url> --format generic|wecom|dingtalk|feishu
  runledger notify --on both|finish|crash
  runledger notify --off
  runledger notify --test
      Where to POST when a job finishes or crashes. No URL means no request.
  runledger demo
      Insert labeled example runs (a train, ComfyUI, a local LLM, an OOM).
      Replaces earlier examples. Real wrapped runs are kept.

  --db PATH            SQLite file (default: ~/.runledger/runs.sqlite)
  --interval SECONDS   Sample gap while wrapping (default: 3)
  --version

The exit code of `runledger -- <command>` is the command's exit code.
A missing program exits 127. Ctrl+C records the run as interrupted and exits 130.
"""


def _print_run_line(run: dict) -> None:
    duration = webhook.format_duration(run.get("duration_sec"))
    if run.get("duration_sec") is None and run.get("status") == "running":
        duration = "running"
    command = run.get("command") or ""
    if len(command) > 72:
        command = command[:69] + "..."
    print(
        f"#{run['id']:<4}  {run['status']:<11}  {duration:<10}  {command}"
    )


def _annotate(run: dict) -> dict:
    shown = server.present_run(run)
    return shown


def cmd_list(db_path: Path, limit: int) -> int:
    runs = db.list_runs(db_path, limit=limit)
    if not runs:
        print("No runs yet. Wrap one with:  runledger -- python train.py")
        return 0
    for run in runs:
        _print_run_line(_annotate(run))
    return 0


def cmd_show(db_path: Path, run_id: int) -> int:
    run = db.get_run(db_path, run_id)
    if run is None:
        print(f"runledger: no run #{run_id}", file=sys.stderr)
        return 1
    run = _annotate(run)
    print(
        f"#{run['id']}  {run['status']}  exit {run['exit_code']}  "
        f"{webhook.format_duration(run.get('duration_sec'))}"
    )
    print(run["command"])
    print(f"cwd      {run['cwd']}")
    print(f"sampler  {run['sampler']} — {run['sampler_note']}")
    if run.get("peak_vram_mb") is not None:
        power = "—" if run.get("peak_power_w") is None else f"{run['peak_power_w']:.0f} W"
        temp = "—" if run.get("peak_temp_c") is None else f"{run['peak_temp_c']:.0f}°C"
        util = "—" if run.get("peak_util_pct") is None else f"{run['peak_util_pct']:.0f}%"
        print(f"peak     {run['peak_vram_mb'] / 1024:.1f} GB  {power}  {temp}  {util}")
    if run.get("webhook_status"):
        extra = f" — {run['webhook_error']}" if run.get("webhook_error") else ""
        print(f"webhook  {run['webhook_status']}{extra}")
    print("\nstdout tail:")
    print(run.get("stdout_tail") or "(empty)")
    print("\nstderr tail:")
    print(run.get("stderr_tail") or "(empty)")
    return 0


def cmd_notify(db_path: Path, args: argparse.Namespace) -> int:
    current = db.get_settings(db_path)
    if args.test:
        if args.url:
            current = db.save_settings(
                db_path,
                webhook_url=args.url,
                webhook_format=args.format or current["webhook_format"],
                notify_on=args.on or current["notify_on"],
            )
        result = webhook.send_test(db_path)
        if result.get("ok"):
            print(f"Test ping delivered (HTTP {result['status']}).")
            return 0
        print(f"Test ping failed: {result.get('error') or result.get('status')}", file=sys.stderr)
        return 1
    if args.off:
        db.save_settings(
            db_path,
            webhook_url="",
            webhook_format=args.format or current["webhook_format"],
            notify_on=args.on or current["notify_on"],
        )
        print("Webhook cleared. Runs stay on this machine.")
        return 0
    if args.url or args.format or args.on:
        url = args.url if args.url is not None else current["webhook_url"]
        fmt = args.format or current["webhook_format"]
        notify = args.on or current["notify_on"]
        if url and not (url.startswith("http://") or url.startswith("https://")):
            print("runledger: webhook URL must start with http:// or https://", file=sys.stderr)
            return 2
        saved = db.save_settings(
            db_path, webhook_url=url, webhook_format=fmt, notify_on=notify
        )
        if saved["webhook_url"]:
            print(
                f"Webhook on ({saved['webhook_format']}, {saved['notify_on']}): "
                f"{saved['webhook_url']}"
            )
        else:
            print(f"Format {saved['webhook_format']}, notify {saved['notify_on']}. No URL yet.")
        return 0
    if current["webhook_url"]:
        print(
            f"{current['webhook_format']}  {current['notify_on']}  {current['webhook_url']}"
        )
    else:
        print("No webhook. Nothing leaves this machine until you set a URL.")
    return 0


def dispatch(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    db_override: Path | None = None
    interval: float | None = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--db" and index + 1 < len(argv):
            db_override = Path(argv[index + 1])
            index += 2
            continue
        if token == "--interval" and index + 1 < len(argv):
            try:
                interval = float(argv[index + 1])
            except ValueError:
                print("runledger: --interval needs a number of seconds", file=sys.stderr)
                return 2
            index += 2
            continue
        break
    rest = argv[index:]
    db_path = db_override or db.default_db_path()

    if not rest or rest[0] in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if rest[0] in ("-V", "--version", "version"):
        print(__version__)
        return 0

    command = rest[0]
    if command in ("--", "run"):
        wrapped = rest[1:]
        if not wrapped:
            print("runledger: missing command. Example: runledger -- python train.py", file=sys.stderr)
            return 2
        return runner.execute(wrapped, db_path=db_path, interval=interval or 3.0)

    if command == "serve":
        parser = argparse.ArgumentParser(prog="runledger serve", add_help=True)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8765)
        parser.add_argument("--open", action="store_true")
        try:
            args = parser.parse_args(rest[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        server.serve(args.host, args.port, db_path, open_browser=args.open, block=True)
        return 0

    if command == "list":
        parser = argparse.ArgumentParser(prog="runledger list")
        parser.add_argument("--limit", type=int, default=20)
        try:
            args = parser.parse_args(rest[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        return cmd_list(db_path, args.limit)

    if command == "show":
        parser = argparse.ArgumentParser(prog="runledger show")
        parser.add_argument("run_id", type=int)
        try:
            args = parser.parse_args(rest[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        return cmd_show(db_path, args.run_id)

    if command == "notify":
        parser = argparse.ArgumentParser(prog="runledger notify")
        parser.add_argument("url", nargs="?")
        parser.add_argument("--format", choices=webhook.FORMATS)
        parser.add_argument("--on", choices=webhook.NOTIFY)
        parser.add_argument("--off", action="store_true")
        parser.add_argument("--test", action="store_true")
        try:
            args = parser.parse_args(rest[1:])
        except SystemExit as exc:
            return int(exc.code or 0)
        return cmd_notify(db_path, args)

    if command == "demo":
        removed, ids = demo_data.seed(db_path)
        print(
            f"Inserted {len(ids)} simulated examples (#{ids[0]}–#{ids[-1]}). "
            f"Removed {removed} older examples. Real runs were kept."
        )
        print("These curves are not measurements. The dashboard badges them as simulated.")
        print("Open them with:  runledger serve")
        return 0

    print(
        f"runledger: unknown command {command!r}. "
        "Wrap a program with: runledger -- <command>",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(dispatch(argv))
