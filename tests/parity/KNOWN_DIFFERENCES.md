# Known differences from zipline 3.2.1

Spec 8.1: zipline's known bugs are not taken as the answer. A difference listed here is not a
parity failure; when the two engines differ elsewhere, the hand calculation (T-25) decides.

## zipline bugs worked around in `tests/parity`

- `InMemoryDailyBarReader.get_value` reads `self.frames`, which the class never sets (it keeps
  `_frames`). `parity.bundle.ScaledDailyBarReader` gives it `frames`.
- zipline's daily bundle stores a price as `round(price x 1000)` cast to a uint32. Its
  `winsorise_uint32` checks the price before the x 1000, so a price past about 4,294,967 is
  cast out of range without an error and read back wrong (the value depends on the platform).
  An instrument whose prices pass that is kept with a per-instrument price scale
  (x 1/10^n), undone by `ScaledDailyBarReader`; the evidence file lists the scaled instruments
  as a limit of the comparison (RV-Q08).

## Differences in meaning

- `window_safe` (#252 Decisions, 2026-11-19): `nexusbt.compat.zipline` takes the attribute and
  gives it no meaning; the engine's E17 degree rule alone refuses a Factor read over a window
  (a price level is refused, a ratio and a rank of prices pass). zipline refuses by the flag, so
  a ratio `CustomFactor` without it passes in the engine and is refused by zipline.
- Spec 8.1 lists the others it knows, compared around as it says: missing values under Filter
  `~`, tie-breaking of `top` and `rank("ordinal")`, and `VWAP` with a NaN close and a volume.

## Found by L1 (ADR 0045, spec 8.1, #252)

`tests/parity_compare/test_L1.py` computes each set from the package's corporate actions and
calendar, and fixes for each case and market the cells compared, compared through m, and left
out (`EXPECTED`); the evidence file carries them.

- (A) The day before an ex-date: zipline's value for D carries the adjustments effective at
  D; the engine row `prev_session(D)` is fixed before them (ADR 0044). Compared, not left out:
  a price level as the engine's x that session's price factor m = zipline (split factors only
  for the cases read from the bundle without dividends), a ratio as it is, `close > X` as the
  engine's close x m > X.
- (B) Terms not known at the row: in row t's window the engine uses the version of an event
  known at `cutoff(t)`: none before its terms are published (5.3.4), and for an amended or
  cancelled event the version known then (5.3.3a); zipline applies the final version from the
  ex-date. A cell whose window holds the ex-date of an event not yet final at the row's
  decision is left out (for the cases read without dividends, share events only).
- (C) A Filter on a missing input, `close > X` on a halted bar: unknown in the engine, false in
  zipline, the kind of `~`'s. Left out.
- Not a difference: the engine's rows on and after an instrument's last session have no
  zipline row (zipline's D is the next session, when the asset is gone). Their number is
  fixed (`ENGINE_ONLY`) and they are not compared.
