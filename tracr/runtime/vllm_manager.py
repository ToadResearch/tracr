from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tracr.core.config import Settings
from tracr.runtime.gpu import detect_gpu_count, query_gpu_stats


@dataclass
class ServerHandle:
    key: str
    model: str
    base_url: str
    port: int
    gpu_ids: tuple[int, ...]
    process: subprocess.Popen
    log_path: Path
    ref_count: int = 1


class VLLMServerManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._servers: dict[str, ServerHandle] = {}

        self._total_gpus = detect_gpu_count()
        self._allocated_gpu_ids: set[int] = set()
        self._next_port = settings.vllm_base_port
        self._log_dir = settings.state_path / "vllm_logs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def total_gpus(self) -> int:
        return self._total_gpus

    def gpu_payload(self) -> dict:
        stats = query_gpu_stats()
        return {
            "gpu_count": len(stats),
            "gpus": [
                {
                    "index": stat.index,
                    "name": stat.name,
                    "memory_total_mb": stat.memory_total_mb,
                    "memory_used_mb": stat.memory_used_mb,
                    "utilization_percent": stat.utilization_percent,
                }
                for stat in stats
            ],
        }

    def _supports_local_mode(self) -> tuple[bool, str | None]:
        if self._total_gpus <= 0:
            return False, "No visible NVIDIA GPUs."
        if importlib.util.find_spec("vllm") is None:
            return False, "vllm is not installed. Install with: uv sync --extra local"
        return True, None

    def _find_open_port(self) -> int:
        port = self._next_port
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                    self._next_port = port + 1
                    return port
                except OSError:
                    port += 1

    def _allocate_gpus(self, count: int) -> tuple[int, ...] | None:
        free = [idx for idx in range(self._total_gpus) if idx not in self._allocated_gpu_ids]
        if len(free) < count:
            return None
        allocated = tuple(free[:count])
        self._allocated_gpu_ids.update(allocated)
        return allocated

    def _release_gpu_ids(self, gpu_ids: tuple[int, ...]) -> None:
        for gpu_id in gpu_ids:
            self._allocated_gpu_ids.discard(gpu_id)

    @staticmethod
    def _is_glm_ocr_model(model: str) -> bool:
        return model.strip().lower() == "zai-org/glm-ocr"

    @staticmethod
    def _transformers_version() -> str:
        try:
            return importlib.metadata.version("transformers")
        except Exception:
            return "unknown"

    @classmethod
    def _transformers_major_version(cls) -> int | None:
        version = cls._transformers_version()
        if version == "unknown":
            return None
        match = re.match(r"^(\d+)", version)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _tail_log_lines(path: Path, max_lines: int = 40) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        # Remove ANSI escape sequences from vLLM logs before surfacing in API/UI.
        content = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", content)
        lines = content.splitlines()
        if not lines:
            return ""
        return "\n".join(lines[-max_lines:])

    def acquire_server(
        self,
        *,
        model: str,
        tensor_parallel_size: int,
        data_parallel_size: int,
        gpu_memory_utilization: float,
        max_model_len: int | None,
        extra_vllm_args: list[str] | None = None,
        cancel_event: threading.Event | None = None,
        wait_poll_seconds: float = 2.0,
    ) -> ServerHandle:
        supported, reason = self._supports_local_mode()
        if not supported:
            raise RuntimeError(reason)

        total_required_gpus = tensor_parallel_size * data_parallel_size
        if total_required_gpus > self._total_gpus:
            raise RuntimeError(
                f"Requested {total_required_gpus} GPUs (tp={tensor_parallel_size}, dp={data_parallel_size}), "
                f"but only {self._total_gpus} GPUs are available"
            )

        if self._is_glm_ocr_model(model):
            transformers_major = self._transformers_major_version()
            if transformers_major is not None and transformers_major < 5:
                current = self._transformers_version()
                raise RuntimeError(
                    "zai-org/GLM-OCR requires newer transformers support for `glm_ocr` "
                    f"(detected transformers=={current}). "
                    "Upgrade as documented by the model page, e.g.:\n"
                    "  uv pip install -U --pre vllm --extra-index-url https://wheels.vllm.ai/nightly\n"
                    "  uv pip install -U git+https://github.com/huggingface/transformers.git"
                )

        normalized_extra_args = [arg.strip() for arg in (extra_vllm_args or []) if arg and arg.strip()]
        mm_limit_per_prompt = '{"video": 0}'
        if self._is_glm_ocr_model(model):
            mm_limit_per_prompt = '{"image": 1}'
            has_allowed_media_path = any(arg == "--allowed-local-media-path" for arg in normalized_extra_args)
            if not has_allowed_media_path:
                normalized_extra_args.extend(["--allowed-local-media-path", "/"])

        key = (
            f"{model}::{tensor_parallel_size}::{data_parallel_size}::{gpu_memory_utilization}::{max_model_len}::"
            f"{json.dumps(normalized_extra_args)}"
        )

        with self._condition:
            existing = self._servers.get(key)
            if existing and existing.process.poll() is None:
                existing.ref_count += 1
                return existing

            while True:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Canceled while waiting for GPUs")

                if len(self._servers) >= self.settings.local_max_concurrent_models:
                    self._condition.wait(timeout=wait_poll_seconds)
                    continue

                gpu_ids = self._allocate_gpus(total_required_gpus)
                if gpu_ids is None:
                    self._condition.wait(timeout=wait_poll_seconds)
                    continue

                port = self._find_open_port()
                break

        timestamp = int(time.time())
        log_path = self._log_dir / f"{timestamp}-{port}.log"
        env = dict(os.environ)
        env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in gpu_ids)

        cmd = [
            "vllm",
            "serve",
            model,
            "--served-model-name",
            model,
            "--port",
            str(port),
            "--uvicorn-log-level",
            "warning",
            "--tensor-parallel-size",
            str(tensor_parallel_size),
            "--data-parallel-size",
            str(data_parallel_size),
            "--limit-mm-per-prompt",
            mm_limit_per_prompt,
            "--gpu-memory-utilization",
            str(gpu_memory_utilization),
            "--trust-remote-code",
        ]
        if max_model_len is not None:
            cmd.extend(["--max-model-len", str(max_model_len)])
        if normalized_extra_args:
            cmd.extend(normalized_extra_args)

        env["OMP_NUM_THREADS"] = "1"

        log_file = log_path.open("w", encoding="utf-8")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                text=True,
            )
        except FileNotFoundError as exc:
            log_file.close()
            with self._condition:
                self._release_gpu_ids(gpu_ids)
                self._condition.notify_all()
            raise RuntimeError("vLLM CLI executable not found in PATH. Install with: uv sync --extra local") from exc
        finally:
            # Child process holds the file descriptor; close parent handle.
            log_file.close()

        base_url = f"http://127.0.0.1:{port}/v1"

        try:
            self._wait_for_server_ready(base_url, process, timeout_seconds=900.0)
        except Exception as exc:
            process.terminate()
            with self._condition:
                self._release_gpu_ids(gpu_ids)
                self._condition.notify_all()
            recent_logs = self._tail_log_lines(log_path)
            detail = f"{exc}. vLLM log: {log_path}"
            if self._is_glm_ocr_model(model) and "does not recognize this architecture" in recent_logs:
                detail += (
                    "\nHint: GLM-OCR needs newer transformers support (`glm_ocr`). "
                    "Try:\n"
                    "  uv pip install -U --pre vllm --extra-index-url https://wheels.vllm.ai/nightly\n"
                    "  uv pip install -U git+https://github.com/huggingface/transformers.git"
                )
            if recent_logs:
                detail += f"\nRecent log lines:\n{recent_logs}"
            raise RuntimeError(detail) from exc

        handle = ServerHandle(
            key=key,
            model=model,
            base_url=base_url,
            port=port,
            gpu_ids=gpu_ids,
            process=process,
            log_path=log_path,
        )

        with self._condition:
            self._servers[key] = handle

        return handle

    @staticmethod
    def _wait_for_server_ready(base_url: str, process: subprocess.Popen, timeout_seconds: float) -> None:
        deadline = time.time() + timeout_seconds
        probe_url = f"{base_url}/models"

        while time.time() < deadline:
            if process.poll() is not None:
                raise RuntimeError("vLLM server process exited before becoming ready")

            try:
                with urllib.request.urlopen(probe_url, timeout=5) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass

            time.sleep(2)

        raise RuntimeError(f"Timed out waiting for vLLM server at {probe_url}")

    def release_server(self, handle: ServerHandle) -> None:
        should_stop = False
        with self._condition:
            current = self._servers.get(handle.key)
            if not current:
                return

            current.ref_count -= 1
            if current.ref_count > 0:
                return

            should_stop = True
            self._servers.pop(handle.key, None)
            self._release_gpu_ids(current.gpu_ids)
            self._condition.notify_all()

        if should_stop:
            process = handle.process
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()

    def shutdown_all(self) -> None:
        with self._condition:
            handles = list(self._servers.values())
            self._servers.clear()
            for handle in handles:
                self._release_gpu_ids(handle.gpu_ids)
            self._condition.notify_all()

        for handle in handles:
            if handle.process.poll() is None:
                handle.process.terminate()
                try:
                    handle.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    handle.process.kill()
