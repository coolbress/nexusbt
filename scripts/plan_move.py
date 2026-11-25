"""Move spec chapter 10 (the plan) out of one spec edition into its plan document (#767).

    python3 scripts/plan_move.py docs/spec/engine-spec-v3.4.md docs/plan/plan.md
    python3 scripts/plan_move.py docs/spec/engine-spec-v3.4.ko.md docs/plan/plan.ko.md

Run at the base commit of the pull request, on a spec that still holds chapter 10. It writes
the plan document as chapter 10's lines exactly as they are (heading levels kept), and rewrites
the spec with that span replaced by the chapter's heading, a blank line and one pointer
paragraph. `scripts/check_plan_move.py` proves the result. One-off for #767; it is deleted
when #764 closes.
"""

from __future__ import annotations

import sys
from pathlib import Path

POINTER = {
    "en": "The milestone table (10.0), the engine tickets (10.1) and the note on the"
    " producer-side tickets (10.2) are in the plan document, [docs/plan/{name}](../plan/{name})."
    " This chapter keeps its number so that references to 10.0, 10.1 and 10.2 still find"
    " where they are kept.",
    "ko": "마일스톤 표(10.0), 엔진 티켓(10.1), 생산자 쪽 티켓 안내(10.2)는 계획 문서"
    " [docs/plan/{name}](../plan/{name})에 있다. 10.0, 10.1, 10.2를 가리키는 참조가 그 자리를"
    " 찾을 수 있도록 이 장은 번호를 그대로 둔다.",
}


def chapter_10(lines: list[str]) -> tuple[int, int]:
    """Chapter 10's first line and the end of its text: the `## 10. ` heading (outside code
    blocks) up to its last non-blank line before the `---` that precedes the next `## `."""
    heads, code = [], False
    for i, line in enumerate(lines):
        code ^= line.startswith("```")
        if not code and line.startswith("## "):
            heads.append(i)
    starts = [i for i in heads if lines[i].startswith("## 10. ")]
    if len(starts) != 1:
        raise SystemExit(f"expected one '## 10. ' heading, found {len(starts)}")
    start = starts[0]
    end = next(i for i in heads if i > start)
    while lines[end - 1].strip() in ("", "---"):
        end -= 1
    return start, end


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    spec, plan = Path(argv[0]), Path(argv[1])
    lines = spec.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = chapter_10(lines)
    pointer = POINTER["ko" if spec.name.endswith(".ko.md") else "en"].format(name=plan.name)
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("".join(lines[start:end]), encoding="utf-8")
    new = [*lines[:start], lines[start], "\n", pointer + "\n", *lines[end:]]
    spec.write_text("".join(new), encoding="utf-8")
    print(f"{spec}: lines {start + 1}..{end} ({end - start}) -> {plan}; {len(new)} lines left")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
