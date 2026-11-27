# Changelog

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
versions follow [Semantic Versioning](https://semver.org/).

> This file is for a project that makes releases. *Keep a Changelog* collects
> entries per release; a project that never tags has no unit to fill, and an
> empty changelog looks like information without being any. Delete the file
> in that case. When releases start, add a section per version and a compare
> link for each: `[1.0.0]: https://github.com/<owner>/<repo>/compare/v0.9.0...v1.0.0`

## [Unreleased]

### Added
- Initial skeleton
- `@nx.filter(window=..., inputs=..., mask=None)` makes a Filter from a window function that
  returns bool `(n_alive,)` (#620). A cell is unknown where any cell of the instrument's input
  windows is NaN; a result of another dtype or shape is E8. It is called, hashed and checked
  as an `@nx.factor` is: `.function`, the E16 for a call with an array, E8 before the window,
  E24 for a global array, helpers and bound values in the graph hash.
- `@nx.classifier(window=..., inputs=..., mask=None)` makes a Classifier from a window function
  that returns integer codes `(n_alive,)` (#620): -1 is the missing group, left out by
  `groupby` and counted `UnknownGroup`, as is a cell outside `mask` or before the window; any
  other negative code, a code int32 cannot hold, or a result of another dtype (a float, a bool)
  or shape is E8. It is called, hashed and checked as `@nx.filter` is. A classifier that
  returns strings is E8 until its code table comes (#818).
- `rerun` compares the run's captured engine and project `uv.lock` with the current ones
  (#637). When either differs, or a project lock is on one side only, the comparison line
  starts `environment differs;`. The tables' values are then compared cell by cell within
  8.1's L1-a tolerance, `|a−b| ≤ 1e-9 + 1e-9·|b|`; their bytes are not compared.
  `nexusbt rerun` exits 0 within the tolerance and 4 beyond it. With the same locks the
  comparison is exact, as before. `--env`, which rebuilds the run's environment, moved
  to #820.

### Changed
- `@nx.factor(dtype=...)` takes `"float64"` only, the dtype a Factor's values are in; any
  other value (`"float32"`, `"int64"`, a misspelling) is now refused when the term is built
  (`ConfigError`, E16), where before it was taken, ignored, and gave the term a graph hash of
  its own (#638). Code that writes another value gets E16: write `dtype="float64"` or leave
  `dtype` out; the graph hash of either is as before.

### Removed
- `nx.Panel`, `nx.Label` and `nexusbt.pipeline.Fund`, the config tables `[panels]` and
  `[fund]`, and the reading of `dictionary/columns`' `is_label` (#752). A `nexusbt.toml`
  that still has `[panels]` or `[fund]` is refused (E16); remove the table. A package's
  values outside trading become value-table items (`nx.Item`, spec 5.3.5), which come
  later. `nexusbt stubs` writes `Price` and `Meta` only.
- `Meta.sector`, `Meta.industry`, `Meta.is_financial`, `Price.shares_out` and
  `Price.market_cap` (now E7, "has no column"); a sector or a share count becomes a
  value-table item (`nx.Item`, spec 3.2, 5.3.5a), which comes later (#752).
- The config keys `[data] share_count_kinds`, `[universe] investable` and
  `eligibility_rule`, `[dividends] missing_pay_date`, `fallback_pay_lag_days`,
  `estimate_window_years` and `estimate_min_obs`, and `[meta] sector` and `industry`; one
  still written is refused (E16): remove it. The market rules packs lose `[dividends]`.
- `MissingPayDatePolicy`, and the retired errors `PointInTimeError` (E3) and
  `DatasetShapeError` (E47); their numbers are not reused (#752).
- `nx.screen`'s result now says `universe: listed (the default universe comes with T2.4)`.
- The engine no longer reads `share_counts`, `fundamentals_events`, `fundamentals_state`,
  `universe_membership`, `eligibility_daily`, `feature_panels` or `label_panels` (their
  `ENGINE_COLUMNS` rows left), and supports the profiles `tds:minimal-daily` and
  `tds:equity-daily-core` only (#752).
- The engine no longer reads `classifications` (its `ENGINE_COLUMNS` row left): the price
  grid comes from `instruments.tick_size`, the `market_rules` rule set
  `instruments.tick_rule_id` names, the market's `tick_band` rows or the rules pack (#752). The
  US per-instrument tick assignment from 2027-11-01 has no source until #802 decides one; an
  instrument without one keeps the pack's US 0.01.

### Fixed
- The `.function(...)` call E16 shows for a user Factor called with an array writes a bound
  NaN or infinity as `float("nan")`, `float("inf")` or `float("-inf")`, also inside a bound
  tuple or frozenset, so the call runs as pasted (#624).
- A constant a library wrapper's closure holds and one the function it wraps reads under the
  same name are both in the graph hash, so editing either changes it (#797): a chain of names
  that starts inside a wrapper is marked `@` (`…inner[fast>@g]:k` beside `…inner[fast>g]:k`).
  Every key that carries a chain in brackets (#689: two objects that would share a key) and
  whose chain goes into a wrapper changes with it: stacked wrappers' `u.stacked[u.stacked>f]:…`
  is now `u.stacked[u.stacked>@f]:…`, two wrappers each holding a factory's helper as `g` give
  `[fa>@g]` and `[fb>@g]`, and a wrapper reached through a helper `[mid>fast>@g]`. The hash of
  such a function moves once more; a key with no brackets, and so a function with no such
  collision, is unchanged.
- A user function that reads a helper kept in `__wrapped__` by an object that is not a Python
  function, such as an instance of a library's class (`joblib.Memory.cache`'s), is E24 with
  the L1 cache off, the message naming the function that reads it and the class (#695). Only
  `functools.lru_cache`'s and `functools.cache`'s wrappers and `numba.njit`'s dispatcher stay
  pure (`numba.jit` is that dispatcher too). Also E24 now: an instance of a library's class
  that holds no state; numba's other wrappers, such as `numba.vectorize`'s, `numba.cfunc`'s
  and `numba.cuda.jit`'s; and a `staticmethod` object read as a global. Call the undecorated
  function inside the term.
- `environment.machine_id` is the same in every process on a host (#635). On a host
  with no machine-id file where Python finds no hardware address (seen on macOS), it
  was the hash of a random number chosen anew in each process; it is now the hardware
  UUID on macOS, and `"unknown"` where no host id can be read. A run sealed on any
  macOS host before this fix records an id that is no longer this host's (the random
  number, or the network address used before), so once `rerun` lands
  (#250) it will refuse such a run as another machine's (E31): read its `source/`,
  then run it with `nx.rerun(id, trust=True)` or `nexusbt rerun ID --trust`.
- A run saved from an entry file outside the project folder reruns when `multiprocessing`
  was imported during it (#644). That import gives the entry module a second name,
  `__mp_main__`, which was recorded in `source.outside` as an outside module that no rerun
  could find again by its name, so every rerun of such a run was refused (E15). This
  happened on Linux, where a library imports it, since `source.outside` came in (#250). The
  name is no longer recorded, and a run that recorded it is read without it.
