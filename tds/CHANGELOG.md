# Changelog (nexusbt-tds)

The format is [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the
package version follows the `tds_version` it checks (`1.0.x`), tagged
`tds-v1.0.0-rc.N` then `tds-v1.0.0`.

## [Unreleased]

### Added
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
