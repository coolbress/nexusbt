"""The helper behind P-FUT's earlier snapshot (`_future.cut_after`, #254 ③a): what it cuts,
and that what it keeps is the original."""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from nexusbt.testing.synth import make_snapshot
from nexusbt_tds import check
from property._future import TIMELESS, cut_after

pytestmark = pytest.mark.unit

#: Mid-session in KR (open 00:00, close 06:30 UTC) and before the US open: a KR session whose
#: open is known and whose close is not.
TAU = dt.datetime(2017, 6, 15, 3, 0, tzinfo=dt.UTC)
#: The first-known column of each dataset, as `_future` reads TDS 6.2 (an independent spelling
#: of the cut rule for this package, whose columns have no nulls there).
KNOWN = {"bars_1d": "ts_end", "share_counts": "ts_available", "delistings": "ts_exit_known",
         "instrument_symbols": "ts_known_from"}  # fmt: skip


@pytest.fixture(scope="module", params=[(), ("late_bars",)], ids=["small", "late_bars"])
def original(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synth") / "pkg"
    return make_snapshot(root, preset="small", markets=("KR", "US"), n_kr=8, n_us=8,
                         degrade=request.param)  # fmt: skip


@pytest.fixture(scope="module")
def cut(original: Path) -> Path:
    at = shutil.copytree(original, original.parent / "cut")
    cut_after(at, TAU)
    return at


def rows(root: Path, name: str) -> list[dict[str, Any]]:
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == name)
    return [r for f in entry["files"] for r in pq.read_table(root / f["path"]).to_pylist()]


def names(root: Path) -> list[str]:
    manifest = json.loads((root / "tds.json").read_text(encoding="utf-8"))
    return [d["name"] for d in manifest["datasets"]]


def known(root: Path) -> dict[str, str]:
    """`KNOWN`, with the bars' column where the package writes one (`late_bars`, 4.8 rule 3a)."""
    late = any("ts_available" in r for r in rows(root, "bars_1d")[:1])
    return KNOWN | ({"bars_1d": "ts_available"} if late else {})


def after(value: Any) -> bool:
    return value is not None and value > TAU


def test_no_row_first_known_after_tau(original: Path, cut: Path) -> None:
    for name, column in known(original).items():
        assert not any(after(r[column]) for r in rows(cut, name)), name
        assert any(after(r[column]) for r in rows(original, name)), name  # it had some to cut
    for name in ("eligibility_daily", "tradability_daily"):  # by their session's close
        for market in ("KR:", "US:"):  # both close on 2017-06-14 before τ, KR's 06-15 after
            days = {r["session_date"] for r in rows(cut, name) if r["instrument_id"][:3] == market}
            assert max(days) == dt.date(2017, 6, 14), (name, market)


def existence(r: dict[str, Any]) -> Any:
    """A corporate action's existence instant (TDS 6.2): the earlier of its announcement and
    its terms, else its effect."""
    told = [t for t in (r["ts_announced"], r["ts_terms_available"]) if t is not None]
    return min(told, default=r["ts_effective"])


def test_kept_rows_are_the_original_rows(original: Path, cut: Path) -> None:
    """Every row the cut keeps is an original row, byte for byte (`repr` tells -0.0 from 0.0),
    and every original row known by τ is kept: a dataset with an instant loses only rows after
    τ, the timeless ones nothing, `instruments` aside (its own test below)."""
    for name in names(original):
        if name == "instruments":
            continue
        was, now = (
            [repr(sorted(r.items())) for r in rows(original, name)],
            [repr(sorted(r.items())) for r in rows(cut, name)],
        )
        assert set(now) <= set(was), name
        if name in TIMELESS:
            assert sorted(now) == sorted(was), name
    for name, column in known(original).items():
        kept = [r for r in rows(original, name) if not after(r[column])]
        assert sorted(map(repr, kept)) == sorted(map(repr, rows(cut, name))), name
    kept = [r for r in rows(original, "corporate_actions") if not after(existence(r))]
    assert sorted(map(repr, kept)) == sorted(map(repr, rows(cut, "corporate_actions")))
    for name in ("eligibility_daily", "tradability_daily"):  # every session closed by τ, kept
        kept = [r for r in rows(original, name) if r["session_date"] <= dt.date(2017, 6, 14)]
        assert sorted(map(repr, kept)) == sorted(map(repr, rows(cut, name))), name


def test_a_dataset_left_without_rows_keeps_one_empty_file(original: Path) -> None:
    """τ before the first exit is known: `delistings` loses every row and keeps an empty file
    of its schema, so the package still hashes (TDS 4.5)."""
    at = shutil.copytree(original, original.parent / "early")
    first_close = dt.datetime(2015, 6, 1, 21, 0, tzinfo=dt.UTC)  # after KR's and US's closes
    exits = [r["ts_exit_known"] for r in rows(original, "delistings")]
    assert exits
    assert all(t is not None and t > first_close for t in exits)  # none known yet
    cut_after(at, first_close)
    assert rows(at, "delistings") == []
    manifest = json.loads((at / "tds.json").read_text(encoding="utf-8"))
    (entry,) = (d for d in manifest["datasets"] if d["name"] == "delistings")
    assert [f["rows"] for f in entry["files"]] == [0]
    assert check(at, level="schema").error_count == 0


def test_tau_before_the_first_close_is_refused(original: Path) -> None:
    at = shutil.copytree(original, original.parent / "before")
    with pytest.raises(ValueError, match="before KR's first close"):
        cut_after(at, dt.datetime(2015, 1, 2, 3, 0, tzinfo=dt.UTC))


def test_instruments_change_only_in_their_two_exceptions(original: Path, cut: Path) -> None:
    """`delisted_on` empties only for an exit known after τ, `last_session` only where it is
    after τ's last closed session (both markets' is 2017-06-14 here); every other value stays."""
    later = {r["instrument_id"] for r in rows(original, "delistings") if after(r["ts_exit_known"])}
    assert later  # the package has some
    before = {r["instrument_id"]: r for r in rows(original, "instruments")}
    assert sorted(before) == sorted(r["instrument_id"] for r in rows(cut, "instruments"))
    watermark = dt.date(2017, 6, 14)
    for r in rows(cut, "instruments"):
        was = before[r["instrument_id"]]
        expected = was | ({"delisted_on": None} if r["instrument_id"] in later else {})
        if was["last_session"] is not None and was["last_session"] > watermark:
            expected |= {"last_session": None}
        assert repr(sorted(r.items())) == repr(sorted(expected.items())), r["instrument_id"]


def test_cut_package_passes_full_check(cut: Path) -> None:
    found = check(cut, level="full")
    assert found.error_count == 0, [str(e)[:200] for e in found.errors[:5]]


def test_tau_after_the_end_gives_the_original(original: Path) -> None:
    at = shutil.copytree(original, original.parent / "late")
    assert not any(cut_after(at, dt.datetime(2030, 1, 1, tzinfo=dt.UTC)).values())
    files = sorted(p.relative_to(original) for p in original.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(at) for p in at.rglob("*") if p.is_file())
    assert all((original / f).read_bytes() == (at / f).read_bytes() for f in files)
