"""The English spec keeps every id of the Korean spec, chapter by chapter (#6).

The texts here are small made-up chapters, not the spec: what is checked is
the comparison, and the spec itself is compared in the last test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from spec_translation import compare, main

KOREAN = """\
# 명세

## 3. 공개 API

### 3.1 import 표면 [R-01, R-09]

표면은 E13을 낸다.
"""


def test_a_chapter_that_keeps_every_id_has_no_difference() -> None:
    english = """\
# Spec

## 3. Public API

### 3.1 The import surface [R-01, R-09]

The surface raises E13.
"""
    assert compare(KOREAN, english) == []


def test_a_citation_dropped_in_translation_is_a_difference() -> None:
    english = """\
# Spec

## 3. Public API

### 3.1 The import surface [R-01]

The surface raises E13.
"""
    assert compare(KOREAN, english) == ["chapter 3: R-09 appears 1 time(s) in Korean, 0 in English"]


@pytest.mark.parametrize(
    "token",
    [
        "G-42",  # golden
        "P-CHUNK",  # property test
        "V31-LS-05",
        "E9",  # error code
        "T0.13a",  # ticket
        "11.4.4",  # citation of a section
        "2026-10-28",  # dated decision
        "D6",  # short citations, `[D6, C10, R-48]`
        "M3a",  # milestone
        "P1",  # performance budget
        "L1-c",  # lowercase part, `L1-a`…`L2-e`
        "P2-small",
    ],
)
def test_each_kind_of_id_dropped_in_translation_is_a_difference(token: str) -> None:
    korean = f"## 3. 공개 [{token}]에서 {token}은\n"
    english = f"## 3. Public [{token}]\n"
    assert compare(korean, english) == [
        f"chapter 3: {token} appears 2 time(s) in Korean, 1 in English"
    ]


def test_a_heading_inside_a_code_block_does_not_start_a_chapter() -> None:
    korean = """\
## 1. 범위 [R-01]

## 9. 순서

```markdown
## 1. 견본 파일 [R-50]
```
"""
    english = "## 1. Scope [R-01]\n"
    assert compare(korean, english) == []


def test_appendices_the_header_and_unnumbered_chapters_are_compared() -> None:
    korean = """\
# 명세 (2026-10-28)

## 목차

5.3.3a

## 부록 A. 충돌 [RV-C03]

## 부록 I. 변경 [R4F-01]

## 갱신 기록

V31-05
"""
    english = """\
# Spec (2026-10-28)

## Contents

5.3.3a

## Appendix A. Conflicts

## Appendix I. Changes [R4F-01]

## Revision history
"""
    assert compare(korean, english) == [
        "appendix A: RV-C03 appears 1 time(s) in Korean, 0 in English",
        "the chapter after appendix I: V31-05 appears 1 time(s) in Korean, 0 in English",
    ]


def test_a_chapter_the_korean_text_does_not_have_is_a_difference() -> None:
    english = "## 13. Not in the spec\n"
    assert compare(KOREAN, english) == ["chapter 13: the Korean text has no such chapter"]


def test_a_chapter_not_yet_translated_is_a_difference_only_when_complete() -> None:
    english = "# Spec\n"
    assert compare(KOREAN, english) == []
    assert compare(KOREAN, english, complete=True) == [
        "chapter 3: the English text has no such chapter"
    ]


def test_a_chapter_written_twice_is_a_difference() -> None:
    english = "## 3. Public API [R-01, R-09]\n\n## 3. Again\n\nE13\n"
    assert compare(KOREAN, english) == ["chapter 3: appears 2 times in the English text"]


def arguments_for(folder: Path, korean: str, english: str) -> list[str]:
    """Write the two texts to files and return the command's arguments for them."""
    (folder / "ko.md").write_text(korean, encoding="utf-8")
    (folder / "en.md").write_text(english, encoding="utf-8")
    return [str(folder / "ko.md"), str(folder / "en.md")]


def test_the_command_exits_0_and_says_what_it_compared_when_the_ids_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    english = "# Spec\n\n## 3. API\n\n### 3.1 [R-01, R-09] E13\n"
    assert main(arguments_for(tmp_path, KOREAN, english)) == 0
    assert capsys.readouterr().out == "No difference in the 2 of 2 chapters English has.\n"


def test_the_command_exits_1_and_prints_each_difference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(arguments_for(tmp_path, KOREAN, "## 3. API\n\n### 3.1 [R-01] E13\n")) == 1
    assert capsys.readouterr().out == (
        "chapter 3: R-09 appears 1 time(s) in Korean, 0 in English\n1 difference(s).\n"
    )


SPEC = Path(__file__).resolve().parents[2] / "docs" / "spec"


def spec_arguments() -> list[str] | None:
    """The command's arguments for the stage the translation is at, or None before it starts.

    While it is made, the Korean text is canonical at the spec's path and the
    English grows beside it; the last pull request of #6 swaps the two, and
    from then on every chapter must be there.
    """
    canonical = str(SPEC / "engine-spec-v3.4.md")
    if (SPEC / "engine-spec-v3.4.ko.md").exists():
        return [str(SPEC / "engine-spec-v3.4.ko.md"), canonical, "--complete"]
    if (SPEC / "engine-spec-v3.4.en.md").exists():
        return [canonical, str(SPEC / "engine-spec-v3.4.en.md")]
    return None


def test_the_english_spec_keeps_every_id_of_the_korean_spec(
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = spec_arguments()
    if arguments is None:
        pytest.skip("no English translation of the spec yet (#6)")
    assert main(arguments) == 0, capsys.readouterr().out
