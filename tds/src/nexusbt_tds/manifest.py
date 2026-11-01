"""`read_manifest`, `build_manifest`: tds.json read and drafted (TDS 4, 8.1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Manifest:
    """tds.json as read (TDS 4); its fields come with T0.13a."""


def read_manifest(path: Path) -> Manifest:
    raise NotImplementedError


def build_manifest(path: Path) -> Manifest:
    raise NotImplementedError
