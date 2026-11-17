"""Instrument ids into the integer arrays the cross-section kernels of `_kernels` take (2.4):
the kernels see no strings, so these run outside the seam."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np

from nexusbt.compute._kernels import I64
from nexusbt.contracts import TiebreakPolicy

_SALT = b"nexusbt-tiebreak-v1"


def sorted_order(ids: Sequence[str]) -> I64:
    """The memory positions of `ids` in ascending `instrument_id` order."""
    found: I64 = np.argsort(np.asarray(ids, dtype=object), kind="stable").astype(np.int64)
    return found


def tie_order(ids: Sequence[str], policy: TiebreakPolicy) -> I64:
    """Each cell's place (0 first) in the order of the `[portfolio] tiebreak` key (3.7): `"hash"`
    ascending (the first 8 bytes of sha256(salt || 0x1F || id), big-endian, then the id), `"id"`
    ascending `instrument_id`. The key reads nothing but the id, so it is the same at every
    decision."""

    def key(i: int) -> tuple[int, str]:
        if policy is TiebreakPolicy.ID:
            return (0, ids[i])
        digest = hashlib.sha256(_SALT + b"\x1f" + ids[i].encode()).digest()
        return (int.from_bytes(digest[:8], "big"), ids[i])

    place = np.empty(len(ids), dtype=np.int64)
    place[sorted(range(len(ids)), key=key)] = np.arange(len(ids))
    return place
