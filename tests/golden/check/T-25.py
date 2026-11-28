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
# The cases above under `min_periods=1`; by default (#868) min_periods = W: a window with fewer
# finite cells than W is NaN.
S2 = (1.0, 2.0, 3.0, nan, 5.0)
assert isnan(S2[3])  # rows 2-4 and 3-5 hold two finite cells of 3
sma_full = [None, None, r6((S2[0] + S2[1] + S2[2]) / 3), nan, nan]

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
assert isnan(TV[1])  # by default, rows 1-2, 2-3 and 3-4 hold fewer than 2 finite cells
assert isnan(TV[2])
atv_full = [None, nan, nan, nan, r6((TV[3] + TV[4]) / 2)]

# AnnualizedVolatility(3, annualization_factor=252): nanstd(daily returns, ddof=0) * sqrt(252).
VP = (100.0, 110.0, 99.0, nan, 108.9)
v2, v3 = VP[1] / VP[0] - 1, VP[2] / VP[1] - 1  # the returns of rows 4 and 5 are NaN
vm = (v2 + v3) / 2
vol = [None, None, None, r6(sqrt(((v2 - vm) ** 2 + (v3 - vm) ** 2) / 2) * sqrt(252)),
       r6(sqrt((v3 - v3) ** 2 / 1) * sqrt(252))]  # fmt: skip
# By default rows 4 and 5 hold 2 and 1 finite returns of 3: NaN, not 0.0 (#868).
vol_short = [None, None, None, nan, nan]
VQ = (100.0, 110.0, 99.0, 108.9, 98.01)
q2, q3, q4, q5 = VQ[1] / VQ[0] - 1, VQ[2] / VQ[1] - 1, VQ[3] / VQ[2] - 1, VQ[4] / VQ[3] - 1
qm4, qm5 = (q2 + q3 + q4) / 3, (q3 + q4 + q5) / 3
vol_full = [None, None, None,
            r6(sqrt(((q2 - qm4) ** 2 + (q3 - qm4) ** 2 + (q4 - qm4) ** 2) / 3) * sqrt(252)),
            r6(sqrt(((q3 - qm5) ** 2 + (q4 - qm5) ** 2 + (q5 - qm5) ** 2) / 3) * sqrt(252)),
            ]  # fmt: skip

# RollingStd(3): nanstd(x, ddof=1); fewer than 2 values -> NaN.
RX = (2.0, 4.0, nan, 8.0, nan)
rm3, rm4 = (RX[0] + RX[1]) / 2, (RX[1] + RX[3]) / 2
rstd = [None, None, r6(sqrt(((RX[0] - rm3) ** 2 + (RX[1] - rm3) ** 2) / 1)),
        r6(sqrt(((RX[1] - rm4) ** 2 + (RX[3] - rm4) ** 2) / 1)), nan]  # fmt: skip
# By default (#868) a window needs W finite cells.
R2 = (2.0, 4.0, 6.0, nan, 8.0)
assert isnan(R2[3])  # rows 2-4 and 3-5 hold two of 3
rm = (R2[0] + R2[1] + R2[2]) / 3
rstd_full = [None, None, r6(sqrt(((R2[0] - rm) ** 2 + (R2[1] - rm) ** 2 + (R2[2] - rm) ** 2) / 2)),
             nan, nan]  # fmt: skip

# VWAP(3): sum(close * volume) / sum(volume) over the rows whose close and volume are both finite;
# no pair, or the pairs' volume summing to 0 -> NaN. The NaN closes come with NaN volumes.
WC = (10.0, nan, 12.0, 11.0, 10.0)
WV = (100.0, nan, 300.0, nan, 100.0)
vwap = [None, None, r6((WC[0] * WV[0] + WC[2] * WV[2]) / (WV[0] + WV[2])),
        r6(WC[2] * WV[2] / WV[2]),
        r6((WC[2] * WV[2] + WC[4] * WV[4]) / (WV[2] + WV[4]))]  # fmt: skip
# A NaN close with a volume: rows 2 and 4 are out of both sums.
YC = (10.0, nan, 12.0, nan, 11.0)
YV = (100.0, 300.0, 300.0, 200.0, 0.0)
vwap_pairs = [None, None, r6((YC[0] * YV[0] + YC[2] * YV[2]) / (YV[0] + YV[2])),
              r6(YC[2] * YV[2] / YV[2]),
              r6((YC[2] * YV[2] + YC[4] * YV[4]) / (YV[2] + YV[4]))]  # fmt: skip
# Rows 1-3: no finite close, no pair. Rows 2-4 and 3-5: the one pair (12, 0), its volume 0.
ZC = (nan, nan, nan, 12.0, nan)
ZV = (100.0, 200.0, 300.0, 0.0, 400.0)
assert isnan(ZC[0])  # rows 1-3: no finite close
assert isnan(ZC[1])
assert isnan(ZC[2])
assert isnan(ZC[4])  # rows 2-4 and 3-5: (12, 0) is the only pair
assert ZV[3] == 0.0  # so the pairs' volume sums to 0: 0/0
vwap_none = [None, None, nan, nan, nan]
# By default (#868) a window needs W pairs.
VC = (10.0, 11.0, 12.0, nan, 10.0)
VV = (100.0, 200.0, 300.0, 100.0, 100.0)
assert isnan(VC[3])  # rows 2-4 and 3-5 hold two pairs of 3
vwap_full = [None, None,
             r6((VC[0] * VV[0] + VC[1] * VV[1] + VC[2] * VV[2]) / (VV[0] + VV[1] + VV[2])),
             nan, nan]  # fmt: skip

# RSI(4): d = diff(x); up = nanmean(clip(d, 0, inf)); dn = |nanmean(clip(d, -inf, 0))|.
QX = (10.0, 12.0, 11.0, 13.0, nan)
up4, dn4 = (2.0 + 0.0 + 2.0) / 3, abs((0.0 - 1.0 + 0.0) / 3)  # d = 2, -1, 2
up5, dn5 = (0.0 + 2.0) / 2, abs((-1.0 + 0.0) / 2)  # d = -1, 2, NaN
assert (QX[1] - QX[0], QX[2] - QX[1], QX[3] - QX[2]) == (2.0, -1.0, 2.0)
assert isnan(QX[4] - QX[3])
rsi = [None, None, None, r6(100 - 100 / (1 + up4 / dn4)), r6(100 - 100 / (1 + up5 / dn5))]
# By default (#868) a window needs W - 1 = 3 finite differences: row 5 has two.
rsi_full = [None, None, None, r6(100 - 100 / (1 + up4 / dn4)), nan]

# MaxDrawdown(W): max((cummax(x) - x) / cummax(x)), NaN left out. 50 is outside the later windows.
MX = (50.0, 10.0, 12.0, 9.0, 11.0)
mdd4 = [None, None, None, r6((MX[0] - MX[3]) / MX[0]), r6((MX[2] - MX[3]) / MX[2])]
mdd3 = [None, None, r6((MX[0] - MX[1]) / MX[0]), r6((MX[2] - MX[3]) / MX[2]),
        r6((MX[2] - MX[3]) / MX[2])]  # fmt: skip
NX = (nan, 12.0, 9.0, nan, 6.0)
mdd3n = [None, None, r6((NX[1] - NX[2]) / NX[1]), r6((NX[1] - NX[2]) / NX[1]),
         r6((NX[2] - NX[4]) / NX[2])]  # fmt: skip
assert isnan(NX[0])  # by default (#868) each window of NX holds a NaN
assert isnan(NX[3])
mdd3n_full = [None, None, nan, nan, nan]

# Latest: x[-1].
LX = (10.0, nan, 12.0, nan, 14.0)
latest = [LX[0], LX[1], LX[2], LX[3], LX[4]]

# In file-name order, then the order of the cases in each file.
ROWS = (
    case("AnnualizedVolatility",
         "AnnualizedVolatility(3, annualization_factor=252, min_periods=1)", {"close_tr": VP}, vol),
    case("AnnualizedVolatility", "AnnualizedVolatility(3, annualization_factor=252)",
         {"close_tr": VP}, vol_short),
    case("AnnualizedVolatility", "AnnualizedVolatility(3, annualization_factor=252)",
         {"close_tr": VQ}, vol_full),
    case("AverageDollarVolume", "AverageDollarVolume(2)", {"close": AC, "volume": AV}, adv),
    case("AverageTradedValue", "AverageTradedValue(2, min_periods=1)", {"value_traded": TV}, atv),
    case("AverageTradedValue", "AverageTradedValue(2)", {"value_traded": TV}, atv_full),
    case("DailyReturns", "DailyReturns()", {"close_tr": DP}, daily),
    case("ExponentialWeightedMovingAverage", "EWMA(3, decay_rate=0.5)", {"close": EX}, ewma),
    case("ExponentialWeightedMovingAverage", "EWMA(3, decay_rate=0.5)", {"close": FX}, ewma_nan),
    case("Latest", "Price.close.latest", {"close": LX}, latest),
    case("MaxDrawdown", "MaxDrawdown(4)", {"close_tr": MX}, mdd4),
    case("MaxDrawdown", "MaxDrawdown(3)", {"close_tr": MX}, mdd3),
    case("MaxDrawdown", "MaxDrawdown(3, min_periods=1)", {"close_tr": NX}, mdd3n),
    case("MaxDrawdown", "MaxDrawdown(3)", {"close_tr": NX}, mdd3n_full),
    case("RSI", "RSI(4, min_periods=1)", {"close_tr": QX}, rsi),
    case("RSI", "RSI(4)", {"close_tr": QX}, rsi_full),
    case("Returns", "Returns(3)", {"close_tr": RP}, returns),
    case("RollingStd", "RollingStd(3, min_periods=2)", {"close": RX}, rstd),
    case("RollingStd", "RollingStd(3)", {"close": R2}, rstd_full),
    case("SimpleMovingAverage", "SMA(3, min_periods=1)", {"close": SX}, sma),
    case("SimpleMovingAverage", "SMA(3)", {"close": S2}, sma_full),
    case("VWAP", "VWAP(3, min_periods=1)", {"close": WC, "volume": WV}, vwap),
    case("VWAP", "VWAP(3, min_periods=1)", {"close": YC, "volume": YV}, vwap_pairs),
    case("VWAP", "VWAP(3, min_periods=1)", {"close": ZC, "volume": ZV}, vwap_none),
    case("VWAP", "VWAP(3)", {"close": VC, "volume": VV}, vwap_full),
)  # fmt: skip


def cell(v: float | None) -> str:
    return "-" if v is None else str(v)


def line(r: dict[str, Any]) -> str:
    e = r["expected"]
    return "{:<64} {:>10} {:>10} {:>10} {:>10} {:>10}".format(
        r["term"], cell(e[0]), cell(e[1]), cell(e[2]), cell(e[3]), cell(e[4])
    )


if __name__ == "__main__":
    print("{:<64} {:>10} {:>10} {:>10} {:>10} {:>10}".format("term", 1, 2, 3, 4, 5))
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
    print(line(ROWS[15]))
    print(line(ROWS[16]))
    print(line(ROWS[17]))
    print(line(ROWS[18]))
    print(line(ROWS[19]))
    print(line(ROWS[20]))
    print(line(ROWS[21]))
    print(line(ROWS[22]))
    print(line(ROWS[23]))
    print(line(ROWS[24]))
