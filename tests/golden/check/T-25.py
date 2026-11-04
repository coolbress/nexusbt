"""T-25 by arithmetic only (spec 3.4, 8.2): the 12 built-in factors over 5 rows with NaN.

Run it: `uv run python tests/golden/check/T-25.py` prints each case's value at rows 1 to 5
(`-` = warm-up: no full window in the 5 rows). Each window is written out, one line each, with
the cells it keeps. Rounded to 6 decimals. No loops, classes or engine imports
(`tests/golden/test_handcalc_self.py`); the cases are `tests/golden/factors/<name>.yaml`.
"""

from math import isnan, nan, sqrt
from typing import Any


def r6(x: float) -> float:
    return round(x, 6)


def case(factor: str, term: str, inputs: dict[str, Any], values: list[Any]) -> dict[str, Any]:
    return {"factor": factor, "term": term, "inputs": inputs, "expected": values}


# Returns(3): x[-1]/x[0] - 1; either end NaN -> NaN.
RP = (100.0, nan, 110.0, nan, 121.0)
returns = [None, None, r6(RP[2] / RP[0] - 1), r6(RP[3] / RP[1] - 1), r6(RP[4] / RP[2] - 1)]

# DailyReturns() = Returns(2).
DP = (100.0, 110.0, nan, 121.0, 133.1)
daily = [None, r6(DP[1] / DP[0] - 1), r6(DP[2] / DP[1] - 1), r6(DP[3] / DP[2] - 1),
         r6(DP[4] / DP[3] - 1)]  # fmt: skip

# SimpleMovingAverage(3): nanmean, NaN left out.
SX = (1.0, nan, 3.0, 5.0, nan)
sma = [None, None, r6((SX[0] + SX[2]) / 2), r6((SX[2] + SX[3]) / 2), r6((SX[2] + SX[3]) / 2)]

# ExponentialWeightedMovingAverage(3, decay_rate=0.5): weights 0.5^2, 0.5^1, 0.5^0; any NaN -> NaN.
EX = (1.0, 2.0, 3.0, nan, 5.0)
W0, W1, W2 = 0.25, 0.5, 1.0
ewma = [None, None,
        r6((W0 * EX[0] + W1 * EX[1] + W2 * EX[2]) / (W0 + W1 + W2)),
        r6((W0 * EX[1] + W1 * EX[2] + W2 * EX[3]) / (W0 + W1 + W2)),
        r6((W0 * EX[2] + W1 * EX[3] + W2 * EX[4]) / (W0 + W1 + W2))]  # fmt: skip
FX = (5.0, 1.0, nan, 3.0, 4.0)  # row 4 is 8.2's 1, NaN, 3
ewma_nan = [None, None,
            r6((W0 * FX[0] + W1 * FX[1] + W2 * FX[2]) / (W0 + W1 + W2)),
            r6((W0 * FX[1] + W1 * FX[2] + W2 * FX[3]) / (W0 + W1 + W2)),
            r6((W0 * FX[2] + W1 * FX[3] + W2 * FX[4]) / (W0 + W1 + W2))]  # fmt: skip

# AverageDollarVolume(2): nansum(close * volume) / W; a NaN product counts as 0.
AC = (10.0, nan, 12.0, 11.0, 10.0)
AV = (100.0, 300.0, nan, 200.0, 500.0)
adv = [None, r6((AC[0] * AV[0] + 0) / 2), r6((0 + 0) / 2), r6((0 + AC[3] * AV[3]) / 2),
       r6((AC[3] * AV[3] + AC[4] * AV[4]) / 2)]  # fmt: skip

# AverageTradedValue(2): nanmean(value_traded); all NaN -> NaN.
TV = (1000.0, nan, nan, 3000.0, 5000.0)
atv = [None, r6(TV[0] / 1), nan, r6(TV[3] / 1), r6((TV[3] + TV[4]) / 2)]

# AnnualizedVolatility(3, annualization_factor=252): nanstd(daily returns, ddof=0) * sqrt(252).
VP = (100.0, 110.0, 99.0, nan, 108.9)
v2, v3 = VP[1] / VP[0] - 1, VP[2] / VP[1] - 1  # the returns of rows 4 and 5 are NaN
vm = (v2 + v3) / 2
vol = [None, None, None, r6(sqrt(((v2 - vm) ** 2 + (v3 - vm) ** 2) / 2) * sqrt(252)),
       r6(sqrt((v3 - v3) ** 2 / 1) * sqrt(252))]  # fmt: skip

# RollingStd(3): nanstd(x, ddof=1); fewer than 2 values -> NaN.
RX = (2.0, 4.0, nan, 8.0, nan)
rm3, rm4 = (RX[0] + RX[1]) / 2, (RX[1] + RX[3]) / 2
rstd = [None, None, r6(sqrt(((RX[0] - rm3) ** 2 + (RX[1] - rm3) ** 2) / 1)),
        r6(sqrt(((RX[1] - rm4) ** 2 + (RX[3] - rm4) ** 2) / 1)), nan]  # fmt: skip

# VWAP(3): nansum(close * volume) / nansum(volume). The NaN closes come with NaN volumes.
WC = (10.0, nan, 12.0, 11.0, 10.0)
WV = (100.0, nan, 300.0, nan, 100.0)
vwap = [None, None, r6((WC[0] * WV[0] + WC[2] * WV[2]) / (WV[0] + WV[2])),
        r6(WC[2] * WV[2] / WV[2]),
        r6((WC[2] * WV[2] + WC[4] * WV[4]) / (WV[2] + WV[4]))]  # fmt: skip

# RSI(4): d = diff(x); up = nanmean(clip(d, 0, inf)); dn = |nanmean(clip(d, -inf, 0))|.
QX = (10.0, 12.0, 11.0, 13.0, nan)
up4, dn4 = (2.0 + 0.0 + 2.0) / 3, abs((0.0 - 1.0 + 0.0) / 3)  # d = 2, -1, 2
up5, dn5 = (0.0 + 2.0) / 2, abs((-1.0 + 0.0) / 2)  # d = -1, 2, NaN
assert (QX[1] - QX[0], QX[2] - QX[1], QX[3] - QX[2]) == (2.0, -1.0, 2.0)
assert isnan(QX[4] - QX[3])
rsi = [None, None, None, r6(100 - 100 / (1 + up4 / dn4)), r6(100 - 100 / (1 + up5 / dn5))]

# MaxDrawdown(W): max((cummax(x) - x) / cummax(x)), NaN left out. 50 is outside the later windows.
MX = (50.0, 10.0, 12.0, 9.0, 11.0)
mdd4 = [None, None, None, r6((MX[0] - MX[3]) / MX[0]), r6((MX[2] - MX[3]) / MX[2])]
mdd3 = [None, None, r6((MX[0] - MX[1]) / MX[0]), r6((MX[2] - MX[3]) / MX[2]),
        r6((MX[2] - MX[3]) / MX[2])]  # fmt: skip
NX = (nan, 12.0, 9.0, nan, 6.0)
mdd3n = [None, None, r6((NX[1] - NX[2]) / NX[1]), r6((NX[1] - NX[2]) / NX[1]),
         r6((NX[2] - NX[4]) / NX[2])]  # fmt: skip

# Latest: x[-1].
LX = (10.0, nan, 12.0, nan, 14.0)
latest = [LX[0], LX[1], LX[2], LX[3], LX[4]]

# In file-name order, then the order of the cases in each file.
ROWS = (
    case("AnnualizedVolatility", "AnnualizedVolatility(3, annualization_factor=252)",
         {"close_tr": VP}, vol),
    case("AverageDollarVolume", "AverageDollarVolume(2)", {"close": AC, "volume": AV}, adv),
    case("AverageTradedValue", "AverageTradedValue(2)", {"value_traded": TV}, atv),
    case("DailyReturns", "DailyReturns()", {"close_tr": DP}, daily),
    case("ExponentialWeightedMovingAverage", "EWMA(3, decay_rate=0.5)", {"close": EX}, ewma),
    case("ExponentialWeightedMovingAverage", "EWMA(3, decay_rate=0.5)", {"close": FX}, ewma_nan),
    case("Latest", "Price.close.latest", {"close": LX}, latest),
    case("MaxDrawdown", "MaxDrawdown(4)", {"close_tr": MX}, mdd4),
    case("MaxDrawdown", "MaxDrawdown(3)", {"close_tr": MX}, mdd3),
    case("MaxDrawdown", "MaxDrawdown(3)", {"close_tr": NX}, mdd3n),
    case("RSI", "RSI(4)", {"close_tr": QX}, rsi),
    case("Returns", "Returns(3)", {"close_tr": RP}, returns),
    case("RollingStd", "RollingStd(3)", {"close": RX}, rstd),
    case("SimpleMovingAverage", "SMA(3)", {"close": SX}, sma),
    case("VWAP", "VWAP(3)", {"close": WC, "volume": WV}, vwap),
)  # fmt: skip


def cell(v: float | None) -> str:
    return "-" if v is None else str(v)


def line(r: dict[str, Any]) -> str:
    e = r["expected"]
    return "{:<50} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
        r["term"], cell(e[0]), cell(e[1]), cell(e[2]), cell(e[3]), cell(e[4])
    )


if __name__ == "__main__":
    print("{:<50} {:>10} {:>10} {:>10} {:>10} {:>10}".format("term", 1, 2, 3, 4, 5))
    print(line(ROWS[0]))
    print(line(ROWS[1]))
    print(line(ROWS[2]))
    print(line(ROWS[3]))
    print(line(ROWS[4]))
    print(line(ROWS[5]))
    print(line(ROWS[6]))
    print(line(ROWS[7]))
    print(line(ROWS[8]))
    print(line(ROWS[9]))
    print(line(ROWS[10]))
    print(line(ROWS[11]))
    print(line(ROWS[12]))
    print(line(ROWS[13]))
    print(line(ROWS[14]))
