# 33. The default label is the economic holding return

- Status: Accepted
- Date: 2026-10-28
- Spec: §5.8

## Context

Adjusted-price ratios reinvest at the theoretical ex price and differ from real holding returns (100 → dividend 10 → 100 is 10%, not 11.1%).

## Decision

Default `fwd_return` reinvests dividends at the ex-date close (CRSP style); `fwd_return_adj` is for comparison. Three label times (start, end, available) purge labels at segment ends.

## Consequences

Label construction needs dividend amounts and their availability.
