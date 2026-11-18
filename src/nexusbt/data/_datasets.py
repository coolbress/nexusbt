"""Which dataset of a kind the engine reads (spec 4.3, #547, #551): chosen by its `kind`, and
where parameters tell datasets of that kind apart by those parameters, never by its place in
`datasets[]`, since TDS 3.1 lets a package hold several datasets of one kind."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nexusbt.contracts import CapabilityError

#: The parameters that tell datasets of a kind apart, each to the value the engine reads and
#: the values it reads as that one: session daily bars (4.6). Minute bars are not read in v1,
#: nor `utc_day` daily bars (TDS 9.4); a `bars` dataset with no `bar_time` is read as `session`,
#: the engine's rule where TDS 5.5 names no default (4.3, #551).
TOLD_APART = {"bars": {"freq": ("1d", ("1d",)), "bar_time": ("session", ("session", None))}}

Dataset = Mapping[str, Any]


def left(data: Mapping[str, Any], kind: str) -> list[Dataset]:
    """The datasets of `kind` that carry the parameter values the engine reads, in list order."""
    told = TOLD_APART.get(kind, {})
    return [d for d in _datasets(data) if d.get("kind") == kind and all(
        (d.get("params") or {}).get(p) in read for p, (_, read) in told.items())]  # fmt: skip


def chosen(data: Mapping[str, Any]) -> dict[str, Dataset]:
    """Each kind with exactly one dataset left, to its dataset: what `open` reads, where a kind
    with none or two or more left counts as missing and turns off what needs it (4.3)."""
    kinds = dict.fromkeys(str(d.get("kind")) for d in _datasets(data))
    return {k: found[0] for k in kinds if len(found := left(data, k)) == 1}


def doubled(data: Mapping[str, Any]) -> list[str]:
    """The kinds with two or more datasets left: what needs one is off, fallback or not (4.3)."""
    kinds = dict.fromkeys(str(d.get("kind")) for d in _datasets(data))
    return [k for k in kinds if len(left(data, k)) > 1]


def dataset(data: Mapping[str, Any], kind: str) -> Dataset | None:
    """The one dataset of `kind` the engine reads, or None without one; two or more left is
    E18, naming each, since the engine cannot choose between them (4.3)."""
    found = left(data, kind)
    if len(found) > 1:
        raise _ambiguous(data, kind, [str(d.get("name")) for d in found])
    return found[0] if found else None


def needed(data: Mapping[str, Any], kind: str) -> Dataset:
    """`dataset`, where the read needs it: none left is E18 as a missing dataset (4.3)."""
    found = dataset(data, kind)
    if found is None:
        told = TOLD_APART.get(kind, {})
        shown = f"{kind} ({', '.join(f'{p}={v}' for p, (v, _) in told.items())})" if told else kind
        raise CapabilityError(
            what=f"no {shown} dataset in snapshot {data.get('snapshot_id')}",
            where=f"snapshot {data.get('snapshot_id')} datasets",
            why="a dataset a read needs and the package lacks is refused, not substituted (4.3)",
            fix=f"use a snapshot with a {shown} dataset", more="spec 4.3",
            layer=layer(data, kind),
        )  # fmt: skip
    return found


def _ambiguous(data: Mapping[str, Any], kind: str, names: Sequence[str]) -> CapabilityError:
    params = " and ".join(f"params.{p} = {v}" for p, (v, _) in TOLD_APART.get(kind, {}).items())
    return CapabilityError(
        what=f"{len(names)} datasets of kind {kind}{f' with {params}' if params else ''}: "
             f"{', '.join(names)}",
        where=f"snapshot {data.get('snapshot_id')} datasets",
        why="the engine chooses a dataset by its kind and parameters, never by its place in "
            "datasets[], and cannot choose between these (4.3)",
        fix=f"keep only one of {', '.join(names)} in the package", more="spec 4.3",
        layer=layer(data, names[0]),
    )  # fmt: skip


def _datasets(data: Mapping[str, Any]) -> list[Dataset]:
    value = data.get("datasets")
    return [d for d in value if isinstance(d, dict)] if isinstance(value, list) else []


def layer(data: Mapping[str, Any], dataset: str) -> str:
    """The error's layer line: the snapshot, the dataset and the producer (6.6)."""
    producer = data.get("producer")
    name = str(producer.get("name", "-")) if isinstance(producer, dict) else "-"
    return f"data — snapshot {data.get('snapshot_id')} / {dataset} / column - / producer {name}"
