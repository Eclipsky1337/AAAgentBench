from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class Target:
    id: str
    name: str
    description: str
    files: list[str]
    flag_format: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    target: Target
    connection_info: dict[str, Any]
    workdir: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""


@dataclass
class SolveResult:
    status: Literal["solved", "give_up", "timeout", "error"]
    flag: str | None
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunRecord:
    target_id: str
    status: str
    solved: bool
    duration_sec: float
    submitted_flag: str | None
    error: str | None = None
    solver_stats: dict[str, Any] = field(default_factory=dict)
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunRecord":
        return cls(**data)


@dataclass
class BenchmarkSummary:
    total: int
    solved: int
    solve_rate: float
    avg_solve_time_sec: float | None
    avg_run_time_sec: float
    give_up_count: int
    timeout_count: int
    error_count: int
    records: list[RunRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["records"] = [record.to_dict() for record in self.records]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkSummary":
        copied = dict(data)
        copied["records"] = [RunRecord.from_dict(record) for record in copied.get("records", [])]
        return cls(**copied)
