from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium

try:
    import PIL.Image  # noqa: F401

    PIL_AVAILABLE = True
except ModuleNotFoundError:
    PIL_AVAILABLE = False


@dataclass
class PDFDescriptor:
    path: Path
    page_count: int


def _ensure_pillow_available() -> None:
    if not PIL_AVAILABLE:
        raise RuntimeError(
            "Pillow is required to render PDF pages. Run `uv sync` to install project dependencies."
        )


def get_page_count(pdf_path: Path) -> int:
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(document)
    finally:
        document.close()


def describe_pdfs(paths: list[Path]) -> list[PDFDescriptor]:
    descriptors: list[PDFDescriptor] = []
    for path in paths:
        descriptors.append(PDFDescriptor(path=path, page_count=get_page_count(path)))
    return descriptors


def render_pdf_page_png(pdf_path: Path, page_index: int, dpi: int = 180) -> bytes:
    _ensure_pillow_available()
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        page = document[page_index]
        pil_image = page.render(scale=dpi / 72.0).to_pil()
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


def iter_rendered_pages(pdf_path: Path, dpi: int = 180):
    _ensure_pillow_available()
    document = pdfium.PdfDocument(str(pdf_path))
    try:
        for index in range(len(document)):
            page = document[index]
            pil_image = page.render(scale=dpi / 72.0).to_pil()
            buffer = BytesIO()
            pil_image.save(buffer, format="PNG")
            yield index + 1, buffer.getvalue()
    finally:
        document.close()
