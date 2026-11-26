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
- `environment.machine_id` is the same in every process on a host (#635). On a host
  with no machine-id file where Python finds no hardware address (seen on macOS), it
  was the hash of a random number chosen anew in each process; it is now the hardware
  UUID on macOS, and `"unknown"` where no host id can be read. A run sealed on any
  macOS host before this fix records an id that is no longer this host's (the random
  number, or the network address used before), so once `rerun` lands
  (#250) it will refuse such a run as another machine's (E31): read its `source/`,
  then run it with `nx.rerun(id, trust=True)` or `nexusbt rerun ID --trust`.
