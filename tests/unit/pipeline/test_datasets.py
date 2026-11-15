"""Spec 3.2, 2.5: the datasets' columns, E7 for a wrong name, the schema registry at binding."""

from __future__ import annotations

from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt import Label, Meta, Panel, Price
from nexusbt.cli.main import main as nexusbt_main
from nexusbt.contracts import SchemaRegistry
from nexusbt.pipeline import BoundColumn, bind, stub_source

ODD = ("class", "1m", "_x", "Filter")  # column names a stub cannot list
TYPO = "clsoe"  # by `getattr`: the stubs make `Price.clsoe` a type error too
#: 3.2, the `Price` table, in its order.
PRICE = "open high low close close_tr close_unadjusted volume volume_unadjusted value_traded"
PRICE += " shares_out market_cap"


def test_price_columns_fixed() -> None:
    assert dir(Price) == sorted(PRICE.split())  # what a console completes after `Price.`
    for name in PRICE.split():
        assert getattr(Price, name) == BoundColumn.of("Price", name)
    assert type(Price.close.latest) is nx.Factor
    for name in ("mine", "close"):  # fixed: not a namespace to add to or change
        with pytest.raises(AttributeError):
            setattr(Price, name, Price.open)


def test_typo_suggestions() -> None:
    with pytest.raises(nx.ColumnNameError) as wrong:
        getattr(Price, TYPO)
    text = str(wrong.value)
    assert text.startswith("ColumnNameError [E7] in test_datasets.py:")
    assert " Price.clsoe\n" in text
    assert "Price has no column 'clsoe'. Did you mean: close, close_tr?" in text  # cutoff 0.6
    assert "layer  your code — test_datasets.py:" in text
    with pytest.raises(AttributeError, match=r"Price has no column 'zzz'\.\n"):  # none is close
        getattr(Price, TYPO[:0] + "zzz")
    assert not hasattr(Price, "clsoe")


def test_meta_aliases() -> None:
    assert Meta.country == Meta.market
    assert Meta.exchange == Meta.venue_mic
    assert Meta.market != Meta.venue_mic
    assert type(Meta.market) is nx.Classifier
    assert type(Meta.is_financial) is nx.Filter
    assert type(Meta.sector.eq("10")) is nx.Filter
    assert {"country", "exchange", "market"} <= set(dir(Meta))
    with pytest.raises(nx.ColumnNameError, match=r"'contry'\. Did you mean: country\?"):
        getattr(Meta, TYPO[:0] + "contry")


@pytest.mark.parametrize("name", ["delisted_on", "last_session", "name"])
def test_meta_has_no_hindsight_columns(name: str) -> None:
    """INV-01: what is known only after the fact is not a `Meta` column (3.2, RV-C08)."""
    with pytest.raises(nx.ColumnNameError, match=f"instruments.{name} is known only after"):
        getattr(Meta, name)
    assert name not in dir(Meta)


#: A snapshot with the 4.8 panels: `ret_fwd_1m_dl` is a label, also where a producer put one
#: into the feature panel.
KEYS = [("instrument_id", "id"), ("period", "date"), ("as_of_date", "date")]
MARKED = frozenset({"ret_fwd_1m_dl"})
REGISTRY = SchemaRegistry(
    columns={
        "factor_pit_monthly": (*KEYS, ("ts_available", "ts_us"), ("bm", "f64"),
                               ("mom_12_1", "f64"), ("ret_fwd_1m_dl", "f64")),
        "label_monthly": (*KEYS, ("entry_date", "date"), ("ret_fwd_1m_dl", "f64")),
    },
    labels={"factor_pit_monthly": MARKED, "label_monthly": MARKED},
)  # fmt: skip


def test_is_label_columns_only_in_Label() -> None:  # noqa: N802 - the spec's name (10.1 T1.6)
    bind(Label.ret_fwd_1m_dl, REGISTRY)
    only_label_marked = SchemaRegistry(REGISTRY.columns, {"label_monthly": MARKED})
    for registry in (REGISTRY, only_label_marked):  # 8.4: a label read like a `Panel` is E2
        with pytest.raises(nx.LabelLeakError, match=r"Panel\.ret_fwd_1m_dl is a label"):
            bind(Panel.ret_fwd_1m_dl.latest, registry)
    for not_a_label in ("entry_date", "bm"):
        with pytest.raises(nx.ColumnNameError, match=f"Label has no column '{not_a_label}'"):
            bind(getattr(Label, not_a_label), REGISTRY)


def test_schema_registry_injected_at_binding() -> None:
    """2.5: `pipeline` reads no data, so a snapshot's columns are checked when the graph meets
    the registry, wherever the column sits in it."""
    graph = Panel.bm.latest.rank(mask=Panel.mom_12_1.latest > 0) + Price.close.latest
    bind(graph, REGISTRY)
    bind(nx.Pipeline({"value": graph}, screen=Panel.bm.latest > 0), REGISTRY)
    typo = Panel.bmm.latest  # not known where it is written
    for wrong in (typo, graph.rank(mask=typo > 0), nx.Pipeline({"x": graph}, screen=typo > 0)):
        with pytest.raises(nx.ColumnNameError, match=r"'bmm'\. Did you mean: bm\?\n"):
            bind(wrong, REGISTRY)
    with pytest.raises(nx.ColumnNameError, match="Panel has no column 'period'"):  # a key
        bind(Panel.period, REGISTRY)
    deep = Panel.bmm.latest
    for _ in range(3000):  # deeper than the call stack
        deep = deep + 1
    with pytest.raises(nx.ColumnNameError):
        bind(deep, REGISTRY)
    other = SchemaRegistry({"value_m": (("bmm", "f64"),)}, {}, feature="value_m")
    bind(typo, other)  # `[panels] feature` names the dataset
    with pytest.raises(nx.ColumnNameError, match="Panel has no column 'bm'"):
        bind(Panel.bm.latest, SchemaRegistry({}, {}))  # a snapshot without panels


def test_stub_file_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """3.2: `nexusbt stubs` writes the datasets' columns where the editor reads them."""
    fixed = stub_source()
    for line in (
        "class Price:\n    open: BoundColumn",
        "market_cap: BoundColumn",
        "class Meta:\n",
        "    market: Classifier\n",
        "    is_financial: Filter\n",
        "    country: Classifier\n",
        "class Label(metaclass=_Snapshot): ...\n",
    ):
        assert line in fixed
    assert "delisted_on" not in fixed
    bound = stub_source(SchemaRegistry(
        {**REGISTRY.columns, "label_monthly": (*((c, "f64") for c in ("ret_fwd_1m_dl", *ODD)),)},
        {"label_monthly": frozenset({"ret_fwd_1m_dl", *ODD})}))  # fmt: skip
    assert "class Panel(metaclass=_Snapshot):\n    bm: BoundColumn\n    mom_12_1: Bound" in bound
    # a label is a `Label` column only; a name Python cannot write after a dot is left out
    assert bound.endswith("class Label(metaclass=_Snapshot):\n    ret_fwd_1m_dl: BoundColumn\n")
    stub = Path(nx.__file__).parent / "_stubs" / "datasets.pyi"
    assert stub.read_text(encoding="utf-8") == fixed  # the committed file: no snapshot
    monkeypatch.chdir(tmp_path)  # no nexusbt.toml: no snapshot to read
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    assert nexusbt_main(["stubs"]) == 0
    assert capsys.readouterr().out.strip() == str(stub)
    assert stub.read_text(encoding="utf-8") == fixed
