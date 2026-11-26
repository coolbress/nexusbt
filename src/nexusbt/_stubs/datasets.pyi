# Written by `nexusbt stubs` from the snapshot's dictionary (spec 3.2); not edited by hand.
from nexusbt.pipeline._terms import BoundColumn, Classifier

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

class Meta:
    market: Classifier
    currency: Classifier
    asset_class: Classifier
    venue_mic: Classifier
    category: Classifier
    country: Classifier
    exchange: Classifier
