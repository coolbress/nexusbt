"""The manifest's `environment` (5.9.2, SC-26): where a bit-identity claim holds (INV-09)."""

from __future__ import annotations

import hashlib
import os
import platform
import uuid
from importlib import metadata
from pathlib import Path

import numpy as np

_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMBA_NUM_THREADS")
_MACHINE_ID_FILES = (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id"))


def _host_unique_id() -> str:
    """The host's own id: the systemd/dbus machine-id where there is one, else the MAC address."""
    for path in _MACHINE_ID_FILES:
        found = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
        if found:
            return found
    return f"{uuid.getnode():012x}"


def machine_id() -> str:
    """2.6: sha256(host unique id)[:16]; the host name and the raw id are never written."""
    return hashlib.sha256(_host_unique_id().encode()).hexdigest()[:16]


def environment(engine_lock: bytes) -> dict[str, object]:
    lock = hashlib.sha256(engine_lock).hexdigest()  # the source tree's or the wheel's copy
    blas = np.show_config(mode="dicts")["Build Dependencies"].get("blas", {})  # a summary of it
    packages = {d.metadata["Name"]: d.version for d in metadata.distributions()}
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": f"{platform.machine()}/{platform.processor() or 'unknown'}",
        "machine_id": machine_id(),
        "uv_lock_sha256": lock,
        "packages": dict(sorted(packages.items())),
        "numerics": {  # the engine compiles no kernel with fastmath or parallel (SC-26)
            "numba_fastmath": False,
            "numba_parallel": False,
            "blas": {key: blas.get(key) for key in ("name", "version")},
            "thread_env": {name: os.environ.get(name) for name in _ENV},
        },
    }
