"""Labels, IC, quantiles, breadth, statistics, segments, validation methods, attempts, probes.

2.4 names `psr` … `signal_weight_corr` and the probes without signatures, and
gives `forward_labels` only its `kind`; until their tickets they take anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from nexusbt.contracts import FactorFrame


@dataclass(frozen=True, slots=True)
class LabelFrame: ...


@dataclass(frozen=True, slots=True)
class EvalConfig: ...


@dataclass(frozen=True, slots=True)
class FactorStats: ...


@dataclass(frozen=True, slots=True)
class Segments: ...


class TrialRegistry:
    """Candidates, observations, cohorts."""


def forward_labels(*args: object, kind: Literal["econ", "adj"] = "econ") -> LabelFrame:
    raise NotImplementedError


def factor_stats(values: FactorFrame, labels: LabelFrame, cfg: EvalConfig) -> FactorStats:
    raise NotImplementedError


def psr(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def dsr(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def min_trl(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def pbo_cscv(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def bhy_adjust(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def lo_sharpe(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def newey_west_t(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def signal_weight_corr(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def probe_truncation(*args: object, **kwargs: object) -> object:
    raise NotImplementedError


def probe_start(*args: object, **kwargs: object) -> object:
    raise NotImplementedError
