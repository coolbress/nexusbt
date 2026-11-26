"""The value tables' manifest checks (TDS 5.28, 8.3; #752's V2a, the owner's decisions of
2026-11-27): M018, an item name outside 5.28's rule; M019, one item in two value tables; M014,
a `params.items` word or shape outside 5.28's table, or an `availability` written for a value
table. All read `tds.json` only: an item is the `item=` part of a listed file's path.

Not judged (the owner, 2026-11-27): an item declared in `params.items` that the dataset lacks,
a `carry` on `symbol_values`, and a row whose instrument belongs to another market than its
`market=` partition.
"""

from __future__ import annotations

import keyword
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from .check import Finding

#: TDS 5.28's three kinds.
VALUE_KINDS = frozenset({"values", "market_values", "symbol_values"})
#: 3.1's column-name rule, starting with a letter so that `nx.Item.<name>` reads it (5.28).
_NAME = re.compile(r"[a-z][a-z0-9_]*")
#: 5.28's declaration words; `carry` may also be a positive whole number N.
KINDS = ("per_share", "share_count")
CARRIES = ("to_end", "none", "next_listing")


def check_items(datasets: Sequence[Mapping[str, Any]], only: Sequence[str] | None) -> list[Finding]:
    out: list[Finding] = []
    owner: dict[str, str] = {}  # item → the first value table holding it
    for ds in datasets:
        kind = ds.get("kind")
        if not isinstance(kind, str) or kind not in VALUE_KINDS:  # `["values"]`: M001's
            continue
        name = str(ds.get("name"))
        mine = only is None or name in only
        items = sorted(set(_items(ds)))
        for item in items:
            if mine and not (_NAME.fullmatch(item) and not keyword.iskeyword(item)):
                msg = f"item {item!r} of {name}: not a value-table item name (TDS 5.28)"
                out.append(Finding("TDS-M018", "error", msg, dataset=name))
            first = owner.setdefault(item, name)
            if first != name and (mine or first in (only or ())):
                msg = f"item {item!r} is in {first} and {name}: an item lives in one value table"
                out.append(Finding("TDS-M019", "error", f"{msg} (TDS 5.28)", dataset=name))
        if mine:
            out += [Finding("TDS-M014", "error", m, dataset=name) for m in _declared(ds)]
    return out


def _items(ds: Mapping[str, Any]) -> Iterable[str]:
    files = ds.get("files")
    for entry in files if isinstance(files, list) else []:
        rel = entry.get("path") if isinstance(entry, dict) else None
        for part in PurePosixPath(rel).parent.parts if isinstance(rel, str) else ():
            if part.startswith("item="):
                yield part.removeprefix("item=")


def _declared(ds: Mapping[str, Any]) -> Iterable[str]:
    """M014's messages for one value table: its `availability` and `params.items`."""
    if "availability" in ds:
        yield "availability is written: a value table's is 5.28's, never declared (TDS 5.28)"
    params = ds.get("params")
    items = params.get("items") if isinstance(params, dict) else None
    if items is None:
        return
    if not isinstance(items, dict):
        yield f"params.items {items!r} is not an object of item declarations (TDS 5.28)"
        return
    for item, said in sorted(items.items()):
        at = f"params.items.{item}"
        if not isinstance(said, dict):
            yield f"{at} {said!r} is not an object with kind and carry (TDS 5.28)"
            continue
        for field in sorted(set(said) - {"kind", "carry"}):
            yield f"{at}: unknown field {field!r}; 5.28 declares kind and carry"
        if "kind" in said and said["kind"] not in KINDS:
            yield f"{at}.kind {said['kind']!r} is not one of {', '.join(KINDS)} (TDS 5.28)"
        carry = said.get("carry", "to_end")
        whole = isinstance(carry, int) and not isinstance(carry, bool) and carry >= 1
        if not whole and carry not in CARRIES:
            words = ", ".join(CARRIES)
            yield f"{at}.carry {carry!r} is not one of {words} or a positive whole number N"
