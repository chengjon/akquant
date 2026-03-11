from __future__ import annotations

from typing import Any, Sequence

from ..akquant import DataFeed
from .base import GatewayBundle, MarketGateway, TraderGateway
from .ctp_adapter import CTPMarketAdapter, CTPTraderAdapter
from .miniqmt import MiniQMTMarketGateway, MiniQMTTraderGateway
from .ptrade import PTradeMarketGateway, PTradeTraderGateway
from .registry import create_registered_gateway_bundle, list_registered_brokers


def create_gateway_bundle(
    broker: str,
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool = True,
    **kwargs: Any,
) -> GatewayBundle:
    """Create market/trader gateway bundle by broker key."""
    broker_key = broker.strip().lower()
    registered_bundle = create_registered_gateway_bundle(
        name=broker_key,
        feed=feed,
        symbols=symbols,
        use_aggregator=use_aggregator,
        **kwargs,
    )
    if registered_bundle is not None:
        return registered_bundle

    if broker_key == "ctp":
        md_front = kwargs.get("md_front", "")
        if not md_front:
            raise ValueError("md_front is required when broker='ctp'")

        market_gateway: MarketGateway = CTPMarketAdapter(
            feed=feed,
            front_url=md_front,
            symbols=list(symbols),
            use_aggregator=use_aggregator,
        )

        trader_gateway: TraderGateway | None = None
        td_front = kwargs.get("td_front")
        user_id = kwargs.get("user_id")
        if td_front and user_id:
            trader_gateway = CTPTraderAdapter(
                front_url=td_front,
                broker_id=kwargs.get("broker_id", "9999"),
                user_id=user_id,
                password=kwargs.get("password", ""),
                auth_code=kwargs.get("auth_code", "0000000000000000"),
                app_id=kwargs.get("app_id", "simnow_client_test"),
            )
        return GatewayBundle(
            market_gateway=market_gateway,
            trader_gateway=trader_gateway,
            metadata={"broker": "ctp"},
        )

    if broker_key == "miniqmt":
        market_gateway = MiniQMTMarketGateway(
            feed=feed,
            symbols=list(symbols),
            **kwargs,
        )
        miniqmt_trader_gateway: TraderGateway | None = MiniQMTTraderGateway(**kwargs)
        return GatewayBundle(
            market_gateway=market_gateway,
            trader_gateway=miniqmt_trader_gateway,
            metadata={"broker": "miniqmt"},
        )

    if broker_key == "ptrade":
        market_gateway = PTradeMarketGateway(
            feed=feed,
            symbols=list(symbols),
            **kwargs,
        )
        ptrade_trader_gateway: TraderGateway | None = PTradeTraderGateway(**kwargs)
        return GatewayBundle(
            market_gateway=market_gateway,
            trader_gateway=ptrade_trader_gateway,
            metadata={"broker": "ptrade"},
        )

    builtins = ["ctp", "miniqmt", "ptrade"]
    registered = list_registered_brokers()
    all_brokers = builtins + [name for name in registered if name not in builtins]
    supported = ", ".join(all_brokers)
    raise ValueError(f"broker must be one of: {supported}")
