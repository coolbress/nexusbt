"""A pure-Python reference encoder of the TDS 4.5 canonical value serialisation (no pyarrow).

Written apart from `nexusbt_tds.hash` on purpose: a different sort (a comparison function) and
byte assembly by hand, so the two cross-check each other and the published vectors. Values are
the vectors' JSON forms: a date is `"YYYY-MM-DD"`, an instant an integer in its unit.
"""

from __future__ import annotations

import datetime as dt
import functools
import struct
from typing import Any

EPOCH = dt.date(1970, 1, 1)
WIDE = {"i8", "i16", "i32", "i64", "fixed", "ts_us", "ts_ns"}
TEXT = {"string", "id", "code", "json"}


def le(n: int, size: int, signed: bool = True) -> bytes:
    return n.to_bytes(size, "little", signed=signed)


def cell(tag: str, v: Any) -> bytes:
    if v is None:
        return b"\x00"
    if tag == "bool":
        body = b"\x01" if v else b"\x00"
    elif tag in WIDE:
        body = le(v, 8)
    elif tag == "f64":
        body = struct.pack("<d", 0.0 if v == 0 else float(v))  # IEEE-754 bits, -0.0 as +0.0
    elif tag == "date":
        body = le((dt.date.fromisoformat(v) - EPOCH).days, 4)
    elif tag in TEXT:
        body = le(len(v.encode()), 4, signed=False) + v.encode()
    elif tag.startswith("list<"):
        body = le(len(v), 4, signed=False) + b"".join(cell(tag[5:-1], x) for x in v)
    else:
        raise ValueError(tag)
    return b"\x01" + body


def compare(tag: str, a: Any, b: Any) -> int:
    if a is None or b is None:
        return (a is not None) - (b is not None)
    if tag.startswith("list<"):
        for x, y in zip(a, b, strict=False):
            if c := compare(tag[5:-1], x, y):
                return c
        return (len(a) > len(b)) - (len(a) < len(b))
    if tag == "date":
        a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    if tag in TEXT:
        a, b = a.encode(), b.encode()
    return int(a > b) - int(a < b)


def encode(columns: list[tuple[str, str]], key: list[str], rows: list[list[Any]]) -> bytes:
    names = [n for n, _ in columns]
    tags = dict(columns)
    order = [names.index(n) for n in [*key, *(n for n in names if n not in key)]]

    def by(r: list[Any], s: list[Any]) -> int:
        return next((c for i in order if (c := compare(tags[names[i]], r[i], s[i]))), 0)

    head = b"TDSV1\n" + b"".join(f"{n}\t{t}\n".encode() for n, t in columns) + b"\n"
    body = b"".join(cell(t, r[i]) for r in sorted(rows, key=functools.cmp_to_key(by))
                    for i, (_, t) in enumerate(columns))  # fmt: skip
    return head + body
