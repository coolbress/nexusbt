"""G-60 by arithmetic only (spec 8.2, 5.7): metrics by hand and PSR's kurtosis convention.

Run it: `uv run python tests/golden/check/G-60.py` prints one line per number, PSR 0.759233
among them, and the line "excess-kurtosis value 0.915240 is wrong". No loops, classes or engine
imports (`tests/golden/test_handcalc_self.py`); the 60 returns of the PSR series are 30 of each
of two values, so every moment is written as 30 x one term + 30 x the other.
"""

from math import erf, sqrt
from typing import Any

ANNUAL = 252  # 5.7: the one annualisation of volatility, Sharpe and Sortino


def phi(z: float) -> float:
    """The standard normal distribution function."""
    return (1 + erf(z / sqrt(2))) / 2


# Series `nav` (rf 0): NAV_0 100, then 110, 99, 108.9 inside one calendar month.
NAV_0, NAV_1, NAV_2, NAV_3 = 100.0, 110.0, 99.0, 108.9
r1, r2, r3 = NAV_1 / NAV_0 - 1, NAV_2 / NAV_1 - 1, NAV_3 / NAV_2 - 1
mean = (r1 + r2 + r3) / 3
std = sqrt(((r1 - mean) ** 2 + (r2 - mean) ** 2 + (r3 - mean) ** 2) / (3 - 1))  # ddof = 1
sharpe = mean / std * sqrt(ANNUAL)
# Sortino: target 0, the squared shortfalls averaged over every observation.
downside = sqrt((min(r1, 0) ** 2 + min(r2, 0) ** 2 + min(r3, 0) ** 2) / 3)
sortino = mean / downside * sqrt(ANNUAL)
# Maximum drawdown: each NAV over the highest NAV so far, NAV_0 included.
max_drawdown = min(
    NAV_0 / NAV_0 - 1,
    NAV_1 / max(NAV_0, NAV_1) - 1,
    NAV_2 / max(NAV_0, NAV_1, NAV_2) - 1,
    NAV_3 / max(NAV_0, NAV_1, NAV_2, NAV_3) - 1,
)
month_return = (1 + r1) * (1 + r2) * (1 + r3) - 1
assert round(month_return, 6) != round(r1 + r2 + r3, 6), "a month compounds, it does not add"

# Series `psr`: 0.02 and 0.00 alternating, 30 of each, against SR* = 0.9 (daily).
HIGH, LOW, EACH, T, SR_STAR = 0.02, 0.00, 30, 60, 0.9
mu = (EACH * HIGH + EACH * LOW) / T
up, down = HIGH - mu, LOW - mu
sr = mu / sqrt((EACH * up**2 + EACH * down**2) / (T - 1))  # daily, ddof = 1
m2 = (EACH * up**2 + EACH * down**2) / T  # population moments, no bias correction
m3 = (EACH * up**3 + EACH * down**3) / T
m4 = (EACH * up**4 + EACH * down**4) / T
skewness, kurtosis_raw = m3 / m2**1.5, m4 / m2**2
psr = phi((sr - SR_STAR) * sqrt(T - 1) / sqrt(1 - skewness * sr + (kurtosis_raw - 1) / 4 * sr**2))
# The wrong convention: excess kurtosis (raw - 3) where the formula takes raw kurtosis.
excess = kurtosis_raw - 3
psr_excess = phi((sr - SR_STAR) * sqrt(T - 1) / sqrt(1 - skewness * sr + (excess - 1) / 4 * sr**2))
assert round(psr_excess, 6) != round(psr, 6), "the two conventions give different numbers"


def row(series: str, metric: str, value: float) -> dict[str, Any]:
    return {"series": series, "metric": metric, "value": round(value, 6)}


ROWS = (
    row("nav", "return_1", r1),
    row("nav", "return_2", r2),
    row("nav", "return_3", r3),
    row("nav", "mean", mean),
    row("nav", "std", std),
    row("nav", "sharpe", sharpe),
    row("nav", "sortino", sortino),
    row("nav", "max_drawdown", max_drawdown),
    row("nav", "month_return", month_return),
    row("psr", "observations", T),
    row("psr", "sr_daily", sr),
    row("psr", "skewness", skewness),
    row("psr", "kurtosis_raw", kurtosis_raw),
    row("psr", "psr", psr),
    row("psr", "psr_with_excess_kurtosis_wrong", psr_excess),
)


def line(r: dict[str, Any]) -> str:
    return "{series:<4} {metric:<31} {value:>10.6f}".format(**r)


if __name__ == "__main__":
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
    print("PSR(SR* = {}) {:.6f}".format(SR_STAR, ROWS[13]["value"]))
    print("excess-kurtosis value {:.6f} is wrong".format(ROWS[14]["value"]))
