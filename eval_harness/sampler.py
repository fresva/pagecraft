"""Weighted sampler: selects eval runs for human review and writes JSONL output."""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

from eval_harness.models import EvalRun


class ReviewSampler:
    """Selects a stratified, weighted sample of runs for human review.

    Selection tiers:
      3x — edge cases  (not completed, score < 2.5, or C4 < 3)
      2x — borderline  (2.5 <= score < 3.5)
      1x — rest

    Guarantees at least one row per persona that has >= 1 run.
    """

    def __init__(self, csv_path: Path, jsonl_path: Path, seed: int = 42) -> None:
        """Initialise with output paths and an optional RNG seed for reproducibility."""
        self._csv_path = csv_path
        self._jsonl_path = jsonl_path
        self._rng = random.Random(seed)

    def run(self, runs: list[EvalRun]) -> set[str]:
        """Execute sampling, update CSV flags, write JSONL. Returns sampled eval_ids."""
        if not runs:
            return set()

        weights = [self._tier_weight(run) for run in runs]
        target = min(max(10, math.ceil(0.20 * len(runs))), len(runs))

        sampled_ids = self._weighted_sample(runs, weights, target)
        sampled_ids = self._enforce_persona_coverage(runs, sampled_ids)

        self._update_csv(sampled_ids)
        self._write_jsonl(runs, sampled_ids)
        return sampled_ids

    # ------------------------------------------------------------------
    # Sampling logic
    # ------------------------------------------------------------------

    def _weighted_sample(
        self,
        runs: list[EvalRun],
        weights: list[float],
        k: int,
    ) -> set[str]:
        """Return up to *k* eval_ids drawn without replacement using *weights*."""
        if k >= len(runs):
            return {run.eval_id for run in runs}

        pool = list(zip(runs, weights))
        selected: set[str] = set()

        while len(selected) < k and pool:
            total = sum(weight for _, weight in pool)
            pick = self._rng.uniform(0, total)
            cumulative = 0.0
            for index, (run, weight) in enumerate(pool):
                cumulative += weight
                if cumulative >= pick:
                    selected.add(run.eval_id)
                    pool.pop(index)
                    break

        return selected

    @staticmethod
    def _enforce_persona_coverage(
        runs: list[EvalRun],
        sampled_ids: set[str],
    ) -> set[str]:
        """Ensure every persona that has >= 1 run appears at least once in the sample."""
        result = set(sampled_ids)
        covered_personas = {run.log.persona_id for run in runs if run.eval_id in result}
        missing_personas = {run.log.persona_id for run in runs} - covered_personas

        if not missing_personas:
            return result

        persona_counts: dict[str, list[str]] = {}
        for run in runs:
            if run.eval_id in result:
                persona_counts.setdefault(run.log.persona_id, []).append(run.eval_id)

        for persona_id in missing_personas:
            candidate = next((run for run in runs if run.log.persona_id == persona_id), None)
            if candidate is None:
                continue

            if persona_counts:
                most_represented = max(persona_counts, key=lambda p: len(persona_counts[p]))
                if len(persona_counts[most_represented]) > 1:
                    evicted = persona_counts[most_represented].pop()
                    result.discard(evicted)

            result.add(candidate.eval_id)
            persona_counts.setdefault(persona_id, []).append(candidate.eval_id)

        return result

    # ------------------------------------------------------------------
    # Output writers
    # ------------------------------------------------------------------

    def _update_csv(self, sampled_ids: set[str]) -> None:
        """Back-fill the ``in_human_review`` column in the CSV for sampled rows."""
        if not self._csv_path.exists():
            return

        rows: list[dict] = []
        fieldnames: list[str] = []
        with open(self._csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            for row in reader:
                row["in_human_review"] = str(row.get("eval_id", "") in sampled_ids)
                rows.append(row)

        if not rows:
            return

        with open(self._csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _write_jsonl(self, runs: list[EvalRun], sampled_ids: set[str]) -> None:
        """Write one JSON object per sampled run to the JSONL review file."""
        sampled = [run for run in runs if run.eval_id in sampled_ids]
        with open(self._jsonl_path, "w", encoding="utf-8") as fh:
            for run in sampled:
                record = {
                    "eval_id": run.eval_id,
                    "persona_id": run.log.persona_id,
                    "overall_score": run.verdict.overall_score,
                    "judge_reasoning": run.verdict.judge_reasoning,
                    "transcript": [
                        {
                            "direction": turn.direction,
                            "turn": turn.turn,
                            "text": turn.text,
                            "type": turn.ws_type,
                        }
                        for turn in run.log.turns
                        if turn.direction == "sent"
                        or turn.ws_type in ("chat", "component")
                    ],
                    "components": {
                        comp_type: {
                            "data_json": state.data_json,
                            "status": state.status,
                        }
                        for comp_type, state in run.log.components.items()
                    },
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Pure helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tier_weight(run: EvalRun) -> float:
        """Return a sampling weight: 3x for edge cases, 2x for borderline, 1x otherwise."""
        score = run.verdict.overall_score
        c4 = run.verdict.c4_graceful_recovery

        if run.log.termination_reason != "completed" or score < 2.5 or (
            c4 is not None and c4 < 3
        ):
            return 3.0
        if score < 3.5:
            return 2.0
        return 1.0
