# START HERE

**Event-driven where it matters, vectorized where it scales. You just snap the blocks together.**

This repository builds **NexusBT**, an open-source (Apache-2.0) backtesting and screening engine for equity factor research. The design is finished; the code is not written yet. Everything an agent needs is in this repository after the hand-off pack is copied in. There is no other memory to look for. Korean translation: [START-HERE.ko.md](START-HERE.ko.md).

## File map (after copying)

| What | Where | Notes |
|---|---|---|
| Engine spec v3.4 (Korean) | [docs/spec/engine-spec-v3.4.md](docs/spec/engine-spec-v3.4.md) | **The single source of truth.** Public edition. If anything disagrees with it, the spec wins |
| Spec checker | `tools/spec_lint.py` (not in the repository yet: it was not in the pack) | `python3 tools/spec_lint.py` (stdlib only): § refs, ticket graph, ids. Run it after any spec edit |
| Ticket index | [SPEC-INDEX.md](SPEC-INDEX.md) | milestone → ticket → spec sections → tests → blocked by. Ticket text lives in spec 10.1 |
| Data standard TDS v1.4 | [docs/tds/tds-v1.4.md](docs/tds/tds-v1.4.md) (+ [.ko](docs/tds/tds-v1.4.ko.md)), [examples](docs/tds/tds-examples.md) | Spec 2.3 and T0.1 place it at `tds/spec/tds-v1.md`; move it there in T0.1 and fix the links |
| Glossary | [GLOSSARY.md](GLOSSARY.md) (+ [.ko](GLOSSARY.ko.md)) | The words of this project. `CONTEXT.md` and `CONTEXT.ko.md`, the spec's names, are symbolic links to these |
| ADRs 0001–0040 | [docs/adr/](docs/adr/) | All accepted. Short form in spec 9.3 |
| Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) (+ [.ko](ARCHITECTURE.ko.md)) | Bird's-eye view, layers, code map (planned), invariants, where to look in the spec |
| Prototype evidence | [docs/design/prototype-results.md](docs/design/prototype-results.md) | Measured P5/P11, 32/32 hand-computed cases, decision-rows = full compute |
| Public README | [README.md](README.md) (+ [.ko](README.ko.md)) | |

The interview notes for `/grill-with-docs` are **not** in this repository. They stay in the hand-off pack folder as `$PACK/GRILL-NOTES.md` on the maintainer's machine and are never committed.

## Read first

1. This file.
2. [ARCHITECTURE.md](ARCHITECTURE.md): the map of the system and its invariants.
3. [GLOSSARY.md](GLOSSARY.md): the glossary.
4. [SPEC-INDEX.md](SPEC-INDEX.md), then only the spec sections your ticket lists.

## Order of work

### (a) Create the repository and copy the pack

1. Create the repository **public with the Apache-2.0 license**. plinth's default license is MIT, so pass it:
   `/plinth:new-project <owner>/nexusbt --archetype=library --license=apache-2.0` (public is plinth's default on GitHub; `--private` would make it private). If it was already created with MIT, replace `LICENSE` with the Apache-2.0 text and add `NOTICE` in T0.1.
2. Copy the pack into the repository root. `-n` never overwrites a file plinth made; exit code 1 only means some files were skipped:

   ```bash
   PACK=<the hand-off pack folder; the user gives you this path. Never write it into the repository>
   REPO=~/nexusbt
   cd "$REPO" && git switch -c docs/handoff-pack
   (cd "$PACK" && find . -type f ! -name .DS_Store) | while read -r f; do [ -e "$REPO/$f" ] && echo "plinth already has: $f"; done
   cp -Rn "$PACK/." "$REPO/"
   rm -f "$REPO/GRILL-NOTES.md"   # interview notes: read them from $PACK/GRILL-NOTES.md, never commit them
   ```

3. Merge every file the loop printed (keep plinth's scaffolding, add ours; never delete plinth's sections):
   - plinth may already have: `README.md`, `CONTEXT.md`, `AGENTS.md` (`CLAUDE.md` links to it), `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, `NOTICE`, `SECURITY.md`, `.gitignore`, `.github/`, `docs/agents/`, `docs/adr/`, other `docs/` folders.
   - `README.md`: put the pack's text (title, motto, sections up to Documentation) first; keep plinth's sections (first day, build and test commands, badges) below. Same for `README.ko.md` if plinth made one.
   - `CONTEXT.md`: put the pack's glossary in; keep any plinth heading or note about how the file is maintained.
   - `docs/adr/`: keep plinth's ADR files. If one uses a number from 0001 to 0040, renumber it after 0040 with `git mv`. T0.1 checks `ls docs/adr | wc -l` = 40, so adjust that count to match in the T0.1 PR.
   - `AGENTS.md`: add two lines: "The spec `docs/spec/engine-spec-v3.4.md` is the single source of truth; do not invent rules it does not have (use chapter 12 defaults, else stop and ask)" and the public rule below.
4. Create a git-ignored `.hygiene-private.txt` on the user's machine only, listing private words (account, hosts, producer name, data paths). T0.2b's hygiene test reads it. Never commit it.
5. Run `python3 tools/spec_lint.py`. It should print PASS with the numbers below. Open the PR; this is most of ticket T0.1.

### (b) `/grill-with-docs`

Use the interview notes at `$PACK/GRILL-NOTES.md` (the local hand-off pack folder; not committed, do not copy them into the repository) as the question list and [CONTEXT.md](CONTEXT.md) as the glossary. The notes say what to ask: unverified market-rule seeds (A1–A9), calendar and data interpretation (B1–B4), engine estimates (C1–C5). Settle answers into `CONTEXT.md`, ADRs or a spec PR. Do not reopen the decisions listed below.

### (c) `/to-spec`

Make **one plan issue** that points at spec sections. Do not rewrite the spec. Include the milestone table and end conditions (spec 10.0), the build order (spec 9), and links to the spec, `SPEC-INDEX.md` and the ADRs.

### (d) `/to-tickets`

Cut issues from [SPEC-INDEX.md](SPEC-INDEX.md): 219 tickets in milestone order (M0 → M6, then v1.x). Each issue body is the ticket text from spec 10.1, copied as written: title, size, Done means, Acceptance, Blocked by, § sections. The issue's own title is a plain sentence of what the ticket does, not the ticket's commit-style title (`T6.16 ci(release): …`); the ticket id and that title go under the body's `## Parent`. Golden tickets (`T<m>.G…`) come before the tickets that use them. Replace `Blocked by` ticket ids with issue numbers as you go, and keep the id → issue map in the plan issue.

### (e) `/implement #N`

One ticket per session (`/clear` between). Write tests first: the ticket's acceptance test names are the red tests. Golden cases come from spec 8.2 (`G-NN`, `tests/golden/`), property tests from 8.3, point-in-time cases from 8.4. Open only the § sections the ticket lists. If the spec is wrong or silent, stop and propose a spec PR. Do not decide it in code.

## Decisions not to re-litigate

From the spec header ("사용자 결정" blocks, 2026-10-27/28):
- Name NexusBT: distribution `nexusbt`, `import nexusbt as nx`, `nexusbt.toml`, CLI `nexusbt`, env `NEXUSBT_*`; checker `nexusbt-tds` / `nexusbt_tds` / CLI `tds`.
- One key name `instrument_id`, with no `security_id` alias. Other names are renamed only at import (`rename=`, `mapping.yaml`).
- Public docs (TDS, README, quickstart, error messages, CONTEXT) are English canonical plus a Korean translation. Amended 2026-10-31 (spec OI-45): the spec too. Until its English text is complete, the Korean spec stays canonical; the English text grows in `docs/spec/engine-spec-v3.4.en.md` and takes over the spec's path in one last step.
- v1 is built on synthetic data. It is released after it passes KR/US real-data verification. PyPI name reserved; publish at v1.
- zipline parity covers presets only (ADR-0021). The hold band is the last M6 ticket (T7.1).
- Shorting is in v1, off by default. It uses signed symmetry; with `enabled = false` the result is bit-identical to long-only (P-SHORT-OFF). Borrow costs are user config. There is no borrow-availability data. KR short bans come from the market rules pack.
- The producer has no export layer: its snapshot folder is a TDS package, and the engine connects by path only.
- Cash interest is `[account] cash_rate_bps` (default 0). A sleeve whose equity hits ≤ 0 is marked `ruined`. Cash accounts have no forced liquidation (margin accounts: spec 5.6.7a).
- Snapshot reuse clones first, falls back to hardlinks, checks file identity, and keeps published files read-only.
- Python + numpy/Numba with a Rust-replaceable seam. Rust only if measurements show Numba misses the budget.
- Defaults: pins `index+root`. No long margin loan in a cash account (130/30 → E16). Tie-break salt `sha256("nexusbt-tiebreak-v1" ‖ instrument_id)`. Borrow accrues by calendar days/`day_count`. Three exit-value bases. KR rounding `down`.
- Share-changing corporate actions need exact integer ratios (TDS A010 = error). No f64 fraction inference; `decimal_ratio = "literal"` is opt-in.
- `size.kelly` is v1.x. ML training inside every validation method is forward-only.
- CPCV, walk-forward, CSCV/PBO, DSR are in v1 through one entry point `backtest(method=…)`; there is no `nx.validate`. The minimal `nx.ml.factor` block is in v1, and no pickle is used.
- Economic-event investing uses the same blocks: `Macro.series`, `Events.<kind>`, `nx.on_event`, `from_parquet(shape=)`.
- Engine, spec and TDS are public. Only the producer's data is private (2026-10-27).

ADRs (all accepted; full text in [docs/adr/](docs/adr/)):
0001 keep zipline Pipeline vocabulary, new executor · 0002 read TDS directly, `instrument_id` · 0003 cumulative-factor adjustment + reference impl · 0004 producer resolves fundamentals · 0005 one availability rule `decision_ts`, sleeves · 0006 daily state machine and order types in v1 · 0007 P&L from raw prices and explicit events · 0008 costs are cash debits, provisional bp · 0009 float64 only · 0010 no future lock: segments, attempt records, DSR · 0011 zipline-reloaded 3.2.1 only as isolated parity reference · 0012 run records sealed, source captured, hashes, SQLite index · 0013 microcaps included · 0014 benchmarks TR KOSPI and S&P 500 · 0015 missing pay dates estimated and flagged · 0016 Python/numpy/Numba behind a Rust seam · 0017 event engine only as a boundary, no `engine="auto"` · 0018 input contract is public TDS v1, checker versioned separately · 0019 numerical determinism · 0020 risk stage slot and hold-band recursion · 0021 zipline parity narrowed to equal semantics · 0022 public repo, Apache-2.0, data outside · 0023 no pickle, secrets outside config · 0024 defined fallbacks · 0025 three cache layers · 0026 events are the source of truth · 0027 one corporate-action resolver · 0028 three hashes · 0029 market names from data, rules from packs · 0030 integer minor-unit money · 0031 order lifecycle · 0032 paper-ledger transactions and idempotency · 0033 default label = economic holding return · 0034 integer share arithmetic · 0035 price grid and rounding from packs · 0036 signed long-short symmetry, off by default · 0037 snapshot immutability · 0038 sizing, risk slots and account-reading layer · 0039 validation is `backtest(method=…)`, ML factors in-engine · 0040 processes in v1, free-threading later.

## Public / private rule

- **Public (Apache-2.0):** engine code, the spec, TDS (format, schemas, checker), docs, tests.
- **Private, never in this repository:** the producer's data, snapshots and any part of them; fixtures made from vendor data; producer paths, host names, IP addresses, account names, the producer's name, producer-internal ticket ids. All test data comes from the synthetic generator (spec 4.8). Real-data evidence holds summary numbers only (spec 2.7). The hygiene tests (T0.2b) enforce this.

## Numbers (computed by script from the spec, 2026-10-29)

219 tickets (M0 16, M1 40, M2 30, M3a 37, M3b 11, M4 28, M5 24, M6 31, v1.x 2) · 107 golden cases (G-01..G-107) · 34 property tests · 49 error codes (E1..E49) · 40 ADRs · 950 named acceptance tests · 177 headings. Recompute tickets, goldens and property tests with `python3 tools/spec_lint.py`; error codes and ADRs are the rows of the tables in spec 6.6 and 9.3.

## Where the evidence is

[docs/design/prototype-results.md](docs/design/prototype-results.md): on the M4 16 GB machine, P5 ran in 5.8 s p50 / 6.8 s p95 cold against a 30 s gate and 10 s target. P11 (a)/(b)/(c) ran 5× under budget. Accounting hand cases passed 32/32. Computing only the decision rows gave bit-identical values to computing all rows. Output hashes matched on two machines. Spec chapter 7 cites it as [R4H-05]~[R4H-08].

## Notes for the first sessions

- Bracketed citations such as `review/…`, `teardown/…`, `sources/…`, `STORY.md` point to design-history files outside this repository. They explain why a rule exists; the rule itself is fully stated in the spec.
- The spec mentions plinth 2.7.1; use the installed plinth. GRILL-NOTES item C5 (public flag name) is answered: GitHub repos are public unless `--private`.
- Spec [R6-11]: the grill notes stay out of the repository. Read them from `$PACK/GRILL-NOTES.md` during `/grill-with-docs` and record answers in `CONTEXT.md`, ADRs or a spec PR.
