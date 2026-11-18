"""`Pipeline(screen=)` (3.5): the rows a screen keeps, unknown being false (5.4.1, R3-13).

`run_pipeline` calls `screened` on the executor's tables rather than writing the rule again
(#249 Decisions).
"""

from __future__ import annotations

from collections.abc import Mapping

import pyarrow as pa
import pyarrow.compute as pc

from nexusbt.contracts import ID_COLUMN
from nexusbt.pipeline import Pipeline, graph_hash


def screened(pipeline: Pipeline, frames: Mapping[str, pa.Table]) -> dict[str, pa.Table]:
    """Each column's table, by its name, with the rows its screen is true at: a false or an
    unknown (null) screen cell drops the row. `frames` are one `execute()` call's tables, keyed
    by graph hash, the screen's among them when the pipeline has one; they list the same
    `(row, instrument_id)` cells in the same order."""
    named = {**pipeline.columns, **({"screen": pipeline.screen} if pipeline.screen else {})}
    if missing := [name for name, term in named.items() if graph_hash(term) not in frames]:
        raise ValueError(f"execute() was not given these terms of the pipeline: {missing}")
    found = {name: frames[graph_hash(term)] for name, term in pipeline.columns.items()}
    if pipeline.screen is None:
        return found
    screen = frames[graph_hash(pipeline.screen)]
    keep = pc.fill_null(screen["value"], False)
    for name, table in found.items():
        if not table.select(["row", ID_COLUMN]).equals(screen.select(["row", ID_COLUMN])):
            raise ValueError(f"column {name!r} and the screen list different cells")
        found[name] = table.filter(keep)
    return found
