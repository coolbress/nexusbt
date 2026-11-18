"""TDS 10.5 (#529): the `tds_draft` the code writes is the one TDS's revision history last moved
to, so an edit of the TDS text that moves it and forgets the code fails here."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nexusbt_tds.manifest import TDS_DRAFT

ROOT = Path(__file__).resolve().parents[2]
#: Per language: how an entry says it moves `tds_draft`, and how it says it does not.
SAYS = {
    "tds-v1.4.md": (r"moves `tds_draft` to (\d{4}-\d{2}-\d{2})", r"`tds_draft` stays "),
    "tds-v1.4.ko.md": (r"`tds_draft`를 (\d{4}-\d{2}-\d{2})로 옮긴다", r"`tds_draft`는 \S+ 그대로"),
}
#: The writers that cannot import `TDS_DRAFT` (the engine's testing layer, the standalone
#: conformance builder) and write it as a literal.
LITERALS = ("src/nexusbt/testing/_synth_package.py", "tds/conformance/build.py")


def last_move(text: str, moves: str, stays: str) -> str:
    """The date the last entry that moves `tds_draft` names; every entry from the first move on
    says whether it moves it."""
    history = text.rsplit("\n## ", 1)[1]  # the last chapter: Revision history, 갱신 기록
    entries = [e for e in history.splitlines() if re.match(r"- \d{4}-\d{2}-\d{2}: ", e)]
    first = next(i for i, e in enumerate(entries) if re.search(moves, e))
    silent = [e[:40] for e in entries[first:] if not re.search(f"{moves}|{stays}", e)]
    assert silent == [], "an entry that says neither that it moves `tds_draft` nor that it stays"
    return [m.group(1) for e in entries[first:] if (m := re.search(moves, e))][-1]


@pytest.mark.parametrize("name", SAYS)
def test_the_code_writes_the_date_the_history_last_moved_to(name: str) -> None:
    text = (ROOT / "docs" / "tds" / name).read_text(encoding="utf-8")
    assert last_move(text, *SAYS[name]) == TDS_DRAFT
    for path in LITERALS:
        source = (ROOT / path).read_text(encoding="utf-8")
        assert re.findall(r'"tds_draft": "([^"]+)"', source) == [TDS_DRAFT], path


def test_a_later_move_the_code_missed_is_caught() -> None:
    moved = "x\n## Revision history\n- 2026-11-18: moves `tds_draft` to 2026-11-18.\n"
    later = moved + "- 2026-12-01: a hash rule; moves `tds_draft` to 2026-12-01.\n"
    assert last_move(moved, *SAYS["tds-v1.4.md"]) == "2026-11-18"
    assert last_move(later, *SAYS["tds-v1.4.md"]) == "2026-12-01" != TDS_DRAFT
    with pytest.raises(AssertionError, match="neither"):
        last_move(later + "- 2026-12-02: wording.\n", *SAYS["tds-v1.4.md"])
