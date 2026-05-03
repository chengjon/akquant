"""Backtest validation and normalization helpers."""

import logging
import os
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import pandas as pd

from ..akquant import Bar
from ..strategy import Strategy, StrategyRuntimeConfig
from ._execution import _resolve_execution_policy
from ._types import (
    CommissionPolicy,
    FillPolicy,
    SlippagePolicy,
)

_BROKER_PROFILE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "cn_stock_miniqmt": {
        "commission_rate": 0.0003,
        "stamp_tax_rate": 0.001,
        "transfer_fee_rate": 0.00001,
        "min_commission": 5.0,
        "slippage": 0.0002,
        "volume_limit_pct": 0.2,
        "lot_size": 100,
    },
    "cn_stock_t1_low_fee": {
        "commission_rate": 0.0002,
        "stamp_tax_rate": 0.001,
        "transfer_fee_rate": 0.000005,
        "min_commission": 3.0,
        "slippage": 0.0001,
        "volume_limit_pct": 0.25,
        "lot_size": 100,
    },
    "cn_stock_sim_high_slippage": {
        "commission_rate": 0.0003,
        "stamp_tax_rate": 0.001,
        "transfer_fee_rate": 0.00001,
        "min_commission": 5.0,
        "slippage": 0.001,
        "volume_limit_pct": 0.1,
        "lot_size": 100,
    },
}


def _normalize_symbols_argument(
    symbols: Union[str, List[str], Tuple[str, ...], set[str]],
    *,
    api_name: str,
) -> List[str]:
    """Normalize symbols input."""
    if isinstance(symbols, str):
        normalized = [symbols]
    elif isinstance(symbols, (list, tuple, set)):
        normalized = [str(item) for item in symbols]
    else:
        raise TypeError("symbols must be str, list, tuple, or set")

    cleaned: List[str] = []
    seen: set[str] = set()
    for item in normalized:
        value = str(item).strip()
        if not value:
            raise ValueError("symbols cannot contain empty values")
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)

    if not cleaned:
        raise ValueError("symbols cannot be empty")
    return cleaned


def _resolve_effective_symbols(
    *,
    symbols: Union[str, List[str], Tuple[str, ...], set[str], None],
    kwargs: Dict[str, Any],
    api_name: str,
) -> Tuple[Union[str, List[str], Tuple[str, ...], set[str]], List[str]]:
    if "symbol" in kwargs:
        raise ValueError(
            f"{api_name} no longer accepts `symbol`; please use `symbols` only"
        )

    if symbols is None and "symbols" in kwargs:
        symbols = cast(
            Union[str, List[str], Tuple[str, ...], set[str]],
            kwargs.pop("symbols"),
        )
    elif "symbols" in kwargs:
        kwargs.pop("symbols")
    if symbols is None:
        symbols = "BENCHMARK"
    effective_symbols = _normalize_symbols_argument(
        symbols=symbols,
        api_name=api_name,
    )
    return symbols, effective_symbols


def _resolve_broker_profile(profile: Optional[str]) -> Dict[str, Any]:
    if profile is None:
        return {}
    key = str(profile).strip().lower()
    if not key:
        return {}
    if key not in _BROKER_PROFILE_TEMPLATES:
        available = ", ".join(sorted(_BROKER_PROFILE_TEMPLATES.keys()))
        raise ValueError(
            f"Unknown broker_profile '{profile}', available profiles: {available}"
        )
    return dict(_BROKER_PROFILE_TEMPLATES[key])


def _resolve_stock_fee_rules(
    *,
    commission_rate: Optional[float],
    stamp_tax_rate: Optional[float],
    transfer_fee_rate: Optional[float],
    min_commission: Optional[float],
    broker_profile_values: Dict[str, Any],
    strategy_config: Optional[Any],
) -> Tuple[float, float, float, float]:
    resolved_commission_rate = commission_rate
    resolved_stamp_tax_rate = stamp_tax_rate
    resolved_transfer_fee_rate = transfer_fee_rate
    resolved_min_commission = min_commission

    if resolved_commission_rate is None:
        resolved_commission_rate = cast(
            Optional[float], broker_profile_values.get("commission_rate")
        )
    if resolved_stamp_tax_rate is None:
        resolved_stamp_tax_rate = cast(
            Optional[float], broker_profile_values.get("stamp_tax_rate")
        )
    if resolved_transfer_fee_rate is None:
        resolved_transfer_fee_rate = cast(
            Optional[float], broker_profile_values.get("transfer_fee_rate")
        )
    if resolved_min_commission is None:
        resolved_min_commission = cast(
            Optional[float], broker_profile_values.get("min_commission")
        )

    if strategy_config is not None:
        if resolved_commission_rate is None:
            resolved_commission_rate = cast(
                Optional[float], getattr(strategy_config, "commission_rate", None)
            )
        if resolved_stamp_tax_rate is None:
            resolved_stamp_tax_rate = cast(
                Optional[float], getattr(strategy_config, "stamp_tax_rate", None)
            )
        if resolved_transfer_fee_rate is None:
            resolved_transfer_fee_rate = cast(
                Optional[float], getattr(strategy_config, "transfer_fee_rate", None)
            )
        if resolved_min_commission is None:
            resolved_min_commission = cast(
                Optional[float], getattr(strategy_config, "min_commission", None)
            )

    return (
        float(
            resolved_commission_rate if resolved_commission_rate is not None else 0.0
        ),
        float(resolved_stamp_tax_rate if resolved_stamp_tax_rate is not None else 0.0),
        float(resolved_transfer_fee_rate or 0.0),
        float(resolved_min_commission or 0.0),
    )


def _apply_strategy_config_overrides(
    *,
    strategy_config: Optional[Any],
    strategy_id: Optional[str],
    strategies_by_slot: Optional[
        Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
    ],
    strategy_max_order_value: Optional[Dict[str, float]],
    strategy_max_order_size: Optional[Dict[str, float]],
    strategy_max_position_size: Optional[Dict[str, float]],
    strategy_max_daily_loss: Optional[Dict[str, float]],
    strategy_max_drawdown: Optional[Dict[str, float]],
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]],
    strategy_risk_cooldown_bars: Optional[Dict[str, int]],
    strategy_priority: Optional[Dict[str, int]],
    strategy_risk_budget: Optional[Dict[str, float]],
    strategy_fill_policy: Optional[Dict[str, FillPolicy]],
    strategy_slippage: Optional[Dict[str, SlippagePolicy]],
    strategy_commission: Optional[Dict[str, CommissionPolicy]],
    portfolio_risk_budget: Optional[float],
    strategy_runtime_config: Optional[Union[StrategyRuntimeConfig, Dict[str, Any]]],
    strategy_source: Optional[Union[str, bytes, os.PathLike[str]]],
    strategy_loader: Optional[str],
    strategy_loader_options: Optional[Dict[str, Any]],
) -> Tuple[
    Optional[str],
    Optional[Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, float]],
    Optional[Dict[str, bool]],
    Optional[Dict[str, int]],
    Optional[Dict[str, int]],
    Optional[Dict[str, float]],
    Optional[Dict[str, FillPolicy]],
    Optional[Dict[str, SlippagePolicy]],
    Optional[Dict[str, CommissionPolicy]],
    Optional[float],
    Optional[Union[StrategyRuntimeConfig, Dict[str, Any]]],
    Optional[Union[str, bytes, os.PathLike[str]]],
    Optional[str],
    Optional[Dict[str, Any]],
]:
    if strategy_config is None:
        return (
            strategy_id,
            strategies_by_slot,
            strategy_max_order_value,
            strategy_max_order_size,
            strategy_max_position_size,
            strategy_max_daily_loss,
            strategy_max_drawdown,
            strategy_reduce_only_after_risk,
            strategy_risk_cooldown_bars,
            strategy_priority,
            strategy_risk_budget,
            strategy_fill_policy,
            strategy_slippage,
            strategy_commission,
            portfolio_risk_budget,
            strategy_runtime_config,
            strategy_source,
            strategy_loader,
            strategy_loader_options,
        )

    if strategy_id is None:
        strategy_id = cast(Optional[str], getattr(strategy_config, "strategy_id", None))
    if strategies_by_slot is None:
        strategies_by_slot = cast(
            Optional[
                Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
            ],
            getattr(strategy_config, "strategies_by_slot", None),
        )
    if strategy_max_order_value is None:
        strategy_max_order_value = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_max_order_value", None),
        )
    if strategy_max_order_size is None:
        strategy_max_order_size = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_max_order_size", None),
        )
    if strategy_max_position_size is None:
        strategy_max_position_size = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_max_position_size", None),
        )
    if strategy_max_daily_loss is None:
        strategy_max_daily_loss = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_max_daily_loss", None),
        )
    if strategy_max_drawdown is None:
        strategy_max_drawdown = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_max_drawdown", None),
        )
    if strategy_reduce_only_after_risk is None:
        strategy_reduce_only_after_risk = cast(
            Optional[Dict[str, bool]],
            getattr(strategy_config, "strategy_reduce_only_after_risk", None),
        )
    if strategy_risk_cooldown_bars is None:
        strategy_risk_cooldown_bars = cast(
            Optional[Dict[str, int]],
            getattr(strategy_config, "strategy_risk_cooldown_bars", None),
        )
    if strategy_priority is None:
        strategy_priority = cast(
            Optional[Dict[str, int]],
            getattr(strategy_config, "strategy_priority", None),
        )
    if strategy_risk_budget is None:
        strategy_risk_budget = cast(
            Optional[Dict[str, float]],
            getattr(strategy_config, "strategy_risk_budget", None),
        )
    if strategy_fill_policy is None:
        strategy_fill_policy = cast(
            Optional[Dict[str, FillPolicy]],
            getattr(strategy_config, "strategy_fill_policy", None),
        )
    if strategy_slippage is None:
        strategy_slippage = cast(
            Optional[Dict[str, SlippagePolicy]],
            getattr(strategy_config, "strategy_slippage", None),
        )
    if strategy_commission is None:
        strategy_commission = cast(
            Optional[Dict[str, CommissionPolicy]],
            getattr(strategy_config, "strategy_commission", None),
        )
    if portfolio_risk_budget is None:
        portfolio_risk_budget = cast(
            Optional[float],
            getattr(strategy_config, "portfolio_risk_budget", None),
        )
    if strategy_runtime_config is None:
        config_indicator_mode = getattr(strategy_config, "indicator_mode", None)
        if config_indicator_mode is not None:
            strategy_runtime_config = {"indicator_mode": config_indicator_mode}
    if strategy_source is None:
        strategy_source = cast(
            Optional[Union[str, bytes, os.PathLike[str]]],
            getattr(strategy_config, "strategy_source", None),
        )
    if strategy_loader is None:
        strategy_loader = cast(
            Optional[str],
            getattr(strategy_config, "strategy_loader", None),
        )
    if strategy_loader_options is None:
        strategy_loader_options = cast(
            Optional[Dict[str, Any]],
            getattr(strategy_config, "strategy_loader_options", None),
        )

    return (
        strategy_id,
        strategies_by_slot,
        strategy_max_order_value,
        strategy_max_order_size,
        strategy_max_position_size,
        strategy_max_daily_loss,
        strategy_max_drawdown,
        strategy_reduce_only_after_risk,
        strategy_risk_cooldown_bars,
        strategy_priority,
        strategy_risk_budget,
        strategy_fill_policy,
        strategy_slippage,
        strategy_commission,
        portfolio_risk_budget,
        strategy_runtime_config,
        strategy_source,
        strategy_loader,
        strategy_loader_options,
    )


def _validate_strategy_risk_inputs(
    *,
    strategies_by_slot: Optional[
        Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
    ],
    strategy_max_order_value: Optional[Dict[str, float]],
    strategy_max_order_size: Optional[Dict[str, float]],
    strategy_max_position_size: Optional[Dict[str, float]],
    strategy_max_daily_loss: Optional[Dict[str, float]],
    strategy_max_drawdown: Optional[Dict[str, float]],
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]],
    strategy_risk_cooldown_bars: Optional[Dict[str, int]],
    strategy_priority: Optional[Dict[str, int]],
    strategy_risk_budget: Optional[Dict[str, float]],
    portfolio_risk_budget: Optional[float],
    risk_budget_mode: str,
) -> Tuple[Optional[float], str]:
    if strategies_by_slot is not None and not isinstance(strategies_by_slot, dict):
        raise TypeError("strategies_by_slot must be a dict when provided")
    if strategy_max_order_value is not None and not isinstance(
        strategy_max_order_value, dict
    ):
        raise TypeError("strategy_max_order_value must be a dict when provided")
    if strategy_max_order_size is not None and not isinstance(
        strategy_max_order_size, dict
    ):
        raise TypeError("strategy_max_order_size must be a dict when provided")
    if strategy_max_position_size is not None and not isinstance(
        strategy_max_position_size, dict
    ):
        raise TypeError("strategy_max_position_size must be a dict when provided")
    if strategy_max_daily_loss is not None and not isinstance(
        strategy_max_daily_loss, dict
    ):
        raise TypeError("strategy_max_daily_loss must be a dict when provided")
    if strategy_max_drawdown is not None and not isinstance(
        strategy_max_drawdown, dict
    ):
        raise TypeError("strategy_max_drawdown must be a dict when provided")
    if strategy_reduce_only_after_risk is not None and not isinstance(
        strategy_reduce_only_after_risk, dict
    ):
        raise TypeError("strategy_reduce_only_after_risk must be a dict when provided")
    if strategy_risk_cooldown_bars is not None and not isinstance(
        strategy_risk_cooldown_bars, dict
    ):
        raise TypeError("strategy_risk_cooldown_bars must be a dict when provided")
    if strategy_priority is not None and not isinstance(strategy_priority, dict):
        raise TypeError("strategy_priority must be a dict when provided")
    if strategy_risk_budget is not None and not isinstance(strategy_risk_budget, dict):
        raise TypeError("strategy_risk_budget must be a dict when provided")
    if portfolio_risk_budget is not None:
        portfolio_risk_budget = float(portfolio_risk_budget)
        if not pd.notna(portfolio_risk_budget) or portfolio_risk_budget < 0.0:
            raise ValueError("portfolio_risk_budget must be >= 0")
    normalized_mode = str(risk_budget_mode).strip().lower()
    if normalized_mode not in {"order_notional", "trade_notional"}:
        raise ValueError(
            "risk_budget_mode must be 'order_notional' or 'trade_notional'"
        )
    return portfolio_risk_budget, normalized_mode


def _normalize_strategy_fill_policy_map(
    strategy_fill_policy: Optional[Dict[str, FillPolicy]],
    configured_slot_ids: Sequence[str],
    logger: logging.Logger,
) -> Optional[Dict[str, FillPolicy]]:
    if not strategy_fill_policy:
        return None
    if not isinstance(strategy_fill_policy, dict):
        raise TypeError("strategy_fill_policy must be a dict when provided")
    normalized: Dict[str, FillPolicy] = {}
    for strategy_key, raw_policy in strategy_fill_policy.items():
        strategy_key_str = str(strategy_key).strip()
        if not strategy_key_str:
            raise ValueError("strategy_fill_policy contains empty strategy id")
        if not isinstance(raw_policy, dict):
            raise TypeError(
                f"strategy_fill_policy[{strategy_key_str}] must be a dict FillPolicy"
            )
        resolved = _resolve_execution_policy(
            execution_mode="next_open",
            timer_execution_policy="same_cycle",
            fill_policy=cast(FillPolicy, raw_policy),
            logger=logger,
        )
        normalized[strategy_key_str] = {
            "price_basis": resolved.price_basis,
            "bar_offset": int(resolved.bar_offset),
            "temporal": resolved.temporal,
            "twap_bars": resolved.twap_bars,
        }
    unknown_keys = sorted(set(normalized.keys()).difference(set(configured_slot_ids)))
    if unknown_keys:
        raise ValueError(
            "strategy_fill_policy contains unknown strategy id(s): "
            + ",".join(unknown_keys)
        )
    return normalized


def _normalize_strategy_slippage_map(
    strategy_slippage: Optional[Dict[str, SlippagePolicy]],
    configured_slot_ids: Sequence[str],
) -> Optional[Dict[str, SlippagePolicy]]:
    if not strategy_slippage:
        return None
    if not isinstance(strategy_slippage, dict):
        raise TypeError("strategy_slippage must be a dict when provided")
    normalized: Dict[str, SlippagePolicy] = {}
    for strategy_key, raw_slippage in strategy_slippage.items():
        strategy_key_str = str(strategy_key).strip()
        if not strategy_key_str:
            raise ValueError("strategy_slippage contains empty strategy id")
        if not isinstance(raw_slippage, dict):
            raise TypeError(
                f"strategy_slippage[{strategy_key_str}] must be a dict SlippagePolicy"
            )
        raw_type = str(raw_slippage.get("type", "percent")).strip().lower()
        if raw_type not in {"percent", "fixed"}:
            raise ValueError(
                f"strategy_slippage[{strategy_key_str}].type must be one of: "
                "percent, fixed"
            )
        raw_value = raw_slippage.get("value", 0.0)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(
                f"strategy_slippage[{strategy_key_str}].value must be a number >= 0"
            ) from None
        if value < 0:
            raise ValueError(
                f"strategy_slippage[{strategy_key_str}].value must be >= 0"
            )
        normalized[strategy_key_str] = {"type": raw_type, "value": value}
    unknown_keys = sorted(set(normalized.keys()).difference(set(configured_slot_ids)))
    if unknown_keys:
        raise ValueError(
            "strategy_slippage contains unknown strategy id(s): "
            + ",".join(unknown_keys)
        )
    return normalized


def _normalize_strategy_commission_map(
    strategy_commission: Optional[Dict[str, CommissionPolicy]],
    configured_slot_ids: Sequence[str],
) -> Optional[Dict[str, CommissionPolicy]]:
    if not strategy_commission:
        return None
    if not isinstance(strategy_commission, dict):
        raise TypeError("strategy_commission must be a dict when provided")
    normalized: Dict[str, CommissionPolicy] = {}
    for strategy_key, raw_commission in strategy_commission.items():
        strategy_key_str = str(strategy_key).strip()
        if not strategy_key_str:
            raise ValueError("strategy_commission contains empty strategy id")
        if not isinstance(raw_commission, dict):
            raise TypeError(
                f"strategy_commission[{strategy_key_str}] must be a dict "
                "CommissionPolicy"
            )
        raw_type = str(raw_commission.get("type", "percent")).strip().lower()
        if raw_type not in {"percent", "fixed"}:
            raise ValueError(
                f"strategy_commission[{strategy_key_str}].type must be one of: "
                "percent, fixed"
            )
        raw_value = raw_commission.get("value", 0.0)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(
                f"strategy_commission[{strategy_key_str}].value must be a number >= 0"
            ) from None
        if value < 0:
            raise ValueError(
                f"strategy_commission[{strategy_key_str}].value must be >= 0"
            )
        normalized[strategy_key_str] = {"type": raw_type, "value": value}
    unknown_keys = sorted(set(normalized.keys()).difference(set(configured_slot_ids)))
    if unknown_keys:
        raise ValueError(
            "strategy_commission contains unknown strategy id(s): "
            + ",".join(unknown_keys)
        )
    return normalized
