# -*- coding: utf-8 -*-

from typing import Any, Callable, Sequence

from akquant import DataFeed
from akquant.gateway import (
    GatewayBundle,
    create_gateway_bundle,
    register_broker,
    unregister_broker,
)
from akquant.gateway.models import (
    UnifiedAccount,
    UnifiedExecutionReport,
    UnifiedOrderRequest,
    UnifiedOrderSnapshot,
    UnifiedPosition,
    UnifiedTrade,
)


class _DemoMarketGateway:
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


class _DemoTraderGateway:
    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def place_order(self, req: UnifiedOrderRequest) -> str:
        return f"demo-{req.client_order_id}"

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


def _demo_builder(
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool,
    **kwargs: Any,
) -> GatewayBundle:
    _ = feed
    _ = symbols
    _ = use_aggregator
    return GatewayBundle(
        market_gateway=_DemoMarketGateway(),
        trader_gateway=_DemoTraderGateway(),
        metadata={"broker": "demo", "label": kwargs.get("label", "default")},
    )


def _main() -> None:
    register_broker("demo", _demo_builder)
    bundle = create_gateway_bundle(
        broker="demo",
        feed=DataFeed(),
        symbols=["000001.SZ"],
        label="registry-demo",
    )
    print(bundle.metadata)
    unregister_broker("demo")


if __name__ == "__main__":
    _main()
