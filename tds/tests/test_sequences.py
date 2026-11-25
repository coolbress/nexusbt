"""TDS 5.6~5.8: the `params.sequence_consecutive_within` declaration (#348's `## Decision`).

V032, which judged the declared groups, is retired (#752); the declaration's shape and its
TDS-S001 leave with `trades`, `quotes` and `book_deltas` (#725 Decision 252)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from nexusbt_tds import check

from .conformance_build import build

DAY = "2024-01-02"


def write(root: Path, change: Any) -> Path:
    manifest, files = build.base()
    change(manifest, files)
    return Path(build.write(root, manifest, files))


def _declared(within: object, **params: object) -> Any:
    """A `trades` dataset (`venue=XNYS`, one row) declaring `within`, plus `params`."""
    row = {"instrument_id": ["US:AAA"], "sequence": pa.array([1], pa.int64())}
    return build._both(build._add("trades", row, f"trades/venue=XNYS/date={DAY}/p.parquet"),
                       lambda m, f: m["datasets"][-1].update(
                           params={"sequence_consecutive_within": within, **params}))  # fmt: skip


@pytest.mark.parametrize(
    ("within", "said"),
    [  # When the list holds `sequence` or a name twice, then TDS-M001.
        (["sequence"], '"sequence" does not match'),
        (["x_dbn_channel_id", "x_dbn_channel_id"], "'x_dbn_channel_id' is listed twice"),
        ("instrument_id", "is not a JSON array"),
        ([1], "1 is not a JSON string"),
    ],
)
def test_the_manifest_schema_gives_the_key_its_shape(
    within: object, said: str, tmp_path: Path
) -> None:
    errors = check(write(tmp_path, _declared(within)), level="manifest").errors
    assert [(e.code, said in e.message) for e in errors] == [("TDS-M001", True)]
    # `trades` after the base's three datasets, its calendar the third since #705
    assert errors[0].message.startswith("$.datasets[3].params.sequence_consecutive_within")


def test_the_other_params_keys_stay_open(tmp_path: Path) -> None:
    pkg = write(tmp_path, _declared([], depth=5, continuity=["any"]))
    assert check(pkg, level="manifest").errors == ()


def test_a_listed_column_missing_from_a_footer_is_S001(tmp_path: Path) -> None:
    # When the list names a column no file has, then TDS-S001 at the `schema` level; a listed
    # partition column is not an error.
    errors = check(write(tmp_path, _declared(["x_dbn_channel_id", "venue"])), level="schema")
    listed = [e for e in errors.errors if "x_dbn_channel_id" in e.message or "venue" in e.message]
    assert [(e.code, e.message, e.file) for e in listed] == [
        ("TDS-S001", "column x_dbn_channel_id in params.sequence_consecutive_within is missing",
         f"trades/venue=XNYS/date={DAY}/p.parquet")
    ]  # fmt: skip

    # on a kind V032 did not read, the key is ignored
    def bars(m: dict[str, Any], f: Any) -> None:
        m["datasets"][1]["params"]["sequence_consecutive_within"] = ["x_y"]

    assert check(write(tmp_path / "bars", bars), level="schema").errors == ()
