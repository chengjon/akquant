from typing import Any, Dict, Optional, Tuple, cast

import pandas as pd

from .akquant import TradingSession

_RUNTIME_DEFAULTS = {
    "enable_precise_day_boundary_hooks": False,
    "portfolio_update_eps": 0.0,
    "error_mode": "raise",
    "re_raise_on_error": True,
}


def _runtime_option(strategy: Any, name: str) -> Any:
    default = _RUNTIME_DEFAULTS[name]
    cfg = getattr(strategy, "runtime_config", None)
    if isinstance(cfg, dict):
        value = cfg.get(name, default)
    else:
        value = getattr(cfg, name, default) if cfg is not None else default
    if name == "portfolio_update_eps":
        try:
            value = float(cast(Any, value))
        except (TypeError, ValueError):
            raise ValueError("portfolio_update_eps must be >= 0") from None
        if value < 0.0:
            raise ValueError("portfolio_update_eps must be >= 0")
    if name == "error_mode":
        mode = str(value).strip().lower()
        if mode not in {"raise", "continue", "legacy"}:
            raise ValueError("error_mode must be one of: raise, continue, legacy")
        value = mode
    return value


def _is_normal_session(session: Any) -> bool:
    normal = getattr(TradingSession, "Normal", None)
    if normal is not None:
        return bool(session == normal)
    text = str(session).lower()
    return text == "normal" or text.endswith(".normal")


def _should_reraise_on_error(strategy: Any) -> bool:
    mode = str(_runtime_option(strategy, "error_mode")).strip().lower()
    if mode == "raise":
        return True
    if mode == "continue":
        return False
    return bool(_runtime_option(strategy, "re_raise_on_error"))


def call_user_callback(
    strategy: Any, callback_name: str, *args: Any, payload: Optional[Any] = None
) -> Any:
    """调用用户回调，并在异常时转发到 on_error."""
    callback = getattr(strategy, callback_name)
    try:
        return callback(*args)
    except Exception as exc:
        if callback_name != "on_error":
            error_payload = (
                payload if payload is not None else (args[0] if args else None)
            )
            try:
                strategy.on_error(exc, callback_name, error_payload)
            except Exception:
                pass
            if not _should_reraise_on_error(strategy):
                return None
        raise


def dispatch_time_hooks(strategy: Any) -> None:
    """分发会话与交易日相关钩子."""
    if strategy.ctx is None:
        return

    current_time = int(getattr(strategy.ctx, "current_time", 0))
    if current_time <= 0:
        return

    ts = pd.to_datetime(current_time, unit="ns", utc=True).tz_convert(strategy.timezone)
    current_date = ts.date()
    current_session = getattr(strategy.ctx, "session", None)

    last_date = getattr(strategy, "_framework_last_local_date", None)
    before_done_date = getattr(strategy, "_framework_before_trading_done_date", None)
    after_done_date = getattr(strategy, "_framework_after_trading_done_date", None)

    if (
        last_date is not None
        and current_date != last_date
        and before_done_date == last_date
        and after_done_date != last_date
    ):
        call_user_callback(
            strategy,
            "after_trading",
            last_date,
            current_time,
            payload={"trading_date": last_date, "timestamp": current_time},
        )
        strategy._framework_after_trading_done_date = last_date

    last_session = getattr(strategy, "_framework_last_session", None)
    if current_session != last_session:
        if last_session is not None:
            call_user_callback(
                strategy,
                "on_session_end",
                last_session,
                current_time,
                payload={"session": last_session, "timestamp": current_time},
            )
        if current_session is not None:
            call_user_callback(
                strategy,
                "on_session_start",
                current_session,
                current_time,
                payload={"session": current_session, "timestamp": current_time},
            )

    if (
        _is_normal_session(current_session)
        and getattr(strategy, "_framework_before_trading_done_date", None)
        != current_date
    ):
        call_user_callback(
            strategy,
            "before_trading",
            current_date,
            current_time,
            payload={"trading_date": current_date, "timestamp": current_time},
        )
        strategy._framework_before_trading_done_date = current_date

    if (
        not _is_normal_session(current_session)
        and getattr(strategy, "_framework_before_trading_done_date", None)
        == current_date
        and getattr(strategy, "_framework_after_trading_done_date", None)
        != current_date
    ):
        call_user_callback(
            strategy,
            "after_trading",
            current_date,
            current_time,
            payload={"trading_date": current_date, "timestamp": current_time},
        )
        strategy._framework_after_trading_done_date = current_date

    strategy._framework_last_session = current_session
    strategy._framework_last_local_date = current_date


def register_boundary_timers(strategy: Any) -> None:
    """注册交易日边界定时器，用于精确触发 before/after_trading."""
    if strategy.ctx is None:
        return
    if not bool(_runtime_option(strategy, "enable_precise_day_boundary_hooks")):
        return
    if getattr(strategy, "_framework_boundary_timers_registered", False):
        return

    bounds = getattr(strategy, "_trading_day_bounds", None)
    if not bounds:
        strategy._framework_boundary_timers_registered = True
        return

    for day_key, day_bounds in bounds.items():
        if not isinstance(day_bounds, (list, tuple)) or len(day_bounds) != 2:
            continue
        start_ns = int(day_bounds[0])
        end_ns = int(day_bounds[1])
        if start_ns > 0:
            strategy.ctx.schedule(start_ns, f"__framework_boundary__|before|{day_key}")
        if end_ns > 0:
            strategy.ctx.schedule(end_ns + 1, f"__framework_boundary__|after|{day_key}")

    strategy._framework_boundary_timers_registered = True


def dispatch_boundary_timer(strategy: Any, payload: str) -> bool:
    """处理框架级边界定时器，返回是否已消费该 payload."""
    if strategy.ctx is None:
        return False
    if not bool(_runtime_option(strategy, "enable_precise_day_boundary_hooks")):
        return False
    if not payload.startswith("__framework_boundary__|"):
        return False

    parts = payload.split("|", 2)
    if len(parts) != 3:
        return True

    _, phase, day_text = parts
    try:
        day = pd.Timestamp(day_text).date()
    except Exception:
        return True

    current_time = int(getattr(strategy.ctx, "current_time", 0))
    if phase == "before":
        if getattr(strategy, "_framework_before_trading_done_date", None) != day:
            call_user_callback(
                strategy,
                "before_trading",
                day,
                current_time,
                payload={"trading_date": day, "timestamp": current_time},
            )
            strategy._framework_before_trading_done_date = day
        return True

    if phase == "after":
        if getattr(strategy, "_framework_after_trading_done_date", None) != day:
            call_user_callback(
                strategy,
                "after_trading",
                day,
                current_time,
                payload={"trading_date": day, "timestamp": current_time},
            )
            strategy._framework_after_trading_done_date = day
        return True

    return True


def mark_portfolio_dirty(strategy: Any) -> None:
    """标记账户快照需要重新计算."""
    strategy._framework_portfolio_dirty = True


def dispatch_portfolio_update(strategy: Any) -> None:
    """在账户状态变化时分发 on_portfolio_update."""
    if strategy.ctx is None:
        return
    if (
        not getattr(strategy, "_framework_portfolio_dirty", True)
        and getattr(strategy, "_framework_last_portfolio_state", None) is not None
    ):
        return

    current_time = int(getattr(strategy.ctx, "current_time", 0))
    session = getattr(strategy.ctx, "session", None)
    cash = float(strategy.ctx.cash)
    positions = {k: float(v) for k, v in dict(strategy.ctx.positions).items()}
    available_positions = {
        k: float(v) for k, v in dict(strategy.ctx.available_positions).items()
    }
    equity = float(strategy.get_portfolio_value())
    market_value = float(equity - cash)

    state_key: Tuple[Any, ...] = (
        round(cash, 8),
        round(equity, 8),
        tuple(sorted((k, round(v, 8)) for k, v in positions.items())),
        tuple(sorted((k, round(v, 8)) for k, v in available_positions.items())),
    )

    if state_key == getattr(strategy, "_framework_last_portfolio_state", None):
        strategy._framework_portfolio_dirty = False
        return

    eps = float(_runtime_option(strategy, "portfolio_update_eps"))
    last_state = getattr(strategy, "_framework_last_portfolio_state", None)
    if eps > 0.0 and last_state is not None:
        last_positions = last_state[2]
        last_available_positions = last_state[3]
        if (
            state_key[2] == last_positions
            and state_key[3] == last_available_positions
            and abs(cash - float(last_state[0])) <= eps
            and abs(equity - float(last_state[1])) <= eps
        ):
            strategy._framework_portfolio_dirty = False
        return

    strategy._framework_last_portfolio_state = state_key
    snapshot: Dict[str, Any] = {
        "timestamp": current_time,
        "session": session,
        "cash": cash,
        "equity": equity,
        "market_value": market_value,
        "positions": positions,
        "available_positions": available_positions,
        "margin": 0.0,
    }
    call_user_callback(strategy, "on_portfolio_update", snapshot, payload=snapshot)
    strategy._framework_portfolio_dirty = False


def dispatch_shutdown_hooks(strategy: Any) -> None:
    """在停止阶段补发未完成的会话/交易日钩子."""
    if strategy.ctx is None:
        return
    if getattr(strategy, "_framework_stop_flushed", False):
        return

    current_time = int(getattr(strategy.ctx, "current_time", 0))
    last_session = getattr(strategy, "_framework_last_session", None)
    if last_session is not None:
        call_user_callback(
            strategy,
            "on_session_end",
            last_session,
            current_time,
            payload={"session": last_session, "timestamp": current_time},
        )
        strategy._framework_last_session = None

    before_done_date = getattr(strategy, "_framework_before_trading_done_date", None)
    after_done_date = getattr(strategy, "_framework_after_trading_done_date", None)
    if before_done_date is not None and after_done_date != before_done_date:
        call_user_callback(
            strategy,
            "after_trading",
            before_done_date,
            current_time,
            payload={"trading_date": before_done_date, "timestamp": current_time},
        )
        strategy._framework_after_trading_done_date = before_done_date

    strategy._framework_stop_flushed = True


def ensure_framework_state(strategy: Any) -> None:
    """确保框架级钩子状态字段存在."""
    if not hasattr(strategy, "_framework_last_session"):
        strategy._framework_last_session = None
    if not hasattr(strategy, "_framework_last_local_date"):
        strategy._framework_last_local_date = None
    if not hasattr(strategy, "_framework_before_trading_done_date"):
        strategy._framework_before_trading_done_date = None
    if not hasattr(strategy, "_framework_after_trading_done_date"):
        strategy._framework_after_trading_done_date = None
    if not hasattr(strategy, "_framework_last_portfolio_state"):
        strategy._framework_last_portfolio_state = None
    if not hasattr(strategy, "_framework_portfolio_dirty"):
        strategy._framework_portfolio_dirty = True
    if not hasattr(strategy, "_framework_rejected_order_ids"):
        strategy._framework_rejected_order_ids = set()
    if not hasattr(strategy, "_framework_stop_flushed"):
        strategy._framework_stop_flushed = False
    if not hasattr(strategy, "_framework_boundary_timers_registered"):
        strategy._framework_boundary_timers_registered = False
    if not hasattr(strategy, "_trading_day_bounds"):
        strategy._trading_day_bounds = {}
