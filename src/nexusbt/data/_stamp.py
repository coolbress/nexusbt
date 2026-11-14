"""Spec 4.2 and 4.4-1: the verification stamp `<runs.dir>/.cache/verified/<physical_sha256>`.

A package whose file sha256s were checked once gets a stamp holding each file's identity
`(dev, inode, size, mtime_ns)`; the next check skips the sha256 of a file whose identity is the
same and computes it again when it differs, and then the stamp is discarded [R3-16, ADR-0037].
The identity is not a proof: `verify = "full"` reads every byte."""

from __future__ import annotations

import json
import os
from pathlib import Path

from nexusbt_tds.check import Finding
from nexusbt_tds.hash import file_sha256
from nexusbt_tds.manifest import Manifest


def _identity(path: Path) -> list[int]:
    st = path.stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]


def check_files(folder: Path, manifest: Manifest, stamps: Path | None) -> list[Finding]:
    """H001 for each declared file whose sha256 differs, hashing only the files the stamp does
    not hold as they are; the stamp is rewritten when one changed and none differs, and left
    out when one does. Paths in the stamp are the package's own, relative (2.7)."""
    declared = {f["path"]: (d["name"], f["sha256"]) for d in manifest.datasets
                for f in d.get("files") or [] if "sha256" in f}  # fmt: skip
    physical = manifest.data.get("hashes", {}).get("physical_sha256")
    stamp = stamps / str(physical) if stamps is not None and physical else None
    try:
        held = json.loads(stamp.read_text(encoding="utf-8"))["files"] if stamp else {}
    except (OSError, ValueError, KeyError, TypeError):  # none yet, or unreadable: hash all
        held = {}
    held = held if isinstance(held, dict) else {}  # a stamp of another shape holds nothing
    now = {path: _identity(folder / path) for path in declared}
    found = [
        Finding("TDS-H001", "error", f"sha256 {actual}, declared {sha}", name, path)
        for path, (name, sha) in declared.items()
        if now[path] != held.get(path) and (actual := file_sha256(folder / path)) != sha
    ]
    if stamp is None or now == held:
        return found
    try:
        stamp.unlink(missing_ok=True)  # an identity changed: this stamp no longer holds
        if not found:
            stamp.parent.mkdir(parents=True, exist_ok=True)
            part = stamp.with_name(f".{stamp.name}.{os.getpid()}")
            part.write_text(json.dumps({"files": now}, sort_keys=True), encoding="utf-8")
            part.replace(stamp)  # whole or absent, never half written
    except OSError:  # a stamp is a cache: without it the next open hashes the files again
        pass
    return found
