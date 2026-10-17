"""One POST when a run finishes or crashes. Four body shapes, no account of our own."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from runledger import db

FORMATS = ("generic", "wecom", "dingtalk", "feishu")
NOTIFY = ("both", "finish", "crash")


def duration_sec(run: dict[str, Any]) -> float | None:
    start, end = run.get("started_at"), run.get("ended_at")
    if not start or not end:
        return None
    try:
        began = datetime.fromisoformat(str(start))
        finished = datetime.fromisoformat(str(end))
    except ValueError:
        return None
    return max(0.0, (finished - began).total_seconds())


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _gb(mb: float | None) -> str:
    if mb is None:
        return "—"
    return f"{mb / 1024:.1f} GB"


def _num(value: float | None, kind: str) -> str:
    if value is None:
        return "—"
    if kind == "W":
        return f"{value:.0f} W"
    if kind == "C":
        return f"{value:.0f}°C"
    if kind == "%":
        return f"{value:.0f}%"
    return f"{value:.0f}"


def _command(run: dict[str, Any]) -> str:
    text = str(run.get("command") or "").replace("`", "'")
    if len(text) > 180:
        return text[:177] + "..."
    return text


def event_name(run: dict[str, Any]) -> str:
    return "run.finished" if run.get("status") == "success" else "run.crashed"


def summary_lines(run: dict[str, Any]) -> list[str]:
    label = "finished" if event_name(run) == "run.finished" else str(run.get("status") or "crashed")
    exit_code = run.get("exit_code")
    exit_text = "—" if exit_code is None else str(exit_code)
    peaks = " · ".join(
        [
            _gb(run.get("peak_vram_mb")),
            _num(run.get("peak_power_w"), "W"),
            _num(run.get("peak_temp_c"), "C"),
            _num(run.get("peak_util_pct"), "%"),
        ]
    )
    sampler = "demo sampler" if run.get("sampler") == "demo" else "measured with nvidia-smi"
    lines = [
        f"Run Ledger · {label}",
        _command(run),
        f"exit {exit_text} · {format_duration(duration_sec(run))}",
        f"peak {peaks}",
        sampler,
    ]
    if run.get("status") != "success":
        err_lines = str(run.get("stderr_tail") or "").strip().splitlines()
        if err_lines:
            last = err_lines[-1].strip().replace("`", "'")
            if len(last) > 200:
                last = last[:197] + "..."
            lines.append(last)
    return lines


def build_payload(fmt: str, run: dict[str, Any]) -> dict[str, Any]:
    lines = summary_lines(run)
    event = event_name(run)
    if fmt == "wecom":
        color = "info" if event == "run.finished" else "warning"
        body = "\n".join(f"> {line}" for line in lines[1:])
        content = f'### <font color="{color}">{lines[0]}</font>\n{body}'
        return {"msgtype": "markdown", "markdown": {"content": content}}
    if fmt == "dingtalk":
        text = "### " + lines[0] + "\n\n" + "\n\n".join(f"- {line}" for line in lines[1:])
        return {"msgtype": "markdown", "markdown": {"title": "Run Ledger", "text": text}}
    if fmt == "feishu":
        template = "green" if event == "run.finished" else "red"
        md = f"**{lines[1]}**\n" + "\n".join(lines[2:])
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": lines[0]},
                    "template": template,
                },
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": md}}],
            },
        }
    return {
        "source": "runledger",
        "event": event,
        "run": {
            "id": run.get("id"),
            "command": run.get("command"),
            "status": run.get("status"),
            "exit_code": run.get("exit_code"),
            "started_at": run.get("started_at"),
            "ended_at": run.get("ended_at"),
            "duration_sec": duration_sec(run),
            "sampler": run.get("sampler"),
            "origin": run.get("origin"),
            "peaks": {
                "vram_mb": run.get("peak_vram_mb"),
                "power_w": run.get("peak_power_w"),
                "temp_c": run.get("peak_temp_c"),
                "util_pct": run.get("peak_util_pct"),
            },
            "stdout_tail": str(run.get("stdout_tail") or "")[-2000:],
            "stderr_tail": str(run.get("stderr_tail") or "")[-2000:],
        },
    }


def post_json(url: str, payload: dict[str, Any], timeout: float = 5.0) -> tuple[str, str | None]:
    if not (url.startswith("http://") or url.startswith("https://")):
        return "error", "webhook URL must start with http:// or https://"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "runledger/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return str(response.status), None
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode("utf-8", "replace").strip()
        return str(exc.code), detail or str(exc.reason)
    except Exception as exc:
        return "error", str(exc)


def _allows(notify_on: str, event: str) -> bool:
    if notify_on == "finish":
        return event == "run.finished"
    if notify_on == "crash":
        return event == "run.crashed"
    return True


def maybe_notify(db_path, run: dict[str, Any] | None) -> None:
    if not run or run.get("status") in (None, "running"):
        return
    settings = db.get_settings(db_path)
    url = (settings.get("webhook_url") or "").strip()
    if not url:
        return
    event = event_name(run)
    if not _allows(settings.get("notify_on") or "both", event):
        return
    fmt = settings.get("webhook_format") or "generic"
    if fmt not in FORMATS:
        fmt = "generic"
    status, error = post_json(url, build_payload(fmt, run))
    if run.get("id"):
        db.set_webhook_result(db_path, int(run["id"]), status, error)


def send_test(db_path) -> dict[str, Any]:
    settings = db.get_settings(db_path)
    url = (settings.get("webhook_url") or "").strip()
    if not url:
        return {"ok": False, "error": "Save a webhook URL first.", "status": None, "payload": None}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fake = {
        "id": 0,
        "command": "runledger notify test",
        "status": "success",
        "exit_code": 0,
        "started_at": now,
        "ended_at": now,
        "sampler": "demo",
        "origin": "wrap",
        "peak_vram_mb": 18432,
        "peak_power_w": 320,
        "peak_temp_c": 71,
        "peak_util_pct": 97,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    fmt = settings.get("webhook_format") or "generic"
    if fmt not in FORMATS:
        fmt = "generic"
    payload = build_payload(fmt, fake)
    status, error = post_json(url, payload)
    ok = error is None and status.isdigit() and status.startswith("2")
    return {"ok": ok, "status": status, "error": error, "payload": payload}
