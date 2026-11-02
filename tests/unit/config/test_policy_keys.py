"""#95: the 3.11 choice keys of `nexusbt.toml` are checked with the 2.4 policy enums.

The enum ↔ key pairs are read from the spec's 2.4 `contracts` row; what a key
accepts is read through `load_config()`: each value it loads, and the choices
its E16 lists for a value it refuses.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from nexusbt import contracts
from nexusbt.config import load_config
from nexusbt.contracts import ConfigError, PinsPolicy

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
ROW = next(line for line in SPEC.splitlines() if line.startswith("| `contracts` |"))
NAMED = dict(re.findall(r"`(\w+Policy)` `(\[[^\]]+\] \w+)`", ROW))  # enum → its 3.11 key


def toml_and_path(key: str, value: str) -> tuple[str, tuple[str, ...], list[str]]:
    """The nexusbt.toml that writes `key = value`, the path to it in `values`, the markets."""
    table, name = key.strip("[").split("] ")
    if table == "rounding.<MARKET>":  # a market's rounding table holds named `{mode, unit}` items
        return (
            f'[rounding.KR.commission]\n{name} = "{value}"\n',
            ("rounding", "KR", "commission", name),
            ["KR"],
        )
    if table == "taxes.groups.<name>":
        return f'[taxes.groups.g]\n{name} = "{value}"\n', ("taxes", "groups", "g", name), []
    return f'[{table}]\n{name} = "{value}"\n', (table, name), []


def load(tmp_path: Path, text: str, markets: list[str]) -> Any:
    (path := tmp_path / "nexusbt.toml").write_text(text, encoding="utf-8")
    return load_config(path, markets=markets).values


def test_2_4_pairs_26_enums_with_keys() -> None:
    assert len(NAMED) == 26


@pytest.mark.parametrize(("name", "key"), sorted(NAMED.items()))
def test_key_accepts_exactly_the_enum_values(tmp_path: Path, name: str, key: str) -> None:
    enum: type[StrEnum] = getattr(contracts, name)
    for member in enum:
        text, at, markets = toml_and_path(key, member.value)
        got: Any = load(tmp_path, text, markets)
        for part in at:
            got = got[part]
        assert got is member, key
        assert got == member.value  # still the 3.11 string
    text, at, markets = toml_and_path(key, "not_a_choice")
    with pytest.raises(ConfigError) as caught:
        load(tmp_path, text, markets)
    assert caught.value.code == "E16"
    fix, what = caught.value.parts["fix"], caught.value.parts["what"]
    assert fix.startswith("use one of "), fix  # the shape `one()` gives today
    assert sorted(re.findall(r"'([^']+)'", fix)) == sorted(m.value for m in enum), key
    assert "'not_a_choice'" in what, what
    assert what.endswith(": not allowed"), what


def test_defaults_are_enum_members(tmp_path: Path) -> None:
    values = load(tmp_path, "", [])
    assert values["data"]["pins"] is PinsPolicy.INDEX_ROOT  # not the enum's first member
    for name, key in NAMED.items():
        if "<" not in key:  # the two nested keys default to a rules pack or to no table
            table, field = key.strip("[").split("] ")
            assert isinstance(values[table][field], getattr(contracts, name)), key
