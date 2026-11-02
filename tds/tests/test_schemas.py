"""TDS 5, 10.3: the schema files `tds/schemas/<kind>/1.0.json` and `nexusbt_tds.schemas.verify`."""

from __future__ import annotations

import re

import pytest

from nexusbt_tds.schemas.verify import (
    CHAPTER_5,
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
| kind | code (closed) | no | `a`, `b` |
| open, close | f64 | yes | prices |
| ts_event, ts_recv | ts_ns | no / yes | |
| ts_start | ts_us/ns | daily yes / intraday no | |
| unit | | | 5.17 |

## 6. Next chapter
"""


def _things(**changes: Column) -> Schema:
    columns = {
        "thing_id": Column("thing_id", "id", False),
        "kind": Column("kind", "code", False, enum="closed"),
        "open": Column("open", "f64", True),
        "close": Column("close", "f64", True),
        "ts_event": Column("ts_event", "ts_ns", False),
        "ts_recv": Column("ts_recv", "ts_ns", True),
        "ts_start": Column("ts_start", "ts_us/ns", "daily yes / intraday no"),
        "unit": Column("unit", "code", False),
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


def test_a_column_missing_or_out_of_order_is_a_mismatch() -> None:
    first, second, _open, *rest = _things().columns
    reordered = Schema("things", "stable", (second, first, *rest))
    assert compare(SAMPLE_DOC, {"things": reordered}) == [
        "things: doc columns thing_id, kind, open, close, ts_event, ts_recv, ts_start, unit;"
        " schema kind, thing_id, close, ts_event, ts_recv, ts_start, unit",
    ]


def test_doc_tables_match_schema_files() -> None:
    doc = TDS_DOC.read_text(encoding="utf-8")
    schemas = load_schemas()
    assert compare(doc, schemas) == []
    # Tables were compared, not skipped: only the experimental tables wait for a file (#55).
    assert doc_tables(doc).keys() - schemas.keys() == {"trades", "book_deltas"}


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
    assert out[0].startswith("stable: bars, calendar_segments, calendar_sessions, classifications,")
    assert out[1].startswith("experimental:")
    assert out[-1] == "doc tables match schema files"
