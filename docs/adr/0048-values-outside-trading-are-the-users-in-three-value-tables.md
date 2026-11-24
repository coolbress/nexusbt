# 48. Values outside trading are the user's, in three value tables

- Status: Accepted
- Date: 2026-11-24
- Supersedes: [ADR 0004](0004-the-producer-resolves-fundamentals-the-engine-only.md)
- Spec: §4, §5.1.4, §5.3; TDS chapter 5

## Context

The spec and TDS read each kind of non-price data by its own rule: fundamentals through producer-resolved intervals (ADR 0004), panels by their latest period, classifications on two time axes, eligibility without carry, macro series by vintage, events by their own terms, external frames by `known_on`. None of those readers was built. A user had to learn a different kind, and often a different time rule, for each value they wanted to use.

## Decision

Two parts (#725 Decisions 204 to 229). The engine is strict only about what trading and returns need: bars, instruments, calendar, splits and dividends, delistings, symbol periods. Every other value is the user's, given in three value tables of four words: per symbol and date (`symbol, date, item, value`), market-wide by date (`date, item, value`), per symbol without a date (`symbol, item, value`). Each is read as `nx.Item.<name>` under one date rule (ADR 0047), with two optional per-item declarations: a kind (per-share or share count, scaled by the engine's split ratios) and a carry. The tools stop on an unknown symbol, a key given twice, an item name outside the rule, an item in two tables, or an empty key cell, and check nothing else about the values.

## Considered options

- **Producer-resolved state per data kind (ADR 0004).** Accurate where a producer resolves it, but no producer publishes it, and each kind keeps its own reader and rule.
- **One table with a declared shape.** One kind, but its key would change with the declaration; three kinds keep one key per schema file.

## Consequences

`fundamentals_events`, `fundamentals_state`, `feature_panels`, `series_observations`, `events`, `share_counts`, `universe_membership`, `eligibility_daily`, the dictionary's items and the label path leave TDS and the spec, with `Fund`, `Panel`, `Macro`, `Events`, `from_parquet` and `from_frame`. Restatements, consolidated or separate statements, sums and units become the user's, documented and not checked; T007 retires with nothing in its place.
