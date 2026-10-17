"""SQLite notebook shared by the wrapper and the local page."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    argv_json TEXT NOT NULL,
    cwd TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    exit_code INTEGER,
    status TEXT NOT NULL,
    stdout_tail TEXT NOT NULL DEFAULT '',
    stderr_tail TEXT NOT NULL DEFAULT '',
    sampler TEXT NOT NULL,
    sampler_note TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'wrap',
    peak_vram_mb REAL,
    peak_power_w REAL,
    peak_temp_c REAL,
    peak_util_pct REAL,
    gpu_name TEXT,
    webhook_status TEXT,
    webhook_error TEXT
);

CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    ts TEXT NOT NULL,
    gpu_index INTEGER NOT NULL,
    gpu_name TEXT NOT NULL,
    vram_used_mb REAL,
    vram_total_mb REAL,
    power_w REAL,
    temp_c REAL,
    util_pct REAL
);

CREATE INDEX IF NOT EXISTS samples_run_id ON samples(run_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "webhook_url": "",
    "webhook_format": "generic",
    "notify_on": "both",
}


def default_db_path() -> Path:
    env = os.environ.get("RUNLEDGER_DB")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".runledger" / "runs.sqlite"


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init(path: Path) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def insert_run(
    path: Path,
    *,
    command: str,
    argv: list[str],
    cwd: str,
    started_at: str,
    sampler: str,
    sampler_note: str,
    origin: str = "wrap",
) -> int:
    init(path)
    with connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                command, argv_json, cwd, started_at, status, sampler, sampler_note, origin
            ) VALUES (?, ?, ?, ?, 'running', ?, ?, ?)
            """,
            (command, json.dumps(list(argv)), cwd, started_at, sampler, sampler_note, origin),
        )
        return int(cur.lastrowid)


def _recompute_peaks(conn: sqlite3.Connection, run_id: int) -> None:
    row = conn.execute(
        """
        SELECT
            MAX(vram_used_mb) AS peak_vram_mb,
            MAX(power_w) AS peak_power_w,
            MAX(temp_c) AS peak_temp_c,
            MAX(util_pct) AS peak_util_pct
        FROM samples WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    name = conn.execute(
        "SELECT gpu_name FROM samples WHERE run_id = ? ORDER BY id LIMIT 1",
        (run_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE runs
        SET peak_vram_mb = ?, peak_power_w = ?, peak_temp_c = ?, peak_util_pct = ?, gpu_name = ?
        WHERE id = ?
        """,
        (
            row["peak_vram_mb"],
            row["peak_power_w"],
            row["peak_temp_c"],
            row["peak_util_pct"],
            name["gpu_name"] if name else None,
            run_id,
        ),
    )


def insert_samples(path: Path, run_id: int, ts: str, gpus: list[Any]) -> None:
    if not gpus:
        return
    rows = [
        (
            run_id,
            ts,
            gpu.gpu_index,
            gpu.gpu_name,
            gpu.vram_used_mb,
            gpu.vram_total_mb,
            gpu.power_w,
            gpu.temp_c,
            gpu.util_pct,
        )
        for gpu in gpus
    ]
    with connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO samples (
                run_id, ts, gpu_index, gpu_name,
                vram_used_mb, vram_total_mb, power_w, temp_c, util_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        _recompute_peaks(conn, run_id)


def insert_sample_rows(path: Path, run_id: int, rows: list[tuple]) -> None:
    """Bulk insert (ts, gpu_index, gpu_name, vram_used, vram_total, power, temp, util)."""
    if not rows:
        return
    with connect(path) as conn:
        conn.executemany(
            """
            INSERT INTO samples (
                run_id, ts, gpu_index, gpu_name,
                vram_used_mb, vram_total_mb, power_w, temp_c, util_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(run_id, *row) for row in rows],
        )
        _recompute_peaks(conn, run_id)


def update_live(path: Path, run_id: int, stdout_tail: str, stderr_tail: str) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            UPDATE runs SET stdout_tail = ?, stderr_tail = ?
            WHERE id = ? AND status = 'running'
            """,
            (stdout_tail, stderr_tail, run_id),
        )


def finish_run(
    path: Path,
    run_id: int,
    *,
    ended_at: str,
    exit_code: int,
    status: str,
    stdout_tail: str,
    stderr_tail: str,
) -> None:
    with connect(path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET ended_at = ?, exit_code = ?, status = ?, stdout_tail = ?, stderr_tail = ?
            WHERE id = ?
            """,
            (ended_at, exit_code, status, stdout_tail, stderr_tail, run_id),
        )


def set_webhook_result(path: Path, run_id: int, status: str | None, error: str | None) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE runs SET webhook_status = ?, webhook_error = ? WHERE id = ?",
            (status, error, run_id),
        )


def list_runs(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    init(path)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [row for row in (_as_dict(item) for item in rows) if row is not None]


def get_run(path: Path, run_id: int) -> dict[str, Any] | None:
    init(path)
    with connect(path) as conn:
        return _as_dict(conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())


def get_samples(path: Path, run_id: int) -> list[dict[str, Any]]:
    init(path)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM samples WHERE run_id = ? ORDER BY ts, gpu_index, id",
            (run_id,),
        ).fetchall()
    return [row for row in (_as_dict(item) for item in rows) if row is not None]


def get_settings(path: Path) -> dict[str, str]:
    init(path)
    with connect(path) as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    found = {row["key"]: row["value"] for row in rows}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(found)
    return merged


def save_settings(
    path: Path,
    *,
    webhook_url: str,
    webhook_format: str,
    notify_on: str,
) -> dict[str, str]:
    init(path)
    pairs = {
        "webhook_url": webhook_url,
        "webhook_format": webhook_format,
        "notify_on": notify_on,
    }
    with connect(path) as conn:
        for key, value in pairs.items():
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
    return get_settings(path)


def delete_seed(path: Path) -> int:
    init(path)
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM runs WHERE origin = 'seed'")
        return int(cur.rowcount)


def insert_finished_run(path: Path, **fields: Any) -> int:
    """Insert a completed run. Samples are added by the caller."""
    init(path)
    with connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                command, argv_json, cwd, started_at, ended_at, exit_code, status,
                stdout_tail, stderr_tail, sampler, sampler_note, origin, gpu_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields["command"],
                json.dumps(fields.get("argv") or []),
                fields.get("cwd") or "",
                fields["started_at"],
                fields["ended_at"],
                fields["exit_code"],
                fields["status"],
                fields.get("stdout_tail") or "",
                fields.get("stderr_tail") or "",
                fields.get("sampler") or "demo",
                fields.get("sampler_note") or "",
                fields.get("origin") or "seed",
                fields.get("gpu_name"),
            ),
        )
        return int(cur.lastrowid)
