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


def query_gpu_stats() -> list[GPUStat]:
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


def detect_gpu_count() -> int:
    override = os.getenv("OCR_GPU_COUNT")
    if override:
        try:
            return max(0, int(override))
        except ValueError:
            pass

    stats = query_gpu_stats()
    return len(stats)
