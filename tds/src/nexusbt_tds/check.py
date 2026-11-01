"""`check(path, *, level, ...) -> CheckResult`: the levels manifest, schema and full (TDS 8.2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Level = Literal["manifest", "schema", "full"]


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    declared: bool
    verified_level: Literal["none"] | Level
    result: Literal["pass", "fail", "not_checked"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    """`.errors`, `.warnings`, `.profiles`, `.unchecked`, `.to_jsonl()` come with T0.13a."""


def check(
    path: Path,
    *,
    level: Level,
    profiles: Sequence[str] | None = None,
    datasets: Sequence[str] | None = None,
    max_errors: int = 1000,
) -> CheckResult:
    raise NotImplementedError
