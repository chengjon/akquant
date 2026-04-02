from typing import Any, Dict, List, Optional, Tuple, cast

from .akquant import OrderSide, OrderStatus, OrderType, TimeInForce

OrderFillPolicy = Dict[str, Any]
OrderSlippage = Dict[str, Any]
OrderCommission = Dict[str, Any]


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
        order = strategy._known_orders[order_id]
        _attach_broker_options(strategy, order_id, order)
        return order

    if strategy.ctx:
        for o in strategy.ctx.active_orders:
            if o.id == order_id:
                _attach_broker_options(strategy, order_id, o)
                return o
    return None


def _record_broker_options(
    strategy: Any, order_id: Optional[str], broker_options: Optional[Dict[str, Any]]
) -> None:
    if not order_id or not broker_options:
        return
    if not isinstance(broker_options, dict):
        raise TypeError("broker_options must be a dict when provided")
    store = getattr(strategy, "_broker_options_by_order_id", None)
    if not isinstance(store, dict):
        store = {}
        setattr(strategy, "_broker_options_by_order_id", store)
    normalized = dict(broker_options)
    store[str(order_id)] = normalized
    order = get_order(strategy, str(order_id))
    if order is not None:
        _attach_broker_options(strategy, str(order_id), order)


def _attach_broker_options(strategy: Any, order_id: str, order: Any) -> None:
    store = getattr(strategy, "_broker_options_by_order_id", None)
    if not isinstance(store, dict):
        return
    options = store.get(str(order_id))
    if not isinstance(options, dict):
        return
    try:
        setattr(order, "broker_options", dict(options))
    except Exception:
        return


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
    fill_policy: Optional[OrderFillPolicy] = None,
    slippage: Optional[OrderSlippage] = None,
    commission: Optional[OrderCommission] = None,
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
                fill_policy=fill_policy,
                slippage=slippage,
                commission=commission,
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
        fill_policy=fill_policy,
        slippage=slippage,
        commission=commission,
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
    fill_policy: Optional[OrderFillPolicy] = None,
    slippage: Optional[OrderSlippage] = None,
    commission: Optional[OrderCommission] = None,
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
                fill_policy=fill_policy,
                slippage=slippage,
                commission=commission,
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
        fill_policy=fill_policy,
        slippage=slippage,
        commission=commission,
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
    fill_policy: Optional[OrderFillPolicy] = None,
    slippage: Optional[OrderSlippage] = None,
    commission: Optional[OrderCommission] = None,
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

    effective_fill_policy = _resolve_effective_order_fill_policy(strategy, fill_policy)
    fill_price_basis, fill_bar_offset, fill_temporal = _normalize_order_fill_policy(
        effective_fill_policy
    )
    effective_slippage = _resolve_effective_order_slippage(strategy, slippage)
    fill_slippage_type, fill_slippage_value = _normalize_order_slippage(
        effective_slippage
    )
    effective_commission = _resolve_effective_order_commission(strategy, commission)
    fill_commission_type, fill_commission_value = _normalize_order_commission(
        effective_commission
    )
    if quantity > 0:
        if (
            order_type is None
            and trail_offset is None
            and trail_reference_price is None
            and effective_fill_policy is None
            and effective_slippage is None
            and effective_commission is None
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
                fill_price_basis,
                fill_bar_offset,
                fill_temporal,
                fill_slippage_type,
                fill_slippage_value,
                fill_commission_type,
                fill_commission_value,
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
    fill_policy: Optional[OrderFillPolicy] = None,
    slippage: Optional[OrderSlippage] = None,
    commission: Optional[OrderCommission] = None,
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

    effective_fill_policy = _resolve_effective_order_fill_policy(strategy, fill_policy)
    fill_price_basis, fill_bar_offset, fill_temporal = _normalize_order_fill_policy(
        effective_fill_policy
    )
    effective_slippage = _resolve_effective_order_slippage(strategy, slippage)
    fill_slippage_type, fill_slippage_value = _normalize_order_slippage(
        effective_slippage
    )
    effective_commission = _resolve_effective_order_commission(strategy, commission)
    fill_commission_type, fill_commission_value = _normalize_order_commission(
        effective_commission
    )
    if quantity > 0:
        if (
            order_type is None
            and trail_offset is None
            and trail_reference_price is None
            and effective_fill_policy is None
            and effective_slippage is None
            and effective_commission is None
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
                fill_price_basis,
                fill_bar_offset,
                fill_temporal,
                fill_slippage_type,
                fill_slippage_value,
                fill_commission_type,
                fill_commission_value,
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
    broker_options: Optional[Dict[str, Any]] = None,
    trail_offset: Optional[float] = None,
    trail_reference_price: Optional[float] = None,
    fill_policy: Optional[OrderFillPolicy] = None,
    slippage: Optional[OrderSlippage] = None,
    commission: Optional[OrderCommission] = None,
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
        order_id = _submit_buy_side(
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
            fill_policy=fill_policy,
            slippage=slippage,
            commission=commission,
        )
        _record_broker_options(strategy, order_id, broker_options)
        return order_id
    if side_text == "sell":
        order_id = _submit_sell_side(
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
            fill_policy=fill_policy,
            slippage=slippage,
            commission=commission,
        )
        _record_broker_options(strategy, order_id, broker_options)
        return order_id
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


def _normalize_order_fill_policy(
    fill_policy: Optional[OrderFillPolicy],
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    if fill_policy is None:
        return None, None, None
    if not isinstance(fill_policy, dict):
        raise TypeError("fill_policy must be a dict when provided")
    raw_basis = str(fill_policy.get("price_basis", "open")).strip().lower()
    raw_temporal = str(fill_policy.get("temporal", "same_cycle")).strip().lower()
    if raw_basis not in {"open", "close", "ohlc4", "hl2"}:
        raise ValueError(
            "fill_policy.price_basis must be one of: open, close, ohlc4, hl2"
        )
    if raw_temporal not in {"same_cycle", "next_event"}:
        raise ValueError("fill_policy.temporal must be one of: same_cycle, next_event")
    raw_offset_value = fill_policy.get(
        "bar_offset",
        0 if raw_basis == "close" else 1,
    )
    try:
        raw_offset = int(raw_offset_value)
    except (TypeError, ValueError):
        raise ValueError("fill_policy.bar_offset must be 0 or 1") from None
    if raw_offset not in {0, 1}:
        raise ValueError("fill_policy.bar_offset must be 0 or 1")
    if raw_basis in {"open", "ohlc4", "hl2"} and raw_offset != 1:
        raise ValueError(f"fill_policy({raw_basis}) requires bar_offset=1")
    return raw_basis, raw_offset, raw_temporal


def _normalize_order_slippage(
    slippage: Optional[OrderSlippage],
) -> Tuple[Optional[str], Optional[float]]:
    if slippage is None:
        return None, None
    if not isinstance(slippage, dict):
        raise TypeError("slippage must be a dict when provided")
    raw_type = str(slippage.get("type", "percent")).strip().lower()
    if raw_type not in {"percent", "fixed"}:
        raise ValueError("slippage.type must be one of: percent, fixed")
    raw_value = slippage.get("value", 0.0)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError("slippage.value must be a number >= 0") from None
    if value < 0:
        raise ValueError("slippage.value must be >= 0")
    return raw_type, value


def _normalize_order_commission(
    commission: Optional[OrderCommission],
) -> Tuple[Optional[str], Optional[float]]:
    if commission is None:
        return None, None
    if not isinstance(commission, dict):
        raise TypeError("commission must be a dict when provided")
    raw_type = str(commission.get("type", "percent")).strip().lower()
    if raw_type not in {"percent", "fixed"}:
        raise ValueError("commission.type must be one of: percent, fixed")
    raw_value = commission.get("value", 0.0)
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError("commission.value must be a number >= 0") from None
    if value < 0:
        raise ValueError("commission.value must be >= 0")
    return raw_type, value


def _resolve_effective_order_fill_policy(
    strategy: Any, fill_policy: Optional[OrderFillPolicy]
) -> Optional[OrderFillPolicy]:
    if fill_policy is not None:
        return fill_policy
    owner_strategy_id = str(getattr(strategy, "_owner_strategy_id", "") or "").strip()
    if not owner_strategy_id:
        owner_strategy_id = "_default"
    policy_map = cast(
        Optional[Dict[str, OrderFillPolicy]],
        getattr(strategy, "_strategy_fill_policy_map", None),
    )
    if not policy_map:
        return None
    policy = policy_map.get(owner_strategy_id)
    if policy is None and owner_strategy_id != "_default":
        policy = policy_map.get("_default")
    if policy is None:
        return None
    return dict(policy)


def _resolve_effective_order_slippage(
    strategy: Any, slippage: Optional[OrderSlippage]
) -> Optional[OrderSlippage]:
    if slippage is not None:
        return slippage
    owner_strategy_id = str(getattr(strategy, "_owner_strategy_id", "") or "").strip()
    if not owner_strategy_id:
        owner_strategy_id = "_default"
    slippage_map = cast(
        Optional[Dict[str, OrderSlippage]],
        getattr(strategy, "_strategy_slippage_map", None),
    )
    if not slippage_map:
        return None
    resolved = slippage_map.get(owner_strategy_id)
    if resolved is None and owner_strategy_id != "_default":
        resolved = slippage_map.get("_default")
    if resolved is None:
        return None
    return dict(resolved)


def _resolve_effective_order_commission(
    strategy: Any, commission: Optional[OrderCommission]
) -> Optional[OrderCommission]:
    if commission is not None:
        return commission
    owner_strategy_id = str(getattr(strategy, "_owner_strategy_id", "") or "").strip()
    if not owner_strategy_id:
        owner_strategy_id = "_default"
    commission_map = cast(
        Optional[Dict[str, OrderCommission]],
        getattr(strategy, "_strategy_commission_map", None),
    )
    if not commission_map:
        return None
    resolved = commission_map.get(owner_strategy_id)
    if resolved is None and owner_strategy_id != "_default":
        resolved = commission_map.get("_default")
    if resolved is None:
        return None
    return dict(resolved)


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


def _resolve_mark_price(strategy: Any, symbol: str) -> float:
    price = float(strategy._last_prices.get(symbol, 0.0))
    if price > 0.0:
        return price
    if strategy.current_bar and strategy.current_bar.symbol == symbol:
        return float(strategy.current_bar.close)
    if strategy.current_tick and strategy.current_tick.symbol == symbol:
        return float(strategy.current_tick.price)
    return 0.0


def _is_margin_account(strategy: Any) -> bool:
    if strategy.ctx is None:
        return False
    risk_config = getattr(strategy.ctx, "risk_config", None)
    account_mode = str(getattr(risk_config, "account_mode", "cash")).strip().lower()
    return account_mode == "margin"


def _stock_margin_ratio(strategy: Any, margin_ratio: float) -> float:
    if not _is_margin_account(strategy):
        return margin_ratio
    if strategy.ctx is None:
        return margin_ratio
    risk_config = getattr(strategy.ctx, "risk_config", None)
    ratio = float(getattr(risk_config, "initial_margin_ratio", margin_ratio))
    if ratio <= 0.0:
        return margin_ratio
    return ratio


def _calc_position_margin(strategy: Any, symbol: str, quantity: float) -> float:
    if quantity == 0.0:
        return 0.0
    try:
        inst = strategy.get_instrument(symbol)
    except Exception:
        price = _resolve_mark_price(strategy, symbol)
        return abs(float(quantity) * float(price))

    qty = float(quantity)
    price = _resolve_mark_price(strategy, symbol)
    multiplier = float(inst.multiplier)
    margin_ratio = float(inst.margin_ratio)
    asset_type = str(inst.asset_type).upper()

    if asset_type == "OPTION":
        if qty > 0:
            return 0.0
        underlying_symbol = (
            str(inst.underlying_symbol) if inst.underlying_symbol else ""
        )
        underlying_price = (
            _resolve_mark_price(strategy, underlying_symbol)
            if underlying_symbol
            else 0.0
        )
        if underlying_price > 0.0:
            margin_per_unit = price + underlying_price * margin_ratio
        else:
            margin_per_unit = price * (1.0 + margin_ratio)
        return max(margin_per_unit, 0.0) * multiplier * abs(qty)

    if asset_type in {"STOCK", "FUND"}:
        margin_ratio = _stock_margin_ratio(strategy, margin_ratio)
    return abs(qty * price * multiplier) * margin_ratio


def _calc_used_margin(strategy: Any) -> float:
    if strategy.ctx is None:
        return 0.0
    total = 0.0
    for sym, qty in strategy.ctx.positions.items():
        total += _calc_position_margin(strategy, str(sym), float(qty))
    return total


def _calc_frozen_cash(strategy: Any) -> float:
    if strategy.ctx is None:
        return 0.0
    frozen = 0.0
    for order in get_open_orders(strategy):
        qty = max(float(order.quantity) - float(order.filled_quantity), 0.0)
        if qty <= 0.0:
            continue
        symbol = str(order.symbol)
        current_pos = float(strategy.ctx.positions.get(symbol, 0.0))
        if order.side == OrderSide.Buy:
            next_pos = current_pos + qty
        elif order.side == OrderSide.Sell:
            next_pos = current_pos - qty
        else:
            continue
        current_margin = _calc_position_margin(strategy, symbol, current_pos)
        next_margin = _calc_position_margin(strategy, symbol, next_pos)
        frozen += max(next_margin - current_margin, 0.0)
    return frozen


def get_account(strategy: Any) -> Dict[str, Any]:
    """获取账户资金详情快照."""
    if strategy.ctx is None:
        raise RuntimeError("Context not ready")

    cash = float(strategy.ctx.cash)
    equity = float(strategy.equity)
    market_value = float(equity - cash)
    margin = float(_calc_used_margin(strategy))
    frozen_cash = float(_calc_frozen_cash(strategy))
    borrowed_cash = float(max(-cash, 0.0))
    short_market_value = 0.0
    for sym, qty in strategy.ctx.positions.items():
        qty_f = float(qty)
        if qty_f >= 0.0:
            continue
        short_market_value += abs(qty_f) * _resolve_mark_price(strategy, str(sym))
    denominator = market_value + short_market_value
    maintenance_ratio = float(equity / denominator) if denominator > 0.0 else 0.0
    account_mode = "margin" if _is_margin_account(strategy) else "cash"
    accrued_interest = float(getattr(strategy.ctx, "margin_accrued_interest", 0.0))
    daily_interest = float(getattr(strategy.ctx, "margin_daily_interest", 0.0))
    return {
        "cash": cash,
        "equity": equity,
        "market_value": market_value,
        "frozen_cash": frozen_cash,
        "margin": margin,
        "borrowed_cash": borrowed_cash,
        "short_market_value": float(short_market_value),
        "maintenance_ratio": maintenance_ratio,
        "account_mode": account_mode,
        "accrued_interest": accrued_interest,
        "daily_interest": daily_interest,
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
