from __future__ import annotations

import logging
import threading
import time

from pathlib import Path

from ..platform.base import BasePlatform
from ..result.models import RunRecord
from ..result.report import summarize_runs
from ..solver.base import BaseSolver

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    def __init__(self, logs_dir: str = "logs", enable_run_logs: bool = True) -> None:
        self.logs_dir = Path(logs_dir)
        self.enable_run_logs = enable_run_logs

    def run_target(
        self,
        platform: BasePlatform,
        solver: BaseSolver,
        target_id: str,
        timeout_sec: int,
    ) -> RunRecord:
        logger.info("Starting benchmark run for target id=%s timeout_sec=%s", target_id, timeout_sec)

        log_path = self._get_log_path(platform=platform, solver=solver, target_id=target_id)
        started_at = time.monotonic()

        try:
            target = platform.get_target(target_id)
            session = platform.prepare(target)
        except Exception as exc:
            duration_sec = time.monotonic() - started_at
            logger.exception("Failed to prepare target id=%s", target_id)
            return RunRecord(
                target_id=target_id,
                status="error",
                solved=False,
                duration_sec=duration_sec,
                submitted_flag=None,
                error=f"Platform prepare failed: {exc}",
                log_path=str(log_path) if log_path is not None else None,
            )

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            session.metadata["solver_log_path"] = str(log_path)
        submitted_flag: str | None = None
        solve_result = None
        error: str | None = None
        timed_out = False

        def submit_flag(flag: str):
            nonlocal submitted_flag
            submitted_flag = flag
            return platform.validate_flag(session, flag)

        result_holder: dict[str, object] = {}

        def _run_solver() -> None:
            try:
                result_holder["solve_result"] = solver.solve(session, submit_flag)
            except Exception as exc:
                logger.exception("Solver raised an exception for target id=%s", target_id)
                result_holder["error"] = str(exc)

        worker = threading.Thread(target=_run_solver, daemon=True)
        worker.start()
        worker.join(timeout=timeout_sec)

        if worker.is_alive():
            timed_out = True
            if hasattr(solver, "request_stop"):
                solver.request_stop()
        else:
            solve_result = result_holder.get("solve_result")
            error = result_holder.get("error")  # type: ignore[assignment]

        duration_sec = time.monotonic() - started_at

        try:
            if timed_out:
                logger.warning("Benchmark run timed out for target id=%s", target_id)
                return RunRecord(
                    target_id=target_id,
                    status="timeout",
                    solved=False,
                    duration_sec=duration_sec,
                    submitted_flag=submitted_flag,
                    error=None,
                    log_path=str(log_path) if log_path is not None else None,
                )

            if error is not None:
                logger.warning("Benchmark run failed for target id=%s error=%s", target_id, error)
                return RunRecord(
                    target_id=target_id,
                    status="error",
                    solved=False,
                    duration_sec=duration_sec,
                    submitted_flag=submitted_flag,
                    error=error,
                    log_path=str(log_path) if log_path is not None else None,
                )

            if solve_result is None:
                logger.warning("Solver returned no result for target id=%s", target_id)
                return RunRecord(
                    target_id=target_id,
                    status="error",
                    solved=False,
                    duration_sec=duration_sec,
                    submitted_flag=submitted_flag,
                    error="Solver returned no result",
                    log_path=str(log_path) if log_path is not None else None,
                )

            solved = solve_result.status == "solved"
            record = RunRecord(
                target_id=target_id,
                status=solve_result.status,
                solved=solved,
                duration_sec=duration_sec,
                submitted_flag=submitted_flag,
                solver_stats=solve_result.stats,
                log_path=str(log_path) if log_path is not None else None,
            )
            logger.info(
                "Completed benchmark run for target id=%s status=%s duration_sec=%.2f",
                target_id,
                record.status,
                record.duration_sec,
            )
            return record
        finally:
            platform.cleanup(session)
            logger.info("Finished cleanup after benchmark run for target id=%s", target_id)

    def _get_log_path(self, platform: BasePlatform, solver: BaseSolver, target_id: str) -> Path | None:
        if not self.enable_run_logs:
            return None
        platform_name = platform.__class__.__name__.removesuffix("Platform").lower()
        solver_name = solver.__class__.__name__.removesuffix("Solver").lower()
        return self.logs_dir / platform_name / solver_name / f"{target_id}.log"

    def run_all(
        self,
        platform: BasePlatform,
        solver: BaseSolver,
        target_ids: list[str] | None = None,
        category: str | list[str] | None = None,
        timeout_sec: int = 1800,
    ):
        if target_ids is None:
            targets = platform.list_targets()
            if category is not None:
                categories = {category} if isinstance(category, str) else set(category)
                targets = [
                    target for target in targets if target.metadata.get("category") in categories
                ]
            target_ids = [target.id for target in targets]
        logger.info("Starting benchmark suite total_targets=%s", len(target_ids))

        records = [
            self.run_target(platform=platform, solver=solver, target_id=target_id, timeout_sec=timeout_sec)
            for target_id in target_ids
        ]
        summary = summarize_runs(records)
        logger.info(
            "Completed benchmark suite total=%s solved=%s solve_rate=%.4f",
            summary.total,
            summary.solved,
            summary.solve_rate,
        )
        return summary
