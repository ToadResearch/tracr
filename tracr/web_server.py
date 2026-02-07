from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn

from tracr.app.api import app
from tracr.core.config import get_settings


def _browser_url(host: str, port: int) -> str:
    if host in {"0.0.0.0", "::", "::0", "[::]"}:
        host = "127.0.0.1"
    return f"http://{host}:{port}/web"


def _open_browser_delayed(url: str) -> None:
    time.sleep(0.7)
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass


def run_web_server(host: str, port: int, no_open: bool = False) -> None:
    url = _browser_url(host, port)
    print(f"Starting TRACR web at {url}")
    if not no_open:
        threading.Thread(target=_open_browser_delayed, args=(url,), daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Run TRACR web reviewer + ELO interface")
    parser.add_argument("--host", default=settings.web_host)
    parser.add_argument("--port", type=int, default=settings.web_port)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open a browser tab",
    )
    args = parser.parse_args()

    run_web_server(host=args.host, port=args.port, no_open=args.no_open)


if __name__ == "__main__":
    main()
