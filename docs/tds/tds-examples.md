# TDS data examples: what the data you feed NexusBT looks like

This is the canonical English text; a Korean translation is in tds-examples.ko.md.

An illustrated guide based on TDS (NexusBT Data Standard) v1.4. Every number is an **example value that only shows the shape** (not real quotes or financials). The formal definition of each column is in the corresponding section of `tds-v1.4.md`.

The instrument key is `instrument_id` (e.g. `KR:005930` Samsung Electronics, `US:AAPL` Apple). All time columns are UTC.

---

## 0. At a glance: two ways to feed data

```
                ┌──────────────────────────── one snapshot folder = one TDS package ─────────────────────────┐
  (A) inputs    │ bars (daily bars) · corporate_actions (corporate actions) · fundamentals_state (PIT fundamentals) │
  engine        │ calendar_sessions (trading days) · delistings (delistings) · tradability_daily (halts, admin)    │──▶ the Pipeline
  computes      │ classifications (sectors) · share_counts (share counts) · fx_rates (exchange rates)              │    builds factor panels
                ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
  (B) finished  │ feature_panels (instrument × month factor panels computed by the producer) · label_panels (labels)│──▶ used directly as
  used directly │                                                                                                  │    Panel.<column>
                ├──────────────────────────────────────────────────────────────────────────────────────────────────┤
  (C) events,   │ events (filings, earnings releases) · series_observations (macro series, release times, revisions)│──▶ Events · Macro
  macro         └──────────────────────────────────────────────────────────────────────────────────────────────────┘    blocks
```

(A) and (B) can be used together. The reference producer's snapshots contain both. The "instrument × period × column" panel users want is **either (B) used as is, or the same shape built by the engine from (A)** (chapter 4).

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
├── delistings/part-00000.parquet
├── fundamentals_state/edition=strict/market=KR/part-00000.parquet
├── feature_panels/name=factor_pit_monthly/edition=strict/year=2024/part-00000.parquet
├── label_panels/name=label_monthly/year=2024/part-00000.parquet
├── events/event_type=earnings.prelim/part-00000.parquet   (added in v3.4; partition = event kind)
└── series_observations/part-00000.parquet
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

### 2-3. `fundamentals_state` PIT fundamentals — intervals of "from when could this value be known"

| instrument_id | item | ts_known_from | ts_known_to | period_end | period_kind | value | strict_eligible |
|---|---|---|---|---|---|---|---|
| KR:005930 | net_income_ttm | 2023-11-14T07:00Z | 2024-01-31T07:00Z | 2023-09-30 | TTM | 9.0e12 | true |
| KR:005930 | net_income_ttm | 2024-01-31T07:00Z | 2024-04-30T07:00Z | 2023-12-31 | TTM | 1.5e13 | true |
| KR:005930 | equity | 2024-03-12T07:00Z | | 2023-12-31 | POINT | 3.6e14 | true |
| US:AAPL | revenue_ttm | 2024-02-02T21:30Z | 2024-05-02T21:30Z | 2023-12-30 | TTM | 3.86e11 | true |

- A decision on 2024-01-15 sees only the first row (as of 2023-09). From the 2024-01-31 filing on it switches to the second row. **The quarter's value never leaks before the filing date** — that is the point of this table.
- `strict_eligible = true`: a value from the original filing (strict edition). Cells filled with vendor values are only in the compare edition.

### 2-4. Other inputs (shape only)

| Table | One-row example |
|---|---|
| `calendar_sessions` | calendar_id XKRX · session_date 2024-03-29 · ts_open 2024-03-29T00:00Z · ts_close 06:30Z · session_kind regular |
| `delistings` | KR:999990 · last_trading_date 2019-07-10 · exit_date 2019-07-19 · delist_type performance · exit_value_status observed · ret_observed −0.95 |
| `tradability_daily` | KR:123456 · 2024-03-29 · status_known true · halted_full_day true · admin_status administrative |
| `classifications` | KR:005930 · scheme krx_sector · level 1 · code "IT" · effective_from 2000-01-01 · ts_known_from 2000-01-01 |
| `share_counts` | KR:005930 · count_kind listed · as_of_date 2023-12-31 · shares 5,969,782,550 · ts_available 2024-01-02T00:00Z |
| `fx_rates` | base USD · quote KRW · rate_kind fixing · obs_date 2024-03-29 · rate 1,346.8 · ts_available 2024-03-29T06:30Z |

---

## 3. Finished tables (B): the "panel" users want

### 3-1. `feature_panels` (name = `factor_pit_monthly`) — instrument × month × factor columns

| instrument_id | period | as_of_date | ts_available | market_cap | per | pbr | roe_ttm | mom_12_1 | vol_1y | ret_1m | dps_ttm | … |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KR:005930 | 2024-03-01 | 2024-03-29 | 2024-04-01T00:00Z | 4.92e14 | 32.8 | 1.37 | 0.042 | 0.271 | 0.212 | 0.124 | 1,444 | … |
| KR:000660 | 2024-03-01 | 2024-03-29 | 2024-04-01T00:00Z | 1.33e14 | — | 2.11 | −0.162 | 0.884 | 0.341 | 0.198 | 1,200 | … |
| US:AAPL | 2024-03-01 | 2024-03-29 | 2024-04-01T13:30Z | 2.65e12 | 26.7 | 35.6 | 1.54 | 0.021 | 0.198 | −0.051 | 0.96 | … |
| KR:005930 | 2024-04-01 | 2024-04-30 | 2024-05-02T00:00Z | 4.69e14 | 31.3 | 1.31 | 0.042 | 0.233 | 0.215 | −0.047 | 1,444 | … |

- One row = **one instrument for one month**. Columns = factors (e.g. about 360 columns in a strict edition). Column meanings are in `dictionary/columns`.
- `ts_available`: the first instant this row may be used in a decision (the open of the trading day after month end). The engine does not show this row to earlier decisions.
- An empty cell (—) has no value. The engine does not fill it with 0.
- Delisted instruments also have rows up to the month before delisting (no survivorship bias).

### 3-2. `label_panels` (labels) — same shape + future returns

| instrument_id | period | fwd_ret_1m | entry_date | exit_date | ts_label_available |
|---|---|---|---|---|---|
| KR:005930 | 2024-03-01 | −0.047 | 2024-04-01 | 2024-04-30 | 2024-05-02T00:00Z |

- Labels are used only for scoring in `evaluate`. If put into a factor computation, the engine blocks it (LabelLeakError).

---

## 4. The panel the engine builds = the same shape as 3-1

Feeding only the (A) inputs, the Pipeline builds the same "instrument × date × column" table.

```python
pipe = nx.Pipeline({
    "per":      Price.market_cap.latest / Fund.net_income_ttm.latest,
    "roe":      Fund.net_income_ttm.latest / Fund.equity.latest,
    "mom_12_1": Returns(252).shift(21),
    "vol_1y":   AnnualizedVolatility(252),
}, screen=nx.universe())
nx.run_pipeline(pipe, start="2024-01-01", end="2024-04-30", freq="monthly")
```

| market | session_date | instrument_id | per | roe | mom_12_1 | vol_1y |
|---|---|---|---|---|---|---|
| KR | 2024-03-29 | KR:005930 | 32.8 | 0.042 | 0.271 | 0.212 |
| KR | 2024-03-29 | KR:000660 | — | −0.162 | 0.884 | 0.341 |
| US | 2024-03-29 | US:AAPL | 26.7 | 1.54 | 0.021 | 0.198 |

- The result table also has a `decision_ts` column (specification 3.5; omitted here).
- To use a (B) panel column as is, call it like `Panel.per.latest`. It can be mixed with values computed directly from (A).

---

## 5. Events and macro (C) — v3.4

### 5-1. `events` filings and earnings releases

| event_id | event_type | instrument_id | series_id | ts_event | ts_available | value | consensus | unit | source |
|---|---|---|---|---|---|---|---|---|---|
| ev-1001 | earnings.prelim | KR:005930 | | 2024-04-05T00:00Z | 2024-04-05T00:05Z | 6.6e12 | 5.4e12 | KRW (operating income) | dart |
| ev-1002 | buyback.decision | KR:000660 | | 2024-03-20T07:30Z | 2024-03-20T07:31Z | 1.0e11 | | KRW | dart |
| ev-1003 | earnings.announcement | US:AAPL | | 2024-05-02T20:30Z | 2024-05-02T20:31Z | 1.53 | 1.50 | USD/share (EPS) | sec |
| ev-1004 | macro.release | | US_CPI_YOY | 2024-03-12T12:30Z | 2024-03-12T12:30Z | 3.2 | 3.1 | % | bls |

Column names are exactly those of TDS v1.4 5.21 (the kind column is named `event_type`, a namespaced string). One of `instrument_id`, `issuer_id` and `series_id` must be present (otherwise warning V041). A revision is a new `event_id`.

How to use: `Events.earnings.days_since()` (= `event_type` `earnings.announcement`), `Events.of("earnings.prelim").surprise`, schedule `nx.on_event(Events.of("earnings.prelim"), delay=1)`.

### 5-2. `series_observations` macro series (release time + revision history)

| series_id | obs_period_end | value | unit | ts_available | is_revision | consensus | frequency |
|---|---|---|---|---|---|---|---|
| KR_CPI_YOY | 2024-02-29 | 3.1 | % | 2024-03-06T23:00Z | false | | M |
| US_CPI_YOY | 2024-02-29 | 3.2 | % | 2024-03-12T12:30Z | false | 3.1 | M |
| US_GDP_QOQ | 2023-12-31 | 3.3 | % | 2024-01-25T13:30Z | false | 2.0 | Q |
| US_GDP_QOQ | 2023-12-31 | 3.4 | % | 2024-03-28T12:30Z | true | | Q |

- A decision on 2024-03-01 sees KR CPI only up to the January value (the February value is released on March 7).
- US GDP 2023Q4 is 3.3 on January 25 and 3.4 after the March 28 revision. The engine gives the value known at that time.

How to use: `Macro.series("US_CPI_YOY").latest`, `.obs(1)` (previous period value), `.age_days`, `.surprise` (when consensus exists), `vintage="first"` (first-release vintage only), `nx.on_event(Macro.series("US_CPI_YOY").changed(), universe_scope="all")`.

---

## 6. Attaching your own data

```python
nx.dataset.from_parquet("my_sentiment.parquet", shape="panel",  key=("instrument_id","date"), known_on="published_at")
nx.dataset.from_parquet("my_events.parquet",    shape="events", ts_event="event_at", known_on="announced_at", name="my_events")
nx.dataset.from_parquet("my_macro.parquet",     shape="series", period_end="period_end", known_on="released_at", vintage="vintage", name="my_macro")
```

All three shapes **require a "when could it be known" (`known_on`) column**. Without it you get `PointInTimeError` (E3, `layer: data`); if a shape's required columns (events: `ts_event` and one of the instrument, issuer or series ids; series: `period_end`, `value`) are missing, `DatasetShapeError` (E47) tells you which column to add. If an event table has no `event_type` column, `name` becomes the event kind (specification 3.2).
