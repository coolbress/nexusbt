# NexusBT Data Standard (TDS) v1 — engine input format specification, document version v1.4 (2026-10-28)

This is the canonical English text; a Korean translation is in tds-v1.4.ko.md.

> Status: **draft** within **draft → RC → 1.0**. The standard version string stays `tds_version = "1.0"` (grammar `MAJOR.MINOR`); the release status is shown only by repository tags and the document header (10.5 graduation criteria).
> Version history: v1 (2026-10-27 draft) → **v1.1** (2026-10-28): applied the P0, P1 and cheap P2 items of the three-way review (Opus 5.5 · Fable 5.1 · GPT-6.1 Sol xhigh, `review/consensus.md`) — three hashes (physical, value, semantic) and a language-independent canonical serialisation, `level` and `edition` in the `classifications` key, two-time-axis rectangle lookup and consistent names (`instrument_symbols.ts_known_to`), the corporate-action resolution procedure, missing eligibility = false, profile versions and the three check results, `producer.hints`, path safety, unexercised schemas marked `experimental`, `minimal-daily` for analysis only; change summary in chapter 15.
> Version history (continued): **v1.2** (2026-10-28): applied the teardown of existing engines (`teardown/MATRIX.md`, numbers `[V31-NN]`) — exact split ratios `ratio_num/ratio_den`, whether delisting returns include distributions, volume unit check, price grid and the `market_rules` dataset, per-file value hashes, index weighting method. All are optional columns, datasets or warnings, so `tds_version` stays `"1.0"` (chapter 16).
> Version history (continued): **v1.3** (2026-10-28): applied review round 3 (`review/consensus-r3.md`, numbers `[R3-NN]`) — corporate-action resolution separates existence time from terms time (5.11), three terminal-value bases (5.13), price comparison coordinate = integer market minimum unit (5.27), snapshot immutability (clone first, read-only, atomic publish, 4.1), `files[].value_sha256` is advisory (4.2), consumer rejection of invalid exact ratios (5.11), corrected K1 recommended id example. Only interpretation wording fixes, examples and recommendations, so `tds_version` stays `"1.0"` (chapter 17).
> Version history (continued): **v1.4** (2026-10-28): review round 4 + maintainer decision 2026-10-28 (numbers `[R4F-NN]`) — corporate actions that change share counts **MUST** carry `ratio_num/ratio_den`, otherwise checker error A010 (E); the path by which a consumer infers ratios from f64 is removed (only when a user setting opts into decimal literals, with a warning and a record); a null "includes distributions" on a delisting is read on the conservative side that never counts twice; event table `series_id` and `consensus`, macro series `consensus` and `frequency`, and the definition of the first-release vintage. Still a draft, so `tds_version` stays `"1.0"` (chapter 18).
> Relation: this document is **the canonical input definition referenced by chapter 4** of the engine specification v3.4 (`engine-spec-v3.4-2026-10-28.md`). Where the two differ, this document is right about the input format (difference list in chapter 12). Maintainer decisions (design document 9.0) take precedence over this document.
> Public: this standard and the checker (`nexusbt-tds`, import `nexusbt_tds`, command `tds`) are public (Apache-2.0). Chapter 11 of the working draft (producer-specific mapping) is not normative and is not part of this public edition.
> Examples: example rows for every dataset the engine reads (including events and macro series) are in `tds-examples.md` (same folder).
> Notation: [verified] = the original source was opened and checked for this document. [unverified] = relies on memory or secondary sources; check the original before implementing. [est.] = estimate. [decided] = decided by this document.

## Contents

0. One-page summary
1. Survey: how other engines, vendors and standards define input data
2. Goals and key decisions of TDS v1 (K1–K12)
3. Common rules (types, names, times, units, missing values, keys, partitions, physical format)
4. Package structure and the manifest `tds.json`
5. Dataset kinds (per table: columns, types, key, sort, partitions, point-in-time meaning, checks)
6. Point-in-time (PIT) semantics
7. Profiles (from the smallest user to the full set)
8. Conformance checker (CLI, check levels, error codes)
9. Import adapters (zipline, LEAN, Nautilus, Databento DBN, CSV, etc.)
10. Versioning and evolution rules
11. (Removed from the public edition)
12. Alignment with chapter 4 of the engine specification (difference list)
13. Open questions
14. Sources
15. v1 → v1.1 change summary (three-way review)
16. v1.1 → v1.2 change summary (teardown of existing engines)
17. v1.2 → v1.3 change summary (review round 3)
18. v1.3 → v1.4 change summary (review round 4 + maintainer decision)

---

## 0. One-page summary

**What it is.** TDS is the public format of "one data folder that the engine reads". The folder holds one manifest `tds.json` and Parquet files. As long as this format is followed, the engine reads the output of any producer the same way (a data warehouse export, a personal CSV import, or a conversion from a zipline bundle, a LEAN folder, a Nautilus catalog or Databento files). Data preparation and the engine meet only through this format.

**Key decisions (detailed reasons in chapter 2).**

| # | Decision | One-line reason |
|---|---|---|
| K1 | Public key = the string `instrument_id`, an **opaque, never-reused** id chosen by the producer. Symbols (tickers), FIGI, ISIN and PERMNO live in separate tables (`instrument_symbols`, `instrument_xref`) with periods | Tickers change and are reused. FIGI and ISIN have many gaps for old delisted names and for Korea. Same idea as CRSP PERMNO and Sharadar permaticker |
| K2 | Every time is a UTC instant `timestamp[unit, tz="UTC"]`. Tick and quote series use `ns`, everything else `us`. Local dates (`session_date` etc.) are only `date32` labels | Parquet `isAdjustedToUTC=true` means an instant. Nautilus and Databento use ns. DuckDB's default TIMESTAMPTZ is us |
| K3 | Every observation has an **availability time** `ts_available` (a column or a derivation rule in the manifest), separate from the event time `ts_event` | Enforces engine invariant INV-01 (`ts_available <= decision_ts`) at the data-format level |
| K4 | Prices are stored as **raw** prices. The source of adjustment is the `corporate_actions` event table, and cumulative factors are **forward-cumulative with the first listed session = 1.0** | Factors fitted backward from the latest date (LEAN, Yahoo adjusted close) rewrite the whole past on every new event → immutable partitions and hashes break |
| K5 | Fundamentals in two layers: raw events `fundamentals_events` (availability time, source and version per fact) + resolved state intervals `fundamentals_state` (`[ts_known_from, ts_known_to)`, no overlaps, per edition) | The engine does not re-implement fiscal-period selection rules (9.0 Q24). Combines the strengths and weaknesses of Qlib PIT and Sharadar AR/MR |
| K6 | Changing classifications, universes and identifiers use **two time axes**: effective period (`effective_from/to`) and known time (`ts_known_from/to`) | "It was in that class then" differs from "we knew that then" (the backfill problem of industry histories filled in later) |
| K7 | Price numbers: daily bars and event amounts = `float64`; ticks and quotes = `int64` fixed point (per-dataset exponent, default 1e-9) | Book levels must be exactly equal to be the same level (Databento 1e-9). For daily bars float64 is enough and easy to handle |
| K8 | Package = folder + `tds.json` (a skeleton **inspired by** Frictionless Data Package v2; it does not implement the Data Package `resources` structure as is — v1.1 wording fix). Per file sha256, row count and statistics; per dataset value hash and coverage; per package physical, value and semantic hashes | Aligns ideas with Frictionless tools, while TDS defines the Arrow types and time rules |
| K9 | **Profiles** (versioned, `@1.0`): from `tds:minimal-daily` (2 tables, analysis) to `tds:equity-daily-research` and `tds:l3-book` (experimental). A package declares the profiles it follows and the checker confirms them with three results (declared, check level, result). Consumer support is stated by the consumer | Small users start with 2–4 tables |
| K10 | Versions: standard `MAJOR.MINOR`, each dataset schema `MAJOR.MINOR`. Adding optional columns or open enum values = MINOR, everything else = MAJOR. Readers ignore unknown columns | Simplifies the Avro/Confluent compatibility rules and the idea of SchemaVer |
| K11 | Deterministic writing: same content gives the same bytes and the same value hash (4.5 canonical serialisation — independent of writer tool and language). File and row order and row-group boundaries are fixed | Same as engine INV-09 and the producer build-fingerprint principle |
| K12 | Conformance checker `tds check`: 3 levels (`manifest` / `schema` / `full`), error codes `TDS-<area><number>`, JSON output | The engine's `SnapshotError` (E14) carries these codes as is |

**Relation to current work.** The v1 engine requires only the datasets needed by the features a graph uses (at the widest, `tds:equity-daily-research` + `panels` + `pit-fundamentals`: equity daily bars + fundamentals + panels). The rest (minute bars, ticks, quotes, futures, options, crypto) have their table shapes fixed as **experimental** (`experimental`) and are promoted to stable after lossless import and pinned replay cases exist (v1.1; the v1 promise "use without change" was premature).

---

## 1. Survey: how other engines, vendors and standards define input data

### 1.1 Engines

| Subject | Input data shape | What TDS takes / avoids |
|---|---|---|
| **zipline-reloaded bundle** | `ingest(environ, asset_db_writer, minute_bar_writer, daily_bar_writer, adjustment_writer, calendar, start_session, end_session, cache, show_progress, output_dir)` [verified]. Daily and minute bars in bcolz (price ×1000 as uint32, engine E0 document 5.2); minute bars zero-filled between sessions [verified]. Adjustment SQLite: `splits`, `mergers` (sid, effective_date, ratio), `dividends` (sid, ex_date, declared_date, pay_date, record_date, amount), `stock_dividends` (+ payment_sid, ratio) [verified]. Dividend ratio = `1 − dividend / close of the session before the ex-date` [verified]. Asset DB: equities (symbol, asset_name, start_date, end_date, first_traded, auto_close_date, exchange), futures (root_symbol, notice_date, expiration_date, tick_size, multiplier …), exchanges (exchange, canonical_name, country_code) [verified]. The `csvdir` bundle is `date,open,high,low,close,volume,dividend,split` [verified] | Take: raw prices + event tables + factors computed by the engine, the dividend factor definition (TDS uses the same formula). Avoid: integer sid as the file key (breaks on renumbering), the uint32 price limit, no availability time (splits and dividends assumed known on the event day), session calendar relying on a name outside the bundle (`NYSE`) |
| **QuantConnect LEAN data folder** | `<securityType>/<market>/<resolution>/<ticker>/<date>_<tickType>.zip` (tick, second, minute), `<securityType>/<market>/<resolution>/<ticker>.zip` (hour, daily). Headerless CSV, first field is the time: for minute and below "milliseconds since midnight of that file's date", for hour and daily `YYYYMMDD HH:mm`, **bar time is the start time**, time zone is the data time zone in `market-hours-database.json` [verified]. US equity, equity option and index option prices are ×10,000 integers (deci-cents) [verified]. Minute bar columns time, open, high, low, close, volume; quote bars bid OHLC, bid size, ask OHLC, ask size; quote ticks fill one side and leave the other 0 [verified]. Intervals without trades have no row [verified]. Factor files `factor_files/<ticker>.csv` (date, price factor, split factor, reference price) and map files `map_files/<ticker>.csv` (date, ticker at the time, exchange) mark adjustments, ticker changes and delistings [unverified: column order, latest format] | Take: factors and maps kept separate from raw prices, time zone separated into market metadata, exercise style, right and strike in the option path. Avoid: factors fitted backward (latest = 1, the past changes on every new event), file name = ticker (needs map files on reuse and change), bar time = start (invites availability-time mistakes), no availability time |
| **NautilusTrader** | Data types: `Bar`, `QuoteTick`, `TradeTick`, `OrderBookDelta(s)`, `OrderBookDepth`, `InstrumentStatus`, `InstrumentClose`, `MarkPriceUpdate`, `FundingRateUpdate` [verified]. Two times `ts_event` (event, exchange time) and `ts_init` (when Nautilus created the object), both Unix ns; backtests replay in stable `ts_init` order [verified]. `BarType` string `{instrument_id}-{step}-{aggregation}-{price_type}-{INTERNAL|EXTERNAL}`, e.g. `AAPL.XNAS-5-MINUTE-LAST-INTERNAL`; price_type LAST/BID/ASK/MID; bar `ts_event` is by default the **close time**, intervals are LEFT_OPEN (start excluded, end included) [verified]. `ParquetDataCatalog`: `data/<type>/<identifier>/{start}_{end}.parquet`, overlapping writes raise `OSError` by default, instrument definitions in per-class folders (`data/equity/` etc.), instants are `Timestamp(Nanosecond, "UTC")` [verified]. Price fixed point and precision metadata scheme [unverified] | Take: event time separate from receive time, bar time = close time, the components of the bar-type string (step, aggregation, price type, source), per-file time-range names and no overlaps. TDS tick tables are defined so their columns map 1:1 to Nautilus data types (chapter 9) |
| **vectorbt** | Wide pandas tables (rows = time index, columns = instruments), prices and signals aligned to the same shape [unverified: docs not opened this time; source is the engine survey document] | Good as an in-memory shape inside the engine but avoided as a storage format (instrument lifetimes, reasons for missing values and time information are lost). Only a TDS → wide-table export is provided |
| **Qlib** | `calendars/day.txt` (one date per line), `instruments/all.txt` (`SYMBOL<TAB>start<TAB>end`), `features/<sym>/<field>.day.bin` = headerless little-endian float32, **first value = calendar position of the first date of that data**, then values aligned to the calendar (NaN on empty days) [verified]. Required columns open, close, high, low, volume, factor; prices and volume are **adjusted values**, `factor = adjusted price / raw price`, first trading day price normalised to 1 [verified]. PIT fundamentals: `XXX_q.data`/`XXX_a.data` rows = (date = publication date, period = period integer like 200704, value, _next = byte offset of the next revision of the same period) + `.index`; revisions do not overwrite but add new rows [verified] | Take: the calendar is the axis and data is aligned by calendar position (dense index in engine memory), PIT = "revision is a new row + publication date". Avoid: float32 prices (precision loss for large KRW values and US BRK.A; the reference producer has already hit this), storing only adjusted prices, availability time as a date only |
| **hftbacktest** | numpy structured array with 8 fields: `ev` (u64 event flags), `exch_ts` (i64), `local_ts` (i64), `px` (f64), `qty` (f64), `order_id` (u64, L3), `ival` (i64), `fval` (f64) [verified]. Flags BUY/SELL, DEPTH/TRADE, EXCH_EVENT (processed in exchange-time order), LOCAL_EVENT (processed in local-time order); `exch_ts <= local_ts` must hold and negative latency must be fixed [verified]. Examples use ns [verified] | Take: exchange time and receive time both required, which become the input of a latency model; "receive time < event time" as a check item |
| **backtrader** | `GenericCSVData`: specify field numbers for datetime, open, high, low, close, volume, openinterest (-1 = absent) [unverified] | Only the "column mapping file" approach of the CSV adapter is used as a reference |
| **ArcticDB** | Versioned DataFrames per symbol inside a library (time index), snapshots, append/update, LMDB and S3 storage [unverified: docs not opened this time] | The storage engine is not used (rejected by the reference producer after review). "Version + snapshot name" is reflected as `snapshot_id` and `parent_snapshot_id` in the manifest |

### 1.2 Data vendors and conventions

| Subject | Shape | What TDS takes |
|---|---|---|
| **Databento DBN** | Schemas: MBO (L3), MBP-10 (L2), MBP-1, TBBO, BBO and Trades (L1), OHLCV (L0), Definition, Statistics, Status, Imbalance, plus reference schemas for corporate actions, adjustment factors and the security master [verified]. Every record has a 16-byte header: `length`, `rtype`, `publisher_id`, `instrument_id`, `ts_event` (ns) [verified]. Price = signed integer, 1 unit = 1e-9; absent = `INT64_MAX`; times `ts_event` (arrival at the matching engine), `ts_recv` (Databento receipt, UTC-synchronised, monotonic per instrument), `ts_in_delta`; absent time = `UINT64_MAX` [verified]. `action` A/M/C/R/T/F/N, `side` A/B/N, `flags` bits (F_LAST 128, F_TOB 64, F_SNAPSHOT 32, F_MBP 16, F_BAD_TS_RECV 8, F_MAYBE_BAD_BOOK 4) [verified]. Metadata: schema, stype_in/stype_out, symbol mapping (raw_symbol ↔ output symbol per period), versions 1/2/3 [verified]. Symbology raw_symbol / instrument_id (assigned by the publisher, **some venues renumber daily**) / parent (`ES.FUT`) / continuous (`ES.c.0` calendar, `.n.` open interest, `.v.` volume rank; prices not adjusted) [verified]. OHLCV `ts_event` = **interval start (inclusive)**, no row without trades, `ohlcv-1d` is **by UTC date** and can differ from the exchange session [verified] | Tick and quote columns (action, side, flags values as is), 1e-9 fixed-point prices, `ts_recv` as the availability time, continuous contracts defined by rule name + rank with unadjusted prices, instrument ids mapped to symbols by period. Caution: UTC daily bars must not be used as session daily bars (warned at import) |
| **Polygon → Massive flat files** | S3 path `us_stocks_sip/day_aggs_v1/...`, daily columns ticker, volume, open, close, high, low, `window_start` (Unix ns, bar start), transactions; the file for a day appears around 11:00 (Eastern) the next day [verified] | Import adapter target (ticker → id mapping needs symbol history). A distribution delay such as "appears at 11:00 the next day" is an example for the `ts_available` rule |
| **kdb+/tick conventions** | Tables `trade:([]time;sym;price;size)`, `quote`, date partitions + sort by instrument and time + `p#` (parted) attribute, repeated string `sym` enumeration, memory → disk once a day [unverified: general knowledge] | Tick partition = date, in-file sort = (instrument, time, sequence), dictionary encoding of repeated strings |
| **CRSP / Compustat** | Security id PERMNO (never reused), company id PERMCO; delisting codes (first digit: 2 merger, 3 exchange move, 4 liquidation, 5 dropped …) and delisting return DLRET [unverified: detailed codes]. From 2025 only the new CIZ format is updated (2024-12 data is the last of the old SIZ); the new format adds delisting, distribution and share-code flags [verified]. CCM link table: GVKEY ↔ PERMNO by period (LINKDT–LINKENDDT), link type (LINKTYPE, starting with L) and primary link (LINKPRIM P/C) [verified: secondary source] | Separate security id and company id, a link table with periods (`instrument_xref`), delisting as an event + terminal return (not as a label), an optional CRSP-equivalent column for the exit type code |
| **Sharadar (SF1, SEP, ACTIONS, TICKERS)** | Six fundamental dimensions = (AR as first reported / MR most recent restatement) × (Q / Y / T) [verified: secondary source]. `datekey` (filing date) is used as the publication date (the reference producer's `available_date`) [verified: producer code]. SEP `closeunadj` raw close, `close` split-adjusted, `closeadj` split + dividend adjusted [verified: producer code]. ACTIONS dividend amounts are split-adjusted values [verified: producer code]. TICKERS `permaticker` stable id [verified: producer code] | The distinction between "as first reported (AR)" and "most recent restatement (MR)" = the TDS edition and revision-event model. Vendor dividends are converted back to raw amounts before storing |

### 1.3 Identifier and code standards

| Standard | Content | Use in TDS |
|---|---|---|
| **FIGI / OpenFIGI** | Levels: share class FIGI (across countries) > composite FIGI (country) > FIGI (exchange) [verified: secondary source]. Said never to change once assigned [verified: openfigi.com]. 12 characters, `BBG` prefix, no vowels, check digit [unverified] | `figi`, `figi_composite`, `figi_share_class` in `instrument_xref`. Not used as the public key (old delistings and Korea have gaps) |
| **ISIN (ISO 6166)** | 12 characters: 2-letter country + 9 characters + check digit [unverified: original standard] | `instrument_xref.isin`. Korea uses the form `KR7` + short code + …, which helps linking [unverified] |
| **MIC (ISO 10383)** | 4 characters. Operating MIC (OPRT) and segment MIC (SGMT, linked to a parent operating MIC) [verified]. XNAS is operating; XNGS, XNCM etc. are segments [verified: secondary source]. XKRX, XNYS [unverified: list check], KOSDAQ segment code (believed to be XKOS) [unverified] | `instruments.venue_mic` (segment allowed) + `operating_mic`. Calendar ids prefer MICs |
| **ISO 4217** | 3-letter currency, minor-unit digits (KRW 0, USD 2, JPY 0) [unverified: table check] | All currency columns. Currencies outside ISO (crypto etc.) are declared in the manifest `currencies` (4.3) |
| **ISO 8601 / RFC 3339** | Text representation of dates and times | Text times in the manifest and CSV are RFC 3339 ending in `Z` (e.g. `2026-10-27T06:30:00Z`), dates are `YYYY-MM-DD` |

### 1.4 Storage formats, packages, schema evolution

| Subject | Content | TDS decision |
|---|---|---|
| **Parquet logical types** | TIMESTAMP with `isAdjustedToUTC=true` is "one instant on the timeline", false is "a local wall-clock value (does not determine an instant)"; units MILLIS/MICROS/NANOS [verified]. DECIMAL as int32 (precision ≤9), int64 (≤18), fixed length or variable bytes [verified]. STRING is UTF-8 in BYTE_ARRAY [verified] | All instants are `isAdjustedToUTC=true` (Arrow `tz="UTC"`). Wall-clock time columns are forbidden. INT96 is forbidden (old Spark style, no time zone marker [unverified: official deprecation wording]) |
| **Row group size** | The Parquet docs recommend large row groups (512MB–1GB) and 8KB pages (based on HDFS sequential reads) [verified] | For pruning, TDS recommends about one month for daily tables (about 200,000 rows for one market) and 64–256MB for tick tables. A recommendation, not checked |
| **Arrow** | If a timestamp type has tz, values are epoch relative to UTC [unverified: Schema.fbs wording]. Dictionary encoding is a physical representation of the same logical type | Dictionary strings and plain strings are treated as the same logical type (by both checker and hash) |
| **Frictionless Data Package v2** | Required `resources` (1 or more); recommended `name` (lowercase, digits, `.-_`, stable), `id` (UUID/DOI etc.), `licenses`; optional `$schema` (2.0 profile), `version` (semver recommended), `created` (RFC 3339), `contributors`, `sources` [verified]. Resources (path, hash, bytes, schema) and Table Schema (fields, primaryKey, foreignKeys, missingValues) are separate specifications [verified: location only] | `tds.json` uses the same top-level fields as Data Package v2 and puts TDS-specific information in a `tds` block. Resource hash string format `sha256:<hex>` [unverified: v2 hash grammar] |
| **SchemaVer (Snowplow)** | MODEL-REVISION-ADDITION. Breaking changes in the first part, non-breaking in later parts; "breaking" can depend on the store (required → optional breaks in Redshift) [verified] | TDS reduces this to two parts (MAJOR.MINOR) and defines "breaking" **from the reader's side** (chapter 10) |
| **Avro / Confluent compatibility rules** | BACKWARD (new reader reads old data), FORWARD (old reader reads new data), FULL [unverified: original not opened in this survey] | Within one MAJOR aim for FULL compatibility: add columns only as optional, and readers ignore unknown columns |

### 1.5 Design lessons from the survey

1. **Only tick formats carry both an event time and an availability time** (Nautilus `ts_event/ts_init`, Databento `ts_event/ts_recv`, hftbacktest `exch_ts/local_ts`). Daily and fundamentals formats (zipline, LEAN, Qlib bin) have no availability time. TDS extends this tick idea to all data (K3).
2. **Bar time conventions differ**: LEAN, Databento and Massive use the start, Nautilus the close time. Using the start time as if it were the availability time causes look-ahead mistakes. TDS keeps both `ts_start` and `ts_end`, and the default availability time is `ts_end`.
3. **The anchor of adjustment factors differs**: LEAN (latest = 1, backward), Qlib (first day = 1), zipline (event tables only, computed by the engine), Sharadar (adjusted price columns). If you want immutable files and hashes, only "first day = 1, forward-cumulative" works (K4).
4. **Identifiers**: mature data (CRSP, Sharadar, Databento symbol mapping) all use "stable id + symbol mapping with periods". Publisher ids that change daily (some Databento venues) and reused tickers cannot be keys.
5. **PIT fundamentals**: combining Qlib (revision = new row + publication date) and Sharadar (two editions AR/MR) gives "fact event table + per-edition state intervals" (K5). State intervals make the engine lookup a single `searchsorted` (specification 5.3.5).
6. **Fixed point**: book reconstruction needs exact equality of price levels (both Databento and Nautilus use integers). For daily research float64 is easy and sufficient (K7).
7. **Package metadata**: combines Nautilus's "file name = time range + no overlap", Frictionless's "resource list + hash + schema", and the reference producer's snapshot manifest "build run id + file sha256" (K8).

---

## 2. Goals and key decisions of TDS v1

### 2.1 Goals and scope

- **Goals**: (1) fully separate the data producer from the engine. (2) Anyone who follows this format can use the engine with their own data. (3) The format alone determines "what could be known when". (4) Same content gives the same hash.
- **What the v1 engine uses**: Korean and US equity daily research (`tds:equity-daily-research`).
- **What v1 only shapes**: minute and hour bars, trades, L1 quotes, L2/L3 books, futures (contracts, rolls), options (contracts, chains, Greek inputs), crypto (24/7, funding rates), FX, alternative and event data.
- **Out of scope**: choice of storage engine (DuckDB, ArcticDB etc.), collection and cleaning methods, cost tables (engine resource files, specification 4.17), the engine's run record format (specification 5.9).

### 2.2 Decisions K1–K12 (reasons and rejected alternatives)

**K1. Public key = `instrument_id` (opaque, never reused).**
- Format: `^[A-Z0-9][A-Z0-9_]{0,15}:[A-Za-z0-9._\-/^=+]{1,64}$` (namespace `:` local id). Namespaces are declared with a description in the manifest `id_namespaces`. Consumers **do not interpret** ids (opaque).
- Rules: (a) within one package one id is one tradable object (one line of one share class on one exchange, one futures month, one option contract, one crypto pair on one exchange). (b) The id stays when the ticker changes. (c) **An id once used is never given to a different object** (even across package versions). (d) A new security created by a merger etc. gets a new id.
- The reference producer's ids (`KR:005930`, `US:AAPL`, reuse-handled `US:ECHO2`) already satisfy these rules.
- Recommendation for small users: `<MIC>:<ticker>_<first listing date YYYYMMDD>` (e.g. `XNAS:AAPL_19801212`; the v1.2 example `XNAS:AAPL:19801212` put a `:` in the local part and violated the format above — the regex is unchanged and the example is fixed, so as not to make the namespace split ambiguous [v1.3, R3-28]) or `FIGI:<value>` if a FIGI exists. Ticker-only `<MIC>:<ticker>` is not recommended because ticker reuse (common) easily breaks K1(c) [v1.1, RV-Q04]. The checker verifies only via period overlaps in `instrument_symbols`.
- Cross-sectional ties are broken by `instrument_id` order, so **changing the id scheme can change tie results** (an intended deterministic rule).
- Rejected alternatives: FIGI as the key (gaps for old delistings and Korea, historical mapping hard without paid data), ISIN (conversions and reissues, gaps in old US data), integer sid (changes per snapshot; already forbidden by specification 4.2).
- The specification name `security_id` is renamed to `instrument_id` (fits futures, options, crypto and FX too; the term used by Nautilus, Databento and FIX). The engine user API also uses only `instrument_id` without aliases (v1.1, chapter 13 Q1 closed). Other names are changed only in import mappings (chapter 9).
- Company grouping: `issuer_id` (optional, opaque). A producer's company id (Korean DART corp code, US CIK etc.) belongs here.

**K2. Time = UTC instant; the unit is fixed by the dataset kind.**
- Instant column names start with `ts_` and their type is `timestamp[us, tz="UTC"]` or `timestamp[ns, tz="UTC"]`. Which unit is fixed once per dataset kind (no freedom to choose → guarantees hashes and determinism).
  - `ns`: `trades`, `quotes`, `book_deltas`, `book_snapshots`, `trading_status_events`, and `bars` with a period below 1 second.
  - `us`: everything else (including daily and minute bars).
- Local dates are `date32` with names ending in `_date` or `_on` (exceptions: `period_end`, `period_start`, `effective_from/to`). A date is a label and does not replace a time.
- Local wall-clock time columns (timestamps without a time zone) are forbidden. Computations that need a time zone (session open and close) are already resolved by `calendar_sessions` as UTC instants.
- The ns int64 range is years 1677–2262, enough for financial data.

**K3. Every observation has an availability time `ts_available`.**
- An observation table either has a `ts_available` column or declares a **derivation rule** (a rule name from 6.2) in the manifest. The checker and the engine expand the rule into a column and use it with the same meaning.
- The engine rule is one: observation x is used only when `ts_available(x) <= decision_ts` (specification INV-01).
- A publication known only by date (`known_on`) is converted to an instant by the producer before export. Default rule `next_session_open(known_on)` = `ts_open` of the first session after `known_on` in that market (same as specification 5.1.4).

**K4. Raw prices + event tables + forward-cumulative factors.**
- Prices in `bars` are raw prices (the price actually traded that day, in local currency). Users with only adjusted prices are allowed only in the `tds:minimal-daily` profile and must declare `price_basis` (chapter 7).
- The source of adjustment is, per event in `corporate_actions`, the price multiplier `price_factor` (m_e) and the share-count multiplier `share_factor` (q_e). The quantity effect is stated **explicitly** with `share_factor`, and consumers do not infer quantity from the reciprocal of the price factor for events that are not split-like (5.11 resolution procedure) [v1.1].
- Cumulative factors `cum_factor_split`, `cum_factor_total` (an **optional** column of bars, required in no profile): `C[s] = Π_{e ≤ s} m_e` (one latest version per revision chain), first listed session = 1.0. Appending new data never changes the values of old rows. If a past event is discovered late, only the rows after it change.
- Because of reverse splits, `C` is not monotonic. The check is "event ↔ factor reconciliation" (A001).
- Availability: a factor takes effect at the event's `ts_effective`, but for events whose amount or ratio was published late (old Korean dividends) the consumer holds the event pending using the event's `ts_terms_available` (specification 5.3.4; `ts_amount_available` in v1 was a typo). The standard therefore states that there are cells where look-ahead-free adjustment cannot be done from the factor columns alone (5.11).

**K5. Fundamentals = fact events + resolved state intervals.**
- `fundamentals_events`: one reported number = one row (a revision is a new row). Source, document id, availability time, recording time.
- `fundamentals_state`: intervals of "the value to use at that time", computed by the producer's resolution rules (period selection, TTM, source priority, strict eligibility). Per `(edition, instrument_id, item)` the intervals `[ts_known_from, ts_known_to)` do not overlap.
- The engine looks up only the state table. The event table is for explanation (`nx.explain`) and audit.
- Small users MAY ship only the state table (`lineage_id` etc. are optional).

**K6. Changing attributes use two time axes.**
- Effective period `effective_from`/`effective_to` (the period the state held in the world, date or instant) and known period `ts_known_from`/`ts_known_to` (the period that record could be trusted and used).
- Rows used at decision time t: `ts_known_from <= t < ts_known_to` and the effective period contains t (or the queried date).
- The lookup is a **rectangle**: rows that satisfy the known condition and the effective condition together (6.3). Picking the row with the maximum known time first and then checking effectiveness is wrong (a pre-announced future-effective row hides the current row).
- Two-time-axis tables (`classifications`, `universe_membership`, `instrument_symbols`) use the same pair of names: effective `effective_from`/`effective_to` (`instrument_symbols` keeps the v1 names `valid_from`/`valid_to` but is stated to have the same meaning), known `ts_known_from`/`ts_known_to` [v1.1].
- Data whose known period is unknown (most classification histories) MAY set `ts_known_from = the instant of effective_from` but MUST declare `pit_quality = backfilled` (per row if the row column exists, otherwise per dataset). **Strict-edition lookups exclude rows with row-level `backfilled`**; for dataset-level `backfilled`/`mixed` without row-level quality the consumer only warns (6.5) [v1.1].

**K7. Number types.**
- Daily bars, event amounts and fundamental values: `float64`. NaN and Inf forbidden (missing is null).
- Tick and quote prices and sizes: `int64` fixed point. Dataset manifest `price_exponent` (default −9), `size_exponent` (default 0; crypto usually −8). Value = integer × 10^exponent. Absent is null (instead of Databento `INT64_MAX`).
- Volume (bars): `float64` (to handle fractional crypto quantities and adjusted volume together). For equities values must be integers (check V010, warning).
- Ratios and factors: `float64`. Counts: `int64`. Sequence numbers: `int64` (some tools cannot read uint64).

**K8. Package = folder + `tds.json`.** Chapter 4.

**K9. Profiles.** Chapter 7.

**K10. Versions.** Chapter 10.

**K11. Deterministic writing.**
- Row order inside a file = the dataset's `sort` key (each table in chapter 5). Fixed file naming rule (4.2). Row-group boundaries are a fixed row count (recorded in the manifest). Do not put the write time into Parquet metadata. Compression zstd (level 3 recommended), statistics on, page index on.
- The value hash (4.5) is independent of physical choices (compression, row groups, dictionary or not) and of the writer tool and language.

**K12. Conformance checker.** Chapter 8.

---

## 3. Common rules

### 3.1 Names

- Column names: lowercase snake_case, ASCII. Reserved prefixes: `ts_` (instants), `x_<namespace>_` (producer extension columns, e.g. `x_ex_kr_base_close`). The checker looks only at the type of extension columns, not their meaning.
- Dataset kind name = folder name (chapter 5 headings). When there are several datasets of the same kind, the manifest gives each its own `name` and states the kind in `kind` (e.g. `bars_1d`, `bars_1m` of kind `bars`).

### 3.2 Arrow types (logical types)

| TDS type name | Arrow | Notes |
|---|---|---|
| id | `string` | dictionary<int32, string> is accepted as the same logical type |
| code | `string` | Enumerated value. Closed enums (outside the list = error) and open enums (outside the list = warning + read as `other`) are marked in chapter 5 |
| date | `date32` | |
| ts_us | `timestamp[us, tz="UTC"]` | |
| ts_ns | `timestamp[ns, tz="UTC"]` | |
| f64 | `float64` | NaN and ±Inf forbidden |
| fixed | `int64` | Fixed point, exponent in the manifest |
| i8/i16/i32/i64 | signed integers | |
| bool | `bool` | |
| json | `string` | RFC 8259 JSON text. For leftover fields of event data; not used for key or filter columns |
| list<code> | `list<string>` | Trade condition codes etc. |

### 3.3 Missing values and null

- The only missing value is Parquet null. NaN, 0, empty string or `-1` are not used as missing markers (S009).
- Each column has a fixed nullability. A null in a non-nullable column is S003.
- When "unknown" and "none" differ, a status column distinguishes them (e.g. `tradability_daily.status_known`, `bars.obs_status`, `corporate_actions.pay_date_status`).

### 3.4 Units and currencies

- Unit vocabulary (`unit`): `ccy` (currency amount; currency in the same row's `currency` column or the instrument currency), `LCY` (the instrument's trading currency), `shares`, `contracts`, `ratio` (1 = 100%), `bp`, `count`, `days`, `index_points`, `price` (the instrument's price unit), `none`. `pct` is not used (ratios as ratio).
- Currency codes: ISO 4217 alpha-3. Currencies outside ISO (crypto BTC, USDT etc.) MUST be declared in the manifest `currencies` as `{"code","kind":"crypto|other","decimals"}` (R004).
- Scale of large fundamental values: `scale` (int8, value × 10^scale is the actual amount). Default 0.
- **Volume unit** [v1.2, V31-16]: equity `volume` is the number of shares, derivatives the number of contracts. It MUST NOT be stored in exchange or vendor lot units (100 shares, 1,000 shares) (this was always forbidden but unchecked → V011 warning added). If `value_traded` exists, the checker computes `R = median(value_traded / (volume × (high + low + close)/3))` per instrument and year, and if it is outside [0.5, 2] emits V011 (count and R value, hint "volume may be in lots"). Otherwise the `tds check` summary says "volume unit unverified".

### 3.5 Keys, sort, uniqueness

- Each dataset has a `key` (a set of columns that must be unique) and a `sort` (row order inside files) (chapter 5). They are also written in the manifest.
- Partition columns may be part of the key. Sort order is required only within a partition. For a partition with several files, the concatenation in file-name order must be sorted (K002).
- Key uniqueness is checked across the whole dataset (K001).

### 3.6 Partitions and files

- Hive-style `key=value` folders. Partition column values are **not stored inside files** (they are read from the path). Value hashes and checks use the logical table with partition columns filled from path values. [decided; conflict with the opposite convention in chapter 13 Q9]
- The type of a partition value is written in the dataset schema (e.g. `year` = i16, `date` = date32, `market` = code).
- File names: `part-<5-digit sequence>.parquet` (e.g. `part-00000.parquet`). Tables split by time range, like tick data, MAY use `<ts_min>_<ts_max>.parquet` (Nautilus style, with `:` and `.` in the RFC 3339 times replaced by `-`). Time ranges of files in the same partition MUST NOT overlap (K004).
- Small tables (security master etc.) have no partition: `<dataset>/part-00000.parquet`.

### 3.7 Parquet physical rules (recommended and required)

| Item | Rule |
|---|---|
| Format version | Parquet 2.6 or later logical types (needed for ns times). INT96 forbidden (required) |
| Compression | zstd recommended. Hashes are independent of compression |
| Statistics | Column statistics required (used for pruning and by the checker's `schema` level). Page index recommended |
| Row group | About one month for daily tables, 64–256MB for tick tables recommended |
| Dictionary | Recommended for repeated strings (id, code) |
| Bloom filter | Optional on `instrument_id` of tick tables |
| Key-value metadata | Put `tds.dataset` and `tds.schema_version` in the Parquet file metadata (required). Do not put the write time |
| Writer tool | Record name and version in the manifest `writer` |

### 3.8 Market

- Market = a group with one calendar, one default currency and one default time zone. Declared in the manifest `markets` (e.g. `KR`: XKRX, KRW, Asia/Seoul; `US`: XNYS, USD, America/New_York; `CRYPTO`: `CRYPTO-UTC`, USD, UTC).
- The market code is the unit of partitions (`market=`) and engine sleeves (specification 1.2). One instrument belongs to one market (`instruments.market`).
- The market's **completeness watermark** (`complete_through`): a promise that all data up to that instant is present. The engine's `live` does not use sessions after it for fills (specification 4.3).

---

## 4. Package structure and the manifest `tds.json`

### 4.1 Folder shape

One package = one immutable folder (snapshot).

**Producer-native packages and immutability** [v1.2, V31-PUB-01]:
- A package MAY be written **directly** by the producer's build (with no separate export or conversion layer). Example: the producer database holds tables identical to the TDS datasets in name, columns, types and enums, and the build swap step writes the snapshot folder in this chapter's Parquet layout + `tds.json` (including hashes). However it was made, the standard looks only at the resulting folder.
- **Immutability holds per snapshot folder**: once a `<snapshot_id>/` folder is published, its file contents and `tds.json` do not change. To change something, write a new folder with a new `snapshot_id`.
- Partition files MAY be **copy-on-write clones, hard links, or content-addressed storage inside the package**: a partition whose file sha256 (`files[].sha256`) equals the previous snapshot's can be reused without rewriting (saves disk). **Clones are recommended first** (APFS `clonefile`, Linux reflink): accidentally modifying one side does not change the other snapshot with it. Use hard links only on file systems without clones, and then keep published files read-only [v1.3, R3-16]. What determines content is the **hash**, not the path or inode — the physical hash is computed from paths and file sha256, and the value and semantic hashes from the 4.5 canonical serialisation, so the hash rules do not change. Therefore the producer **never modifies a published file in place** (MUST; with hard links both snapshots would change together and immutability breaks; on deletion the data disappears only when the link count reaches 0). Changed partitions are written only as new files.
- **Publish procedure** [v1.3, R3-16]: write everything to a staging folder → check (`tds check`) → make published files read-only (SHOULD, `chmod a-w`) → atomically switch the latest marker (a distribution convention such as `LATEST`). On failure, do not switch the latest marker. Producers that use links SHOULD compare the sha256 of shared files (link count > 1) against the previous `tds.json`. Content-addressed storage MUST be a path inside the package or come in via links or clones; symbolic links pointing outside the package remain forbidden (M012).
- **Consumer file identity check** (recommended): a consumer MAY record `(dev, inode, size, mtime_ns)` for each file whose sha256 it verified and recompute if they differ. The identity check defends against accidental modification and is not a cryptographic proof (the `full` check reads every byte).
- **Consumers do not require write permission on the package**: the checker and the engine only read the package, and caches, stamps and pins live outside the package (in a consumer-side folder). They must work as is on read-only mounts and hard-linked files.
- Why time-travel table formats (DuckLake, Iceberg etc.) are not used instead of packages: they tie consumers to one catalog format, the package stops being a self-contained folder, and "what was in the table then" (transaction time) is not "what could be known then" (`ts_available`, chapter 6). Producers are free to use such formats internally (for their benefits in transactions, concurrency, schema evolution and retention); the standard looks only at the published package [v1.3]. Point-in-time is defined by the standard's availability-time columns; the snapshot is only the unit of reproduction.

```
<package>/
  tds.json                                   manifest (required)
  dictionary/columns/part-00000.parquet      column dictionary (required if there are feature_panels or fundamentals items)
  dictionary/items/part-00000.parquet        fundamentals item dictionary (required if there are fundamentals)
  dictionary/codes/part-00000.parquet        meanings of open enum values (optional)
  instruments/part-00000.parquet             (required)
  instrument_symbols/part-00000.parquet
  instrument_xref/part-00000.parquet
  calendar_sessions/part-00000.parquet
  calendar_segments/part-00000.parquet
  bars/freq=1d/market=KR/year=2024/part-00000.parquet
  bars/freq=1m/market=US/date=2024-01-02/part-00000.parquet
  tradability_daily/market=KR/year=2024/part-00000.parquet
  market_rules/part-00000.parquet           (optional, v1.2)
  corporate_actions/part-00000.parquet
  delistings/part-00000.parquet
  share_counts/market=US/part-00000.parquet
  fx_rates/part-00000.parquet
  fundamentals_events/market=KR/part-00000.parquet ...
  fundamentals_state/edition=strict/market=KR/part-00000.parquet
  classifications/part-00000.parquet
  universe_membership/part-00000.parquet
  eligibility_daily/market=KR/year=2024/part-00000.parquet
  feature_panels/name=factor_pit_monthly/edition=strict/year=2024/part-00000.parquet
  label_panels/name=label_monthly/year=2024/part-00000.parquet
  trades/venue=XNAS/date=2024-01-02/<ts_min>_<ts_max>.parquet          (ticks, optional)
  ...
```

- Files not listed in the manifest are not part of the package (checker M005 warning; the engine does not read them).
- Paths are relative to `tds.json`, so they stay correct when the package is moved.
- Distribution conventions (latest marker `LATEST`, pin list `PINS`, number kept) are outside the standard. They remain producer conventions (as in specification 4.1).

### 4.2 `tds.json` fields

```json
{
  "$schema": "tds/schemas/1.0/tds.schema.json",
  "tds_version": "1.0",
  "name": "example-kr-us-equity",
  "id": "urn:uuid:6f1c…",
  "version": "20261027-143144",
  "snapshot_id": "20261027-143144",
  "parent_snapshot_id": "20261026-204108",
  "created": "2026-10-27T06:05:46Z",
  "title": "Example KR+US equities",
  "licenses": [{"name": "proprietary"}],
  "producer": {"name": "example-producer", "version": "build-I", "commit": "0000000",
               "checks": {"passed": 92, "total": 92},
               "hints": {"TDS-A001": "rebuild cum factors from corporate_actions (export step 'factors')",
                         "fallback:F-01": "open/high/low not yet exported for this market"}},
  "profiles": ["tds:equity-daily-core@1.0", "tds:equity-daily-research@1.0", "tds:pit-fundamentals@1.0"],
  "id_namespaces": {
    "KR": "KR listed securities: 6-char KRX short code (+ suffix on reuse); never reused",
    "US": "US securities: ticker at first listing (+ digit on reuse, us-identity-v1); never reused",
    "IDX": "benchmark indices"
  },
  "currencies": [],
  "markets": {
    "KR": {"calendar_id": "XKRX", "currency": "KRW", "timezone": "Asia/Seoul",
           "complete_through_session": "2026-10-27", "complete_through": "2026-10-27T06:30:00Z"},
    "US": {"calendar_id": "XNYS", "currency": "USD", "timezone": "America/New_York",
           "complete_through_session": "2026-10-26", "complete_through": "2026-10-26T20:00:00Z"}
  },
  "editions": {"default": "strict",
               "values": {"strict": "filing-sourced lineage only (strict-by-column-v1)",
                          "compare": "vendor values allowed (comparison)"}},
  "policies": {"fundamentals_resolution": "fund-resolution-v1", "delisting": "exit-value-v1",
               "adjustment": "adj-forward-cum-v1", "eligibility": "investable-v1",
               "availability_default": "next_session_open"},
  "roll_rules": {},
  "datasets": [
    {"name": "bars_1d", "kind": "bars", "schema_version": "1.0", "path": "bars/freq=1d",
     "partitioning": [{"name": "freq", "type": "code"}, {"name": "market", "type": "code"}, {"name": "year", "type": "i16"}],
     "key": ["instrument_id", "session_date"], "sort": ["session_date", "instrument_id"],
     "params": {"freq": "1d", "price_basis": "raw", "density": "dense", "bar_time": "session"},
     "availability": {"rule": "ts_end"},
     "pit_quality": "native",
     "rows": 60700000, "value_sha256": "…",
     "coverage": {"instruments": 27627, "ts_min": "1995-05-02", "ts_max": "2026-10-27",
                  "by_market": {"KR": {"instruments": 5495, "first": "1995-05-02", "last": "2026-10-27", "rows": 15700000}}},
     "columns": [{"name": "instrument_id", "type": "id", "nullable": false}, "…"],
     "files": [{"path": "bars/freq=1d/market=KR/year=1995/part-00000.parquet", "rows": 123456, "bytes": 4567890,
                "sha256": "…", "stats": {"session_date": ["1995-05-02", "1995-12-28"]}}]}
  ],
  "hashes": {"physical_sha256": "…", "value_sha256": "…", "semantic_sha256": "…", "hash_spec": "tds-hash-1"},
  "writer": {"name": "pyarrow", "version": "26.0.0", "row_group_rows": 200000}
}
```

| Field | Required | Meaning |
|---|---|---|
| `tds_version` | ○ | Standard version `MAJOR.MINOR` |
| `name`, `id`, `version`, `created` | name, created ○ | Same meaning as Data Package v2. `version` = package version (e.g. snapshot_id) |
| `snapshot_id`, `parent_snapshot_id` | ○ / optional | Immutable version id. Previous version (for diffing) |
| `producer` | ○ | Producing tool, version, commit, check results. Optional `hints`: `{"<TDS code>" or "fallback:<id>": "sentence"}` — a producer-side fix that the consumer shows next to errors and warnings with that code (the consumer does not know any particular producer) [v1.1, MINOR addition] |
| `profiles` | ○ | Profiles and versions this package declares it follows (`tds:<name>@<MAJOR.MINOR>`, chapter 7; without `@` means `@1.0`). Verified by the checker |
| `id_namespaces` | ○ | Id namespaces used, with descriptions |
| `currencies` | optional | Declarations of currencies outside ISO 4217 |
| `markets` | ○ | 3.8. The watermark fields (`complete_through_session`, `complete_through`) change on every publish, so consumers SHOULD use only the stable fields (`calendar_id`, `currency`, `timezone`) in their partition cache keys [v1.3, R3-04] |
| `editions` | ○ if any table uses editions | Edition names and meanings, default edition |
| `policies` | optional | Producer rule names and versions (kept as is in the engine run record) |
| `roll_rules` | ○ if there are futures continuous contracts | 5.22 |
| `datasets[]` | ○ | Per dataset: `name`, `kind`, `schema_version`, `path`, `partitioning`, `key`, `sort`, `params` (kind-specific parameters), `availability` (a 6.2 rule or `{"column": "ts_available"}`), `pit_quality` (`native` / `backfilled` / `mixed`), `rows`, `value_sha256`, `coverage`, `columns` (name, type, null, unit, description), `files[]` (path, rows, bytes, sha256, min/max of main columns, **optional `value_sha256`** — the value hash of the 4.5 canonical value serialisation over that file's rows only, partition columns included; advisory for consumers — this value is at H004 warning level, so a wrong value does not block the package, and consumers therefore do not use an unverified `value_sha256` as a cache identity; per-partition cache identity is set by the file `sha256` [v1.2, V31-12; v1.3, R3-04]). **Path safety**: every `path` is relative to the package folder, and `..`, absolute paths and symbolic links leading outside are forbidden (M012); the same file path must not appear twice (M013) [v1.1] |
| `hashes` | ○ | 4.5 (`physical_sha256`, `value_sha256`, `semantic_sha256`, `hash_spec`) |
| `writer` | ○ | Writer tool, row-group row count |

### 4.3 Coverage block

Each dataset records the following. With it the engine reports before a run "is this data present for this period" (linked to the specification R-22 warning).

- `instruments`: number of distinct `instrument_id`.
- `ts_min`, `ts_max` (or dates): the range the data covers.
- `by_market`: the same values and row counts per market.
- Optional `by_item`: first year and fill ratio per fundamentals or panel column (as numerator/denominator).

### 4.4 Column dictionary (`dictionary/`)

| Dataset | Key | Columns |
|---|---|---|
| `dictionary/columns` | (`dataset`, `column`) | `dataset`, `column`, `type`, `unit`, `currency_source` (`column:<name>` / `instrument` / `fixed:<code>` / null), `scale`, `freq` (daily/monthly/event/…), `edition_class` (name of the strict eligibility rule), `start_by_market` (json), `description`, `alias_of`, `std_name` (that name if it equals a TDS standard item), `is_label` (bool; if true, forbidden as a decision input) |
| `dictionary/items` | `item` | `item`, `std_item` (5.17 core item name or null), `statement` (IS/BS/CF/other), `flow_or_stock` (flow/stock), `unit`, `description`, `source_concepts` (json: XBRL concepts etc.) |
| `dictionary/codes` | (`field`, `code`) | `field`, `code`, `label`, `description`, `maps_to` (value when read as a closed TDS enum) |

### 4.5 Hashes (`hash_spec = "tds-hash-1"`) [v1.1, RV-C10]

Three hashes are kept separately. The v1 "logical hash = Arrow IPC bytes" varied with the Arrow implementation, version and buffer alignment, so producers in other languages could not produce the same value; it was changed before 1.0.

- **File hash**: sha256 of the file bytes (lowercase hex).
- **Physical hash** `physical_sha256` = sha256(bytes of `"{path}\t{sha256}\n"` concatenated in ascending path order). Means file integrity only.
- **Dataset value hash** `value_sha256` — **canonical value serialisation** (same bytes from any language or library):
  1. Build the logical table with partition columns filled from path values (dictionaries decoded to values). Column order = schema file order (declaration order), then `x_` extension columns in ascending name order.
  2. Row order = ascending by the `key` columns (value comparison: numbers by magnitude, strings by UTF-8 byte lexicographic order, null first); ties broken by the remaining columns with the same rule.
  3. Header bytes: `b"TDSV1\n"` + per column `name (UTF-8) + b"\t" + type tag + b"\n"` + `b"\n"`.
  4. Per row, **cell bytes** in column order: if null, one byte `0x00` (no value). Otherwise `0x01` + value bytes: `bool` 1 byte (0/1); `i8/i16/i32/i64` widened to int64, 8 bytes little-endian; `f64` IEEE-754 bits, 8 bytes little-endian (−0.0 normalised to +0.0; NaN already forbidden by S009); `date` int32 epoch days, 4 bytes LE; `ts_us`/`ts_ns` int64 in that unit, 8 bytes LE (the unit is fixed by the dataset kind, K2); `string`/`id`/`code` length u32 LE + UTF-8 bytes (NFC normalisation assumed; the checker reports non-NFC as W); `fixed` (int64 fixed point) int64 8 bytes; `list<T>` element count u32 LE + the element cell bytes.
  5. sha256 over the header + all row bytes concatenated (streaming).
- **Package value hash** `value_sha256` = sha256(`"{name}\t{value_sha256}\n"` in ascending dataset name order).
- **Package semantic hash** `semantic_sha256` = sha256(canonical JSON{`tds_version`, `hash_spec`, per dataset {`name`, `kind`, `schema_version`, `value_sha256`, `params`, `availability`, `pit_quality`, `key`, column units, `price_exponent`, `size_exponent`}, `markets`, `id_namespaces`, `editions`, `policies`, `currencies`, `roll_rules`, `profiles`}). Canonical JSON = keys ascending, no whitespace, UTF-8, numbers in shortest round-trip form. Even with the same Parquet, the semantic hash changes when availability rules, exponents, policies, markets, editions or profile declarations change. `producer`, `created`, `writer`, `coverage`, `files` and `title` are not included.
- **Consumer use**: engine caches, decision records and reruns use the **semantic hash** as the definition of "same data". The physical hash is only for confirming that files have not changed.
- **Test vectors**: `conformance/hash-vectors.json` (10 small tables: every type, null, −0.0, empty string, non-ASCII, partition columns, sort ties; hex of the expected byte stream and the sha256) is distributed with the standard. Independent implementations MUST match these vectors (10.5 graduation criteria).

---

## 5. Dataset kinds

How to read the tables: **Type** uses the names from 3.2. **Null**: no = value required. **Key, sort, partitions** are at the head of each table. "Checks" are chapter 8 error codes.

### 5.1 `instruments` (security master) — required in every profile

Key `instrument_id`. Sort `instrument_id`. No partition (`asset_class=` if needed).

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id | id | no | K1 |
| asset_class | code (closed) | no | `equity`, `etf`, `fund`, `index`, `future`, `option`, `crypto_spot`, `crypto_perp`, `crypto_future`, `fx_spot`, `bond`, `rate`, `other` |
| category | code (open) | yes | Share type: `common`, `preferred`, `adr`, `reit`, `spac`, `unit`, `warrant`, `right`, `closed_end_fund`, `other` |
| market | code | no | Key of the manifest `markets` |
| venue_mic | code | yes | MIC of the primary venue (segment allowed) |
| operating_mic | code | yes | Operating MIC |
| calendar_id | id | no | `calendar_sessions.calendar_id` |
| currency | code | no | Trading currency (ISO 4217 or a declared currency) |
| issuer_id | id | yes | Company grouping (opaque) |
| name | string | yes | Current name (history in `instrument_symbols`) |
| listed_on | date | no | First session (within what this package knows; for listings earlier than the data start, the first data session + `listed_on_censored = true`) |
| listed_on_censored | bool | yes | true = the actual listing is earlier |
| last_session | date | yes | Last price session (null while listed) |
| delisted_on | date | yes | Ledger exit date (must equal `delistings`, R008) |
| lot_size | f64 | no | Minimum order unit (shares, contracts, coins). Default 1 |
| tick_size | f64 | yes | Fixed tick size. If it varies by price band, null + `tick_rule_id` |
| tick_rule_id | id | yes | Price-band tick rule (`market_rules.rule_id`, 5.27; defined in v1.2) [V31-05] |
| multiplier | f64 | no | Contract multiplier. Equities 1.0 |
| price_precision | i8 | yes | Price decimal places (for tick data checks) |
| size_precision | i8 | yes | Size decimal places |
| underlying_instrument_id | id | yes | Underlying of a derivative |
| root | string | yes | Futures or options product root (e.g. `ES`, `AAPL`) |
| ts_expiry | ts_us | yes | Expiry instant (futures, options) |
| ts_last_trade | ts_us | yes | Last trading instant |
| first_notice_date | date | yes | Futures first notice date |
| settlement_type | code | yes | `cash` / `physical` |
| strike | f64 | yes | Strike (price unit) |
| option_right | code | yes | `call` / `put` |
| exercise_style | code | yes | `american` / `european` / `bermudan` |
| base_currency, quote_currency | code | yes | Crypto and FX pairs |
| settlement_currency | code | yes | Settlement currency of futures and perpetuals |
| is_inverse | bool | yes | Inverse contract (crypto) |
| index_kind | code | yes | `TR` (total return) / `PR` (price) / `NTR` — when `asset_class = index` |
| index_weighting | code (open) | yes | Index weighting method `cap` / `float_cap` / `equal` / `price` / `other` — when `asset_class = index`. Consumers show it in benchmark comparisons [v1.2, V31-15] |
| is_synthetic | bool | no | true = not an actually tradable object (continuous contracts, indices). The engine does not use it for fills |

Checks: R001 (an id in another table is missing here), V020 (required columns per `asset_class`: option requires underlying, strike, right, style, expiry, multiplier, settlement; future requires root, expiry, multiplier, settlement; crypto requires base and quote), T010 (`last_session < listed_on`), R002 (calendar missing).

**After-the-fact static table** [v1.1, RV-C08]: `instruments` is a timeless "what is known now" table. `name`, `last_session` and `delisted_on` are after-the-fact information, so consumers MUST NOT use them as decision inputs (only for listing-period masks, display and delisting handling). If an instrument's changeable attributes (`category`, `venue_mic`, `currency`, `lot_size`, `tick_size`) actually changed, the producer also exports that history in `classifications` under a scheme of the same name (`category`, `venue_mic` …, two time axes), and consumers read that scheme when present. `asset_class`, `market` and `calendar_id` do not change within one id (a change means a new id, K1(d)).

### 5.2 `instrument_symbols` (symbol history)

Key (`instrument_id`, `symbol_type`, `venue_mic`, `valid_from`, `ts_known_from`) (v1.1: known axis and venue added). Sort same.

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id | id | no | |
| symbol_type | code (open) | no | `ticker` (exchange symbol), `local_code` (Korean short code etc.), `name`, `vendor:<name>` (e.g. `vendor:sharadar`, `vendor:lean`, `vendor:databento_raw`) |
| symbol | string | no | |
| venue_mic | code | yes | |
| valid_from | date | no | Effective start (inclusive) |
| valid_to | date | yes | Effective end (exclusive), null = still current |
| ts_known_from | ts_us | yes | Instant this mapping became known (null = treated as the session open of valid_from) |
| ts_known_to | ts_us | yes | End of trust in this record (exclusive), null = still current. A corrected symbol mapping closes the old row's `ts_known_to` and adds a new row [v1.1] |
| source | string | yes | |

- The same `(symbol_type, symbol, venue_mic)` may point to different ids in different periods (reuse). **Pointing to two ids at the same known time and the same effective period is an error**, K010.
- The lookup is the two-time-axis rectangle (6.3).
- Intervals of the same `symbol_type` for one id do not overlap (T003).

### 5.3 `instrument_xref` (external identifier links)

Key (`instrument_id`, `id_type`, `id_value`, `valid_from`). Columns: `instrument_id`, `id_type` (open: `figi`, `figi_composite`, `figi_share_class`, `isin`, `cusip`, `sedol`, `permno`, `permco`, `gvkey_iid`, `cik`, `lei`, `sharadar_permaticker`, `lean_sid`, `nautilus_instrument_id`, `databento_instrument_id`, `occ_osi`, `dart_corp_code` …), `id_value` string, `valid_from` date null (unknown), `valid_to` date null, `link_quality` code (`primary`/`secondary`/`inferred`), `source`.
- Publisher ids that change daily, as in Databento, are written as one-day intervals `valid_from = valid_to − 1 day`. 64-bit unsigned publisher ids go into `id_value` as decimal strings (no precision loss) [v1.1].
- Known axis: `instrument_xref` has no known time in v1. The two-time-axis promise of K6 therefore **does not apply** to this table (for explanation and mapping, not a decision input). Links that need a known time get optional `ts_known_from/to` columns in the next MINOR [v1.1].
- Company-level links like CRSP CCM (GVKEY ↔ PERMNO) use `id_type = gvkey_iid`, with the meaning of LINKPRIM carried into `link_quality`.

### 5.4 `calendar_sessions` (sessions) — required in daily-and-above profiles

Key (`calendar_id`, `session_date`). Sort same.

| Column | Type | Null | Meaning |
|---|---|---|---|
| calendar_id | id | no | MIC preferred (`XKRX`, `XNYS`), otherwise `CRYPTO-UTC`, `CME-GLOBEX-EQ` etc. |
| session_date | date | no | Trading day (for futures, the settlement trading day) |
| ts_open | ts_us | no | Regular session start instant |
| ts_close | ts_us | no | Regular session close instant (half days and hour changes reflected) |
| session_ord | i32 | yes | Consecutive number from 0 within the calendar (checked by K011 if present) |
| is_half_day | bool | yes | |
| session_kind | code | no | `regular`, `continuous_24h` (crypto UTC day), `special` |
| calendar_version | string | yes | Session table version |
| source | string | yes | e.g. `exchange_calendars+prices` |

- The session table is built by reconciling schedule data with prices. A session is not removed because some instrument has no price (specification 4.6).
- 24/7: `session_date` = UTC date, `ts_open` = 00:00Z, `ts_close` = 00:00Z of the next day.
- Futures overnight trading: the session of trading day D may start on the evening of D−1 (`ts_open < session_date 00:00 local`). This is normal.

`calendar_segments` (optional, intraday segments): key (`calendar_id`, `session_date`, `segment`, `ts_start`). `segment` code: `pre`, `opening_auction`, `continuous`, `break`, `closing_auction`, `post`, `single_price_period` etc. Used by the intraday fill model (E4) and for Korean single-price periods.

### 5.5 `bars` (bars, all periods)

Partitions: daily `freq=1d/market=/year=`, minute and hour bars `freq=/market=/date=` (one folder per day). Key: daily (`instrument_id`, `session_date`), intraday (`instrument_id`, `ts_start`, `price_type`). Sort: daily (`session_date`, `instrument_id`) — for cross-sectional reads; intraday (`instrument_id`, `ts_start`).

Parameters (`params`): `freq` (`1d`, `1w`, `1mo`, `1h`, `30m`, `5m`, `1m`, `1s` …), `price_basis` (`raw` default / `split_adjusted` / `total_adjusted` — the latter two only in `tds:minimal-daily`), `density` (`dense` = a row for every interval during the instrument's life / `sparse` = only intervals with trades), `bar_time` (`session` = session-bounded daily bar / `utc_day` = UTC-date daily bar / `interval`), `aggregation` (`time` default; `tick`, `volume`, `value` bars also allowed — then `ts_start/ts_end` vary), `source_kind` (`external` vendor bar / `internal` bar built from trades), `ready_delay` (ISO 8601 duration, optional; when the availability rule is `column`, the delay after which a market-axis row freezes — consumers treat a bar published after `ts_close + ready_delay` as missing in that row; for rule `ts_end+P` it is taken to equal P) [v1.1]. If `price_basis` is not `raw`, the package's bars cannot be used for raw-price accounting (chapter 7 `minimal-daily`).

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id | id | no | |
| session_date | date | no | Trading day. Required for intraday bars too (futures overnight → next trading day) |
| ts_start | ts_us/ns | daily yes / intraday no | Interval start (inclusive). If null on a daily bar, the session `ts_open` |
| ts_end | ts_us/ns | daily yes / intraday no | Interval end (exclusive). If null on a daily bar, the session `ts_close`. **A bar is complete at `ts_end`** |
| price_type | code | yes | `last` (default, trade price) / `bid` / `ask` / `mid` (Nautilus price_type) |
| open, high, low, close | f64 | yes | Raw prices (local currency). Null allowed if `obs_status ∈ {halted, missing, no_trade}` |
| volume | f64 | yes | Raw volume (shares, contracts, coins) |
| value_traded | f64 | yes | Traded value (local currency) |
| trade_count | i64 | yes | Number of trades (Massive `transactions`) |
| vwap | f64 | yes | |
| open_interest | f64 | yes | Futures and options open interest (as of the bar end; official values in `market_statistics`) |
| obs_status | code (closed) | no if dense | `traded` / `no_trade` (no trades) / `halted` (halted) / `missing` (no data, reason unknown) |
| cum_factor_split | f64 | yes | K4. First listed session 1.0 (daily bars only) |
| cum_factor_total | f64 | yes | Cumulative factor including cash distributions (daily bars only) |
| ts_available | ts_us | yes | Column or rule (default rule `ts_end`; if vendor daily data arrives late, include the delay with rule `ts_end+P`) |
| source | code | yes | |

- Daily `dense`: per instrument exactly one row for every session of its calendar from `listed_on` to `last_session` (or the market watermark if absent) (D001). Rows on dates outside sessions are forbidden (D002).
- Price check V001: `low <= min(open, close)`, `high >= max(open, close)`, `low <= high` (when all values exist). Raw prices lie on the price grid (5.27 grid norm, V012 W) [v1.2, V31-05]. The `volume` unit follows 3.4 (V011 W) [v1.2, V31-16]. V002 negative prices and volumes forbidden (instruments that allow negatives, such as indices and spread contracts, declare an exception via `instruments.category`). V004: if `obs_status = traded`, `close` is required.
- Daily close = official close (Korean closing single-price auction, US official close). If different, use an `x_` column.
- `shares_out` (specification 4.7) is removed from bars and moved to `share_counts` (because its availability time differs from prices; chapter 12 D9). A producer convenience column `x_<ns>_shares_out` is allowed.
- Continuous contract bars: the `instrument_id` is a continuous instrument with `is_synthetic = true`, and `params.roll_rule` is stated (5.22).

### 5.6 `trades` (trade ticks) — `status: experimental` [v1.1]

> The schemas of 5.6–5.9 and 5.22–5.24 are **experimental**: until lossless import and pinned replay cases exist they are outside the 1.x compatibility promise (10.2) and may change in the next MINOR. Their schema files say `status: experimental`, and the checker emits W (M015) for packages containing these datasets. Only the daily equity datasets (5.1–5.5, 5.10–5.21, 5.25–5.26) are `stable` [RV-I07].

Partition `venue=/date=` (date = `session_date`). Key (`instrument_id`, `ts_event`, `sequence`, `trade_id`) (if trade_id is nullable it drops out of the key and `sequence` must be unique). Sort (`instrument_id`, `ts_event`, `sequence`). Time unit ns. Parameters `price_exponent`, `size_exponent`.

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id | id | no | |
| session_date | date | no | |
| ts_event | ts_ns | no | Exchange trade instant |
| ts_recv | ts_ns | yes | Receive instant (collection system) |
| sequence | i64 | no | Exchange or vendor sequence number (if absent, an in-file order number) |
| price | fixed | no | |
| size | fixed | no | |
| aggressor_side | code | no | `buy` / `sell` / `none` (Databento B/A/N, Nautilus AggressorSide) |
| trade_id | string | yes | |
| venue_mic | code | yes | Actual venue in consolidated trade data |
| conditions | list<code> | yes | Trade condition codes (original vendor codes, `dictionary/codes`) |
| action | code | no | `new` / `cancel` / `correct` (corrected and cancelled trades) |
| flags | i32 | yes | Vendor flag bits (to keep Databento values as is) |

Default availability rule: if `ts_recv` is present, `ts_recv`; otherwise `ts_event + params.assumed_latency` (declaration required). T008: warning if `ts_recv < ts_event − tolerance` (hftbacktest's negative latency).

### 5.7 `quotes` (L1 quotes / BBO) — `experimental`

Partitions and sort are the same as `trades`. Key (`instrument_id`, `ts_event`, `sequence`).

Columns: `instrument_id`, `session_date`, `ts_event`, `ts_recv`, `sequence`, `bid_px` fixed null, `bid_sz` fixed null, `ask_px` fixed null, `ask_sz` fixed null, `bid_ct` i32 null, `ask_ct` i32 null, `venue_mic`, `conditions`, `flags`.
- A row is "the best bid and offer state on both sides from that instant on". If one side is empty, that side is null. Ticks where only one side changed, as in LEAN, have the other side filled from the previous value at import (chapter 9).
- V030: `bid_px >= ask_px` (locked or crossed) is a warning (may be normal in some markets).

### 5.8 `book_deltas`, `book_snapshots` (L2/L3 books) — `experimental`

`book_deltas` — partition `venue=/date=`, sort (`instrument_id`, `ts_event`, `sequence`), time ns. Parameters `depth_kind` (`mbp` L2 by price level / `mbo` L3 by order), `max_depth` (for mbp).

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id, session_date | | no | |
| ts_event, ts_recv | ts_ns | no / yes | |
| sequence | i64 | no | |
| action | code (closed) | no | `add`, `modify`, `cancel`, `clear`, `trade`, `fill`, `none` (Databento A/M/C/R/T/F/N) |
| side | code | no | `bid` / `ask` / `none` |
| price | fixed | yes | null for `clear` |
| size | fixed | yes | mbp: new total size at that level (0 = level removed). mbo: size of that order |
| order_id | i64 | yes | Required for mbo |
| level | i16 | yes | Level number in mbp (optional) |
| is_snapshot | bool | no | Row from a replay or snapshot (Databento F_SNAPSHOT) |
| is_last | bool | no | Last row of the same event batch (F_LAST; the book is consistent only after this row) |
| flags | i32 | yes | Original bits |

- Reconstruction rule: the start of a file (or date) is either a batch of `is_snapshot = true` rows after a `clear`, or declares with `params.continuity = "carry"` that it carries over the last state of the previous date.
- The engine reads the book only after rows with `is_last = true`. V031: warning if a crossed book appears after reconstruction; V032: warning on `sequence` gaps (when the vendor promised consecutive sequence numbers).

`book_snapshots` — depth-N state at fixed intervals or per event. Long shape: key (`instrument_id`, `ts_event`, `side`, `level`). Columns `ts_event`, `ts_recv`, `side`, `level` (0 = best), `price`, `size`, `order_count`. Databento MBP-10 and Nautilus OrderBookDepth unrolled into rows.

### 5.9 `market_statistics` (official statistics) — `experimental`

Key (`instrument_id`, `stat_type`, `ts_event`). Columns: `instrument_id`, `session_date`, `stat_type` (open: `settlement_price`, `open_interest`, `official_open`, `official_close`, `auction_price`, `auction_volume`, `high_limit`, `low_limit`, `vwap`, `reference_price` …), `value` f64, `unit`, `ts_event`, `ts_available`, `is_final` bool (preliminary/final), `source`. Corresponds to Databento Statistics and Nautilus InstrumentClose. The availability time of futures settlement prices and open interest (usually the next morning) is recorded exactly here.

### 5.10 Tradability: `tradability_daily`, `trading_status_events`

`tradability_daily` — partitions, key and sort are the same as daily bars.

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id, session_date | | no | |
| status_known | bool | no | false = that day's status is unknown (US before 2019-08-23) |
| halted_full_day | bool | yes | Halted all day |
| halt_count | i32 | yes | Number of intraday halts |
| limit_up_close, limit_down_close | bool | yes | Close at the upper or lower limit |
| locked_up, locked_down | bool | yes | Locked at that price all day |
| price_limit_ratio | f64 | yes | That day's limit (0.30 = 30%) |
| up_limit_price, down_limit_price | f64 | yes | Upper and lower limit prices after tick rounding |
| reference_price | f64 | yes | Reference price for the limit |
| admin_status | code | yes | Administrative issue, investment caution etc. (open: `normal`, `administrative`, `caution`, `warning`, `liquidation_trading`) |
| ts_available | ts_us | yes | Rules per column group, **`params.availability_by_column` required** (v1.1): prior information (`price_limit_ratio`, `up/down_limit_price`, `reference_price`, `admin_status`) is `session_open`, day results (`halted_full_day`, `halt_count`, `limit_up_close`, `limit_down_close`, `locked_up`, `locked_down`) are `session_close` [RV-Q10] |
| source | code | yes | |

`trading_status_events` — intraday status changes. Key (`instrument_id`, `ts_event`, `sequence`). Columns `ts_event` (ns), `ts_recv`, `status` (`halted`, `resumed`, `auction`, `pre_open`, `closed`, `luld_pause` …), `reason` (original code), `reason_group`, `source`, `source_record_id`. Corresponds to Databento Status and Nautilus InstrumentStatus.

### 5.11 `corporate_actions` (corporate action events, including dividends)

Key `event_id`. Sort (`instrument_id`, `ex_date`, `event_id`). No partition (`market=` if large).

| Column | Type | Null | Meaning |
|---|---|---|---|
| event_id | id | no | Stable event id. A revision is a new id + `revision_of` |
| instrument_id | id | no | Affected instrument (old shares) |
| kind | code (closed) | no | `split`, `reverse_split`, `stock_dividend`, `bonus_issue` (bonus issue), `capital_reduction` (capital reduction, consolidation), `cash_dividend`, `special_dividend`, `return_of_capital`, `rights_issue`, `spinoff`, `stock_merger`, `cash_merger`, `mixed_merger`, `exchange_offer`, `symbol_change`, `name_change`, `par_change`, `other` |
| ex_date | date | no | Ex-rights or ex-dividend session (effective session). Must be a session (A005) |
| ts_effective | ts_us | no | Effective instant = that session's `ts_open` (default) |
| record_date | date | yes | Record date |
| declared_date | date | yes | Board resolution or announcement date |
| pay_date | date | yes | Cash payment or new share listing date |
| pay_date_status | code | no | `observed` / `estimated` / `missing` |
| ts_announced | ts_us | yes | Instant the event was made public (filing receipt) |
| ts_terms_available | ts_us | yes | Instant the amount or ratio was published as final (old Korean dividends: after the ex-date). null = same as `ts_announced` |
| ratio_num, ratio_den | i64 | yes | [v1.2, V31-01] **Exact rational form** of the quantity ratio (two positive integers, both present or both null): for split-like events `share_factor = num/den` (1:8 reverse split = 1/8, 7:1 = 7/1, 5% stock dividend = 21/20, stock dividend 0.29 = 129/100), for mergers and spinoffs `ratio_new_per_old = num/den` (exchange ratio 0.4237 = 4237/10000). Consumers treat this as canonical and use integer arithmetic `q' = (q·num) div den`. The f64 column is its quotient (auxiliary). **[v1.4, R4F-01] Every event that changes the number of shares held** (`split`, `reverse_split`, `stock_dividend`, `bonus_issue`, `capital_reduction` that is a share consolidation, `spinoff`, `stock_merger`, `mixed_merger`, `exchange_offer` with a share exchange, `rights_issue` with an allotment ratio) **MUST fill `ratio_num/ratio_den`.** Check A010 (**E**, W → E in v1.4): for such an event both null, only one present, ≤ 0, or differing from the f64 column by more than 1e-12 relative. Consumers do not infer a rational from the f64 column (the v1.3 allowance "infer and record" is removed — from f64 alone one cannot tell whether 0.333 is 1/3 or 333/1000). For external data without exact ratios, only when the user explicitly opts in via a consumer setting (NexusBT `[corporate_actions] decimal_ratio = "literal"`) MAY the shortest round-trip decimal form of the f64 be used as an exact decimal fraction (0.333 → 333/1000); A010 is then lowered to a warning and the consumer records the count in the report |
| ratio_new_per_old | f64 | yes | New shares received per old share (2:1 split → 2.0, 1:10 reverse split → 0.1, stock dividend b → b, merger exchange ratio, spinoff allotment ratio) |
| new_instrument_id | id | yes | Instrument received (stock_merger, spinoff, exchange_offer) |
| cash_per_share | f64 | yes | Cash per old share (dividend, cash merger, basis for cash in lieu) — **raw amount (on that day's share basis)** |
| currency | code | yes | Currency of cash_per_share |
| gross_or_net | code | yes | `gross` / `net` (before/after withholding) |
| subscription_price | f64 | yes | Rights issue subscription price (rights) |
| price_factor | f64 | yes | This event's price multiplier m_e (below). Required if `factor_method ≠ unavailable` (A003). If it cannot be computed, null + `factor_method = unavailable`, not 1.0 |
| share_factor | f64 | yes | How many shares one old share becomes (multiplier of holdings, volume and share counts; split r → r, stock dividend b → 1 + b, cash and rights events 1.0). If null for split-like kinds (`split`, `reverse_split`, `stock_dividend`, `bonus_issue`, `capital_reduction`), it is built by the `ratio_new_per_old` rule. **For other kinds it is not inferred from the reciprocal of the price factor** (rights, distributions and spinoffs have different price and quantity effects) [v1.1] |
| affects | code | no | `split_and_total` (events that change the share count) / `total_only` (cash distributions) / `none` (name changes etc.) |
| factor_method | code | no | `ratio` (split-like: 1/(r)), `cash_prev_close` (1 − D/close[e−1]), `terp` (rights: theoretical ex-rights price/close[e−1]), `spinoff_first_close` (1 − allotment ratio × new company's first close/close[e−1]), `vendor` (vendor factor as is), `unavailable` |
| factor_ref_price | f64 | yes | Reference price used for the factor (close[e−1] etc.) |
| revision_of | id | yes | |
| status | code | no | `announced` / `effective` / `cancelled` |
| source, evidence_id | string | yes | Original document id |

**Factor rules (m_e).** Split, reverse split, consolidation: `1 / ratio_new_per_old` (a reverse split has ratio < 1 → m > 1). Stock dividend or bonus issue b: `1 / (1 + b)`. Cash dividend D: `1 − D / close[e−1]` (same formula as zipline [verified]). Rights issue: `TERP / close[e−1]`, `TERP = (close[e−1] + n·S) / (1 + n)` (n = new shares per old share, S = subscription price). Spinoff: `1 − ratio × first_close(new) / close[e−1]` (or computed by the producer from the disclosed reference price; stated in `factor_method`). When an instrument disappears through a merger, this is handled not by a factor but by `delistings` + holdings conversion (`price_factor = 1.0`, `affects = none`).

**Relation to cumulative factors.** `bars.cum_factor_split[s] / cum_factor_split[s−1]` = the product of `price_factor` of the `affects = split_and_total` events effective in that session (relative 1e-12, A001). total works the same way with all events. Sessions without events are exactly 1.0.

**Time.** A factor is effective from `ts_effective`, but consumers do not include an event in a decision where `ts_terms_available > decision time` (specification 5.3.4). So `cum_factor_*` are convenience values "assuming all events are known", and the event table is the right answer for look-ahead-free adjustment. This is stated as standard text. A spinoff factor (`spinoff_first_close`) can only be computed once the new instrument's first close exists, so `ts_terms_available >= ts_close(effective session)` must hold (A009). If the terms of a quantity-changing event are published after it takes effect, W (A008) [v1.1].

**Resolution procedure (at reference time c)** [v1.1, RV-C03] — adjustment, accounting and checks (A001) all use this one procedure (reference implementation `nexusbt_tds.actions.resolve(events, c)`):
1. Group events into chains by following `revision_of` (root = an event without `revision_of`; a cycle is A007).
2. The **existence time** of version r, `ts_known(r)` = the earliest non-null of `ts_announced` and `ts_terms_available` (if both are null, `ts_effective`); the **terms time** `ts_terms(r) = coalesce(ts_terms_available, ts_known(r))`. The version used at c = among versions with `ts_known(r) <= c`, the one with the maximum `ts_known` (ties: the last in ascending `event_id`). If none, "unknown" at c. If the chosen version has `ts_terms(r) > c`, it is "existence known but terms not yet published": the price effect is pending, the entitlement is an entitlement of unknown amount, and its quantity is fixed to the holding at the start of the effective session (it remains even if sold afterwards). The v1.2 `ts_pub = coalesce(ts_terms_available, …)` hid a version with late terms entirely until its terms were published, so this pending state could not be reached. `ts_effective` is used only when both other times are absent (if an event disclosed after it took effect became visible from the effective instant, that would be look-ahead) [v1.3, R3-01].
3. If the chosen version has `status = cancelled`, no effect; if `announced` with `ts_effective <= c`, no effect (consumer warning); if `effective`, it has effect.
4. Four effects: price factor `price_factor` (if null, "none" — the cumulative factor is also "none" at that boundary), quantity factor `share_factor` (rule above), entitlement (cash, new instrument, ratio), settlement (`pay_date`, `pay_date_status`).
5. When the version of a chain changes with c (revision, cancellation), the consumer corrects amounts already booked with correcting entries (it does not modify past entries).
6. A001 resolves with `c = +∞` (the whole package's knowledge), multiplying only one latest version per chain and reconciling cancelled chains as 1.0. A factor that multiplies both the old and the new version of the same event is an A001 error.

**Dividend date caution.** In Korea the record date ≠ the ex-date. Because of the settlement cycle, the ex-date is usually the business day before the record date [unverified: rules by period]. Data that knows only the record date derives `ex_date` by rule and leaves a column such as `x_<ns>_ex_date_method = 'record_minus_1_session'`.

### 5.12 (Handling data that has only factors)

Users with only LEAN factor files, Qlib `factor` or vendor adjusted closes reverse-engineer events from factor changes at import: wherever the factor ratio between consecutive sessions is not 1, one event with `kind = other`, `factor_method = vendor`, `price_factor = ratio`, `ts_terms_available = null` (= assumed known at the effective instant). The manifest says `pit_quality: "backfilled"`. The engine warns that it can adjust prices with these events but cannot do cash-dividend account handling. `kind = other` is the "unknown" value of a closed enum that affects execution, so consumers treat it as an "unsupported event" when held (no silent accounting) [v1.1].

### 5.13 `delistings` (delisting and exit events)

Key `delisting_id`. Sort (`instrument_id`, `exit_date`). Carries over the meaning of specification 4.11 and the producer policy `exit-value-v1` as is, with names changed to TDS rules only.

| Column | Type | Null | Meaning |
|---|---|---|---|
| delisting_id, instrument_id | id | no | |
| last_trading_date | date | no | Last price session |
| exit_date | date | no | Ledger exit date |
| ts_exit_known | ts_us | yes | Instant the exit became public. Nullable since v1.1 (many producers know it only after the fact): if null, it is taken as the open of the exit session and that dataset's `pit_quality` is `backfilled`/`mixed` [RV-Q09] |
| delist_type | code (open) | no | `merger`, `spac_merger`, `acquisition_cash`, `exchange_transfer`, `liquidation`, `performance`, `voluntary`, `expiry` (derivative or fund expiry), `unknown` |
| crsp_dlstcd_equiv | i16 | yes | CRSP delisting code equivalent (optional, for comparison) [unverified code table] |
| ref_date | date | no | Date of the reference price for the terminal value |
| ref_price | f64 | no | Raw reference price (for Korean liquidation trading, that price) |
| exit_value_status | code (closed) | no | `observed` / `estimated` / `unobserved` |
| ret_observed | f64 | yes | Observed terminal return relative to the reference price (`ref_price`, with only share-count units aligned) |
| ret_observed_includes_distributions | bool | yes | [v1.2, V31-04; v1.3, R3-05] true = `ret_observed` already includes cash distributions with ex-dates after `last_trading_date` (liquidating distributions etc.) (CRSP DLRET style) → observed total = `q·ref_units·(1 + r)`, and the distribution already booked at its ex-date is subtracted to set the remaining terminal amount (past entries are not erased by a flag that was unknown at the ex-date); false = not included → the distribution is booked separately and terminal = `q·ref_units·(1 + r)` (the observed amount is already net of the distribution, so the distribution factor is **not multiplied in**; the v1.2 "basis multiplied by the distribution factor" reduced the distribution twice); null = unknown (A011 W if such a distribution exists). If unknown, the consumer uses the **smaller** total recovery (distribution + terminal) of the true and false interpretations and warns — a distribution is never counted twice (the v1.3 "treat as false" counted the distribution twice for an observation with `r = 0`) [v1.4, R4F-05]. Policy values (`ret_policy`, `ret_lo`, `ret_hi`) use the capital remaining after distributions (the basis multiplied by the distribution factor). `ref_units` = `ref_price` × the price factors of later share-unit events |
| ts_value_available | ts_us | yes | Instant the observed consideration became public. Before this instant, consumers do not use the observed consideration for decision sizing or cash (an entitlement of unknown amount) — if null, `ts_exit_known`; if that is also null, the open of the exit session [v1.1, RV-C01] |
| ret_policy | f64 | yes | Policy value (producer rule, `policy_id`) |
| ret_lo, ret_hi | f64 | no | Loss scenarios (not lower/upper bounds — consumers do not call this the "largest burden" [v1.3, R3-09]) |
| policy_id | id | no | |
| pay_date | date | yes | Consideration payment date |
| handled_by_event_id | id | yes | If `corporate_actions` handles it (stock merger etc.), that id (then no terminal value is applied) |
| reason_code | string | yes | Original reason code |
| evidence_id | string | yes | |

Checks: A011 (W, v1.2: there is an ex-date distribution after `last_trading_date` but `ret_observed_includes_distributions` is null), R008 (`instruments.delisted_on` equals `exit_date`), V040 (`ret_lo <= ret_hi`), T011 (warning if `ts_value_available < ts_exit_known`).

### 5.14 `share_counts` (share counts, PIT)

Key (`instrument_id`, `count_kind`, `as_of_date`, `ts_available`). Columns `instrument_id`, `count_kind` (`listed` (listed shares), `outstanding` (issued and outstanding), `float`, `treasury`), `as_of_date` date (the date the count is correct for), `shares` f64, `ts_available`, `source`, `evidence_id`. Korean listed shares (daily from the exchange) use `as_of_date = session, ts_available = session close`; US SEC dei share counts use `as_of_date = cover page date, ts_available = filing instant`.

### 5.15 `fx_rates` (exchange rates)

Key (`base`, `quote`, `rate_kind`, `ts_event`, `source`). Sort same.

| Column | Type | Null | Meaning |
|---|---|---|---|
| base, quote | code | no | 1 base = rate quote |
| rate_kind | code | no | `fixing` (published or reference rate), `mid`, `bid`, `ask`, `close` |
| obs_date | date | no | Fixing date |
| ts_event | ts_us | no | Observation instant (e.g. FRED H.10 is the New York noon buying rate [unverified: exact definition]) |
| ts_available | ts_us | no | Release instant (if released late like H.10, that instant) |
| rate | f64 | no | > 0 (V005) |
| source | code | no | |

The engine takes the opposite direction as `1/rate`. When FX is used as a tradable object: `instruments(asset_class = fx_spot)` + `bars`/`quotes`.

### 5.16 `rates` (rate curves, option Greek inputs)

Key (`curve_id`, `tenor_days`, `ts_event`). Columns `curve_id` (e.g. `USD-SOFR`, `USD-TBILL`, `KRW-CD91`), `currency`, `tenor_days` i32, `rate` f64 (annualised, ratio), `compounding` code (`simple`/`annual`/`continuous`), `day_count` code (`ACT/360` etc.), `ts_event`, `ts_available`, `source`.

### 5.17 `fundamentals_events` (fundamental facts, raw PIT events)

Partition `market=`. Key `fact_id`. Sort (`instrument_id`, `item`, `period_end`, `ts_available`, `fact_id`).

| Column | Type | Null | Meaning |
|---|---|---|---|
| fact_id | id | no | Stable fact id |
| instrument_id | id | no | If fundamentals are company-level, the representative instrument (preferred shares etc. grouped via `issuer_id`) |
| issuer_id | id | yes | |
| item | code | no | Item from `dictionary/items` |
| period_start | date | yes | Period start of flow items |
| period_end | date | no | Period end (for balances, that date) |
| period_kind | code | no | `Q`, `H`, `9M`, `A`, `TTM`, `POINT` (balance) |
| fiscal_year | i16 | yes | |
| fiscal_period | code | yes | `Q1`..`Q4`, `H1`, `FY` |
| statement_basis | code | no | `consolidated` / `separate` / `unspecified` |
| accounting_standard | code | yes | `K-IFRS`, `K-GAAP`, `US-GAAP`, `IFRS` … |
| value | f64 | no | |
| unit | code | no | 3.4 |
| currency | code | yes | |
| scale | i8 | no | |
| known_on | date | yes | Publication date (when the source gives only a date) |
| ts_available | ts_us | no | Publication instant (K3; derived by rule if only `known_on` exists) |
| ts_recorded | ts_us | yes | Instant the producer first recorded it (system time) |
| version | i32 | yes | Revision number for the same (instrument, item, period, basis, source) |
| supersedes_fact_id | id | yes | Fact being revised |
| source | code | no | Source |
| source_rank | i16 | yes | Producer priority |
| doc_id | string | yes | Original document id (DART receipt number, SEC accession) |
| value_how | code | yes | `reported`, `derived` (subtraction or sum), `vendor`, `preliminary` (preliminary results; added in v1.1 — an open enum, so MINOR) |
| strict_eligible | bool | no | Strict eligibility (transitive lineage) |
| vendor_input | bool | no | Vendor value in the lineage |
| pit_quality | code | no | `native` (original availability time) / `backfilled` (collected later, time estimated) |

- T007: error if `ts_available < period_end`. But for rows with `value_how = preliminary` it is lowered to a warning (W) (preliminary disclosures can come before the period end) [v1.1, RV-I06].
- **TDS core items** (`std_item`, optional mapping): `revenue`, `gross_profit`, `operating_income`, `pretax_income`, `net_income`, `net_income_parent`, `eps_basic`, `eps_diluted`, `dps`, `ocf`, `capex`, `fcf`, `da`, `interest_expense`, `total_assets`, `current_assets`, `cash`, `total_liabilities`, `current_liabilities`, `total_debt`, `equity`, `equity_parent`, `shares_outstanding`, `shares_weighted_basic`, `shares_weighted_diluted`, `inventory`, `receivables`, `payables`, `dividends_paid`, `buyback`. **This list is a provisional mapping and does not guarantee interoperability**: the defining sentences for consolidated/separate scope, parent share, flow period, currency, scale and sign (e.g. capex) are set in an appendix of the next version. Until then, do not assume that the same `std_item` from different producers means the same thing [v1.1, RV-I06]. Producer items are free and are mapped only through `std_item`.

### 5.18 `fundamentals_state` (resolved fundamental state intervals) — the fundamentals the engine reads

Partition `edition=/market=`. Key (`instrument_id`, `item`, `ts_known_from`). Sort same.

| Column | Type | Null | Meaning |
|---|---|---|---|
| instrument_id | id | no | |
| item | code | no | |
| ts_known_from | ts_us | no | Instant this state became usable |
| ts_known_to | ts_us | yes | Instant it changed to the next state (null = still current) |
| period_end | date | no | End of the selected reporting period |
| period_kind | code | no | 5.17 |
| statement_basis | code | no | |
| value | f64 | no | |
| unit, currency, scale | | | 5.17 |
| strict_eligible | bool | no | |
| vendor_input | bool | no | |
| selected_fact_id | id | yes | Chosen fact |
| lineage_id | id | yes | Lineage (for TTM, the list of component facts; expanded in an `x_` extension table or `fundamentals_events`) |
| resolution_policy | id | no | Resolution rule version |

- Intervals are half-open and do not overlap per `(edition, instrument_id, item)` (T003). `ts_known_to > ts_known_from` (T004).
- The strict edition contains only states with `strict_eligible = true`. A gap is the absence of an interval (engine NaN). The engine does not fill from another edition.
- Value at decision time t: the one interval with `ts_known_from <= t < ts_known_to`. Filtering stale values (`max_age_days`) is an engine setting (specification 5.3.5).
- Small users: MAY ship only this table without `fundamentals_events` (event → state conversion is the producer's job). Conversely, for users with only events, a reference converter `tds derive fundamentals-state --policy latest-available` (value of the latest period with the latest publication; revisions applied) is provided (8.4).

### 5.19 `classifications` (classifications, two time axes)

Key (`instrument_id`, `scheme`, `level`, `edition`, `effective_from`, `ts_known_from`) (v1.1: `level` and `edition` added — with the v1 key, GICS sector and industry rows, or strict and compare rows, arriving on the same day were K001 duplicates) [RV-C08]. Sort same.

Columns: `instrument_id`, `scheme` (e.g. `gics`, `krx_sector`, `sic`, `industry_pit`, `market_segment`, `is_financial`, `category`, `venue_mic`), `level` i8 **null forbidden** (0 for single-level schemes; for multi-level schemes 1 = the coarsest level), `code` string, `label` string null, `effective_from` date, `effective_to` date null, `ts_known_from` ts_us, `ts_known_to` ts_us null, `edition` code (`strict`/`compare`/`both`, default both), `pit_quality` code (row level), `source`.
- Lookup: rectangle (6.3) — `ts_known_from <= t < ts_known_to` and `effective_from <= date(t) < effective_to`, edition filter (strict = `strict`+`both`, compare = `compare`+`both`), strict excludes row-level `backfilled`. For the same (instrument, scheme, level, edition filter) exactly one row satisfies these conditions (T012).
- `dictionary/columns.alias_of` can map a consumer name (e.g. `sector`) to `"<scheme>@<level>"`.
- The `valid_from_utc/valid_to_utc/known_at_utc` of specification 4.13 are replaced by these two axes (chapter 12 D12).

### 5.20 Universe: `universe_membership`, `eligibility_daily`

`universe_membership` (periods such as index membership): key (`universe_id`, `instrument_id`, `effective_from`, `ts_known_from`), lookup is the rectangle (6.3). Columns `universe_id` (e.g. `index:KOSPI200`, `index:SP500`), `instrument_id`, `effective_from` date, `effective_to` date null, `ts_known_from`, `ts_known_to`, `weight` f64 null, `source`. Index changes are announced before they take effect, so both axes are needed.

`eligibility_daily` (the producer's investable-universe judgement): partition `market=/year=`, key (`rule_id`, `instrument_id`, `session_date`). Columns `rule_id` (e.g. `investable-v1`), `is_eligible` bool, `reason` code null (open: `not_common`, `administrative`, `unit`, `preferred`, `fund`, `no_price`, `no_mcap` …), `ts_available` (v1.1 **default `session_close`** — the judgement usually uses that day's information, so a conservative default; `session_open` only when the producer declares that the judgement uses only pre-open information) [RV-C09]. Need not be dense. **Read rule** (v1.1): at decision session s only that session's one row is looked at; if there is no row or `ts_available > decision time`, it is **not eligible (false)** — a true from a previous session is not carried forward (`params.missing_means = false` declares this meaning, and v1.1 has no other value). Producers that need carried-forward state resolve the carry in advance and export dense rows.

### 5.21 Events and alternative data: `events`, `series_observations`

`events` (general events: earnings announcements, filings, insider trades, news scores, estimate snapshots …): key `event_id`. Partition `event_type=` (namespaced string, e.g. `filing.kr_dart`, `earnings.announcement`, `estimate.snapshot`). Columns `event_id`, `event_type`, `instrument_id` null, `issuer_id` null, `series_id` null [v1.4: market-level events such as macro releases — at least one of the three must be present, otherwise check V041 (W)], `ts_event` (instant the event happened), `ts_available` (required, instant the content was published — consumers MUST NOT show the event before this time), `ts_recorded` null, `value` f64 null, `consensus` f64 null [v1.4: the market expectation before the release; if present, surprise = value − consensus], `unit` null, `payload` json null, `source`, `doc_id`. A revision of the same event is a new `event_id` + `payload.revision_of` [v1.4, R4F-EV-02]. Frequently used events MAY add typed columns defined by `params.columns` (in that case give a separate dataset `name` per event kind, with `kind = events`).

`series_observations` (macro and alternative time series, with vintages): key (`series_id`, `obs_period_end`, `ts_available`). Columns `series_id`, `obs_period_start` date null, `obs_period_end` date, `value` f64, `unit`, `ts_available` (release instant of that vintage — not the end of the observation period: September CPI is the October release instant), `is_revision` bool, `consensus` f64 null [v1.4], `frequency` code null (`D`/`W`/`M`/`Q`/`A`) [v1.4], `source`. ALFRED-style vintage storage: a revision of the value for the same period is a new row; first-release vintage = the row with the earliest `ts_available` for that period [v1.4, R4F-EV-01].

### 5.22 Futures: contracts, roll schedules, continuous contracts — `experimental`

- Contract = a row in `instruments` (asset_class `future`). Recommended contract id `CME:ESZ2024` (4-digit year; `ESZ4` is reused every 10 years so it is not used as an id, but it stays in the symbol history).
- `roll_calendar`: key (`roll_rule_id`, `root`, `session_date`, `rank`). Columns `roll_rule_id`, `root`, `session_date`, `rank` i16 (0 = front), `instrument_id`, `ts_available` (rolls based on OI or volume are determined by **the previous day's** data, so the publication instant of the previous day's statistics; Databento `.n.` and `.v.` are also based on the previous day [verified]).
- Manifest `roll_rules`: `{"ES-c": {"mapping": "calendar", "offset_sessions": -5, "anchor": "last_trade"}, "CL-n": {"mapping": "open_interest"}}`. `mapping` ∈ {`calendar`, `last_trade`, `first_notice`, `open_interest`, `volume`}; `normalization` ∈ {`none`, `ratio`, `difference`} (only when producing continuous bars).
- Continuous contract bars are an optional derivative: `instruments(is_synthetic = true, asset_class = future, root, x_roll_rule)` + `bars`. **For signals**; fills and P&L use actual contracts (specification 11.3).
- Settlement prices and open interest are in `market_statistics`.

### 5.23 Options: contracts, chain snapshots, Greek inputs — `experimental`

- Contract = `instruments` (asset_class `option`; underlying, strike, right, exercise_style, ts_expiry, multiplier, settlement_type required). For US listed options the OCC symbol (OSI) goes in `instrument_xref.occ_osi`. Recommended id `OPRA:AAPL240621C00190000`.
- `option_chain_snapshots`: partition `underlying=/date=`. Key (`instrument_id`, `ts_snapshot`). Columns `instrument_id`, `underlying_instrument_id`, `session_date`, `ts_snapshot` (ts_us), `ts_available`, `bid`, `ask`, `bid_size`, `ask_size`, `last`, `volume`, `open_interest`, `underlying_price`, `underlying_price_kind` (`mid`/`last`/`close`), `iv_vendor`, `delta_vendor`, `gamma_vendor`, `vega_vendor`, `theta_vendor`, `rho_vendor`, `greeks_model` (vendor model name) — **only vendor values are stored**. Values recomputed by the engine are not inputs (specification 11.3 "distinguish vendor values from recomputed values").
- Inputs for Greek recomputation: underlying price (column above or underlying `bars`/`quotes`), rates `rates`, dividends `corporate_actions` (announced future dividends) + optional `dividend_forecasts` (an `events` kind), borrow cost (optional `series_observations`).
- Tick-level option quotes use `quotes` as is.

### 5.24 Crypto: 24/7, perpetual contracts — `experimental`

- Calendar `CRYPTO-UTC` (5.4). Recommended instrument id `<exchange>:<symbol>` (`BINANCE:BTCUSDT`, `BINANCE:BTCUSDT-PERP`).
- `funding_rates`: key (`instrument_id`, `ts_event`). Columns `ts_event` (payment instant), `rate` f64 (rate for that interval), `interval_hours` f64, `is_predicted` bool (predicted value), `ts_available`, `source`. Nautilus FundingRateUpdate.
- `reference_prices`: key (`instrument_id`, `price_kind`, `ts_event`). `price_kind` ∈ {`mark`, `index`, `settlement`}. Nautilus MarkPriceUpdate.
- Quantities are fractional: `size_exponent` (ticks), bar `volume` f64.

### 5.25 `feature_panels`, `label_panels` (wide tables computed by the producer)

`feature_panels` — partition `name=/edition=/year=`. Key (`instrument_id`, `period`). Columns `instrument_id`, `period` date (first day of the period, e.g. day 1 for a month), `as_of_date` date (economic reference date), `ts_available` (required per row; e.g. a monthly panel uses the open of the session after `as_of_date`), and the feature columns (each with unit, meaning and `is_label = false` in `dictionary/columns`). Lineage marker columns (`x_ex_fin_strict_row` etc.) are extension columns.

`label_panels` — the same shape + `entry_date`, `entry_price_basis`, `exit_date`, `horizon`, `return_definition` (e.g. `econ_reinvest_ex_close`, `adj_ratio`), `terminal_policy_id`, and optional time columns `ts_label_start`, `ts_label_end` (end of the outcome), `ts_label_available` (the first instant that label value could be computed — including late-published delisting recoveries and dividend amounts) [v1.1, RV-C04]. Without the time columns, the consumer builds the first two from `entry/exit_date` and `entry_price_basis` and assumes `ts_label_available = ts_label_end` (assumption recorded). Every value column has `is_label = true`. **The engine does not read them as decision inputs** (specification R-16). Check V050: error if a `label_panels` column name exists in `feature_panels` (prevents leaks through name collisions).

### 5.26 Benchmarks

No separate table. An index is `instruments(asset_class = index, index_kind = TR|PR, is_synthetic = true)` + `bars` (`close` = index value, `volume` null). Specification 4.16 `benchmarks_1d` becomes this shape (chapter 12 D15). If absent, the engine shows "n/a: not in snapshot" (R-59 as is).

---

### 5.27 `market_rules` (market rules: tick sizes, price limits) — optional, stable [v1.2, V31-05]

Key (`rule_id`, `rule_kind`, `venue_group`, `valid_from`, `price_from`). Sort same. No partition. Closes chapter 13 Q15 (deferred to "the next version" in v1.1).

| Column | Type | Null | Meaning |
|---|---|---|---|
| rule_id | id | no | Rule set id (e.g. `krx-tick-2023`). `instruments.tick_rule_id` points to this |
| market | code | no | Key of the manifest `markets` |
| rule_kind | code (closed) | no | `tick_band` (tick size by price band) / `price_limit` (daily price limit) |
| venue_group | code (open) | no | `*`, `KOSPI`, `KOSDAQ`, `NYSE` etc. (name of a price policy group) |
| valid_from | date | no | Effective start (inclusive) |
| valid_to | date | yes | Effective end (exclusive), null = still current |
| price_from | f64 | yes | Lower bound of the price band (inclusive, `tick_band` only; null = 0) |
| price_to | f64 | yes | Upper bound of the price band (exclusive; null = unbounded) |
| tick_size | f64 | yes | Tick size of that band (required for `tick_band`, greater than 0) |
| limit_ratio | f64 | yes | Limit relative to the reference price (required for `price_limit`, 0.30 = 30%) |
| source | string | no | URL of the exchange regulation or notice |
| verified | bool | no | Whether a person checked it against the original |

- **Price grid norm**: raw price columns (`bars.open/high/low/close`, `tradability_daily.*_limit_price`) must lie on the grid of that instrument and date, but jitter within 1e-9 relative due to f64 representation is allowed (`0.6768000000000001`). Before comparing, consumers convert to an **integer of the market minimum unit** (one coordinate such as KR 1 won, US 0.0001 dollar) — comparing tick counts of bands with different tick sizes reverses the order of two prices across a boundary (4,995/5 = 999 > 5,000/10 = 500). The tick-size table is used for confirming grid membership and snapping order prices. Observed prices that do not fit the minimum-unit integer are not converted by the consumer (only that row is compared as a float) [v1.3, R3-02]. Grid source order: `instruments.tick_size` (fixed) → `market_rules` of `tick_rule_id` → consumer resources. Check V012 (W): rows where grid information exists but the raw price deviates from the grid by more than 1e-9 relative (catches packages that declared adjusted prices as raw).
- Price bands are determined by the value before snapping. Overlapping price bands within the same (`rule_id`, `venue_group`, date) are T003.
- Short-sale ban periods and securities lending data are not in this standard (they belong to the engine's market rules pack; datasets for borrowable quantity and fees are candidates for the next MINOR) [V31-LS-07].

## 6. Point-in-time (PIT) semantics

### 6.1 Meaning of time columns (common to all tables)

| Column | Meaning | Who sets it |
|---|---|---|
| `ts_event` | Instant something happened in the world (trade, bar end, effect) | Source data |
| `ts_recv` | Instant the collection system received it (ticks) | Collector |
| `ts_available` | Earliest instant a strategy may use it in a decision. **The engine gate is this one alone** | Producer (rule or column) |
| `ts_known_from` / `ts_known_to` | Known period during which a state or record could be trusted and used | Producer |
| `effective_from` / `effective_to` | Effective period during which the state held in the world | Source data |
| `ts_recorded` | Instant the producer system first recorded it (system time) | Producer |
| `known_on` | Publication date (the original value when only a date exists) | Source data |

### 6.2 Availability-time derivation rules (manifest `availability.rule`)

| Rule | Meaning |
|---|---|
| `column` | The `ts_available` column as is |
| `ts_end` | The bar's `ts_end` (if null on a daily bar, the session `ts_close`) |
| `ts_end+<ISO 8601 duration>` | e.g. `ts_end+PT15M` (vendor delay) |
| `session_open` / `session_close` | Open / close of the session of the row's `session_date` |
| `next_session_open(<date column>)` | `ts_open` of the first session **after** that date (by the instrument's calendar). Default date column `known_on` |
| `ts_recv` | Instant the tick was received |
| `ts_recv_else(<column>+<duration>)` | If `ts_recv` is null, another time + delay |
| `ts_recv+<duration>` | `ts_recv` + an assumed receive delay on the user side (e.g. Databento `ts_recv` is gateway receipt, earlier than user receipt) [v1.1] |

- What a rule cannot express (e.g. "distributed at 11:00 Eastern the next day") is shipped as a column.
- If both a column and a rule are declared, the checker verifies they agree (T002).
- Different availability times per column (e.g. pre-open information and close results in `tradability_daily`) get a rule per group with `params.availability_by_column` (required for `tradability_daily`, 5.10).
- Rule names are **mandatory interpretation rules**: a consumer that meets an unknown rule name MUST reject it, not ignore it (checker M014, 10.3) [v1.1].
- `corporate_actions` has two availability times: effect `ts_effective`, terms `ts_terms_available` (if null, `ts_announced`; if both null, `ts_effective`). The manifest `availability` is written as `{"effect": "ts_effective", "terms": "ts_terms_available"}` (verified by T002) [v1.1].

### 6.3 Lookup semantics (what the engine and the reference implementation must follow)

1. **Point observations** (bars, events, FX, panels): at decision t only rows with `ts_available <= t`. The "latest" for the same key target is the maximum `ts_event` (or `period`).
2. **State intervals** (`fundamentals_state`): the one row with `ts_known_from <= t < ts_known_to` (one axis; no overlap is guaranteed by T003).
3. **Two time axes — rectangle lookup** (`classifications`, `universe_membership`, `instrument_symbols`): per discriminating key, rows with `ts_known_from <= t < ts_known_to` **and** an effective period that contains the query date. The two conditions are filtered **together**: picking the single row with the maximum known time first lets a pre-announced future-effective row hide the current effective row. Pinned examples (same as the specification 5.3.6 table, checker T012 conformance): ① pre-announcement: A effective [2019-01-01, ∞), known [2018-12-01, 2020-03-06); A′ (same code, effective [2019-01-01, 2020-03-20)), known [2020-03-06, ∞); B effective [2020-03-20, ∞), known [2020-03-06, ∞) → the answer for (t = 2020-03-10, q = 2020-03-10) is A′; ② late discovery: effective date passed but before known → the old row; ③ correction: the new row instead of the old row whose known interval is closed; ④ level: one per level; ⑤ edition: one per strict/compare filter.
4. **Corporate actions whose effect and terms publication differ**: the 5.11 resolution procedure. In decisions they are included in adjustment when both the effect and the terms publication are `<= t` (specification 5.3.3, 5.3.4).
5. **Session close basis**: the value of market-axis row s uses only information available up to `ts_close(s)` (specification 5.1.2). This is an engine rule; the data format provides only `ts_available`.

### 6.4 Two history modes

- **Economic history** (`history_mode = economic`, default): old disclosures collected later are used at their original availability time. Only `ts_available` is looked at.
- **System history** (`history_mode = system`): replays "what the producer's system actually knew then". At decision t, `ts_recorded <= t` is also required. The `tds:bitemporal` profile makes `ts_recorded` required.

### 6.5 `pit_quality`

Per dataset (or row): `native` (availability time given by the source) / `backfilled` (collected later and estimated) / `mixed`. **Strict handling (v1.1, unified with K6)**: tables with a row-level `pit_quality` column (two-time-axis tables) exclude `backfilled` rows from strict lookups; for dataset-level `backfilled`/`mixed` without row-level quality the consumer warns in strict runs (excluding everything would remove required data such as prices and events). `mixed` declares "some rows are backfilled", and a row column is recommended so as not to hide which rows. The checker does not judge the values; it only verifies the declaration [RV-C09].

---

## 7. Profiles

A package lists the profiles it follows, with versions, in `profiles` (`tds:<name>@<MAJOR.MINOR>`; all v1.1 profiles are `@1.0`). Profiles can be stacked. "Required" below means the datasets and columns MUST be present in that profile. **A profile is a conformance claim, distinct from consumer support** [v1.1, RV-I01]: the check result per profile has three parts — **declared** (in `profiles`), **verified** (up to which level `manifest`/`schema`/`full` it was checked; rules that level cannot see are `not_checked`, not a pass), and the consumer's (engine's) **support** is stated separately in the consumer's documentation (the last column of the table below is for reference). New error checks are attached only to new profile versions (`@1.1`) so that the standard MAJOR does not have to rise (10.2). `cum_factor_*` is required in no profile (events are the source).

| Profile | Required datasets | Additional required columns and conditions | What the engine can do |
|---|---|---|---|
| `tds:minimal-daily@1.0` | `instruments`, `bars(freq=1d)` | bars: only `close` required. Any `price_basis` (declaration required). Without `calendar_sessions` the consumer builds one from bar dates and warns | **Analysis path only** (NexusBT v1: `run_pipeline`, `screen(factor)`, `evaluate(target="fwd_return_adj")`). With adjusted prices, dividend, quantity and terminal-value accounting are undefined, so economic backtests and economic labels are not supported (the v1 promise of a "close-fill backtest" was removed) [v1.1, RV-I03] |
| `tds:equity-daily-core@1.0` | above + `calendar_sessions`, `corporate_actions` (empty table allowed), `delistings` (empty table allowed) | bars `price_basis = raw`, `density = dense`, OHLCV, `obs_status`; corporate_actions factor columns | All of `backtest` and `screen` in specification v1 (OHLC fill rules, splits, dividends, delistings) |
| `tds:equity-daily-research@1.0` | above + `tradability_daily`, `eligibility_daily`, `instrument_symbols`, `fx_rates` (if more than one market), `fundamentals_state`, `classifications`, `dictionary/columns`, `dictionary/items` (optional `market_rules`, v1.2) | Explicit `ts_available` rules (including `tradability_daily.availability_by_column`). (The v1 requirement of `cum_factor_*` was removed) | All of v1 (Fund.*, Universe, multi-currency sleeves) — **reference producer target** |
| `tds:panels@1.0` | `feature_panels`, `label_panels`, `dictionary/columns` | Row-level `ts_available` | `Panel.*`, `evaluate(target=Label.*)` |
| `tds:pit-fundamentals@1.0` | `fundamentals_events` + `fundamentals_state` | `fact_id`, `doc_id`, `lineage_id` | `nx.explain` lineage |
| `tds:bitemporal@1.0` | (on top of other profiles) | `ts_recorded` in events, classifications and state | System history replay |
| `tds:intraday-bars@1.0` (experimental) | `instruments`, `calendar_sessions`, `bars(freq<1d)` | `ts_start`, `ts_end`, `session_date`, `density` declaration | E4 intraday path fills |
| `tds:l1-ticks@1.0` (experimental) | `trades`, `quotes` | `ts_event`, `sequence`, availability rule | E4 |
| `tds:l2-book@1.0` (experimental) | `book_deltas(mbp)` or `book_snapshots` | `is_last`, starting snapshot | E4 |
| `tds:l3-book@1.0` (experimental) | `book_deltas(mbo)` | `order_id` | E4 queue model |
| `tds:futures@1.0` (experimental) | `instruments(future)`, `market_statistics`, `roll_calendar` (if continuous contracts are used) | Contract required columns | E4, E5 |
| `tds:options@1.0` (experimental) | `instruments(option)`, `option_chain_snapshots` or `quotes`, `rates` | Contract required columns | E5 |
| `tds:crypto@1.0` (experimental) | `instruments(crypto_*)`, `bars` or ticks, `funding_rates` (if there are perps) | `CRYPTO-UTC` calendar, currency declaration | E4 |
| `tds:fx` | `fx_rates` or `instruments(fx_spot)` + bars | | |
| `tds:alt-events` | `events` or `series_observations` | `ts_available` required (no rule, column only) | User term inputs |

**The smallest example** (`tds:minimal-daily`, two hand-made CSVs → `tds import csv`):

```
instruments.csv:  instrument_id,asset_class,market,calendar_id,currency,listed_on
                  XNYS:AAPL,equity,US,XNYS,USD,1980-12-12
bars.csv:         instrument_id,session_date,close,volume
                  XNYS:AAPL,2024-01-02,185.64,82488700
```
+ `tds import csv --profile tds:minimal-daily@1.0 --price-basis total_adjusted --market US:XNYS:USD:America/New_York` creates `tds.json` (an id of the form `XNYS:AAPL_19801212`, as recommended by K1, is safer).

---

## 8. Conformance checker

### 8.1 Commands

```
tds check PATH [--profile P ...] [--level manifest|schema|full] [--datasets a,b]
               [--max-errors N] [--format text|json] [--strict] [--sample-rows N]
tds hash PATH [--write]            # compute file, dataset and package hashes (physical, value, semantic) (--write updates tds.json)
tds manifest build PATH            # scan a folder and draft tds.json (rules and descriptions filled in by a person)
tds describe PATH [DATASET]        # summary of coverage, columns, profiles
tds derive fundamentals-state ...  # 5.18 reference conversion
tds import {csv|zipline|lean|nautilus|dbn|qlib|massive} ...   # chapter 9
tds export {zipline-bundle|nautilus-catalog|wide-parquet} ... # 9.8
```

- Exit codes: `0` pass, `1` errors present, `2` only warnings and `--strict`, `64` usage error, `66` input missing, `70` checker internal error.
- Without `--profile`, every profile in `tds.json` `profiles` is checked. Giving an undeclared profile checks only "does this package follow that profile" (independent of the declaration).
- The engine calls the same checker as a library when it opens a snapshot: `manifest` by default, `full` with `verify="full"`/`nexusbt doctor --full` (specification v3 4.4). On failure, `SnapshotError` (E14) carries the list of TDS codes and the sentences from `producer.hints`.
- **Status per command** [v1.1, RV-I03] — whether the commands advertised by the standard actually exist:

| Command | Status (checker `nexusbt-tds` 1.0.x) |
|---|---|
| `tds check`, `tds hash`, `tds describe` | Implemented (engine M0–M1) |
| `tds import csv`, `tds manifest build` | Implemented (engine M1) |
| `tds export zipline-bundle` | Implemented on the test side (for parity, `tests/parity`); public command planned |
| `tds derive fundamentals-state` | Planned (reference conversion, 5.18) |
| `tds import zipline|lean|nautilus|dbn|qlib|massive` | Planned (the chapter 9 mapping tables are design notes; once implemented, each adapter writes a conversion report) |
| `tds export nautilus-catalog|wide-parquet` | Planned (E4) |

### 8.2 Check levels

| Level | Reads | Checks performed |
|---|---|---|
| `manifest` | `tds.json`, file sizes | M*, presence of profile datasets, file presence and bytes |
| `schema` | + Parquet footers and statistics | S*, partition path values, range checks possible from file statistics (T006 watermark, part of D002) |
| `full` | + all rows | K*, R*, T*, D*, A*, V*, H* (sha256, value and semantic hashes) |

- **Three results** [v1.1, RV-I01]: the summary per profile is `{"declared": bool, "verified_level": "none|manifest|schema|full", "result": "pass|fail|not_checked"}`. Rules that level cannot see (e.g. row rules at the `manifest` level) are `not_checked` and are not written as "pass". The `unchecked` list holds the rule codes not checked.
- A valid lower-profile package (declares only a smaller profile and follows it) differs from a package that breaks its declaration: the latter is an error and the consumer does not fix it with fallback behaviour. Fixing old formats is the import step's job of making a new package.

### 8.3 Error codes

Severity: E = error (profile fails), W = warning.

| Code | Severity | Meaning |
|---|---|---|
| TDS-M001 | E | `tds.json` missing, unreadable, or violating the JSON schema |
| TDS-M002 | E | `tds_version` MAJOR not supported |
| TDS-M003 | E | Required manifest field missing |
| TDS-M004 | E | A listed file is missing |
| TDS-M005 | W | A file in the folder that is not listed |
| TDS-M006 | E | File byte count differs |
| TDS-M007 | E | Unknown profile |
| TDS-M008 | E | Required dataset of a profile missing |
| TDS-M009 | E | Dataset `schema_version` MAJOR not supported |
| TDS-M010 | E | Data differs from the `markets`, `id_namespaces` or `editions` declarations (use of an undeclared market, namespace or edition) |
| TDS-M011 | W | Dataset `schema_version` MINOR is newer than the checker (continue, ignoring unknown columns) |
| TDS-M012 | E | A path points outside the package folder (`..`, absolute path, symbolic link leading outside) [v1.1] |
| TDS-M013 | E | The same file path appears twice [v1.1] |
| TDS-M014 | E | Unknown **mandatory interpretation rule** (availability rule name, a new value of a closed enum that affects execution, unknown `hash_spec`) — rejected because ignoring it changes the meaning [v1.1] |
| TDS-M015 | W | A dataset with an `experimental` schema is present (outside the 1.x compatibility promise) [v1.1] |
| TDS-S001 | E | Required column missing |
| TDS-S002 | E | Column type differs |
| TDS-S003 | E | Null in a non-nullable column |
| TDS-S004 | E | An instant column without UTC tz or with a unit different from the dataset rule, INT96 |
| TDS-S005 | W | Unknown column (without `x_` prefix) |
| TDS-S006 | E | Value not in a closed enum |
| TDS-S007 | W | Value not in an open enum (and not in `dictionary/codes`) |
| TDS-S008 | E | A partition path value does not fit its type, or the partition column is also inside the file |
| TDS-S009 | E | NaN or ±Inf in a float column |
| TDS-S010 | E | Parquet key-value metadata `tds.dataset`/`tds.schema_version` missing or different |
| TDS-K001 | E | Duplicate key |
| TDS-K002 | E | Sort violation (inside a file or across concatenated files) |
| TDS-K003 | E | A row outside its partition range (e.g. a 2023 row in the year=2024 folder) |
| TDS-K004 | E | Time ranges of files in the same partition overlap |
| TDS-K010 | E | The same symbol points to two ids in the same period |
| TDS-K011 | E | `session_ord` not consecutive from 0 |
| TDS-R001 | E | `instrument_id` not in `instruments` |
| TDS-R002 | E | `calendar_id` not in `calendar_sessions` |
| TDS-R003 | E | `session_date` is not a session of that instrument's calendar |
| TDS-R004 | E | Currency code is neither ISO 4217 nor a declared currency |
| TDS-R005 | W | MIC format (4 uppercase letters or digits) violated |
| TDS-R006 | E | Referenced target missing for `new_instrument_id`, `underlying_instrument_id`, `handled_by_event_id` etc. |
| TDS-R007 | W | `selected_fact_id` or `lineage_id` not found in `fundamentals_events` (only when the event table exists) |
| TDS-R008 | E | `instruments.delisted_on` ≠ `delistings.exit_date` |
| TDS-R009 | E | `item` not in `dictionary/items`, panel column not in `dictionary/columns` |
| TDS-T001 | E | `ts_available < ts_event` (bars, events; where it cannot be later by rule) |
| TDS-T002 | E | The `ts_available` column and the declared rule give different values |
| TDS-T003 | E | Overlapping state or history intervals |
| TDS-T004 | E | Interval end ≤ start |
| TDS-T005 | E | Daily `ts_start/ts_end` differ from the session open and close (when present) |
| TDS-T006 | E | Data after the market watermark `complete_through` |
| TDS-T007 | E | Fundamentals `ts_available < period_end` (without a preliminary marker) |
| TDS-T008 | W | `ts_recv < ts_event − tolerance` |
| TDS-T010 | E | `last_session < listed_on` |
| TDS-T011 | W | Publication of the exit consideration earlier than publication of the exit |
| TDS-T012 | E | The two-time-axis **rectangle** lookup returns more than one row for one time and one discriminating key (for classifications including scheme, level and edition filter) |
| TDS-D001 | E | Missing session row in dense daily bars |
| TDS-D002 | E | Row on a non-session day, or outside the listing period |
| TDS-D004 | E | Manifest `rows` or `coverage` differs from the actual data |
| TDS-A001 | E | Cumulative factor ratio ≠ product of the session's event factors (relative 1e-12; by the 5.11 resolution procedure one latest version per revision chain, cancelled chains as 1.0, "none" factor boundaries not reconciled) |
| TDS-A002 | E | Cumulative factor of the first session ≠ 1.0 |
| TDS-A003 | E | `price_factor ≤ 0` or null while `factor_method ≠ unavailable` |
| TDS-A004 | W | Cash dividend factor differs from `1 − D/ref_price` (relative 1e-9) |
| TDS-A005 | E | `ex_date` is not a session |
| TDS-A006 | E | Merger, spinoff or exchange without `new_instrument_id` or ratio (except cash mergers) |
| TDS-A007 | E | `revision_of` cycle |
| TDS-A008 | W | The terms publication (`ts_terms_available`) of a quantity-changing event (`affects = split_and_total`) is after its effect (`ts_effective`) [v1.1] |
| TDS-A010 | E | An event that changes the share count (5.11) without `ratio_num/ratio_den`, with only one, with a value ≤ 0, or differing from the f64 ratio column by more than 1e-12 relative [v1.2, V31-01; v1.4 W → E, R4F-01]. Only when decimal literals are chosen in the consumer setting does the consumer lower it to W (5.11) |
| TDS-A011 | W | An ex-date cash distribution after the last trading day exists but `delistings.ret_observed_includes_distributions` is null [v1.2, V31-04] |
| TDS-A009 | E | `factor_method = spinoff_first_close` but `ts_terms_available < ts_close(effective session)` (the factor cannot be known before the new company's first close) [v1.1] |
| TDS-V001 | E | OHLC contradiction |
| TDS-V002 | E | Negative price or volume (no allowance declared) |
| TDS-V004 | E | `obs_status` contradicts null prices |
| TDS-V005 | E | FX or rate curve value ≤ 0 (rates may be negative; FX only) |
| TDS-V010 | W | Equity volume is not an integer |
| TDS-V011 | W | Suspected volume unit: per-instrument-year median of `value_traded / (volume × (H+L+C)/3)` outside [0.5, 2] [v1.2, V31-16] |
| TDS-V012 | W | Grid information exists but a raw price deviates from the grid by more than 1e-9 relative [v1.2, V31-05] |
| TDS-V020 | E | Required column per asset kind missing |
| TDS-V030 | W | Crossed or locked BBO |
| TDS-V031 | W | Crossed book after reconstruction |
| TDS-V032 | W | Sequence gap |
| TDS-V040 | E | `ret_lo > ret_hi` |
| TDS-V041 | W | An `events` row with `instrument_id`, `issuer_id` and `series_id` all null [v1.4, R4F-EV-02] |
| TDS-V050 | E | A label column name also exists in the feature table |
| TDS-H001 | E | File sha256 differs |
| TDS-H002 | E | Dataset value hash differs |
| TDS-H003 | E | Package physical, value or semantic hash differs |
| TDS-H004 | W | `files[].value_sha256` (optional) differs from the file's canonical value hash [v1.2, V31-12] |

### 8.4 Output

`--format json` writes one object per line (JSON Lines):

```json
{"code":"TDS-A001","severity":"error","dataset":"bars_1d","file":"bars/freq=1d/market=KR/year=2015/part-00000.parquet",
 "key":{"instrument_id":"KR:005930","session_date":"2015-05-08"},"count":3,
 "message":"cum_factor_split ratio 0.0200 != product of event factors 0.0201",
 "hint":"check corporate_actions event KR-CA-… (split 50:1, ex 2018-05-04)"}
```

The last line is the summary `{"summary": {"errors": n, "warnings": m, "level": "manifest", "profiles": {"tds:equity-daily-core@1.0": {"declared": true, "verified_level": "manifest", "result": "not_checked"}}, "unchecked": ["TDS-K001", …]}}`. The engine's `SnapshotError` message uses the first error + the count + the hint (`producer.hints`).

### 8.5 Checker implementation notes

- The reference implementation is Python + pyarrow only (distribution `nexusbt-tds`, import `nexusbt_tds`; the v1 DuckDB note moved to the engine repository rules). Kept as pure functions so the engine and every producer use the same code (producers run `full` right after export, the engine `manifest` when opening). The value hash is cross-checked with a pure-Python reference encoder that does not use pyarrow (4.5 test vectors).
- One check = one code = one test. A set of small deliberately broken packages `conformance/` (one failing example and one passing example per code) is distributed with the standard.

---

## 9. Import adapters (other formats → TDS)

Common: adapters **do not invent** availability times that the source does not have. They use a default rule (e.g. `ts_end`) and mark the dataset `pit_quality = backfilled`. In the mapping tables, [loss] is what is lost when moving to TDS and [supply] is what the user must provide separately. **The mapping tables are not an interoperability guarantee** [v1.1, RV-Q08]: an implemented adapter writes a **conversion report** `import_report.json` next to the package (fields preserved, assumptions made, counts of dropped and unsupported records, precision loss, identifier mapping, semantic tests passed). Unknown events in the source are preserved as `kind = other` (treated as unsupported) and are not guessed into another kind. The command status table in 8.1 says which adapters are implemented.

### 9.1 zipline bundle → TDS

| zipline | TDS | Notes |
|---|---|---|
| asset DB `equities` (sid, symbol, asset_name, start_date, end_date, first_traded, auto_close_date, exchange) | `instruments` (`instrument_id = <namespace>:<sid or first symbol>`), `instrument_symbols` (periods of `equity_symbol_mappings`) | sid is kept as `instrument_xref(id_type = zipline_sid)` |
| `futures_contracts`, `root_symbols` | `instruments(future)` | notice_date → first_notice_date, expiration_date → ts_expiry (time [supply]) |
| `exchanges(exchange, canonical_name, country_code)` | `markets` + `venue_mic` | MIC mapping [supply] |
| daily bars (bcolz, price ×1000 uint32) | `bars(freq=1d)` raw price = value/1000 | 0 meant missing, so null + `obs_status = missing`. Volume 0 and missing cannot be distinguished [loss] |
| minute bars (zero-filled between sessions) | `bars(freq=1m, density=dense)` | Zero-filled rows are `no_trade` |
| `splits` (sid, effective_date, ratio) | `corporate_actions(kind = split/reverse_split, price_factor = ratio)` | The zipline ratio is a **price multiplier** (2:1 split = 0.5; confirmed as the convention by two of the three reviews, finally confirmed by round-trip test L3). `ratio_new_per_old = 1/ratio` |
| `mergers` (sid, effective_date, ratio) | `corporate_actions(kind = other, factor_method = vendor, price_factor = ratio)` | Only a price adjustment, not evidence of a share conversion, so not made into `split` or `stock_merger` (unsupported if held) [v1.1] |
| `dividend_payouts` (ex, record, declared, pay, amount) | `corporate_actions(cash_dividend)` | Factor recomputed with the TDS formula (reconciled with the ratio in the zipline `dividends` table, A004) |
| `stock_dividend_payouts` (payment_sid, ratio) | `corporate_actions(stock_dividend or spinoff)` | spinoff if payment_sid ≠ sid |
| calendar name (`XNYS`) | `calendar_sessions` (generated with exchange_calendars) | |
| (none) | `ts_announced`, `ts_terms_available`, `delistings` | [loss] availability times and terminal values. `auto_close_date` is the **processing date after** delisting, so it is closer to `delistings.exit_date` than to `last_session` [v1.1] |
| price ×1000 uint32 range (about 4.29 million) | – | Instruments beyond it are stored with a per-instrument price scale in the opposite direction (`tds export zipline-bundle`), and the list is reported |

### 9.2 LEAN data folder → TDS

| LEAN | TDS | Notes |
|---|---|---|
| `equity/usa/daily/<t>.zip` (`YYYYMMDD HH:mm`, OHLC deci-cents, volume) | `bars(freq=1d)` | ÷10,000. Time is local in the data time zone → only the date as `session_date`. Whether LEAN daily prices are raw (adjusted by factors when read) [unverified: believed to be stored raw] |
| `minute/<t>/<date>_trade.zip` (ms since midnight) | `bars(freq=1m)`: `ts_start = local midnight + ms` converted to UTC via the time zone, `ts_end = ts_start + 1 minute` | LEAN bar time = start [verified]. Minutes without trades have no row → `density = sparse` |
| `_quote.zip` (bid OHLC, bid size, ask OHLC, ask size) | two lines of `bars(price_type = bid/ask)` | |
| tick trade (time, price, size, exchange, condition hex, suspicious) | `trades` (`conditions = [hex]`, suspicious → `x_lean_suspicious`) | Price deci-cents → kept as integers with `price_exponent = -4` |
| tick quote (one side only) | `quotes` (other side filled from the previous state) | |
| `factor_files/<t>.csv` (date, price factor, split factor, reference price) | Price factor and split factor **decoded separately**: split factor changes → `split/reverse_split` (with explicit `share_factor`), changes of the price factor alone → `cash_dividend` (when back-solving `D` from the reference price fits) or `other` (`factor_method = vendor`), reference price → `factor_ref_price`; `bars.cum_factor_*` recomputed as forward-cumulative | LEAN factors are backward-cumulative with latest = 1 and the effective-date convention may differ — confirmed by normalisation-mode tests [v1.1, RV-Q08] |
| `map_files/<t>.csv` (date, ticker, exchange) | `instrument_symbols`; if the last date is in the past, `last_session` and `delistings(unknown)` — but a ticker change has the same shape, so decide together with the next row of `instrument_symbols` | Delisting value [loss]. Check the convention whether a map row's date is the start or the end of a TDS interval [v1.1] |
| `market-hours-database.json` | `calendar_sessions`, `calendar_segments` | |
| option path (style, right, strike×10,000, expiry) | `instruments(option)` | |

### 9.3 Nautilus catalog → TDS (and back)

| Nautilus | TDS |
|---|---|
| `Equity`, `FuturesContract`, `OptionContract`, `CryptoPerpetual`, `CurrencyPair` | `instruments` (by asset_class), `InstrumentId` (e.g. `AAPL.XNAS`) → `instrument_xref(nautilus_instrument_id)`. A TDS id must follow the K1 grammar (`namespace:local id`), so it cannot be used as is: recommended `XNAS:AAPL:<first listing date>` or `NT:AAPL.XNAS` [v1.1, RV-Q08] |
| `Bar` + `BarType` | `bars`: step and aggregation → `freq`/`aggregation`, price_type → `price_type`, INTERNAL/EXTERNAL → `source_kind`; `ts_event` (close time by default) → `ts_end`, only for time bars `ts_start = ts_end − period` (tick and volume bars: null if the source has no start [supply]); `ts_init` → not `ts_recv` (creation time), so preserved as `x_nt_ts_init`, and the replay order rule is declared separately in the manifest `params.replay_order`. Prices and sizes are moved exactly as fixed point without going through float; precision is **per instrument** in Nautilus, so the dataset exponent (K7) is set to the smallest exponent of that file (e.g. −9) [v1.1] |
| `QuoteTick` | `quotes` (bid_price → bid_px …) |
| `TradeTick` | `trades` (aggressor_side, trade_id as is) |
| `OrderBookDelta` | `book_deltas` (action, side, price, size, order_id, flags, sequence 1:1) |
| `OrderBookDepth` | `book_snapshots` |
| `InstrumentStatus` | `trading_status_events` |
| `InstrumentClose` | `market_statistics(official_close / settlement_price)` |
| `MarkPriceUpdate`, `FundingRateUpdate` | `reference_prices`, `funding_rates` |

The opposite direction (`tds export nautilus-catalog`) is the default path of E4 (specification 11.2). Prices build Nautilus `Price` with `price_precision`.

### 9.4 Databento DBN → TDS

| DBN schema | TDS | Notes |
|---|---|---|
| `definition` | `instruments` + `instrument_xref(databento_instrument_id, one-day interval)` + `instrument_symbols(vendor:databento_raw)` | Expiry, tick size, strike, multiplier |
| `mbo` | `book_deltas(depth_kind = mbo)` | action A/M/C/R/T/F/N → add/modify/cancel/clear/trade/fill/none; side A/B/N → ask/bid/none (**the side of T/F is the aggressor side**, so trade rows are also copied to `trades.aggressor_side`); F_LAST → `is_last`; F_SNAPSHOT → `is_snapshot`; 1e-9 integer prices as is (`price_exponent = -9`); `INT64_MAX` → null |
| `mbp-10`, `mbp-1` | `book_snapshots` or `book_deltas(mbp)` + `quotes` | |
| `tbbo`, `trades` | `trades` (+ `quotes`) | |
| `ohlcv-1s/1m/1h` | `bars`: `ts_event` = **interval start** [verified] → `ts_start`; `density = sparse` | |
| `ohlcv-1d` | `bars(bar_time = utc_day)` | UTC-date daily bars [verified] → `freq = 1d` but `bar_time = utc_day` so they are not used as session daily bars; the engine rejects them in features that need session daily bars. Decide by the record and schema type (if there is a session-end daily variant, `bar_time = session`) and do not relabel dates [v1.1] |
| `statistics` | `market_statistics` | |
| `status` | `trading_status_events` | |
| `imbalance` | `events(event_type = auction.imbalance)` | |
| time `ts_recv` | availability rule `ts_recv` or `ts_recv+<delay>` (gateway receipt is earlier than user receipt) | [v1.1] |
| `publisher_id`, channel and dataset, record order | `x_dbn_publisher_id`, `x_dbn_dataset`, `x_dbn_channel_id`, stable sort sequence `sequence` (unique only within a channel) | Preserved so original order and source are not lost [v1.1, RV-Q08] |
| uint64 `order_id` etc. | decimal string column (`x_dbn_order_id`) + an integer column only when it does not overflow int64 | Signed int64 cannot hold all values losslessly [v1.1] |
| continuous symbols (`ES.c.0`) | `roll_calendar(roll_rule_id = "databento:c")` | Prices not adjusted [verified] |

### 9.5 CSV → TDS

- UTF-8 CSV with a header line. Column names equal to TDS names are used as is; otherwise a mapping file:

```yaml
# mapping.yaml
dataset: bars
params: {freq: 1d, price_basis: raw, density: sparse}
market: {code: KR, calendar_id: XKRX, currency: KRW, timezone: Asia/Seoul}
columns:
  instrument_id: {from: code, template: "KR:{value}"}
  session_date: {from: date, format: "%Y%m%d"}
  close: {from: 종가}
  volume: {from: 거래량}
availability: {rule: ts_end}
```

- Time text is RFC 3339 (`Z` or an offset required). Times without an offset require `timezone`, and times in a daylight-saving overlap are rejected as an error (`TDS-S004`).
- Numeric missing values are empty fields. `NaN`, `-`, `0` as missing markers only via `missing_values` in the mapping file.

### 9.6 Qlib → TDS

`instruments/all.txt` → `instruments` (listed_on/last_session), `calendars/day.txt` → `calendar_sessions` (open and close [supply]), `features/<s>/<f>.day.bin` (first value = calendar position, float32) → `bars` (not price_basis = total_adjusted but **raw prices restored with the Qlib factor**: `raw = adj / factor`), `factor` changes → 5.12 event back-solving. PIT `*_q.data` (date, period, value, _next) → `fundamentals_events` (`known_on = date`, period integer → period_end) [loss: original precision is float32].

### 9.7 Massive (formerly Polygon) flat files → TDS

`day_aggs_v1` (ticker, volume, open, close, high, low, window_start ns, transactions) → `bars(freq=1d)`: `window_start` → `session_date` (New York local date), `transactions → trade_count`, availability rule `column` (the file distribution time = 11:00 ET the next day [verified] as a column). Ticker → id mapping needs the user's `instrument_symbols` [supply].

### 9.8 Export (TDS → other formats)

| Target | Use |
|---|---|
| `zipline-bundle` | **For parity tests**: build a zipline bundle from the same TDS snapshot and feed the same data to the engine and zipline (specification 8.1). Also writes the list of rows outside uint32 |
| `nautilus-catalog` | E4 event engine |
| `wide-parquet` | Wide tables for vectorbt and pandas users (one table per price or factor column) |

---

## 10. Versioning and evolution rules

### 10.1 Three versions

| Subject | Format | Example |
|---|---|---|
| Standard | `tds_version` = `MAJOR.MINOR` | `1.0` |
| Dataset schema | per dataset kind `schema_version` = `MAJOR.MINOR` | `bars 1.0`, `fundamentals_state 1.1` |
| Package (data) | `version` / `snapshot_id` (producer's choice; a sortable string recommended) | `20261027-143144` |

Standard `1.x` bundles all dataset schemas `1.x`. If a dataset schema MAJOR rises, the standard MAJOR rises too.

### 10.2 What is MINOR and what is MAJOR (from the reader's side)

| Change | Version |
|---|---|
| Adding an optional (nullable) column | MINOR |
| Adding a value to an open enum | MINOR |
| New dataset kind, new profile, new availability rule name | MINOR |
| Adding a warning (W) check | MINOR |
| Adding a required column, nullable → non-nullable | MAJOR |
| Changing a column's name, type, unit or meaning; removing a column | MAJOR |
| Adding a value to a closed enum | MAJOR (old readers reject it) |
| Changing key, sort or partitions | MAJOR |
| Adding a new error (E) check | MAJOR. Except "the standard text already forbade it but there was no check": MINOR + W first for one version |
| Wording fix (same meaning) | No version change (document fix record only) |

### 10.3 Reader and writer obligations

- Readers (engine, checker): read data of a higher MINOR of the same MAJOR. Ignore unknown columns and datasets with an M011 warning. Unknown open enum values as `other`.
- Writers: write all required columns of the declared version. New MINOR columns are optional, so a writer may declare that MINOR without writing them.
- Deprecation: to remove a column, `deprecated: true` for one MINOR (dictionary and schema documents) → removal in the next MAJOR.
- The standard schema files (`tds-schemas/<kind>/<MAJOR.MINOR>.json`: columns, types, null, key, sort) are the machine-readable source. The tables in this document are those files written for people (generated from the tables at implementation).

### 10.3a Handling unknown features (v1.1) [RV-I01]

- When reading a package of a higher MINOR of the same MAJOR, a consumer distinguishes by **whether it uses unknown features**: unknown optional columns and optional datasets → ignore (M011); unknown descriptive open enum values → `other`; things that affect execution or interpretation (availability rule names, new values of closed enums, `hash_spec`) → reject (M014). So there is no promise to "accept every future 1.x package".
- **Adding a value to a closed enum stays MAJOR** (an old consumer cannot do accounting without knowing the meaning). Descriptive enums (`category`, `delist_type`, `reason`) are kept open so they grow by MINOR.
- `experimental` schemas (5.6–5.9, 5.22–5.24) are outside this compatibility promise.

### 10.4 Extensions and registration

- Producer extensions: `x_<ns>_` columns, `<ns>:`-prefixed enum values (e.g. `delist_type = "ex:spac_warrant_expiry"`), namespaces of `event_type`. If several producers use the same extension, it is promoted to the standard in the next MINOR.
- Reserved standard namespaces: `tds`, `x`; country codes such as `KR`/`US` may be used by anyone as id namespaces (meaningful only inside a package, so no conflict). Id stability across snapshots is promised only between packages with the same `id_namespaces` descriptions (producer authority).

### 10.5 Release status and 1.0 graduation criteria (v1.1) [RV-I07]

- Status: **draft** → **candidate (RC)** → **1.0**. The `tds_version` string is `"1.0"` regardless of status (grammar `MAJOR.MINOR` unchanged), and the status is shown only by repository tags (`tds-v1.0.0-rc.N`, `tds-v1.0.0`) and the document header.
- Draft → RC: checker levels `manifest`, `schema`, `full` and the hash test vectors are implemented, and the synthetic package passes every stable profile.
- RC → 1.0 (all required): (1) one **independent producer** package (via an import tool is fine, e.g. CSV import) passes `full`, (2) one producer export (e.g. the reference producer's build) passes `full`, (3) a consumer (engine) reads both and the same example runs, (4) the value and semantic hash test vectors agree in two independent implementations (the pyarrow path and the pure-Python reference encoder, or another language), (5) a canonical English document (after the public documentation language decision).
- After 1.0, changes to stable schemas follow the 10.2 rules.

---

## 11. (Removed from the public edition)

This chapter is one producer's export plan, not a norm of the standard, and is not included in the public edition. Only the chapter number is kept so that references from other chapters stay valid.

---

## 12. Alignment with chapter 4 of the engine specification (difference list)

> This table records where the TDS v1 draft differed from chapter 4 of specification **v1** (specification v2 and v3 have absorbed all of it). What changed in v1.1 is in chapter 15.

**Principle: TDS replaces chapter 4.** The meaning of chapter 4 (what it holds) mostly stays and the names and shapes change. Where other chapters of the specification (3, 5, 8, 10) use chapter 4 names, read them through this table at implementation time. The specification text is fixed in one pass after the maintainer confirms.

| # | Specification chapter 4 | TDS | Reason |
|---|---|---|---|
| D1 | `security_id` | `instrument_id` (v1.1: no alias) | A name independent of asset kind (chapter 13 Q1) |
| D2 | `*_utc` column names (`open_utc`, `available_at_utc`, `valid_from_utc` …) | `ts_*` (`ts_open`, `ts_available`, `ts_known_from` …) | The type guarantees UTC, so it is dropped from the name; Nautilus and Databento convention |
| D3 | `manifest.json` (`schema_version: "nexusbt-export/1"`) + `columns.json` | `tds.json` (`tds_version`, per-dataset `schema_version`, profiles, coverage) + `dictionary/` datasets | Public standard, profiles, coverage |
| D4 | One time unit, us | us for daily bars, fundamentals etc. (unchanged), ns for ticks and quotes | Tick precision |
| D5 | Partition `country=` | `market=` (key of the manifest `markets`) | Crypto and futures markets |
| D6 | `instrument_master.parquet` | `instruments/` (+ `issuer_id`, `venue_mic` and `operating_mic`, `is_synthetic`, `index_kind`, `listed_on_censored`, `tick_size`, derivative column names such as `ts_expiry`) | |
| D7 | `symbol_history.parquet` (symbol, name, valid_from, valid_to) | `instrument_symbols/` (names, tickers and vendor symbols in one table via `symbol_type`, `ts_known_from`) + new `instrument_xref/` | |
| D8 | `rule_version`, `price_limit_pct` in `calendar_sessions` | Removed from the session table. The limit is `tradability_daily.price_limit_ratio`, rule versions are 1.1 `market_rules` (Q15); `session_ord` optional | The session table holds only time |
| D9 | `bars_1d` columns `shares_out`, `adj_split_cum`, `adj_total_cum`, `available_at_utc` | `shares_out` → `share_counts/` (PIT); factors → `cum_factor_split`, `cum_factor_total` (same meaning: first session 1.0, forward-cumulative); optional `ts_start`/`ts_end`/`price_type`/`trade_count`/`vwap` added; availability time is the rule `ts_end` | Share counts have a different availability time from prices. The engine's `weight=value` computes market cap with a point-in-time lookup of `share_counts` (Q4) |
| D10 | `tradability_1d` | `tradability_daily` (`price_limit_pct` → `price_limit_ratio` (0.30), `halted` → `halted_full_day` + `halt_count`, `admin_status` and `reference_price` added) + new `trading_status_events` | Unified ratio unit, US halt records |
| D11 | `corp_actions.parquet` (`ratio`, `cash_amount`, `effective_ts_utc`, `announced_available_at_utc`, `amount_available_at_utc`) | `corporate_actions/` (`ratio_new_per_old`, `cash_per_share`, `ts_effective`, `ts_announced`, `ts_terms_available`, + `declared_date`, `share_factor`, `factor_method`, `factor_ref_price`, `subscription_price`, `gross_or_net`, `status`; `bonus_issue`, `capital_reduction`, `rights_issue`, `return_of_capital`, `mixed_merger`, `exchange_offer`, `par_change` added to kind) | Representation of rights and spinoff data (engine handling stays within v1 scope: unsupported events fail or follow policy as in specification 5.6.12) |
| D12 | `classif_pit` (`valid_from_utc`, `valid_to_utc`, `known_at_utc`, `edition` column) | `classifications/` (effective `effective_from/to` date + known `ts_known_from/to`, `pit_quality`; `edition` column kept) | Symmetric two time axes |
| D13 | `exits.parquet` | `delistings/` (`exit_available_at_utc` → `ts_exit_known`, `value_available_at_utc` → `ts_value_available`, optional `crsp_dlstcd_equiv` added; the rest the same) | |
| D14 | `fund_state/` (`valid_from_utc`, `valid_to_utc`) + `facts_pit/` | `fundamentals_state/` (`ts_known_from`, `ts_known_to`, the rest the same) + `fundamentals_events/` (`ts_recorded`, `supersedes_fact_id`, `pit_quality`, `accounting_standard` added) | Names; preparation for system history |
| D15 | `benchmarks_1d.parquet` | Index = `instruments(asset_class=index)` + `bars` | Fewer table kinds |
| D16 | `universe_1d/` (`is_investable`, `exclusion_reason`) | `eligibility_daily/` (`rule_id`, `is_eligible`, `reason`) + new `universe_membership/` | Several rules, index membership |
| D17 | `fx_1d` (`observed_date`, `observed_at_utc`) | `fx_rates/` (`obs_date`, `ts_event`, `rate_kind`) | Frequency-independent |
| D18 | `panel_monthly/`, `labels_monthly/` (`month`, `lineage_flags`) | `feature_panels/name=…`, `label_panels/name=…` (`period`, lineage columns as `x_ex_*`) | Several panels |
| D19 | Logical hash definition | Same + "partition columns included as path values" made explicit (v1.1: redefined as the value hash, 4.5) | Removes ambiguity |
| D20 | Whether partition columns are inside files undecided | Not put in files (Hive) | 3.6 |
| D21 | 4.18 check table (`SnapshotError` E14) | Uses the chapter 8 checker levels and codes as is. TDS codes in the E14 message | One checker |
| D22 | `LATEST`, `PINS`, retention rules | Kept as is outside the standard (producer distribution convention); v1.2: the snapshot folder is the package (no separate export folder) [V31-PUB-02] | |
| D23 | 4.17 engine resource `kr_price_limits_v1.csv` | Stays an engine resource (fallback when the data is null). Moves to the data side once 1.1 `market_rules` exists | |
| D24 | 4.19 synthetic generator | The same generator writes TDS packages and must pass `tds check --level full` (test `test_synth_conforms`) | One format |

What does not change: raw prices + events + factor definition (the m_e formulas), half-open intervals, no filling of the strict edition from compare, the default rule `known_on → next session open`, missing = null, deterministic writing, per-market completeness watermarks, the table sort principle (daily bars sort by date first).

---

## 13. Open questions (work does not stop; recommended defaults apply)

| # | Question | Recommended default |
|---|---|---|
| Q1 | Rename `security_id` to `instrument_id` in the engine public API too? | **Closed (v1.1)**: only `instrument_id`, no alias (unanimous in the three-way review). External names only in import mappings |
| Q2 | Can a DuckDB-based producer (DuckDB 1.5.6) handle tick ns times? DuckDB TIMESTAMPTZ is us and may truncate ns (warned in the Nautilus docs [verified]) | Tick data is written directly with pyarrow from a separate collection path, not from the producer database. Daily bars are us, so no problem |
| Q3 | Use the SEC acceptance instant as the precise fundamentals availability time, or keep the conservative `known_on` next session open? | v1 uses the conservative rule (same as the specification). The acceptance instant is shipped alongside as `fundamentals_events.x_ex_ts_accepted` and switched when the policy version is raised |
| Q4 | Removing `shares_out` from bars means the engine's `weight=value` needs a new `share_counts` lookup | Remove it (different availability time). The engine uses a point-in-time `share_counts` (listed) lookup × close. Reconciliation test against the producer panel's market cap |
| Q5 | Relation between publishing the standard document and keeping producer data private | **Closed**: only **data** may be private; the format specification and the checker code are public (Apache-2.0) |
| Q6 | Standard name and schema URL (`nx.dev` is a placeholder) | After the engine name is fixed (N1) (before creating the public repository — recommended by the three-way review). Until then `$schema` is the relative path `tds/schemas/1.0/tds.schema.json`. The checker import name is `nexusbt_tds` (`tds` is too common) |
| Q7 | Defining the logical hash as Arrow IPC bytes may vary with the Arrow version | **Closed (v1.1)**: fixed before 1.0 with the 4.5 canonical value serialisation (value hash) + resolved metadata (semantic hash) + test vectors (unanimous in the three-way review) |
| Q8 | Is float64 enough (binary error of US cent prices, Korean fundamentals of 2e15 won)? | Daily bars and fundamentals float64 (2^53 ≈ 9e15 > 2e15). Account computations that need exact amounts are converted by the engine to integer minor currency units (specification INV-06) |
| Q9 | Without partition columns in files, reading a single detached file has no value | Do not put them in (fewer conflicts with tool defaults). Instead record the path values in the Parquet key-value metadata `tds.partition` (optional) |
| Q10 | Edition in `classifications`: column (`edition`) or partition? | Column (few rows). Only large tables (`fundamentals_state`, panels) use partitions |
| Q11 | `eligibility_daily` availability time: can it be judged from pre-open information alone? If a producer rule (e.g. `investable-v1`) uses that day's close or market cap, `session_close` | The producer declares the rule. The engine follows the declaration (if judged at the close, used only at decision times after that day's close) |
| Q12 | Korean ex-date derivation rule (changes in settlement cycle) | Register as a contract after research. Until then only `record_date` is certain; mark `ex_date_method` |
| Q13 | Cumulative factors as bar columns or a separate dataset (a late-discovered old event forces rewriting all later partitions) | Bar columns, **optional in every profile** (v1.1). Events are the source and factors are convenience values. A separate `adjustment_factors` dataset after measuring rewrite costs (three-way review consensus) |
| Q14 | Who writes the defining sentences of the TDS core fundamental items (`std_item`)? | v1.1 marks them "provisional mapping" (5.17). An appendix in the next version, seeded by the producer's standard column list |
| Q15 | Keep tick size and price limit rule changes as data (`market_rules`) or as engine resources? | **Closed (v1.2)**: 5.27 `market_rules` (optional, stable). If present in the data, the data comes before engine resources [V31-05] |
| Q16 | Run the three-way discussion (Opus 5.5 + Fable 5.1 + GPT-6.1 Sol xhigh) review on this draft? | **Done** (2026-10-28, together with specification v2; `review/`). The result is v1.1. One more TDS-only round is optional before 1.0 graduation |
| Q17 | Put an engine-side "support matrix" in the standard? | No (v1.1). The standard defines only conformance; consumer support is stated per version in the consumer documentation (engine specification 4.3) |

---

## 14. Sources

Opened and checked for this document [verified]:
- zipline bundles: https://zipline.ml4trading.io/bundles.html
- zipline adjustment writer: https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/data/adjustments.py
- zipline asset DB writer: https://raw.githubusercontent.com/stefan-jansen/zipline-reloaded/main/src/zipline/assets/asset_writer.py
- LEAN data format concepts: https://www.quantconnect.com/docs/v2/lean-engine/data-format/key-concepts
- LEAN US equity format: https://www.quantconnect.com/docs/v2/lean-engine/data-format/us-equity , https://raw.githubusercontent.com/QuantConnect/Lean/master/Data/equity/readme.md
- NautilusTrader data: https://nautilustrader.io/docs/latest/concepts/data
- NautilusTrader catalog: https://nautilustrader.io/docs/latest/concepts/data/catalog/
- Databento schema list: https://databento.com/docs/schemas-and-data-formats
- Databento DBN: https://databento.com/docs/standards-and-conventions/databento-binary-encoding
- Databento common fields: https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- Databento symbology: https://databento.com/docs/standards-and-conventions/symbology
- Databento OHLCV: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Qlib data: https://qlib.readthedocs.io/en/latest/component/data.html
- Qlib PIT: https://qlib.readthedocs.io/en/latest/advanced/PIT.html
- Qlib dump_bin: https://raw.githubusercontent.com/microsoft/qlib/main/scripts/dump_bin.py
- hftbacktest data: https://hftbacktest.readthedocs.io/en/latest/data.html
- Massive flat files (daily): https://massive.com/docs/flat-files/stocks/day-aggregates.md , https://massive.com/docs/flat-files/quickstart
- Parquet logical types: https://github.com/apache/parquet-format/blob/master/LogicalTypes.md
- Parquet configuration recommendations: https://parquet.apache.org/docs/file-format/configurations/
- Frictionless Data Package v2: https://datapackage.org/standard/data-package/
- SchemaVer: https://docs.snowplow.io/docs/api-reference/iglu/common-architecture/schemaver , https://snowplow.io/blog/introducing-schemaver-for-semantic-versioning-of-schemas
- MIC (ISO 10383): https://en.wikipedia.org/wiki/Market_Identifier_Code , https://www.iso20022.org/sites/default/files/media/file/FAQ_ISO_10383_January2023.pdf
- CRSP CIZ migration: https://wrds-www.wharton.upenn.edu/pages/data-announcements/changes-to-crsp-data , https://www.crsp.org/crsp_pdf/crsp-us-stock-indexes-databases-fiz-to-ciz-executive-summary
- CCM links (secondary source): https://docs.nuvolos.cloud/user-guides/data-guides/working-with-crsp-and-compustat , https://crsp.org/crsp_pdf/january-2009-monthly-release-notes-1-2
- Sharadar dimensions (secondary source): https://www.quantrocket.com/codeload/fundamental-factors/fundamental_factors/Lesson03-Basic-Usage.ipynb.html
- OpenFIGI levels (secondary source): https://docs.cybersyn.com/free-public-data-products/sec-filings/data-dictionary/openfigi-security-index , https://openfigi.com/about/features

Not opened, or original still to be checked [unverified]:
- vectorbt: https://vectorbt.dev/ (source: the engine survey document)
- backtrader feeds: https://www.backtrader.com/docu/datafeed/
- ArcticDB: https://github.com/man-group/ArcticDB
- kdb+/tick: https://code.kx.com/q/kb/kdb-tick/
- LEAN factor and map file columns, latest format
- FIGI character structure: https://www.openfigi.com/about/figi
- ISIN ISO 6166, ISO 4217 minor unit table, list check of XKRX, XNYS, XKOS: https://www.iso20022.org/market-identifier-codes
- tz meaning in the Arrow schema: https://github.com/apache/arrow/blob/main/format/Schema.fbs
- Avro schema resolution / Confluent compatibility rules: https://avro.apache.org/docs/ , https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html
- `hash` grammar of the Frictionless Data Resource: https://datapackage.org/standard/data-resource/
- CRSP delisting code table, CIZ field names
- FRED H.10 release schedule, changes in Korean ex-dates and settlement cycles, effective date of the Korean trading-hours extension

Local evidence:
- Engine specification `engine-spec-v1-2026-10-27.md` chapters 1, 4, 5, 10, 11; design document `engine-design-2026-10-27.md` 4.2, 4.3, 9.0, 11.5

## 15. v1 → v1.1 change summary (three-way review, 2026-10-28)

`tds_version` stays `"1.0"` (still a draft, before any compatibility promise; the items below correct definitions before 1.0 graduation). Reference numbers are from `review/consensus.md`.

| Area | v1 | v1.1 | Reference |
|---|---|---|---|
| Hashes | Logical hash = Arrow IPC bytes (varies with version and implementation) | Three: physical, value (language-independent canonical serialisation, `hash_spec = tds-hash-1`), semantic (value + resolved metadata); test vectors published | C10a, Q7 |
| Two time axes | No `level` in the classification key, no `ts_known_to` in the symbol table, lookup method ambiguous | Classification key `(instrument_id, scheme, level, edition, effective_from, ts_known_from)`, `level` null forbidden, `instrument_symbols.ts_known_to`, rectangle lookup with 5 examples, `instrument_xref` stated to be outside the two-time-axis promise | C08 |
| Strict quality | Contradiction between K6 "excluded" and 6.5 "warning" | Row-level backfilled excluded from strict lookups, dataset-level warned | C09 |
| Eligibility | Default `session_open`, ambiguous meaning of missing (consumer could carry forward) | Default `session_close`, no row for that session or unpublished = not eligible, no carry-forward | C09 |
| Corporate actions | No resolution procedure, `share_factor` default = 1/price_factor, typo `ts_amount_available` | Resolution procedure (5.11: chains, version at the reference time, status, four effects, corrections), `share_factor` not inferred outside split-like kinds, unified `ts_terms_available`, A008 and A009 | C03, Q03 |
| Delistings | `ts_exit_known` required | Nullable (backfilled), consumer sentence that recoveries are not used in decisions before `ts_value_available` | Q09, C01 |
| Label table | No time columns | Optional `ts_label_start/end/available`, `return_definition` examples | C04 |
| Profiles | No versions, one "pass", `minimal-daily` promised a close-price backtest, research required `cum_factor_*` | `@1.0` versions, three results (declared, check level, result, `not_checked`), `minimal-daily` for analysis only, `cum_factor_*` optional in every profile, engine support matrix outside the standard | I01, I03 |
| Compatibility | Unknown enum values as `other`, every MINOR readable | Unknown mandatory interpretation rules and new closed-enum values rejected (M014), only descriptive ones as `other`, experimental schemas outside the promise | I01, Q11 |
| Manifest | `$schema` = a domain not owned, no producer hints, no path safety | Relative-path `$schema`, `producer.hints`, path safety (M012, M013), profile versions | Q04, I09, I01 |
| Experimental | Ticks, books, futures, options, crypto inside 1.0 | `experimental` (M015 warning), only daily equity stable | I07 |
| Fundamentals | `preliminary` not in the enum (contradicting T007), `std_item` presented as a standard without definitions | `preliminary` added and T007 lowered to a warning for it, `std_item` is a provisional mapping | I06 |
| Interoperability | Mapping tables only | Conversion report, zipline `mergers` not treated as conversions, LEAN factor components decoded, Nautilus id grammar and precision, DBN publisher, channel and uint64, `ts_recv+<duration>` | Q08 |
| Identifiers | `<MIC>:<ticker>` recommended for small users, `security_id` alias possible | `<MIC>:<ticker>:<first listing date>` or FIGI, no alias | Q04, Q01 |
| Release | Declared 1.0 | Draft → RC → 1.0, graduation criteria 10.5 | I07 |
| Public edition | Included the producer mapping chapter (chapter 11) | Chapter 11 removed from the public edition, checker import `nexusbt_tds` | Q04 |

---

## 16. v1.1 → v1.2 change summary (teardown of existing engines, 2026-10-28)

Reference numbers are `V31-NN` from `teardown/MATRIX.md` (the same numbers as specification v3.1). **`tds_version` stays `"1.0"`.** Reason: everything changed is only (1) added optional (nullable) columns, (2) added optional datasets, (3) added warning (W) checks, (4) added optional manifest fields — all MINOR in the 10.2 table, and the standard is still a draft before any compatibility promise. Old (v1.1-shaped) packages remain valid, and a v1.1 checker that does not know the new columns still reads v1.2 packages (M011 warning). No error (E) check was added (H004 also starts as W, under the 10.2 "W for one version" rule).

| Area | v1.1 | v1.2 | Reference |
|---|---|---|---|
| Corporate action ratios | Only f64 `ratio_new_per_old` and `share_factor` (1:3 and 0.29 are not exact binary fractions, so a consumer loses a share) | Optional `ratio_num`, `ratio_den` (integers, canonical), check A010 (W) | V31-01 |
| Delistings | Unknown whether `ret_observed` includes distributions after the last trading day (double-count risk, LEAN#9819) | Optional `ret_observed_includes_distributions`, check A011 (W) | V31-04 |
| Volume unit | Only the sentence "raw volume (shares)", the only check was integrality (V010) | Sentence forbidding lot units + V011 (W: median of traded value/(volume × representative price) outside [0.5, 2]; qlib#2362) | V31-16 |
| Price grid | No `market_rules` for `tick_rule_id` to point to (Q15 open) | 5.27 `market_rules` (optional, stable), grid norm and V012 (W) | V31-05 |
| Hashes | Only dataset and package value hashes | Optional `files[].value_sha256` (per-file canonical value hash, for consumer incremental caches), H004 (W) | V31-12 |
| Indices | Only `index_kind` | Optional `instruments.index_weighting` (weighting method marker) | V31-15 |
| Producer | Assumed an export layer (`export/<id>/`) | The producer build MAY write the package directly, immutability per snapshot folder, hard links and content-addressed partitions allowed (the hash defines the content), consumers do not require write permission | V31-PUB-01 |
| Shorting | – | No data change. Ban periods are in the engine rules pack; securities lending data is a candidate for the next MINOR (end of 5.27) | V31-LS-07 |

## 17. v1.2 → v1.3 change summary (review round 3, 2026-10-28)

Reference numbers are `R3-NN` from `review/consensus-r3.md` (the same numbers as specification v3.2). **`tds_version` stays `"1.0"`.** Reason: the changes are only (1) fixes to the sentences by which consumers interpret existing columns (5.11 version choice, 5.13 terminal-value basis, 5.27 comparison coordinate) — the columns, types and requiredness that producers write are unchanged, and the v1.2 sentences were self-contradictory (the 5.11 pending state was unreachable, 5.13 reduced distributions twice), so the fix is the original intent, (2) recommendations and SHOULDs (clone first, read-only, atomic publish, file identity, `value_sha256` advisory, watermark excluded from cache keys), (3) an example fix (K1). The only MUST makes explicit the existing "never modify published files in place". No check code was added and no severity changed (A010 stays W; consumer rejection is written as permitted). Still a draft before any compatibility promise, and old packages remain valid.

| Area | v1.2 | v1.3 | Reference |
|---|---|---|---|
| Corporate action version choice | `ts_pub = coalesce(terms, announced, effective)` — a version with late terms is hidden entirely | Choose by existence time `ts_known` and hold pending by terms time `ts_terms`; entitlement quantity fixed to the holding at the effective session | R3-01 |
| Terminal value | includes = false → "basis multiplied by the distribution factor" | Observed (includes and excludes) uses `ref_units`, policy uses the post-distribution basis; if included, the distribution already booked is subtracted; `ret_hi` is not an upper bound | R3-05, R3-09 |
| Price comparison | Grid integers (tick counts) | One coordinate of market-minimum-unit integers; observed prices off the grid are not converted | R3-02 |
| Exact ratios | A010 (W) | A010 unchanged (W), consumers MAY reject invalid canonical values, f64 inference recorded | R3-06 |
| Package immutability | Hard links and content addressing allowed, sentence forbidding in-place modification | Clone first with hard-link fallback, publish = staging → check → atomic switch, read-only (SHOULD), shared file reconciliation, consumer file identity (recommended), DuckLake reason fixed | R3-16 |
| Hashes and caches | `files[].value_sha256` for incremental cache keys | Advisory — cache identity is the file sha256; recommended to exclude the watermark from keys | R3-04 |
| K1 example | `XNAS:AAPL:19801212` (violates its own regex) | `XNAS:AAPL_19801212` | R3-28 |

## 18. v1.3 → v1.4 change summary (review round 4 + maintainer decision, 2026-10-28)

Reference numbers are `R4F-NN` of specification v3.4 (appendix I). **`tds_version` stays `"1.0"`.** Reason: the standard is still a draft before any compatibility promise (10.5), and the reference producer already writes `ratio_num/ratio_den` in `tds.corporate_actions`. After 1.0 is final, optional → required would be MAJOR (10.2).

| Area | v1.3 | v1.4 | Reference |
|---|---|---|---|
| Exact ratios | Optional columns, A010 (W), consumer f64 inference allowed if recorded | **Required** for events that change share counts, A010 (E); f64 inference forbidden; only decimal literals by user setting as an exception (warning and count) | R4F-01 (maintainer decision 2026-10-28) |
| Null "includes distributions" on delistings | Treated as false + warning | The smaller total recovery of the two interpretations + warning (never counted twice) | R4F-05 |
| `events` | Only instrument and issuer events | Optional `series_id` (market-level events), `consensus`, sentence requiring `ts_available`, revision = new id, check V041 (W) | R4F-EV-02 |
| `series_observations` | Vintage columns | Optional `consensus` and `frequency`, first-release vintage definition, sentence that release time ≠ end of the observation period | R4F-EV-01 |

---

## Revision history
- 2026-10-27: draft written (survey + TDS v1 + producer mapping + differences from specification chapter 4).
- 2026-10-28: **v1.1**. Applied the three-way review consensus (chapter 15).
- 2026-10-28: **v1.2**. Applied the teardown of existing engines (chapter 16, `[V31-NN]`): optional columns `ratio_num/ratio_den`, `ret_observed_includes_distributions`, `index_weighting`, `files[].value_sha256`, optional dataset `market_rules` (5.27), warnings A010, A011, V011, V012, H004. `tds_version` stays `"1.0"` (MINOR in nature + draft). The standard version string is kept at `"1.0"`, status = draft.
- 2026-10-28: **v1.4**. Applied review round 4 + maintainer decision (chapter 18, `[R4F-NN]`): `ratio_num/ratio_den` required for corporate actions that change share counts, A010 E, f64 inference forbidden (decimal literals only by user setting), null "includes distributions" on delistings = the smaller one. `tds_version` stays `"1.0"` (draft).
- 2026-10-28: **v1.3**. Applied review round 3 (chapter 17, `[R3-NN]`): 5.11 separation of existence and terms time, 5.13 terminal-value basis fixed, 5.27 minimum-unit integer comparison, 4.1 clone first, atomic publish, read-only, file identity, 4.2 `value_sha256` advisory and watermark, A010 consumer rejection allowed, K1 example. `tds_version` stays `"1.0"` (only interpretation wording fixes, recommendations and examples; draft).
