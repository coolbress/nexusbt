"""`nx.screen(factor, top=n)` (spec 3.8, 3.9 Screen; T1.13, #249): the top n of one factor per
market on each market's last snapshot session, among the listed instruments until T2.4's
investable universe (#249 Decisions, 2026-11-19), sealed as a `kind="screen"` run.

`tiny`'s instrument n has base close 10000·n in KR and 10·n in US, times (1.00, 1.01, 1.02,
1.01)[k % 4] on its k-th listed session; `T00006` lists on 2020-02-18 at base 60000 (KR) and
60 (US), so on the last session, 2020-03-31, the two highest closes are T00006's and T00005's.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt.testing.synth import make_snapshot

pytestmark = pytest.mark.unit

LAST = dt.date(2020, 3, 31)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_snapshot(tmp_path_factory.mktemp("tiny") / "pkg", preset="tiny")


@pytest.fixture(autouse=True)
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project whose `m.py` is the entry file, pinning in the index only (`tiny` has no
    data root)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    (tmp_path / "m.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys.modules["__main__"], "__file__", str(tmp_path / "m.py"), raising=False)
    return tmp_path


def test_top_per_market(tiny: Path, project: Path) -> None:
    """3.8: the top 2 closes per market on each market's last session, ranked 1 and 2; the run
    is sealed as `kind="screen"` and its id is on the result and in its last line."""
    found = nx.screen(nx.Price.close.latest, top=2, snapshot=str(tiny))
    assert found.asof == {"KR": LAST, "US": LAST}
    rows = [(r["market"], r["rank"], r["instrument_id"]) for r in found.table.to_pylist()]
    assert rows == [("KR", 1, "KR:T00006"), ("KR", 2, "KR:T00005"),
                    ("US", 1, "US:T00006"), ("US", 2, "US:T00005")]  # fmt: skip
    assert all(r["session_date"] == LAST for r in found.table.to_pylist())
    assert found.run_id is not None
    manifest = json.loads((project / "runs" / found.run_id / "manifest.json").read_text())
    assert manifest["kind"] == "screen"
    shown = str(found)
    assert f"run {found.run_id}" in shown.splitlines()[-1]
    assert "selected 2/6 KR, 2/6 US" in shown


def test_universe_is_the_listed_instruments_until_t24(tiny: Path) -> None:
    """#249 Decisions, #43's notes: the universe is 3.3's default domain, said on the result;
    T2.4's investable universe changes this line and this test."""
    found = nx.screen(nx.Price.close.latest, top=1, snapshot=str(tiny))
    assert "universe: listed (investable comes with T2.4)" in str(found)
    on_jan = nx.screen(nx.Price.close.latest, top=1, asof="2020-01-31", snapshot=str(tiny))
    assert "universe 5 KR / 5 US" in str(on_jan)  # T00006 lists on 2020-02-18


def test_asof_on_a_holiday_takes_the_session_before(tiny: Path) -> None:
    """`asof` that is no session of a market takes that market's last session before it, with
    an E9 notice (5.1.6): 2020-01-20 is a KR session and a US holiday."""
    with pytest.warns(UserWarning, match=r"SessionNotice \[E9\][\s\S]*2020-01-17"):
        found = nx.screen(nx.Price.close.latest, top=1, asof="2020-01-20", snapshot=str(tiny))
    assert found.asof == {"KR": dt.date(2020, 1, 20), "US": dt.date(2020, 1, 17)}


def test_what_screen_does_not_take_yet(tiny: Path) -> None:
    """A Strategy or Pipeline screen and the keywords of a strategy screen are later tickets':
    each is refused with its name, not ignored."""
    with pytest.raises(NotImplementedError, match="Pipeline"):
        nx.screen(nx.Pipeline({"c": nx.Price.close.latest}), snapshot=str(tiny))
    with pytest.raises(NotImplementedError, match="book"):
        nx.screen(nx.Price.close.latest, book="b", snapshot=str(tiny))
