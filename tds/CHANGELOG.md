# Changelog (nexusbt-tds)

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the
package version follows the `tds_version` it checks (`1.0.x`), tagged
`tds-v1.0.0-rc.N` then `tds-v1.0.0`.

## [Unreleased]

### Removed
- TDS-V031 (a crossed book after reconstruction) and TDS-V032 (a gap in `sequence` numbers) are
  retired, their numbers not reused, before `trades`, `quotes` and `book_deltas` leave the
  standard (#752); `tds check` lists neither as `unchecked` at any level
- TDS-V030 (a locked or crossed quote) and TDS-T008 (`ts_recv` before `ts_event`) are retired,
  their numbers not reused (#752); `tds check` lists neither as `unchecked` at any level
- `params.sequence_consecutive_within` is no longer read: its JSON-schema shape (TDS-M001) and its
  TDS-S001 for a listed column absent from a file are gone (#752)
- The schema files of `trades`, `quotes`, `book_deltas`, `book_snapshots`, `market_statistics`,
  `calendar_segments`, `trading_status_events`, `rates`, `roll_calendar`,
  `option_chain_snapshots`, `funding_rates` and `reference_prices`, and the profiles
  `tds:l1-ticks`, `tds:l2-book`, `tds:l3-book`, `tds:futures`, `tds:options` and `tds:crypto`
  (#752, TDS 5.6): a dataset of one of those kinds is now a kind with no schema file, so its
  columns, key and sort are not checked, while the rules that read any kind still apply (R001
  on its `instrument_id`, for one); a `calendar_segments` dataset now leaves T006 unchecked and
  R002 no longer reads its `calendar_id`. A package declaring one of those profiles gets
  TDS-M007. No schema is `experimental` now; TDS-M015 stays for a kind that
  comes later
- TDS-T007 (a fact available before `period_end`), TDS-R007 (`selected_fact_id` not in
  `fundamentals_events`), TDS-V041 (an `events` row with no id) and TDS-V050 (a label column
  also a feature column) are retired, their numbers not reused, before their kinds leave (#752);
  `tds check` lists none of them as `unchecked` at any level
- TDS-V020 no longer asks for `issuer_id` on an `equity` row where
  `tds:equity-daily-research@1.0` or `tds:pit-fundamentals@1.0` is declared (#725 Decision 255);
  it still asks each `asset_class` for its columns
- TDS-T001, TDS-T003, TDS-T004 and TDS-T012 no longer read the user-data kinds (#752): T001
  reads bars only (not `events`), T003 `market_rules` only (not `fundamentals_state`), T004 and
  T012 neither `fundamentals_state` nor `universe_membership`; `classifications`,
  `instrument_symbols`, `instrument_xref` and `market_rules` are judged as before. The
  conformance cases TDS-T001, TDS-T003, TDS-T004, TDS-K001 and TDS-S005 are rewritten on bars
  and `market_rules`
- TDS-R009 (an `item` not in `dictionary/items`, a panel column not in `dictionary/columns`) is
  retired, its number not reused, before `dictionary/items` and the panels leave (#752); `tds
  check` lists it as `unchecked` at no level. TDS-K003 and TDS-D004 no longer read a panel's
  `period`: a panel's K003 is `unchecked`, and D004 no longer compares its `coverage` `ts_min`
  and `ts_max`. `dictionary/columns` stays
- The schema files of `events`, `series_observations` and `dictionary/items`, and the profiles
  `tds:equity-daily-research`, `tds:pit-fundamentals`, `tds:bitemporal` and `tds:alt-events`
  (#752, TDS 5.6, engine specification 4.3): a dataset of one of those kinds
  is now a kind with no schema file, so its columns, key and sort are not checked and at `full`
  TDS-H002, H003 and H004 are `unchecked` (no value hash without its types), while the rules
  that read any kind still apply; a package declaring one of those profiles gets TDS-M007
- The profile `tds:intraday-bars@1.0` (#752, engine specification 4.3): a package declaring it
  gets TDS-M007. Minute bars themselves are checked as before, and `freq<1d` still picks the
  intraday key of `bars` (TDS 5.5)
- The schema file of `instrument_xref` (#752, TDS 5.3, 5.6): a dataset of that kind is now a
  kind with no schema file, so its columns, key and sort are not checked, `tds hash --write`
  stops on it (no value hash without its types) and at `full` TDS-H002, H003 and H004 are
  `unchecked`; TDS-T004 no longer reads its validity intervals, and TDS-T006 is `unchecked` on
  it, as on any kind without an availability rule, where until now it was timeless and never
  judged; `tds manifest build` no longer names its folder's kind and drafts an `availability`
  TODO for it
- The schema files of `share_counts`, `fundamentals_events`, `fundamentals_state`,
  `universe_membership`, `eligibility_daily`, `feature_panels` and `label_panels`, and the
  profile `tds:panels` (#752, TDS 5.6, 5.14, 5.17, 5.18, 5.20, 5.25, 7): a dataset of one of
  those kinds is now a kind with no schema file (its columns, key and sort are not checked,
  `tds hash --write` stops on it); a package declaring `tds:panels` gets TDS-M007
- `dictionary/columns` loses `is_label` (#752, TDS 4.4): a file that still holds it gets no
  finding, and the dataset's value hash no longer covers the column, so a package hashed with it
  no longer matches its recorded hash (no package in this repository has one)
- `corporate_actions.kind` loses `symbol_change` (#752, TDS 5.11; symbol periods are
  `instrument_symbols`'s): a row holding it is TDS-S006, an error, as a value outside a closed
  list

### Added
- TDS-M010 at the `schema` level for an `instruments.market` not declared in `markets` (TDS 3.8,
  8.2), one finding per market naming its first instrument; until now M010 read only the
  `market=` values of listed paths and `coverage.by_market`
- TDS-M003 for a `markets` entry without `calendar_id`, `currency` or `timezone`, and TDS-M001
  for one that is not a non-empty string (TDS 3.8, 4.2): the manifest schema requires the three,
  which until now accepted any object. `tds_draft` moves to `2026-11-19`, so a package that
  names `2026-11-18` warns TDS-M017; its hashes do not change. `tds import csv` refuses a
  mapping whose `market` lacks one of the three (until now only `code` was needed), so it no
  longer writes a package the checker refuses
- TDS-M017 (W) at every level: a `tds.json` with no `tds_draft`, or one naming another draft
  text than the checker implements (TDS 10.5); a package written before it still passes
- `tds_draft` in `tds.json` (TDS 4.2, 10.5): the date of the draft text a package follows,
  `2026-11-18`; `tds manifest build` and `tds import csv` write it, and a value that is not a
  `YYYY-MM-DD` date is TDS-M001. It is not in the semantic hash
- `actions.Resolution.affects`: the chosen version's `affects`, so the engine picks the events
  of `C_split` and `C_total` from the resolver's result (spec 5.3.3)
- `tds check` checks `tds.json` against its JSON schema, `tds/schemas/manifest/1.0.json`, at every
  level: TDS-M001 for a field of another shape, a `columns[].type` or `partitioning[].type` that is
  not a TDS type name (`ts_us/ns`, `""` and `null` included; until now a declaration the checker did not
  know counted as none), and a column name listed twice in a dataset, each with its JSON path
- `dictionary/items` has an optional `freq` column (TDS 4.4, an item's own cadence): the value
  hash takes it where a file writes it, so two dictionaries that differ only in an item's `freq`
  no longer hash the same; a dictionary without the column keeps its value hash
- `tds check --level schema` checks a column the schema file leaves untyped, and an `x_` column,
  against the type `tds.json` `columns[]` declares for it: TDS-S002 when the file's column is
  another type, TDS-S004 when a declared `ts_us` or `ts_ns` column is in another unit or not UTC
- `tds check --level full` judges S006, S007 and S009 from the rows: a value outside an enum that
  lies between a row group's minimum and maximum, and a NaN in a float column, are found there
  and no longer `unchecked`; TDS-M015 warns of a dataset with an `experimental` schema at every
  level, and is a pass, not `unchecked`, when there is none
- `tds manifest build PATH`: a `tds.json` draft for a folder of Parquet files, with a `TODO` list
  of what a person fills in; a folder that holds several datasets of one kind is drafted as one
  dataset per `tds.dataset` name the files state, else one per `freq=` value (`bars_1d` at
  `bars/freq=1d`; so too when the name they state is the kind), and any other mix of partition
  keys, or of files in the folder itself with partition folders, is named in `TODO`
- Package skeleton with the `tds` entry point

### Changed
- `tds hash` orders `bars` whose `freq` does not meet `freq<1d` by the daily key, as the key
  checks K001 and K002 do (TDS 5.5); until now only `freq` `1d` took it. The `value_sha256` and
  `semantic_sha256` hashed before change for bars with `freq` `1w`, `1mo`, `24h`, `1440m`, `0m`,
  an unreadable value such as `1D`, `null` or no `freq`, when their `ts_start, price_type` order
  differs from `session_date`'s; such bars without `ts_start` or `price_type` now hash instead of
  failing. Bars with `freq` `1d` or `freq<1d` keep their hash (#609)
- `tds hash` takes a column's type tag from the schema file wherever the schema file types the
  column, as `tds check --level schema` does; a `tds.json` `columns[].type` that differs from it
  (TDS-S002) no longer changes the dataset's `value_sha256` (TDS 4.5 step 3)
