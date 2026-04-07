"""Platform implementations."""

from __future__ import annotations

from typing import Any

from .base import BasePlatform
from .nyu_platform import NyuPlatform

AVAILABLE_PLATFORMS: dict[str, type[BasePlatform]] = {
    "nyu": NyuPlatform,
}


def create_platform(name: str, **kwargs: Any) -> BasePlatform:
    try:
        platform_cls = AVAILABLE_PLATFORMS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown platform: {name}") from exc
    return platform_cls(**kwargs)


__all__ = [
    "AVAILABLE_PLATFORMS",
    "BasePlatform",
    "NyuPlatform",
    "create_platform",
]
