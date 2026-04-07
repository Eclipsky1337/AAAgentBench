from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from ..result.models import Session, SolveResult, ValidationResult


class BaseSolver(ABC):
    @abstractmethod
    def solve(
        self,
        session: Session,
        submit_flag: Callable[[str], ValidationResult],
    ) -> SolveResult:
        raise NotImplementedError
