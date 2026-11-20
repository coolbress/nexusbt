"""A memory measurement in a process of its own, where no coverage is measured.

`tracemalloc` counts every allocation of the process it runs in: in the suite's process that is
coverage's tracer, every thread an earlier test left and whatever the collector has not freed
yet, none of it the code measured (#359, #662).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


def measured_alone(script: str, *args: str) -> dict[str, Any]:
    """Run `script` with `args` in a new interpreter without coverage's variables. Its last line
    of output is a JSON object holding `"coverage": "coverage" in sys.modules`, which must be
    false; the rest of that object is the result."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("COVERAGE_")}
    done = subprocess.run(  # noqa: S603 - this interpreter, the caller's script
        [sys.executable, "-c", script, *args],
        env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    seen: dict[str, Any] = json.loads(done.stdout.splitlines()[-1])
    assert not seen.pop("coverage"), "coverage is loaded where the peak is measured (#359)"
    return seen
