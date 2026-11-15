"""`nexusbt init` and `nexusbt doctor` (3.10, T1.2): the text both commands print."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from nexusbt.artifacts import Index
from nexusbt.config import load_config
from nexusbt.contracts import ConfigError
from nexusbt.data import GENERIC, DataConfig, _data_root, open_snapshot

TOML = Path("nexusbt.toml")
#: What `init` says when no data root is given anywhere (3.10; no personal path, 2.7).
NO_ROOT = (
    "no data root: pass --data-root PATH or set $NEXUSBT_DATA_ROOT; to make a synthetic"
    " snapshot: uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap"
)


def init(data_root: str | None = None) -> str:
    """Write `nexusbt.toml` naming the snapshot, from `data_root` or `$NEXUSBT_DATA_ROOT` (3.10).

    A package folder (with tds.json) goes in `[data] path`, a root (with `LATEST`) in `root`
    (3.11). The commented two-tier template is T5.21's, `--demo` T5.18's."""
    given = data_root or os.environ.get("NEXUSBT_DATA_ROOT")
    if TOML.exists():
        raise _refused(f"{TOML} already exists", "keep it, or delete it and run init again")
    if not given:
        raise _refused("no data root to write", NO_ROOT)
    key = "path" if (Path(given) / "tds.json").is_file() else "root"
    source = "--data-root" if data_root else "$NEXUSBT_DATA_ROOT"
    text = f"# written by `nexusbt init` from {source} (spec 3.10, 3.11)\n[data]\n"
    TOML.write_text(text + f"{key} = {json.dumps(given, ensure_ascii=False)}\n", encoding="utf-8")
    return f"wrote {TOML}: [data] {key} from {source}; next: nexusbt doctor"


def doctor() -> str:
    """The snapshot `nexusbt.toml` points at, as 3.10's `doctor` row lists it (T1.2's part)."""
    cfg = load_config(TOML if TOML.is_file() else None)  # no tds.json read: it may be mid-write
    data = DataConfig.from_config(cfg)
    found = _data_root(Path(data.path))  # None for a package alone: no `PINS/` to see
    root = found or Path(data.path)
    if (root / ".publishing").exists():  # a distribution convention outside TDS (3.10)
        return "publishing in progress: wait for the new snapshot, then run nexusbt doctor again"
    s = open_snapshot(data)
    lines = [("snapshot", s.id), ("semantic", s.semantic_hash),
             ("edition", str(cfg.values["data"]["edition"]))]  # fmt: skip
    for name, p in s.profiles.items():  # declared / check level / supported (4.3)
        said = f"declared {_yes(p.declared)}  checked {p.verified_level}  result {p.result}"
        supported = _yes(name in s.capabilities.supported)
        lines.append(("profile", f"{name}  {said}  supported {supported}"))
    lines.append(("unchecked", ", ".join(s.unchecked) or "none"))
    lines.append(("codes", ", ".join(f"{c} {n}" for c, n in sorted(s.warnings.items())) or "none"))
    lines += [("fallback", f"{f.id} {f.dataset} {f.market} {f.count}") for f in s.fallbacks]
    lines += [] if s.fallbacks else [("fallbacks", "none")]
    for m, info in s.markets.items():
        d = s.daily.get(m)
        rules = "none" if info.rules is None else info.rules.replace(GENERIC, "untested")
        counts = f"{d.first}..{d.last}  instruments {d.instruments}  rows {d.rows}" if d else "-"
        lines.append((f"market {m}", f"rules {rules}  {counts}"))
    lines.append(("columns", f"{s.daily_columns} daily bar columns"))
    lines.append(("free disk", f"{shutil.disk_usage(root).free / 1e9:.1f} GB"))
    hidden = _unseen_pins(Path(cfg.values["runs"]["dir"]), found)
    text = "\n".join(f"{k:<11}{v}" for k, v in lines)
    return text + f"\npins not visible to producer: {hidden} runs"


def _unseen_pins(runs: Path, root: Path | None) -> int:
    """The runs pinned in the index with no `PINS/<snapshot_id>/<run_id>` under the data root:
    the producer's clean-up sees only that folder (4.2, R3-17). No index, no run: 0."""
    if not (runs / "index.sqlite").is_file():
        return 0
    held = Index(runs).held("run")
    return sum(root is None or not (root / "PINS" / s / r).exists() for s, r in held)


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _refused(what: str, fix: str) -> ConfigError:
    return ConfigError(
        what=what, where=f"{TOML} in the working folder", why="init writes the file once (3.10)",
        fix=fix, more="spec 3.10 nexusbt init", layer="config — nexusbt.toml [data] -",
    )  # fmt: skip
