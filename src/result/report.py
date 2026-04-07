from __future__ import annotations

import logging

from .models import BenchmarkSummary, RunRecord

logger = logging.getLogger(__name__)


def summarize_runs(records: list[RunRecord]) -> BenchmarkSummary:
    total = len(records)
    solved_records = [record for record in records if record.solved]
    give_up_count = sum(1 for record in records if record.status == "give_up")
    timeout_count = sum(1 for record in records if record.status == "timeout")
    error_count = sum(1 for record in records if record.status == "error")

    solved = len(solved_records)
    solve_rate = solved / total if total else 0.0
    avg_solve_time_sec = (
        sum(record.duration_sec for record in solved_records) / solved if solved else None
    )
    avg_run_time_sec = (
        sum(record.duration_sec for record in records) / total if total else 0.0
    )

    summary = BenchmarkSummary(
        total=total,
        solved=solved,
        solve_rate=solve_rate,
        avg_solve_time_sec=avg_solve_time_sec,
        avg_run_time_sec=avg_run_time_sec,
        give_up_count=give_up_count,
        timeout_count=timeout_count,
        error_count=error_count,
        records=records,
    )
    logger.info(
        "Summarized runs total=%s solved=%s give_up=%s timeout=%s error=%s avg_solve_time=%s avg_run_time=%.2f",
        summary.total,
        summary.solved,
        summary.give_up_count,
        summary.timeout_count,
        summary.error_count,
        summary.avg_solve_time_sec,
        summary.avg_run_time_sec,
    )
    return summary
