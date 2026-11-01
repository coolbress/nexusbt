"""Spec 2.4: the policy enums of `contracts`, one per 3.11 key with two or more closed choices.

Expected values are read from the spec, not restated here: the names and their
keys from the 2.4 `contracts` row, each key's choices from its 3.11 row.
"""

from __future__ import annotations

import inspect
import re
from enum import StrEnum
from pathlib import Path

import pytest

from nexusbt import contracts

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")


def named_in_2_4() -> dict[str, str]:
    """Enum name → its 3.11 key, as the 2.4 `contracts` row pairs them."""
    row = next(line for line in SPEC.splitlines() if line.startswith("| `contracts` |"))
    return dict(re.findall(r"`(\w+Policy)` `(\[[^\]]+\] \w+)`", row))


def rows_3_11() -> list[list[str]]:
    """The cells of each 3.11 table row; `\\|` inside a cell is not a separator."""
    body = SPEC.split("### 3.11 ", 1)[1].split("\n### ", 1)[0]
    return [
        [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        for line in body.splitlines()
        if line.startswith("| `[")
    ]


ROWS = rows_3_11()


def choices(key: str) -> list[str]:
    """The closed choices 3.11 gives for `key`, in the order it writes them.

    A row that covers several names (`[evaluate] freq`, `quantiles`, … or a
    `{mode, unit}` type) gives each name's choices after that name in the
    Validation cell. A type of quoted literals (`"cash"` \\| `"margin"`) is the
    choice list itself. Otherwise the Validation cell opens with `a / b / c`:
    parentheses, `= meaning` clauses and what follows the first `.`, `—` or `,`
    are commentary.
    """
    parts = re.fullmatch(r"(\[[^\]]+\]) (\w+)", key)
    assert parts, key
    section, name = parts.groups()
    for first, kind, _default, validation, *_ in ROWS:
        names = re.findall(r"`(?:\[[^\]]+\] )?([^`]+)`", first)
        if not first.startswith(f"`{section} "):
            continue
        covered = names + re.findall(r"\w+", kind) if kind.startswith("{") else names
        if name not in covered:
            continue
        literals = re.findall(r'`"(\w+)"`', kind)
        if literals:
            return literals
        text = validation
        if len(covered) > 1:
            text = text.split(f"{name} ", 1)[1]
        while re.search(r"\([^()]*\)", text):
            text = re.sub(r"\([^()]*\)", "", text)
        text = re.split(r"\.|—", text, maxsplit=1)[0]
        text = re.sub(r"=[^/]*", "", text).split(",", 1)[0]
        return [choice.strip() for choice in text.split("/")]
    raise AssertionError(f"no 3.11 row for {key}")


NAMED = named_in_2_4()


def test_2_4_names_26_policy_enums() -> None:
    assert len(NAMED) == 26


def test_policy_enums_are_the_ones_2_4_names() -> None:
    defined = {
        name
        for name, obj in inspect.getmembers(contracts, inspect.isclass)
        if issubclass(obj, StrEnum) and name.endswith("Policy")
    }
    assert defined == set(NAMED)


@pytest.mark.parametrize(("name", "key"), sorted(NAMED.items()))
def test_values_are_the_3_11_choices(name: str, key: str) -> None:
    expected = choices(key)
    assert len(expected) >= 2, expected
    assert all(re.fullmatch(r"[a-z_+]+", c) for c in expected), expected
    assert [member.value for member in getattr(contracts, name)] == expected


@pytest.mark.parametrize("name", sorted(NAMED))
def test_member_names_follow_unit_rule(name: str) -> None:
    for member in getattr(contracts, name):
        assert member.name == re.sub(r"[^A-Z0-9]", "_", member.value.upper())
