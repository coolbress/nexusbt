"""Spec 8.4b, the layer golden: every 6.6 code and condition has a case whose `layer` line
matches `layers.toml` with its layer's tail, and a `fix` line. A case is `example()`, plus
`EXTRA` for a second condition; cases that run engine code come with each code's ticket."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.contracts import NexusBTError

HERE = Path(__file__).resolve().parent
SPEC = (HERE.parents[1] / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
TABLE: dict[str, str | dict[str, str]] = tomllib.loads((HERE / "layers.toml").read_text())
CLASSES = {c.code: c for c in NexusBTError.__subclasses__()}
CODES = sorted(TABLE, key=lambda code: int(code[1:]))

#: A second condition's case, where the example shows the first.
EXTRA = [
    nx.CapabilityError(
        what="fundamentals_state not in snapshot; needed for Fund.roe",
        where="snapshot s1",
        why="the term reads a dataset this snapshot does not have",
        fix="use a snapshot with fundamentals_state, or remove Fund.roe",
        more="spec 4.3 and 4.5; tds check snap --level full",
        layer="data — snapshot s1 / fundamentals_state / column value / producer synthetic",
        subject="Fund.roe",
    )
]
CASES = [CLASSES[code].example() for code in CODES] + EXTRA

#: The tail each layer carries (6.6 "Layer line").
TAILS = {
    "data": r"snapshot \S+ / \S+ / column \S+ / producer .+"
    r"|run \S+ / series \S+ / T = \d+ \(needs \d+\)"  # E21's second form
    r"|file \S+ / \S+ / column \S+",  # a user's own file: #52 Decisions 2026-11-02
    "your code": r"\S+:\d+ in \w+( \(\w+ slot\))?",
    "config": r"nexusbt\.toml \[[\w.]+\] \w+ = .+|argument \w+=.+",
    "engine bug": r"please report: nexusbt bugreport \S+",
}


def layer(err: NexusBTError) -> tuple[list[str], list[str]]:
    """The layers of the second line, outside in, and the tail of each."""
    label, _, rest = str(err).splitlines()[1].strip().partition("  ")
    assert label == "layer"
    names, _, tails = rest.strip().partition(" — ")
    return names.split(" → "), tails.split(" → ")


def conditions(code: str) -> dict[str, str]:
    return value if isinstance(value := TABLE[code], dict) else {"": value}


def condition_of(err: NexusBTError) -> str:
    names = " → ".join(layer(err)[0])
    found = [c for c, name in conditions(err.code).items() if name in (names, "*")]
    assert found, f"{err.code}: layer {names!r} is not in layers.toml"
    return found[0]


def spec_layers() -> dict[str, set[str]]:
    """The 6.6 "Layers" paragraph: code → its layers (E45's "that skip reason" is `*`)."""
    paragraph = re.search(r"^Layers \(`layers\.toml`, \[R4-15\]\): (.+)\.$", SPEC, re.MULTILINE)
    assert paragraph
    found: dict[str, set[str]] = {}
    for item in paragraph[1].split("; "):
        codes, _, text = item.partition(" = ")
        text = re.sub(r"\s*(\([^)]*\)|\[[^]]*\])", "", text).strip()
        names = {"*"} if "skip reason" in text else set(text.split(" or "))
        for code in codes.split("·"):
            found.setdefault(code, set()).update(names)
    return found


def test_every_code_has_layer_case() -> None:
    assert [f"E{n}" for n in range(1, 50)] == CODES == sorted(CLASSES, key=lambda c: int(c[1:]))
    covered = {(err.code, condition_of(err)) for err in CASES}
    assert covered == {(code, c) for code in CODES for c in conditions(code)}


def test_layer_line_matches_table() -> None:
    """The table is the 6.6 paragraph; each case is matched to it in the test above."""
    assert spec_layers() == {code: set(conditions(code).values()) for code in CODES}


@pytest.mark.parametrize("err", CASES, ids=lambda err: err.code)
def test_layer_tail_fields(err: NexusBTError) -> None:
    names, tails = layer(err)
    assert len(names) == len(tails)
    for name, tail in zip(names, tails, strict=True):
        assert re.fullmatch(TAILS[name], tail), (name, tail)
        if name == "data" and tail.startswith("snapshot "):
            assert re.search(r"tds check \S+ --level full", err.parts["more"])


@pytest.mark.parametrize("err", CASES, ids=lambda err: err.code)
def test_fix_line_present(err: NexusBTError) -> None:
    lines = str(err).splitlines()[1:]
    labels = [line.split()[0] for line in lines if not line.startswith(" " * 9)]
    assert labels == ["layer", "what", "where", "why", "fix", "more"]
    assert err.parts["fix"].strip()


@pytest.mark.parametrize("bad", ["", "your code", "network — down", "data → — x"])
def test_layer_line_rejects_an_unknown_layer(bad: str) -> None:
    with pytest.raises(ValueError, match="layer"):
        nx.UnitError(what="x", where="x", why="x", fix="x", more="x", layer=bad)
