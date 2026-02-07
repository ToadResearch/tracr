from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRACR (no subcommand runs API + TUI)")
    subparsers = parser.add_subparsers(dest="command", required=False)

    all_parser = subparsers.add_parser("all", help="Run API and TUI together in one command")
    all_parser.add_argument("--host", default=None)
    all_parser.add_argument("--port", type=int, default=None)
    all_parser.add_argument(
        "--api-base-url",
        default=None,
        help="Override API URL used by the TUI when running in combined mode",
    )

    api_parser = subparsers.add_parser("api", help="Run TRACR API service")
    api_parser.add_argument("--host", default=None)
    api_parser.add_argument("--port", type=int, default=None)

    tui_parser = subparsers.add_parser("tui", help="Run Textual TUI")
    tui_parser.add_argument(
        "--api-base-url",
        default=None,
        help="Base URL of OCR API service (default from env OCR_API_BASE_URL)",
    )

    web_parser = subparsers.add_parser("web", help="Run TRACR web reviewer + ELO UI")
    web_parser.add_argument("--host", default=None)
    web_parser.add_argument("--port", type=int, default=None)
    web_parser.add_argument("--no-open", action="store_true")

    launcher = subparsers.add_parser("vllm-launch", help="Launch a standalone vLLM server")
    launcher.add_argument("model", help="Model name/path")
    launcher.add_argument("--num-gpus", type=int, default=1)
    launcher.add_argument("--data-parallel-size", type=int, default=1)
    launcher.add_argument("--port", type=int, default=9000)
    launcher.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    launcher.add_argument("--max-model-len", type=int, default=None)
    launcher.add_argument("--served-model-name", default=None)
    launcher.add_argument(
        "--extra-vllm-arg",
        action="append",
        default=[],
        help="Extra raw arg forwarded to `vllm serve` (repeatable).",
    )

    test_parser = subparsers.add_parser("test", help="Run all tests with pytest")
    test_parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Optional extra pytest args; use `--` before args (e.g. tracr test -- -k output)",
    )

    return parser


def run_vllm_launch(args: argparse.Namespace) -> int:
    cmd = [
        "vllm",
        "serve",
        args.model,
        "--served-model-name",
        args.served_model_name or args.model,
        "--port",
        str(args.port),
        "--disable-log-requests",
        "--uvicorn-log-level",
        "warning",
        "--tensor-parallel-size",
        str(args.num_gpus),
        "--data-parallel-size",
        str(args.data_parallel_size),
        "--limit-mm-per-prompt",
        '{"video": 0}',
        "--gpu-memory-utilization",
        str(args.gpu_memory_utilization),
        "--trust-remote-code",
    ]
    if args.max_model_len is not None:
        cmd.extend(["--max-model-len", str(args.max_model_len)])
    if args.extra_vllm_arg:
        cmd.extend([arg for arg in args.extra_vllm_arg if isinstance(arg, str) and arg.strip()])

    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, env={**os.environ, "OMP_NUM_THREADS": "1"})


def run_tests(args: argparse.Namespace) -> int:
    cmd = [sys.executable, "-m", "pytest"]
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


def _local_tui_base_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::", "::0", "[::]"}:
        host = "127.0.0.1"
    return f"http://{host}:{port}"


def _wait_for_api_ready(base_url: str, timeout_seconds: float = 90.0) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url.rstrip('/')}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for API readiness at {health_url}")


def run_all(args: argparse.Namespace) -> int:
    from tracr.core.config import get_settings
    from tracr.tui.app import run_tui

    settings = get_settings()
    host = getattr(args, "host", None) or settings.api_host
    port = getattr(args, "port", None) or settings.api_port
    api_base_url = getattr(args, "api_base_url", None) or _local_tui_base_url(host, port)

    log_path: Path = settings.state_path / "combined_api.log"
    cmd = [
        sys.executable,
        "-m",
        "tracr",
        "api",
        "--host",
        host,
        "--port",
        str(port),
    ]

    print(f"Starting API in background on {host}:{port} (logs: {log_path})")
    with log_path.open("a", encoding="utf-8") as log_file:
        api_process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            _wait_for_api_ready(api_base_url)
        except Exception as exc:  # noqa: BLE001
            if api_process.poll() is None:
                api_process.terminate()
                try:
                    api_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api_process.kill()
            print(f"Failed to start API: {exc}", file=sys.stderr)
            return 1

        try:
            run_tui(api_base_url)
            return 0
        finally:
            if api_process.poll() is None:
                api_process.terminate()
                try:
                    api_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api_process.kill()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {None, "all"}:
        raise SystemExit(run_all(args))

    if args.command == "api":
        import uvicorn

        from tracr.app.api import app
        from tracr.core.config import get_settings

        settings = get_settings()
        host = args.host or settings.api_host
        port = args.port or settings.api_port
        uvicorn.run(app, host=host, port=port, log_level="info")
        return

    if args.command == "tui":
        from tracr.core.config import get_settings
        from tracr.tui.app import run_tui

        settings = get_settings()
        base_url = args.api_base_url or settings.api_base_url
        run_tui(base_url)
        return

    if args.command == "web":
        from tracr.core.config import get_settings
        from tracr.web_server import run_web_server

        settings = get_settings()
        host = args.host or settings.web_host
        port = args.port or settings.web_port
        run_web_server(host=host, port=port, no_open=bool(args.no_open))
        return

    if args.command == "vllm-launch":
        raise SystemExit(run_vllm_launch(args))

    if args.command == "test":
        raise SystemExit(run_tests(args))

    parser.print_help()


if __name__ == "__main__":
    main()
