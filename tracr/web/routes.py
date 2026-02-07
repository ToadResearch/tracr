from __future__ import annotations

import html
import json
import random
from pathlib import Path
from typing import Any

try:
    import markdown as md
except ModuleNotFoundError:  # pragma: no cover - exercised when web extra is not installed
    md = None
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from tracr.core.config import Settings
from tracr.core.pdf_tools import render_pdf_page_png
from tracr.runtime.elo_manager import EloManager
from tracr.runtime.job_manager import JobManager
from tracr.web.page_elo import elo_js, elo_section_html
from tracr.web.page_shell import head_html, header_html, init_js, shared_js
from tracr.web.page_viewer import viewer_js, viewer_section_html


class EloVoteRequest(BaseModel):
    choice: str
    pdf_slug: str
    page_number: int
    left_model_slug: str
    left_model_label: str
    left_run_number: int
    right_model_slug: str
    right_model_label: str
    right_run_number: int


def build_web_router(*, settings: Settings, manager: JobManager, elo_manager: EloManager) -> APIRouter:
    router = APIRouter()

    def _read_json_if_exists(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:  # noqa: BLE001
            return {}
        return {}

    def _job_dir(job_id: str) -> Path:
        job_dir = settings.outputs_path / job_id
        if not job_dir.exists() or not job_dir.is_dir():
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return job_dir

    def _output_token_usage(pdf_metadata: dict[str, Any], page_number: int) -> int | None:
        pages = pdf_metadata.get("pages")
        if not isinstance(pages, list):
            return None
        for page in pages:
            if not isinstance(page, dict):
                continue
            try:
                entry_page = int(page.get("page_number"))
            except Exception:  # noqa: BLE001
                continue
            if entry_page != page_number:
                continue
            token_usage = page.get("token_usage")
            if not isinstance(token_usage, dict):
                return None
            try:
                return int(token_usage.get("output_tokens"))
            except Exception:  # noqa: BLE001
                return None
        return None

    def _collect_job_outputs(job_id: str) -> dict[str, Any]:
        job_dir = _job_dir(job_id)
        job_metadata = _read_json_if_exists(job_dir / "job_metadata.json")
        job_title = str(job_metadata.get("title") or job_id)

        outputs: list[dict[str, Any]] = []
        for model_dir in sorted((item for item in job_dir.iterdir() if item.is_dir()), key=lambda item: item.name):
            model_slug = model_dir.name
            model_metadata = _read_json_if_exists(model_dir / "model_metadata.json")
            fallback_model_label = str(model_metadata.get("model") or model_slug)

            run_dirs = sorted(
                (
                    item
                    for item in model_dir.iterdir()
                    if item.is_dir() and manager.layout.parse_run_number(item.name) is not None
                ),
                key=lambda item: int(manager.layout.parse_run_number(item.name) or 0),
            )

            for run_dir in run_dirs:
                run_number = int(manager.layout.parse_run_number(run_dir.name) or 0)
                run_metadata = _read_json_if_exists(run_dir / "run_metadata.json")
                model_label = str(run_metadata.get("model") or fallback_model_label)

                for pdf_dir in sorted((item for item in run_dir.iterdir() if item.is_dir()), key=lambda item: item.name):
                    pdf_slug = pdf_dir.name
                    pdf_metadata = _read_json_if_exists(pdf_dir / "pdf_metadata.json")
                    source_pdf = str(pdf_metadata.get("source_pdf") or "")
                    pdf_label = Path(source_pdf).stem if source_pdf else pdf_slug

                    page_numbers: list[int] = []
                    for page_file in pdf_dir.glob("*.md"):
                        if not page_file.is_file() or not page_file.stem.isdigit():
                            continue
                        page_numbers.append(int(page_file.stem))
                    page_numbers.sort()

                    if not page_numbers:
                        continue

                    output_id = f"{model_slug}|{run_number}|{pdf_slug}"
                    outputs.append(
                        {
                            "output_id": output_id,
                            "model_slug": model_slug,
                            "model_label": model_label,
                            "run_number": run_number,
                            "pdf_slug": pdf_slug,
                            "pdf_label": pdf_label,
                            "source_pdf": source_pdf,
                            "page_numbers": page_numbers,
                            "page_count": len(page_numbers),
                            "pdf_metadata": pdf_metadata,
                            "pdf_dir": pdf_dir,
                        }
                    )

        outputs.sort(key=lambda item: (item["model_slug"], item["run_number"], item["pdf_slug"]))
        return {
            "job_id": job_id,
            "title": job_title,
            "outputs": outputs,
        }

    def _find_output(job_id: str, output_id: str) -> dict[str, Any]:
        payload = _collect_job_outputs(job_id)
        for output in payload["outputs"]:
            if output["output_id"] == output_id:
                return output
        raise HTTPException(status_code=404, detail=f"Output not found for id: {output_id}")

    def _discover_jobs() -> list[dict[str, Any]]:
        outputs_root = settings.outputs_path
        jobs: list[dict[str, Any]] = []

        for job_dir in sorted((item for item in outputs_root.iterdir() if item.is_dir()), key=lambda item: item.name):
            if job_dir.name == "proxy_logs":
                continue
            job_id = job_dir.name
            try:
                payload = _collect_job_outputs(job_id)
            except HTTPException:
                continue

            outputs = payload["outputs"]
            if not outputs:
                continue

            model_slugs = {item["model_slug"] for item in outputs}
            page_count = sum(int(item["page_count"]) for item in outputs)
            metadata = _read_json_if_exists(job_dir / "job_metadata.json")
            jobs.append(
                {
                    "job_id": job_id,
                    "title": str(metadata.get("title") or payload["title"] or job_id),
                    "model_count": len(model_slugs),
                    "output_count": len(outputs),
                    "page_count": page_count,
                    "elo_eligible": len(model_slugs) > 1,
                    "created_at": metadata.get("created_at"),
                }
            )

        jobs.sort(key=lambda item: (str(item.get("created_at") or ""), item["job_id"]), reverse=True)
        return jobs

    def _render_markdown(raw_markdown: str) -> str:
        if md is None:
            return f"<pre>{html.escape(raw_markdown)}</pre>"
        return md.markdown(
            raw_markdown,
            extensions=[
                "fenced_code",
                "tables",
                "sane_lists",
            ],
        )

    def _elo_pair_candidates(job_id: str) -> dict[str, Any]:
        payload = _collect_job_outputs(job_id)
        outputs = payload["outputs"]
        if not outputs:
            return {
                "job_id": job_id,
                "title": payload["title"],
                "model_labels": {},
                "grouped": {},
            }

        latest_run_by_model: dict[str, int] = {}
        model_labels: dict[str, str] = {}
        for output in outputs:
            model_slug = str(output["model_slug"])
            run_number = int(output["run_number"])
            model_labels[model_slug] = str(output["model_label"])
            previous = latest_run_by_model.get(model_slug)
            if previous is None or run_number > previous:
                latest_run_by_model[model_slug] = run_number

        latest_outputs = [
            output
            for output in outputs
            if int(output["run_number"]) == int(latest_run_by_model.get(str(output["model_slug"]), -1))
        ]

        grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for output in latest_outputs:
            for page_number in output["page_numbers"]:
                key = (str(output["pdf_slug"]), int(page_number))
                grouped.setdefault(key, []).append(output)

        filtered_grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for key, entries in grouped.items():
            if len({str(entry["model_slug"]) for entry in entries}) >= 2:
                filtered_grouped[key] = entries

        return {
            "job_id": job_id,
            "title": payload["title"],
            "model_labels": model_labels,
            "grouped": filtered_grouped,
        }

    @router.get("/web", response_class=HTMLResponse)
    @router.get("/web/", response_class=HTMLResponse)
    def web_home() -> HTMLResponse:
        return HTMLResponse(_web_page_html())

    @router.get("/web/tracr.png")
    def web_logo() -> Response:
        logo = Path(__file__).parent / "tracr.png"
        if not logo.exists():
            raise HTTPException(status_code=404, detail="Logo not found")
        return Response(content=logo.read_bytes(), media_type="image/png")

    @router.get("/api/web/jobs")
    def web_jobs() -> dict[str, Any]:
        return {"jobs": _discover_jobs()}

    @router.get("/api/web/jobs/{job_id}/outputs")
    def web_job_outputs(job_id: str) -> dict[str, Any]:
        payload = _collect_job_outputs(job_id)
        outputs = [
            {
                "output_id": output["output_id"],
                "model_slug": output["model_slug"],
                "model_label": output["model_label"],
                "run_number": output["run_number"],
                "pdf_slug": output["pdf_slug"],
                "pdf_label": output["pdf_label"],
                "page_numbers": output["page_numbers"],
                "page_count": output["page_count"],
                "label": f"{output['model_label']} · Run {output['run_number']} · {output['pdf_label']}",
            }
            for output in payload["outputs"]
        ]
        return {
            "job_id": job_id,
            "title": payload["title"],
            "outputs": outputs,
        }

    @router.get("/api/web/jobs/{job_id}/viewer/page")
    def web_viewer_page(job_id: str, output_id: str, page_number: int | None = None) -> dict[str, Any]:
        output = _find_output(job_id, output_id)
        pages = list(output["page_numbers"])
        if not pages:
            raise HTTPException(status_code=404, detail="No pages available for this output")

        current_page = int(page_number or pages[0])
        if current_page not in pages:
            raise HTTPException(status_code=404, detail=f"Page {current_page} not available for this output")

        markdown_path = Path(output["pdf_dir"]) / f"{current_page}.md"
        if not markdown_path.exists():
            raise HTTPException(status_code=404, detail=f"Page markdown missing: {current_page}")
        markdown_raw = markdown_path.read_text(encoding="utf-8")

        output_tokens = _output_token_usage(output["pdf_metadata"], current_page)
        return {
            "job_id": job_id,
            "job_title": _collect_job_outputs(job_id)["title"],
            "output": {
                "output_id": output["output_id"],
                "model_label": output["model_label"],
                "model_slug": output["model_slug"],
                "run_number": output["run_number"],
                "pdf_label": output["pdf_label"],
                "pdf_slug": output["pdf_slug"],
                "page_numbers": pages,
                "current_page": current_page,
            },
            "markdown_raw": markdown_raw,
            "markdown_html": _render_markdown(markdown_raw),
            "output_characters": len(markdown_raw),
            "output_tokens": output_tokens,
            "image_url": f"/api/web/jobs/{job_id}/viewer/page-image?output_id={output_id}&page_number={current_page}",
        }

    @router.get("/api/web/jobs/{job_id}/viewer/page-image")
    def web_viewer_page_image(job_id: str, output_id: str, page_number: int, dpi: int = 180) -> Response:
        output = _find_output(job_id, output_id)
        if page_number not in output["page_numbers"]:
            raise HTTPException(status_code=404, detail=f"Page {page_number} not available for this output")

        source_pdf = str(output["source_pdf"])
        if not source_pdf:
            raise HTTPException(status_code=500, detail="Source PDF path missing for this output")

        pdf_path = Path(source_pdf)
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Source PDF no longer exists")

        try:
            image_bytes = render_pdf_page_png(pdf_path, page_index=page_number - 1, dpi=dpi)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Failed rendering page image: {exc}") from exc

        return Response(content=image_bytes, media_type="image/png")

    @router.get("/api/web/elo/jobs")
    def web_elo_jobs() -> dict[str, Any]:
        jobs = [job for job in _discover_jobs() if bool(job.get("elo_eligible"))]
        return {"jobs": jobs}

    @router.get("/api/web/elo/jobs/{job_id}/ratings")
    def web_elo_ratings(job_id: str) -> dict[str, Any]:
        candidates = _elo_pair_candidates(job_id)
        ratings = elo_manager.ratings_table(job_id, model_labels=candidates["model_labels"])
        return {
            "job_id": job_id,
            "job_title": candidates["title"],
            "ratings": ratings,
        }

    @router.get("/api/web/elo/jobs/{job_id}/next")
    def web_elo_next(job_id: str) -> dict[str, Any]:
        candidates = _elo_pair_candidates(job_id)
        model_labels = candidates["model_labels"]
        grouped = candidates["grouped"]
        ratings = elo_manager.ratings_table(job_id, model_labels=model_labels)

        if not grouped:
            return {
                "job_id": job_id,
                "job_title": candidates["title"],
                "has_pair": False,
                "message": "No comparable pages found for this job.",
                "ratings": ratings,
            }

        key = random.choice(list(grouped.keys()))
        entries = list(grouped[key])
        left, right = random.sample(entries, 2)
        page_number = int(key[1])

        left_markdown = (Path(left["pdf_dir"]) / f"{page_number}.md").read_text(encoding="utf-8")
        right_markdown = (Path(right["pdf_dir"]) / f"{page_number}.md").read_text(encoding="utf-8")

        return {
            "job_id": job_id,
            "job_title": candidates["title"],
            "has_pair": True,
            "pair": {
                "pdf_slug": str(key[0]),
                "pdf_label": str(left["pdf_label"]),
                "page_number": page_number,
                "image_url": (
                    f"/api/web/jobs/{job_id}/viewer/page-image?"
                    f"output_id={left['output_id']}&page_number={page_number}"
                ),
                "left": {
                    "model_slug": left["model_slug"],
                    "model_label": left["model_label"],
                    "run_number": left["run_number"],
                    "markdown_raw": left_markdown,
                    "markdown_html": _render_markdown(left_markdown),
                },
                "right": {
                    "model_slug": right["model_slug"],
                    "model_label": right["model_label"],
                    "run_number": right["run_number"],
                    "markdown_raw": right_markdown,
                    "markdown_html": _render_markdown(right_markdown),
                },
            },
            "ratings": ratings,
        }

    @router.post("/api/web/elo/jobs/{job_id}/vote")
    def web_elo_vote(job_id: str, payload: EloVoteRequest) -> dict[str, Any]:
        _job_dir(job_id)
        candidates = _elo_pair_candidates(job_id)
        known_models = set(candidates["model_labels"].keys())
        if payload.left_model_slug not in known_models or payload.right_model_slug not in known_models:
            raise HTTPException(status_code=400, detail="Vote references unknown models for this job")

        try:
            result = elo_manager.record_vote(
                job_id=job_id,
                left_model_slug=payload.left_model_slug,
                left_model_label=payload.left_model_label,
                right_model_slug=payload.right_model_slug,
                right_model_label=payload.right_model_label,
                choice=payload.choice,
                context={
                    "pdf_slug": payload.pdf_slug,
                    "page_number": payload.page_number,
                    "left_run_number": payload.left_run_number,
                    "right_run_number": payload.right_run_number,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result

    return router


def _web_page_html() -> str:
    return (
        '<!doctype html>\n<html lang="en" class="dark">\n  <head>\n'
        + head_html()
        + "\n  </head>\n"
        + '  <body class="bg-g-bg text-g-text font-sans text-sm leading-relaxed min-h-screen transition-colors duration-200">\n'
        + '    <div class="max-w-[1720px] mx-auto px-5 py-4">\n'
        + header_html()
        + "\n"
        + viewer_section_html()
        + "\n"
        + elo_section_html()
        + "\n"
        + "    </div>\n"
        + '    <div id="toast-container" class="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none"></div>\n'
        + "    <script>\n"
        + shared_js()
        + "\n"
        + viewer_js()
        + "\n"
        + elo_js()
        + "\n"
        + init_js()
        + "\n"
        + "    </script>\n"
        + "  </body>\n</html>\n"
    )
