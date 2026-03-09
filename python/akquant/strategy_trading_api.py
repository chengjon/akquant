from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from .akquant import OrderStatus, OrderType, TimeInForce


def resolve_symbol(strategy: Any, symbol: Optional[str]) -> str:
    """解析标的代码，默认使用当前处理的 bar/tick 标的."""
    if symbol is None:
        if strategy._last_event_type == "tick" and strategy.current_tick:
            symbol = strategy.current_tick.symbol
        elif strategy._last_event_type == "bar" and strategy.current_bar:
            symbol = strategy.current_bar.symbol
        elif strategy.current_bar:
            symbol = strategy.current_bar.symbol
        elif strategy.current_tick:
            symbol = strategy.current_tick.symbol
        else:
            raise ValueError("Symbol must be provided")
    return symbol


def get_position(strategy: Any, symbol: Optional[str] = None) -> float:
    """获取指定标的的持仓数量."""
    if strategy.ctx is None:
        return 0.0
    symbol = resolve_symbol(strategy, symbol)
    return float(strategy.ctx.get_position(symbol))


def get_available_position(strategy: Any, symbol: Optional[str] = None) -> float:
    """获取指定标的的可用持仓数量."""
    if strategy.ctx is None:
        return 0.0
    symbol = resolve_symbol(strategy, symbol)
    return float(strategy.ctx.get_available_position(symbol))


def hold_bar(strategy: Any, symbol: Optional[str] = None) -> int:
    """获取当前持仓持有的 Bar 数量."""
    if strategy.ctx is None:
        return 0
    symbol = resolve_symbol(strategy, symbol)
    return int(strategy._hold_bars[symbol])


def get_positions(strategy: Any) -> Dict[str, float]:
    """获取所有持仓信息."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")
    return cast(Dict[str, float], strategy.ctx.positions)


def get_open_orders(strategy: Any, symbol: Optional[str] = None) -> List[Any]:
    """获取当前未完成的订单."""
    if strategy.ctx is None:
        return []

    orders = [
        o
        for o in strategy.ctx.active_orders
        if o.status
        in (OrderStatus.New, OrderStatus.Submitted, OrderStatus.PartiallyFilled)
    ]
    if symbol:
        return [o for o in orders if o.symbol == symbol]
    return orders


def get_order(strategy: Any, order_id: str) -> Optional[Any]:
    """获取指定订单详情."""
    if order_id in strategy._known_orders:
        return strategy._known_orders[order_id]

    if strategy.ctx:
        for o in strategy.ctx.active_orders:
            if o.id == order_id:
                return o
    return None


def cancel_order(strategy: Any, order_id: str) -> None:
    """取消指定订单."""
    if strategy.ctx:
        strategy.ctx.cancel_order(order_id)


def cancel_all_orders(strategy: Any, symbol: Optional[str] = None) -> None:
    """取消当前所有未完成的订单."""
    for order in get_open_orders(strategy, symbol=symbol):
        cancel_order(strategy, order.id)


def buy(
    strategy: Any,
    symbol: Optional[str] = None,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
    trigger_price: Optional[float] = None,
    tag: Optional[str] = None,
    order_type: Optional[str] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
) -> str:
    """买入下单."""
    submit_order_method = getattr(strategy, "submit_order", None)
    if callable(submit_order_method):
        return cast(
            str,
            submit_order_method(
                symbol=symbol,
                side="Buy",
                quantity=quantity,
                price=price,
                time_in_force=time_in_force,
                trigger_price=trigger_price,
                tag=tag,
                order_type=order_type,
                trail_offset=trail_offset,
                trail_reference_price=trail_reference_price,
            ),
        )
    order_type_enum = _parse_order_type(order_type)
    return _submit_buy_side(
        strategy=strategy,
        symbol=symbol,
        quantity=quantity,
        price=price,
        time_in_force=time_in_force,
        trigger_price=trigger_price,
        tag=tag,
        order_type=order_type_enum,
        trail_offset=trail_offset,
        trail_reference_price=trail_reference_price,
    )


def sell(
    strategy: Any,
    symbol: Optional[str] = None,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
    trigger_price: Optional[float] = None,
    tag: Optional[str] = None,
    order_type: Optional[str] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
) -> str:
    """卖出下单."""
    submit_order_method = getattr(strategy, "submit_order", None)
    if callable(submit_order_method):
        return cast(
            str,
            submit_order_method(
                symbol=symbol,
                side="Sell",
                quantity=quantity,
                price=price,
                time_in_force=time_in_force,
                trigger_price=trigger_price,
                tag=tag,
                order_type=order_type,
                trail_offset=trail_offset,
                trail_reference_price=trail_reference_price,
            ),
        )
    order_type_enum = _parse_order_type(order_type)
    return _submit_sell_side(
        strategy=strategy,
        symbol=symbol,
        quantity=quantity,
        price=price,
        time_in_force=time_in_force,
        trigger_price=trigger_price,
        tag=tag,
        order_type=order_type_enum,
        trail_offset=trail_offset,
        trail_reference_price=trail_reference_price,
    )


def _submit_buy_side(
    strategy: Any,
    symbol: Optional[str],
    quantity: Optional[float],
    price: Optional[float],
    time_in_force: Optional[TimeInForce],
    trigger_price: Optional[float],
    tag: Optional[str],
    order_type: Optional[Any] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
) -> str:
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = resolve_symbol(strategy, symbol)

    ref_price = price
    if ref_price is None:
        ref_price = strategy._last_prices.get(symbol, 0.0)

    if quantity is None:
        quantity = strategy.sizer.get_size(
            ref_price, strategy.ctx.cash, strategy.ctx, symbol
        )

    if quantity > 0:
        if (
            order_type is None
            and trail_offset is None
            and trail_reference_price is None
        ):
            return cast(
                str,
                strategy.ctx.buy(
                    symbol, quantity, price, time_in_force, trigger_price, tag or ""
                ),
            )
        return cast(
            str,
            strategy.ctx.buy(
                symbol,
                quantity,
                price,
                time_in_force,
                trigger_price,
                tag or "",
                order_type,
                trail_offset,
                trail_reference_price,
            ),
        )
    return ""


def _submit_sell_side(
    strategy: Any,
    symbol: Optional[str],
    quantity: Optional[float],
    price: Optional[float],
    time_in_force: Optional[TimeInForce],
    trigger_price: Optional[float],
    tag: Optional[str],
    order_type: Optional[Any] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
) -> str:
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = resolve_symbol(strategy, symbol)

    if quantity is None:
        pos = strategy.ctx.get_position(symbol)
        if pos > 0:
            quantity = pos
        else:
            return ""

    if quantity > 0:
        if (
            order_type is None
            and trail_offset is None
            and trail_reference_price is None
        ):
            return cast(
                str,
                strategy.ctx.sell(
                    symbol, quantity, price, time_in_force, trigger_price, tag or ""
                ),
            )
        return cast(
            str,
            strategy.ctx.sell(
                symbol,
                quantity,
                price,
                time_in_force,
                trigger_price,
                tag or "",
                order_type,
                trail_offset,
                trail_reference_price,
            ),
        )
    return ""


def get_execution_capabilities(strategy: Any) -> Dict[str, Any]:
    """获取当前执行环境能力描述."""
    _ = strategy
    return {
        "broker_live": False,
        "client_order_id": False,
        "order_type": True,
        "time_in_force_str": False,
        "broker_extra_fields": [],
    }


def submit_order(
    strategy: Any,
    symbol: Optional[str] = None,
    side: str = "Buy",
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce | str] = None,
    trigger_price: Optional[float] = None,
    tag: Optional[str] = None,
    client_order_id: Optional[str] = None,
    order_type: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
) -> str:
    """统一下单接口."""
    capabilities = get_execution_capabilities(strategy)
    if client_order_id and not bool(capabilities.get("client_order_id", False)):
        raise RuntimeError("client_order_id is not supported in current execution mode")
    if extra:
        raise RuntimeError(
            "extra broker fields are not supported in current execution mode"
        )
    order_type_key, order_type_enum = _parse_order_type(order_type)
    if time_in_force is not None and not isinstance(time_in_force, TimeInForce):
        raise RuntimeError(
            "time_in_force string is not supported in current execution mode"
        )
    if order_type_key in {"stoptrail", "stoptraillimit"}:
        if trail_offset is None or trail_offset <= 0:
            raise RuntimeError("trail_offset must be > 0 for trailing orders")
    if order_type_key == "stoptraillimit" and price is None:
        raise RuntimeError("price must be provided for StopTrailLimit order")
    if order_type_key in {"stoptrail", "stoptraillimit"} and order_type_enum is None:
        raise RuntimeError("trailing order requires runtime with StopTrail support")

    side_text = side.strip().lower()
    if side_text == "buy":
        return _submit_buy_side(
            strategy=strategy,
            symbol=symbol,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            trigger_price=trigger_price,
            tag=tag,
            order_type=order_type_enum,
            trail_offset=trail_offset,
            trail_reference_price=trail_reference_price,
        )
    if side_text == "sell":
        return _submit_sell_side(
            strategy=strategy,
            symbol=symbol,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            trigger_price=trigger_price,
            tag=tag,
            order_type=order_type_enum,
            trail_offset=trail_offset,
            trail_reference_price=trail_reference_price,
        )
    raise ValueError(f"Unsupported side: {side}")


def _parse_order_type(order_type: Optional[str]) -> Tuple[Optional[str], Optional[Any]]:
    if order_type is None:
        return None, None
    key = str(order_type).strip().lower()
    mapping: Dict[str, str] = {
        "market": "Market",
        "limit": "Limit",
        "stop": "StopMarket",
        "stopmarket": "StopMarket",
        "stop_limit": "StopLimit",
        "stoplimit": "StopLimit",
        "stoptrail": "StopTrail",
        "stoptraillimit": "StopTrailLimit",
    }
    if key not in mapping:
        raise RuntimeError(
            f"order_type {order_type!r} is not supported in current execution mode"
        )
    attr_name = mapping[key]
    return key, getattr(OrderType, attr_name, None)


def stop_buy(
    strategy: Any,
    symbol: Optional[str] = None,
    trigger_price: float = 0.0,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
) -> None:
    """发送止损买入单."""
    buy(strategy, symbol, quantity, price, time_in_force, trigger_price=trigger_price)


def stop_sell(
    strategy: Any,
    symbol: Optional[str] = None,
    trigger_price: float = 0.0,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
) -> None:
    """发送止损卖出单."""
    sell(strategy, symbol, quantity, price, time_in_force, trigger_price=trigger_price)


def get_portfolio_value(strategy: Any) -> float:
    """计算当前投资组合总价值 (现金 + 持仓市值)."""
    if strategy.ctx is None:
        return 0.0

    total_value = float(strategy.ctx.cash)
    for sym, qty in strategy.ctx.positions.items():
        if qty == 0:
            continue

        price = strategy._last_prices.get(sym, 0.0)
        if price == 0.0:
            if strategy.current_bar and strategy.current_bar.symbol == sym:
                price = strategy.current_bar.close
            elif strategy.current_tick and strategy.current_tick.symbol == sym:
                price = strategy.current_tick.price

        total_value += float(qty) * price
    return total_value


def get_account(strategy: Any) -> Dict[str, float]:
    """获取账户资金详情快照."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    cash = strategy.ctx.cash
    equity = strategy.equity
    market_value = equity - cash
    return {
        "cash": cash,
        "equity": equity,
        "market_value": market_value,
        "frozen_cash": 0.0,
        "margin": 0.0,
    }


def calculate_max_buy_qty(
    strategy: Any, symbol: str, price: float, cash: float
) -> float:
    """计算考虑费率后的最大可买数量."""
    if price <= 0 or cash <= 0:
        return 0.0

    total_rate = float(strategy.commission_rate) + float(strategy.transfer_fee_rate)

    safety_margin = 0.0001
    if strategy.ctx and hasattr(strategy.ctx, "risk_config"):
        safety_margin = float(strategy.ctx.risk_config.safety_margin)

    safe_cash = float(cash) * (1.0 - float(safety_margin))
    est_qty = safe_cash / (float(price) * (1 + float(total_rate)))
    est_commission = est_qty * float(price) * float(strategy.commission_rate)

    if est_commission < float(strategy.min_commission):
        remaining_cash = safe_cash - float(strategy.min_commission)
        if remaining_cash <= 0:
            return 0.0
        est_qty = remaining_cash / (
            float(price) * (1 + float(strategy.transfer_fee_rate))
        )

    current_lot_size = 1
    if isinstance(strategy.lot_size, int):
        current_lot_size = int(strategy.lot_size)
    elif isinstance(strategy.lot_size, dict):
        val = strategy.lot_size.get(symbol, strategy.lot_size.get("DEFAULT", 1))
        current_lot_size = int(val) if val is not None else 1

    if current_lot_size > 0:
        est_qty = (est_qty // current_lot_size) * current_lot_size

    return float(est_qty)


def order_target(
    strategy: Any,
    target: float,
    symbol: Optional[str] = None,
    price: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """调整仓位到目标数量."""
    symbol = resolve_symbol(strategy, symbol)

    current_qty = 0.0
    if strategy.ctx:
        current_qty = float(strategy.ctx.get_position(symbol))

    delta_qty = target - current_qty

    if delta_qty > 0:
        buy(strategy, symbol, delta_qty, price, **kwargs)
    elif delta_qty < 0:
        sell(strategy, symbol, abs(delta_qty), price, **kwargs)


def order_target_value(
    strategy: Any,
    target_value: float,
    symbol: Optional[str] = None,
    price: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """调整仓位到目标价值."""
    symbol = resolve_symbol(strategy, symbol)

    cancel_all_orders(strategy, symbol=symbol)

    if price is not None:
        current_price = price
    else:
        current_price = strategy._last_prices.get(symbol, 0.0)

    if current_price == 0.0:
        if strategy.current_bar and strategy.current_bar.symbol == symbol:
            current_price = strategy.current_bar.close
        elif strategy.current_tick and strategy.current_tick.symbol == symbol:
            current_price = strategy.current_tick.price
        else:
            print(
                f"Warning: Cannot determine price for {symbol}, "
                "skipping order_target_value"
            )
            return

    current_qty = 0.0
    if strategy.ctx:
        current_qty = float(strategy.ctx.get_position(symbol))

    target_qty = target_value / current_price
    delta_qty = target_qty - current_qty

    current_lot_size = 1
    if isinstance(strategy.lot_size, int):
        current_lot_size = strategy.lot_size
    elif isinstance(strategy.lot_size, dict):
        val = strategy.lot_size.get(symbol, strategy.lot_size.get("DEFAULT", 1))
        current_lot_size = int(val) if val is not None else 1

    if current_lot_size > 0:
        if delta_qty > 0:
            delta_qty = (delta_qty // current_lot_size) * current_lot_size
        elif delta_qty < 0:
            delta_qty = -((abs(delta_qty) // current_lot_size) * current_lot_size)

    if delta_qty > 0 and strategy.ctx:
        max_buy_qty = calculate_max_buy_qty(
            strategy, symbol, current_price, float(strategy.ctx.cash)
        )
        if delta_qty > max_buy_qty:
            delta_qty = max_buy_qty

    if delta_qty > 0:
        buy(strategy, symbol, delta_qty, price, **kwargs)
    elif delta_qty < 0:
        sell(strategy, symbol, abs(delta_qty), price, **kwargs)


def order_target_percent(
    strategy: Any,
    target_percent: float,
    symbol: Optional[str] = None,
    price: Optional[float] = None,
    **kwargs: Any,
) -> None:
    """调整仓位到目标百分比."""
    portfolio_value = get_portfolio_value(strategy)
    target_value = portfolio_value * float(target_percent)
    order_target_value(strategy, target_value, symbol, price, **kwargs)


def order_target_weights(
    strategy: Any,
    target_weights: Dict[str, float],
    price_map: Optional[Dict[str, float]] = None,
    liquidate_unmentioned: bool = False,
    allow_leverage: bool = False,
    rebalance_tolerance: float = 0.0,
    **kwargs: Any,
) -> None:
    """按多标的目标权重调仓."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    if rebalance_tolerance < 0:
        raise ValueError("rebalance_tolerance must be >= 0")

    normalized_weights: Dict[str, float] = {}
    for symbol, weight in target_weights.items():
        if not symbol:
            raise ValueError("symbol in target_weights must be non-empty")
        normalized_weight = float(weight)
        if normalized_weight < 0:
            raise ValueError(f"target weight for {symbol} must be >= 0")
        normalized_weights[symbol] = normalized_weight

    total_weight = sum(normalized_weights.values())
    if not allow_leverage and total_weight > 1.0 + 1e-8:
        raise ValueError(
            f"sum of target_weights ({total_weight:.6f}) exceeds 1.0; "
            "set allow_leverage=True to permit this"
        )

    if liquidate_unmentioned:
        for symbol, qty in strategy.ctx.positions.items():
            if float(qty) != 0.0 and symbol not in normalized_weights:
                normalized_weights[symbol] = 0.0

    if not normalized_weights:
        return

    portfolio_value = get_portfolio_value(strategy)
    abs_tolerance_value = abs(float(portfolio_value)) * float(rebalance_tolerance)
    planned: List[Tuple[str, float, float]] = []

    for symbol, weight in normalized_weights.items():
        target_value = float(portfolio_value) * float(weight)
        current_qty = float(strategy.ctx.get_position(symbol))

        current_price = strategy._last_prices.get(symbol, 0.0)
        if current_price == 0.0:
            if strategy.current_bar and strategy.current_bar.symbol == symbol:
                current_price = strategy.current_bar.close
            elif strategy.current_tick and strategy.current_tick.symbol == symbol:
                current_price = strategy.current_tick.price

        current_value = current_qty * float(current_price)
        delta_value = target_value - current_value
        if abs(delta_value) <= abs_tolerance_value:
            continue
        planned.append((symbol, target_value, delta_value))

    if not planned:
        return

    sell_legs = [item for item in planned if item[2] < 0]
    buy_legs = [item for item in planned if item[2] >= 0]

    for symbol, target_value, _ in sorted(sell_legs, key=lambda item: item[2]):
        leg_price = price_map.get(symbol) if price_map else None
        order_target_value(strategy, target_value, symbol, leg_price, **kwargs)

    for symbol, target_value, _ in sorted(
        buy_legs, key=lambda item: item[2], reverse=True
    ):
        leg_price = price_map.get(symbol) if price_map else None
        order_target_value(strategy, target_value, symbol, leg_price, **kwargs)


def buy_all(strategy: Any, symbol: Optional[str] = None) -> None:
    """全仓买入 (Buy All)."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = resolve_symbol(strategy, symbol)

    price = 0.0
    if strategy.current_bar and strategy.current_bar.symbol == symbol:
        price = strategy.current_bar.close
    elif strategy.current_tick and strategy.current_tick.symbol == symbol:
        price = strategy.current_tick.price

    if price <= 0:
        return

    cash = strategy.ctx.cash
    quantity = int(cash / price)

    if quantity > 0:
        buy(strategy, symbol=symbol, quantity=quantity)


def close_position(strategy: Any, symbol: Optional[str] = None) -> None:
    """平仓 (Close Position)."""
    symbol = resolve_symbol(strategy, symbol)
    position = get_position(strategy, symbol)

    if position > 0:
        sell(strategy, symbol=symbol, quantity=position)
    elif position < 0:
        buy(strategy, symbol=symbol, quantity=abs(position))


def short(
    strategy: Any,
    symbol: Optional[str] = None,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
    trigger_price: Optional[float] = None,
) -> None:
    """卖出开空 (Short Sell)."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = resolve_symbol(strategy, symbol)

    ref_price = price
    if ref_price is None:
        if strategy.current_bar:
            ref_price = strategy.current_bar.close
        elif strategy.current_tick:
            ref_price = strategy.current_tick.price
        else:
            ref_price = 0.0

    if quantity is None:
        quantity = strategy.sizer.get_size(
            ref_price, strategy.ctx.cash, strategy.ctx, symbol
        )

    if quantity > 0:
        strategy.ctx.sell(symbol, quantity, price, time_in_force, trigger_price)


def cover(
    strategy: Any,
    symbol: Optional[str] = None,
    quantity: Optional[float] = None,
    price: Optional[float] = None,
    time_in_force: Optional[TimeInForce] = None,
    trigger_price: Optional[float] = None,
) -> None:
    """买入平空 (Buy to Cover)."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    symbol = resolve_symbol(strategy, symbol)

    if quantity is None:
        pos = strategy.ctx.get_position(symbol)
        if pos < 0:
            quantity = abs(pos)
        else:
            return

    if quantity > 0:
        strategy.ctx.buy(symbol, quantity, price, time_in_force, trigger_price)


def get_cash(strategy: Any) -> float:
    """获取现金."""
    if strategy.ctx is None:
        return 0.0
    return float(strategy.ctx.cash)
