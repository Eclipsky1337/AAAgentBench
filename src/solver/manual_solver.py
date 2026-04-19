from __future__ import annotations

from ..result.models import Session, SolveResult
from .base import BaseSolver


class ManualSolver(BaseSolver):
    """A minimal interactive solver for local smoke testing."""

    def solve(self, session: Session, submit_flag) -> SolveResult:
        super().__init__()
        print(f"Target: {session.target.name}")
        print(session.target.description)
        print(f"Files: {session.target.files}")
        print(f"Connection: {session.connection_info}")
        print(f"Workdir: {session.workdir}")

        while True:
            candidate = input("flag (or 'giveup'): ").strip()
            if candidate == "giveup":
                return SolveResult(status="give_up", flag=None)
            result = submit_flag(candidate)
            print(result.message)
            if result.ok:
                return SolveResult(status="solved", flag=candidate)
