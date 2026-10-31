# 2. Read TDS packages directly, no bundle step; one stable key `instrument_id`

- Status: Accepted
- Date: 2026-10-28
- Spec: §1.2, §3.2, §4

## Context

An ingest step forces users to reshape data for the engine. Re-numbering ids per snapshot breaks chunk reuse and contradicts snapshot partition reuse.

## Decision

The engine reads a TDS package (Parquet + `tds.json`) as it is and builds integer indexes in memory. Files carry only `instrument_id`, an asset-neutral opaque string. No aliases; external names are mapped only at import (`rename=`, `tds import csv` mapping).

## Consequences

A dictionary-to-index mapping cost at read time (measured in M1). One name everywhere: data, internals, outputs, API, docs.
