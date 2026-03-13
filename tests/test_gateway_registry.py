from typing import Any, Callable, Sequence

from akquant import DataFeed
from akquant.gateway import (
    GatewayBundle,
    create_gateway_bundle,
    get_broker_builder,
    list_registered_brokers,
    register_broker,
    unregister_broker,
)
from akquant.gateway.models import (
    UnifiedAccount,
    UnifiedExecutionReport,
    UnifiedOrderRequest,
    UnifiedOrderSnapshot,
    UnifiedOrderStatus,
    UnifiedPosition,
    UnifiedTrade,
)


class _DummyMarketGateway:
    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def subscribe(self, symbols: Sequence[str]) -> None:
        _ = symbols

    def unsubscribe(self, symbols: Sequence[str]) -> None:
        _ = symbols

    def on_tick(self, callback: Callable[[dict[str, Any]], None]) -> None:
        _ = callback

    def on_bar(self, callback: Callable[[dict[str, Any]], None]) -> None:
        _ = callback

    def start(self) -> None:
        return None


class _DummyTraderGateway:
    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def place_order(self, req: UnifiedOrderRequest) -> str:
        return f"b-{req.client_order_id}"

    def cancel_order(self, broker_order_id: str) -> None:
        _ = broker_order_id

    def query_order(self, broker_order_id: str) -> UnifiedOrderSnapshot | None:
        _ = broker_order_id
        return None

    def query_trades(self, since: int | None = None) -> list[UnifiedTrade]:
        _ = since
        return []

    def query_account(self) -> UnifiedAccount | None:
        return None

    def query_positions(self) -> list[UnifiedPosition]:
        return []

    def on_order(self, callback: Callable[[UnifiedOrderSnapshot], None]) -> None:
        _ = callback

    def on_trade(self, callback: Callable[[UnifiedTrade], None]) -> None:
        _ = callback

    def on_execution_report(
        self, callback: Callable[[UnifiedExecutionReport], None]
    ) -> None:
        _ = callback

    def sync_open_orders(self) -> list[UnifiedOrderSnapshot]:
        return []

    def sync_today_trades(self) -> list[UnifiedTrade]:
        return []

    def heartbeat(self) -> bool:
        return True

    def start(self) -> None:
        return None


def _dummy_builder(
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool,
    **kwargs: Any,
) -> GatewayBundle:
    _ = feed
    _ = symbols
    _ = use_aggregator
    return GatewayBundle(
        market_gateway=_DummyMarketGateway(),
        trader_gateway=_DummyTraderGateway(),
        metadata={
            "broker": "dummy",
            "tag": kwargs.get("tag", ""),
            "status": UnifiedOrderStatus.SUBMITTED.value,
        },
    )


def test_gateway_registry_register_and_create_bundle() -> None:
    """Registered broker should be creatable through factory."""
    unregister_broker("dummy")
    register_broker("dummy", _dummy_builder)
    feed = DataFeed()
    bundle = create_gateway_bundle(
        broker="dummy",
        feed=feed,
        symbols=["000001.SZ"],
        tag="x",
    )

    assert bundle.metadata is not None
    assert bundle.metadata["broker"] == "dummy"
    assert bundle.metadata["tag"] == "x"
    unregister_broker("dummy")


def test_gateway_registry_lookup_and_list() -> None:
    """Registry list and lookup should reflect registration lifecycle."""
    unregister_broker("dummy")
    register_broker("dummy", _dummy_builder)

    assert get_broker_builder("dummy") is not None
    assert "dummy" in list_registered_brokers()

    unregister_broker("dummy")
    assert get_broker_builder("dummy") is None
