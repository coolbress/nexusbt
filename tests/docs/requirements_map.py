"""Read the ids of the spec's appendix B and the rows of `docs/requirements.md` (T0.12).

Appendix B names an item by its number alone inside each table (`D1` in B.3, `01` in B.5);
the map prefixes it with the table's name so that the same number in two tables stays apart.
"""

from __future__ import annotations

import re

#: What the map puts before the number of each appendix B table; B.1 and B.2 name their ids in full.
PREFIX = {"B.3": "TDS-", "B.4": "RV-", "B.5": "V31-", "B.6": "R3-", "B.7": "R4-"}
SUBHEADING = re.compile(r"^### (B\.\d) ")

#: `RV-Q08~Q11`, `R3-29~37`, `V31-LS-01~LS-11`: the digits before and after `~`,
#: with the letters between them repeating the end of the head or absent.
RANGE = re.compile(r"(?P<head>.*?)(?P<a>\d+)~(?P<mid>[A-Za-z-]*)(?P<b>\d+)$")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def tables(text: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """Each Markdown table of the text as (the `##`/`###` heading above it, header, rows)."""
    found: list[tuple[str, list[str], list[list[str]]]] = []
    heading = ""
    previous = ""
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line
        elif line.startswith("|"):
            if not previous.startswith("|"):
                found.append((heading, cells(line), []))
            elif set("".join(cells(line))) - set("-:"):
                found[-1][2].append(cells(line))
        previous = line
    return found


def appendix_b_ids(spec: str) -> list[str]:
    """The id of every row of appendix B, with its table's name in front."""
    ids = []
    for heading, _, rows in tables(spec):
        if m := SUBHEADING.match(heading):
            ids += [PREFIX.get(m.group(1), "") + row[0].split()[0] for row in rows]
    return ids


def map_rows(doc: str) -> list[dict[str, str]]:
    """Every row of the map as a dict keyed by its table's header."""
    return [dict(zip(header, row, strict=True)) for _, header, rows in tables(doc) for row in rows]


def expand(ident: str) -> list[str]:
    """The ids a range id covers; an id without `~` covers itself."""
    m = RANGE.match(ident)
    if not m or (m.group("mid") and not m.group("head").endswith(m.group("mid"))):
        return [ident]
    width = len(m.group("a"))
    return [
        f"{m.group('head')}{n:0{width}d}" for n in range(int(m.group("a")), int(m.group("b")) + 1)
    ]


def missing(ids: list[str], wanted: list[str]) -> list[str]:
    """The wanted ids no id covers; an id covers itself, each id of its range, and itself
    without a trailing letter (`RV-C04a` covers `RV-C04`)."""
    covered = set()
    for ident in ids:
        for one in expand(ident):
            covered.add(one)
            covered.add(one.rstrip("abcdefghijklmnopqrstuvwxyz"))
    return [w for w in wanted if w not in covered]
