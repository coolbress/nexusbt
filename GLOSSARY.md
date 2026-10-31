# NexusBT glossary

In this repository the words below mean exactly this. Code names are in parentheses. Korean translation: [GLOSSARY.ko.md](GLOSSARY.ko.md) (this English file is canonical).

This file holds the terms of the spec's glossary (spec §1.2 and §9.2) and nothing about implementation. `CONTEXT.md` and `CONTEXT.ko.md`, the names the spec uses (§2.3, §9.2, ticket T0.1), are symbolic links to this file and its translation. A term is added or changed here when it is settled, with `/domain-modeling`; if it changes a rule, the spec changes first.

## Five nouns every user knows

- **Data column** (`Price.close`, `Fund.equity`, `Meta.sector`, `Panel.bm`, `Label.*`, `Trad.*`): an importable attribute built from the snapshot's column dictionary. `Label.*` is a label (ground truth) and may be used only in `evaluate(target=...)` and `ml.factor(label=...)`.
- **Term** (`Factor`, `Filter`, `Classifier`): a node of the computation graph, built from columns and combined with other terms. Same names and meanings as the zipline Pipeline.
- **Strategy** (`Strategy`): a value object with nine slots — schedule, universe, signal, construction, sizing, risk, execution, exits, costs.
- **Run**: one call of `evaluate`, `backtest`, `screen`, `sweep` or `live`. Sealed into `runs/<run_id>/`.
- **Config** (`nexusbt.toml`): project defaults in two parts. Part 1 is what changes results most (data path, edition, capital, base currency, sleeves, account type, shorting, costs, taxes, segments); part 2 is advanced. `nexusbt config check` and `nexusbt config show` explain it.

## Data and time

- **TDS** (NexusBT Data Standard): the only input format the engine reads — a folder with `tds.json` and Parquet files. Versioned separately under `tds/`; checked by `tds check`.
- **Producer**: whoever builds a TDS package (a CSV import, a data warehouse build, …). The engine reads packages only and knows no particular producer; producer hints go only in `tds.json producer.hints`.
- **Instrument id** (`instrument_id`): an opaque, never-reused string key chosen by the producer. No aliases.
- **Snapshot / package**: a published, immutable TDS folder with a `snapshot_id` and three hashes — physical (file bytes), value (canonical serialisation, TDS 4.5) and semantic (value + resolved metadata). The engine decides "same data" by the semantic hash.
- **Profile**: a TDS bundle a package claims to follow (`tds:equity-daily-core@1.0`). A claim only; what the engine needs is the *capability* of the datasets the graph uses. Results come in three: declared / verified up to a level (manifest, schema, full) / supported by this engine.
- **Capability**: whether the snapshot has the data a graph needs. Missing capability fails with `CapabilityError` (E18) or triggers a defined fallback.
- **Fallback**: a defined engine behaviour when a profile or column is missing. Always warned (E30) and recorded in the manifest; never hidden.
- **Edition**: `strict` (default; only values whose lineage has no vendor input or after-the-fact publication) or `compare` (vendor values included, for comparison).
- **Market**: a key of TDS `markets` (for example `KR` = XKRX/KRW, `US` = XNYS/USD). Never hard-coded. A **supported market** has a market rules pack (`resources/markets/<M>.toml`).
- **Market rules pack**: per-market rules — price limits, tick grid, rounding, provisional costs, settlement and short-sale ban dates, margin seeds. Seeds marked unverified are reported as such.
- **Session**: one trading day of a market calendar. `ts_open` and `ts_close` are the real instants; the date is a label.
- **Availability time** (`ts_available`): the first UTC instant an observation may be used. A date-only value becomes usable at the next session open.
- **Information cutoff** (`decision_ts`): the last instant of information a decision may use. One rule everywhere: `ts_available <= decision_ts`.
- **As of**: always "as of `decision_ts`". Currencies and date strings never set the as-of time.
- **Market axis**: the session sequence of one market. Row s freezes at `ready(s) = ts_close(s) + declared delay` and never changes afterwards.
- **Phase**: the order inside a session: `session_start < open < intraday < close_fill < close_mark < decision < session_end`. Equal instants follow this order.
- **As-of adjustment**: past prices in a window adjusted only by splits and dividends known up to the computation day. Future splits are unknown.
- **Corporate-action resolver**: the one function that, given a reference time, resolves amendments, cancellations and late terms into one version per chain and four effects (price factor, share factor, entitlement, settlement). Adjustment, accounting, labels and checks all use it.
- **Exact ratio** (`ratio_num/ratio_den`): every share-changing corporate action carries an exact integer ratio. The engine never infers fractions from floats; a decimal literal is used only if the user opts in (`[corporate_actions] decimal_ratio = "literal"`, warned).
- **`fundamentals_state`**: resolved financial-state intervals `[ts_known_from, ts_known_to)` published by the producer (period choice, TTM, source priority, strict eligibility). The engine only looks them up. Raw facts are `fundamentals_events`.
- **Two time axes**: classifications and index membership are used only when both the effective period (`effective_from/to`) and the known period (`ts_known_from/to`) hold.
- **Forward cumulative factors** (`cum_factor_split/total`): products of event factors starting at 1.0 on the first listed session. New data never changes old values.
- **Watermark**: the last complete session of a market in a snapshot. `live` never fills after it.
- **Macro series** (`Macro.series`): a versioned (vintage) macro or alternative series from `series_observations`, used as a market-level term. Default `vintage="as_of"` = the latest version known at the decision.
- **Event term** (`Events.<kind>`, `Events.of(type)`): a term over event datasets (earnings, filings, dividends, …). An event exists only after its `ts_available`. `surprise = value − consensus` when both exist.
- **External dataset** (`nx.dataset.from_parquet`, `nx.dataset.from_frame`): a user table in one of three shapes (`panel`, `events`, `series`). A `known_on` column is required; the table is hashed by the TDS value-hash rule and copied into the run folder.

## Decisions and accounts

- **Sleeve**: an account compartment funded once for one market. Cash in local currency; no transfers between sleeves. Target weights are per sleeve.
- **Reference clock** (`clock`): the decision time for multi-market strategies: `"<MARKET>_close"` (for example `KR_close`: Korean close, US values from the previous session) or `market_local`.
- **Base currency** (`base_ccy`): the currency of combined reports. Changes valuation only, never information time.
- **Decision** (`DecisionContext`): one time a sleeve sets its targets. Records id, `decision_ts`, session and snapshot.
- **Schedule**: when decisions happen (`nx.monthly()`, …). `nx.on_event(trigger, delay=)` schedules decisions after events; event schedules combine with others by `|`.
- **Eligibility / tradability**: eligibility = can it be chosen at the decision (universe); tradability = can it fill in the execution session (state machine).
- **Canonical target** (`target_weight`): the decision's `(instrument_id, target_weight)` table, from market information only — a pure function, identical in `screen` and `backtest`. Built by construction (`portfolio=`) → sizing (`sizing=`) → market-only risk rules (`risk=`).
- **Final target** (`final_weight`): the canonical target times the multipliers of account-reading risk rules (drawdown brake, portfolio stop, no-reentry). Orders use this value.
- **Sizing slot**: a pure function that sets weights for the chosen names (equal, inverse volatility, ERC, volatility target, …). Never reads the account.
- **Risk slot**: an ordered list of rules that only scale weights toward zero. Rules that read the account run only in the final-target layer.
- **Shadow index**: the canonical target held without costs. The drawdown brake uses it to decide re-entry.
- **Target state / anchor**: the previous decision's canonical target set and the decision where that recursion starts. The hold band (`hold=`) relies on it instead of account holdings.
- **Order intent**: a fixed share quantity computed from the final target and the account state.
- **Order status**: NEW → ACCEPTED → (TRIGGERED) → PARTIALLY_FILLED → FILLED, or CANCELLED / EXPIRED / REJECTED. A trigger persists; quantities always satisfy `requested = filled + cancelled + remaining`. "Blocked" is a session event, not a status.
- **Order types**: market, limit, stop, stop-limit; time in force day or GTC.
- **Exit order**: a protective order created right after the entry fill, resized on every holding change, never expiring; cancelled only when the holding is zero. Exits include stop, trailing stop and time stop.
- **Adverse assumption**: an unknown price order inside a daily bar is assumed adverse to the order owner. Short sales and covers mirror the same rule.
- **Signed position**: long = positive, short = negative. Gross exposure = Σ|w|, net = Σw. Shorting is off by default; when on, collateral, borrow cost and short dividends apply.
- **Account type** (`[account] type`): `cash` (default; cash never goes negative from fills) or `margin` (borrowing with initial and maintenance margin, debit interest, a close-of-session margin call reduced at the next open).
- **Ruined sleeve** (`ruined`): a sleeve with shorts whose decision value is ≤ 0. New orders stop; only mandatory obligations are booked, as negative cash. The cash account has no forced liquidation; the margin account liquidates fully when equity is ≤ 0.
- **Price grid**: the tick grid of a market, date and price band. Order prices snap conservatively to the grid; comparisons use integer market minimum units.
- **Three-valued Filter**: true, false, unknown (missing input). At the final use (universe, selection, mask) unknown is false. Explicit replacement only via `Filter.fillna(bool)`.
- **Participation cap**: daily fill ≤ maximum participation × average volume of the past 20 sessions (and ≤ a share of that session's volume). The rest carries over.
- **`decision_value` / `nav_economic`**: the account value used for sizing (only what is known at the decision; unknown dividend and delisting amounts excluded) / the economic value used for reports (realised amounts included).
- **Money**: integer minor units (KRW 1 won, USD 1 cent), rounded once per entry. The NAV and P&L bridge closes every day.
- **Entitlement / receivable**: a right created by holding at the ex-date / an entitlement whose amount is known. Cash arrives on the pay date.
- **Terminal value**: what a delisted holding receives — observed-inclusive, observed-exclusive or policy basis — applied once, together with any distribution just before delisting.
- **Provisional costs**: fixed basis-point costs used until cost tables are verified.
- **Fill record**: per fill, the decision resolution (`fill_resolution`), the rule (`fill_rule`), decision price and arrival price.
- **Event truth**: `orders` and `account_events` are the source of truth; every other table is derived from them.
- **Attribution**: returns split into local, FX and cross terms and into cost components. The exposure table (`exposures.parquet`) is holdings exposure, not segment exposure.
- **Reconcile**: replaying a paper ledger with the snapshots it recorded to find the first difference. Comparison with the latest data is a restatement (`restate=True`).

## Research hygiene

- **Segment**: a user-named period (train, validation, test). Not locked; exposure is recorded.
- **Exposure**: the record of which segments a run computed performance on.
- **Study / `study_id`**: the group in which attempts are counted. Default name = file name; stored as a UUID.
- **Candidate / observation / cohort**: candidate = a distinct (graph, parameters, config, segment) inside a study; observation = statistics of one run; cohort = comparable observations. DSR's N and BHY's m are counted within a cohort.
- **Attempt counts**: runs, candidates and assumed independent trials are counted separately.
- **PSR, DSR, PBO**: probabilistic Sharpe, Sharpe deflated by attempts, probability of backtest overfitting (CSCV). Shown, never blocking.
- **MinTRL, BHY, naive breadth, signal–weight correlation**: minimum track record length for this Sharpe; multiple-testing adjusted p; naive opportunity count with IC·√breadth (not independent bets); how much of the signal reached the weights. Shown only.
- **Structural guarantee vs diagnostic**: time rules for engine-managed inputs are guaranteed by construction. Truncation and start-date probes of user functions are diagnostics, not proofs.
- **Registered kernel and numeric order**: engine kernels sum in a defined order (windows by row, cross-sections by `instrument_id`) so results are bit-identical across chunking and ordering in the same environment.
- **Label**: default `fwd_return` = holding return with dividends reinvested at the ex-date close; `fwd_return_adj` = adjusted-price ratio, for comparison. Three label times (start, end, available) purge labels at segment ends.
- **Validation method / splitter / path** (`backtest(method=...)`): `linear` (default), `walk_forward`, `cpcv`, `cscv`. Folds and paths are diagnostics and are not counted as attempts. Purge = drop training samples whose label interval (up to availability) overlaps the test block; embargo = drop training samples right after the test block.
- **ML factor** (`ml.factor`): a Pipeline node that the engine trains forward-only (label availability + embargo ≤ refit time) and that predicts at every decision. Model objects are not saved; prediction and fit tables are.
- **Pretrained model** (`ml.pretrained`): a predict-only model with a declared `training_cutoff`. Decisions before cutoff + embargo are blocked (E48) unless `allow_overlap=True`, which is marked (E49).
- **Oracle**: what a result is checked against — hand-written per-session arithmetic (golden cases), slow reference implementations, producer-resolved outputs, and a pinned zipline-reloaded 3.2.1 (through an imitation preset only).
- **Block / slot**: a value plugged into one of the strategy's nine slots. Each slot has fixed inputs, outputs and what it may read.
- **Error layer**: the second line of every error: `data`, `your code`, `config` or `engine bug`.
- **Preview**: `backtest --preview` runs a short period and shows what the full run would do.
