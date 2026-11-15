# Written by `nexusbt stubs` from the snapshot's dictionary (spec 3.2); not edited by hand.
from nexusbt.pipeline._terms import BoundColumn, Classifier, Filter

class _Snapshot(type):  # another snapshot holds other columns: any name is one
    def __getattr__(cls, name: str) -> BoundColumn: ...

class Price:
    open: BoundColumn
    high: BoundColumn
    low: BoundColumn
    close: BoundColumn
    close_tr: BoundColumn
    close_unadjusted: BoundColumn
    volume: BoundColumn
    volume_unadjusted: BoundColumn
    value_traded: BoundColumn
    shares_out: BoundColumn
    market_cap: BoundColumn

class Meta:
    market: Classifier
    currency: Classifier
    asset_class: Classifier
    venue_mic: Classifier
    category: Classifier
    sector: Classifier
    industry: Classifier
    is_financial: Filter
    country: Classifier
    exchange: Classifier

class Panel(metaclass=_Snapshot): ...
class Label(metaclass=_Snapshot): ...
