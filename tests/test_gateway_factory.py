import pytest
from akquant import DataFeed
from akquant.gateway import create_gateway_bundle


def test_create_miniqmt_gateway_bundle() -> None:
    """Create MiniQMT gateway bundle with trader gateway."""
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="miniqmt",
        feed=feed,
        symbols=["000001.SZ"],
    )
    assert bundle.metadata is not None
    assert bundle.metadata["broker"] == "miniqmt"
    assert bundle.trader_gateway is not None


def test_create_ptrade_gateway_bundle() -> None:
    """Create PTrade gateway bundle with trader gateway."""
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="ptrade",
        feed=feed,
        symbols=["000001.SZ"],
    )
    assert bundle.metadata is not None
    assert bundle.metadata["broker"] == "ptrade"
    assert bundle.trader_gateway is not None


def test_factory_sets_stock_asset_class_for_miniqmt() -> None:
    """MiniQMT bundle metadata must carry asset_class=stock."""
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="miniqmt",
        feed=feed,
        symbols=["000001.SZ"],
    )
    assert bundle.metadata is not None
    assert bundle.metadata["asset_class"] == "stock"


def test_factory_sets_stock_asset_class_for_ptrade() -> None:
    """PTrade bundle metadata must carry asset_class=stock."""
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="ptrade",
        feed=feed,
        symbols=["000001.SZ"],
    )
    assert bundle.metadata is not None
    assert bundle.metadata["asset_class"] == "stock"


def test_factory_sets_futures_asset_class_for_ctp() -> None:
    """CTP bundle metadata must carry asset_class=futures."""
    pytest.importorskip("openctp_ctp", reason="openctp-ctp not installed")
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="ctp",
        feed=feed,
        symbols=["au2606"],
        md_front="tcp://180.168.146.187:10131",
    )
    assert bundle.metadata is not None
    assert bundle.metadata["asset_class"] == "futures"


def test_miniqmt_bridge_url_raises_not_implemented() -> None:
    """MiniQMT with bridge_url must raise NotImplementedError."""
    feed = DataFeed()
    with pytest.raises(
        NotImplementedError, match="HTTP bridge mode is not yet available"
    ):
        create_gateway_bundle(
            broker="miniqmt",
            feed=feed,
            symbols=["000001.SZ"],
            bridge_url="http://localhost:8080",
        )
