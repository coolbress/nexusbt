"""The manifest's `environment` (5.9.2, SC-26): where a bit-identity claim holds (INV-09)."""

from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import sys
import uuid
from importlib import metadata
from pathlib import Path

import numpy as np

_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS")
_MACHINE_ID_FILES = (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id"))
UNKNOWN_MACHINE = "unknown"  # the manifest's machine_id when no host id is read (2.6)
_GETHOSTUUID_WAIT_SECONDS = 2  # the kernel answers at once; bounded so a seal never hangs on it


def _darwin_host_uuid() -> str | None:
    """macOS's hardware UUID from gethostuuid(2), or None when the call fails."""
    libc = ctypes.CDLL(None)
    found = (ctypes.c_ubyte * 16)()
    wait = (ctypes.c_long * 2)(_GETHOSTUUID_WAIT_SECONDS, 0)  # a timespec; 0 waits forever
    if libc.gethostuuid(found, wait) != 0:
        return None
    return str(uuid.UUID(bytes=bytes(found)))


def _host_unique_id() -> str | None:
    """The host's own id: the systemd/dbus machine-id, macOS's hardware UUID, else the MAC.

    None when none of them is read: uuid.getnode() then returns a random node with the
    multicast bit set, chosen anew in every process, which names no host (#635).
    """
    for path in _MACHINE_ID_FILES:
        found = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
        if found:
            return found
    darwin = _darwin_host_uuid() if sys.platform == "darwin" else None
    if darwin:
        return darwin
    node = uuid.getnode()
    return None if node >> 40 & 1 else f"{node:012x}"


def machine_id() -> str | None:
    """2.6: sha256(host unique id)[:16], or None when no host id is read; never a made-up one.

    The host name and the raw id are never written.
    """
    found = _host_unique_id()
    return None if found is None else hashlib.sha256(found.encode()).hexdigest()[:16]


def same_machine(recorded: str) -> bool:
    """2.6, E31: whether a manifest's `environment.machine_id` names this host.

    An id that was not read, on either side, is another machine: two unidentified hosts
    are never taken for one (#635).
    """
    current = machine_id()
    unread = (None, UNKNOWN_MACHINE)
    return recorded not in unread and current not in unread and recorded == current


def environment(engine_lock: bytes) -> dict[str, object]:
    lock = hashlib.sha256(engine_lock).hexdigest()  # the source tree's or the wheel's copy
    blas = np.show_config(mode="dicts")["Build Dependencies"].get("blas", {})  # a summary of it
    packages = {d.metadata["Name"]: d.version for d in metadata.distributions()}
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": f"{platform.machine()}/{platform.processor() or 'unknown'}",
        "machine_id": machine_id() or UNKNOWN_MACHINE,
        "uv_lock_sha256": lock,
        "packages": dict(sorted(packages.items())),
        "numerics": {  # the engine compiles no kernel with fastmath or parallel (SC-26)
            "numba_fastmath": False,
            "numba_parallel": False,
            "blas": {key: blas.get(key) for key in ("name", "version")},
            "thread_env": {name: os.environ.get(name) for name in _ENV},
        },
    }
