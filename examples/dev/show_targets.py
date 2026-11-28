"""Print the TargetFrame of one decision: `nx.top(3)` on one factor, equal weights (spec 3.7,
5.5.1).

Run it: `uv run python examples/dev/show_targets.py`. It shows the two things of T3.1a:

1. six scores, three of them equal, under `top(3)`: the selection rank and the weight of each
   name taken, 1/3 each, with the sum of the weights (at most 1) and how many names tie at the
   cutoff (`n_tied_at_cutoff`);
2. five names with two missing scores under `top(4)`: three names at 1/3 each, not 1/4.
"""

from __future__ import annotations

import datetime as dt

import pyarrow as pa

import nexusbt as nx
from nexusbt.contracts import DecisionGrid, FactorFrame
from nexusbt.portfolio import build_targets

DAY = dt.date(2019, 6, 28)
AT = dt.datetime(2019, 6, 28, 6, 30, tzinfo=dt.UTC)
NAN = float("nan")


def show(title: str, scores: dict[str, float], n: int) -> None:
    rows = [{"market": "KR", "session_date": DAY, "decision_ts": AT, "instrument_id": i,
             "score": s} for i, s in scores.items()]  # fmt: skip
    grid = DecisionGrid("KR", "XKRX", "KR_close", DAY, DAY, (DAY,), (AT,))
    targets, _ = build_targets(FactorFrame(pa.Table.from_pylist(rows)), nx.top(n), grid)
    print(title)
    print("decision_id           instrument_id  score  selected_rank  target_weight")
    for row in targets.table.to_pylist():
        print(f"{row['decision_id']}  {row['instrument_id']}  {row['score']:>5}"
              f"  {row['selected_rank']:>13}  {row['target_weight']:.6f}")  # fmt: skip
    total = sum(targets.table["target_weight"].to_pylist())
    tied = targets.coverage["n_tied_at_cutoff"][0].as_py()
    print(f"sum of weights {total:.6f}, n_tied_at_cutoff {tied}\n")


def main() -> None:
    show("top(3) of six scores, three of them equal:",
         {"KR:T00001": 2.0, "KR:T00002": 2.0, "KR:T00003": 2.0, "KR:T00004": 5.0,
          "KR:T00005": 1.0, "KR:T00006": 4.0}, 3)  # fmt: skip
    show("top(4) of five names, two with no score:",
         {"KR:T00001": 2.0, "KR:T00002": NAN, "KR:T00003": 4.0, "KR:T00004": NAN,
          "KR:T00005": 3.0}, 4)  # fmt: skip


if __name__ == "__main__":
    main()
