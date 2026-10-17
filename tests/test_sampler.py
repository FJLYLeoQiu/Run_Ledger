import pytest

from runledger import sampler


def test_parse_nvidia_csv_with_na_power():
    text = "0, NVIDIA GeForce RTX 4090 D, 18432, 24564, [N/A], 71, 97\n"
    parsed = sampler.parse_nvidia_csv(text)
    assert len(parsed) == 1
    gpu = parsed[0]
    assert gpu.gpu_index == 0
    assert gpu.gpu_name == "NVIDIA GeForce RTX 4090 D"
    assert gpu.vram_used_mb == 18432
    assert gpu.vram_total_mb == 24564
    assert gpu.power_w is None
    assert gpu.temp_c == 71
    assert gpu.util_pct == 97


def test_parse_two_gpus_and_blank_lines():
    text = "\n0, GPU A, 100, 200, 50, 40, 10\n1, GPU B, 10, 200, [Not Supported], 30, 0\n"
    parsed = sampler.parse_nvidia_csv(text)
    assert [gpu.gpu_index for gpu in parsed] == [0, 1]
    assert parsed[1].power_w is None


def test_demo_curve_stays_in_range():
    for elapsed in (0, 1, 10, 25, 80):
        gpu = sampler.demo_gpus(elapsed, seed=3)[0]
        assert gpu.gpu_name.startswith("Demo GPU")
        assert 0 < gpu.vram_used_mb < gpu.vram_total_mb
        assert 0 <= gpu.util_pct <= 100
        assert 20 < gpu.temp_c < 100
        assert gpu.power_w > 30


def test_prefer_demo_does_not_call_nvidia(monkeypatch):
    def boom():
        raise AssertionError("nvidia-smi should not be queried")

    monkeypatch.setattr(sampler, "query_nvidia", boom)
    reading = sampler.read_once(2, seed=1, prefer="demo")
    assert reading.mode == "demo"
    assert reading.samples


def test_prefer_nvidia_miss_does_not_invent_a_point(monkeypatch):
    monkeypatch.setattr(sampler, "query_nvidia", lambda: None)
    reading = sampler.read_once(2, seed=1, prefer="nvidia")
    assert reading.mode == "nvidia"
    assert reading.samples == []
