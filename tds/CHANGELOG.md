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
  (#752, TDS 5.6): a dataset of one of those kinds is now a kind with no schema file, so no
  column, key or sort rule is read for it and it raises nothing, and a package declaring one of
  those profiles gets TDS-M007. No schema is `experimental` now; TDS-M015 stays for a kind that
  comes later

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
