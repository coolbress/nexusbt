"""Take the review-round tags and version marks out of the spec and the plan, and prove it (#770).

    git show BASE:docs/spec/engine-spec-v3.4.md > spec.md     (likewise the other three)
    python3 scripts/strip_marks.py spec.md docs/spec/engine-spec-v3.4.md --write
    python3 scripts/strip_marks.py spec.md docs/spec/engine-spec-v3.4.md

The first argument is the base, the second the new document; which of the four documents it is
comes from the second's name. `--write` makes the new document: the places changed by hand
(`HAND`) first, then the rules. Without it the program proves three things and exits 0 or 1:

1. the new document is what `--write` makes of the base;
2. once every removable mark is erased from both (`erase`), the base with the hand changes
   applied and the new document are the same text, and appendix A is unchanged;
3. no tag of the ten families is left outside the kept set: an id naming a row of chapter 12's
   tables (or a range covering one), appendix A, and the places `KEPT` lists.

It prints the counts, each hand change old and new, and the tags left in appendix A.

The rules, applied outside code spans and appendix A (a tag is removable when it is not kept):
1. a bracket of removable tags goes with the space before it (after it at a line's start);
   inside a parenthesis it takes the parenthesis, before a closing one the comma before it;
2. a bracket with other items loses its removable tags and one separator each;
3. so do a parenthesis and a table cell whose items are lone tags; a cell may end empty;
4. inside fenced code only rules 1 and 2 apply;
5. `*(vX: ...)*`, `(vX: ...)` and `(vX)` go with the space before them; a note holding a date or
   an issue number stays and loses its `vX: ` only;
6. a clause's leading `vX: `, `Added in vX: ` or `vX 추가: ` goes, its content stays;
7. the ticket marks `**[vX]**` and `**[new]**` go with the space before them;
8. a note right after a test name loses its leading `vX `: `(v3.2 two properties)`.
vX is v2, v3, v3.1 ... v3.4 (v1 is the product release). One-off for #770; deleted when #764
closes.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

FAM = r"(?:V31|R3|R4F|R4G|R4H|R4|R5|R6|R7|RV)"
TAG = re.compile(
    rf"(?<![\w-]){FAM}(?:-[A-Za-z0-9]+)+(?:~(?:[A-Za-z0-9]+-)*[A-Za-z0-9]+)?(?![A-Za-z0-9_-])"
)
VER = r"v(?:2|3(?:\.[1-4])?)"
NOTE = re.compile(rf" ?\*\({VER}: [^\n]*?\)\*| ?\({VER}: (?:[^()\n]|\([^()\n]*\))*\)")
DATED = re.compile(r"#\d+|\d{4}-\d{2}-\d{2}")
MARK = re.compile(rf" ?\*\*\[(?:{VER}|new)\]\*\*| ?\({VER}\)")
LEAD = re.compile(
    rf"(?:(?<=^)|(?<=^- )|(?<=^> )|(?<=[.;|] )|(?<=\*\*))(?:Added in )?{VER}(?: 추가)?: ", re.M
)
AFTER_TEST = re.compile(rf"(`[^`]*test_[^`]*` ?\(){VER} ")
SEP = re.compile(r"\s*(?:,|;|→)\s*")
SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
SPEC = "docs/spec/engine-spec-v3.4.md"  # chapter 12, for the plan
ZONE_A = (re.compile(r"^## (?:Appendix|부록) A\."), re.compile(r"^## (?:Appendix|부록) B\."))

#: Places changed by hand, per document: (text of the base, its replacement), each unique.
HAND: dict[str, list[tuple[str, str]]] = {
    "spec.en": [
        ("(the R3-06 inference rule", "(the inference rule"),
        (" (after the fourth review round, v3.4)", " (after the fourth review round)"),
        ("(before round 4, v3.3)", "(before round 4)"),
        ("[R7-10: ", "["),
        ("OI-07, RV-C08 (leaves", "OI-07 (leaves"),
        ("[R7-12: ", "["),
        ("5.6.1 R7-01 excluded", "5.6.1 excluded"),
        (
            ", (v3.1 kinds [V31-01, V31-04, V31-18, V31-19, V31-LS-04, V31-LS-05]; v3.2 kinds "
            "[R3-06, R3-09, R3-21, R3-25])",
            "",
        ),
        ("made it negative [R3-09])", "made it negative)"),
        (" [R4F-07 number fix, checked by prototype]", ""),
        ("[R7-09: ", "["),
        ("The V31-03 cap", "The cap"),
        (" (v3.2 comparison coordinates R3-02, KR rounding R3-27)", ""),
        (" (v3.2 key fix R3-04)", ""),
        (" (v3.2 fixed salt R3-12)", ""),
        (" (v3.3 opened the reservation)", ""),
        (
            " (v3.3 opened `risk.group_caps`, `splits`, `time_stop` and `labels.triple_barrier` "
            "[R4-28])",
            "",
        ),
        ("HTML sections added in v3.1: ", "HTML sections: "),
        ("[the seam is v3.2; the P11", "[the P11"),
        (
            "how each version was made were removed",
            "how each version was made, the review-round tags and the version notes were removed",
        ),
    ],
    "spec.ko": [
        ("(v3.2의 R3-06 추론 규칙", "(v3.2의 추론 규칙"),
        ("(4라운드 검토 뒤, v3.4)", "(4라운드 검토 뒤)"),
        ("(라운드 4 전, v3.3)", "(라운드 4 전)"),
        ("[R7-10: ", "["),
        ("OI-07, RV-C08 (", "OI-07 ("),
        ("[R7-12: ", "["),
        ("(5.6.1 R7-01이 종목을", "(5.6.1이 종목을"),
        (
            ", (v3.1 종류 [V31-01, V31-04, V31-18, V31-19, V31-LS-04, V31-LS-05]; v3.2 종류 "
            "[R3-06, R3-09, R3-21, R3-25])",
            "",
        ),
        ("음수 현금이 됨 [R3-09])", "음수 현금이 됨)"),
        (" [R4F-07 숫자 고침, 시제품 확인]", ""),
        ("[R7-09: ", "["),
        ("V31-03 그날 거래량 상한은", "그날 거래량 상한은"),
        (" (v3.2 비교 좌표 R3-02, KR 끝수 R3-27)", ""),
        (" (v3.2 열쇠 고침 R3-04)", ""),
        (" (v3.2 고정 소금 R3-12)", ""),
        ("(v3.3에서 예약을 엶)", ""),
        (
            " (v3.3에서 `risk.group_caps`·`splits`·`time_stop`·`labels.triple_barrier`는 열림 "
            "[R4-28])",
            "",
        ),
        ("v3.1 HTML 칸 추가: ", "HTML 칸: "),
        ("[이음새는 v3.2, P11", "[P11"),
        (
            "만들었는지 적은 머리말 문단은 뺐다",
            "만들었는지 적은 머리말 문단, 검토 딱지와 판 메모는 뺐다",
        ),
    ],
    "plan.en": [
        (" (appendix E)", ""),
        (
            " Tickets changed from v1 carry *(v2: …)*, tickets changed in v3 carry *(v3: …)*, new "
            "tickets in v2 carry **[new]**, and new·split tickets in v3 carry **[v3]**.",
            "",
        ),
        (
            " New·split tickets of v3.1 carry **[v3.1]**, changed ones *(v3.1: …)*. New·split"
            " tickets of v3.2 carry **[v3.2]**, changed ones *(v3.2: …)*. New·split tickets of v3.3"
            " carry **[v3.3]**, changed ones *(v3.3: …)*.",
            "",
        ),
        (" (v3.2 numbering [R3-23])", ""),
        (" **[v3: v2 T6.1 moved to M1]**", ""),
        ("[R6-04] **[v3.4 final]**", "[R6-04]"),
        ("forced reduction`** **[v3.4 final]**", "forced reduction`**"),
        ("config show`** **[v3.4 final]**", "config show`**"),
        ("result tables)`** **[v3.4 R5]**", "result tables)`**"),
        ("leak guard`** **[v3.4 R5]**", "leak guard`**"),
        ("(default policy)`** **[v3.4 R7]**", "(default policy)`**"),
        (" (RV-D2 measurement)", ""),
        ("*(v3 user decision 2026-10-28:", "*(user decision 2026-10-28:"),
    ],
    "plan.ko": [
        ("(부록 E)", ""),
        (
            " v1에서 바뀐 티켓은 *(v2: …)*, v3에서 바뀐 티켓은 *(v3: …)*, "
            "v2의 새 티켓은 **[new]**, v3의 새 티켓·나눈 티켓은 **[v3]** 를 붙였다.",
            "",
        ),
        (
            " v3.1의 새 티켓·나눈 티켓은 **[v3.1]**, 바뀐 티켓은 *(v3.1: …)*. v3.2의 새 티켓·나눈 "
            "티켓은 **[v3.2]**, 바뀐 티켓은 *(v3.2: …)*. v3.3의 새 티켓·나눈 티켓은 **[v3.3]**, "
            "바뀐 티켓은 *(v3.3: …)*.",
            "",
        ),
        ("(v3.2 번호 [R3-23])", ""),
        (" **[v3: v2 T6.1을 M1로]**", ""),
        ("[R6-04] **[v3.4 최종]**", "[R6-04]"),
        ("forced reduction`** **[v3.4 최종]**", "forced reduction`**"),
        ("config show`** **[v3.4 최종]**", "config show`**"),
        ("result tables)`** **[v3.4 R5]**", "result tables)`**"),
        ("leak guard`** **[v3.4 R5]**", "leak guard`**"),
        ("(default policy)`** **[v3.4 R7]**", "(default policy)`**"),
        ("(RV-D2 측정)", ""),
        ("*(v3 사용자 결정 2026-10-28:", "*(사용자 결정 2026-10-28:"),
    ],
}
#: Places where a removable tag stays, by a snippet of the line that holds it.
KEPT: dict[str, list[str]] = {
    "spec.en": ["V31-47"],
    "spec.ko": ["V31-47"],
    "plan.en": [],
    "plan.ko": [],
}
#: Lines no rule touches, by a snippet: T0.12 lists the requirement map's ids as data.
PROTECT = {
    "spec.en": [],
    "spec.ko": [],
    "plan.en": ["V31-LS-01~V31-LS-11; appendix B.5"],
    "plan.ko": ["V31-LS-01~V31-LS-11"],
}


def at(text: str, letter: str) -> int:
    """Where the heading of appendix `letter` starts, or -1."""
    m = re.search(rf"\n## (?:Appendix|부록) {letter}\.", text)
    return m.start() if m else -1


def live_ids(spec: str) -> set[str]:
    """The ids that open a table row of chapter 12 (each a row's name)."""
    part = spec[spec.index("\n## 12. ") : at(spec, "A")]
    return set(re.findall(rf"^\| ({FAM}(?:-[A-Za-z0-9]+)+)(?=[ |(])", part, re.M))


class Marks:
    def __init__(self, live: set[str], keep: tuple[str, ...] = ()) -> None:
        self.live, self.keep, self.count = live, keep, Counter[str]()

    def kept(self, tag: str) -> bool:
        if tag in self.live:
            return True
        m = re.fullmatch(r"(.*?)(\d+)~[A-Za-z-]*?(\d+)", tag)  # a range, "R3-29~37"
        if m is None:
            return False
        return any(f"{m[1]}{n:0{len(m[2])}d}" in self.live for n in range(int(m[2]), int(m[3]) + 1))

    def removable(self, text: str, versions: bool = False) -> bool:
        if versions and any(re.fullmatch(VER, p) for p in SEP.split(text)):
            return True
        return any(not self.kept(t) for t in TAG.findall(text))

    def items(self, inner: str, versions: bool = False) -> str | None:
        """The list's new inside ('' when nothing stays), or None to leave it as it is."""
        parts, seps = SEP.split(inner), SEP.findall(inner)
        out: list[str] = []
        gone = prev = False
        for i, p in enumerate(parts):
            if versions and re.fullmatch(VER, p):
                gone, prev = True, False
                self.count["version in a bracket"] += 1
                continue
            if (TAG.fullmatch(p) and not self.kept(p)) or (
                prev and re.fullmatch(r"[A-Z]?\d+[a-z]?", p)
            ):
                gone = prev = True
                self.count["tag"] += len(TAG.findall(p))
                continue
            if self.removable(p):
                return None
            out += [seps[i - 1], p] if out else [p]
            prev = False
        return "".join(out) if gone else None

    def brackets(self, line: str, code: bool) -> str:
        spans = [m.span() for m in SPAN.finditer(line)] if not code else []
        out, pos = [], 0
        for m in re.finditer(r"\[([^\[\]\n]*)\]", line):
            a, b = m.span()
            bold = line[a - 2 : a] == "**"
            if any(x <= a < y for x, y in spans) or bold or not self.removable(m[1], True):
                continue
            new = self.items(m[1], versions=True)
            if new is None:
                continue
            if new:
                out.append(line[pos:a] + f"[{new}]")
            else:
                if line[a - 1 : a] == "(" and line[b : b + 1] == ")":
                    a, b = a - 1, b + 1
                if line[a - 1 : a] == " ":
                    a -= 1 + (line[a - 2 : a - 1] in ",;" and line[b : b + 1] in (")", ""))
                elif line[b : b + 1] == " " and re.fullmatch(r"[\s>|*+#-]*(?:\d+\.\s*)?", line[:a]):
                    b += 1
                out.append(line[pos:a])
            self.count["bracket"] += 1
            pos = b
        return "".join(out) + line[pos:]

    def lists(self, line: str) -> str:
        spans = [m.span() for m in SPAN.finditer(line)]

        def paren(m: re.Match[str]) -> str:
            if any(x <= m.start() < y for x, y in spans) or not self.removable(m[1]):
                return m[0]
            new = None if re.match(VER, m[1]) else self.items(m[1])
            if new is None:
                return m[0]
            self.count["parenthesis"] += 1
            return f"({new})" if new else "\x00"

        line = re.sub(r" ?\x00", "", re.sub(r"\(([^()\n]*)\)", paren, line))
        if not line.startswith("|"):
            return line
        cells = re.split(r"\|(?=(?:[^`]*`[^`]*`)*[^`]*$)", line)
        for i, cell in enumerate(cells):
            new = self.items(cell.strip()) if self.removable(cell) else None
            if new is not None:
                self.count["table cell"] += 1
                cells[i] = f" {new} " if new else " "
        return "|".join(cells)

    def notes(self, line: str) -> str:
        def note(m: re.Match[str]) -> str:
            self.count["version note"] += 1
            if DATED.search(m[0]):
                return re.sub(rf"\({VER}: ", "(", m[0], count=1)
            self.count["tag"] += sum(not self.kept(t) for t in TAG.findall(m[0]))
            return ""

        line = NOTE.sub(note, line)
        for name, rx, new in (
            ("mark", MARK, ""),
            ("lead", LEAD, ""),
            ("after test", AFTER_TEST, r"\1"),
        ):
            line, k = rx.subn(new, line)
            self.count[name] += k
        line, k = re.subn(rf"(\d{{4}}-\d{{2}}-\d{{2}} \(){VER}(?:, )", r"\1", line, count=1)
        self.count["lead"] += k
        return line

    def run(self, text: str) -> str:
        out, fenced, zone = [], False, False
        for line in text.split("\n"):
            zone = (zone or bool(ZONE_A[0].match(line))) and not ZONE_A[1].match(line)
            if line.startswith("```"):
                fenced = not fenced
            elif fenced:
                line = self.brackets(line, code=True)
            elif not zone and not any(k in line for k in self.keep):
                line = self.notes(self.lists(self.brackets(line, code=False)))
            out.append(line)
        return "\n".join(out)


def which(path: str) -> str:
    return ("plan" if "plan" in Path(path).name else "spec") + (".ko" if ".ko." in path else ".en")


def hand(text: str, doc: str) -> str:
    for old, new in HAND[doc]:
        if text.count(old) != 1:
            raise SystemExit(f"hand change not found once: {old!r}")
        text = text.replace(old, new)
    return text


def erase(text: str, live: set[str]) -> str:
    """Every removable mark out, then the punctuation and spaces the rules may touch."""
    m = Marks(live)
    text = NOTE.sub(lambda x: re.sub(rf"\({VER}: ", "(", x[0]) if DATED.search(x[0]) else "", text)
    run = re.compile(f"({TAG.pattern})" + r"(?:,\s*[A-Z]?\d+[a-z]?(?![\w.-]))*")  # "RV-I03, Q03"
    text = run.sub(lambda x: x[0] if m.kept(x[1]) else "", text)
    text = re.sub(r" ?\[[\s,;→]*\]", "", text)
    for rx in (MARK, LEAD, re.compile(rf"(?<=\d \(){VER}, ")):
        text = rx.sub("", text)
    text = AFTER_TEST.sub(r"\1", text)
    text = re.sub(rf" ?\[{VER}\]|(?<=\[){VER}, ", "", text)
    return re.sub(r"[\s,;:()\[\]*|→]+", "", text)


def zone(text: str) -> str:
    """Appendix A, the record no rule touches."""
    a = at(text, "A")
    return text[a : at(text, "B")] if a >= 0 else ""


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3) or argv[2:] not in ([], ["--write"]):
        raise SystemExit(__doc__)
    doc = which(argv[1])
    base = Path(argv[0]).read_text(encoding="utf-8")
    spec = base if doc.startswith("spec") else Path(SPEC).read_text(encoding="utf-8")
    marks = Marks(live_ids(spec), tuple(PROTECT[doc]))
    made = marks.run(hand(base, doc))
    if argv[2:]:
        Path(argv[1]).write_text(made, encoding="utf-8")
        return 0
    new = Path(argv[1]).read_text(encoding="utf-8")
    found = []
    if new != made:
        found.append("the document is not what --write makes of the base")
    if erase(hand(base, doc), marks.live) != erase(new, marks.live):
        found.append("with the marks erased from both, the text differs")
    if zone(base) != zone(new):
        found.append("appendix A changed")
    rest = re.sub(r"\n## (?:Appendix|부록) A\.[\s\S]*?(?=\n## (?:Appendix|부록) B\.)", "\n", new)
    for line in rest.split("\n"):
        left = [t for t in TAG.findall(line) if not marks.kept(t)]
        if left and not any(k in line for k in KEPT[doc] + PROTECT[doc]):
            found.append(f"tag left {left}: {line[:120]}")
    print(f"{doc}: {dict(marks.count)}; ids kept as row names: {len(marks.live)}")
    print(
        f"  tags left in appendix A: {len(TAG.findall(zone(new)))}; hand changes: {len(HAND[doc])}"
    )
    for old, rep in HAND[doc]:
        print(f"  hand: {old!r}\n     -> {rep!r}")
    print("\n".join(f"FAIL: {f}" for f in found) or "OK")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
