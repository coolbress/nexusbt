"""Cut the spec's hand-written history in whole blocks, and prove nothing else changed (#770).

    git show BASE:docs/spec/engine-spec-v3.4.md > base.md
    python3 scripts/history_cut.py base.md docs/spec/engine-spec-v3.4.md BASE --write
    python3 scripts/history_cut.py base.md docs/spec/engine-spec-v3.4.md BASE

(and the same for the `.ko.md` edition), where BASE is the commit that last holds the text.
`--write` makes the new edition from the base. Without it the program proves, line for line,
that the new edition is the base with only these spans removed or replaced, and prints the
first and last line of each, and the replaced lines in full:

1. the header's Status line, without the history of each version and "No code.";
2. the header's Inputs line, keeping only "the three-reviewer consensus", "the blueprint",
   "TDS" and "the design";
3. the tracing legend's lines for the removed tag families, replaced by one line naming BASE;
4. the contents lines of appendices D to I;
5. from the blank line before the rule above appendix D to the end of the file.

Exit 0 when that holds, otherwise 1 with what differs. One-off for #770; it is deleted when
#764 closes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: The first words of the lines each span is found by, English and Korean.
STATUS = ("> **Status.**", "> **상태.**")
INPUTS = ("> **Inputs.**", "> **입력.**")
LEGEND = ("> - `[RV-C01]`", "> - `[R4F-NN]`")
CONTENTS = ("- Appendix D.", "- Appendix I.", "- 부록 D.", "- 부록 I.")
TAIL = ("## Appendix D.", "## 부록 D.")

#: What goes out of the Status line, in this order: (pattern, replacement).
STATUS_CUTS = [
    (r"(\*\*v3\.4\*\*) = v3\.3 \+ .*? (No code|코드 없음)", r"\1. \2"),
    (r" (No code|코드 없음)\. ", " "),
    (r"implementation\*\*; v3\.3 \(`sources/.*? remain only for comparison\.", "implementation**."),
    (r"이 문서\*\*이고 v3\.3\(`sources/.*?비교용으로만 남는다\.", "이 문서**다."),
    (r"the same in v1\.4 — v1\.2 added .*?\(TDS chapter 18\)\) \[R6-01\]", "the same in v1.4)"),
    (r"v1\.4에서도 같다 — v1\.2는 .*?\(TDS 18장\)\) \[R6-01\]이", "v1.4에서도 같다)가"),
]
#: The Inputs items that stay: (the item, where to end it).
INPUT_ITEMS = [
    (r"`review/consensus\.md` ?\((?:the three-reviewer consensus|3자 검토 합의)", ")"),
    (r"`engine-blueprint-by-aspect\.md` ?\([^)]*\)", ""),
    (r"`engine-data-standard-v1\.4\.md` ?\([^)]*?(?:private appendix|비공개 부록)", ")"),
    (r"`engine-design-2026-10-27\.md` ?\([^)]*\)", ""),
]
LEGEND_LINE = {
    "en": "> - Appendices D to I (the change summaries), the revision history and the header "
    "paragraphs on how each version was made were removed; commit `{c}` holds them "
    "(`git show {c}:docs/spec/engine-spec-v3.4.md`).\n",
    "ko": "> - 부록 D~I(변경 요약), 갱신 기록, 각 판을 어떻게 만들었는지 적은 머리말 문단은 "
    "뺐다. 커밋 `{c}`에 있다(`git show {c}:docs/spec/engine-spec-v3.4.ko.md`).\n",
}


def find(lines: list[str], starts: tuple[str, ...]) -> list[int]:
    return [i for i, line in enumerate(lines) if line.startswith(starts)]


def one(lines: list[str], starts: tuple[str, ...]) -> int:
    found = find(lines, starts)
    if len(found) != 1:
        raise SystemExit(f"{len(found)} lines start with {starts}, not one")
    return found[0]


def spans(base: list[str]) -> list[tuple[str, int, int, int]]:
    """(name, first line, end, how many lines take its place), in order of the file."""
    legend = find(base, LEGEND)
    contents = find(base, CONTENTS)
    if len(legend) != 2 or len(contents) != 2:
        raise SystemExit(f"legend lines {legend}, contents lines {contents}: not two each")
    heading = one(base, TAIL)
    rule = max(i for i in range(heading) if base[i] == "---\n")
    if any(line.strip() for line in base[rule + 1 : heading]):
        raise SystemExit("text between the rule and the heading of appendix D")
    tail = rule
    while not base[tail - 1].strip():
        tail -= 1
    status, inputs = one(base, STATUS), one(base, INPUTS)
    found = [
        ("Status", status, status + 1, 1),
        ("Inputs", inputs, inputs + 1, 1),
        ("legend", legend[0], legend[1] + 1, 1),
        ("contents", contents[0], contents[1] + 1, 0),
        ("appendices D to I and the revision history", tail, len(base), 0),
    ]
    if [s[1] for s in found] != sorted(s[1] for s in found):
        raise SystemExit("the spans are not in the expected order")
    return found


def new_status(line: str) -> str:
    for pattern, replacement in STATUS_CUTS:
        line = re.sub(pattern, replacement, line, count=1)
    return line


def new_inputs(line: str) -> str:
    items = []
    for pattern, end in INPUT_ITEMS:
        m = re.search(pattern, line)
        if not m:
            raise SystemExit(f"no Inputs item {pattern}")
        items.append(m.group(0) + end)
    return line[: line.index("**", 4) + 2] + " " + ", ".join(items) + ".\n"


def cut(base: list[str], commit: str, lang: str) -> list[str]:
    new = {
        "Status": [new_status(base[one(base, STATUS)])],
        "Inputs": [new_inputs(base[one(base, INPUTS)])],
        "legend": [LEGEND_LINE[lang].format(c=commit)],
    }
    out, pos = [], 0
    for name, start, end, _ in spans(base):
        out += base[pos:start] + new.get(name, [])
        pos = end
    return out + base[pos:]


def check(base: list[str], new: list[str], commit: str, lang: str) -> list[str]:
    """Each line outside the spans is unchanged, each replaced line is what `cut` makes."""
    found, pos, at = [], 0, 0
    for name, start, end, takes in spans(base):
        keep = base[pos:start]
        if new[at : at + len(keep)] != keep:
            found.append(f"a line before the {name} span differs")
        at += len(keep)
        print(f"{name}: lines {start + 1}..{end} ({end - start} lines) -> {takes} line(s)")
        print(f"  first: {base[start].rstrip()[:100]}\n  last:  {base[end - 1].rstrip()[:100]}")
        for line in new[at : at + takes]:
            print(f"  new:   {line.rstrip()}")
        at += takes
        pos = end
    if new[at:] != base[pos:]:
        found.append("the lines after the last span differ")
    if not found and new != cut(base, commit, lang):
        found.append("a replaced line is not what the cut makes of the base (printed above)")
    return found


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4) or argv[3:] not in ([], ["--write"]):
        raise SystemExit(__doc__)
    base = Path(argv[0]).read_text(encoding="utf-8").splitlines(keepends=True)
    lang = "ko" if argv[1].endswith(".ko.md") else "en"
    if argv[3:]:
        Path(argv[1]).write_text("".join(cut(base, argv[2], lang)), encoding="utf-8")
        return 0
    new = Path(argv[1]).read_text(encoding="utf-8").splitlines(keepends=True)
    if found := check(base, new, argv[2], lang):
        print("\n".join(f"FAIL: {line}" for line in found))
        return 1
    print(f"OK: {argv[1]} = {argv[0]} with only the spans above removed or replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
