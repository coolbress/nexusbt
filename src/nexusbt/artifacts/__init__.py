"""Run transactions, manifests, hashes, index, saved sources, ledgers, reconciliation, reports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunRecord: ...


@dataclass(frozen=True, slots=True)
class DerivedTables: ...


class RunTxn:
    def write_table(self, name: str, table: object) -> None:
        raise NotImplementedError

    def capture_sources(self, paths: Iterable[Path]) -> None:
        raise NotImplementedError

    def set_manifest(self, fields: Mapping[str, object]) -> None:
        raise NotImplementedError

    def seal(self) -> RunRecord:
        raise NotImplementedError

    def abort(self) -> None:
        raise NotImplementedError


class RunStore:
    def __init__(self, root: Path) -> None:
        raise NotImplementedError

    def begin(self, kind: str, name: str, study: str | None, **kwargs: object) -> RunTxn:
        raise NotImplementedError


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
