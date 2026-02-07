from pathlib import Path

from tracr.core.output_layout import OutputLayout, build_job_id


class DummySettings:
    def __init__(self, outputs_path: Path):
        self.outputs_path = outputs_path


def test_build_job_id_uses_title_or_input_stem() -> None:
    with_title = build_job_id("My Job", "inputs/doc.pdf")
    without_title = build_job_id(None, "inputs/another-doc.pdf")

    assert with_title.startswith("My-Job-")
    assert without_title.startswith("another-doc-")


def test_run_number_increments(tmp_path: Path) -> None:
    settings = DummySettings(tmp_path / "outputs")
    layout = OutputLayout(settings)

    layout.ensure_job("job-a", {"job_id": "job-a"})

    run1 = layout.prepare_run("job-a", "org/model", {"hello": "world"})
    run2 = layout.prepare_run("job-a", "org/model", {"hello": "again"})

    assert run1.run_number == 1
    assert run2.run_number == 2
    assert run1.run_dir.exists()
    assert run2.run_dir.exists()
    assert run1.run_dir.name == "run-1"
    assert run2.run_dir.name == "run-2"


def test_next_run_number_reads_run_dirs_only(tmp_path: Path) -> None:
    settings = DummySettings(tmp_path / "outputs")
    layout = OutputLayout(settings)
    model_dir = settings.outputs_path / "job-a" / "org-model"
    (model_dir / "ignored").mkdir(parents=True)
    (model_dir / "run-2").mkdir(parents=True)

    assert layout.next_run_number(model_dir) == 3


def test_prepare_pdf_deduplicates_slug(tmp_path: Path) -> None:
    settings = DummySettings(tmp_path / "outputs")
    layout = OutputLayout(settings)

    run = layout.prepare_run("job-a", "org/model", {"x": 1})

    pdf1 = layout.prepare_pdf(run.run_dir, Path("/tmp/invoice.pdf"), page_count=2)
    pdf2 = layout.prepare_pdf(run.run_dir, Path("/var/data/invoice.pdf"), page_count=3)

    assert pdf1.pdf_slug == "invoice"
    assert pdf2.pdf_slug == "invoice-2"
