import pytest

from tracr.core import pdf_tools


def test_rendering_requires_pillow(monkeypatch) -> None:
    monkeypatch.setattr(pdf_tools, "PIL_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="Pillow is required"):
        pdf_tools._ensure_pillow_available()
