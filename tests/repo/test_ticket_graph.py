"""The "Blocked by" graph of the plan is acyclic and never points forward (T0.12, #46).

The chapter here is a small made-up one in the plan's ticket-line shape; the plan document
`docs/plan/plan.md` itself is checked in the last test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ticket_graph import TICKET_ID, Ticket, check, milestones, tickets

CHAPTER = """\
### 10.1 Engine tickets

#### M0 — Normative contracts

**T0.1 `docs: add the spec`** · `M0` `docs` · S (docs) · Blocked by: none · §2.1
- Context: the spec.

**T0.2a `chore: skeleton`** **[v3]** · `M0` `infra` · M · Blocked by: T0.1 · §2.3~2.6

#### M1 — Snapshot

**T1.1a `feat(data): open snapshots`** · `M1` `data` · M · Blocked by: T0.2a, T0.1 · §4.1

#### M6 — Performance

**T7.1 `feat: hold band`** **[new]** · `M6 (last ticket)` `portfolio` · M · \
Blocked by: T1.1a, T0.2a (and T0.1 if it was done) · §5.5.3 [SC-02]

### 10.2 Producer-side tickets (left out of the public edition)

**T9.1 `not a ticket of 10.1`** · `M0` `x` · S · Blocked by: T0.1 · §1
"""
ORDER = ["M0", "M1", "M6"]


def test_the_ticket_lines_of_10_1_are_read_with_their_milestone_and_dependencies() -> None:
    """A note after the milestone and a conditional dependency are read too."""
    assert tickets(CHAPTER) == [
        Ticket("T0.1", "M0", ()),
        Ticket("T0.2a", "M0", ("T0.1",)),
        Ticket("T1.1a", "M1", ("T0.2a", "T0.1")),
        Ticket("T7.1", "M6", ("T1.1a", "T0.2a", "T0.1")),
    ]
    assert milestones(CHAPTER) == ORDER
    assert check(tickets(CHAPTER), ORDER) == []


def test_a_ticket_under_the_wrong_milestone_heading_stops_the_reading() -> None:
    text = CHAPTER.replace("· `M1` `data`", "· `M2` `data`")
    with pytest.raises(ValueError, match=r"T1\.1a says milestone M2 under the heading of M1"):
        tickets(text)
    with pytest.raises(ValueError, match=r"no section 10\.1"):
        tickets("### 10.2 only\n")


def test_a_later_milestone_an_unknown_ticket_and_an_id_written_twice_are_problems() -> None:
    found = [*tickets(CHAPTER), Ticket("T0.3", "M0", ("T1.1a", "T0.9")), Ticket("T0.3", "M0", ())]
    assert check(found, ORDER) == [
        "T0.3: written twice",
        "T0.3 (M0): blocked by T1.1a, which is in the later milestone M1",
        "T0.3: blocked by T0.9, which is no ticket",
    ]


def test_a_cycle_is_a_problem_reported_as_its_path() -> None:
    found = [
        Ticket("T0.1", "M0", ("T0.3",)),
        Ticket("T0.2", "M0", ("T0.1",)),
        Ticket("T0.3", "M0", ("T0.2",)),
    ]
    assert check(found, ORDER) == ["cycle: T0.1 → T0.3 → T0.2 → T0.1"]


PLAN = Path(__file__).resolve().parents[2] / "docs" / "plan" / "plan.md"


def test_acyclic_and_milestone_order() -> None:
    """The plan's ticket graph (10.1) holds the rule of 10.0 "Ticket rules". A problem here
    is a plan defect: it stops and proposes a pull request (#46, "Not building")."""
    text = PLAN.read_text(encoding="utf-8")
    found = tickets(text)
    assert len(found) >= 224, (
        "the plan held 224 tickets when it left the spec; fewer means lines were lost"
    )
    assert check(found, milestones(text)) == []


SPEC = PLAN.parents[1] / "spec" / "engine-spec-v3.4.md"


def appendix_b_tickets(spec: str) -> list[list[str]]:
    """The ticket ids in the Ticket column of each row of appendix B's tables."""
    block = spec.split("\n## Appendix B.", 1)[1].split("\n## ", 1)[0]
    rows: list[list[str]] = []
    column, previous = 0, ""
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and not previous.startswith("|"):
            column = cells.index("Ticket")
        elif line.startswith("|") and set(line) - set("|-: "):
            rows.append(TICKET_ID.findall(cells[column]))
        previous = line
    return rows


def test_every_ticket_appendix_b_names_is_a_ticket_of_the_plan() -> None:
    rows = appendix_b_tickets(SPEC.read_text(encoding="utf-8"))
    assert len(rows) >= 256, (
        "appendix B's tables held 256 rows on 2026-11-25; fewer means rows were lost"
    )
    known = {t.id for t in tickets(PLAN.read_text(encoding="utf-8"))}
    assert sorted({t for row in rows for t in row} - known) == []
