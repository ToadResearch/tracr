from __future__ import annotations

from types import SimpleNamespace

from tracr.runtime import gpu


def test_query_gpu_stats_parses_nvidia_smi(monkeypatch) -> None:
    sample_output = "0, NVIDIA H100, 81559, 1024, 13\n1, NVIDIA H100, 81559, 2048, 21\n"

    monkeypatch.setattr(gpu.shutil, "which", lambda _: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(
        gpu.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=sample_output),
    )

    stats = gpu.query_gpu_stats()
    assert len(stats) == 2
    assert stats[0].index == 0
    assert stats[0].name == "NVIDIA H100"
    assert stats[1].memory_used_mb == 2048


def test_query_gpu_stats_falls_back_to_nvml(monkeypatch) -> None:
    monkeypatch.setattr(gpu.shutil, "which", lambda _: None)

    class _FakeMemInfo:
        def __init__(self, total: int, used: int):
            self.total = total
            self.used = used

    class _FakeUtil:
        def __init__(self, value: int):
            self.gpu = value

    class _FakePynvml:
        def nvmlInit(self) -> None:
            return None

        def nvmlShutdown(self) -> None:
            return None

        def nvmlDeviceGetCount(self) -> int:
            return 1

        def nvmlDeviceGetHandleByIndex(self, index: int) -> int:
            return index

        def nvmlDeviceGetName(self, _handle: int) -> bytes:
            return b"NVIDIA L4"

        def nvmlDeviceGetMemoryInfo(self, _handle: int) -> _FakeMemInfo:
            gib = 1024 * 1024 * 1024
            return _FakeMemInfo(total=24 * gib, used=3 * gib)

        def nvmlDeviceGetUtilizationRates(self, _handle: int) -> _FakeUtil:
            return _FakeUtil(47)

    import builtins

    real_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001, A002
        if name == "pynvml":
            return _FakePynvml()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)

    stats = gpu.query_gpu_stats()
    assert len(stats) == 1
    assert stats[0].name == "NVIDIA L4"
    assert stats[0].memory_total_mb == 24576
    assert stats[0].utilization_percent == 47


def test_detect_gpu_count_uses_override(monkeypatch) -> None:
    monkeypatch.setenv("OCR_GPU_COUNT", "7")
    assert gpu.detect_gpu_count() == 7
