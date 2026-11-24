"""`make_snapshot(price_decimals=)`, spec 4.8 (5a): 8.1's CI fixture, US and ZZ prices to 10^-n.

Without it the output is unchanged: `test_synth.py::test_small_hashes_match_on_macos_and_linux`
pins `small`'s hashes with the default arguments.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pytest
from _applied import applied, resolved

from nexusbt.testing import _synth_package as pkg
from nexusbt.testing import synth
from nexusbt.testing.synth import main, make_snapshot, read

OHLC = ("open", "high", "low", "close")
SHORT: dict[str, Any] = {"markets": ("KR", "US", "ZZ"), "end": dt.date(2015, 12, 31),
                         "n_kr": 8, "n_us": 8}  # fmt: skip


def bars_of(package: Path, market: str) -> pa.Table:
    bars = read(package, "bars_1d")
    return bars.filter(pc.starts_with(bars["instrument_id"], f"{market}:"))


@pytest.fixture(scope="module")
def rounded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    # a split and a dividend on a US instrument, so events move rounded bars (4.8 (5a))
    plain = make_snapshot(tmp_path_factory.mktemp("plain") / "p", **SHORT)
    us = bars_of(plain, "US").filter(pc.equal(bars_of(plain, "US")["obs_status"], "traded"))
    iid = us["instrument_id"][0].as_py()
    days = [d for i, d in zip(us["instrument_id"].to_pylist(), us["session_date"].to_pylist(),
                              strict=True) if i == iid]  # fmt: skip
    events = [
        {"dataset": "corporate_actions", "kind": "split", "instrument_id": iid,
         "ex_date": days[40].isoformat(), "ratio_new_per_old": 3.0},
        {"dataset": "corporate_actions", "kind": "cash_dividend", "instrument_id": iid,
         "ex_date": days[80].isoformat(), "cash_per_share": 0.37},
    ]  # fmt: skip
    return make_snapshot(tmp_path_factory.mktemp("rounded") / "r", **SHORT, events=events,
                         price_decimals=3)  # fmt: skip


def test_us_and_zz_prices_are_on_the_grid_and_pass_the_full_check(rounded: Path) -> None:
    for market in ("US", "ZZ"):
        bars = bars_of(rounded, market)
        for name in OHLC:
            values = bars[name].drop_null().to_numpy()
            assert values.size, (market, name)
            np.testing.assert_array_equal(np.round(values, 3), values, err_msg=f"{market} {name}")
    done = pkg._tds("check", str(rounded), "--level", "full")
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.search(r"\b0 errors\b", done.stdout), done.stdout
    assert applied(rounded) == resolved(rounded)  # rounding moved no factor (#608, #705)


def test_rounded_bars_still_enclose_open_and_close(rounded: Path) -> None:
    bars = read(rounded, "bars_1d").drop_null()  # a halted bar has no prices
    high, low = bars["high"].to_numpy(), bars["low"].to_numpy()
    for name in ("open", "close"):
        assert (high >= bars[name].to_numpy()).all(), name
        assert (bars[name].to_numpy() >= low).all(), name


def test_kr_bars_are_as_without_it(rounded: Path, tmp_path: Path) -> None:
    # KR prices are on their tick grid already (4.8 (5)); the KR draws do not see the option
    plain = make_snapshot(tmp_path / "p", **SHORT)
    assert bars_of(rounded, "KR").equals(bars_of(plain, "KR"))
    assert not bars_of(rounded, "US").equals(bars_of(plain, "US"))


@pytest.mark.parametrize("value", [-1, 10, 400, 1.5, True, "3"])  # 400 overflowed 10^n to NaN
def test_price_decimals_takes_an_integer_from_zero_to_nine(value: object, tmp_path: Path) -> None:
    given: dict[str, Any] = SHORT | {"price_decimals": value}  # past the type, as a caller may
    with pytest.raises(ValueError, match="price_decimals"):
        make_snapshot(tmp_path / "p", **given)


def test_tiny_takes_no_price_decimals(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="price_decimals"):
        make_snapshot(tmp_path / "p", preset="tiny", price_decimals=3)


def test_command_passes_price_decimals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    given: dict[str, Any] = {}

    def record(root: Path, **kwargs: Any) -> Path:
        given.update(kwargs)
        raise SystemExit(9)

    monkeypatch.setattr(synth, "make_snapshot", record)
    for argv, want in ((["--price-decimals", "3"], 3), ([], None)):
        with pytest.raises(SystemExit):
            main(["--preset", "small", "--out", str(tmp_path / "c"), *argv])
        assert given["price_decimals"] == want
