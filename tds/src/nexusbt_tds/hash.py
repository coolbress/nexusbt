"""`value_hash`, `semantic_hash`: canonical value serialisation and the package hashes (TDS 4.5)."""

from __future__ import annotations

from pathlib import Path


def value_hash(path: Path, dataset: str) -> str:
    raise NotImplementedError


def semantic_hash(path: Path) -> str:
    raise NotImplementedError
