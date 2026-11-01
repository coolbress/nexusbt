"""Read the ticket lines of spec 10.1 and check their "Blocked by" graph (T0.12).

A ticket line: ``**T0.2a `chore: …`** **[v3]** · `M0` `infra` · M · Blocked by: T0.1 · §2.3``.
The milestone order is the order of the ``#### <M> — …`` headings of 10.1. Spec 10.0
("Ticket rules") says the graph is acyclic and that every dependency is in the same
or an earlier milestone; `check` says where that is not so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: The ticket lines live between these two headings.
START = re.compile(r"^### 10\.1 ")
END = re.compile(r"^### 10\.2 ")

#: `#### M3a — …`, `#### v1.x — …`
MILESTONE = re.compile(r"^#### (\S+) — ")

#: The id, the first backtick field after the bold title (its first word is the
#: milestone: `M6 (before T7.1)`), then everything after "Blocked by:" up to the next `·`.
TICKET = re.compile(
    r"^\*\*(?P<id>T\d+\.[A-Za-z0-9]+) `[^`]*`\*\*.*?· `(?P<milestone>[^\s`]+)[^`]*`"
    r".*?· Blocked by: (?P<blocked>[^·]*)"
)
TICKET_ID = re.compile(r"\bT\d+\.[A-Za-z0-9]+\b")


@dataclass(frozen=True)
class Ticket:
    id: str
    milestone: str
    blocked_by: tuple[str, ...]


def section(text: str) -> list[str]:
    """The lines of 10.1."""
    lines = text.splitlines()
    start = [i for i, line in enumerate(lines) if START.match(line)]
    end = [i for i, line in enumerate(lines) if END.match(line) and start and i > start[0]]
    if not end:
        raise ValueError("the text has no section 10.1 followed by 10.2")
    return lines[start[0] : end[0]]


def milestones(text: str) -> list[str]:
    """The milestones of 10.1 in the order of their headings."""
    return [m.group(1) for m in map(MILESTONE.match, section(text)) if m]


def tickets(text: str) -> list[Ticket]:
    """The tickets of 10.1, in order; a ticket whose milestone field disagrees with
    the heading it sits under stops the reading, since the two cannot both be read."""
    found = []
    heading = ""
    for line in section(text):
        if m := MILESTONE.match(line):
            heading = m.group(1)
        elif m := TICKET.match(line):
            if m.group("milestone") != heading:
                raise ValueError(
                    f"{m.group('id')} says milestone {m.group('milestone')} "
                    f"under the heading of {heading}"
                )
            blocked = tuple(TICKET_ID.findall(m.group("blocked")))
            found.append(Ticket(m.group("id"), heading, blocked))
    return found


def check(found: list[Ticket], order: list[str]) -> list[str]:
    """One line per problem (an id written twice, a dependency that is no ticket or is
    in a later milestone, a cycle as the path that closes it); empty when the graph is sound."""
    problems = []
    by_id: dict[str, Ticket] = {}
    for t in found:
        if t.id in by_id:
            problems.append(f"{t.id}: written twice")
        by_id[t.id] = t
    for t in found:
        for dep in t.blocked_by:
            if dep not in by_id:
                problems.append(f"{t.id}: blocked by {dep}, which is no ticket")
            elif order.index(by_id[dep].milestone) > order.index(t.milestone):
                problems.append(
                    f"{t.id} ({t.milestone}): blocked by {dep}, "
                    f"which is in the later milestone {by_id[dep].milestone}"
                )
    if cycle := first_cycle(by_id):
        problems.append("cycle: " + " → ".join(cycle))
    return problems


def first_cycle(by_id: dict[str, Ticket]) -> list[str]:
    """The first cycle a depth-first walk meets, closed at its first id; empty when none."""
    done: set[str] = set()
    path: list[str] = []

    def walk(node: str) -> list[str]:
        if node in path:
            return [*path[path.index(node) :], node]
        if node in done or node not in by_id:
            return []
        path.append(node)
        for dep in by_id[node].blocked_by:
            if cycle := walk(dep):
                return cycle
        path.pop()
        done.add(node)
        return []

    for node in by_id:
        if cycle := walk(node):
            return cycle
    return []
