from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tracr.core.config import Settings
from tracr.core.output_layout import write_json


DEFAULT_RATING = 1000.0
DEFAULT_K_FACTOR = 24.0


class EloManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def elo_dir(self, job_id: str) -> Path:
        return self.settings.outputs_path / job_id / "elo"

    def ratings_path(self, job_id: str) -> Path:
        return self.elo_dir(job_id) / "ratings.json"

    def votes_path(self, job_id: str) -> Path:
        return self.elo_dir(job_id) / "votes.jsonl"

    @staticmethod
    def _new_model_entry(model_slug: str, model_label: str) -> dict[str, Any]:
        return {
            "model_slug": model_slug,
            "model_label": model_label,
            "rating": DEFAULT_RATING,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "comparisons": 0,
        }

    @staticmethod
    def _expected_score(ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    def _read_ratings_payload(self, job_id: str) -> dict[str, Any]:
        path = self.ratings_path(job_id)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:  # noqa: BLE001
            pass
        return {}

    def _write_ratings_payload(self, job_id: str, payload: dict[str, Any]) -> None:
        payload["updated_at"] = datetime.now(UTC).isoformat()
        write_json(self.ratings_path(job_id), payload)

    def load_ratings(self, job_id: str, model_labels: dict[str, str] | None = None) -> dict[str, Any]:
        model_labels = model_labels or {}
        existing = self._read_ratings_payload(job_id)
        models = existing.get("models")
        if not isinstance(models, dict):
            models = {}

        changed = False
        for model_slug, model_label in model_labels.items():
            entry = models.get(model_slug)
            if not isinstance(entry, dict):
                models[model_slug] = self._new_model_entry(model_slug, model_label)
                changed = True
                continue

            if not entry.get("model_label"):
                entry["model_label"] = model_label
                changed = True

            for key, default in {
                "rating": DEFAULT_RATING,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "comparisons": 0,
            }.items():
                if key not in entry:
                    entry[key] = default
                    changed = True

        payload = {
            "job_id": job_id,
            "k_factor": float(existing.get("k_factor", DEFAULT_K_FACTOR)),
            "updated_at": existing.get("updated_at"),
            "models": models,
        }
        if changed or not self.ratings_path(job_id).exists():
            self._write_ratings_payload(job_id, payload)
        return payload

    def ratings_table(self, job_id: str, model_labels: dict[str, str] | None = None) -> list[dict[str, Any]]:
        payload = self.load_ratings(job_id, model_labels=model_labels)
        models = payload.get("models", {})
        rows: list[dict[str, Any]] = []
        for model_slug, entry in models.items():
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "model_slug": model_slug,
                    "model_label": str(entry.get("model_label") or model_slug),
                    "rating": float(entry.get("rating", DEFAULT_RATING)),
                    "wins": int(entry.get("wins", 0)),
                    "losses": int(entry.get("losses", 0)),
                    "ties": int(entry.get("ties", 0)),
                    "comparisons": int(entry.get("comparisons", 0)),
                }
            )
        rows.sort(key=lambda row: row["rating"], reverse=True)
        return rows

    def _append_vote(self, job_id: str, payload: dict[str, Any]) -> None:
        votes_path = self.votes_path(job_id)
        votes_path.parent.mkdir(parents=True, exist_ok=True)
        with votes_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def record_vote(
        self,
        *,
        job_id: str,
        left_model_slug: str,
        left_model_label: str,
        right_model_slug: str,
        right_model_label: str,
        choice: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self.load_ratings(
            job_id,
            model_labels={
                left_model_slug: left_model_label,
                right_model_slug: right_model_label,
            },
        )
        models = payload["models"]
        left = models[left_model_slug]
        right = models[right_model_slug]
        k_factor = float(payload.get("k_factor", DEFAULT_K_FACTOR))

        before = {
            "left_rating": float(left.get("rating", DEFAULT_RATING)),
            "right_rating": float(right.get("rating", DEFAULT_RATING)),
        }

        timestamp = datetime.now(UTC).isoformat()
        normalized_choice = str(choice).strip().lower()
        if normalized_choice == "skip":
            self._append_vote(
                job_id,
                {
                    "timestamp": timestamp,
                    "job_id": job_id,
                    "choice": normalized_choice,
                    "left_model_slug": left_model_slug,
                    "right_model_slug": right_model_slug,
                    "before": before,
                    "after": before,
                    "context": context,
                },
            )
            return {
                "job_id": job_id,
                "choice": normalized_choice,
                "ratings": self.ratings_table(job_id),
            }

        if normalized_choice == "left_better":
            score_left, score_right = 1.0, 0.0
            left["wins"] = int(left.get("wins", 0)) + 1
            right["losses"] = int(right.get("losses", 0)) + 1
        elif normalized_choice == "right_better":
            score_left, score_right = 0.0, 1.0
            right["wins"] = int(right.get("wins", 0)) + 1
            left["losses"] = int(left.get("losses", 0)) + 1
        elif normalized_choice in {"both_good", "both_bad"}:
            score_left = score_right = 0.5
            left["ties"] = int(left.get("ties", 0)) + 1
            right["ties"] = int(right.get("ties", 0)) + 1
        else:
            raise ValueError(
                "Invalid choice. Expected one of: left_better, right_better, both_good, both_bad, skip."
            )

        ra = float(left.get("rating", DEFAULT_RATING))
        rb = float(right.get("rating", DEFAULT_RATING))
        ea = self._expected_score(ra, rb)
        eb = self._expected_score(rb, ra)
        new_ra = ra + k_factor * (score_left - ea)
        new_rb = rb + k_factor * (score_right - eb)

        left["rating"] = round(new_ra, 4)
        right["rating"] = round(new_rb, 4)
        left["comparisons"] = int(left.get("comparisons", 0)) + 1
        right["comparisons"] = int(right.get("comparisons", 0)) + 1

        self._write_ratings_payload(job_id, payload)

        after = {"left_rating": left["rating"], "right_rating": right["rating"]}
        self._append_vote(
            job_id,
            {
                "timestamp": timestamp,
                "job_id": job_id,
                "choice": normalized_choice,
                "left_model_slug": left_model_slug,
                "right_model_slug": right_model_slug,
                "before": before,
                "after": after,
                "context": context,
            },
        )

        return {
            "job_id": job_id,
            "choice": normalized_choice,
            "ratings": self.ratings_table(job_id),
        }
