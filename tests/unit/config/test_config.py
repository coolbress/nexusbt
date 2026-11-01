"""Spec T0.5a, `nexusbt.toml` (3.11, 2.6); the expected defaults are read from the 3.11 table."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from nexusbt.config import load_config
from nexusbt.contracts import CapabilityError, ConfigError

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
RESERVED = ["settlement.model", "compute.precision", "data.history_mode"]  # each a fixed() key


def spec_rows() -> list[tuple[str, str, str]]:
    """(table, key, default cell) per key of the 3.11 table; a row naming two keys gives two."""
    body = SPEC.split("### 3.11 ", 1)[1].split("\n---", 1)[0]
    rows = []
    for line in body.splitlines():
        if not line.startswith("| `["):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
        match = re.match(r"`\[([^\]]+)\] ([^`]+)`", cells[0])
        assert match, line
        table, first = match.groups()
        keys = [first, *re.findall(r", `([^`]+)`", cells[0])]
        split = cells[2].split(", ")
        defaults = split if len(split) == len(keys) > 1 else [cells[2]] * len(keys)
        rows += [(table, key, default) for key, default in zip(keys, defaults, strict=True)]
    return rows


def literal(cell: str) -> Any:
    """The cell as a TOML value, or `ValueError` when it is prose ("0 in every market")."""
    try:
        return tomllib.loads("v = " + cell.strip("`").replace(chr(0x2212), "-"))["v"]
    except tomllib.TOMLDecodeError as error:
        raise ValueError(cell) from error


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "nexusbt.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_match_spec_table(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, ""))
    rows = spec_rows()
    named = {(*table.split(".")[:2], key)[:2] for table, key, _ in rows}
    assert {(t, k) for t, keys in config.values.items() for k in keys} <= named
    compared = 0
    for table, key, cell in rows:
        if "<" in table + key:  # `[benchmarks] <MARKET>` and the like: the table only
            assert table.split(".")[0] in config.values, table
            continue
        assert key in config.values[table], f"[{table}] {key}"
        try:
            expected = literal(cell)
        except ValueError:
            continue
        assert config.values[table][key] == expected, f"[{table}] {key}"
        compared += 1
    assert compared >= 100
    config.values["data"]["require_profiles"].append("x")  # each Config owns its defaults
    assert load_config().values["data"]["require_profiles"] == []


def test_unknown_key_suggests(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, "[execution]\nmax_participaton = 0.1\n"))
    assert caught.value.parts["fix"].startswith("did you mean: max_participation")
    assert caught.value.parts["where"] == "nexusbt.toml [execution] max_participaton"


def test_secret_like_keys_rejected(tmp_path: Path) -> None:
    for text in ('[broker]\napi_key = "x"\n', '[taxes.groups.kr]\nPassword = "x"\n'):
        with pytest.raises(ConfigError, match=r"secrets do not belong in nexusbt\.toml"):
            load_config(write(tmp_path, text))


@pytest.mark.parametrize("key", RESERVED)
def test_reserved_keys_accept_only_v1_value(tmp_path: Path, key: str) -> None:
    table, name = key.split(".")
    with pytest.raises(CapabilityError):
        load_config(write(tmp_path, f"[{table}]\n{name} = 'other'\n"))


def test_cash_rate_default_zero(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "")).values["account"]["cash_rate_bps"] == 0
    config = load_config(write(tmp_path, "[account]\ncash_rate_bps = {KR = 150}\n"), markets=["KR"])
    assert config.values["account"]["cash_rate_bps"] == {"KR": 150}
    for bad in ("2001", "-1", "true", "'150'"):
        with pytest.raises(ConfigError, match="cash_rate_bps"):
            load_config(write(tmp_path, f"[account]\ncash_rate_bps = {bad}\n"))
