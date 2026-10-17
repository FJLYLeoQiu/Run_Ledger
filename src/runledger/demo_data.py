"""Labeled example runs so the page can be shown on a machine with no GPU."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runledger import db

NOTE = "Simulated example from `runledger demo`. Not a measurement from this machine."
GPU = "Demo GPU (simulated example)"
TOTAL = 24564.0


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _rows(started: datetime, count: int, step_s: int, fn) -> list[tuple]:
    rows = []
    for index in range(count):
        moment = started + timedelta(seconds=index * step_s)
        vram, power, temp, util = fn(index, count)
        rows.append(
            (
                _iso(moment),
                0,
                GPU,
                round(vram, 1),
                TOTAL,
                round(power, 1),
                round(temp, 1),
                round(util, 1),
            )
        )
    return rows


def _lora(index: int, count: int):
    t = index / max(1, count - 1)
    ramp = min(1.0, t / 0.18)
    frac = min(0.96, 0.10 + 0.78 * ramp + 0.012 * math.sin(index / 4))
    util = 90 + 7 * math.sin(index / 5) if ramp >= 1 else 35 + 55 * ramp
    util = max(0.0, min(99.0, util))
    power = 50 + util * 3.25
    temp = 41 + 33 * (1 - math.exp(-t * 4)) + util * 0.02
    return TOTAL * frac, power, temp, util


def _comfy(index: int, count: int):
    cycle = index % 18
    rising = cycle / 17
    frac = 0.22 if cycle > 15 else 0.30 + 0.46 * rising
    util = 8 if cycle > 15 else 18 + 74 * rising
    power = 42 + util * 3.1
    temp = 51 + 7 * math.sin(index / 14)
    return TOTAL * frac, power, temp, util


def _llama(index: int, count: int):
    frac = 0.535 + 0.012 * math.sin(index / 11)
    burst = abs(math.sin(index / 6.5)) ** 2
    util = 5 + 68 * burst
    power = 58 + util * 2.3
    temp = 54 + 5 * math.sin(index / 28)
    return TOTAL * frac, power, temp, util


def _oom(index: int, count: int):
    t = index / max(1, count - 1)
    frac = min(0.995, 0.16 + 0.84 * (t ** 1.2))
    util = min(100.0, 72 + 28 * t)
    power = 90 + util * 3.15
    temp = 44 + 36 * t
    return TOTAL * frac, power, temp, util


def _story(
    *,
    ended_ago: timedelta,
    duration: timedelta,
    step_s: int,
    fn,
    command: str,
    cwd: str,
    status: str,
    exit_code: int,
    stdout_tail: str,
    stderr_tail: str,
) -> dict:
    now = datetime.now(timezone.utc)
    ended = now - ended_ago
    count = int(duration.total_seconds() // step_s) + 1
    started = ended - timedelta(seconds=(count - 1) * step_s)
    return {
        "command": command,
        "cwd": cwd,
        "started_at": _iso(started),
        "ended_at": _iso(ended),
        "exit_code": exit_code,
        "status": status,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "rows": _rows(started, count, step_s, fn),
    }


def stories() -> list[dict]:
    return [
        _story(
            ended_ago=timedelta(hours=30),
            duration=timedelta(minutes=96),
            step_s=20,
            fn=_llama,
            command="llama-server -m qwen2.5-14b-q4_k_m.gguf -c 8192 --port 8080",
            cwd="D:/models",
            status="success",
            exit_code=0,
            stdout_tail=(
                "llama server listening on http://127.0.0.1:8080\n"
                "slot 0 | load Qwen2.5-14B Q4_K_M | 13.1 GB\n"
                "slot 0 | task 12 | prompt 1860 tokens | gen 420 tokens\n"
                "slot 0 | task 48 | stop | tps 41.2\n"
            ),
            stderr_tail="",
        ),
        _story(
            ended_ago=timedelta(hours=9),
            duration=timedelta(minutes=22),
            step_s=10,
            fn=_comfy,
            command="python main.py --listen 127.0.0.1 --port 8188",
            cwd="D:/work/ComfyUI",
            status="success",
            exit_code=0,
            stdout_tail=(
                "To see the GUI go to: http://127.0.0.1:8188\n"
                "got prompt\n"
                "Prompt executed in 14.22 seconds\n"
                "got prompt\n"
                "Prompt executed in 11.80 seconds\n"
            ),
            stderr_tail="",
        ),
        _story(
            ended_ago=timedelta(hours=3),
            duration=timedelta(minutes=42),
            step_s=12,
            fn=_lora,
            command="python train_lora.py --rank 16 --steps 1200 --dataset ./chars",
            cwd="D:/work/char-lora",
            status="success",
            exit_code=0,
            stdout_tail=(
                "epoch 1/8  step 200  loss 0.482\n"
                "epoch 3/8  step 600  loss 0.231\n"
                "epoch 8/8  step 1200 loss 0.094\n"
                "saved ./out/char-lora.safetensors\n"
            ),
            stderr_tail="",
        ),
        _story(
            ended_ago=timedelta(minutes=40),
            duration=timedelta(minutes=8),
            step_s=6,
            fn=_oom,
            command="python train_lora.py --rank 64 --batch 8",
            cwd="D:/work/char-lora",
            status="failed",
            exit_code=1,
            stdout_tail="epoch 1/8  step 40  loss 0.611\nstep 80  allocating activation\n",
            stderr_tail=(
                "Traceback (most recent call last):\n"
                '  File "train_lora.py", line 214, in <module>\n'
                "    loss.backward()\n"
                "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 1.20 GiB. "
                "GPU 0 has a total capacity of 23.99 GiB of which 184.00 MiB is free. "
                "Process 4412 has 23.10 GiB memory in use.\n"
            ),
        ),
    ]


def seed(db_path: Path) -> tuple[int, list[int]]:
    """Replace previous examples. Real wrapped runs stay."""
    removed = db.delete_seed(db_path)
    ids: list[int] = []
    for story in stories():
        rows = story.pop("rows")
        run_id = db.insert_finished_run(
            db_path,
            sampler="demo",
            sampler_note=NOTE,
            origin="seed",
            gpu_name=GPU,
            **story,
        )
        db.insert_sample_rows(db_path, run_id, rows)
        ids.append(run_id)
    return removed, ids
