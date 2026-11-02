"""Spec 6.6 "No internal terms" and 8.4b: the what/where/why/fix of every case outside the
engine-bug layer name no engine module or class outside the 3.1 public table."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import cases
import pytest

import nexusbt as nx
from nexusbt.contracts import NexusBTError

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "nexusbt"
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
NAMED = {"Planner", "kernel", "_step"}  # 6.6's own examples


def public() -> set[str]:
    """The 3.1 table: each part of every name it writes, and the 6.6 classes."""
    rows = SPEC.split("### 3.1 ", 1)[1].split("\n### ", 1)[0].splitlines()
    names = {n for row in rows if row.startswith("| ") for n in re.findall(r"`([\w.]+)", row)}
    classes = {c.__name__ for c in NexusBTError.__subclasses__()}
    return {part for name in names for part in name.split(".")} | classes | {"NexusBTError"}


def internal() -> set[str]:
    """The engine's classes and `_` functions, its module paths, and 6.6's examples."""
    found = NAMED | {f"nexusbt.{p.name}" for p in SRC.iterdir() if p.is_dir()}
    for file in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) or (
                isinstance(node, ast.FunctionDef) and re.match(r"_[^_]", node.name)
            ):
                found.add(node.name)
    return found - public()


INTERNAL = re.compile("|".join(rf"(?<![\w.]){re.escape(n)}(?!\w)" for n in sorted(internal())))
CASES = [c.example() for c in NexusBTError.__subclasses__()] + cases.raised()


def internal_names(err: NexusBTError) -> list[str]:
    parts = (err.parts[part] for part in ("what", "where", "why", "fix"))
    return [hit for text in parts for hit in INTERNAL.findall(text)]


@pytest.mark.parametrize("err", [c for c in CASES if c.layer.split(" — ")[0] != "engine bug"])
def test_public_layers_have_no_internal_names(err: NexusBTError) -> None:
    assert internal_names(err) == [], err.code


def test_an_internal_name_is_found() -> None:
    err = nx.UnitError(
        what="Planner failed", where="nexusbt.compute", why="x", fix="DelistingPolicy", more="x",
        layer="config — argument x=1",
    )  # fmt: skip
    assert internal_names(err) == ["Planner", "nexusbt.compute", "DelistingPolicy"]
