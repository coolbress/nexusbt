"""Compare the ids of the Korean spec and its English translation, chapter by chapter.

A translation changes the words around an id, never the id (issue #6). For each
chapter the English text has, every id must appear as many times as in the
Korean chapter. Prints one line per difference and exits 1 when there is any.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

#: The ids a translation keeps. ASCII-only boundaries: a Korean particle
#: written straight after an id (`R-01은`) does not make it a different word.
#: The first alternative that matches wins, so a ticket is tried before a
#: short id (`T0.13a`, not `T0`).
ID = re.compile(
    r"\b[A-Z][A-Za-z0-9]*(?:-[A-Z0-9]+)+\b"  # R-01, G-42, V31-LS-05, P-CHUNK, ADR-0019
    r"|\b[A-Z]+\d[A-Z0-9]*(?:-[A-Za-z0-9]+)+\b"  # a lowercase part: L1-c, P2-small
    r"|\bT\d+(?:\.\d+)+[a-z]?\b"  # tickets, T0.13a
    r"|\b[A-Z]\d+[a-z]?\b"  # error codes E9, short citations D6, P1, milestones M3a
    r"|(?<![\w.])\d+(?:\.\d+)+[a-z]?\b"  # sections and citations, 5.3.3a, 11.4.4
    r"|\b\d{4}-\d{2}-\d{2}\b",  # dates of decisions
    re.ASCII,
)

#: A numbered chapter or an appendix, in either language.
NUMBERED = re.compile(r"^## (\d+)\.")
APPENDIX = re.compile(r"^## (?:부록|Appendix) ([A-Z])\.")

HEADER = "the header"


def chapters(text: str) -> list[tuple[str, Counter[str]]]:
    """The name and ids of each chapter, in order.

    A chapter is named by its number or appendix letter, which both languages
    share. One without either (the contents, the revision history) is named
    after the chapter before it, since its title is translated. A `## ` line
    inside a code block quotes a file and starts no chapter.
    """
    name = HEADER
    found = [(name, Counter[str]())]
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and line.startswith("## "):
            numbered, appendix = NUMBERED.match(line), APPENDIX.match(line)
            if numbered:
                name = f"chapter {numbered.group(1)}"
            elif appendix:
                name = f"appendix {appendix.group(1)}"
            else:
                name = f"the chapter after {name}"
            found.append((name, Counter()))
        found[-1][1].update(ID.findall(line))
    return found


def by_name(text: str, language: str) -> tuple[dict[str, Counter[str]], list[str]]:
    """The chapters by name, and a line for each name used more than once."""
    found = chapters(text)
    times = Counter(name for name, _ in found)
    twice = [
        f"{name}: appears {n} times in the {language} text" for name, n in times.items() if n > 1
    ]
    return dict(found), twice


def compare(korean: str, english: str, *, complete: bool = False) -> list[str]:
    """One line per difference, for the chapters English has.

    With `complete`, a Korean chapter the English text lacks is a difference
    too: the translation is finished and canonical.
    """
    ko, ko_twice = by_name(korean, "Korean")
    en, en_twice = by_name(english, "English")
    if ko_twice or en_twice:
        # With a chapter written twice, counting its ids would compare the wrong text.
        return ko_twice + en_twice
    differences = []
    if complete:
        differences += [
            f"{name}: the English text has no such chapter" for name in ko if name not in en
        ]
    for name, english_ids in en.items():
        if name not in ko:
            differences.append(f"{name}: the Korean text has no such chapter")
            continue
        korean_ids = ko[name]
        for token in sorted(korean_ids.keys() | english_ids.keys()):
            if korean_ids[token] != english_ids[token]:
                differences.append(
                    f"{name}: {token} appears {korean_ids[token]} time(s) in Korean, "
                    f"{english_ids[token]} in English"
                )
    return differences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("korean", type=Path, help="the Korean spec")
    parser.add_argument("english", type=Path, help="the English translation")
    parser.add_argument(
        "--complete", action="store_true", help="every Korean chapter must be translated"
    )
    args = parser.parse_args(argv)
    korean = args.korean.read_text(encoding="utf-8")
    english = args.english.read_text(encoding="utf-8")
    differences = compare(korean, english, complete=args.complete)
    for line in differences:
        print(line)
    if differences:
        print(f"{len(differences)} difference(s).")
        return 1
    print(
        f"No difference in the {len(chapters(english))} of {len(chapters(korean))} "
        "chapters English has."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
