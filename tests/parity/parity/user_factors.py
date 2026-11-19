"""The user factors of spec 8.1's L1, one source for both sides: zipline user code, given
zipline's `CustomFactor` and `USEquityPricing` or `nexusbt.compat.zipline`'s (#252).

It imports neither: the engine side loads this file by its path, the zipline side through
`parity`. `today` and `assets` are not read (the shim passes the windows only).
"""

from __future__ import annotations

from typing import Any

#: L1-b's window: the adjusted close of the day and the 10 sessions before it, as seen that day
LAGS = range(11)


def momentum_12_1(self: Any, today: Any, assets: Any, out: Any, close: Any) -> None:
    """12-1 momentum over 253 rows: the close a month ago over the close a year ago."""
    out[:] = close[-22] / close[0] - 1


def sma_ratio(self: Any, today: Any, assets: Any, out: Any, close: Any) -> None:
    """The 20-row mean of the close over its 200-row mean."""
    out[:] = close[-20:].mean(axis=0) / close.mean(axis=0)


def lagged(self: Any, today: Any, assets: Any, out: Any, close: Any) -> None:
    """The adjusted close `self.lag` sessions before the computation day, as seen from it."""
    out[:] = close[-1 - self.lag]


def build(custom_factor: Any, pricing: Any, threshold: float) -> dict[str, Any]:
    """The L1-a user cases and L1-b's lags, by case id; `lag` reaches compute through `self`,
    a constant the engine puts in the term's hash."""

    def factor(name: str, compute: Any, window: int, **attrs: Any) -> Any:
        body = {"inputs": (pricing.close,), "window_length": window, "compute": compute}
        return type(name, (custom_factor,), body | attrs)()

    return {"momentum_12_1": factor("Momentum12x1", momentum_12_1, 253),
            "sma_ratio": factor("SmaRatio", sma_ratio, 200),
            "close_above": pricing.close.latest > threshold,
            **{f"lag_{k}": factor(f"Lag{k}", lagged, len(LAGS), lag=k) for k in LAGS}}  # fmt: skip
