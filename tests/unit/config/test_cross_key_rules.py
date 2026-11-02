"""#94: the 3.11 Validation rules that tie a key to another key or to a form."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nexusbt.config import load_config
from nexusbt.contracts import ConfigError, TaxesBasisPolicy

KR_US = {"KR": "KRW", "US": "USD"}
MARGIN = '[account]\ntype = "margin"\n'


@pytest.fixture(autouse=True)
def _no_data_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)


def write(tmp_path: Path, text: str) -> Path:
    (path := tmp_path / "nexusbt.toml").write_text(text, encoding="utf-8")
    return path


def refused(tmp_path: Path, text: str, key: str) -> ConfigError:
    """The E16 the file `text` raises; its `where` names `key`."""
    with pytest.raises(ConfigError) as caught:
        load_config(write(tmp_path, text), markets=KR_US)
    assert caught.value.code == "E16"
    assert caught.value.parts["where"].startswith(f"nexusbt.toml {key}"), caught.value.parts
    return caught.value


@pytest.mark.parametrize(
    ("text", "key", "accepted"),
    [
        (  # 3.11 `[defaults] end`: "≥ start"
            '[defaults]\nstart = "2020-01-01"\nend = "2019-12-31"\n',
            "[defaults] end",
            '[defaults]\nstart = "2020-01-01"\nend = "2020-01-01"\n',
        ),
        (  # `[split] default_segment`: "a name of segments, or "all""
            '[split]\ndefault_segment = "test"\n',
            "[split] default_segment",
            '[split]\ndefault_segment = "all"\n',
        ),
        (  # `[costs] sensitivity`: "contains 1"
            "[costs]\nsensitivity = [0, 2]\n",
            "[costs] sensitivity",
            "[costs]\nsensitivity = [1.0]\n",
        ),
        (  # `[execution] adv_min_obs`: "1..adv_window"
            "[execution]\nadv_window = 5\nadv_min_obs = 6\n",
            "[execution] adv_min_obs",
            "[execution]\nadv_window = 5\nadv_min_obs = 5\n",
        ),
        (  # `[account] maintenance_margin`: "(0, initial_margin]"
            MARGIN + "initial_margin = {US = 0.5}\nmaintenance_margin = {US = 0.6}\n",
            "[account] maintenance_margin",
            MARGIN + "initial_margin = {US = 0.5}\nmaintenance_margin = {US = 0.5, KR = 0.3}\n",
        ),
        (  # `[costs] max_half_spread_bps`: "≥ min"
            "[costs]\nmin_half_spread_bps = {KR = 5, US = 30}\nmax_half_spread_bps = 20\n",
            "[costs] max_half_spread_bps",
            "[costs]\nmin_half_spread_bps = {KR = 5, US = 20}\nmax_half_spread_bps = 20\n",
        ),
    ],
)
def test_a_key_tied_to_another_key(tmp_path: Path, text: str, key: str, accepted: str) -> None:
    refused(tmp_path, text, key)
    load_config(write(tmp_path, accepted), markets=KR_US)  # the boundary itself is allowed


def test_a_market_in_one_tax_group_and_group_defaults(tmp_path: Path) -> None:
    two = '[taxes.groups.a]\nmarkets = ["US"]\n[taxes.groups.b]\nmarkets = ["KR", "US"]\n'
    assert "US" in refused(tmp_path, two, "[taxes] groups").parts["what"]
    once = '[taxes.groups.a]\nmarkets = ["US", "US"]\n'  # one group, written twice: not two
    load_config(write(tmp_path, once), markets=KR_US)
    groups = load_config(write(tmp_path, '[taxes.groups.a]\nmarkets = ["US"]\n'), markets=KR_US)
    group = groups.values["taxes"]["groups"]["a"]
    assert group == {
        "markets": ["US"],
        "gains_rate": 0.0,
        "annual_exemption": 0,
        "basis": "average",
    }
    assert group["basis"] is TaxesBasisPolicy.AVERAGE


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("[costs.provisional_bps]\nKR = {buy = 5}\n", "[costs] provisional_bps"),  # {buy, sell}
        ('[meta]\nsector = "gics@x"\n', "[meta] sector"),  # <level>: digits (chosen rule)
        ('[meta]\nindustry = {KR = "a b"}\n', "[meta] industry"),
        ('[meta]\nsector = "gics@"\n', "[meta] sector"),
        ('[fx]\nseries = {usdkrw = "c@x"}\n', "[fx] series"),  # "<BASE><QUOTE>"
        ('[fx]\nseries = {USDKRWX = "c@x"}\n', "[fx] series"),
        ('[defaults]\nstart = "2021-13-45"\n', "[defaults] start"),  # not a calendar date
        ('[split]\nsegments = {train = ["start", "2021-02-30"]}\n', "[split] segments"),
    ],
)
def test_a_value_outside_its_form(tmp_path: Path, text: str, key: str) -> None:
    error = refused(tmp_path, text, key)
    if key.startswith("[meta]"):
        assert "<scheme> or <scheme>@<level>" in error.parts["fix"]


def test_values_in_their_form(tmp_path: Path) -> None:
    text = (
        "[costs.provisional_bps]\nKR = {buy = 5, sell = 25}\n"
        '[meta]\nsector = "gics@2"\nindustry = {KR = "krx", US = "auto"}\n'
        '[fx]\nseries = {USDKRW = "close@x"}\n[defaults]\nstart = "2020-02-29"\n'
    )
    config = load_config(write(tmp_path, text), markets=KR_US)
    assert config.values["meta"]["sector"] == "gics@2"


def test_default_project_name_is_checked(tmp_path: Path) -> None:
    (folder := tmp_path / "my project").mkdir()
    with pytest.raises(ConfigError, match=re.escape("[project] name")) as caught:
        load_config(write(folder, ""))
    assert caught.value.parts["fix"].startswith("set [project] name")
    assert load_config(write(tmp_path, "")).values["project"]["name"] == tmp_path.name
