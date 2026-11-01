"""Spec T0.3: the id constant, the engine column sets, the phases and the schema versions.

Expected values are read from the documents, not restated here: the phase order
from spec 5.6.3, the column sets from the spec 4.6 table, the columns each TDS
dataset defines from TDS chapter 5, the unit vocabulary from TDS 3.4.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = (ROOT / "docs" / "spec" / "engine-spec-v3.4.md").read_text(encoding="utf-8")
TDS = (ROOT / "docs" / "tds" / "tds-v1.4.md").read_text(encoding="utf-8")


def section(text: str, heading: str) -> str:
    """The body under the first heading that starts with `heading`, up to the next heading."""
    match = re.search(rf"^#+ {re.escape(heading)}.*?$(.*?)^#", text, re.MULTILINE | re.DOTALL)
    assert match, f"no heading {heading!r}"
    return match.group(1)


def tds_table_columns(heading: str) -> set[str]:
    """The column names in the first-cell of each row of a TDS chapter-5 column table."""
    names: set[str] = set()
    for line in section(TDS, heading).splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) >= 2 and cells[0] not in {"Column", ""} and not cells[0].startswith("-"):
            names.update(name.strip() for name in cells[0].split(","))
    return names


def spec_4_6_rows() -> dict[str, set[str]]:
    """Dataset → the columns the spec 4.6 table says the engine reads.

    A row is a dataset when its first cell starts with one backticked name; the
    index-instruments row (instruments + bars) and the dictionary rows are not
    datasets (#48). "every column (TDS 5.x)" is that TDS table's column set.
    """
    rows: dict[str, set[str]] = {}
    table = section(SPEC, "4.6").split("Per dataset", 1)[1].split("\n\n")[1]
    for line in table.splitlines()[2:]:
        first, columns = (cell.strip() for cell in line.split("|")[1:3])
        name = re.match(r"`([a-z_]+)`", first)
        if not name:
            continue
        every = re.match(r"every column \(TDS (5\.\d+)", columns)
        if every:
            rows[name.group(1)] = tds_table_columns(every.group(1) + " ")
        else:
            listed = re.match(r"`([^`]*)`", columns)
            assert listed, line
            rows[name.group(1)] = {c.strip() for c in listed.group(1).split(",")}
    return rows


def test_engine_columns_match_spec_4_6_table() -> None:
    from nexusbt.contracts import ENGINE_COLUMNS

    expected = spec_4_6_rows()
    assert len(expected) == 17
    assert {name: set(cols) for name, cols in ENGINE_COLUMNS.items()} == expected
    assert all(isinstance(cols, frozenset) for cols in ENGINE_COLUMNS.values())


def tds_defined_names(dataset: str) -> set[str]:
    """Names TDS chapter 5 defines under the heading that names `dataset`.

    A section with a column table is read from the table alone, so a name its prose
    mentions (`bars` says `shares_out` was moved out) does not count. A section
    without one (5.14, 5.19, 5.20, 5.25) gives its columns as backticked prose, read
    with every parenthesis dropped except a `key (...)`, as the others hold a
    column's values or examples (`reason` code null (open: `fund`, ...)) and a value
    is not a column. A heading that covers two datasets is read whole: a sibling's
    column would also pass, a column TDS never names would not.
    """
    heading = re.search(rf"^### (5\.\d+ )[^\n]*`{dataset}`", TDS, re.MULTILINE)
    assert heading, f"TDS chapter 5 has no heading for {dataset}"
    table = tds_table_columns(heading.group(1))
    if table:
        return table
    prose, previous = section(TDS, heading.group(1)), ""
    while prose != previous:  # innermost first, so nested parentheses go too
        prose, previous = re.sub(r"(?<![Kk]ey )\([^()]*\)", "", prose), prose
    return set(re.findall(r"`([a-z_][a-z0-9_]*)`", prose))


def test_engine_columns_subset_of_tds_schemas() -> None:
    from nexusbt.contracts import ENGINE_COLUMNS

    undefined = {
        dataset: sorted(missing)
        for dataset, cols in ENGINE_COLUMNS.items()
        if (missing := cols - tds_defined_names(dataset))
    }
    assert undefined == {}


def id_literals(source: str) -> list[int]:
    """Line numbers of each string constant that is exactly the instrument key's name."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and node.value == "instrument_id"
    ]


def test_no_id_alias_public() -> None:
    import nexusbt.contracts as contracts

    # spec header "Identifier name": the key is `instrument_id`, defined only by this constant
    assert contracts.ID_COLUMN == "instrument_id"
    holders = [n for n in dir(contracts) if getattr(contracts, n) == "instrument_id"]
    assert holders == ["ID_COLUMN"]
    engine = sorted((ROOT / "src" / "nexusbt").rglob("*.py"))
    spelled = {
        str(f.relative_to(ROOT)): lines
        for f in engine
        if (lines := id_literals(f.read_text(encoding="utf-8")))
    }
    assert list(spelled) == ["src/nexusbt/contracts/__init__.py"]
    assert len(spelled["src/nexusbt/contracts/__init__.py"]) == 1
    # the v2 alias removed by RV-Q01
    assert [f for f in engine if "security_id" in f.read_text(encoding="utf-8")] == []


def test_unit_matches_tds_3_4() -> None:
    from nexusbt.contracts import Unit

    clause = re.search(r"Unit vocabulary \(`unit`\): (.*?)\. `pct` is not used", TDS)
    assert clause
    expected = re.findall(r"(?:^|, )`([A-Za-z_]+)`", clause.group(1))
    assert len(expected) == 11
    assert [unit.value for unit in Unit] == expected


def test_schema_versions_match_2_4() -> None:
    import nexusbt.contracts as contracts

    row = next(
        line for line in section(SPEC, "2.4").splitlines() if line.startswith("| `contracts`")
    )
    declared = dict(re.findall(r'`([A-Z_]+_SCHEMA) = "([^"]+)"`', row))
    assert sorted(declared) == ["CHECKPOINT_SCHEMA", "EVENTS_SCHEMA", "RUN_SCHEMA"]
    assert {name: getattr(contracts, name) for name in declared} == declared


def test_phase_order_matches_5_6_3() -> None:
    from nexusbt.contracts import Phase

    order = re.search(r"\*\*phase order\*\* is (.*?), then", section(SPEC, "5.6.3"))
    assert order
    expected = [name.strip(" `") for name in order.group(1).split("<")]
    assert len(expected) == 7
    assert [phase.name.lower() for phase in Phase] == expected
    assert sorted(Phase, reverse=True) == list(reversed(Phase))  # members compare in that order
