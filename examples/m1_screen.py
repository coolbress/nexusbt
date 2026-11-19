"""Print the top 10 momentum per market on the reference date, and the run id (spec 10.1,
T1.13's "Done means"; #249).

Run it: `uv run python examples/m1_screen.py`. It makes the synthetic `small` package (4.8: 120
instruments per market, 2015 to 2019) in a new folder under the system's temporary folder,
works there so that `runs/` stays out of this repository, and screens `Returns(126)` on its
default input, `close_tr` (3.4), on each market's last session.

126 rows put the window's ends 125 sessions apart, not a multiple of 4: the `tiny` preset's
closes repeat every 4 sessions, so a return over such a span is 0 there (#260's note). `small`
is not periodic, but the example keeps to a window either preset can show.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import nexusbt as nx
from nexusbt.factors import Returns
from nexusbt.testing.synth import make_snapshot


def main() -> None:
    project = Path(tempfile.mkdtemp(prefix="m1_screen_"))
    package = make_snapshot(project / "data" / "synth", preset="small")
    # The synthetic package has no data root (no LATEST beside it): pin in the index only.
    (project / "nexusbt.toml").write_text('[data]\npins = "index"\n', encoding="utf-8")
    os.chdir(project)
    found = nx.screen(Returns(126), top=10, snapshot=str(package))
    print(found)
    print(f"run folder: {project / 'runs' / str(found.run_id)}")


if __name__ == "__main__":
    main()
