"""Planning, reference kernels, fast kernels, adjustment, cross-sections, L1 cache, executor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexusbt.contracts import DecisionGrid, FactorFrame
    from nexusbt.data import Snapshot
    from nexusbt.pipeline import Pipeline


@dataclass(frozen=True, slots=True)
class ComputePolicy: ...


@dataclass(frozen=True, slots=True)
class TermCache: ...


def compute(
    pipeline: Pipeline,
    grid: DecisionGrid,
    snapshot: Snapshot,
    policy: ComputePolicy,
    cache: TermCache | None = None,
) -> FactorFrame:
    raise NotImplementedError
