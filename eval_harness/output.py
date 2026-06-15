"""CSV result writer for eval harness runs."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from eval_harness.models import ConversationLog, JudgeVerdict

CSV_COLUMNS: list[str] = [
    "run_id",
    "eval_id",
    "timestamp",
    "demo_mode",
    "persona_id",
    "scenario_id",
    "turn_count",
    "components_rendered",
    "components_agreed",
    "completion_rate",
    "termination_reason",
    "score_c1_completeness",
    "score_c2_data_fidelity",
    "score_c3_agenda_progression",
    "score_c4_graceful_recovery",
    "overall_score",
    "judge_type",
    "judge_reasoning",
    "in_human_review",
    "error_detail",
]


class CSVWriter:
    """Writes one row per eval run to a CSV file; safe to call from multiple pytest tests."""

    def __init__(self, path: Path, run_id: str) -> None:
        """Open *path* for writing and emit the header row."""
        self._run_id = run_id
        self._file = open(path, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=CSV_COLUMNS)
        self._writer.writeheader()
        self._file.flush()

    def write_row(
        self,
        log: ConversationLog,
        verdict: JudgeVerdict,
        eval_id: str,
        demo_mode: bool = True,
    ) -> None:
        """Append one result row and flush immediately."""
        self._writer.writerow(self._build_row(log, verdict, eval_id, demo_mode))
        self._file.flush()

    def close(self) -> None:
        """Flush and close the underlying file handle."""
        if not self._file.closed:
            self._file.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_row(
        self,
        log: ConversationLog,
        verdict: JudgeVerdict,
        eval_id: str,
        demo_mode: bool,
    ) -> dict:
        """Assemble the CSV row dict from a log and verdict."""
        agreed_count = sum(1 for c in log.components.values() if c.status == "agreed")
        return {
            "run_id": self._run_id,
            "eval_id": eval_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "demo_mode": demo_mode,
            "persona_id": log.persona_id,
            "scenario_id": log.scenario_id,
            "turn_count": log.turn_count,
            "components_rendered": len(log.components),
            "components_agreed": agreed_count,
            "completion_rate": agreed_count / 10,
            "termination_reason": log.termination_reason,
            "score_c1_completeness": verdict.c1_completeness,
            "score_c2_data_fidelity": verdict.c2_data_fidelity,
            "score_c3_agenda_progression": verdict.c3_agenda_progression,
            "score_c4_graceful_recovery": verdict.c4_graceful_recovery,
            "overall_score": verdict.overall_score,
            "judge_type": verdict.judge_type,
            "judge_reasoning": verdict.judge_reasoning,
            "in_human_review": False,
            "error_detail": log.error_detail,
        }
