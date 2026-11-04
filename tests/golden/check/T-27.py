"""T-27 by hashing only (spec 3.7): the fixed-salt tie-break key and the two orders.

Run it: `uv run python tests/golden/check/T-27.py` prints each instrument's key and its place
under `tiebreak = "hash"` and `"id"`. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`). The orders are stated, and the asserts check them
against the keys and the ids rather than sorting.
"""

from hashlib import sha256
from operator import itemgetter
from typing import Any

SALT = b"nexusbt-tiebreak-v1"
SEPARATOR = b"\x1f"


def key(instrument_id: str) -> int:
    """The first 8 bytes of sha256(salt || 0x1F || id), big-endian unsigned."""
    digest = sha256(SALT + SEPARATOR + instrument_id.encode()).digest()
    return int.from_bytes(digest[:8], "big")


# Equal scores, so the key alone orders them.
key_1, key_2, key_3 = key("KR:T00001"), key("KR:T00002"), key("KR:T00003")
assert key_2 < key_1 < key_3, "hash order T00002, T00001, T00003"
assert "KR:T00001" < "KR:T00002" < "KR:T00003", "id order T00001, T00002, T00003"

ROWS = (
    {"instrument_id": "KR:T00002", "key": key_2, "hash_order": 1, "id_order": 2},
    {"instrument_id": "KR:T00001", "key": key_1, "hash_order": 2, "id_order": 1},
    {"instrument_id": "KR:T00003", "key": key_3, "hash_order": 3, "id_order": 3},
)

COLUMNS = ("instrument_id", "key", "hash_order", "id_order")


def line(row: dict[str, Any]) -> str:
    return "{:<13} {:>20} {!s:>10} {!s:>8}".format(*itemgetter(*COLUMNS)(row))


if __name__ == "__main__":
    print(line(dict(zip(COLUMNS, COLUMNS, strict=True))))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
