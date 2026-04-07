from __future__ import annotations

from abc import ABC, abstractmethod

from ..result.models import Session, Target, ValidationResult


class BasePlatform(ABC):
    @abstractmethod
    def list_targets(self) -> list[Target]:
        raise NotImplementedError

    @abstractmethod
    def get_target(self, target_id: str) -> Target:
        raise NotImplementedError

    @abstractmethod
    def prepare(self, target: Target) -> Session:
        raise NotImplementedError

    @abstractmethod
    def validate_flag(self, session: Session, flag: str) -> ValidationResult:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, session: Session) -> None:
        raise NotImplementedError
