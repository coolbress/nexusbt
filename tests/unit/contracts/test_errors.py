"""Spec T0.4: the teaching errors E1..E39 and their five-part message (6.6).

The codes, class names and kinds are read from the 6.6 table, not restated here.
"""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.contracts import NexusBTError

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
ROW = re.compile(r"^\| (E\d+) \| `(\w+)`[^|]*\| ([^|]+) \|", re.MULTILINE)
KINDS = ("block", "fail", "warning", "notice")
LAYER = "config — argument x=1"

#: 6.6 rows E1..E39: code → (class name, kinds in the order the Kind cell names them); a
#: retired number's row names a class that left with its code.
ROWS = [(code, name, kind) for code, name, kind in ROW.findall(SPEC) if int(code[1:]) <= 39]
RETIRED = {code: name for code, name, _ in re.findall(
    r"^\| (E\d+) \| `(\w+)` \| (\w+) \| retired ", SPEC, re.MULTILINE)}  # fmt: skip
TABLE = {
    code: (name, tuple(re.findall("|".join(KINDS), kind)))
    for code, name, kind in ROWS
    if code not in RETIRED
}
CODES = sorted(TABLE, key=lambda code: int(code[1:]))

#: A producer's internal ticket id has the shape `ABC-123`; TDS codes (`TDS-A010`) and
#: fallback ids (`F-05`) do not.
TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def error(code: str) -> type[NexusBTError]:
    cls: type[NexusBTError] = getattr(nx, TABLE[code][0])
    return cls


def test_all_codes_present_E1_to_E39() -> None:  # noqa: N802 - the name the issue gives
    assert [f"E{n}" for n in range(1, 40) if f"E{n}" not in RETIRED] == CODES
    assert not any(hasattr(nx, name) for name in RETIRED.values())  # retired: not in the engine
    for code in CODES:
        cls = error(code)
        assert issubclass(cls, NexusBTError), code
        assert cls.code == code


@pytest.mark.parametrize("code", CODES)
def test_message_has_five_parts(code: str) -> None:
    lines = str(error(code).example()).splitlines()
    assert lines[0].startswith(f"{TABLE[code][0]} [{code}]")
    labels = [line.split()[0] for line in lines[1:] if not line.startswith(" " * 9)]
    assert labels == ["layer", "what", "where", "why", "fix", "more"]  # the layer line is T0.4b's


def test_codes_E40_to_E49_present() -> None:  # noqa: N802 - the name the issue gives
    rows = {code: (name, kind) for code, name, kind in ROW.findall(SPEC)}
    retired = [f"E{n}" for n in range(40, 50) if f"E{n}" in RETIRED]
    assert not any(hasattr(nx, rows[code][0]) for code in retired)  # retired: not in the engine
    for n in (n for n in range(40, 50) if f"E{n}" not in RETIRED):
        name, kind = rows[f"E{n}"]
        cls: type[NexusBTError] = getattr(nx, name)
        assert cls.code == f"E{n}"
        assert cls.kinds == tuple(re.findall("|".join(KINDS), kind))
        assert cls.example().kind == cls.kinds[0]


def test_message_rejects_a_missing_part() -> None:
    with pytest.raises(ValueError, match="why"):
        nx.UnitError(what="x", where="x", why=" ", fix="x", more="x", layer=LAYER)


def test_column_name_error_header_and_attribute_error() -> None:
    err = nx.ColumnNameError.example()
    assert isinstance(err, AttributeError)
    assert str(err).splitlines()[0] == "ColumnNameError [E7] in strategy.py:12 Price.clsoe"


@pytest.mark.parametrize("code", CODES)
def test_blocking_classification_matches_table(code: str) -> None:
    cls = error(code)
    assert cls.kinds == TABLE[code][1]
    assert cls.example().kind == cls.kinds[0]


def test_only_listed_kinds_are_accepted() -> None:
    parts = dict.fromkeys(("what", "where", "why", "fix", "more"), "x") | {"layer": LAYER}
    assert nx.FxStaleError(**parts, kind="warning").kind == "warning"
    with pytest.raises(ValueError, match="warning"):
        nx.UnitError(**parts, kind="warning")


def test_snapshot_error_carries_tds_codes_and_hints() -> None:
    err = nx.SnapshotError.from_check(
        path="snap/2026-10-30",
        counts={"TDS-A003": 3, "TDS-M012": 1},
        dataset="corporate_actions",
        file="corporate_actions/part-0.parquet",
        key="event_id=7",
        hint="price_factor null while factor_method is not unavailable",
        snapshot_id="s1",
        producer="synthetic",
        producer_hints={"TDS-A003": "re-export price factors (export step 'factors')"},
    )
    text = str(err)
    assert err.code == "E14"
    assert err.layer == "data — snapshot s1 / corporate_actions / column - / producer synthetic"
    assert "TDS-A003" in text.splitlines()[2]  # the first code leads `what`
    assert "TDS-A003 (3), TDS-M012 (1)" in text
    assert "producer hint (TDS-A003): re-export price factors (export step 'factors')" in text
    assert "tds check snap/2026-10-30 --level full; nexusbt doctor --full" in text


def test_snapshot_error_without_hint_names_none() -> None:
    check = partial(nx.SnapshotError.from_check, path="p", dataset="-", file="tds.json", key="-")
    err = check(counts={"TDS-M001": 1}, hint="h", snapshot_id="s1", producer="p")
    assert "producer hint" not in str(err)
    with pytest.raises(ValueError, match="at least one"):
        check(counts={}, hint="h", snapshot_id="s1", producer="p")


def private_words() -> list[str]:
    path = ROOT / ".hygiene-private.txt"  # git-ignored; present only on the owner's machine
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.parametrize("code", CODES)
def test_messages_have_no_producer_tickets(code: str) -> None:
    text = str(error(code).example())
    assert not TICKET.findall(text)
    assert not [word for word in private_words() if word.lower() in text.lower()]
