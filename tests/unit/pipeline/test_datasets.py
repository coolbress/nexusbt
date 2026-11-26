"""Spec 3.2, 2.5: the datasets' columns, E7 for a wrong name, the schema registry at binding."""

from __future__ import annotations

from pathlib import Path

import pytest

import nexusbt as nx
from nexusbt import Meta, Price
from nexusbt.cli.main import main as nexusbt_main
from nexusbt.contracts import SchemaRegistry
from nexusbt.pipeline import BoundColumn, bind, stub_source

TYPO = "clsoe"  # by `getattr`: the stubs make `Price.clsoe` a type error too
#: 3.2, the `Price` table, in its order.
PRICE = "open high low close close_tr close_unadjusted volume volume_unadjusted value_traded"


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
    assert type(Meta.category.eq("etf")) is nx.Filter
    assert {"country", "exchange", "market"} <= set(dir(Meta))
    with pytest.raises(nx.ColumnNameError, match=r"'contry'\. Did you mean: country\?"):
        getattr(Meta, TYPO[:0] + "contry")


@pytest.mark.parametrize(
    ("dataset", "name"),
    [(Meta, "sector"), (Meta, "industry"), (Meta, "is_financial"), (Price, "shares_out"),
     (Price, "market_cap")],
)  # fmt: skip
def test_removed_columns_are_column_name_errors(dataset: type, name: str) -> None:
    """3.2: a sector or an industry is an item (`Item`), a share count a value-table item
    (5.3.5a); these columns were removed 2026-11-24 (#752)."""
    with pytest.raises(nx.ColumnNameError, match=f"has no column '{name}'"):
        getattr(dataset, name)
    assert name not in dir(dataset)


@pytest.mark.parametrize("name", ["delisted_on", "last_session", "name"])
def test_meta_has_no_hindsight_columns(name: str) -> None:
    """INV-01: what is known only after the fact is not a `Meta` column (3.2, RV-C08)."""
    with pytest.raises(nx.ColumnNameError, match=f"instruments.{name} is known only after"):
        getattr(Meta, name)
    assert name not in dir(Meta)


#: A snapshot's column set as `api` hands it to `bind` (2.5).
REGISTRY = SchemaRegistry({"bars_1d": (("instrument_id", "id"), ("close", "f64"))})


def test_schema_registry_injected_at_binding() -> None:
    """2.5: `pipeline` reads no data, so a graph meets the snapshot's registry at binding,
    wherever its nodes sit; a chain deeper than the call stack binds (a loop, not recursion)."""
    graph = Price.close.latest.rank(mask=Price.volume.latest > 0) + Price.open.latest
    bind(graph, REGISTRY)
    bind(nx.Pipeline({"value": graph}, screen=Price.close.latest > 0), REGISTRY)
    deep = Price.close.latest
    for _ in range(3000):  # deeper than the call stack
        deep = deep + 1
    bind(deep, REGISTRY)
    bind(deep, SchemaRegistry({}))  # a snapshot's columns are not read until `Item` (5.3.5)


def test_stub_file_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """3.2: `nexusbt stubs` writes the datasets' columns where the editor reads them."""
    fixed = stub_source()
    for line in (
        "class Price:\n    open: BoundColumn",
        "value_traded: BoundColumn",
        "class Meta:\n",
        "    market: Classifier\n",
        "    category: Classifier\n",
        "    country: Classifier\n",
    ):
        assert line in fixed
    assert "delisted_on" not in fixed
    for removed in ("Panel", "Label"):  # 2026-11-24 (#752)
        assert removed not in fixed
    assert stub_source(REGISTRY) == fixed  # no class holds a snapshot's columns until `Item`
    stub = Path(nx.__file__).parent / "_stubs" / "datasets.pyi"
    assert stub.read_text(encoding="utf-8") == fixed  # the committed file: no snapshot
    monkeypatch.chdir(tmp_path)  # no nexusbt.toml: no snapshot to read
    monkeypatch.delenv("NEXUSBT_DATA_ROOT", raising=False)
    assert nexusbt_main(["stubs"]) == 0
    assert capsys.readouterr().out.strip() == str(stub)
    assert stub.read_text(encoding="utf-8") == fixed
