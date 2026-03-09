from __future__ import annotations

from typing import Any, Tuple

from .akquant import OrderStatus
from .strategy_framework_hooks import (
    call_user_callback,
    ensure_framework_state,
    mark_portfolio_dirty,
)


def check_order_events(strategy: Any) -> None:
    """检查订单和成交事件并触发回调."""
    ensure_framework_state(strategy)
    if strategy.ctx is None:
        return

    if hasattr(strategy.ctx, "canceled_order_ids"):
        for oid in strategy.ctx.canceled_order_ids:
            if oid in strategy._known_orders:
                order = strategy._known_orders[oid]
                try:
                    order.status = OrderStatus.Cancelled
                except Exception:
                    pass

                _emit_order_callback(strategy, order)
                del strategy._known_orders[oid]

    current_active_ids: set[str] = set()
    if hasattr(strategy.ctx, "active_orders"):
        for order in strategy.ctx.active_orders:
            current_active_ids.add(order.id)
            oid = order.id

            if oid not in strategy._known_orders:
                strategy._known_orders[oid] = order
                _emit_order_callback(strategy, order)
            else:
                known = strategy._known_orders[oid]
                status_changed = known.status != order.status
                qty_changed = known.filled_quantity != order.filled_quantity
                if status_changed or qty_changed:
                    strategy._known_orders[oid] = order
                    _emit_order_callback(strategy, order)

    recent_trade_order_ids: set[str] = set()
    if hasattr(strategy.ctx, "recent_trades"):
        for t in strategy.ctx.recent_trades:
            recent_trade_order_ids.add(t.order_id)

    for oid in list(strategy._known_orders.keys()):
        if oid not in current_active_ids:
            if oid in recent_trade_order_ids:
                order = strategy._known_orders[oid]
                try:
                    order.status = OrderStatus.Filled
                except Exception:
                    pass
                _emit_order_callback(strategy, order)
                del strategy._known_orders[oid]
            else:
                del strategy._known_orders[oid]

    if hasattr(strategy.ctx, "recent_trades"):
        for t in strategy.ctx.recent_trades:
            key = trade_event_key(strategy, t)
            if not remember_trade_key(strategy, key):
                continue
            call_user_callback(strategy, "on_trade", t, payload=t)
            process_order_groups(strategy, t)
            analyzer_manager = getattr(strategy, "_analyzer_manager", None)
            if analyzer_manager is not None:
                try:
                    analyzer_manager.on_trade(
                        {
                            "strategy": strategy,
                            "trade": t,
                            "engine": getattr(strategy, "_engine", None),
                            "ctx": strategy.ctx,
                            "owner_strategy_id": str(
                                getattr(strategy.ctx, "strategy_id", None)
                                or getattr(strategy, "_owner_strategy_id", "_default")
                            ),
                        }
                    )
                except Exception:
                    pass
            mark_portfolio_dirty(strategy)


def _emit_order_callback(strategy: Any, order: Any) -> None:
    call_user_callback(strategy, "on_order", order, payload=order)
    mark_portfolio_dirty(strategy)

    if getattr(order, "status", None) == OrderStatus.Rejected:
        order_id = getattr(order, "id", "")
        if order_id and order_id not in strategy._framework_rejected_order_ids:
            strategy._framework_rejected_order_ids.add(order_id)
            call_user_callback(strategy, "on_reject", order, payload=order)


def trade_event_key(strategy: Any, trade: Any) -> Tuple[Any, ...]:
    """生成成交事件去重 Key."""
    return (
        key_value(getattr(trade, "trade_id", None)),
        key_value(getattr(trade, "id", None)),
        key_value(getattr(trade, "order_id", None)),
        key_value(getattr(trade, "timestamp", None)),
        key_value(getattr(trade, "symbol", None)),
        key_value(getattr(trade, "side", None)),
        key_value(getattr(trade, "quantity", None)),
        key_value(getattr(trade, "price", None)),
    )


def key_value(value: Any) -> Any:
    """将复杂对象转换为可稳定哈希的值."""
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return value
    return str(value)


def remember_trade_key(strategy: Any, key: Tuple[Any, ...]) -> bool:
    """记录成交 Key，返回是否为首次出现."""
    if key in strategy._seen_trade_keys:
        return False

    strategy._seen_trade_keys.add(key)
    strategy._seen_trade_key_order.append(key)

    limit = trade_dedupe_cache_limit(strategy)
    while len(strategy._seen_trade_key_order) > limit:
        oldest = strategy._seen_trade_key_order.popleft()
        strategy._seen_trade_keys.discard(oldest)
    return True


def trade_dedupe_cache_limit(strategy: Any) -> int:
    """获取成交去重缓存上限."""
    raw_limit = getattr(strategy, "trade_dedupe_cache_size", 50000)
    try:
        return max(1, int(raw_limit))
    except (TypeError, ValueError):
        return 50000


def process_order_groups(strategy: Any, trade: Any) -> None:
    """处理策略内部订单组联动逻辑."""
    handler = getattr(strategy, "_process_order_groups", None)
    if callable(handler):
        handler(trade)
