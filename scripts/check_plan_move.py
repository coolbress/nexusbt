"""Prove that spec chapter 10 moved to its plan document and nothing else changed (#767).

    git show BASE:docs/spec/engine-spec-v3.4.md > base.md
    python3 scripts/check_plan_move.py base.md docs/spec/engine-spec-v3.4.md docs/plan/plan.md

(and the same for the `.ko.md` edition and `docs/plan/plan.ko.md`), where BASE is the commit
`scripts/plan_move.py` ran on. It proves, character for character:

1. the new spec is the base spec with only chapter 10's span replaced by the same heading
   line, a blank line and one paragraph (one line of text, not a heading, table or list);
2. the plan document is that span.

It finds the span on its own, without `plan_move.py`. Exit 0 when both hold, otherwise 1 with
what differs. One-off for #767; it is deleted when #764 closes.
"""

from __future__ import annotations

import sys
from pathlib import Path


def span(lines: list[str]) -> tuple[int, int]:
    """From the `## 10. ` line to the last non-blank line before the `---` line that ends it."""
    starts = [i for i, line in enumerate(lines) if line.startswith("## 10. ")]
    if len(starts) != 1:
        raise SystemExit(f"the base has {len(starts)} '## 10. ' lines, not one")
    start = starts[0]
    nxt = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## 11. "))
    rule = max(i for i in range(start, nxt) if lines[i] == "---\n")
    if any(line.strip() for line in lines[rule + 1 : nxt]):
        raise SystemExit("text between chapter 10's closing '---' and chapter 11")
    end = rule
    while not lines[end - 1].strip():
        end -= 1
    return start, end


def problems(base: list[str], new: list[str], plan: list[str]) -> list[str]:
    start, end = span(base)
    tail = len(base) - end
    found = []
    if new[:start] != base[:start]:
        found.append("the text before chapter 10 differs")
    if len(new) < start + tail or new[len(new) - tail :] != base[end:]:
        found.append("the text after chapter 10 differs")
    middle = new[start : len(new) - tail]
    shape = len(middle) == 3 and middle[0] == base[start] and middle[1] == "\n"
    if not shape or not middle[2].strip() or middle[2].startswith(("#", "|", "-", "`")):
        found.append(f"chapter 10 is not its heading and one paragraph: {middle[:4]!r}")
    if plan != base[start:end]:
        found.append("the plan document is not chapter 10's span")
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit(__doc__)
    base, new, plan = (Path(a).read_text(encoding="utf-8").splitlines(keepends=True) for a in argv)
    if found := problems(base, new, plan):
        print("\n".join(f"FAIL: {line}" for line in found))
        return 1
    start, end = span(base)
    chars = sum(map(len, base[start:end]))
    print(f"OK: {argv[1]} = {argv[0]} with lines {start + 1}..{end} ({end - start} lines,")
    print(f"    {chars} characters) replaced by heading + 1 paragraph; {argv[2]} = those lines")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
