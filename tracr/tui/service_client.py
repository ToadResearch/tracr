from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import quote
from dataclasses import dataclass
from typing import Any


class ServiceClientError(RuntimeError):
    pass


@dataclass
class ServiceClient:
    base_url: str

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {"Content-Type": "application/json"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise ServiceClientError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ServiceClientError(f"Connection error: {exc}") from exc

        if not body:
            return None
        return json.loads(body)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_presets(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/presets")

    def list_inputs(self) -> dict[str, Any]:
        return self._request("GET", "/api/inputs")

    def list_job_configs(self) -> dict[str, Any]:
        return self._request("GET", "/api/job-configs")

    def load_job_config(self, path: str) -> dict[str, Any]:
        return self._request("POST", "/api/job-configs/load", {"path": path})

    def list_default_local_models(self) -> list[str]:
        return self._request("GET", "/api/local-default-models")

    def list_jobs(self) -> dict[str, Any]:
        return self._request("GET", "/api/jobs")

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/jobs/{job_id}")

    def launch_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/jobs", payload)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/jobs/{job_id}/cancel")

    def dismiss_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/jobs/{job_id}/dismiss")

    def list_job_output_pages(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/jobs/{job_id}/output-pages")

    def get_job_output_page(self, job_id: str, page_index: int) -> dict[str, Any]:
        return self._request("GET", f"/api/jobs/{job_id}/output-pages/{page_index}")

    def list_outputs_tree(self, relative_path: str = "") -> dict[str, Any]:
        encoded = quote(relative_path or "", safe="")
        return self._request("GET", f"/api/outputs/tree?relative_path={encoded}")

    def read_output_file(self, relative_path: str) -> dict[str, Any]:
        encoded = quote(relative_path, safe="")
        return self._request("GET", f"/api/outputs/file?relative_path={encoded}")

    def gpu_stats(self) -> dict[str, Any]:
        return self._request("GET", "/api/system/gpus")

    def provider_key_status(self, provider_key: str, api_key_env: str | None = None) -> dict[str, Any]:
        query = ""
        if api_key_env:
            query = f"?api_key_env={api_key_env}"
        return self._request("GET", f"/api/providers/{provider_key}/key-status{query}")
