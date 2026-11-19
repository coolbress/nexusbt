"""`nexusbt init` and `nexusbt doctor` (3.10, T1.2): the text both commands print."""

from __future__ import annotations

import json
import os
import re
import shutil
import tomllib
import uuid
from pathlib import Path
from typing import Any

from nexusbt import api
from nexusbt.artifacts import Index
from nexusbt.config import DEFAULTS, UUID4, load_config
from nexusbt.contracts import ConfigError
from nexusbt.data import GENERIC, DataConfig, _data_root, open_snapshot

TOML = Path("nexusbt.toml")
_DATA, _RESEARCH = "config — nexusbt.toml [data] -", "config — nexusbt.toml [research] family_id"
#: What `init` says when no data root is given anywhere (3.10; no personal path, 2.7).
NO_ROOT = (
    "no data root: pass --data-root PATH or set $NEXUSBT_DATA_ROOT; to make a synthetic"
    " snapshot: uv run python -m nexusbt.testing.synth --preset tiny --out .scratch/snap"
)
#: `doctor`'s stubs line when the stub file is not what `nexusbt stubs` writes (3.2, #469).
_STALE = "stale: not what nexusbt stubs writes for this snapshot's columns; run nexusbt stubs"


def init(data_root: str | None = None, *, new_family: str | None = None) -> str:
    """Write `nexusbt.toml` naming the snapshot, from `data_root` or `$NEXUSBT_DATA_ROOT` (3.10).

    A package folder (with tds.json) goes in `[data] path`, a root (with `LATEST`) in `root`
    (3.11); a new project's `[research] family_id` is a new UUID4 (6.2). `new_family` is the
    reason of `--new-family`. The commented two-tier template is T5.21's, `--demo` T5.18's."""
    if new_family is not None:
        return _new_family(new_family, data_root)
    if TOML.exists() and data_root is None:
        return _add_family()
    if TOML.exists():
        raise _refused(f"{TOML} already exists", "keep it, or delete it and run init again")
    given = data_root or os.environ.get("NEXUSBT_DATA_ROOT")
    if not given:
        raise _refused("no data root to write", NO_ROOT)
    key = "path" if (Path(given) / "tds.json").is_file() else "root"
    source = "--data-root" if data_root else "$NEXUSBT_DATA_ROOT"
    text = f"# written by `nexusbt init` from {source} (spec 3.10, 3.11)\n[data]\n"
    text += f"{key} = {json.dumps(given, ensure_ascii=False)}\n\n"
    TOML.write_text(text + f'[research]\nfamily_id = "{uuid.uuid4()}"\n', encoding="utf-8")
    return f"wrote {TOML}: [data] {key} from {source}, [research] family_id; next: nexusbt doctor"


#: A `[research]` header on a line of its own, with what ends that line (TOML 1.0 tables).
_HEADER = re.compile(r"^[ \t]*\[[ \t]*research[ \t]*\][ \t]*(?:#[^\r\n]*)?(\r?\n|\Z)", re.M)


def _add_family() -> str:
    """An existing `nexusbt.toml` without `[research] family_id` gets one, every byte already
    there kept: 6.2 creates the family once per project (#466, Decisions 2026-11-16)."""
    text, given, why = *_project(), "init adds the family a project has not got (6.2)"
    if _family(given) is not None:
        raise _refused(f"{TOML} already exists", "keep it, or delete it and run init again")
    newline = "\r\n" if "\r\n" in text else "\n"
    line = f'family_id = "{uuid.uuid4()}"{newline}'
    if "research" not in given:  # a new table at the end
        lead = "" if not text else newline if text.endswith("\n") else newline * 2
        text += lead + "[research]" + newline + line
    elif len(found := list(_HEADER.finditer(text))) == 1:  # under the empty table's header
        at = found[0].end()
        text = text[:at] + ("" if found[0].group(1) else newline) + line + text[at:]
    else:  # an inline table or a dotted key: no line of its own to write under
        fix = 'write [research] family_id = "<a new UUID4>" by hand, or delete the [research] line'
        raise _refused("[research] is there without family_id, not as a table", fix, why, _RESEARCH)
    os.replace(_staged(text.encode("utf-8")), TOML)
    return f"added [research] family_id to {TOML}; nothing else in it changed"


def _new_family(reason: str, data_root: str | None) -> str:
    """`--new-family REASON`: a new UUID4 in place of the old id, which becomes its parent in the
    index's `families` table (3.10, 6.2). Only the id changes in the file; refused before any
    write when there is no project, no id or no reason."""
    no = "--new-family replaces the family of an existing project (3.10)"
    if data_root is not None:
        raise _refused("--data-root with --new-family", "run them as two commands", no, _DATA)
    if not reason.strip():
        raise _refused("--new-family has no reason", 'say why: --new-family "..."', no, _RESEARCH)
    if not TOML.is_file():
        raise _refused(f"no {TOML} here", "run nexusbt init first", no, _RESEARCH)
    text, given = _project()
    if (old := _family(given)) is None:
        fix = "run nexusbt init to write the first one"
        raise _refused("no [research] family_id to record as the parent", fix, no, _RESEARCH)
    if text.count(old) != 1:  # a UUID: once, unless a comment repeats it or an escape hides it
        fix = f'write the line as family_id = "{old}", and nowhere else, then run it again'
        raise _refused(f"the family id is not in {TOML} once as written", fix, no, _RESEARCH)
    new = str(uuid.uuid4())
    part = _staged(text.replace(old, new).encode("utf-8"))  # a full disk stops it before the index
    try:
        runs = Path(_table(given, "runs").get("dir", DEFAULTS["runs"]["dir"]))
        Index(runs, family_id=old).add_family(new, old, f"new family: {reason}")  # 5.9.5's form
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    os.replace(part, TOML)
    return f"[research] family_id {old} -> {new}, the old one recorded as its parent"


def _project() -> tuple[str, dict[str, Any]]:
    """`nexusbt.toml` as written, and parsed; nothing else is checked, so a data root that is
    not mounted does not stop `init` from writing the family (the rest is `load_config`'s)."""
    try:
        text = TOML.read_bytes().decode("utf-8")
        return text, tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise _refused(f"{TOML} is not TOML: {error}", "fix the file", "spec 3.11") from None


def _table(given: dict[str, Any], name: str) -> dict[str, Any]:
    table = given.get(name, {})
    if not isinstance(table, dict):  # `research = "x"`, `[[research]]`: a ConfigError, not a crash
        raise _refused(f"{name} = {table!r} is not a table", f"write it as [{name}]", "spec 3.11")
    return table


def _family(given: dict[str, Any]) -> str | None:
    family = _table(given, "research").get("family_id")
    if family is not None and not (isinstance(family, str) and re.fullmatch(UUID4, family)):
        fix = "a UUID4 as nexusbt init writes it"
        raise _refused(f"[research] family_id = {family!r}", fix, "spec 3.11", _RESEARCH)
    return family


def _staged(content: bytes) -> Path:
    """The new `nexusbt.toml` beside the old; `os.replace` then swaps it in whole."""
    part = TOML.with_name(TOML.name + ".writing")
    part.write_bytes(content)
    return part


def doctor() -> str:
    """The snapshot `nexusbt.toml` points at, as 3.10's `doctor` row lists it (T1.2's part)."""
    cfg = load_config(TOML if TOML.is_file() else None)  # no tds.json read: it may be mid-write
    if not (cfg.values["data"]["path"] or cfg.values["data"]["root"]):  # /run's default target
        why = "doctor reports on one snapshot (3.10)"
        raise _refused("no snapshot to open: [data] names none", f"{NO_ROOT}; then init", why)
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
    named = [(f, f"{f.dataset}.{f.column}" if f.column else f.dataset) for f in s.fallbacks]
    lines += [("fallback", f"{f.id} {name} {f.market} {f.count}") for f, name in named]  # F-01
    lines += [] if s.fallbacks else [("fallbacks", "none")]
    for m, info in s.markets.items():
        d = s.daily.get(m)
        rules = "none" if info.rules is None else info.rules.replace(GENERIC, "untested")
        counts = "-"
        if d is not None:
            first, last, n, rows = (_or(v) for v in (d.first, d.last, d.instruments, d.rows))
            counts = f"{first}..{last}  instruments {n}  rows {rows}"
        lines.append((f"market {m}", f"rules {rules}  {counts}"))
    lines.append(("columns", f"{s.daily_columns} daily bar columns"))
    lines.append(("free disk", f"{shutil.disk_usage(root).free / 1e9:.1f} GB"))
    lines.append(("stubs", "current" if api.stubs_current(s, cfg) else _STALE))
    hidden = _unseen_pins(Path(cfg.values["runs"]["dir"]))
    text = "\n".join(f"{k:<11}{v}" for k, v in lines)
    return text + f"\npins not visible to producer: {hidden} runs (root pin not written)"


def _unseen_pins(runs: Path) -> int:
    """The runs holding an unreleased pin in the index whose sealed manifest says `retention:
    unmanaged`: their root pin was not written, so the producer's clean-up cannot see them (3.10,
    4.2, R3-17). Which data root `nexusbt.toml` names now does not matter; a run not sealed is
    not counted (#465 Decisions). No index, no run: 0."""
    if not (runs / "index.sqlite").is_file():
        return 0
    return sum(_unmanaged(runs / r) for _, r in Index(runs).held("run"))


def _unmanaged(folder: Path) -> bool:  # a run folder with no `SEALED` is not counted
    if not (folder / "SEALED").is_file():
        return False
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return bool(manifest.get("retention") == "unmanaged")


def _or(value: object) -> str:  # an undeclared coverage key is shown as unknown, not 0
    return "-" if value is None else str(value)


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _refused(
    what: str, fix: str, why: str = "init writes the file once (3.10)", layer: str = _DATA
) -> ConfigError:
    return ConfigError(
        what=what, where=f"{TOML} in the working folder", why=why, fix=fix,
        more="spec 3.10 nexusbt init and doctor", layer=layer,
    )  # fmt: skip
