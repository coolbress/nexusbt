"""ID constant, column sets, units, policies, errors, shared frame and context types; no deps.

The 2.4 shared types, declared empty, and the 6.6 error classes. `ID_COLUMN`,
`ENGINE_COLUMNS`, `Unit`, `Currency`, `Phase` and the schema version constants
are T0.3's (#48); the 26 policy enums are the ones 2.4 names (#68); the
E1~E39 messages are T0.4's (#49), the `layer` lines and E40~E49 T0.4b's.
"""

# The 6.6 class names are the spec's: warnings and notices do not end in `Error`.
# ruff: noqa: N818

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import ClassVar, Literal, NewType, Protocol, Self

#: The instrument key, in data, internals, outputs, the API and documents alike (spec header
#: "Identifier name"). The only place in code that spells it; there is no alias.
ID_COLUMN = "instrument_id"

#: Versions of the artifacts a run writes (spec 2.4).
RUN_SCHEMA = "nexusbt-run/2"
EVENTS_SCHEMA = "nexusbt-events/1"
CHECKPOINT_SCHEMA = "nexusbt-checkpoint/1"

#: An ISO 4217 alpha-3 code, or one the snapshot manifest declares under `currencies` (TDS 3.4).
#: An open set, so a string type rather than an enum.
Currency = NewType("Currency", str)


class Unit(StrEnum):
    """The unit vocabulary of TDS 3.4. Ratios are `ratio` (1 = 100%); there is no `pct`."""

    CCY = "ccy"
    LCY = "LCY"
    SHARES = "shares"
    CONTRACTS = "contracts"
    RATIO = "ratio"
    BP = "bp"
    COUNT = "count"
    DAYS = "days"
    INDEX_POINTS = "index_points"
    PRICE = "price"
    NONE = "none"


#: Dataset → the columns the engine must read from it (spec 4.6), names only; their types are TDS
#: chapter 5's, checked when a snapshot is opened. "every column" rows hold the whole TDS table;
#: the panels hold only their fixed columns, as the producer names the feature and label ones.
#: A column a 4.6 row marks "+ optional" (the `ts_label_*` of `label_panels`) is not here.
#: Each list is in the spec's order, space-separated, with `ID_COLUMN` for the key's name.
ENGINE_COLUMNS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        dataset: frozenset(names.split())
        for dataset, names in {
            "instruments": f"{ID_COLUMN} asset_class category market venue_mic calendar_id"
            " currency issuer_id name listed_on listed_on_censored last_session delisted_on"
            " lot_size multiplier is_synthetic index_kind",
            "instrument_symbols": f"{ID_COLUMN} symbol_type symbol venue_mic valid_from valid_to"
            " ts_known_from ts_known_to",
            "calendar_sessions": "calendar_id session_date ts_open ts_close is_half_day",
            "bars": f"{ID_COLUMN} session_date open high low close volume value_traded obs_status"
            " cum_factor_split cum_factor_total",
            "tradability_daily": f"{ID_COLUMN} session_date status_known halted_full_day"
            " limit_up_close limit_down_close locked_up locked_down price_limit_ratio"
            " up_limit_price down_limit_price reference_price admin_status",
            # every column, TDS 5.11
            "corporate_actions": f"event_id {ID_COLUMN} kind ex_date ts_effective record_date"
            " declared_date pay_date pay_date_status resolution_date ts_announced"
            " ts_terms_available ratio_num ratio_den ratio_new_per_old new_instrument_id"
            " cash_per_share currency gross_or_net subscription_price price_factor share_factor"
            " affects factor_method factor_ref_price revision_of status source evidence_id",
            # every column, TDS 5.13
            "delistings": f"delisting_id {ID_COLUMN} last_trading_date exit_date ts_exit_known"
            " delist_type crsp_dlstcd_equiv ref_date ref_price exit_value_status ret_observed"
            " ret_observed_includes_distributions ts_value_available ret_policy ret_lo ret_hi"
            " policy_id pay_date handled_by_event_id reason_code evidence_id",
            "share_counts": f"{ID_COLUMN} count_kind as_of_date shares ts_available",
            "market_rules": "rule_id market rule_kind venue_group valid_from valid_to price_from"
            " price_to tick_size limit_ratio source verified",
            "fx_rates": "base quote rate_kind obs_date ts_event ts_available rate source",
            # every column, TDS 5.18
            "fundamentals_state": f"{ID_COLUMN} item ts_known_from ts_known_to period_end"
            " period_kind statement_basis value unit currency scale strict_eligible vendor_input"
            " selected_fact_id lineage_id resolution_policy",
            "fundamentals_events": f"fact_id {ID_COLUMN} item period_end statement_basis version"
            " value known_on ts_available source source_rank doc_id value_how vendor_input",
            "classifications": f"{ID_COLUMN} scheme level code label effective_from effective_to"
            " ts_known_from ts_known_to edition pit_quality",
            "eligibility_daily": f"rule_id {ID_COLUMN} session_date is_eligible reason",
            "universe_membership": f"universe_id {ID_COLUMN} effective_from effective_to"
            " ts_known_from ts_known_to",
            "feature_panels": f"{ID_COLUMN} period as_of_date ts_available",
            "label_panels": f"{ID_COLUMN} period entry_date entry_price_basis exit_date horizon"
            " return_definition terminal_policy_id",
        }.items()
    }
)


class Phase(IntEnum):
    """The processing phases at one UTC instant, in the order of spec 5.6.3.

    Members compare in that order, so a `(ts, phase, sleeve)` key sorts the event queue.
    """

    SESSION_START = 0
    OPEN = 1
    INTRADAY = 2
    CLOSE_FILL = 3
    CLOSE_MARK = 4
    DECISION = 5
    SESSION_END = 6


# The policy enums of spec 2.4: one per 3.11 key with two or more closed choices. Values are
# the choice strings of that key's Validation cell; member names follow `Unit`'s rule.


class DelistingPolicy(StrEnum):
    """`[delisting] policy` (5.6.13)."""

    OBSERVED_THEN_POLICY = "observed_then_policy"
    OBSERVED_ONLY = "observed_only"
    LO = "lo"
    HI = "hi"


class RightsPolicy(StrEnum):
    """`[corporate_actions] rights` (5.6.12)."""

    LAPSE = "lapse"
    FAIL = "fail"


class UnsupportedPolicy(StrEnum):
    """`[corporate_actions] unsupported` (5.6.12)."""

    FAIL = "fail"
    CASH_AT_ADJUSTMENT = "cash_at_adjustment"


class DecimalRatioPolicy(StrEnum):
    """`[corporate_actions] decimal_ratio` (5.6.1, 5.6.10)."""

    EXCLUDE_INSTRUMENT = "exclude_instrument"
    REQUIRE_EXACT = "require_exact"
    LITERAL = "literal"


class MissingPayDatePolicy(StrEnum):
    """`[dividends] missing_pay_date` (5.6.11)."""

    ESTIMATE = "estimate"
    FAIL = "fail"


class BonusSharesTradablePolicy(StrEnum):
    """`[corporate_actions] bonus_shares_tradable` (5.6.10)."""

    AT_EX = "at_ex"
    AT_PAY_DATE = "at_pay_date"


class UnknownInclusionPolicy(StrEnum):
    """`[delisting] unknown_inclusion` (5.6.13)."""

    CONSERVATIVE = "conservative"
    ERROR = "error"


class EditionPolicy(StrEnum):
    """`[data] edition` (5.3.5)."""

    STRICT = "strict"
    COMPARE = "compare"


class VerifyPolicy(StrEnum):
    """`[data] verify` (4.4)."""

    MANIFEST = "manifest"
    SCHEMA = "schema"
    FULL = "full"


class PinsPolicy(StrEnum):
    """`[data] pins` (4.2)."""

    INDEX = "index"
    INDEX_ROOT = "index+root"


class FallbacksPolicy(StrEnum):
    """`[data] fallbacks` (4.5)."""

    WARN = "warn"
    FAIL = "fail"


class TiebreakPolicy(StrEnum):
    """`[portfolio] tiebreak` (3.7, 5.4.2)."""

    HASH = "hash"
    ID = "id"


class BandEntriesPolicy(StrEnum):
    """`[portfolio] band_entries` (5.5.3, 5.6.7)."""

    SKIP = "skip"
    BUY = "buy"


class AccountTypePolicy(StrEnum):
    """`[account] type` (5.6.7a)."""

    CASH = "cash"
    MARGIN = "margin"


class OrderTypePolicy(StrEnum):
    """`[execution] order` (3.7)."""

    MARKET = "market"
    LIMIT = "limit"


class ExecutionAtPolicy(StrEnum):
    """`[execution] at` (3.7)."""

    OPEN = "open"
    CLOSE = "close"


class BandModePolicy(StrEnum):
    """`[execution] band_mode` (5.6.7)."""

    EDGE = "edge"
    TARGET = "target"


class LimitFillPolicy(StrEnum):
    """`[execution] limit_fill` (5.6.4)."""

    THROUGH = "through"
    TOUCH = "touch"


class UnknownTradabilityPolicy(StrEnum):
    """`[execution] unknown_tradability` (5.6.5)."""

    ASSUME_TRADABLE = "assume_tradable"
    BLOCK = "block"


class CostProfilePolicy(StrEnum):
    """`[costs] profile` (5.6.8)."""

    PROVISIONAL = "provisional"
    REALISTIC = "realistic"
    NONE = "none"


class TaxesProfilePolicy(StrEnum):
    """`[taxes] profile` (5.6.11a)."""

    NONE = "none"
    CUSTOM = "custom"


class TaxesPayPolicy(StrEnum):
    """`[taxes] pay` (5.6.11a)."""

    REPORT = "report"
    CASH = "cash"


class TaxesBasisPolicy(StrEnum):
    """`[taxes.groups.<name>] basis` (5.6.11a)."""

    AVERAGE = "average"
    FIFO = "fifo"


class LabelEntryPolicy(StrEnum):
    """`[evaluate] label_entry` (5.8)."""

    NEXT_OPEN = "next_open"
    CLOSE = "close"


class EvaluateTargetPolicy(StrEnum):
    """`[evaluate] target` (5.8)."""

    FWD_RETURN = "fwd_return"
    FWD_RETURN_ADJ = "fwd_return_adj"


class RoundingModePolicy(StrEnum):
    """`[rounding.<MARKET>] mode` (5.6.1)."""

    HALF_UP = "half_up"
    HALF_EVEN = "half_even"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class FactorFrame: ...


@dataclass(frozen=True, slots=True)
class TargetFrame: ...


@dataclass(frozen=True, slots=True)
class TargetState: ...


@dataclass(frozen=True, slots=True)
class DecisionGrid: ...


@dataclass(frozen=True, slots=True)
class DecisionContext: ...


@dataclass(frozen=True, slots=True)
class DecisionInputs: ...


@dataclass(frozen=True, slots=True)
class SchemaRegistry: ...


@dataclass(frozen=True, slots=True)
class ResolvedActions: ...


@dataclass(frozen=True, slots=True)
class SessionInputs: ...


@dataclass(frozen=True, slots=True)
class MarketView: ...


class EventSink(Protocol): ...


#: 6.6 blocking principle: (a) `block`, (b) `fail`; (c) `warning` and `notice` do not stop a run.
_Kind = Literal["block", "fail", "warning", "notice"]


class NexusBTError(Exception):
    """The root of the 6.6 errors, warnings and notices; its text is the five-part shape.

    ```
    {ClassName} [{code}] in {user_file}:{line} {term_or_object}
      what   ...
      where  ...
      why    ...
      fix    ...
      more   ...
    ```

    `kinds` is the 6.6 Kind column, the default first: only E20 has two (fail when funding,
    warning for `.to`). The `layer` line is T0.4b's.
    """

    code: ClassVar[str] = ""
    kinds: ClassVar[tuple[_Kind, ...]] = ("fail",)

    def __init_subclass__(cls, code: str = "", kinds: tuple[_Kind, ...] = ("fail",)) -> None:
        super().__init_subclass__()
        cls.code, cls.kinds = code, kinds

    def __init__(
        self,
        *,
        what: str,
        where: str,
        why: str,
        fix: str,
        more: str,
        at: str | None = None,
        subject: str | None = None,
        kind: _Kind | None = None,
    ) -> None:
        parts = {"what": what, "where": where, "why": why, "fix": fix, "more": more}
        if empty := [name for name, text in parts.items() if not text.strip()]:
            raise ValueError(f"{type(self).__name__}: empty message part(s) {empty}")
        if kind is not None and kind not in self.kinds:
            raise ValueError(f"{type(self).__name__} is {self.kinds}, not {kind!r}")
        self.kind: _Kind = kind or self.kinds[0]
        self.parts, self.at, self.subject = parts, at, subject
        header = f"{type(self).__name__} [{self.code}]"
        header += f" in {at}" if at else ""
        header += f" {subject}" if subject else ""
        lines = [header] + [
            f"  {name:<6} " + text.replace("\n", "\n" + " " * 9) for name, text in parts.items()
        ]
        super().__init__("\n".join(lines))

    @classmethod
    def example(cls) -> Self:
        """An instance with the 6.6 table's sample sentences, for documents and tests."""
        at, subject, what, where, why, fix, more = _EXAMPLES[cls.code]
        return cls(
            what=what, where=where, why=why, fix=fix, more=more, at=at or None, subject=subject
        )


# 6.6, in code order; kept as a table.
# fmt: off
class LookAheadError(NexusBTError, code="E1", kinds=("block",)): ...
class LabelLeakError(NexusBTError, code="E2", kinds=("block",)): ...
class PointInTimeError(NexusBTError, code="E3", kinds=("block",)): ...
class SurvivorshipWarning(NexusBTError, code="E4", kinds=("warning",)): ...
class UnitError(NexusBTError, code="E5"): ...
class CoverageWarning(NexusBTError, code="E6", kinds=("warning",)): ...
class ColumnNameError(NexusBTError, AttributeError, code="E7"): ...
class WindowError(NexusBTError, code="E8"): ...
class SessionNotice(NexusBTError, code="E9", kinds=("notice",)): ...
class SegmentNotice(NexusBTError, code="E10", kinds=("notice",)): ...
class FillWarning(NexusBTError, code="E11", kinds=("warning",)): ...
class UnsupportedCorporateActionError(NexusBTError, code="E12"): ...
class AccountingDataError(NexusBTError, code="E13"): ...
# E14 `SnapshotError` is below the table: it carries `from_check`.
class ReplayError(NexusBTError, code="E15"): ...
class ConfigError(NexusBTError, code="E16"): ...
class TermDomainError(NexusBTError, code="E17"): ...
class CapabilityError(NexusBTError, code="E18"): ...
class DataAvailabilityError(NexusBTError, code="E19"): ...
class FxStaleError(NexusBTError, code="E20", kinds=("fail", "warning")): ...
class StatisticUnavailable(NexusBTError, code="E21", kinds=("notice",)): ...
class ProvisionalCostWarning(NexusBTError, code="E22", kinds=("warning",)): ...
class CostTableError(NexusBTError, code="E23"): ...
class ImpureFunctionWarning(NexusBTError, code="E24", kinds=("warning",)): ...
class StaleMarkWarning(NexusBTError, code="E25", kinds=("warning",)): ...
class IdempotencyNotice(NexusBTError, code="E26", kinds=("notice",)): ...
class TradabilityUnknownWarning(NexusBTError, code="E27", kinds=("warning",)): ...
class PayDateEstimatedWarning(NexusBTError, code="E28", kinds=("warning",)): ...
class FitLeakError(NexusBTError, code="E29", kinds=("block",)): ...
class DataProfileWarning(NexusBTError, code="E30", kinds=("warning",)): ...
class UntrustedRunError(NexusBTError, code="E31"): ...
class StartDependenceWarning(NexusBTError, code="E32", kinds=("warning",)): ...
class ReconcileMismatch(NexusBTError, code="E33", kinds=("notice",)): ...
class UnmaskedCrossSectionNotice(NexusBTError, code="E34", kinds=("notice",)): ...
class BookConflictError(NexusBTError, code="E35"): ...
class OrderSanityWarning(NexusBTError, code="E36", kinds=("warning",)): ...
class LotRoundingWarning(NexusBTError, code="E37", kinds=("warning",)): ...
class CollateralWarning(NexusBTError, code="E38", kinds=("warning",)): ...
class UnknownFilterNotice(NexusBTError, code="E39", kinds=("notice",)): ...
# E40~E49 are T0.4b's; their codes and sentences come with it.
class BlockOutputError(NexusBTError): ...  # E41
class EngineBugError(NexusBTError): ...  # E46
class DatasetShapeError(NexusBTError): ...  # E47
class PretrainedLeakError(NexusBTError): ...  # E48
# fmt: on


class SnapshotError(NexusBTError, code="E14"):
    @classmethod
    def from_check(
        cls,
        *,
        path: str,
        counts: Mapping[str, int],
        dataset: str,
        file: str,
        key: str,
        hint: str,
        producer_hints: Mapping[str, str] | None = None,
    ) -> SnapshotError:
        """E14 from a failed check: `counts` is TDS code → errors, the first error's code first.

        `dataset`, `file`, `key` and `hint` are the first error's (TDS 11); `producer_hints` is
        `tds.json` `producer.hints`, and only its sentence for that first code is shown.
        """
        if not counts:
            raise ValueError("SnapshotError.from_check needs at least one TDS error code")
        first = next(iter(counts))
        sentence = (producer_hints or {}).get(first)
        return cls(
            what=f"snapshot check failed: {first} {hint}",
            where=f"dataset {dataset}, file {file}, key {key}",
            why="errors per code: " + ", ".join(f"{c} ({n})" for c, n in counts.items()),
            fix=(f"producer hint ({first}): {sentence}\n" if sentence else "")
            + f"tds check {path} --level full; nexusbt doctor --full",
            more="spec 4.4 (what opening a snapshot checks) and the TDS code table",
        )


#: Code → (at, subject, what, where, why, fix, more), from the 6.6 "Message core" column.
# fmt: off
_EXAMPLES: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "E1": ("strategy.py:8", "mom", "The value on 2020-03-02 changed when data after 2020-03-02 was removed", "term mom, instrument X1, 2020-03-02", "the term reads the future, so a backtest of it is not possible in real time", "use .shift(k) with k ≥ 1, nx.ops.rolling(...), or window style", "nx.explain(strategy, 'X1', '2020-03-02'); spec 6.5 truncation probe"),  # noqa: E501
    "E2": ("strategy.py:9", "Label.ret_1m", "Label.ret_1m is a forward-looking label", "the signal of Strategy 'value'", "a label is known only after the decision, so it cannot drive one", "remove it from the signal; test it with nx.evaluate(f, target=Label.ret_1m)", "spec 5.3.11 (label ports)"),  # noqa: E501
    "E3": ("strategy.py:4", "earnings", "dataset 'earnings' has no known_on column", "file data/earnings.parquet", "without the time a row became known, it could be read before it existed", "from_parquet(path, key=[...], known_on='published_at') or known_on='date' (recorded as an assumption)", "nx.describe(earnings)"),  # noqa: E501
    "E4": ("", "universe", "a fixed list of 40 securities is used from 2000-01-03 to 2024-12-30; 0 delisted included", "Strategy 'value', universe", "a list of names alive today hides the ones that failed", "nx.universe('KR') & ... .top(n) or index_members('KOSPI200'); keep with survivorship_ok='reason'", "spec 6.6 E4"),  # noqa: E501
    "E5": ("strategy.py:11", "market_cap", "market_cap is in local currency (KRW for KR, USD for US)", "rank across markets KR, US", "numbers in two currencies are not comparable", "remove across_markets=True, .to('USD'), or use a ratio", "nx.describe(Price.market_cap)"),  # noqa: E501
    "E6": ("", "screen", "the screen keeps 120 of 2400 names on 2020-03-02 (5%)", "NaN counts: Fund.roe 2100, Price.close 180", "most of the universe is missing, so results describe a few names", "accept (coverage table recorded), edition='compare', or start=...", "nx.check(strategy)"),  # noqa: E501
    "E7": ("strategy.py:12", "Fund.roa", "Fund has no column 'roa'. Did you mean: roe, roic?", "dataset Fund", "the column is not in this snapshot's dictionary", "nx.describe(Fund)", "spec 3.2 (dataset columns)"),  # noqa: E501
    "E8": ("strategy.py:14", "mom", "mom reads close[-253] but window=252", "factor mom, input close", "the row is outside the window the engine loads", "@nx.factor(window=253, ...)", "spec 3.3 and 5.3.7 (windows)"),  # noqa: E501
    "E9": ("", "start", "start 2020-01-01 is not a KR session; using 2020-01-02", "argument start", "runs begin on a session", "start='2020-01-02'", "spec 6.6 E9"),  # noqa: E501
    "E10": ("", "segment", "this run computes performance on segment 'test' (2020-01-02 → 2024-12-30); exposures in study: 3", "study 'value'", "each look at a held-out segment uses it up", "nx.preregister(...) before looking, if you want a recorded criterion", "spec 6.3a"),  # noqa: E501
    "E11": ("", "execution", "daily-bar fills for limit/stop orders are approximations", "[execution] order types", "the order of prices inside a day is not known", "see [execution] fill_model note; use at='open' market orders to avoid", "spec 5.6.4"),  # noqa: E501
    "E12": ("", "X1", "X1 has a spinoff on 2020-03-02 while held (100 shares)", "instrument X1, 2020-03-02", "the engine cannot tell what the holding becomes", "[corporate_actions] unsupported = 'cash_at_adjustment' (recorded), or exclude the security from the universe before 2020-03-02", "spec 5.6.12"),  # noqa: E501
    "E13": ("", "corporate_actions", "the snapshot lacks ratio_num/ratio_den for event 7", "table corporate_actions, key event_id=7, column ratio_num", "a decimal ratio cannot give exact share counts", "ask the producer for ratio_num/ratio_den, or use the default [corporate_actions] decimal_ratio = 'exclude_instrument', or 'literal' (recorded)", "spec 5.6.1"),  # noqa: E501
    "E14": ("", "","snapshot check failed: TDS-A001 cum_factor_split does not match corporate_actions", "dataset bars, file bars/year=2020/part-0.parquet, key instrument_id=X1", "errors per code: TDS-A001 (3)", "tds check snap --level full; nexusbt doctor --full", "spec 4.4 (what opening a snapshot checks) and the TDS code table"),  # noqa: E501
    "E15": ("", "run r1", "snapshot s1 is not available", "run r1", "a rerun needs the exact data it ran on", "nx.rerun(id, new_snapshot=True) creates a new run", "nx.runs()"),  # noqa: E501
    "E16": ("", "", "[costs] profle = 'realistic' is not a key", "nexusbt.toml [costs] profle", "unknown keys would be silently ignored", "did you mean: profile?", "nx.config()"),  # noqa: E501
    "E17": ("strategy.py:15", "rel_mom", "rel_mom is a cross-market term and cannot feed a window", "term rel_mom", "a window over a cross-market value mixes calendars", "compute the window per market, then compare across markets", "spec 3.3 (terms)"),  # noqa: E501
    "E18": ("", "", "engine='event' is not available in v1", "argument engine", "the feature is outside v1", "use the default engine", "spec 6.6 E18 (features outside v1)"),  # noqa: E501
    "E19": ("", "", "the execution session 2020-03-03 for KR is not in snapshot s1 (complete through 2020-03-02)", "market KR, snapshot s1", "orders for a session the data has not reached would guess prices", "run again after the next data refresh", "nexusbt doctor"),  # noqa: E501
    "E20": ("", "USDKRW", "latest USDKRW available at 2020-03-02 is 9 days old", "fx_rates USDKRW", "a stale rate misstates the cash needed", "[fx] max_stale_days_decision = 9 (recorded) or use a snapshot with newer fx_rates", "spec 5.1.5 and 3.11 [fx]"),  # noqa: E501
    "E21": ("", "DSR", "DSR n/a (12 sessions)", "series returns of run r1 (T = 12, needs 30)", "the statistic needs more observations", "run longer than 30 sessions or add candidates to the study", "spec 6.3"),  # noqa: E501
    "E22": ("", "costs", "costs are provisional fixed bps (KR buy 5/sell 25, US 5/5)", "[costs] profile", "real costs depend on a verified table", "[costs] profile='realistic' after the cost table is verified", "spec 5.6.8"),  # noqa: E501
    "E23": ("", "costs", "the cost table has no rows for (KR, 2001, sell, tax)", "costs/*.csv", "realistic costs need every component", "use provisional, or add verified rows to costs/*.csv", "spec 5.6.8"),  # noqa: E501
    "E24": ("strategy.py:20", "my_score", "my_score reads global 'weights'; the engine cannot check what it contains", "function my_score", "a hidden input breaks reruns and checks", "pass weights as nx.param(...)", "spec 3.7"),  # noqa: E501
    "E25": ("", "X1", "X1 is valued at a price 25 sessions old", "instrument X1, 2020-02-01 → 2020-03-02", "the mark may be far from a tradable price", "exclude X1 from the universe, or check trading_status for X1 with tds check (the mark is the last valid close, 5.6.3)", "spec 5.6.3"),  # noqa: E501
    "E26": ("", "book b1", "orders for decision d1 already exist in book b1 (state version 4); showing them", "book b1", "the same orders must not be sent twice", "nothing to do; the existing batch is shown, not sent again", "spec 5.9.6"),  # noqa: E501
    "E27": ("", "fills", "14 fills with unknown tradability", "2020-01-02 → 2020-12-30", "the security may not have been tradable", "[execution] unknown_tradability='block' to see the sensitivity", "spec 5.6.5"),  # noqa: E501
    "E28": ("", "dividends", "3 dividends used an estimated pay date", "corporate_actions, pay_date_status", "cash may arrive on another day", "[dividends] missing_pay_date = 'fail' to stop instead", "spec 5.6.11"),  # noqa: E501
    "E29": ("", "model", "model is fitted on 2019-01-02 → 2020-12-30 which overlaps test", "ml.factor model", "test labels would enter training", "set fit_segment='train' and embargo_sessions", "spec 6.3a"),  # noqa: E501
    "E30": ("", "F-08", "fallback F-08 used: market_cap is NaN without share_counts", "dataset share_counts, market KR, 2400 rows", "a fallback changes what a term means", "[data] fallbacks='fail' to stop instead", "spec 4.5"),  # noqa: E501
    "E31": ("", "run r1", "run r1 was created on another machine; its source/ will be executed", "run folder r1", "running code you did not read is unsafe", "nx.rerun(id, trust=True) after reading source/", "spec 5.9.3"),  # noqa: E501
    "E32": ("", "mom", "mom on 2020-03-02 changed when the run started 20 sessions earlier", "term mom", "the value depends on when the run began", "remove state carried across windows (globals, recursion)", "spec 6.5"),  # noqa: E501
    "E33": ("", "X1", "first difference on 2020-03-02 for X1 at stage fills: 100 vs 90", "book b1, 2020-03-02, X1, stage fills", "the book and the engine disagree", "check fills and cash flows; nexusbt reconcile --restate; if the snapshot is identical, nexusbt bugreport r1", "spec 5.9.7"),  # noqa: E501
    "E34": ("strategy.py:16", "score", "score ranks over all listed equities, not the strategy universe", "the signal of Strategy 'value'", "ranks then depend on names the strategy never holds", "pass mask=universe (or ignore if intended)", "spec 6.5 check 10"),  # noqa: E501
    "E35": ("", "book b1", "book b1 is locked by pid 4242", "book b1", "two writers would corrupt the book", "wait for pid 4242 or create a new book", "spec 5.9.6"),  # noqa: E501
    "E36": ("", "order o1", "order o1 for X1: price jump (0.42 vs limit 0.30)", "order o1, X1, 2020-03-02", "the data may be wrong", "check the data for 2020-03-02; the order is shown, not blocked", "spec 5.9.6"),  # noqa: E501
    "E37": ("", "rounding", "12 of 60 decisions leave >5% cash from share rounding (median 6%; 3 targets got 0 shares)", "Strategy 'value'", "the portfolio is not the one designed", "raise capital, lower n, or use max price filters", "spec 5.6.7"),  # noqa: E501
    "E38": ("", "shorting", "collateral short by 1000 USD on 4 sessions (max 2500)", "sleeve US", "new shorts and buys were blocked", "lower [shorting] max_gross or collateral_ratio; forced buy-ins are not modeled", "spec 5.6.7a"),  # noqa: E501
    "E39": ("", "listed", "60% of listed names are unknown for universe filter listed on 4 decisions (input NaN: market_cap)", "universe filter listed", "unknown is neither in nor out", "make the fallback explicit: (listed).fillna(True) or .fillna(False)", "spec 5.4.1"),  # noqa: E501
}
# fmt: on
