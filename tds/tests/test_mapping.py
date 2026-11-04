"""`read_mapping`: a mapping file as JSON, else the YAML subset of TDS 9.5 (#257 Decisions)."""

from __future__ import annotations

import pytest

from nexusbt_tds._mapping import read_mapping


def test_json_is_read_first() -> None:
    assert read_mapping('{"profiles": ["tds:minimal-daily@1.0"], "n": 1}') == {
        "profiles": ["tds:minimal-daily@1.0"],
        "n": 1,  # JSON keeps its numbers; YAML plain values below stay text
    }
    assert read_mapping('\ufeff{"a": 1}') == {"a": 1}  # a byte-order mark is not part of it
    with pytest.raises(ValueError, match=r"^line 2: not JSON \(Illegal trailing comma"):
        read_mapping('{\n  "a": 1,\n}\n')  # meant as JSON: JSON's own error, not a YAML one


def test_an_empty_file_is_none() -> None:
    assert read_mapping("# only a comment\n\n") is None


def test_list_forms() -> None:
    assert read_mapping("a:\n- b\n- c\nd: e\n") == {"a": ["b", "c"], "d": "e"}
    assert read_mapping("a:\n  -\n  -\n    b: c\n") == {"a": [None, {"b": "c"}]}
    assert read_mapping("- key: v\n  other: w\n- x\n") == [{"key": "v", "other": "w"}, "x"]


def test_the_subset() -> None:
    text = """# a comment line
name: "demo: a colon inside quotes"
profiles: [tds:minimal-daily@1.0, 'it''s']
market: {code: US, timezone: America/New_York}
datasets:
  bars:
    file: bars.csv   # a comment after a value
    missing_values: ["-", 0, "#"]
    columns:
      session_date: {from: date, format: "%Y%m%d"}
      close:
        from: 종가
    notes:
      - plain, with a comma
      - {a: b}
      - key: value
        other: 2
    empty:
"""
    assert read_mapping(text) == {
        "name": "demo: a colon inside quotes",
        "profiles": ["tds:minimal-daily@1.0", "it's"],
        "market": {"code": "US", "timezone": "America/New_York"},
        "datasets": {
            "bars": {
                "file": "bars.csv",
                "missing_values": ["-", "0", "#"],
                "columns": {
                    "session_date": {"from": "date", "format": "%Y%m%d"},
                    "close": {"from": "종가"},
                },
                "notes": ["plain, with a comma", {"a": "b"}, {"key": "value", "other": "2"}],
                "empty": None,
            }
        },
    }


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("profiles: &p [x]\n", 1),  # anchor
        ("a: b\nc: !tag d\n", 2),  # tag
        ("a: |\n  block\n", 1),  # block scalar
        ("a: b\na: c\n", 2),  # a key twice
        ("a:\n  b: c\n d: e\n", 3),  # indentation off
        ("a: 'not closed\n", 1),
        ("a: {b: c\n", 1),
        ("a: b\n- c\n", 2),  # a list item among keys
        ("a\n", 1),
        ('a: b\nc: "C:\\dir"\n', 2),  # an escape JSON does not read
        ("a: {b: c, b: d}\n", 1),  # a key twice, in flow form too
        ("a:\n\tb: c\n", 2),  # a tab in the indentation
        ("a: {b: c} d\n", 1),  # text after a flow form
        ("a: {b, c: d}\n", 1),  # a flow key with no `:`
        ('a: "b\\"\n', 1),  # the closing quote escaped
        ("a: {b: }\n", 1),  # an empty flow value
    ],
)
def test_outside_the_subset_names_the_line(text: str, line: int) -> None:
    with pytest.raises(ValueError, match=rf"^line {line}: .*; write this part as JSON$"):
        read_mapping(text)
