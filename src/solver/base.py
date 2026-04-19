from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from ..result.models import Session, SolveResult, ValidationResult


class BaseSolver(ABC):
    def __init__(self) -> None:
        self._stop_event = threading.Event()

    def request_stop(self) -> None:
        """Signal the solver to stop as soon as possible."""
        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_event.is_set()

    def _clear_stop(self) -> None:
        self._stop_event.clear()

    @abstractmethod
    def solve(
        self,
        session: Session,
        submit_flag: Callable[[str], ValidationResult],
    ) -> SolveResult:
        raise NotImplementedError
