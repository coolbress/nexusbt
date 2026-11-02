"""Spec T0.5a, `nexusbt.toml` (3.11, 2.6); the expected defaults are read from the 3.11 table."""

from __future__ import annotations

import importlib
import json
import re
import tomllib
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.config import check_long_short, load_config
from nexusbt.contracts import CapabilityError, ConfigError, SnapshotError

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
RESERVED = ["settlement.model", "compute.precision", "data.history_mode"]  # each a fixed() key
KR_US = {"KR": "KRW", "US": "USD"}
MARGIN = '[account]\ntype = "margin"\ninitial_margin = {US = 0.5}\n'


@pytest.fixture(autouse=True)
def _no_data_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)


def snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, markets: dict[str, str]) -> Path:
    """A data root whose `LATEST` snapshot's tds.json declares `markets`; the cwd is `tmp_path`."""
    (folder := tmp_path / "data" / "20261027-143144").mkdir(parents=True, exist_ok=True)
    declared = {name: {"currency": ccy} for name, ccy in markets.items()}
    (folder / "tds.json").write_text(json.dumps({"markets": declared}), encoding="utf-8")
    (tmp_path / "data" / "LATEST").write_text(folder.name, encoding="utf-8")
    monkeypatch.setenv("NEXUSBT_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    return folder


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


def write(tmp_path: Path, text: str) -> Path:
    (path := tmp_path / "nexusbt.toml").write_text(text, encoding="utf-8")
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
        try:  # the cell as a TOML value; prose ("0 in every market") is skipped
            expected = tomllib.loads("v = " + cell.strip("`").replace(chr(0x2212), "-"))["v"]
        except tomllib.TOMLDecodeError:
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
    assert caught.value.layer == "config — nexusbt.toml [execution] max_participaton = 0.1"


def test_secret_like_keys_rejected(tmp_path: Path) -> None:
    for text in ('[broker]\napi_key = "sk-1"\n', '[taxes.groups.kr]\nPassword = "sk-1"\n'):
        with pytest.raises(ConfigError, match=r"secrets do not belong in nexusbt\.toml") as caught:
            load_config(write(tmp_path, text))
        assert "sk-1" not in str(caught.value)  # the secret is never echoed
        assert caught.value.layer.endswith("= <hidden>")  # 6.6 config tail


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


def test_unknown_market_in_a_market_key(tmp_path: Path) -> None:
    for text in ("[sleeves]\nweights = {JP = 1}\n", "[defaults]\nclock = 'JP_close'\n"):
        with pytest.raises(ConfigError, match="unknown market JP; snapshot markets: KR, US"):
            load_config(write(tmp_path, text), markets=["KR", "US"])
    with pytest.raises(CapabilityError, match="utc"):  # 3.11 clock: `utc:HH:MM` reserved, E18
        load_config(write(tmp_path, "[defaults]\nclock = 'utc:14:00'\n"))


def test_market_tables_and_table_values_are_checked(tmp_path: Path) -> None:
    text = '[rounding.KR]\ncommission = {mode = "down", unit = 1}\n[fx]\nseries = {USDKRW = "c@x"}'
    config = load_config(write(tmp_path, text), markets=["KR"])
    assert config.values["rounding"] == {"KR": {"commission": {"mode": "down", "unit": 1}}}
    assert config.values["fx"]["series"] == {"USDKRW": "c@x"}
    assert "[live] max_price_jump = <rules pack>" in str(config)  # printing; a pack default


def test_done_means(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#53's Done-means line, its four cases, through `nx.config()`."""
    for markets in ({"KR": "KRW", "US": "USD"}, {"US": "USD", "KR": "KRW"}):
        snapshot(tmp_path, monkeypatch, markets)
        printed = str(write(tmp_path, "") and nx.config())
        assert "[defaults] clock = 'KR_close'" in printed
        assert "[defaults] base_ccy = 'KRW'" in printed
        assert "[data] pins = 'index+root'" in printed
    cases = [
        ("[sleeves]\nweights = {JP = 1}", "unknown market JP; snapshot markets: KR, US"),
        ('[broker]\napi_key = "x"', "secrets do not belong in nexusbt.toml"),
        ("[shorting]\nmax_net = [0.2, 0.8]", "[shorting] max_net"),
    ]
    for text, message in cases:
        write(tmp_path, text)
        with pytest.raises(ConfigError, match=re.escape(message)):
            nx.config()


def test_markets_from_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = snapshot(tmp_path, monkeypatch, {"US": "USD", "KR": "KRW"})
    write(tmp_path, "")
    assert nx.config().markets == ("KR", "US")  # UTF-8 byte order, not the object's
    monkeypatch.delenv("NEXUSBT_DATA_ROOT")
    write(tmp_path, f"[data]\npath = '{folder}'\n")  # a package folder directly
    assert nx.config().resolved["base_ccy"] == "KRW"
    write(tmp_path, "")
    assert nx.config().markets == ()  # no data location: nothing to resolve against
    with pytest.raises(ConfigError, match="base_ccy"):  # a market without a currency code
        load_config(markets={"KR": "None"})
    assert importlib.import_module("nexusbt.config").load_config is load_config  # 2.4 module
    write(tmp_path, f"[data]\npath = '{folder.parent}'\n[defaults]\nclock = 'US_close'\n")
    assert nx.config().resolved["clock"] == "US_close"  # `path`: a parent with LATEST (4.2)
    write(tmp_path, f"[data]\nroot = '{folder.parent}'\nsnapshot = '{folder.name}'\n")
    assert nx.config().markets == ("KR", "US")  # `root` + a snapshot id
    (folder / "tds.json").write_text("{not json", encoding="utf-8")  # a broken file: E14
    with pytest.raises(SnapshotError, match=r"tds\.json"):
        nx.config()
    (folder / "tds.json").unlink()  # no file
    with pytest.raises(SnapshotError, match=r"tds\.json"):
        nx.config()


def test_market_object_reordering_preserves_resolved_defaults(tmp_path: Path) -> None:
    path = write(tmp_path, "")
    for markets in ({"KR": "KRW", "US": "USD"}, {"US": "USD", "KR": "KRW"}):
        config = load_config(path, markets=markets)
        sleeves = {"KR": 0.5, "US": 0.5}
        assert config.resolved == {"clock": "KR_close", "base_ccy": "KRW", "sleeves": sleeves}
        assert config.values["shorting"]["borrow_bps"] == {"KR": 0, "US": 0}  # "in every market"
        assert config.values["taxes"]["currency"] == "KRW"  # "the base currency"
        assert config.values["project"]["name"] == tmp_path.name  # "the folder name"


def test_sleeve_weights_must_sum_to_one(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="sum") as e:
        load_config(write(tmp_path, "[sleeves]\nweights = {KR = 0.5, US = 0.6}\n"), markets=KR_US)
    assert e.value.layer == "config — nexusbt.toml [sleeves] weights = {'KR': 0.5, 'US': 0.6}"
    text = '[defaults]\nuniverse = "US"\n[sleeves]\nweights = {KR = 0.3, US = 0.7}\n'
    assert load_config(write(tmp_path, text), markets=KR_US).resolved["sleeves"] == {"US": 1.0}
    with pytest.raises(ConfigError, match="unknown market JP"):
        load_config(write(tmp_path, '[defaults]\nuniverse = "KR+JP"\n'), markets=KR_US)


def test_segments_must_not_overlap(tmp_path: Path) -> None:
    for segments in (
        '{a = ["2020-01-01", "2021-12-31"], b = ["2021-06-01", "latest"]}',  # overlap
        '{a = ["2022-01-01", "latest"], b = ["start", "2021-12-31"]}',  # out of order
        '{a = ["2022-01-01", "2021-01-01"]}',  # ends before it starts
    ):
        with pytest.raises(ConfigError, match="segments") as e:
            load_config(write(tmp_path, f"[split]\nsegments = {segments}\n"))
        assert e.value.layer.startswith("config — nexusbt.toml [split] segments = {'a': [")
    text = '[split]\nsegments = {train = ["start", "2019-12-31"], b = ["2020-01-01", "latest"]}\n'
    assert list(load_config(write(tmp_path, text)).values["split"]["segments"]) == ["train", "b"]
    load_config(overrides={"defaults": {"start": "2023-01-01"}})  # "start": from the beginning


def test_preset_zipline_forbidden_in_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="zipline") as e:
        load_config(write(tmp_path, '[defaults]\npreset = "zipline"\n'))
    assert e.value.layer == "config — nexusbt.toml [defaults] preset = 'zipline'"
    config = load_config(overrides={"defaults": {"preset": "zipline"}})  # code may set it
    assert config.values["defaults"]["preset"] == "zipline"
    with pytest.raises(ConfigError, match=r"\[defaults\]"):  # not a table: E16, not a crash
        load_config(write(tmp_path, "defaults = 1\n"))


def test_data_root_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = snapshot(tmp_path, monkeypatch, KR_US)
    assert load_config(write(tmp_path, "")).values["data"]["root"] == str(tmp_path / "data")
    monkeypatch.setenv("NEXUSBT_DATA_ROOT", str(tmp_path / "missing"))
    load_config(overrides={"data": {"path": str(folder)}})  # `path` comes before `root`
    with pytest.raises(ConfigError, match="root") as e:
        load_config(write(tmp_path, ""))
    assert e.value.layer == f"config — nexusbt.toml [data] root = {str(tmp_path / 'missing')!r}"


def test_shorting_disabled_by_default(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "")).values["shorting"]["enabled"] is False
    with pytest.raises(ConfigError, match=re.escape("[shorting] enabled = true")) as e:
        check_long_short(load_config(markets=KR_US), "KR", 0.5, 0.5)
    assert e.value.layer == "config — nexusbt.toml [shorting] enabled = False"


def test_pins_default_index_root(tmp_path: Path) -> None:
    assert load_config(write(tmp_path, "")).values["data"]["pins"] == "index+root"
    with pytest.raises(ConfigError, match="pins"):
        load_config(write(tmp_path, "[data]\npins = 'root'\n"))


def test_net_interval_must_contain_zero(tmp_path: Path) -> None:
    for bad in ("[0.2, 0.8]", "[-0.8, -0.2]", "[0.5, -0.5]", "[0.0]"):
        with pytest.raises(ConfigError, match="max_net"):
            load_config(write(tmp_path, f"[shorting]\nmax_net = {bad}\n"))
    config = load_config(write(tmp_path, "[shorting]\nmax_net = [0.0, 0.5]\n"))
    assert config.values["shorting"]["max_net"] == [0.0, 0.5]


def test_margin_keys_need_margin_account(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=re.escape('need [account] type = "margin"')) as e:
        load_config(write(tmp_path, "[account]\ninitial_margin = {US = 0.5}\n"), markets=KR_US)
    assert e.value.layer == "config — nexusbt.toml [account] type = 'cash'"
    assert load_config(write(tmp_path, MARGIN), markets=KR_US).values["account"]["type"] == "margin"


def test_long_short_feasible_region(tmp_path: Path) -> None:
    """3.7: cash book `L + c·S ≤ 1`; 5.6.7a: margin book `L + S ≤ min(max_gross, 1/IM)`."""
    on = "[shorting]\nenabled = true\nmax_gross = 2.0\n"
    cash = load_config(write(tmp_path, on), markets=KR_US)
    check_long_short(cash, "KR", 0.5, 0.5)  # 0.5 + 0.5 * 0.5 = 0.75
    partial = {"shorting": {"enabled": True, "collateral_ratio": {"KR": 1.0}}}  # US: the 0.5
    check_long_short(load_config(overrides=partial, markets=KR_US), "US", 0.5, 1.0)
    sentence = f"collateral_ratio {chr(0xD7)} short_weight = 1.45 > 1"  # 3.7's E16 sentence
    with pytest.raises(ConfigError, match=re.escape(sentence)) as e:
        check_long_short(cash, "KR", 1.3, 0.3)  # 130/30 in a cash account
    assert e.value.layer == "config — nexusbt.toml [account] type = 'cash'"
    margin = on + MARGIN
    check_long_short(load_config(write(tmp_path, margin), markets=KR_US), "US", 1.3, 0.3)
    tight = load_config(write(tmp_path, margin.replace("2.0", "1.5")), markets=KR_US)
    with pytest.raises(ConfigError, match=re.escape("L + S = 1.6 > 1.5")) as e:
        check_long_short(tight, "US", 1.3, 0.3)
    assert e.value.layer == "config — nexusbt.toml [account] type = 'margin'"
    assert e.value.parts["where"] == "nexusbt.toml [account] type, sleeve US"  # `where` as before
    with pytest.raises(ConfigError, match="initial_margin") as e:  # no value for KR: E16
        check_long_short(tight, "KR", 0.5, 0.1)
    assert e.value.layer == "config — nexusbt.toml [account] initial_margin = {'US': 0.5}"
    unset = load_config(overrides={"account": {"type": "margin"}}, markets=KR_US)
    with pytest.raises(ConfigError, match="initial_margin") as e:  # the pack's default, unset
        check_long_short(unset, "KR", 0.5, 0.0)
    assert e.value.layer == "config — nexusbt.toml [account] initial_margin = <rules pack>"
    with pytest.raises(ConfigError) as e:  # an unknown table: no value to show
        load_config(overrides={"foo": {"x": 1}})
    assert " = " not in e.value.layer
    assert e.value.parts["where"] == "overrides [foo]"  # the bracket closed (#87 left `[foo`)


def test_file_path_and_toml_dates(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):  # a misspelt path is not read as an empty file
        load_config(tmp_path / "nexsubt.toml")
    text = "[split]\nsegments = {train = [1995-01-01, 2021-12-31]}\n"  # native TOML dates
    segments = load_config(write(tmp_path, text)).values["split"]["segments"]
    assert segments == {"train": ["1995-01-01", "2021-12-31"]}
