"""ID constant, column sets, units, policies, errors, shared frame and context types; no deps.

The 2.4 shared types, declared empty, and the 6.6 error classes. `ID_COLUMN`,
`ENGINE_COLUMNS`, `Unit`, `Currency`, `Phase`, `Policy*` and the schema version
constants are T0.3's (#48); the error messages and `layer` lines are T0.4's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import NewType, Protocol

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


#: Dataset → the columns the engine reads from it (spec 4.6), names only; their types are TDS
#: chapter 5's, checked when a snapshot is opened. "every column" rows hold the whole TDS table;
#: the panels hold only their fixed columns, as the producer names the feature and label ones.
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
            "tradability_daily": "status_known halted_full_day limit_up_close limit_down_close"
            " locked_up locked_down price_limit_ratio up_limit_price down_limit_price"
            " reference_price admin_status",
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


class NexusBTError(Exception):
    """The root of the 6.6 errors."""


# 6.6, the codes whose kind is block or fail, in code order; kept as a table.
# fmt: off
class LookAheadError(NexusBTError): ...  # E1
class LabelLeakError(NexusBTError): ...  # E2
class PointInTimeError(NexusBTError): ...  # E3
class UnitError(NexusBTError): ...  # E5
class ColumnNameError(NexusBTError, AttributeError): ...  # E7
class WindowError(NexusBTError): ...  # E8
class UnsupportedCorporateActionError(NexusBTError): ...  # E12
class AccountingDataError(NexusBTError): ...  # E13
class SnapshotError(NexusBTError): ...  # E14
class ReplayError(NexusBTError): ...  # E15
class ConfigError(NexusBTError): ...  # E16
class TermDomainError(NexusBTError): ...  # E17
class CapabilityError(NexusBTError): ...  # E18
class DataAvailabilityError(NexusBTError): ...  # E19
class FxStaleError(NexusBTError): ...  # E20
class CostTableError(NexusBTError): ...  # E23
class FitLeakError(NexusBTError): ...  # E29
class UntrustedRunError(NexusBTError): ...  # E31
class BookConflictError(NexusBTError): ...  # E35
class BlockOutputError(NexusBTError): ...  # E41
class EngineBugError(NexusBTError): ...  # E46
class DatasetShapeError(NexusBTError): ...  # E47
class PretrainedLeakError(NexusBTError): ...  # E48
# fmt: on
