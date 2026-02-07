from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tracr.core.config import Settings
from tracr.core.provider_presets import model_slug


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    cleaned = re.sub(r"-+", "-", cleaned)
    return cleaned or "job"


def build_job_id(title: str | None, input_path: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if title and title.strip():
        base = _slug(title)
    else:
        base = _slug(Path(input_path).stem)
    return f"{base}-{stamp}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class RunPaths:
    model_slug: str
    run_number: int
    model_dir: Path
    run_dir: Path
    run_metadata_path: Path


@dataclass
class PDFPaths:
    pdf_slug: str
    pdf_dir: Path
    pdf_metadata_path: Path


class OutputLayout:
    def __init__(self, settings: Settings):
        self.settings = settings

    def job_dir(self, job_id: str) -> Path:
        return self.settings.outputs_path / job_id

    def job_metadata_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job_metadata.json"

    def ensure_job(self, job_id: str, payload: dict) -> Path:
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = self.job_metadata_path(job_id)
        if metadata_path.exists():
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            existing.update(payload)
            payload = existing
        write_json(metadata_path, payload)
        return metadata_path

    def ensure_model(self, job_id: str, model_name: str, payload: dict) -> Path:
        slug = model_slug(model_name)
        model_dir = self.job_dir(job_id) / slug
        model_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = model_dir / "model_metadata.json"

        if metadata_path.exists():
            existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            existing.update(payload)
            payload = existing

        write_json(metadata_path, payload)
        return metadata_path

    def prepare_run(self, job_id: str, model_name: str, payload: dict) -> RunPaths:
        slug = model_slug(model_name)
        model_dir = self.job_dir(job_id) / slug
        model_dir.mkdir(parents=True, exist_ok=True)

        run_number = self.next_run_number(model_dir)
        run_dir = model_dir / self.run_dir_name(run_number)
        run_dir.mkdir(parents=True, exist_ok=True)

        run_metadata_path = run_dir / "run_metadata.json"
        write_json(run_metadata_path, payload)

        return RunPaths(
            model_slug=slug,
            run_number=run_number,
            model_dir=model_dir,
            run_dir=run_dir,
            run_metadata_path=run_metadata_path,
        )

    def prepare_pdf(self, run_dir: Path, source_pdf: Path, page_count: int) -> PDFPaths:
        pdf_slug = _slug(source_pdf.stem)
        candidate = pdf_slug
        index = 1
        while (run_dir / candidate).exists():
            index += 1
            candidate = f"{pdf_slug}-{index}"

        pdf_dir = run_dir / candidate
        pdf_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = pdf_dir / "pdf_metadata.json"
        write_json(
            metadata_path,
            {
                "source_pdf": str(source_pdf),
                "pdf_slug": candidate,
                "page_count": page_count,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

        return PDFPaths(pdf_slug=candidate, pdf_dir=pdf_dir, pdf_metadata_path=metadata_path)

    def write_page_markdown(self, pdf_dir: Path, page_index: int, markdown_text: str) -> Path:
        page_path = pdf_dir / f"{page_index}.md"
        page_path.write_text(markdown_text, encoding="utf-8")
        return page_path

    @staticmethod
    def run_dir_name(run_number: int) -> str:
        return f"run-{run_number}"

    @staticmethod
    def parse_run_number(name: str) -> int | None:
        if not name.startswith("run-"):
            return None
        suffix = name.removeprefix("run-")
        if suffix.isdigit():
            return int(suffix)
        return None

    @classmethod
    def next_run_number(cls, model_dir: Path) -> int:
        run_numbers: list[int] = []
        if model_dir.exists():
            for child in model_dir.iterdir():
                if not child.is_dir():
                    continue
                run_number = cls.parse_run_number(child.name)
                if run_number is not None:
                    run_numbers.append(run_number)
        return (max(run_numbers) + 1) if run_numbers else 1
