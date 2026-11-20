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

### Fixed
- `environment.machine_id` is the same in every process on a host (#635). On a host
  with no machine-id file where Python finds no hardware address (seen on macOS), it
  was the hash of a random number chosen anew in each process; it is now the hardware
  UUID on macOS, and `"unknown"` where no host id can be read. A run sealed on any
  macOS host before this fix records an id that is no longer this host's (the random
  number, or the network address used before), so once `rerun` lands
  (#250) it will refuse such a run as another machine's (E31): read its `source/`,
  then run it with `nx.rerun(id, trust=True)` or `nexusbt rerun ID --trust`.
