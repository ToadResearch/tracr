from pathlib import Path

from tracr.core.config import Settings
from tracr.runtime.elo_manager import EloManager


def _build_manager(tmp_path: Path) -> EloManager:
    settings = Settings(
        _env_file=None,
        OCR_INPUTS_DIR=str(tmp_path / "inputs"),
        OCR_OUTPUTS_DIR=str(tmp_path / "outputs"),
        OCR_JOB_CONFIGS_DIR=str(tmp_path / "job_configs"),
        OCR_STATE_DIR=str(tmp_path / "state"),
    )
    settings.ensure_runtime_dirs()
    return EloManager(settings)


def test_record_vote_updates_ratings_and_writes_files(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    result = manager.record_vote(
        job_id="job-a",
        left_model_slug="model-left",
        left_model_label="Model Left",
        right_model_slug="model-right",
        right_model_label="Model Right",
        choice="left_better",
        context={"pdf_slug": "doc", "page_number": 3},
    )

    ratings = result["ratings"]
    assert len(ratings) == 2
    left = next(row for row in ratings if row["model_slug"] == "model-left")
    right = next(row for row in ratings if row["model_slug"] == "model-right")
    assert left["rating"] > right["rating"]
    assert left["wins"] == 1
    assert right["losses"] == 1
    assert left["comparisons"] == 1
    assert right["comparisons"] == 1

    ratings_path = manager.ratings_path("job-a")
    votes_path = manager.votes_path("job-a")
    assert ratings_path.exists()
    assert votes_path.exists()
    assert len(votes_path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_skip_vote_keeps_ratings_unchanged(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)

    manager.record_vote(
        job_id="job-b",
        left_model_slug="model-left",
        left_model_label="Model Left",
        right_model_slug="model-right",
        right_model_label="Model Right",
        choice="left_better",
        context={"pdf_slug": "doc", "page_number": 1},
    )
    baseline = {row["model_slug"]: row["rating"] for row in manager.ratings_table("job-b")}

    manager.record_vote(
        job_id="job-b",
        left_model_slug="model-left",
        left_model_label="Model Left",
        right_model_slug="model-right",
        right_model_label="Model Right",
        choice="skip",
        context={"pdf_slug": "doc", "page_number": 2},
    )
    after = {row["model_slug"]: row["rating"] for row in manager.ratings_table("job-b")}

    assert baseline == after
    votes_lines = manager.votes_path("job-b").read_text(encoding="utf-8").strip().splitlines()
    assert len(votes_lines) == 2
