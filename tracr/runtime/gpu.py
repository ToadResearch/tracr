from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class GPUStat:
    index: int
    name: str
    memory_total_mb: int
    memory_used_mb: int
    utilization_percent: int


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value.strip())
    except Exception:
        return default


def _query_gpu_stats_nvidia_smi() -> list[GPUStat]:
    if not shutil.which("nvidia-smi"):
        return []

    command = [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
    except Exception:
        return []

    stats: list[GPUStat] = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5:
            continue
        stats.append(
            GPUStat(
                index=_parse_int(parts[0]),
                name=parts[1],
                memory_total_mb=_parse_int(parts[2]),
                memory_used_mb=_parse_int(parts[3]),
                utilization_percent=_parse_int(parts[4]),
            )
        )

    return stats


def _query_gpu_stats_nvml() -> list[GPUStat]:
    try:
        import pynvml
    except Exception:
        return []

    try:
        pynvml.nvmlInit()
    except Exception:
        return []

    stats: list[GPUStat] = []
    try:
        count = int(pynvml.nvmlDeviceGetCount())
        for index in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name_raw = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name_raw, bytes):
                name = name_raw.decode("utf-8", errors="ignore")
            else:
                name = str(name_raw)

            memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_total_mb = int(memory_info.total / (1024 * 1024))
            memory_used_mb = int(memory_info.used / (1024 * 1024))

            utilization_percent = 0
            try:
                utilization_percent = int(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)
            except Exception:
                utilization_percent = 0

            stats.append(
                GPUStat(
                    index=index,
                    name=name,
                    memory_total_mb=memory_total_mb,
                    memory_used_mb=memory_used_mb,
                    utilization_percent=utilization_percent,
                )
            )
    except Exception:
        return []
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    return stats


def query_gpu_stats() -> list[GPUStat]:
    stats = _query_gpu_stats_nvidia_smi()
    if stats:
        return stats
    return _query_gpu_stats_nvml()


def detect_gpu_count() -> int:
    override = os.getenv("OCR_GPU_COUNT")
    if override:
        try:
            return max(0, int(override))
        except ValueError:
            pass

    stats = query_gpu_stats()
    return len(stats)
