"""TDS 4.2: the fields its datasets[] row marks required are the ones M003 checks (#79)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from nexusbt_tds.check import DATASET_REQUIRED, FILE_REQUIRED

DOCS = Path(__file__).resolve().parents[2] / "docs" / "tds"
REQUIRED = r" ?\((?:required|필수)\)"
MARKED = re.compile(r"`([a-z_]+)`" + REQUIRED)


def marked(doc: str) -> tuple[set[str], set[str]]:
    """Required dataset fields and required file fields marked in the 4.2 datasets[] row."""
    text = (DOCS / doc).read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| `datasets[]` |"))
    dataset, _, rest = row.partition("`files[]`")
    files_required = re.match(REQUIRED, rest)
    file_fields = rest.partition("**")[0]  # the files[] list ends before the bold notes
    return (
        set(MARKED.findall(dataset)) | ({"files"} if files_required else set()),
        set(MARKED.findall(file_fields)),
    )


@pytest.mark.parametrize("doc", ["tds-v1.4.md", "tds-v1.4.ko.md"])
def test_tds_table_marks_what_M003_checks(doc: str) -> None:
    assert marked(doc) == (set(DATASET_REQUIRED), set(FILE_REQUIRED))
