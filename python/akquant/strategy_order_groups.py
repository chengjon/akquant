"""OCO 和 Bracket 订单组逻辑 (OCO and Bracket order group logic).

Extracted from strategy.py to reduce file size and improve maintainability.
These functions operate on a strategy instance's internal state.
"""

from typing import TYPE_CHECKING, Any, Optional, Set

from .akquant import TimeInForce

if TYPE_CHECKING:
    pass


def create_oco_order_group(
    strategy: Any,
    first_order_id: str,
    second_order_id: str,
    group_id: Optional[str] = None,
) -> str:
    """创建 OCO 订单组.

    当组内任一订单成交时，自动撤销另一订单。
    """
    first = first_order_id.strip()
    second = second_order_id.strip()
    if not first or not second:
        raise ValueError("OCO order ids cannot be empty")
    if first == second:
        raise ValueError("OCO order ids must be different")

    if group_id is None or not str(group_id).strip():
        strategy._order_group_seq += 1  # noqa: SLF001
        group_id = f"oco-{strategy._order_group_seq}"  # noqa: SLF001
    group_key = str(group_id).strip()

    engine = getattr(strategy, "_engine", None)
    register_oco = getattr(engine, "register_oco_group", None)
    if callable(register_oco):
        try:
            register_oco(group_key, first, second)
            strategy._use_engine_oco = True  # noqa: SLF001
            return group_key
        except Exception:
            strategy._pending_engine_oco_groups.append(  # noqa: SLF001
                (group_key, first, second)
            )
            strategy._use_engine_oco = True  # noqa: SLF001
            return group_key

    detach_oco_order(strategy, first)
    detach_oco_order(strategy, second)

    strategy._oco_groups[group_key] = {first, second}  # noqa: SLF001
    strategy._oco_order_to_group[first] = group_key  # noqa: SLF001
    strategy._oco_order_to_group[second] = group_key  # noqa: SLF001
    return group_key


def place_bracket_order(
    strategy: Any,
    symbol: str,
    quantity: float,
    entry_price: Optional[float] = None,
    stop_trigger_price: Optional[float] = None,
    take_profit_price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
    entry_tag: Optional[str] = None,
    stop_tag: Optional[str] = None,
    take_profit_tag: Optional[str] = None,
) -> str:
    """创建 Bracket 订单.

    先提交进场单，待进场成交后自动挂出止损/止盈，并绑定 OCO。
    """
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    if stop_trigger_price is None and take_profit_price is None:
        raise ValueError("stop_trigger_price or take_profit_price must be provided")

    entry_order_id = strategy.buy(
        symbol=symbol,
        quantity=quantity,
        price=entry_price,
        time_in_force=time_in_force,
        tag=entry_tag,
    )
    if not entry_order_id:
        raise RuntimeError("failed to submit bracket entry order")

    engine = getattr(strategy, "_engine", None)
    register_bracket = getattr(engine, "register_bracket_plan", None)
    if callable(register_bracket):
        try:
            register_bracket(
                entry_order_id,
                stop_trigger_price,
                take_profit_price,
                time_in_force,
                stop_tag,
                take_profit_tag,
            )
            strategy._use_engine_bracket = True  # noqa: SLF001
            return entry_order_id
        except Exception:
            strategy._pending_engine_bracket_plans.append(  # noqa: SLF001
                (
                    entry_order_id,
                    stop_trigger_price,
                    take_profit_price,
                    time_in_force,
                    stop_tag,
                    take_profit_tag,
                )
            )
            strategy._use_engine_bracket = True  # noqa: SLF001
            return entry_order_id

    strategy._pending_brackets[entry_order_id] = {  # noqa: SLF001
        "symbol": symbol,
        "quantity": float(quantity),
        "stop_trigger_price": stop_trigger_price,
        "take_profit_price": take_profit_price,
        "time_in_force": time_in_force,
        "stop_tag": stop_tag,
        "take_profit_tag": take_profit_tag,
    }
    return entry_order_id


def process_order_groups(strategy: Any, trade: Any) -> None:
    """处理成交后的订单组逻辑 (bracket + OCO)."""
    process_pending_bracket(strategy, trade)
    process_oco_trade(strategy, trade)


def process_pending_bracket(strategy: Any, trade: Any) -> None:
    """处理 bracket 订单成交后的止盈止损挂单."""
    if strategy._use_engine_bracket:  # noqa: SLF001
        return
    order_id = str(getattr(trade, "order_id", "") or "")
    if not order_id:
        return

    bracket = strategy._pending_brackets.pop(order_id, None)  # noqa: SLF001
    if bracket is None:
        return

    trade_symbol = getattr(trade, "symbol", None)
    symbol = str(trade_symbol) if trade_symbol else str(bracket["symbol"])

    trade_qty = getattr(trade, "quantity", None)
    if trade_qty is None:
        quantity = float(bracket["quantity"])
    else:
        quantity = float(trade_qty)

    stop_order_id = ""
    take_order_id = ""
    stop_trigger_price = bracket["stop_trigger_price"]
    take_profit_price = bracket["take_profit_price"]
    bracket_tif = bracket["time_in_force"]

    if stop_trigger_price is not None:
        stop_order_id = strategy.sell(
            symbol=symbol,
            quantity=quantity,
            trigger_price=float(stop_trigger_price),
            time_in_force=bracket_tif,
            tag=bracket["stop_tag"],
        )

    if take_profit_price is not None:
        take_order_id = strategy.sell(
            symbol=symbol,
            quantity=quantity,
            price=float(take_profit_price),
            time_in_force=bracket_tif,
            tag=bracket["take_profit_tag"],
        )

    if stop_order_id and take_order_id:
        create_oco_order_group(strategy, stop_order_id, take_order_id)


def process_oco_trade(strategy: Any, trade: Any) -> None:
    """处理 OCO 组内成交: 成交一个则撤销其余."""
    if strategy._use_engine_oco:  # noqa: SLF001
        return
    order_id = str(getattr(trade, "order_id", "") or "")
    if not order_id:
        return

    group_id = strategy._oco_order_to_group.get(order_id)  # noqa: SLF001
    if not group_id:
        return

    group_orders = strategy._oco_groups.get(group_id, set())  # noqa: SLF001
    peer_orders = [oid for oid in group_orders if oid != order_id]
    for peer_order_id in peer_orders:
        strategy.cancel_order(peer_order_id)

    remove_oco_group(strategy, group_id)


def detach_oco_order(strategy: Any, order_id: str) -> None:
    """从现有 OCO 组中分离订单."""
    old_group = strategy._oco_order_to_group.get(order_id)  # noqa: SLF001
    if not old_group:
        return
    group_orders: Set[str] = strategy._oco_groups.get(old_group, set())  # noqa: SLF001
    if group_orders is not None:
        group_orders.discard(order_id)
        if len(group_orders) <= 1:
            remove_oco_group(strategy, old_group)
    strategy._oco_order_to_group.pop(order_id, None)  # noqa: SLF001


def remove_oco_group(strategy: Any, group_id: str) -> None:
    """移除整个 OCO 组."""
    group_orders = strategy._oco_groups.pop(group_id, set())  # noqa: SLF001
    for oid in group_orders:
        strategy._oco_order_to_group.pop(oid, None)  # noqa: SLF001
