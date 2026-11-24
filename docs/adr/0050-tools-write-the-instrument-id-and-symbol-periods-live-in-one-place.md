# 50. The tools write the instrument id, and symbol periods live in one place

- Status: Accepted
- Date: 2026-11-24
- Amends: [ADR 0002](0002-read-tds-packages-directly-no-bundle-step-one-stable.md)
- Spec: §5.3.6, §4.6

## Context

ADR 0002 keeps one stable key, `instrument_id`, and says external names are mapped only at import. It does not say who writes the key, what happens to it when a symbol changes or is reused, or which symbol a user sees. A user's files name instruments by symbol, and a symbol may change, or pass to another instrument after a delisting. The owner's two-part design (#725 Decisions 204 to 263) gives the user facts and the tools the work, with no fact the user did not give.

## Decision

The stored key stays `instrument_id`. The tools write it as `<MIC>:<ticker>_<YYYYMMDD>`, from the earliest symbol and its `list_date`, else the date of the instrument's first bar. A symbol change that merges no two instruments changes no key; a merge keeps the earlier-listed instrument's key; the same input gives the same key. Extending a history back without `list_date` may move a key, and the build report names it. There is no ledger of keys across packages (#725 Decisions 206, 207).

Symbol periods live in `instrument_symbols` only, one period at least for every instrument, also one whose symbol never changed. `symbol_changes.csv` and `securities.csv` are inputs of the tools, not dataset kinds. Rows given under an old symbol and dated before the change move to its instrument. `corporate_actions` loses `symbol_change`: one fact, one place (#725 Decisions 208, 209).

A result table's `symbol` is the symbol in use on the row's date; a symbol with no date (a row of the per-symbol value table, a symbol in code or in a setting) means its latest owner. A result may add the optional column `latest_symbol` (#725 Decision 209; #752's Decisions).

Reuse: an instrument list with listing periods (`symbol`, `list_date`, `delist_date`, not overlapping) splits one symbol into two instruments. The periods only assign ownership; `delistings` keeps the delisting, and a disagreement between the two stops the tool. Without listing periods the tool asks only on a long price gap (#725 Decisions 210, 211).

## Considered options

- **The symbol as the stored key.** What users write, but a change or a reuse would move or merge a key and every row under it.
- **A ledger of keys kept across packages.** Stable across rebuilds, but it is state outside any package that every user would have to carry.
- **A question on every undeclared symbol change.** Thorough, but it would flood the user; a narrower question is an issue of its own.

## Consequences

ADR 0002's one stored name stands; the names a user reads in results are symbols, resolved through `instrument_symbols` by date. A key is reproducible from the same input, not from a different one. A reused symbol without listing periods is one instrument unless the user answers the price-gap question.
