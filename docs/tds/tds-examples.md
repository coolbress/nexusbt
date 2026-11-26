# TDS data examples: what the data you feed NexusBT looks like

This is the canonical English text; a Korean translation is in tds-examples.ko.md.

An illustrated guide based on TDS (NexusBT Data Standard) v1.4. Every number is an **example value that only shows the shape** (not real quotes or financials). The formal definition of each column is in the corresponding section of `tds-v1.4.md`.

The instrument key is `instrument_id` (e.g. `KR:005930` Samsung Electronics, `US:AAPL` Apple). All time columns are UTC.

---

## 0. At a glance

```
                ┌──────────────── one snapshot folder = one TDS package ────────────────┐
  (A) inputs    │ bars (daily bars) · corporate_actions (corporate actions)              │
  engine        │ calendar_sessions (trading days) · delistings (delistings)             │──▶ the Pipeline
  computes      │ tradability_daily (halts, admin)                                       │
                │ fx_rates (exchange rates)                                              │
                └────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Folder shape (snapshot = package)

```
snapshots/2026-11-02_buildK/
├── tds.json                                   ← list + hashes (this makes it a package)
├── instruments/part-00000.parquet
├── calendar_sessions/part-00000.parquet
├── bars/freq=1d/market=KR/year=2024/part-00000.parquet
├── bars/freq=1d/market=US/year=2024/part-00000.parquet
├── corporate_actions/part-00000.parquet
└── delistings/part-00000.parquet
```

The engine takes only this one folder path: `nx.open("snapshots/2026-11-02_buildK")`.

---

## 2. Input tables (A)

### 2-1. `bars` daily bars — instrument × trading day, raw prices

| instrument_id | session_date | open | high | low | close | volume | value_traded | obs_status |
|---|---|---|---|---|---|---|---|---|
| KR:005930 | 2024-03-28 | 80,800 | 81,900 | 80,500 | 81,700 | 18,231,000 | 1.48e12 | traded |
| KR:005930 | 2024-03-29 | 81,900 | 82,600 | 81,300 | 82,400 | 15,904,000 | 1.30e12 | traded |
| KR:000660 | 2024-03-29 | 179,000 | 184,500 | 178,200 | 183,000 | 4,512,000 | 8.22e11 | traded |
| KR:123456 | 2024-03-29 | | | | | 0 | 0 | halted |
| US:AAPL | 2024-03-28 | 171.75 | 172.23 | 170.51 | 171.48 | 65,672,700 | 1.13e10 | traded |

- Prices are **raw prices** (unadjusted). The engine computes split and dividend adjustments on the fly from the corporate action table (so that future adjustments never leak into the past).
- A halted day has a row but empty prices (`halted`).

### 2-2. `corporate_actions` corporate actions — one row per event

| event_id | instrument_id | kind | ex_date | record_date | cash_per_share | ratio_num | ratio_den | ts_announced |
|---|---|---|---|---|---|---|---|---|
| ca-0001 | KR:005930 | split | 2018-05-04 | 2018-05-03 | | 50 | 1 | 2018-01-31T07:30Z |
| ca-0002 | KR:005930 | cash_dividend | 2023-12-27 | 2023-12-28 | 361 | | | 2023-11-03T07:00Z |
| ca-0003 | US:AAPL | split | 2020-08-31 | 2020-08-24 | | 4 | 1 | 2020-07-30T20:30Z |
| ca-0004 | US:AAPL | cash_dividend | 2024-02-09 | 2024-02-12 | 0.24 | | | 2024-02-01T21:30Z |

- Splits use an **integer ratio** (50 : 1). Data with only decimal ratios is accepted only if the user allows it in the settings (v3.4).
- Dividends are **raw amounts** (the amount at the time, not adjusted for splits).
- Availability times are `ts_announced` (event made public) and `ts_terms_available` (amount or ratio final; if empty, the same as `ts_announced`). The other required columns (`ts_effective`, `pay_date_status`, `affects`, `factor_method`, `status`) are omitted from the table (TDS 5.11).

### 2-4. Other inputs (shape only)

| Table | One-row example |
|---|---|
| `calendar_sessions` | calendar_id XKRX · session_date 2024-03-29 · ts_open 2024-03-29T00:00Z · ts_close 06:30Z · session_kind regular |
| `delistings` | KR:999990 · last_trading_date 2019-07-10 · exit_date 2019-07-19 · delist_type performance · exit_value_status observed · ret_observed −0.95 |
| `tradability_daily` | KR:123456 · 2024-03-29 · status_known true · halted_full_day true · admin_status administrative |
| `fx_rates` | base USD · quote KRW · rate_kind fixing · obs_date 2024-03-29 · rate 1,346.8 · ts_available 2024-03-29T06:30Z |

---

## 3. Values outside trading

Values outside trading (fundamentals, share counts, sector codes, universes, events, macro series) are the user's, in three value tables (`tds-v1.4.md` 5.28, engine specification 5.3.5). A file holds the rows of one market and one item: its folder names both (`market=`, `item=`), so the rows carry only `instrument_id`, `date` and `value`. The user meets `instrument_id` as `symbol` and reads an item as `nx.Item.<name>`.

### 3-1. `values` — per instrument and date

`values/market=KR/item=per/part-00000.parquet`

| instrument_id | date | value |
|---|---|---|
| KR:005930 | 2024-03-14 | 12.4 |
| KR:005930 | 2024-05-16 | 13.1 |
| KR:000660 | 2024-03-14 | 8.7 |
| KR:000660 | 2024-05-16 | |

- `date` is the day the value was published, in the market's local date; it need not be a trading day (a value dated on a Saturday is used from the next session).
- KR:000660's 8.7 is carried until its empty `value` of 2024-05-16, which ends its `per` from that day.

### 3-2. `market_values` — one value for the whole market, by date

`market_values/market=KR/item=base_rate/part-00000.parquet`

| date | value |
|---|---|
| 2024-01-11 | 3.50 |
| 2024-10-11 | 3.25 |

### 3-3. `symbol_values` — per instrument, no date

`symbol_values/market=KR/item=sector/part-00000.parquet`

| instrument_id | value |
|---|---|
| KR:005930 | 1 |
| KR:000660 | 1 |
| KR:123456 | 2 |

- Codes are numbers too (`nx.Item.sector.eq(1)`); what `1` means is the user's.

### 3-4. Item declarations (optional)

In `tds.json`, the dataset's `params.items` may declare an item's kind and carry:

```json
"params": {"items": {"shares_out": {"kind": "share_count"},
                     "dps": {"kind": "per_share", "carry": "none"}}}
```

- `kind`: `per_share` or `share_count` — the engine rescales the value by later splits.
- `carry`: `to_end` (default), a number of sessions N, `none`, or `next_listing`.
