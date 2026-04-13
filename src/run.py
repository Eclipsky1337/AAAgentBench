from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .platform import AVAILABLE_PLATFORMS, create_platform
from .result.report import summarize_runs
from .result.store import load_run_record, load_run_records, save_run_record
from .runner.benchmark_runner import BenchmarkRunner
from .solver import AVAILABLE_SOLVERS, create_solver

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AAAgentBench benchmarks.")
    parser.add_argument(
        "--platform",
        choices=sorted(AVAILABLE_PLATFORMS.keys()),
        default="nyu",
        help="Platform implementation to use.",
    )
    parser.add_argument(
        "--solver",
        choices=sorted(AVAILABLE_SOLVERS.keys()),
        default="codex",
        help="Solver implementation to use.",
    )
    parser.add_argument(
        "--testcase",
        "--target-id",
        dest="target_id",
        help="Single target id to run.",
    )
    parser.add_argument(
        "--target-list-file",
        type=Path,
        help="Path to a text file containing one target id per line.",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all targets in the selected platform split.",
    )
    parser.add_argument(
        "--split",
        default="test",
        help="Dataset split for the platform.",
    )
    parser.add_argument(
        "--category",
        action="append",
        help="Filter targets by category when using --run-all. Can be passed multiple times.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Dataset version for platforms that support it.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=1800,
        help="Per-target timeout in seconds.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for solvers that support it.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum solver attempts for solvers that support retries.",
    )
    parser.add_argument(
        "--sandbox-mode",
        default="workspace-write",
        help="Sandbox mode for Codex solver.",
    )
    parser.add_argument(
        "--save-result",
        action="store_true",
        help="Save single-target run results to the local results directory.",
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="Directory used for per-target runtime logs.",
    )
    parser.add_argument(
        "--disable-run-logs",
        action="store_true",
        help="Disable per-target runtime log files.",
    )
    parser.add_argument(
        "--pentestgpt-container-name",
        default="pentestgpt",
        help="Docker container name for the PentestGPT solver.",
    )
    parser.add_argument(
        "--pentestgpt-auth-mode",
        default="openrouter",
        help="Authentication mode passed to PentestGPT.",
    )
    parser.add_argument(
        "--pentestgpt-shared-workspace-host-root",
        default=None,
        help="Host path mirrored into the PentestGPT container for static challenge files. "
        "Required when using the pentestgpt solver.",
    )
    parser.add_argument(
        "--pentestgpt-shared-workspace-container-root",
        default="/workspace/aaagentbench",
        help="Container path corresponding to the shared static challenge workspace.",
    )
    parser.add_argument(
        "--pentestgpt-anthropic-base-url",
        default="http://127.0.0.1:3456",
        help="ANTHROPIC_BASE_URL passed to PentestGPT.",
    )
    parser.add_argument(
        "--pentestgpt-anthropic-auth-token",
        default=None,
        help="ANTHROPIC_AUTH_TOKEN passed to PentestGPT. "
        "Falls back to the PENTESTGPT_ANTHROPIC_AUTH_TOKEN environment variable.",
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory used for saved single-target results and offline summaries.",
    )
    parser.add_argument(
        "--summary-from-results",
        action="store_true",
        help="Build a summary from previously saved single-target results.",
    )
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="Ignore cached single-target results and rerun them.",
    )
    return parser


def create_platform_from_args(args: argparse.Namespace):
    if args.platform == "nyu":
        return create_platform(
            args.platform,
            split=args.split,
            version=args.version,
        )
    return create_platform(args.platform)


def create_solver_from_args(args: argparse.Namespace):
    if args.solver == "codex":
        return create_solver(
            args.solver,
            model=args.model,
            max_attempts=args.max_attempts,
            sandbox_mode=args.sandbox_mode,
        )
    if args.solver == "pentestgpt":
        if not args.pentestgpt_shared_workspace_host_root:
            sys.exit(
                "error: --pentestgpt-shared-workspace-host-root is required "
                "when using the pentestgpt solver"
            )
        return create_solver(
            args.solver,
            container_name=args.pentestgpt_container_name,
            model=args.model,
            auth_mode=args.pentestgpt_auth_mode,
            shared_workspace_host_root=args.pentestgpt_shared_workspace_host_root,
            shared_workspace_container_root=args.pentestgpt_shared_workspace_container_root,
            anthropic_base_url=args.pentestgpt_anthropic_base_url,
            anthropic_auth_token=args.pentestgpt_anthropic_auth_token,
            command_timeout_sec=args.timeout_sec,
        )
    return create_solver(args.solver)


def get_target_ids_from_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    target_ids: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        target_ids.append(stripped)
    return target_ids


def get_target_ids_for_run_all(args: argparse.Namespace, platform) -> list[str]:
    targets = platform.list_targets()
    if args.category is None:
        return [target.id for target in targets]

    categories = set(args.category)
    return [target.id for target in targets if target.metadata.get("category") in categories]


def get_result_path(args: argparse.Namespace) -> Path:
    return Path(args.results_dir) / args.platform / args.solver / f"{args.target_id}.json"


def get_result_path_for_target(args: argparse.Namespace, target_id: str) -> Path:
    return Path(args.results_dir) / args.platform / args.solver / f"{target_id}.json"


def run_or_load_record(
    *,
    args: argparse.Namespace,
    runner: BenchmarkRunner,
    platform,
    solver,
    target_id: str,
):
    result_path = get_result_path_for_target(args, target_id)
    use_cache = args.save_result and not args.force_rerun and result_path.exists()

    if use_cache:
        logger.info("Using cached run record for target id=%s from %s", target_id, result_path)
        return load_run_record(result_path)

    record = runner.run_target(
        platform=platform,
        solver=solver,
        target_id=target_id,
        timeout_sec=args.timeout_sec,
    )

    if args.save_result:
        save_run_record(result_path, record)

    return record


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    if args.summary_from_results:
        if args.target_id or args.run_all or args.target_list_file:
            parser.error(
                "--summary-from-results cannot be combined with --testcase, --target-list-file, or --run-all"
            )
    elif sum(bool(value) for value in (args.run_all, args.target_id, args.target_list_file)) != 1:
        parser.error(
            "exactly one of --testcase/--target-id, --target-list-file, or --run-all is required"
        )

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.summary_from_results:
        results_root = Path(args.results_dir) / args.platform / args.solver
        records = load_run_records(results_root)
        summary = summarize_runs(records)
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, default=str))
        raise SystemExit(0)

    platform = create_platform_from_args(args)
    runner = BenchmarkRunner(logs_dir=args.logs_dir, enable_run_logs=not args.disable_run_logs)
    solver = create_solver_from_args(args)

    if args.run_all:
        target_ids = get_target_ids_for_run_all(args, platform)
        records = [
            run_or_load_record(
                args=args,
                runner=runner,
                platform=platform,
                solver=solver,
                target_id=target_id,
            )
            for target_id in target_ids
        ]
        summary = summarize_runs(records)
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, default=str))
    elif args.target_list_file:
        target_ids = get_target_ids_from_file(args.target_list_file)
        records = [
            run_or_load_record(
                args=args,
                runner=runner,
                platform=platform,
                solver=solver,
                target_id=target_id,
            )
            for target_id in target_ids
        ]
        summary = summarize_runs(records)
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        record = run_or_load_record(
            args=args,
            runner=runner,
            platform=platform,
            solver=solver,
            target_id=args.target_id,
        )
        print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, default=str))
