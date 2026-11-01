"""Reading and validating nexusbt.toml (secret keys forbidden)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Config: ...


def load_config(
    path: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    *,
    markets: Sequence[str] | None = None,
) -> Config:
    raise NotImplementedError
