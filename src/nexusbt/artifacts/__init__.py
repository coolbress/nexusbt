"""Run transactions, manifests, hashes, index, saved sources, ledgers, reconciliation, reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ._runstore import RunRecord as RunRecord
from ._runstore import RunStore as RunStore
from ._runstore import RunTxn as RunTxn


@dataclass(frozen=True, slots=True)
class DerivedTables: ...


class Index:
    """Holds the canonical pins."""

    def __init__(self, root: Path) -> None:
        raise NotImplementedError


class BookTxn:
    """Locking, state version comparison, commit, recovery (5.9.6); members with their ticket."""


class BookStore:
    def __init__(self, root: Path) -> None:
        raise NotImplementedError

    def open(self, name: str) -> BookTxn:
        raise NotImplementedError


def derive_tables(events: object, prices: object, fx: object) -> DerivedTables:
    raise NotImplementedError


def render_report(run: object) -> Path:
    raise NotImplementedError
