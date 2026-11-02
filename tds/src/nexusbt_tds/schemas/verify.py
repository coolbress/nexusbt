"""`python -m nexusbt_tds.schemas.verify`: TDS chapter 5's tables equal the schema files (spec 9.1).

A schema file is `tds/schemas/<kind>/1.0.json`: `kind`, `schema_version`, `status`
(`stable`|`experimental`), `section`, `key`, `sort`, `partitions` and `columns`. A column is
`{"name", "type", "null"}` plus `"enum": "closed"|"open"` for a code; `type` is a TDS 3.2 name or
null where the document does not state one, and `null` is true, false, the document's condition
text, or null where unstated. A blank document cell in a row whose meaning is a section (`5.17`)
takes that section's row of the same name (the file marks it `"from"`); any other blank cell
needs the file's value unstated too. A mismatch is reported, never fixed here: the TDS document
is changed by its own pull request.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: The repository: this file is `tds/src/nexusbt_tds/schemas/verify.py`.
ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = ROOT / "tds" / "schemas"
DOC = ROOT / "docs" / "tds" / "tds-v1.4.md"
VERSION = "1.0"

#: The TDS chapter 5 dataset kinds by section (5.12 and 5.26 define no dataset).
_SECTIONS = """
5.1 instruments; 5.2 instrument_symbols; 5.3 instrument_xref; 5.4 calendar_sessions
5.4 calendar_segments; 5.5 bars; 5.6 trades; 5.7 quotes; 5.8 book_deltas; 5.8 book_snapshots
5.9 market_statistics; 5.10 tradability_daily; 5.10 trading_status_events
5.11 corporate_actions; 5.13 delistings; 5.14 share_counts; 5.15 fx_rates; 5.16 rates
5.17 fundamentals_events; 5.18 fundamentals_state; 5.19 classifications
5.20 universe_membership; 5.20 eligibility_daily; 5.21 events; 5.21 series_observations
5.22 roll_calendar; 5.23 option_chain_snapshots; 5.24 funding_rates; 5.24 reference_prices
5.25 feature_panels; 5.25 label_panels; 5.27 market_rules
"""
CHAPTER_5: dict[str, str] = {kind: n for n, kind in re.findall(r"(5\.\d+) (\w+)", _SECTIONS)}

Null = bool | str | None


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    type: str | None
    null: Null
    enum: str | None = None

    def type_cell(self) -> str:
        if self.type is None:
            return ""
        return f"{self.type} ({self.enum})" if self.enum else self.type

    def null_cell(self) -> str:
        if isinstance(self.null, bool):
            return "yes" if self.null else "no"
        return self.null or ""


@dataclass(frozen=True, slots=True)
class Schema:
    kind: str
    status: str
    columns: tuple[Column, ...]


_HEADER = "| Column | Type | Null | Meaning |"
_NAMED = re.compile(r"^(?:### 5\.\d+ )?`(\w+)`")
#: (name, type cell, null cell, the section a blank cell was taken from or "").
Row = tuple[str, str, str, str]


def _chapter(doc: str) -> list[str]:
    return f"\n{doc}".split("\n## 5. ", 1)[1].split("\n## 6. ", 1)[0].splitlines()


def doc_tables(doc: str) -> dict[str, list[Row]]:
    """Chapter 5's column tables by kind, one row per column, in order.

    A table belongs to the kind named first in the last heading, or line, that starts with one.
    A row naming several columns gives each the shared cell, or its part of a cell with one
    ` / `-separated part per column (`ts_event, ts_recv | ts_ns | no / yes`).
    """
    tables: dict[str, list[Row]] = {}
    by_section: dict[str, str] = {}
    kind: str | None = None
    rows: list[Row] | None = None
    for line in _chapter(doc):
        if heading := re.match(r"### (5\.\d+) ", line):
            kind, section = None, heading[1]
        if named := _NAMED.match(line):
            kind = named.group(1)
        if line.strip() == _HEADER and kind is not None:
            rows, by_section[section] = tables.setdefault(kind, []), kind
        elif rows is not None and line.startswith("|"):
            if line.startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            names = [name.strip() for name in cells[0].split(",")]
            ref = cells[3] if re.fullmatch(r"5\.\d+", cells[3]) else ""
            parts = zip(_spread(cells[1], len(names)), _spread(cells[2], len(names)), strict=True)
            rows.extend((name, *part, ref) for name, part in zip(names, parts, strict=True))
        else:
            rows = None
    named_rows = {k: {row[0]: row for row in rows} for k, rows in tables.items()}

    def resolve(row: Row) -> Row:
        name, type_cell, null_cell, ref = row
        source = named_rows.get(by_section.get(ref, ""), {}).get(name)
        if source is None or (type_cell and null_cell):
            return name, type_cell, null_cell, ""
        return name, type_cell or source[1], null_cell or source[2], ref

    return {k: [resolve(row) for row in rows] for k, rows in tables.items()}


def _spread(cell: str, n: int) -> list[str]:
    parts = cell.split(" / ")
    return parts if n > 1 and len(parts) == n else [cell] * n


def compare(doc: str, schemas: dict[str, Schema]) -> list[str]:
    """Each mismatch between chapter 5's tables and the schemas of the same kind, as a line."""
    tables = doc_tables(doc)
    headers = sum(line.startswith("| Column |") for line in _chapter(doc))
    out = [f"chapter 5 has {headers} column tables, {len(tables)} read"] * (headers != len(tables))
    for kind, rows in tables.items():
        schema = schemas.get(kind)
        if schema is None:
            continue
        doc_names = [row[0] for row in rows]
        file_names = [column.name for column in schema.columns]
        if doc_names != file_names:
            out.append(
                f"{kind}: doc columns {', '.join(doc_names)}; schema {', '.join(file_names)}"
            )
            continue
        for (name, type_cell, null_cell, ref), column in zip(rows, schema.columns, strict=True):
            via = f" ({ref})" if ref else ""
            pairs = (
                ("type", type_cell, column.type_cell()),
                ("null", null_cell, column.null_cell()),
            )
            for what, cell, own in pairs:
                if cell != own:
                    out.append(f"{kind}: column {name}: doc {what} `{cell}`{via}, schema `{own}`")
    return out


def section_status(doc: str) -> dict[str, str]:
    """`experimental` for each chapter 5 section whose heading says so, else `stable` (5.6)."""
    headings = re.findall(r"^### (5\.\d+) (.*)$", doc, flags=re.MULTILINE)
    return {n: "experimental" if "experimental" in text else "stable" for n, text in headings}


def load_schemas(root: Path = SCHEMA_DIR) -> dict[str, Schema]:
    """Every `<kind>/1.0.json` under `root`, by kind."""
    schemas: dict[str, Schema] = {}
    for path in sorted(root.glob(f"*/{VERSION}.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        columns = tuple(
            Column(c["name"], c["type"], c["null"], c.get("enum")) for c in data["columns"]
        )
        schemas[path.parent.name] = Schema(data["kind"], data["status"], columns)
    return schemas


def file_problems(schemas: dict[str, Schema], status: dict[str, str]) -> list[str]:
    """A file naming another folder's kind or no chapter 5 kind, or unlike its section's status."""
    out: list[str] = []
    for folder, schema in schemas.items():
        if schema.kind != folder:
            out.append(f"{folder}/{VERSION}.json: kind `{schema.kind}`, folder `{folder}`")
        elif folder not in CHAPTER_5:
            out.append(f"{folder}: not a TDS chapter 5 dataset kind")
        elif schema.status != (want := status[section := CHAPTER_5[folder]]):
            out.append(f"{folder}: status `{schema.status}`, section {section} is `{want}`")
    return out


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    schemas = load_schemas()
    for status in ("stable", "experimental"):
        kinds = sorted(k for k, s in schemas.items() if s.status == status)
        print(f"{status}: {', '.join(kinds) or '(none)'}")
    # A table of a kind missing from CHAPTER_5 is not skipped silently either.
    missing = [kind for kind in {**CHAPTER_5, **doc_tables(doc)} if kind not in schemas]
    if missing:
        # The files arrive in three pull requests (#55); until the last, this is said, not failed.
        print(f"::warning::not yet confirmed: no schema file yet for {', '.join(missing)}")
    problems = file_problems(schemas, section_status(doc)) + compare(doc, schemas)
    for line in problems:
        print(line)
    if problems:
        return 1
    print("doc tables match schema files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
