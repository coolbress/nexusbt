"""TDS-V031 (TDS 5.8): a crossed book after reconstruction, on each `book_deltas` dataset.

The rules are #347's `## Decision` (2026-11-12). Each partition (`venue`, `date`) is read in its
stored order, its files in file-name order (TDS 3.5). A batch's rows wait until its
`is_last = true` row, then change the book by the table of TDS 5.8, and the instrument's book
is judged: crossed when best bid > best ask, with a level on both sides. A book therefore always
holds the state after the last such row, which is what a `params.continuity = "carry"` date
starts from; a batch left open at a partition's end changes nothing. A `depth_kind` other than
`mbp` or `mbo`, or a file the code cannot read, leaves V031 unchecked.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pyarrow as pa

from .check import BOOK_CODES, Finding
from .keys import listed
from .manifest import Manifest
from .refs import _rows

(V031,) = BOOK_CODES
COLUMNS = ("instrument_id", "ts_event", "action", "side", "price", "size", "order_id", "is_last")
SIDES = ("bid", "ask")
Book = dict[Any, Any]  # mbp: (side, price) → size; mbo: order_id → (side, price, size)


def check_books(
    m: Manifest, only: Sequence[str] | None, blind: set[str], notes: list[str]
) -> list[Finding]:
    """V031 on the checked `book_deltas` datasets; `notes` gets each date judged from a partial
    book (a `carry` date with no previous partition of its venue in the package)."""
    out: list[Finding] = []
    for ds in m.datasets:
        name = str(ds.get("name"))
        if ds.get("kind") != "book_deltas" or (only is not None and name not in only):
            continue
        params = ds.get("params")
        params = params if isinstance(params, dict) else {}
        kind = params.get("depth_kind")
        if kind not in ("mbp", "mbo"):
            blind.add(V031)
            notes.append(f"{V031} not checked on {name}: depth_kind {kind!r} is not mbp or mbo")
            continue
        try:
            out += _dataset(m, ds, kind, params.get("continuity") == "carry", notes)
        except (OSError, pa.ArrowException, TypeError, ValueError):
            blind.add(V031)  # unreadable, or a column of the wrong type: its rows are not judged
    return out


def _dataset(
    m: Manifest, ds: Mapping[str, Any], kind: str, carry: bool, notes: list[str]
) -> list[Finding]:
    root, name, out = m.root.resolve(), str(ds.get("name")), []
    parts: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for rel, values in listed(root, ds):
        parts[values.get("venue", ""), values.get("date", "")].append(rel)
    last: dict[str, dict[Any, Book]] = {}  # venue → each instrument's book after its last date
    for venue, day in sorted(parts):
        if carry and venue not in last:
            notes.append(f"{V031} on {name}: venue {venue} date {day} judged from a partial book"
                         " (continuity carry, no previous partition in the package)")  # fmt: skip
        books = last.setdefault(venue, {}) if carry else {}
        part = {**ds, "files": [{"path": rel} for rel in sorted(parts[venue, day])]}  # TDS 3.5
        for i, (first, n) in _judge(_rows(root, part, COLUMNS), kind, books).items():
            key = {"venue": venue, "session_date": day, "instrument_id": i, "ts_event": first}
            msg = f"crossed book (best bid > best ask) at {n} judgement point(s)"
            out.append(Finding(V031, "warning", msg, name, key=key, count=n))
    return out


def _judge(
    rows: Iterable[tuple[Any, ...]], kind: str, books: dict[Any, Book]
) -> dict[Any, tuple[str, int]]:
    """Each crossed instrument's first crossed `ts_event` and its count of crossed points."""
    pending: defaultdict[Any, list[tuple[Any, ...]]] = defaultdict(list)
    crossed: dict[Any, tuple[str, int]] = {}
    for i, ts, *change, is_last in rows:
        pending[i].append(tuple(change))
        if not is_last:
            continue
        book = books.setdefault(i, {})
        for row in pending.pop(i):
            _apply(book, kind, *row)
        if _crossed(book, kind):
            first, n = crossed.get(i, (str(ts), 0))
            crossed[i] = (first, n + 1)
    return crossed


def _apply(book: Book, kind: str, action: Any, side: Any, price: Any, size: Any, oid: Any) -> None:
    """One row's change to the book (TDS 5.8; `trade`, `fill` and `none` change nothing)."""
    order = book.get(oid) if kind == "mbo" else None
    if action == "clear":
        book.clear()
    elif action not in ("add", "modify", "cancel"):
        return
    elif kind == "mbp":
        if side in SIDES and price is not None:
            if size:
                book[side, price] = size
            else:  # size 0 or null removes the level
                book.pop((side, price), None)
    elif action == "add" or (action == "modify" and order is None):
        if side in SIDES and oid is not None:  # an unknown order is inserted as by `add`
            book[oid] = (side, price, size)
    elif order is None:  # cancel of an unknown order: ignored
        return
    elif action == "modify":
        book[oid] = (order[0], price, size)
    else:  # cancel
        left = order[2]
        if size is None or left is None or size >= left:
            del book[oid]
        else:
            book[oid] = (order[0], order[1], left - size)


def _crossed(book: Book, kind: str) -> bool:
    """Best bid > best ask, both sides with a level (a locked book is not crossed)."""
    levels = list(book) if kind == "mbp" else [(s, p) for s, p, _ in book.values()]
    bids = [p for s, p in levels if s == "bid" and p is not None]
    asks = [p for s, p in levels if s == "ask" and p is not None]
    return bool(bids and asks) and max(bids) > min(asks)
