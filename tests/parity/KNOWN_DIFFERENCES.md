# Known differences from zipline 3.2.1

Spec 8.1: zipline's known bugs are not taken as the answer. A difference listed here is not a
parity failure; when the two engines differ elsewhere, the hand calculation (T-25) decides.

## zipline bugs worked around in `tests/parity`

- `InMemoryDailyBarReader.get_value` reads `self.frames`, which the class never sets (it keeps
  `_frames`). `parity.bundle.ScaledDailyBarReader` gives it `frames`.
- zipline's daily bundle stores a price as `round(price x 1000)` in a uint32 and zeroes a row
  past it. An instrument whose prices pass that is kept with a per-instrument price scale
  (x 1/10^n), undone by `ScaledDailyBarReader`; the evidence file lists the scaled instruments
  as a limit of the comparison (RV-Q08).

## Differences in meaning

- `window_safe` (#252 Decisions, 2026-11-19): `nexusbt.compat.zipline` takes the attribute and
  gives it no meaning; the engine's E17 degree rule alone refuses a Factor read over a window
  (a price level is refused, a ratio and a rank of prices pass). zipline refuses by the flag, so
  a ratio `CustomFactor` without it passes in the engine and is refused by zipline.
- Spec 8.1 lists the others it knows, compared around as it says: missing values under Filter
  `~`, tie-breaking of `top` and `rank("ordinal")`, and `VWAP` with a NaN close and a volume.
