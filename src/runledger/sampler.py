"""nvidia-smi snapshots, or a labeled demo curve when the driver tool is missing."""

from __future__ import annotations

import csv
import io
import math
import shutil
import subprocess
from dataclasses import dataclass

NA_TOKENS = {"", "N/A", "[N/A]", "[Not Supported]", "[Insufficient Permissions]"}

NVIDIA_ARGS = [
    "--query-gpu=index,name,memory.used,memory.total,power.draw,temperature.gpu,utilization.gpu",
    "--format=csv,noheader,nounits",
]

DEMO_GPU_NAME = "Demo GPU (nvidia-smi unavailable)"
DEMO_TOTAL_MB = 24564.0


@dataclass
class GpuSample:
    gpu_index: int
    gpu_name: str
    vram_used_mb: float | None
    vram_total_mb: float | None
    power_w: float | None
    temp_c: float | None
    util_pct: float | None


@dataclass
class SampleReading:
    mode: str
    note: str
    samples: list[GpuSample]


def nvidia_smi_path() -> str | None:
    return shutil.which("nvidia-smi")


def _num(text: str) -> float | None:
    text = text.strip()
    if text in NA_TOKENS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_nvidia_csv(text: str) -> list[GpuSample]:
    samples: list[GpuSample] = []
    for parts in csv.reader(io.StringIO(text)):
        if len(parts) < 7:
            continue
        parts = [part.strip() for part in parts]
        try:
            index = int(float(parts[0]))
        except ValueError:
            continue
        samples.append(
            GpuSample(
                gpu_index=index,
                gpu_name=parts[1] or "GPU",
                vram_used_mb=_num(parts[2]),
                vram_total_mb=_num(parts[3]),
                power_w=_num(parts[4]),
                temp_c=_num(parts[5]),
                util_pct=_num(parts[6]),
            )
        )
    return samples


def query_nvidia() -> list[GpuSample] | None:
    exe = nvidia_smi_path()
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, *NVIDIA_ARGS],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return parse_nvidia_csv(proc.stdout) or None


def fallback_note() -> str:
    if nvidia_smi_path() is None:
        return "nvidia-smi not found"
    return "nvidia-smi did not return GPU data"


def demo_gpus(elapsed_s: float, seed: int) -> list[GpuSample]:
    """A 24 GB card warming up. The name says this is not a measurement."""
    elapsed = max(0.0, elapsed_s)
    phase = (seed % 7) * 0.35
    ramp = min(1.0, elapsed / 25.0)
    frac = 0.12 + 0.75 * ramp + 0.02 * math.sin(elapsed / 3.0 + phase)
    frac = min(0.97, max(0.05, frac))
    util = min(100.0, max(0.0, 22 + 72 * ramp + 6 * math.sin(elapsed / 2.2 + phase)))
    power = 35 + util * 3.5
    temp = 36 + 34 * (1 - math.exp(-elapsed / 70.0)) + util * 0.05
    return [
        GpuSample(
            gpu_index=0,
            gpu_name=DEMO_GPU_NAME,
            vram_used_mb=round(DEMO_TOTAL_MB * frac, 1),
            vram_total_mb=DEMO_TOTAL_MB,
            power_w=round(power, 1),
            temp_c=round(temp, 1),
            util_pct=round(util, 1),
        )
    ]


def read_once(elapsed_s: float, seed: int, *, prefer: str | None = None) -> SampleReading:
    """prefer='demo' skips nvidia-smi. prefer='nvidia' does not invent a point on a miss."""
    if prefer != "demo":
        gpus = query_nvidia()
        if gpus:
            return SampleReading("nvidia", "measured with nvidia-smi", gpus)
        if prefer == "nvidia":
            return SampleReading("nvidia", "nvidia-smi missed a sample", [])
    return SampleReading("demo", fallback_note(), demo_gpus(elapsed_s, seed))
