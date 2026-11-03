"""TDS 5, 10.3: the schema files `tds/schemas/<kind>/1.0.json` and `nexusbt_tds.schemas.verify`.

The package's `nexusbt_tds/schemas/data` links to `tds/schemas`, where the files are (#145).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from nexusbt_tds.schemas.verify import (
    CHAPTER_5,
    SCHEMA_DIR,
    Column,
    Schema,
    compare,
    doc_tables,
    file_problems,
    load_schemas,
    main,
    section_status,
)
from nexusbt_tds.schemas.verify import DOC as TDS_DOC

SAMPLE_DOC = """\
## 5. Dataset kinds

### 5.1 `things` (a test table)

| Column | Type | Null | Meaning |
|---|---|---|---|
| thing_id | id | no | K1 |
| kind | code (closed) | no | `a` (first), `b`, `v:<name>` (e.g. `v:x`) — not `c` |
| open, close | f64 | yes | prices |
| ts_event, ts_recv | ts_ns | no / yes | |
| ts_start | ts_us/ns | daily yes / intraday no | |
| unit | | | 5.17 |
| plain | | no | |

### 5.17 `facts`

| Column | Type | Null | Meaning |
|---|---|---|---|
| unit | code | no | |

## 6. Next chapter
"""


def _things(**changes: Column) -> Schema:
    columns = {
        "thing_id": Column("thing_id", "id", False),
        "kind": Column("kind", "code", False, enum="closed", values=("a", "b", "v:<name>")),
        "open": Column("open", "f64", True),
        "close": Column("close", "f64", True),
        "ts_event": Column("ts_event", "ts_ns", False),
        "ts_recv": Column("ts_recv", "ts_ns", True),
        "ts_start": Column("ts_start", "ts_us/ns", "daily yes / intraday no"),
        "unit": Column("unit", "code", False),
        "plain": Column("plain", None, False),
    }
    columns.update(changes)
    return Schema("things", "stable", tuple(columns.values()))


def test_a_doc_table_written_from_the_schema_matches() -> None:
    assert compare(SAMPLE_DOC, {"things": _things()}) == []


def test_a_hand_edited_type_or_null_is_a_mismatch() -> None:
    edited = _things(open=Column("open", "f32", True), ts_recv=Column("ts_recv", "ts_ns", False))
    assert compare(SAMPLE_DOC, {"things": edited}) == [
        "things: column open: doc type `f64`, schema `f32`",
        "things: column ts_recv: doc null `yes`, schema `no`",
    ]


def test_an_enum_value_list_unlike_the_meaning_cell_is_a_mismatch() -> None:
    # The list is the cell's backticked values outside parentheses and before ` — `.
    edited = _things(kind=Column("kind", "code", False, enum="closed", values=("a", "c")))
    unlisted = _things(kind=Column("kind", "code", False, enum="closed"))
    assert compare(SAMPLE_DOC, {"things": edited}) == [
        "things: column kind: doc values `a, b, v:<name>`, schema `a, c`"
    ]
    assert compare(SAMPLE_DOC, {"things": unlisted}) == [
        "things: column kind: doc values `a, b, v:<name>`, schema ``"
    ]


def test_a_column_missing_or_out_of_order_is_a_mismatch() -> None:
    first, second, _open, *rest = _things().columns
    reordered = Schema("things", "stable", (second, first, *rest))
    assert compare(SAMPLE_DOC, {"things": reordered}) == [
        "things: doc columns thing_id, kind, open, close, ts_event, ts_recv, ts_start, unit, plain;"
        " schema kind, thing_id, close, ts_event, ts_recv, ts_start, unit, plain",
    ]


def test_a_blank_cell_takes_the_section_it_points_to_or_stays_blank() -> None:
    edited = _things(unit=Column("unit", "f64", False), plain=Column("plain", "id", False))
    assert compare(SAMPLE_DOC, {"things": edited}) == [
        "things: column unit: doc type `code` (5.17), schema `f64`",
        "things: column plain: doc type ``, schema `id`",
    ]


def test_a_short_row_reads_and_a_pointer_to_nothing_is_named() -> None:
    doc = "## 5. Kinds\n### 5.1 `x`\n| Column | Type | Null | Meaning |\n|---|\n| a | id | no |\n"
    doc += "| u | | | 5.99 |\n## 6. Next\n"
    a, u = Column("a", "id", False), Column("u", "code", False)
    assert compare(doc, {"x": Schema("x", "stable", (a, u))}) == [
        "x: column u: doc type `` (5.99, not found), schema `code`",
        "x: column u: doc null `` (5.99, not found), schema `no`",
    ]


def test_a_table_the_parser_cannot_place_is_a_mismatch() -> None:
    header = "| Column | Type | Null | Meaning |"
    doc = SAMPLE_DOC.replace(header, f"{header} Checks |", 1)
    assert compare(doc, {"things": _things()}) == ["chapter 5 has 2 column tables, 1 read"]


def test_doc_tables_match_schema_files() -> None:
    doc = TDS_DOC.read_text(encoding="utf-8")
    schemas = load_schemas()
    assert compare(doc, schemas) == []
    # Tables were compared, not skipped: every chapter 5 table has its file.
    assert doc_tables(doc).keys() - schemas.keys() == set()


def test_experimental_schemas_flagged() -> None:
    status = section_status(TDS_DOC.read_text(encoding="utf-8"))
    experimental = sorted(kind for kind, n in CHAPTER_5.items() if status[n] == "experimental")
    assert experimental == [  # 5.6-5.9 and 5.22-5.24, whose headings say experimental
        "book_deltas", "book_snapshots", "funding_rates", "market_statistics",
        "option_chain_snapshots", "quotes", "reference_prices", "roll_calendar", "trades",
    ]  # fmt: skip
    schemas = load_schemas()
    flagged = {k for k, s in schemas.items() if s.status == "experimental"}
    assert [k for k in experimental if k not in flagged] == []


def test_a_kind_without_a_file_fails_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(str(SCHEMA_DIR), tmp_path, dirs_exist_ok=True)
    shutil.rmtree(tmp_path / "quotes")
    assert main(tmp_path) == 1
    assert "quotes: no schema file" in capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "made", [[], ["bars"], None], ids=["empty", "a folder without 1.0.json", "no folder"]
)
def test_no_schema_file_is_an_error_not_an_empty_registry(
    tmp_path: Path, made: list[str] | None
) -> None:
    # An installed checker that found none would check nothing at the schema level (#145).
    for name in made or []:
        (tmp_path / name).mkdir()
    with pytest.raises(FileNotFoundError, match="no schema file"):
        load_schemas(tmp_path if made is not None else tmp_path / "missing")


def test_schema_files_cover_stable_datasets() -> None:
    status = section_status(TDS_DOC.read_text(encoding="utf-8"))
    stable = [kind for kind, n in CHAPTER_5.items() if status[n] == "stable"]
    assert len(stable) == 23  # 5.1-5.5, 5.10-5.21, 5.25 and 5.27 (5.12 and 5.26 name none)
    schemas = load_schemas()
    assert [k for k in stable if k not in schemas or schemas[k].status != "stable"] == []


def test_each_chapter_5_kind_is_named_in_its_section() -> None:
    doc = TDS_DOC.read_text(encoding="utf-8")
    heading_to_next = r"^### (5\.\d+) [\s\S]*?(?=^#{2,3} |\Z)"
    sections = {m[1]: m[0] for m in re.finditer(heading_to_next, doc, flags=re.MULTILINE)}
    assert [kind for kind, n in CHAPTER_5.items() if f"`{kind}`" not in sections[n]] == []


def test_a_status_other_than_its_sections_is_a_problem() -> None:
    doc = TDS_DOC.read_text(encoding="utf-8")
    flagged = {
        "bars": Schema("bars", "experimental", ()),
        "bar": Schema("bar", "stable", ()),
        "quotes": Schema("trades", "experimental", ()),
    }
    assert file_problems(flagged, section_status(doc)) == [
        "bars: status `experimental`, section 5.5 is `stable`",
        "bar: not a TDS chapter 5 dataset kind",
        "quotes/1.0.json: kind `trades`, folder `quotes`",
    ]


def test_verify_prints_the_lists_and_the_match(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == (
        "stable: bars, calendar_segments, calendar_sessions, classifications, corporate_actions,"
        " delistings, eligibility_daily, events, feature_panels, fundamentals_events,"
        " fundamentals_state, fx_rates, instrument_symbols, instrument_xref, instruments,"
        " label_panels, market_rules, rates, series_observations, share_counts, tradability_daily,"
        " trading_status_events, universe_membership"
    )
    assert out[1] == (
        "experimental: book_deltas, book_snapshots, funding_rates, market_statistics,"
        " option_chain_snapshots, quotes, reference_prices, roll_calendar, trades"
    )
    assert out[2:] == ["doc tables match schema files"]
