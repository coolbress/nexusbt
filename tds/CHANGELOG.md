# Changelog (nexusbt-tds)

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the
package version follows the `tds_version` it checks (`1.0.x`), tagged
`tds-v1.0.0-rc.N` then `tds-v1.0.0`.

## [Unreleased]

### Added
- TDS-M003 for a `markets` entry without `calendar_id`, `currency` or `timezone`, and TDS-M001
  for one that is not a non-empty string (TDS 3.8, 4.2): the manifest schema requires the three,
  which until now accepted any object. `tds_draft` moves to `2026-11-19`, so a package that
  names `2026-11-18` warns TDS-M017; its hashes do not change
- TDS-M017 (W) at every level: a `tds.json` with no `tds_draft`, or one naming another draft
  text than the checker implements (TDS 10.5); a package written before it still passes
- `tds_draft` in `tds.json` (TDS 4.2, 10.5): the date of the draft text a package follows,
  `2026-11-18`; `tds manifest build` and `tds import csv` write it, and a value that is not a
  `YYYY-MM-DD` date is TDS-M001. It is not in the semantic hash
- `actions.Resolution.affects`: the chosen version's `affects`, so the engine picks the events
  of `C_split` and `C_total` from the resolver's result (spec 5.3.3)
- `tds check --level full` judges TDS-V032: a gap in `sequence` within each group a `trades`,
  `quotes` or `book_deltas` dataset declares with `params.sequence_consecutive_within`, one
  warning per group; a dataset with no declaration has nothing to judge, so V032 is no longer
  `unchecked` at `full`
- `params.sequence_consecutive_within` of `trades`, `quotes` and `book_deltas` (TDS 5.6~5.8):
  TDS-M001 when it is not an array of distinct strings or names `sequence`, and TDS-S001 at the
  `schema` level for a listed column absent from a file (a partition column excepted)
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
- `tds hash` takes a column's type tag from the schema file wherever the schema file types the
  column, as `tds check --level schema` does; a `tds.json` `columns[].type` that differs from it
  (TDS-S002) no longer changes the dataset's `value_sha256` (TDS 4.5 step 3)
