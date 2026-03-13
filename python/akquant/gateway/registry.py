from typing import Any, Callable, Dict, Sequence

from ..akquant import DataFeed
from .base import GatewayBundle

GatewayBuilder = Callable[[DataFeed, Sequence[str], bool], GatewayBundle]

_BROKER_BUILDERS: Dict[str, Callable[..., GatewayBundle]] = {}


def register_broker(name: str, builder: Callable[..., GatewayBundle]) -> None:
    """Register a custom broker builder."""
    broker_key = name.strip().lower()
    if not broker_key:
        raise ValueError("broker name cannot be empty")
    _BROKER_BUILDERS[broker_key] = builder


def unregister_broker(name: str) -> None:
    """Unregister a custom broker builder."""
    broker_key = name.strip().lower()
    _BROKER_BUILDERS.pop(broker_key, None)


def get_broker_builder(name: str) -> Callable[..., GatewayBundle] | None:
    """Get custom broker builder by key."""
    broker_key = name.strip().lower()
    return _BROKER_BUILDERS.get(broker_key)


def list_registered_brokers() -> list[str]:
    """List registered custom broker keys."""
    return sorted(_BROKER_BUILDERS.keys())


def create_registered_gateway_bundle(
    name: str,
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool,
    **kwargs: Any,
) -> GatewayBundle | None:
    """Create gateway bundle from custom registry if broker exists."""
    builder = get_broker_builder(name)
    if builder is None:
        return None
    return builder(
        feed=feed,
        symbols=symbols,
        use_aggregator=use_aggregator,
        **kwargs,
    )
