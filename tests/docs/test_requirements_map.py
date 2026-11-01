"""`docs/requirements.md` has one row for every id of the spec's appendix B (T0.12, #46)."""

from __future__ import annotations

import re
from pathlib import Path

from requirements_map import appendix_b_ids, map_rows, missing

APPENDIX = """\
## Appendix B. Requirement map

### B.1 Requirements R, performance P

| Requirement | Section | M | Status | Ticket |
|---|---|---|---|---|
| R-01 import surface | 3.1 | M0 | v1 | T0.2a |

### B.4 Three-reviewer review consensus RV

| RV | Priority | Content | Where reflected | Ticket |
|---|---|---|---|---|
| C04a | P0 | three label times | 5.8 | T2.7 |
| Q08~Q11 | P2 | four small items | TDS | (TDS document), T0.7 |
| D1 | user | window kernel | 5.3.10 | T1.24 |

### B.5 Teardown V31

| V31 | Priority | Where reflected | Ticket |
|---|---|---|---|
| 01 integer quantity arithmetic | P0 | INV-18 | T0.15c |
| LS-01~LS-11 short selling | user decision | header | T4.Gs |

## Appendix C. `SimConfig` knob table

| Knob | Default |
|---|---|
| R-99 | not appendix B |
"""

MAP = """\
Prose with a | bar in it is not a row.

| Id | Requirement | Spec status | Status | Ticket |
|---|---|---|---|---|
| R-01 | import surface | v1 | planned | T0.2a (#45) |
| RV-Q08~Q11 | four | | planned | T0.7 |
| RV-C04a | labels | | planned | T2.7 |
"""


def test_appendix_b_ids_carry_the_name_of_their_table() -> None:
    expected = ["R-01", "RV-C04a", "RV-Q08~Q11", "RV-D1", "V31-01", "V31-LS-01~LS-11"]
    assert appendix_b_ids(APPENDIX) == expected


def test_map_rows_are_read_by_their_column_names_and_cover_ranges_and_letters() -> None:
    rows = map_rows(MAP)
    assert rows[0] == {
        "Id": "R-01",
        "Requirement": "import surface",
        "Spec status": "v1",
        "Status": "planned",
        "Ticket": "T0.2a (#45)",
    }
    ids = [row["Id"] for row in rows]
    assert missing(ids, ["R-01", "RV-Q09", "RV-Q11", "RV-C04", "RV-C04a"]) == []
    assert missing(ids, ["R-02", "RV-Q12", "RV-C05"]) == ["R-02", "RV-Q12", "RV-C05"]


ROOT = Path(__file__).resolve().parents[2]
SPEC_IDS = appendix_b_ids((ROOT / "docs/spec/engine-spec-v3.4.md").read_text(encoding="utf-8"))
ROWS = map_rows((ROOT / "docs/requirements.md").read_text(encoding="utf-8"))
MAP_IDS = [row["Id"] for row in ROWS]


def test_the_map_has_exactly_one_row_per_id_of_appendix_b() -> None:
    assert MAP_IDS == SPEC_IDS


def test_every_requirement_listed() -> None:
    """R-01~R-70 and P1~P10. R-28 and R-29 are numbers the spec never used (appendix A-29)."""
    wanted = [f"R-{n:02d}" for n in range(1, 71) if n not in (28, 29)]
    wanted += [f"P{n}" for n in range(1, 11)]
    assert missing(MAP_IDS, wanted) == []


def test_every_sc_tds_d_and_rv_listed() -> None:
    wanted = [f"SC-{n:02d}" for n in range(1, 28)]
    wanted += [f"TDS-D{n}" for n in range(1, 25)]
    wanted += [f"RV-C{n:02d}" for n in range(1, 14)]
    wanted += [f"RV-I{n:02d}" for n in range(1, 11)]
    wanted += [f"RV-Q{n:02d}" for n in range(1, 12)]
    assert missing(MAP_IDS, wanted) == []


def test_every_applied_v31_listed() -> None:
    """V31-01~30 and 33 (31, 32 and 34 are deferred in spec 12.1), and LS-01~LS-11."""
    wanted = [f"V31-{n:02d}" for n in [*range(1, 31), 33]]
    wanted += [f"V31-LS-{n:02d}" for n in range(1, 12)]
    assert missing(MAP_IDS, wanted) == []


def test_every_r3_listed() -> None:
    assert missing(MAP_IDS, [f"R3-{n:02d}" for n in range(1, 29)]) == []


def test_every_r4_listed() -> None:
    assert missing(MAP_IDS, [f"R4-{n:02d}" for n in range(1, 29)]) == []


def test_every_row_has_a_status_word_and_a_planned_row_names_its_ticket() -> None:
    words = {"planned", "implemented", "deferred", "replaced"}
    assert [r["Id"] for r in ROWS if r["Status"] not in words] == []
    ticket = re.compile(r"\bT\d+\.[A-Za-z0-9]+\b")
    planned = [r for r in ROWS if r["Status"] == "planned"]
    assert [r["Id"] for r in planned if not ticket.search(r["Ticket"])] == []
