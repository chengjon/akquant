import datetime as dt_module
import inspect
import logging
import os
import sys
from dataclasses import dataclass, fields
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    Union,
    cast,
)

import pandas as pd

from .. import akquant as _akquant_module
from ..akquant import (
    AssetType,
    Bar,
    DataFeed,
    Engine,
    Instrument,
    SettlementType,
    TradingSession,
)
from ..analyzer_plugin import AnalyzerManager, AnalyzerPlugin
from ..config import (
    BacktestConfig,
    ChinaFuturesConfig,
    ChinaFuturesInstrumentTemplateConfig,
    ChinaOptionsConfig,
    RiskConfig,
    StrategyConfig,
)
from ..data import ParquetDataCatalog
from ..feed_adapter import DataFeedAdapter, FeedSlice
from ..log import get_logger, register_logger
from ..risk import apply_risk_config
from ..strategy import (
    InstrumentAssetTypeName,
    InstrumentOptionTypeName,
    InstrumentSettlementMode,
    InstrumentSnapshot,
    Strategy,
    StrategyRuntimeConfig,
)
from ..strategy_loader import resolve_strategy_input
from ..utils import df_to_arrays, prepare_dataframe
from ..utils.inspector import infer_warmup_period
from .result import BacktestResult

_RUNTIME_CONFIG_FIELDS = {f.name for f in fields(StrategyRuntimeConfig)}
_RUNTIME_EXECUTION_MODE = getattr(cast(Any, _akquant_module), "ExecutionMode", None)
_RUNTIME_MODE_NEXT_OPEN = getattr(_RUNTIME_EXECUTION_MODE, "NextOpen", "next_open")
_RUNTIME_MODE_CURRENT_CLOSE = getattr(
    _RUNTIME_EXECUTION_MODE, "CurrentClose", "current_close"
)
_RUNTIME_MODE_NEXT_CLOSE = getattr(_RUNTIME_EXECUTION_MODE, "NextClose", "next_close")
_RUNTIME_MODE_NEXT_AVERAGE = getattr(
    _RUNTIME_EXECUTION_MODE, "NextAverage", "next_average"
)
_RUNTIME_MODE_NEXT_HIGH_LOW_MID = getattr(
    _RUNTIME_EXECUTION_MODE, "NextHighLowMid", "next_high_low_mid"
)


class BacktestStreamEvent(TypedDict):
    """Backtest stream event payload."""

    run_id: str
    seq: int
    ts: int
    event_type: str
    symbol: Optional[str]
    level: str
    payload: Dict[str, str]


class FillPolicy(TypedDict, total=False):
    """Unified fill semantics for price basis and temporal policy."""

    price_basis: str
    temporal: str
    bar_offset: int


class SlippagePolicy(TypedDict, total=False):
    """Per-order slippage semantics."""

    type: str
    value: float


class CommissionPolicy(TypedDict, total=False):
    """Per-order commission semantics."""

    type: str
    value: float


def make_fill_policy(
    *,
    price_basis: str,
    temporal: str,
    bar_offset: Optional[int] = None,
) -> FillPolicy:
    """Build a fill policy payload."""
    policy: FillPolicy = {"price_basis": price_basis, "temporal": temporal}
    if bar_offset is not None:
        policy["bar_offset"] = bar_offset
    return policy


@dataclass(frozen=True)
class ResolvedExecutionPolicy:
    """Resolved execution semantics for matching."""

    price_basis: str
    bar_offset: int
    temporal: str
    execution_mode: Any
    source: Literal["fill_policy", "legacy"]


@dataclass
class PreparedStreamRuntime:
    """Prepared stream runtime components shared by backtest/warm_start."""

    stream_on_event: Callable[[BacktestStreamEvent], None]
    event_stats_snapshot: Dict[str, Any]
    stream_progress_interval: int
    stream_equity_interval: int
    stream_batch_size: int
    stream_max_buffer: int
    stream_error_mode: str
    stream_mode: str


_SUPPORTED_FILL_PRICE_BASIS: set[str] = {"open", "close", "ohlc4", "hl2"}
_RESERVED_FILL_PRICE_BASIS: set[str] = {"mid_quote", "vwap_window", "twap_window"}
_SUPPORTED_FILL_TEMPORAL: set[str] = {"same_cycle", "next_event"}
_SUPPORTED_FILL_BAR_OFFSET: set[int] = {0, 1}
_DEFAULT_FILL_BAR_OFFSET: Dict[str, int] = {
    "open": 1,
    "close": 0,
    "ohlc4": 1,
    "hl2": 1,
}


def _resolve_execution_policy(
    execution_mode: Union[Any, str],
    timer_execution_policy: str,
    fill_policy: Optional[FillPolicy],
    logger: logging.Logger,
) -> ResolvedExecutionPolicy:
    resolved_execution_mode = execution_mode
    resolved_timer_policy = str(timer_execution_policy).strip().lower()
    resolved_price_basis = "open"
    resolved_bar_offset = 1
    resolved_source: Literal["fill_policy", "legacy"] = "legacy"
    if fill_policy is not None:
        if not isinstance(fill_policy, dict):
            raise TypeError("fill_policy must be a dict")
        raw_basis = str(fill_policy.get("price_basis", "open")).strip().lower()
        raw_temporal = str(fill_policy.get("temporal", "same_cycle")).strip().lower()
        if raw_basis not in _SUPPORTED_FILL_PRICE_BASIS:
            if raw_basis in _RESERVED_FILL_PRICE_BASIS:
                raise NotImplementedError(
                    "fill_policy.price_basis='%s' is reserved but not implemented yet"
                    % raw_basis
                )
            raise ValueError(
                "fill_policy.price_basis must be one of: "
                "open, close, ohlc4, hl2; "
                "reserved: mid_quote, vwap_window, twap_window"
            )
        if raw_temporal not in _SUPPORTED_FILL_TEMPORAL:
            raise ValueError(
                "fill_policy.temporal must be one of: same_cycle, next_event"
            )
        raw_offset_value = fill_policy.get(
            "bar_offset", _DEFAULT_FILL_BAR_OFFSET.get(raw_basis, 1)
        )
        try:
            raw_offset = int(raw_offset_value)
        except (TypeError, ValueError):
            raise ValueError("fill_policy.bar_offset must be 0 or 1") from None
        if raw_offset not in _SUPPORTED_FILL_BAR_OFFSET:
            raise ValueError("fill_policy.bar_offset must be 0 or 1")
        if raw_basis == "open":
            if raw_offset != 1:
                raise ValueError("fill_policy(open) requires bar_offset=1")
            basis_mode = _RUNTIME_MODE_NEXT_OPEN
        elif raw_basis == "close":
            basis_mode = (
                _RUNTIME_MODE_CURRENT_CLOSE
                if raw_offset == 0
                else _RUNTIME_MODE_NEXT_CLOSE
            )
        elif raw_basis == "ohlc4":
            if raw_offset != 1:
                raise ValueError("fill_policy(ohlc4) requires bar_offset=1")
            basis_mode = _RUNTIME_MODE_NEXT_AVERAGE
        else:
            if raw_offset != 1:
                raise ValueError("fill_policy(hl2) requires bar_offset=1")
            basis_mode = _RUNTIME_MODE_NEXT_HIGH_LOW_MID
        if execution_mode != _RUNTIME_MODE_NEXT_OPEN:
            logger.warning(
                "fill_policy overrides execution_mode=%s",
                execution_mode,
            )
        if str(timer_execution_policy).strip().lower() != "same_cycle":
            logger.warning(
                "fill_policy overrides timer_execution_policy=%s",
                timer_execution_policy,
            )
        resolved_execution_mode = basis_mode
        resolved_timer_policy = raw_temporal
        resolved_price_basis = raw_basis
        resolved_bar_offset = raw_offset
        resolved_source = "fill_policy"

    if isinstance(resolved_execution_mode, str):
        mode_text = str(resolved_execution_mode).strip()
        mode_raw = mode_text.split(".", 1)[-1] if "." in mode_text else mode_text
        mode_compact = mode_raw.replace(" ", "").replace("-", "_")
        mode_key = mode_compact.lower()
        mode_map = {
            "open": (_RUNTIME_MODE_NEXT_OPEN, "open", 1),
            "close": (_RUNTIME_MODE_CURRENT_CLOSE, "close", 0),
            "next_open": (_RUNTIME_MODE_NEXT_OPEN, "open", 1),
            "nextopen": (_RUNTIME_MODE_NEXT_OPEN, "open", 1),
            "current_close": (_RUNTIME_MODE_CURRENT_CLOSE, "close", 0),
            "currentclose": (_RUNTIME_MODE_CURRENT_CLOSE, "close", 0),
            "next_close": (_RUNTIME_MODE_NEXT_CLOSE, "close", 1),
            "nextclose": (_RUNTIME_MODE_NEXT_CLOSE, "close", 1),
            "next_average": (_RUNTIME_MODE_NEXT_AVERAGE, "ohlc4", 1),
            "nextaverage": (_RUNTIME_MODE_NEXT_AVERAGE, "ohlc4", 1),
            "next_high_low_mid": (_RUNTIME_MODE_NEXT_HIGH_LOW_MID, "hl2", 1),
            "nexthighlowmid": (_RUNTIME_MODE_NEXT_HIGH_LOW_MID, "hl2", 1),
            "ohlc4": (_RUNTIME_MODE_NEXT_AVERAGE, "ohlc4", 1),
            "hl2": (_RUNTIME_MODE_NEXT_HIGH_LOW_MID, "hl2", 1),
        }
        mode_tuple = mode_map.get(mode_key)
        if not mode_tuple:
            logger.warning(
                "Unknown execution mode '%s', defaulting to NextOpen",
                resolved_execution_mode,
            )
            mode_tuple = (_RUNTIME_MODE_NEXT_OPEN, "open", 1)
        resolved_mode_enum, mapped_basis, mapped_offset = mode_tuple
        if fill_policy is None:
            resolved_price_basis = mapped_basis
            resolved_bar_offset = mapped_offset
    else:
        resolved_mode_enum = resolved_execution_mode
        if fill_policy is None:
            reverse_mode_map = {
                _RUNTIME_MODE_NEXT_OPEN: ("open", 1),
                _RUNTIME_MODE_CURRENT_CLOSE: ("close", 0),
                _RUNTIME_MODE_NEXT_CLOSE: ("close", 1),
                _RUNTIME_MODE_NEXT_AVERAGE: ("ohlc4", 1),
                _RUNTIME_MODE_NEXT_HIGH_LOW_MID: ("hl2", 1),
            }
            mapped_basis, mapped_offset = reverse_mode_map.get(
                resolved_mode_enum, ("open", 1)
            )
            resolved_price_basis = mapped_basis
            resolved_bar_offset = mapped_offset

    if resolved_timer_policy not in _SUPPORTED_FILL_TEMPORAL:
        raise ValueError(
            "timer_execution_policy must be one of: same_cycle, next_event"
        )

    return ResolvedExecutionPolicy(
        price_basis=resolved_price_basis,
        bar_offset=resolved_bar_offset,
        temporal=resolved_timer_policy,
        execution_mode=resolved_mode_enum,
        source=resolved_source,
    )


def _raise_if_legacy_execution_policy_used(
    *, legacy_mode_used: bool, legacy_timer_used: bool, api_name: str
) -> None:
    if not (legacy_mode_used or legacy_timer_used):
        return
    raise ValueError(
        f"{api_name} no longer accepts execution_mode/timer_execution_policy; "
        "please use fill_policy"
    )


def _index_to_local_trading_days(
    index: pd.DatetimeIndex, timezone: str
) -> pd.DatetimeIndex:
    local_index = index
    if local_index.tz is None:
        local_index = local_index.tz_localize("UTC")
    return cast(pd.DatetimeIndex, local_index.tz_convert(timezone))


BacktestDataInput = Union[
    pd.DataFrame, Dict[str, pd.DataFrame], List[Bar], DataFeed, DataFeedAdapter
]

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


def _parse_positive_int_option(name: str, value: Any) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


def _parse_stream_error_mode(value: Any) -> str:
    mode = str(value).strip().lower()
    if mode not in {"continue", "fail_fast"}:
        raise ValueError("stream_error_mode must be 'continue' or 'fail_fast'")
    return mode


def _parse_stream_mode(value: Any) -> str:
    mode = str(value).strip().lower()
    if mode not in {"observability", "audit"}:
        raise ValueError("stream_mode must be 'observability' or 'audit'")
    return mode


def _noop_stream_event_handler(_event: BacktestStreamEvent) -> None:
    return None


def _prepare_stream_runtime(
    *,
    on_event: Optional[Callable[[BacktestStreamEvent], None]],
    kwargs: Dict[str, Any],
    owner_strategy_id: Optional[str] = None,
    patch_owner_strategy_id: bool = False,
) -> PreparedStreamRuntime:
    stream_on_event = on_event
    internal_stream_callback = kwargs.pop("_stream_on_event", None)
    if internal_stream_callback is not None and stream_on_event is not None:
        raise TypeError("on_event and _stream_on_event cannot be provided together")
    if internal_stream_callback is not None:
        stream_on_event = internal_stream_callback
    if stream_on_event is not None and not callable(stream_on_event):
        raise TypeError("on_event must be callable when provided")
    if stream_on_event is None:
        stream_on_event = _noop_stream_event_handler
    original_stream_handler = stream_on_event
    event_stats_snapshot: Dict[str, Any] = {}

    def wrapped_stream_on_event(event: BacktestStreamEvent) -> None:
        event_type = str(event.get("event_type", ""))
        if event_type == "finished":
            payload_obj = event.get("payload", {})
            if isinstance(payload_obj, dict):
                for key in (
                    "processed_events",
                    "dropped_event_count",
                    "callback_error_count",
                    "backpressure_policy",
                    "stream_mode",
                    "sampling_enabled",
                    "sampling_rate",
                    "reason",
                ):
                    if key in payload_obj:
                        event_stats_snapshot[key] = payload_obj.get(key)
        if patch_owner_strategy_id and owner_strategy_id is not None:
            if event_type in {"order", "trade", "risk"}:
                payload_obj = event.get("payload", {})
                if isinstance(payload_obj, dict):
                    current_owner = payload_obj.get("owner_strategy_id")
                    if current_owner is None or str(current_owner) == "":
                        patched_event = dict(event)
                        patched_payload = dict(payload_obj)
                        patched_payload["owner_strategy_id"] = owner_strategy_id
                        patched_event["payload"] = cast(Dict[str, str], patched_payload)
                        original_stream_handler(
                            cast(BacktestStreamEvent, patched_event)
                        )
                        return
        original_stream_handler(event)

    stream_progress_interval = _parse_positive_int_option(
        "stream_progress_interval", kwargs.pop("stream_progress_interval", 1)
    )
    stream_equity_interval = _parse_positive_int_option(
        "stream_equity_interval", kwargs.pop("stream_equity_interval", 1)
    )
    stream_batch_size = _parse_positive_int_option(
        "stream_batch_size", kwargs.pop("stream_batch_size", 1)
    )
    stream_max_buffer = _parse_positive_int_option(
        "stream_max_buffer", kwargs.pop("stream_max_buffer", 1024)
    )
    stream_error_mode = _parse_stream_error_mode(
        kwargs.pop("stream_error_mode", "continue")
    )
    stream_mode = _parse_stream_mode(kwargs.pop("stream_mode", "observability"))
    if "legacy_execution_policy_compat" in kwargs:
        raise TypeError(
            "legacy_execution_policy_compat is no longer supported; "
            "please use fill_policy"
        )
    return PreparedStreamRuntime(
        stream_on_event=wrapped_stream_on_event,
        event_stats_snapshot=event_stats_snapshot,
        stream_progress_interval=stream_progress_interval,
        stream_equity_interval=stream_equity_interval,
        stream_batch_size=stream_batch_size,
        stream_max_buffer=stream_max_buffer,
        stream_error_mode=stream_error_mode,
        stream_mode=stream_mode,
    )


def _attach_result_runtime_metadata(
    *,
    result: BacktestResult,
    engine_summary: Any,
    event_stats_snapshot: Dict[str, Any],
    owner_strategy_id: str,
    resolved_policy: Optional[ResolvedExecutionPolicy],
) -> None:
    setattr(result, "_engine_summary", engine_summary)
    setattr(result, "_event_stats", dict(event_stats_snapshot))
    setattr(result, "_owner_strategy_id", owner_strategy_id)
    if resolved_policy is not None:
        setattr(
            result,
            "_resolved_execution_policy",
            {
                "price_basis": resolved_policy.price_basis,
                "bar_offset": resolved_policy.bar_offset,
                "temporal": resolved_policy.temporal,
                "source": resolved_policy.source,
            },
        )
        result.resolved_execution_policy = cast(
            Dict[str, Any], getattr(result, "_resolved_execution_policy")
        )


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


def _accepts_strategy_kwarg(
    strategy_input: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None],
    kwarg_name: str,
) -> bool:
    """Return whether strategy constructor supports a keyword argument."""
    if not isinstance(strategy_input, type) or not issubclass(strategy_input, Strategy):
        return False
    try:
        signature = inspect.signature(strategy_input.__init__)
    except (TypeError, ValueError):
        return False

    if kwarg_name in signature.parameters:
        return True

    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def _split_strategy_kwargs(
    strategy_input: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None],
    strategy_kwargs: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Split kwargs into constructor-accepted kwargs and unknown keys."""
    if not isinstance(strategy_input, type) or not issubclass(strategy_input, Strategy):
        return strategy_kwargs, []

    try:
        signature = inspect.signature(strategy_input.__init__)
    except (TypeError, ValueError):
        return strategy_kwargs, []

    supports_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if supports_var_kwargs:
        return strategy_kwargs, []

    accepted_names = {
        parameter_name
        for parameter_name, parameter in signature.parameters.items()
        if parameter_name != "self"
        and parameter.kind
        in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }
    accepted_kwargs = {
        key: value for key, value in strategy_kwargs.items() if key in accepted_names
    }
    unknown_keys = sorted(
        key for key in strategy_kwargs.keys() if key not in accepted_names
    )
    return accepted_kwargs, unknown_keys


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


def _parse_asset_type_name(value: Any) -> Literal["futures", "stock", "fund", "option"]:
    if isinstance(value, AssetType):
        if value == AssetType.Futures:
            return "futures"
        if value == AssetType.Stock:
            return "stock"
        if value == AssetType.Fund:
            return "fund"
        if value == AssetType.Option:
            return "option"
        raise ValueError(f"Unsupported asset_type: {value}")
    if isinstance(value, str):
        v_lower = value.lower()
        if v_lower in {"future", "futures"}:
            return "futures"
        if v_lower == "stock":
            return "stock"
        if v_lower == "fund":
            return "fund"
        if v_lower == "option":
            return "option"
    raise ValueError(f"Unsupported asset_type: {value}")


def _normalize_expiry_date_yyyymmdd(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("expiry_date does not support bool")
    if isinstance(value, int):
        yyyymmdd = value
    elif isinstance(value, pd.Timestamp):
        if pd.isna(value):
            raise ValueError("expiry_date timestamp is NaT")
        yyyymmdd = int(value.strftime("%Y%m%d"))
    elif isinstance(value, dt_module.datetime):
        yyyymmdd = int(value.date().strftime("%Y%m%d"))
    elif isinstance(value, dt_module.date):
        yyyymmdd = int(value.strftime("%Y%m%d"))
    elif isinstance(value, str):
        raise TypeError(
            "expiry_date no longer supports str, please use date/datetime/"
            "Timestamp/int(YYYYMMDD)"
        )
    else:
        raise TypeError(
            "expiry_date must be date/datetime/pandas.Timestamp/int(YYYYMMDD)"
        )
    text = str(yyyymmdd)
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"expiry_date must be YYYYMMDD, got: {value}")
    year = int(text[0:4])
    month = int(text[4:6])
    day = int(text[6:8])
    dt_module.date(year, month, day)
    return yyyymmdd


def _asset_type_to_upper_name(
    value: Union[str, AssetType],
) -> InstrumentAssetTypeName:
    parsed = _parse_asset_type_name(value)
    if parsed == "futures":
        return "FUTURES"
    if parsed == "fund":
        return "FUND"
    if parsed == "option":
        return "OPTION"
    return "STOCK"


def _option_type_to_upper_name(value: Any) -> Optional[InstrumentOptionTypeName]:
    if value is None:
        return None
    text = str(value).upper()
    if "CALL" in text:
        return "CALL"
    if "PUT" in text:
        return "PUT"
    raise ValueError(f"Unsupported option_type: {value}")


def _settlement_type_to_upper_name(value: Any) -> Optional[InstrumentSettlementMode]:
    if value is None:
        return None
    text = str(value).upper()
    if "FORCE" in text and "CLOSE" in text:
        return "FORCE_CLOSE"
    if "SETTLEMENT_PRICE" in text:
        return "SETTLEMENT_PRICE"
    if "CASH" in text:
        return "CASH"
    raise ValueError(f"Unsupported settlement_type: {value}")


def _parse_trading_session(value: Any) -> Any:
    if isinstance(value, TradingSession):
        return value
    call_auction = getattr(
        TradingSession, "CallAuction", getattr(TradingSession, "Normal", None)
    )
    pre_open = getattr(
        TradingSession, "PreOpen", getattr(TradingSession, "PreMarket", None)
    )
    continuous = getattr(
        TradingSession, "Continuous", getattr(TradingSession, "Normal", None)
    )
    break_session = getattr(
        TradingSession, "Break", getattr(TradingSession, "Normal", None)
    )
    post_close = getattr(
        TradingSession, "PostClose", getattr(TradingSession, "PostMarket", None)
    )
    closed = getattr(
        TradingSession, "Closed", getattr(TradingSession, "PostMarket", None)
    )
    v_lower = str(value).strip().lower()
    mapping = {
        "call_auction": call_auction,
        "callauction": call_auction,
        "pre_open": pre_open,
        "preopen": pre_open,
        "continuous": continuous,
        "break": break_session,
        "post_close": post_close,
        "postclose": post_close,
        "closed": closed,
    }
    if v_lower in mapping and mapping[v_lower] is not None:
        return mapping[v_lower]
    raise ValueError(f"Unsupported trading session: {value}")


def _china_futures_session_template(
    profile: str,
) -> List[Tuple[str, str, str]]:
    normalized = str(profile).strip().upper()
    commodity_day_template: List[Tuple[str, str, str]] = [
        ("09:00", "10:15", "continuous"),
        ("10:15", "10:30", "break"),
        ("10:30", "11:30", "continuous"),
        ("11:30", "13:30", "break"),
        ("13:30", "15:00", "continuous"),
    ]
    cffex_stock_index_day_template: List[Tuple[str, str, str]] = [
        ("09:30", "11:30", "continuous"),
        ("11:30", "13:00", "break"),
        ("13:00", "15:00", "continuous"),
    ]
    cffex_bond_day_template: List[Tuple[str, str, str]] = [
        ("09:30", "11:30", "continuous"),
        ("11:30", "13:00", "break"),
        ("13:00", "15:15", "continuous"),
    ]
    if normalized in {"CN_FUTURES_DAY", "CN_FUTURES_COMMODITY_DAY"}:
        return commodity_day_template
    if normalized == "CN_FUTURES_CFFEX_STOCK_INDEX_DAY":
        return cffex_stock_index_day_template
    if normalized == "CN_FUTURES_CFFEX_BOND_DAY":
        return cffex_bond_day_template
    if normalized == "CN_FUTURES_NIGHT_23":
        return [("21:00", "23:00", "continuous")] + commodity_day_template
    if normalized == "CN_FUTURES_NIGHT_01":
        return [
            ("21:00", "23:59", "continuous"),
            ("00:00", "01:00", "continuous"),
        ] + commodity_day_template
    if normalized == "CN_FUTURES_NIGHT_0230":
        return [
            ("21:00", "23:59", "continuous"),
            ("00:00", "02:30", "continuous"),
        ] + commodity_day_template
    raise ValueError(f"Unsupported china futures session profile: {profile}")


def _is_data_feed_adapter(value: Any) -> bool:
    return hasattr(value, "load") and callable(getattr(value, "load"))


def _load_data_map_from_adapter(
    adapter: Any,
    symbols: List[str],
    start_time: Optional[Union[str, Any]],
    end_time: Optional[Union[str, Any]],
    timezone: Optional[str],
) -> Dict[str, pd.DataFrame]:
    request_start = pd.Timestamp(start_time) if start_time is not None else None
    request_end = pd.Timestamp(end_time) if end_time is not None else None
    requested_symbols = symbols or ["BENCHMARK"]
    data_map: Dict[str, pd.DataFrame] = {}

    for sym in requested_symbols:
        frame = adapter.load(
            FeedSlice(
                symbol=str(sym),
                start_time=request_start,
                end_time=request_end,
                timezone=timezone,
            )
        )
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("DataFeedAdapter.load must return pandas.DataFrame")
        if frame.empty:
            continue

        if "symbol" in frame.columns:
            grouped = frame.groupby(frame["symbol"].astype(str), sort=False)
            for grouped_symbol, grouped_frame in grouped:
                data_map[str(grouped_symbol)] = grouped_frame.copy()
        else:
            normalized = frame.copy()
            normalized["symbol"] = str(sym)
            data_map[str(sym)] = normalized

    return data_map


def _build_strategy_instance(
    strategy: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None],
    strategy_kwargs: Dict[str, Any],
    strict_strategy_params: bool,
    logger: Any,
    initialize: Optional[Callable[[Any], None]],
    on_start: Optional[Callable[[Any], None]],
    on_stop: Optional[Callable[[Any], None]],
    on_tick: Optional[Callable[[Any, Any], None]],
    on_order: Optional[Callable[[Any, Any], None]],
    on_trade: Optional[Callable[[Any, Any], None]],
    on_timer: Optional[Callable[[Any, str], None]],
    context: Optional[Dict[str, Any]],
) -> Strategy:
    if isinstance(strategy, type) and issubclass(strategy, Strategy):
        accepted_kwargs, unknown_keys = _split_strategy_kwargs(
            strategy, strategy_kwargs
        )
        if unknown_keys:
            unknown_keys_text = ", ".join(unknown_keys)
            if strict_strategy_params:
                raise TypeError(
                    "Unknown strategy constructor parameter(s): "
                    f"{unknown_keys_text}. Strategy={strategy.__module__}."
                    f"{strategy.__name__}"
                )
            logger.warning(
                "Ignoring unknown strategy constructor parameter(s): %s. "
                "Strategy=%s.%s",
                unknown_keys_text,
                strategy.__module__,
                strategy.__name__,
            )
        try:
            return cast(Strategy, strategy(**accepted_kwargs))
        except TypeError as e:
            if strict_strategy_params:
                raise TypeError(
                    "Failed to instantiate strategy with provided parameters: "
                    f"{e}. Strategy={strategy.__module__}.{strategy.__name__}"
                ) from e
            logger.warning(
                f"Failed to instantiate strategy with provided parameters: {e}. "
                "Falling back to default constructor (no arguments)."
            )
            return cast(Strategy, strategy())
    if isinstance(strategy, Strategy):
        return strategy
    if callable(strategy):
        return FunctionalStrategy(
            initialize,
            cast(Callable[[Any, Bar], None], strategy),
            on_start=on_start,
            on_stop=on_stop,
            on_tick=on_tick,
            on_order=on_order,
            on_trade=on_trade,
            on_timer=on_timer,
            context=context,
        )
    if strategy is None:
        raise ValueError("Strategy must be provided.")
    raise ValueError("Invalid strategy type")


class FunctionalStrategy(Strategy):
    """内部策略包装器，用于支持函数式 API (Zipline 风格)."""

    def __init__(
        self,
        initialize: Optional[Callable[[Any], None]],
        on_bar: Optional[Callable[[Any, Bar], None]],
        on_start: Optional[Callable[[Any], None]] = None,
        on_stop: Optional[Callable[[Any], None]] = None,
        on_tick: Optional[Callable[[Any, Any], None]] = None,
        on_order: Optional[Callable[[Any, Any], None]] = None,
        on_trade: Optional[Callable[[Any, Any], None]] = None,
        on_timer: Optional[Callable[[Any, str], None]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the FunctionalStrategy."""
        super().__init__()
        self._initialize = initialize
        self._on_bar_func = on_bar
        self._on_start_func = on_start
        self._on_stop_func = on_stop
        self._on_tick_func = on_tick
        self._on_order_func = on_order
        self._on_trade_func = on_trade
        self._on_timer_func = on_timer
        self._context = context or {}

        # 将 context 注入到 self 中，模拟 Zipline 的 context 对象
        # 用户可以通过 self.xxx 访问 context 属性
        for k, v in self._context.items():
            setattr(self, k, v)

        # 调用初始化函数
        if self._initialize is not None:
            self._initialize(self)

    def on_bar(self, bar: Bar) -> None:
        """Delegate on_bar event to the user-provided function."""
        if self._on_bar_func is not None:
            self._on_bar_func(self, bar)

    def on_start(self) -> None:
        """Delegate on_start event to the user-provided function."""
        if self._on_start_func is not None:
            self._on_start_func(self)

    def on_stop(self) -> None:
        """Delegate on_stop event to the user-provided function."""
        if self._on_stop_func is not None:
            self._on_stop_func(self)

    def on_tick(self, tick: Any) -> None:
        """Delegate on_tick event to the user-provided function."""
        if self._on_tick_func is not None:
            self._on_tick_func(self, tick)

    def on_order(self, order: Any) -> None:
        """Delegate on_order event to the user-provided function."""
        if self._on_order_func is not None:
            self._on_order_func(self, order)

    def on_trade(self, trade: Any) -> None:
        """Delegate on_trade event to the user-provided function."""
        if self._on_trade_func is not None:
            self._on_trade_func(self, trade)

    def on_timer(self, payload: str) -> None:
        """Delegate on_timer event to the user-provided function."""
        if self._on_timer_func is not None:
            self._on_timer_func(self, payload)


def _coerce_strategy_runtime_config(
    value: Union[StrategyRuntimeConfig, Dict[str, Any]],
) -> StrategyRuntimeConfig:
    if isinstance(value, StrategyRuntimeConfig):
        return StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=value.enable_precise_day_boundary_hooks,
            portfolio_update_eps=value.portfolio_update_eps,
            error_mode=value.error_mode,
            re_raise_on_error=value.re_raise_on_error,
            indicator_mode=value.indicator_mode,
        )
    if isinstance(value, dict):
        unknown_fields = sorted(set(value.keys()) - _RUNTIME_CONFIG_FIELDS)
        if unknown_fields:
            allowed = ", ".join(sorted(_RUNTIME_CONFIG_FIELDS))
            unknown = ", ".join(unknown_fields)
            raise ValueError(
                "strategy_runtime_config contains unknown fields: "
                f"{unknown}. Allowed fields: {allowed}"
            )
        try:
            return StrategyRuntimeConfig(**value)
        except ValueError as exc:
            raise ValueError(f"invalid strategy_runtime_config: {exc}") from None
    raise TypeError(
        "strategy_runtime_config must be StrategyRuntimeConfig or Dict[str, Any]"
    )


def _runtime_config_conflicts(
    current: StrategyRuntimeConfig, incoming: StrategyRuntimeConfig
) -> List[str]:
    conflicts: List[str] = []
    for key in sorted(_RUNTIME_CONFIG_FIELDS):
        before = getattr(current, key)
        after = getattr(incoming, key)
        if before != after:
            conflicts.append(f"{key}: {before} -> {after}")
    return conflicts


def _should_prepare_precomputed_indicators(strategy_instance: Strategy) -> bool:
    return str(strategy_instance.indicator_mode).strip().lower() == "precompute"


def _apply_strategy_runtime_config(
    strategy_instance: Strategy,
    incoming: Union[StrategyRuntimeConfig, Dict[str, Any]],
    runtime_config_override: bool,
    logger: Any,
) -> None:
    cfg = _coerce_strategy_runtime_config(incoming)
    current = strategy_instance.runtime_config
    conflicts = _runtime_config_conflicts(current, cfg)
    if conflicts:
        conflict_text = "; ".join(conflicts)
        warning_key = f"{runtime_config_override}|{conflict_text}"
        warned_keys = getattr(strategy_instance, "_runtime_config_warning_keys", None)
        if not isinstance(warned_keys, set):
            warned_keys = set()
            setattr(strategy_instance, "_runtime_config_warning_keys", warned_keys)
        should_log = warning_key not in warned_keys
        warned_keys.add(warning_key)
        if runtime_config_override:
            if should_log:
                logger.warning(
                    "strategy_runtime_config overrides strategy runtime_config: "
                    f"{conflict_text}"
                )
        else:
            if should_log:
                logger.warning(
                    "strategy_runtime_config is ignored because "
                    f"runtime_config_override=False: {conflict_text}"
                )
            return
    strategy_instance.runtime_config = cfg


def _coerce_analyzer_plugins(
    analyzer_plugins: Optional[Sequence[AnalyzerPlugin]],
) -> List[AnalyzerPlugin]:
    if analyzer_plugins is None:
        return []
    if not isinstance(analyzer_plugins, (list, tuple)):
        raise TypeError("analyzer_plugins must be a list/tuple of analyzer plugins")
    normalized: List[AnalyzerPlugin] = []
    for plugin in analyzer_plugins:
        if not hasattr(plugin, "name"):
            raise TypeError("analyzer plugin must have 'name' attribute")
        if not hasattr(plugin, "on_start") or not callable(getattr(plugin, "on_start")):
            raise TypeError("analyzer plugin must implement on_start(context)")
        if not hasattr(plugin, "on_bar") or not callable(getattr(plugin, "on_bar")):
            raise TypeError("analyzer plugin must implement on_bar(context)")
        if not hasattr(plugin, "on_trade") or not callable(getattr(plugin, "on_trade")):
            raise TypeError("analyzer plugin must implement on_trade(context)")
        if not hasattr(plugin, "on_finish") or not callable(
            getattr(plugin, "on_finish")
        ):
            raise TypeError("analyzer plugin must implement on_finish(context)")
        normalized.append(plugin)
    return normalized


def run_backtest(
    data: Optional[BacktestDataInput] = None,
    strategy: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None] = None,
    strategy_source: Optional[Union[str, bytes, os.PathLike[str]]] = None,
    strategy_loader: Optional[str] = None,
    strategy_loader_options: Optional[Dict[str, Any]] = None,
    symbols: Union[str, List[str], Tuple[str, ...], set[str]] = "BENCHMARK",
    initial_cash: Optional[float] = None,
    commission_rate: Optional[float] = None,
    stamp_tax_rate: Optional[float] = None,
    transfer_fee_rate: Optional[float] = None,
    min_commission: Optional[float] = None,
    slippage: Optional[float] = None,
    volume_limit_pct: Optional[float] = None,
    timezone: Optional[str] = None,
    t_plus_one: bool = False,
    initialize: Optional[Callable[[Any], None]] = None,
    on_start: Optional[Callable[[Any], None]] = None,
    on_stop: Optional[Callable[[Any], None]] = None,
    on_tick: Optional[Callable[[Any, Any], None]] = None,
    on_order: Optional[Callable[[Any, Any], None]] = None,
    on_trade: Optional[Callable[[Any, Any], None]] = None,
    on_timer: Optional[Callable[[Any, str], None]] = None,
    context: Optional[Dict[str, Any]] = None,
    history_depth: Optional[int] = None,
    warmup_period: int = 0,
    lot_size: Union[int, Dict[str, int], None] = None,
    show_progress: Optional[bool] = None,
    start_time: Optional[Union[str, Any]] = None,
    end_time: Optional[Union[str, Any]] = None,
    catalog_path: Optional[str] = None,
    config: Optional[BacktestConfig] = None,
    custom_matchers: Optional[Dict[AssetType, Any]] = None,
    risk_config: Optional[Union[Dict[str, Any], RiskConfig]] = None,
    strategy_runtime_config: Optional[
        Union[StrategyRuntimeConfig, Dict[str, Any]]
    ] = None,
    runtime_config_override: bool = True,
    strategy_id: Optional[str] = None,
    strategies_by_slot: Optional[
        Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
    ] = None,
    strategy_max_order_value: Optional[Dict[str, float]] = None,
    strategy_max_order_size: Optional[Dict[str, float]] = None,
    strategy_max_position_size: Optional[Dict[str, float]] = None,
    strategy_max_daily_loss: Optional[Dict[str, float]] = None,
    strategy_max_drawdown: Optional[Dict[str, float]] = None,
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None,
    strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None,
    strategy_priority: Optional[Dict[str, int]] = None,
    strategy_risk_budget: Optional[Dict[str, float]] = None,
    strategy_fill_policy: Optional[Dict[str, FillPolicy]] = None,
    strategy_slippage: Optional[Dict[str, SlippagePolicy]] = None,
    strategy_commission: Optional[Dict[str, CommissionPolicy]] = None,
    portfolio_risk_budget: Optional[float] = None,
    risk_budget_mode: str = "order_notional",
    risk_budget_reset_daily: bool = False,
    analyzer_plugins: Optional[Sequence[AnalyzerPlugin]] = None,
    on_event: Optional[Callable[[BacktestStreamEvent], None]] = None,
    broker_profile: Optional[str] = None,
    fill_policy: Optional[FillPolicy] = None,
    strict_strategy_params: bool = True,
    **kwargs: Any,
) -> BacktestResult:
    """
    简化版回测入口函数.

    :param data: 回测数据，可以是 Pandas DataFrame 或 Bar 列表.
    :param custom_matchers: 自定义撮合器字典 {AssetType: MatcherInstance}
                 用于覆盖特定资产类型的默认撮合逻辑。
                 例如：传入一个实现了自定义成交规则的 Rust 撮合器实例，
                 或者用于测试目的的 Mock 撮合器。
                 默认情况下，引擎会根据 AssetType 自动选择内置的撮合器
                 (如 StockMatcher, FuturesMatcher 等)。
    :param risk_config: 风控配置，支持字典 (e.g., {"max_position_pct": 0.1})
                        或 RiskConfig 对象。如果同时提供了 config.strategy_config.risk，
                        此参数将覆盖其中的同名字段。
    :param strategy: 策略类、策略实例或 on_bar 回调函数
    :param strategy_source: 策略源码输入（路径字符串 / bytes / PathLike），
                            当 strategy=None 时用于动态加载策略
    :param strategy_loader: 策略加载器名称，默认 "python_plain"，
                            可选 "encrypted_external" 或用户注册加载器
    :param strategy_loader_options: 传给策略加载器的参数字典（可选），
                                    如 {"strategy_attr": "MyStrategy"} 或
                                    {"decrypt_and_load": callable}
    :param symbols: 标的代码或代码列表
    :param initial_cash: 初始资金 (默认 100,000.0)
    :param commission_rate: 佣金率 (默认 0.0)
    :param stamp_tax_rate: 印花税率 (仅卖出, 默认 0.0)
    :param transfer_fee_rate: 过户费率 (默认 0.0)
    :param min_commission: 最低佣金 (默认 0.0)
    :param slippage: 滑点 (默认 0.0)
    :param volume_limit_pct: 成交量限制比例 (默认 0.25)
    :param fill_policy: 统一成交语义配置（可选），格式:
        {"price_basis": "open|close|ohlc4|hl2",
         "bar_offset": "0|1",
         "temporal": "same_cycle|next_event"}。
        预留未实现 price_basis: mid_quote、vwap_window、twap_window。
    :param legacy_execution_policy_compat: 已移除，不再支持。
    :param strict_strategy_params: 是否严格校验策略构造参数。True 时若参数不匹配将抛错；
                                   False 时保持兼容行为（忽略未知参数并在失败时
                                   回退无参构造）。
    :param timezone: 时区名称 (默认 "Asia/Shanghai")
    :param t_plus_one: 是否启用 T+1 交易规则 (默认 False)
    :param initialize: 初始化回调函数 (仅当 strategy 为函数时使用)
    :param on_start: 启动回调函数 (仅当 strategy 为函数时使用)
    :param on_stop: 停止回调函数 (仅当 strategy 为函数时使用)
    :param on_tick: Tick 回调函数 (仅当 strategy 为函数时使用)
    :param on_order: 订单回调函数 (仅当 strategy 为函数时使用)
    :param on_trade: 成交回调函数 (仅当 strategy 为函数时使用)
    :param on_timer: 定时器回调函数 (仅当 strategy 为函数时使用)
    :param context: 初始上下文数据 (仅当 strategy 为函数时使用)
    :param history_depth: 自动维护历史数据的长度 (0 表示禁用)
    :param warmup_period: 策略预热期 (等同于 history_depth，取最大值)
    :param lot_size: 最小交易单位。如果是 int，则应用于所有标的；
                     如果是 Dict[str, int]，则按代码匹配；如果不传(None)，默认为 1。
    :param show_progress: 是否显示进度条 (默认 True)
    :param start_time: 回测开始时间 (e.g., "2020-01-01 09:30"). 优先级高于
                       config.start_time.
    :param end_time: 回测结束时间 (e.g., "2020-12-31 15:00"). 优先级高于
                     config.end_time.
    :param catalog_path: 当 data 未显式传入时，按该目录加载 ParquetDataCatalog 数据。
                         不传则使用 ParquetDataCatalog 默认目录。
    :param config: BacktestConfig 配置对象 (可选)
    :param strategy_runtime_config: 策略运行时配置对象或字典 (可选)
    :param runtime_config_override: 是否覆盖策略实例内已有 runtime_config (默认 True)
    :param strategy_id: 策略归属 ID（预留多策略归因字段，默认 "_default"）
    :param strategies_by_slot: 可选 slot->策略映射，用于启用多策略 slot 迭代执行
    :param strategy_max_order_value: 可选策略级单笔下单金额上限映射
                                    （strategy_id->max_value）
    :param strategy_max_order_size: 可选策略级单笔下单数量上限映射
                                   （strategy_id->max_size）
    :param strategy_max_position_size: 可选策略级净持仓数量上限映射
                                       （strategy_id->max_abs_position）
    :param strategy_max_daily_loss: 可选策略级日内亏损上限映射
                                    （strategy_id->max_daily_loss）
    :param strategy_max_drawdown: 可选策略级回撤上限映射
                                  （strategy_id->max_drawdown）
    :param strategy_reduce_only_after_risk: 可选策略级风控触发后仅平仓开关映射
                                            （strategy_id->bool）
    :param strategy_risk_cooldown_bars: 可选策略级风控触发后冷却 bars 映射
                                        （strategy_id->cooldown_bars）
    :param strategy_priority: 可选策略级执行优先级映射（strategy_id->priority）
    :param strategy_risk_budget: 可选策略级累计风险预算映射（strategy_id->budget）
    :param strategy_fill_policy: 可选策略级默认成交策略映射
                                 （strategy_id->fill_policy）。
                                 下单优先级：订单级 > 策略级 > 运行级。
    :param strategy_slippage: 可选策略级默认滑点映射
                              （strategy_id->slippage）。
                              下单优先级：订单级 > 策略级 > 引擎级。
    :param strategy_commission: 可选策略级默认佣金映射
                                （strategy_id->commission）。
                                下单优先级：订单级 > 策略级 > 引擎级。
    :param portfolio_risk_budget: 可选账户级累计风险预算上限
    :param risk_budget_mode: 风险预算口径，支持 order_notional/trade_notional
    :param risk_budget_reset_daily: 风险预算是否按交易日重置
    :param analyzer_plugins: Analyzer 插件列表，
                             接收 on_start/on_bar/on_trade/on_finish 生命周期事件
    :param on_event: 可选流式事件回调。阶段 5 后 `run_backtest` 始终走统一事件内核；
                     不传时内部使用 no-op 回调并保持返回语义不变。
    :param broker_profile: 可选 broker 参数模板名称，
                           如 "cn_stock_miniqmt" / "cn_stock_t1_low_fee" /
                           "cn_stock_sim_high_slippage"，
                           用于快速注入一组回测参数默认值。
    故障速查可参考 docs/zh/advanced/runtime_config.md，
    英文文档参考 docs/en/advanced/runtime_config.md
    :param instruments_config: 标的配置列表或字典 (可选)
    :return: 回测结果 Result 对象

    配置优先级说明 (Parameter Priority):
    ----------------------------------
    本函数参数采用以下优先级顺序解析（由高到低）：

    1. **Explicit Arguments (显式参数)**:
       直接传递给 `run_backtest` 的参数优先级最高。
       例如: `run_backtest(..., start_time="2022-01-01")` 会覆盖 Config 中的设置。

    2. **Configuration Objects (配置对象)**:
       如果显式参数为 `None`，则尝试从 `config` (`BacktestConfig`) 及其子配置
       (`StrategyConfig`) 中读取。
       例如: `config.start_time` 或 `config.strategy_config.initial_cash`。

    3. **Default Values (默认值)**:
       如果上述两者都未提供，则使用系统默认值。
       例如: `initial_cash` 默认为 1,000,000。
    """
    if "_engine_mode" in kwargs:
        raise TypeError("_engine_mode is no longer supported")
    _raise_if_legacy_execution_policy_used(
        legacy_mode_used="execution_mode" in kwargs,
        legacy_timer_used="timer_execution_policy" in kwargs,
        api_name="run_backtest",
    )
    strategy_config = config.strategy_config if config is not None else None
    (
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
    ) = _apply_strategy_config_overrides(
        strategy_config=strategy_config,
        strategy_id=strategy_id,
        strategies_by_slot=strategies_by_slot,
        strategy_max_order_value=strategy_max_order_value,
        strategy_max_order_size=strategy_max_order_size,
        strategy_max_position_size=strategy_max_position_size,
        strategy_max_daily_loss=strategy_max_daily_loss,
        strategy_max_drawdown=strategy_max_drawdown,
        strategy_reduce_only_after_risk=strategy_reduce_only_after_risk,
        strategy_risk_cooldown_bars=strategy_risk_cooldown_bars,
        strategy_priority=strategy_priority,
        strategy_risk_budget=strategy_risk_budget,
        strategy_fill_policy=strategy_fill_policy,
        strategy_slippage=strategy_slippage,
        strategy_commission=strategy_commission,
        portfolio_risk_budget=portfolio_risk_budget,
        strategy_runtime_config=strategy_runtime_config,
        strategy_source=strategy_source,
        strategy_loader=strategy_loader,
        strategy_loader_options=strategy_loader_options,
    )
    broker_profile_values = _resolve_broker_profile(broker_profile)
    if broker_profile_values:
        if initial_cash is None:
            initial_cash = cast(
                Optional[float], broker_profile_values.get("initial_cash")
            )
        if commission_rate is None:
            commission_rate = cast(
                Optional[float], broker_profile_values.get("commission_rate")
            )
        if slippage is None:
            slippage = cast(Optional[float], broker_profile_values.get("slippage"))
        if volume_limit_pct is None:
            volume_limit_pct = cast(
                Optional[float], broker_profile_values.get("volume_limit_pct")
            )
        if lot_size is None:
            lot_size = cast(
                Optional[Union[int, Dict[str, int]]],
                broker_profile_values.get("lot_size"),
            )
        if stamp_tax_rate is None:
            stamp_tax_rate = cast(
                Optional[float], broker_profile_values.get("stamp_tax_rate")
            )
        if transfer_fee_rate is None:
            transfer_fee_rate = cast(
                Optional[float], broker_profile_values.get("transfer_fee_rate")
            )
        if min_commission is None:
            min_commission = cast(
                Optional[float], broker_profile_values.get("min_commission")
            )
    portfolio_risk_budget, risk_budget_mode = _validate_strategy_risk_inputs(
        strategies_by_slot=strategies_by_slot,
        strategy_max_order_value=strategy_max_order_value,
        strategy_max_order_size=strategy_max_order_size,
        strategy_max_position_size=strategy_max_position_size,
        strategy_max_daily_loss=strategy_max_daily_loss,
        strategy_max_drawdown=strategy_max_drawdown,
        strategy_reduce_only_after_risk=strategy_reduce_only_after_risk,
        strategy_risk_cooldown_bars=strategy_risk_cooldown_bars,
        strategy_priority=strategy_priority,
        strategy_risk_budget=strategy_risk_budget,
        portfolio_risk_budget=portfolio_risk_budget,
        risk_budget_mode=risk_budget_mode,
    )
    risk_budget_reset_daily = bool(risk_budget_reset_daily)
    effective_strategy_id = strategy_id or "_default"
    prepared_stream_runtime = _prepare_stream_runtime(
        on_event=on_event,
        kwargs=kwargs,
        owner_strategy_id=effective_strategy_id,
        patch_owner_strategy_id=True,
    )
    stream_on_event = prepared_stream_runtime.stream_on_event
    event_stats_snapshot = prepared_stream_runtime.event_stats_snapshot
    stream_progress_interval = prepared_stream_runtime.stream_progress_interval
    stream_equity_interval = prepared_stream_runtime.stream_equity_interval
    stream_batch_size = prepared_stream_runtime.stream_batch_size
    stream_max_buffer = prepared_stream_runtime.stream_max_buffer
    stream_error_mode = prepared_stream_runtime.stream_error_mode
    stream_mode = prepared_stream_runtime.stream_mode

    # 0. 设置默认值 (如果未传入且未在 Config 中设置)
    # 优先级: 参数 > Config > 默认值

    # Defaults
    DEFAULT_INITIAL_CASH = float(getattr(StrategyConfig, "initial_cash", 100000.0))
    DEFAULT_COMMISSION_RATE = 0.0
    DEFAULT_TIMEZONE = "Asia/Shanghai"
    DEFAULT_SHOW_PROGRESS = True
    DEFAULT_HISTORY_DEPTH = 0

    # Resolve Initial Cash
    if initial_cash is None:
        if config and config.strategy_config:
            initial_cash = config.strategy_config.initial_cash
        else:
            initial_cash = DEFAULT_INITIAL_CASH

    # Resolve Commission Rate
    if commission_rate is None:
        if config and config.strategy_config:
            commission_rate = config.strategy_config.commission_rate
        else:
            commission_rate = DEFAULT_COMMISSION_RATE

    # Resolve Other Fees (if not passed as args, check config)
    if config and config.strategy_config:
        if stamp_tax_rate is None:
            stamp_tax_rate = config.strategy_config.stamp_tax_rate
        if transfer_fee_rate is None:
            transfer_fee_rate = config.strategy_config.transfer_fee_rate
        if min_commission is None:
            min_commission = config.strategy_config.min_commission
    if stamp_tax_rate is None:
        stamp_tax_rate = 0.0
    if transfer_fee_rate is None:
        transfer_fee_rate = 0.0
    if min_commission is None:
        min_commission = 0.0

    # Resolve Slippage & Volume Limit
    if slippage is None:
        if config and config.strategy_config:
            slippage = config.strategy_config.slippage
        else:
            slippage = 0.0

    if volume_limit_pct is None:
        if config and config.strategy_config:
            volume_limit_pct = config.strategy_config.volume_limit_pct
        else:
            volume_limit_pct = 0.25

    # Resolve Timezone
    if timezone is None:
        if config and config.timezone:
            timezone = config.timezone
        else:
            timezone = DEFAULT_TIMEZONE

    # Resolve Show Progress
    if show_progress is None:
        if config and config.show_progress is not None:
            show_progress = config.show_progress
        else:
            show_progress = DEFAULT_SHOW_PROGRESS

    # Resolve History Depth
    if history_depth is None:
        if config and config.history_depth is not None:
            history_depth = config.history_depth
        else:
            history_depth = DEFAULT_HISTORY_DEPTH

    # 1. 确保日志已初始化
    logger = get_logger()
    has_effective_handler = any(
        not isinstance(handler, logging.NullHandler) for handler in logger.handlers
    )
    if not has_effective_handler:
        register_logger(console=True, level="INFO")
        logger = get_logger()
    normalized_analyzers = _coerce_analyzer_plugins(analyzer_plugins)

    # 1.2 检查 PyCharm 环境下的进度条可见性
    if show_progress and "PYCHARM_HOSTED" in os.environ:
        # PyCharm Console 或 Run 窗口未开启模拟终端时，isatty 通常为 False
        if not sys.stderr.isatty():
            logger.warning(
                "Progress bar might be invisible in PyCharm. "
                "Solution: Enable 'Emulate terminal in output console' "
                "in Run Configuration."
            )

    # 1.5 处理 Config 覆盖 (剩余部分)
    # Resolve effective start/end time for filtering
    # Priority: explicit argument > config

    if start_time is None:
        if config and config.start_time:
            start_time = config.start_time

    if end_time is None:
        if config and config.end_time:
            end_time = config.end_time

    # Handle strategy_params explicitly
    if "strategy_params" in kwargs:
        s_params = kwargs.pop("strategy_params")
        if isinstance(s_params, dict):
            kwargs.update(s_params)
    if "strategy_runtime_config" in kwargs:
        kwargs_runtime_config = kwargs.pop("strategy_runtime_config")
        if strategy_runtime_config is None:
            strategy_runtime_config = kwargs_runtime_config
    symbols, effective_symbols = _resolve_effective_symbols(
        symbols=symbols,
        kwargs=kwargs,
        api_name="run_backtest",
    )

    strategy_input = resolve_strategy_input(
        strategy=strategy,
        strategy_source=strategy_source,
        strategy_loader=strategy_loader,
        strategy_loader_options=strategy_loader_options,
    )
    strategy_kwargs = dict(kwargs)
    if start_time and _accepts_strategy_kwarg(strategy_input, "start_time"):
        strategy_kwargs["start_time"] = start_time
    if end_time and _accepts_strategy_kwarg(strategy_input, "end_time"):
        strategy_kwargs["end_time"] = end_time
    if (
        symbols is not None
        and "symbols" not in strategy_kwargs
        and _accepts_strategy_kwarg(strategy_input, "symbols")
    ):
        strategy_kwargs["symbols"] = symbols
    strategy_instance = _build_strategy_instance(
        strategy_input,
        strategy_kwargs,
        strict_strategy_params,
        logger,
        initialize,
        on_start,
        on_stop,
        on_tick,
        on_order,
        on_trade,
        on_timer,
        context,
    )
    slot_strategy_instances: Dict[str, Strategy] = {}
    if strategies_by_slot:
        for slot_key, slot_strategy_input in strategies_by_slot.items():
            slot_key_str = str(slot_key).strip()
            if not slot_key_str:
                raise ValueError("strategy slot id cannot be empty")
            slot_strategy_kwargs = dict(kwargs)
            if symbols is not None and _accepts_strategy_kwarg(
                slot_strategy_input, "symbols"
            ):
                slot_strategy_kwargs["symbols"] = symbols
            if start_time and _accepts_strategy_kwarg(
                slot_strategy_input, "start_time"
            ):
                slot_strategy_kwargs["start_time"] = start_time
            if end_time and _accepts_strategy_kwarg(slot_strategy_input, "end_time"):
                slot_strategy_kwargs["end_time"] = end_time
            slot_strategy_instances[slot_key_str] = _build_strategy_instance(
                slot_strategy_input,
                slot_strategy_kwargs,
                strict_strategy_params,
                logger,
                initialize,
                on_start,
                on_stop,
                on_tick,
                on_order,
                on_trade,
                on_timer,
                context,
            )
    all_strategy_instances = [strategy_instance, *slot_strategy_instances.values()]
    configured_slot_ids = [effective_strategy_id]
    for slot_key in slot_strategy_instances.keys():
        if slot_key not in configured_slot_ids:
            configured_slot_ids.append(slot_key)
    normalized_strategy_fill_policy = _normalize_strategy_fill_policy_map(
        strategy_fill_policy,
        configured_slot_ids,
        logger,
    )
    normalized_strategy_slippage = _normalize_strategy_slippage_map(
        strategy_slippage,
        configured_slot_ids,
    )
    normalized_strategy_commission = _normalize_strategy_commission_map(
        strategy_commission,
        configured_slot_ids,
    )
    setattr(strategy_instance, "_owner_strategy_id", effective_strategy_id)
    for slot_key, slot_strategy in slot_strategy_instances.items():
        setattr(slot_strategy, "_owner_strategy_id", slot_key)
    setattr(strategy_instance, "_slot_strategies", dict(slot_strategy_instances))
    setattr(strategy_instance, "_strategy_slot_ids", list(configured_slot_ids))
    if normalized_strategy_fill_policy is not None:
        for current_strategy in all_strategy_instances:
            setattr(
                current_strategy,
                "_strategy_fill_policy_map",
                dict(normalized_strategy_fill_policy),
            )
    if normalized_strategy_slippage is not None:
        for current_strategy in all_strategy_instances:
            setattr(
                current_strategy,
                "_strategy_slippage_map",
                dict(normalized_strategy_slippage),
            )
    if normalized_strategy_commission is not None:
        for current_strategy in all_strategy_instances:
            setattr(
                current_strategy,
                "_strategy_commission_map",
                dict(normalized_strategy_commission),
            )

    if strategy_runtime_config is not None and isinstance(strategy_instance, Strategy):
        _apply_strategy_runtime_config(
            strategy_instance,
            strategy_runtime_config,
            runtime_config_override,
            logger,
        )
        for slot_strategy in slot_strategy_instances.values():
            _apply_strategy_runtime_config(
                slot_strategy,
                strategy_runtime_config,
                runtime_config_override,
                logger,
            )

    # 注入 context
    if context:
        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "_context"):
                continue
            for k, v in context.items():
                setattr(current_strategy, k, v)

    # 注入 Config 中的 Risk Config
    if config and config.strategy_config and config.strategy_config.risk:
        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "risk_config"):
                current_strategy.risk_config = config.strategy_config.risk  # type: ignore

    # 注入费率配置到 Strategy 实例
    for current_strategy in all_strategy_instances:
        if hasattr(current_strategy, "commission_rate"):
            current_strategy.commission_rate = commission_rate
        if hasattr(current_strategy, "min_commission"):
            current_strategy.min_commission = min_commission
        if hasattr(current_strategy, "stamp_tax_rate"):
            current_strategy.stamp_tax_rate = stamp_tax_rate
        if hasattr(current_strategy, "transfer_fee_rate"):
            current_strategy.transfer_fee_rate = transfer_fee_rate

    # 注入 lot_size
    # lot_size 参数可能是 int 或 dict。
    # 如果是 dict，则 Strategy._calculate_max_buy_qty 会自动处理
    if lot_size is not None:
        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "lot_size"):
                current_strategy.lot_size = lot_size

    preliminary_symbols: List[str] = list(effective_symbols)
    if config and config.instruments:
        for s in config.instruments:
            if s not in preliminary_symbols:
                preliminary_symbols.append(s)
    preliminary_inst_conf_map: Dict[str, Any] = {}
    if config and config.instruments_config:
        if isinstance(config.instruments_config, list):
            for conf_item in config.instruments_config:
                if conf_item.symbol not in preliminary_inst_conf_map:
                    preliminary_inst_conf_map[conf_item.symbol] = conf_item
        elif isinstance(config.instruments_config, dict):
            for k, v in config.instruments_config.items():
                if k not in preliminary_inst_conf_map:
                    preliminary_inst_conf_map[k] = v
    preliminary_prebuilt_instruments: Dict[str, Any] = {}
    if "instruments" in kwargs:
        raw_instruments = kwargs["instruments"]
        if isinstance(raw_instruments, list):
            for item in raw_instruments:
                preliminary_prebuilt_instruments[item.symbol] = item
        elif isinstance(raw_instruments, dict):
            preliminary_prebuilt_instruments.update(raw_instruments)
    preliminary_default_expiry = _normalize_expiry_date_yyyymmdd(
        kwargs.get("expiry_date", None)
    )
    preliminary_default_option_type = kwargs.get("option_type", None)
    preliminary_default_strike_price = kwargs.get("strike_price", None)
    preliminary_default_asset_type = kwargs.get("asset_type", AssetType.Stock)
    preliminary_default_multiplier = kwargs.get("multiplier", 1.0)
    preliminary_default_margin_ratio = kwargs.get("margin_ratio", 1.0)
    preliminary_default_tick_size = kwargs.get("tick_size", 0.01)
    preliminary_lot_size = kwargs.get("lot_size", 1)
    preliminary_default_settlement_type = _settlement_type_to_upper_name(
        kwargs.get("settlement_type", None)
    )
    preliminary_default_settlement_price = kwargs.get("settlement_price", None)
    preliminary_snapshots: Dict[str, InstrumentSnapshot] = {}
    for sym in preliminary_symbols:
        if sym in preliminary_prebuilt_instruments:
            prebuilt = preliminary_prebuilt_instruments[sym]
            preliminary_snapshots[sym] = InstrumentSnapshot(
                symbol=sym,
                asset_type=_asset_type_to_upper_name(
                    getattr(prebuilt, "asset_type", "")
                ),
                multiplier=float(getattr(prebuilt, "multiplier", 1.0)),
                margin_ratio=float(getattr(prebuilt, "margin_ratio", 1.0)),
                tick_size=float(getattr(prebuilt, "tick_size", 0.01)),
                lot_size=float(getattr(prebuilt, "lot_size", 1.0)),
                settlement_type=_settlement_type_to_upper_name(
                    getattr(prebuilt, "settlement_type", None)
                ),
                settlement_price=(
                    float(getattr(prebuilt, "settlement_price"))
                    if getattr(prebuilt, "settlement_price", None) is not None
                    else None
                ),
            )
            continue
        conf = preliminary_inst_conf_map.get(sym)
        symbol_lot_size: Optional[float] = None
        if isinstance(preliminary_lot_size, int):
            symbol_lot_size = float(preliminary_lot_size)
        elif isinstance(preliminary_lot_size, dict):
            raw_lot = preliminary_lot_size.get(sym)
            if raw_lot is not None:
                symbol_lot_size = float(raw_lot)
        if conf is None:
            preliminary_snapshots[sym] = InstrumentSnapshot(
                symbol=sym,
                asset_type=_asset_type_to_upper_name(preliminary_default_asset_type),
                multiplier=float(preliminary_default_multiplier),
                margin_ratio=float(preliminary_default_margin_ratio),
                tick_size=float(preliminary_default_tick_size),
                lot_size=float(symbol_lot_size or 1.0),
                option_type=_option_type_to_upper_name(preliminary_default_option_type),
                strike_price=(
                    float(preliminary_default_strike_price)
                    if preliminary_default_strike_price is not None
                    else None
                ),
                expiry_date=preliminary_default_expiry,
                settlement_type=preliminary_default_settlement_type,
                settlement_price=(
                    float(preliminary_default_settlement_price)
                    if preliminary_default_settlement_price is not None
                    else None
                ),
            )
            continue
        conf_static_attrs = getattr(conf, "static_attrs", {})
        if conf_static_attrs is None:
            conf_static_attrs = {}
        if not isinstance(conf_static_attrs, dict):
            raise TypeError("InstrumentConfig.static_attrs must be Dict[str, scalar]")
        conf_lot = (
            float(conf.lot_size)
            if conf.lot_size is not None
            else float(symbol_lot_size or 1.0)
        )
        preliminary_snapshots[sym] = InstrumentSnapshot(
            symbol=sym,
            asset_type=_asset_type_to_upper_name(conf.asset_type),
            multiplier=float(conf.multiplier),
            margin_ratio=float(conf.margin_ratio),
            tick_size=float(conf.tick_size),
            lot_size=conf_lot,
            option_type=_option_type_to_upper_name(conf.option_type),
            strike_price=(
                float(conf.strike_price) if conf.strike_price is not None else None
            ),
            expiry_date=_normalize_expiry_date_yyyymmdd(conf.expiry_date),
            underlying_symbol=(
                str(conf.underlying_symbol)
                if conf.underlying_symbol is not None
                else None
            ),
            settlement_type=_settlement_type_to_upper_name(conf.settlement_type),
            settlement_price=(
                float(conf.settlement_price)
                if conf.settlement_price is not None
                else None
            ),
            static_attrs=dict(conf_static_attrs),
        )
    for current_strategy in all_strategy_instances:
        current_strategy._set_instrument_snapshots(preliminary_snapshots)

    # 调用 on_start 获取订阅
    # 注意：现在调用 _on_start_internal 来触发自动发现
    if hasattr(strategy_instance, "_on_start_internal"):
        strategy_instance._on_start_internal()
    elif hasattr(strategy_instance, "on_start"):
        strategy_instance.on_start()
    for slot_strategy in slot_strategy_instances.values():
        if hasattr(slot_strategy, "_on_start_internal"):
            slot_strategy._on_start_internal()
        elif hasattr(slot_strategy, "on_start"):
            slot_strategy.on_start()

    # 3. 准备数据源和 Symbol
    feed = DataFeed()
    symbols = []
    data_map_for_indicators = {}

    symbols = list(effective_symbols)

    # Merge with Config instruments
    if config and config.instruments:
        for s in config.instruments:
            if s not in symbols:
                symbols.append(s)

    # Merge with Strategy subscriptions
    if hasattr(strategy_instance, "_subscriptions"):
        for s in strategy_instance._subscriptions:
            if s not in symbols:
                symbols.append(s)
    for slot_strategy in slot_strategy_instances.values():
        if hasattr(slot_strategy, "_subscriptions"):
            for s in slot_strategy._subscriptions:
                if s not in symbols:
                    symbols.append(s)

    analyzer_manager = AnalyzerManager()
    for plugin in normalized_analyzers:
        analyzer_manager.register(plugin)
    for current_strategy in all_strategy_instances:
        setattr(current_strategy, "_analyzer_manager", analyzer_manager)

    # Determine Data Loading Strategy
    if data is not None:
        if isinstance(data, DataFeed):
            # Use provided DataFeed
            feed = data
            # We don't know symbols in feed easily without iteration,
            # but usually feed contains all needed data.
            # We might need to update 'symbols' if they were not provided explicitly?
            # For now, assume user provided symbols or feed covers them.
        elif _is_data_feed_adapter(data):
            adapter_data_map = _load_data_map_from_adapter(
                adapter=data,
                symbols=symbols,
                start_time=start_time,
                end_time=end_time,
                timezone=timezone,
            )
            for sym, df in adapter_data_map.items():
                df_prep = prepare_dataframe(df)
                data_map_for_indicators[sym] = df_prep
                arrays = df_to_arrays(df_prep, symbol=sym)
                feed.add_arrays(*arrays)  # type: ignore
                if sym not in symbols:
                    symbols.append(sym)
            feed.sort()
        elif isinstance(data, pd.DataFrame):
            df_input = data
            # Ensure index is datetime
            if not isinstance(df_input.index, pd.DatetimeIndex):
                # Try to find a date column if index is not date
                # Common candidates: "date", "timestamp", "datetime"
                found_date = False
                for col in ["date", "timestamp", "datetime", "Date", "Timestamp"]:
                    if col in df_input.columns:
                        df_input = df_input.set_index(col)
                        found_date = True
                        break

                if not found_date:
                    # try convert index
                    try:
                        df_input.index = pd.to_datetime(df_input.index)
                    except Exception:
                        pass

            # Ensure index is pd.Timestamp compatible
            # (convert datetime.date to Timestamp)
            # This is handled by pd.to_datetime but let's be safe for object index
            if df_input.index.dtype == "object":
                try:
                    df_input.index = pd.to_datetime(df_input.index)
                except Exception:
                    pass

            # Filter by date if provided
            if start_time:
                # Handle potential mismatch between Timestamp and datetime.date
                ts_start = pd.Timestamp(start_time)
                # If index is date objects, compare with date()
                if (
                    len(df_input) > 0
                    and isinstance(df_input.index[0], (dt_module.date))
                    and not isinstance(df_input.index[0], dt_module.datetime)
                ):
                    df_input = df_input[df_input.index >= ts_start.date()]
                else:
                    df_input = df_input[df_input.index >= ts_start]

            if end_time:
                ts_end = pd.Timestamp(end_time)
                if (
                    len(df_input) > 0
                    and isinstance(df_input.index[0], (dt_module.date))
                    and not isinstance(df_input.index[0], dt_module.datetime)
                ):
                    df_input = df_input[df_input.index <= ts_end.date()]
                else:
                    df_input = df_input[df_input.index <= ts_end]

            df = prepare_dataframe(df_input)
            if "symbol" in df.columns:
                df = df.copy()
                df["symbol"] = df["symbol"].astype(str)
                filter_symbols = bool(symbols and "BENCHMARK" not in symbols)
                if filter_symbols:
                    df = df[df["symbol"].isin(symbols)]
                if not df.empty:
                    arrays = df_to_arrays(df)
                    feed.add_arrays(*arrays)  # type: ignore
                    grouped = df.groupby("symbol", sort=False)
                    for grouped_symbol, grouped_df in grouped:
                        sym = str(grouped_symbol)
                        data_map_for_indicators[sym] = grouped_df.copy()
                    detected_symbols = [str(s) for s in df["symbol"].unique().tolist()]
                    if not symbols or symbols == ["BENCHMARK"]:
                        symbols = detected_symbols
                    else:
                        for sym in detected_symbols:
                            if sym not in symbols:
                                symbols.append(sym)
                feed.sort()
            else:
                target_symbol = symbols[0] if symbols else "BENCHMARK"
                data_map_for_indicators[target_symbol] = df
                arrays = df_to_arrays(df, symbol=target_symbol)
                feed.add_arrays(*arrays)  # type: ignore
                feed.sort()
                if target_symbol not in symbols:
                    symbols = [target_symbol]
        elif isinstance(data, dict):
            # If explicit symbols are provided (i.e., not just the default "BENCHMARK"),
            # we filter the data dictionary to only include requested symbols.
            filter_symbols = "BENCHMARK" not in symbols

            for sym, df in data.items():
                if filter_symbols and sym not in symbols:
                    continue

                # Ensure index is datetime
                if not isinstance(df.index, pd.DatetimeIndex):
                    # Try to find a date column if index is not date
                    found_date = False
                    for col in ["date", "timestamp", "datetime", "Date", "Timestamp"]:
                        if col in df.columns:
                            df = df.set_index(col)
                            df.index = pd.to_datetime(df.index)
                            found_date = True
                            break

                    if not found_date:
                        try:
                            df.index = pd.to_datetime(df.index)
                        except Exception:
                            pass

                # Filter by date
                if start_time:
                    df = df[df.index >= pd.Timestamp(start_time)]
                if end_time:
                    df = df[df.index <= pd.Timestamp(end_time)]

                df_prep = prepare_dataframe(df)
                data_map_for_indicators[sym] = df_prep
                arrays = df_to_arrays(df_prep, symbol=sym)
                feed.add_arrays(*arrays)  # type: ignore
                if sym not in symbols:
                    symbols.append(sym)
            feed.sort()
        elif isinstance(data, list):
            if data:
                # Filter by date
                if start_time:
                    # Explicitly convert to int to satisfy mypy
                    ts_start: int = int(pd.Timestamp(start_time).value)  # type: ignore
                    data = [b for b in data if b.timestamp >= ts_start]  # type: ignore
                if end_time:
                    ts_end: int = int(pd.Timestamp(end_time).value)  # type: ignore
                    data = [b for b in data if b.timestamp <= ts_end]  # type: ignore

                data.sort(key=lambda b: b.timestamp)
                feed.add_bars(data)

                # Construct DataFrame for indicator calculation
                # Group by symbol just in case
                bars_by_sym: Dict[str, List[Dict[str, Any]]] = {}
                for bar in data:
                    if bar.symbol not in bars_by_sym:
                        bars_by_sym[bar.symbol] = []
                    bars_by_sym[bar.symbol].append(
                        {
                            "timestamp": pd.Timestamp(
                                bar.timestamp, unit="ns", tz="UTC"
                            ),
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                        }
                    )

                for sym, records in bars_by_sym.items():
                    df = pd.DataFrame(records)
                    if not df.empty:
                        df.set_index("timestamp", inplace=True)
                        df.sort_index(inplace=True)
                        data_map_for_indicators[sym] = df
    else:
        # Load from Catalog / Akshare
        if not symbols:
            logger.warning("No symbols specified and no data provided.")

        catalog = ParquetDataCatalog(root_path=catalog_path)
        logger.info(f"Loading backtest data from catalog root: {catalog.root}")
        # start_time / end_time already resolved above

        loaded_count = 0
        for sym in symbols:
            # Try Catalog
            df = catalog.read(sym, start_time=start_time, end_time=end_time)
            if df.empty:
                logger.warning(f"Data not found in catalog for {sym}")
                continue

            if not df.empty:
                df = prepare_dataframe(df)
                data_map_for_indicators[sym] = df
                arrays = df_to_arrays(df, symbol=sym)
                feed.add_arrays(*arrays)  # type: ignore
                loaded_count += 1

        if loaded_count > 0:
            feed.sort()
        else:
            if symbols:
                logger.warning("Failed to load data for all requested symbols.")

    # Inject timezone to strategy
    for current_strategy in all_strategy_instances:
        current_strategy.timezone = timezone

    # Inject trading days to strategy (for add_daily_timer)
    all_strategy_instances = [strategy_instance, *slot_strategy_instances.values()]
    if data_map_for_indicators:
        all_dates: set[pd.Timestamp] = set()
        day_bounds: Dict[str, Tuple[int, int]] = {}
        for df in data_map_for_indicators.values():
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                local_index = _index_to_local_trading_days(
                    cast(pd.DatetimeIndex, df.index), timezone
                )
                normalized_index = cast(pd.DatetimeIndex, local_index.normalize())
                dates = normalized_index.unique()
                all_dates.update(dates)
                for raw_day_ts in dates:
                    day_ts = pd.Timestamp(raw_day_ts)
                    day_df = df[normalized_index == day_ts]
                    if day_df.empty:
                        continue
                    day_key = day_ts.date().isoformat()
                    start_ns = int(day_df.index.min().value)
                    end_ns = int(day_df.index.max().value)
                    if day_key in day_bounds:
                        prev_start, prev_end = day_bounds[day_key]
                        day_bounds[day_key] = (
                            min(prev_start, start_ns),
                            max(prev_end, end_ns),
                        )
                    else:
                        day_bounds[day_key] = (start_ns, end_ns)

        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "_trading_days") and all_dates:
                current_strategy._trading_days = sorted(list(all_dates))
            if hasattr(current_strategy, "_trading_day_bounds"):
                current_strategy._trading_day_bounds = day_bounds

    # 4. 配置引擎
    engine = Engine()
    for current_strategy in all_strategy_instances:
        setattr(current_strategy, "_engine", engine)
    if analyzer_manager.plugins:
        try:
            analyzer_manager.on_start(
                {
                    "engine": engine,
                    "strategy": strategy_instance,
                    "strategies": list(all_strategy_instances),
                    "slot_strategy_map": {
                        effective_strategy_id: strategy_instance,
                        **slot_strategy_instances,
                    },
                    "symbols": list(symbols),
                }
            )
        except Exception as e:
            logger.error(f"Analyzer on_start error: {e}")
    # engine.set_timezone_name(timezone)
    offset_delta = pd.Timestamp.now(tz=timezone).utcoffset()
    if offset_delta is None:
        raise ValueError(f"Invalid timezone: {timezone}")
    offset = int(offset_delta.total_seconds())
    engine.set_timezone(offset)
    engine.set_cash(initial_cash)
    if hasattr(engine, "set_default_strategy_id"):
        cast(Any, engine).set_default_strategy_id(effective_strategy_id)
    if (
        strategies_by_slot
        and hasattr(engine, "set_strategy_slots")
        and hasattr(engine, "set_strategy_for_slot")
    ):
        cast(Any, engine).set_strategy_slots(configured_slot_ids)
        for slot_index, slot_id in enumerate(configured_slot_ids):
            assigned_strategy: Optional[Strategy] = None
            if slot_id == effective_strategy_id:
                assigned_strategy = strategy_instance
            else:
                assigned_strategy = slot_strategy_instances.get(slot_id)
            if assigned_strategy is not None:
                cast(Any, engine).set_strategy_for_slot(slot_index, assigned_strategy)
    if strategy_priority and hasattr(engine, "set_strategy_priorities"):
        normalized_strategy_priority: Dict[str, int] = {}
        for strategy_key, raw_priority in strategy_priority.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_priority contains empty strategy id")
            priority_value = int(raw_priority)
            normalized_strategy_priority[strategy_key_str] = priority_value
        unknown_keys = sorted(
            set(normalized_strategy_priority.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_priority contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_priorities(normalized_strategy_priority)
    if strategy_risk_budget and hasattr(engine, "set_strategy_risk_budget_limits"):
        normalized_strategy_risk_budget: Dict[str, float] = {}
        for strategy_key, raw_budget in strategy_risk_budget.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_risk_budget contains empty strategy id")
            budget_value = float(raw_budget)
            if not pd.notna(budget_value) or budget_value < 0.0:
                raise ValueError(
                    f"strategy_risk_budget for {strategy_key_str} must be >= 0"
                )
            normalized_strategy_risk_budget[strategy_key_str] = budget_value
        unknown_keys = sorted(
            set(normalized_strategy_risk_budget.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_risk_budget contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_risk_budget_limits(
            normalized_strategy_risk_budget
        )
    if hasattr(engine, "set_portfolio_risk_budget_limit"):
        cast(Any, engine).set_portfolio_risk_budget_limit(portfolio_risk_budget)
    if hasattr(engine, "set_risk_budget_mode"):
        cast(Any, engine).set_risk_budget_mode(risk_budget_mode)
    if hasattr(engine, "set_risk_budget_reset_daily"):
        cast(Any, engine).set_risk_budget_reset_daily(risk_budget_reset_daily)
    if strategy_max_order_value and hasattr(
        engine, "set_strategy_max_order_value_limits"
    ):
        normalized_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_order_value.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_order_value contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_order_value for {strategy_key_str} must be >= 0"
                )
            normalized_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_order_value contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_order_value_limits(normalized_limits)
    if strategy_max_order_size and hasattr(
        engine, "set_strategy_max_order_size_limits"
    ):
        normalized_limits_by_size: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_order_size.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_order_size contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_order_size for {strategy_key_str} must be >= 0"
                )
            normalized_limits_by_size[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_limits_by_size.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_order_size contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_order_size_limits(normalized_limits_by_size)
    if strategy_max_position_size and hasattr(
        engine, "set_strategy_max_position_size_limits"
    ):
        normalized_position_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_position_size.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_max_position_size contains empty strategy id"
                )
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_position_size for {strategy_key_str} must be >= 0"
                )
            normalized_position_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_position_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_position_size contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_position_size_limits(
            normalized_position_limits
        )
    if strategy_max_daily_loss and hasattr(
        engine, "set_strategy_max_daily_loss_limits"
    ):
        normalized_daily_loss_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_daily_loss.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_daily_loss contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_daily_loss for {strategy_key_str} must be >= 0"
                )
            normalized_daily_loss_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_daily_loss_limits.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_daily_loss contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_daily_loss_limits(
            normalized_daily_loss_limits
        )
    if strategy_max_drawdown and hasattr(engine, "set_strategy_max_drawdown_limits"):
        normalized_drawdown_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_drawdown.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_drawdown contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_drawdown for {strategy_key_str} must be >= 0"
                )
            normalized_drawdown_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_drawdown_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_drawdown contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_drawdown_limits(normalized_drawdown_limits)
    if strategy_reduce_only_after_risk and hasattr(
        engine, "set_strategy_reduce_only_after_risk"
    ):
        normalized_reduce_only_flags: Dict[str, bool] = {}
        for strategy_key, raw_flag in strategy_reduce_only_after_risk.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_reduce_only_after_risk contains empty strategy id"
                )
            normalized_reduce_only_flags[strategy_key_str] = bool(raw_flag)
        unknown_keys = sorted(
            set(normalized_reduce_only_flags.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_reduce_only_after_risk contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_reduce_only_after_risk(
            normalized_reduce_only_flags
        )
    if strategy_risk_cooldown_bars and hasattr(
        engine, "set_strategy_risk_cooldown_bars"
    ):
        normalized_cooldown_bars: Dict[str, int] = {}
        for strategy_key, raw_bars in strategy_risk_cooldown_bars.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_risk_cooldown_bars contains empty strategy id"
                )
            cooldown_bars = int(raw_bars)
            if cooldown_bars < 0:
                raise ValueError(
                    f"strategy_risk_cooldown_bars for {strategy_key_str} must be >= 0"
                )
            normalized_cooldown_bars[strategy_key_str] = cooldown_bars
        unknown_keys = sorted(
            set(normalized_cooldown_bars.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_risk_cooldown_bars contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_risk_cooldown_bars(normalized_cooldown_bars)
    if history_depth > 0:
        engine.set_history_depth(history_depth)
    if stream_on_event is not None:
        cast(Any, engine).set_stream_callback(stream_on_event)
        cast(Any, engine).set_stream_options(
            stream_progress_interval,
            stream_equity_interval,
            stream_batch_size,
            stream_max_buffer,
            stream_error_mode,
            stream_mode,
        )

    # Register Custom Matchers
    if custom_matchers:
        for asset_type, matcher in custom_matchers.items():
            try:
                cast(Any, engine).register_custom_matcher(asset_type, matcher)
            except Exception as e:
                logger.warning(
                    "Failed to register custom matcher for %s: %s",
                    asset_type,
                    e,
                )

    resolved_policy = _resolve_execution_policy(
        execution_mode="next_open",
        timer_execution_policy="same_cycle",
        fill_policy=fill_policy,
        logger=logger,
    )
    if not hasattr(engine, "set_fill_policy"):
        raise RuntimeError(
            "Engine binary does not expose set_fill_policy; please rebuild bindings"
        )
    cast(Any, engine).set_fill_policy(
        resolved_policy.price_basis,
        resolved_policy.bar_offset,
        resolved_policy.temporal,
    )
    timer_policy = resolved_policy.temporal
    if (
        not (resolved_policy.price_basis == "close" and resolved_policy.bar_offset == 0)
        and timer_policy == "same_cycle"
    ):
        logger.info(
            "temporal=%s has no effect when price_basis=%s and bar_offset=%s",
            timer_policy,
            resolved_policy.price_basis,
            resolved_policy.bar_offset,
        )

    # 4.1 市场规则配置
    china_futures_config: Optional[ChinaFuturesConfig] = None
    china_options_config: Optional[ChinaOptionsConfig] = None
    has_futures_instruments = False
    has_options_instruments = False
    has_non_futures_instruments = False
    if config is not None:
        china_futures_config = config.china_futures
        china_options_config = config.china_options
        if config.instruments_config:
            if isinstance(config.instruments_config, list):
                for inst in config.instruments_config:
                    asset_name = _parse_asset_type_name(inst.asset_type)
                    if asset_name == "futures":
                        has_futures_instruments = True
                    elif asset_name == "option":
                        has_options_instruments = True
                        has_non_futures_instruments = True
                    else:
                        has_non_futures_instruments = True
            elif isinstance(config.instruments_config, dict):
                for inst in config.instruments_config.values():
                    asset_name = _parse_asset_type_name(inst.asset_type)
                    if asset_name == "futures":
                        has_futures_instruments = True
                    elif asset_name == "option":
                        has_options_instruments = True
                        has_non_futures_instruments = True
                    else:
                        has_non_futures_instruments = True
    if not has_futures_instruments or not has_options_instruments:
        default_asset_name = _parse_asset_type_name(
            kwargs.get("asset_type", AssetType.Stock)
        )
        if not has_futures_instruments:
            has_futures_instruments = default_asset_name == "futures"
        if not has_options_instruments:
            has_options_instruments = default_asset_name == "option"
    if (
        not has_futures_instruments
        and china_futures_config
        and china_futures_config.instrument_templates_by_symbol_prefix
    ):
        has_futures_instruments = True

    if china_futures_config and has_futures_instruments:
        if (
            not china_futures_config.use_china_futures_market
            or has_non_futures_instruments
        ):
            engine.use_china_market()
        else:
            engine.use_china_futures_market()
        if t_plus_one:
            engine.set_t_plus_one(True)
    elif china_options_config and has_options_instruments:
        if china_options_config.use_china_market:
            engine.use_china_market()
        else:
            engine.use_simple_market(commission_rate)
        if t_plus_one:
            engine.set_t_plus_one(True)
    elif t_plus_one:
        engine.use_china_market()
        engine.set_t_plus_one(True)
    else:
        engine.use_simple_market(commission_rate)

    force_session_continuous = True
    if china_futures_config and has_futures_instruments:
        force_session_continuous = not china_futures_config.enforce_sessions
    engine.set_force_session_continuous(force_session_continuous)
    # 无论使用 SimpleMarket 还是 ChinaMarket，set_stock_fee_rules 都能正确配置费率
    engine.set_stock_fee_rules(
        commission_rate, stamp_tax_rate, transfer_fee_rate, min_commission
    )

    # Configure Execution parameters
    if slippage > 0:
        if hasattr(engine, "set_slippage"):
            # Assume "percent" model for the simple float config
            engine.set_slippage("percent", slippage)
        else:
            logger.warning(f"Slippage {slippage} set but not supported by Engine.")

    if volume_limit_pct != 0.25:
        if hasattr(engine, "set_volume_limit"):
            engine.set_volume_limit(volume_limit_pct)
        else:
            logger.warning(
                f"Volume limit {volume_limit_pct} set but not supported by Engine."
            )

    # Configure other asset fees if provided
    if "fund_commission" in kwargs:
        engine.set_fund_fee_rules(
            kwargs["fund_commission"],
            kwargs.get("fund_transfer_fee", 0.0),
            kwargs.get("fund_min_commission", 0.0),
        )

    if china_options_config and has_options_instruments:
        if china_options_config.fee_per_contract is not None:
            engine.set_option_fee_rules(china_options_config.fee_per_contract)
    elif "option_commission" in kwargs:
        engine.set_option_fee_rules(kwargs["option_commission"])

    if china_futures_config and has_futures_instruments:
        template_validation_by_prefix: Dict[
            str, Tuple[Optional[bool], Optional[bool]]
        ] = {}
        template_fee_by_prefix: Dict[str, float] = {}
        if china_futures_config.instrument_templates_by_symbol_prefix:
            for template in china_futures_config.instrument_templates_by_symbol_prefix:
                prefix = template.symbol_prefix.strip().upper()
                if not prefix:
                    continue
                if template.commission_rate is not None:
                    template_fee_by_prefix[prefix] = float(template.commission_rate)
                if (
                    template.enforce_tick_size is not None
                    or template.enforce_lot_size is not None
                ):
                    template_validation_by_prefix[prefix] = (
                        template.enforce_tick_size,
                        template.enforce_lot_size,
                    )

        if hasattr(engine, "set_futures_validation_options"):
            cast(Any, engine).set_futures_validation_options(
                bool(china_futures_config.enforce_tick_size),
                bool(china_futures_config.enforce_lot_size),
            )
        else:
            logger.warning(
                "set_futures_validation_options is not available "
                "in current engine binary"
            )
        merged_validation_by_prefix = dict(template_validation_by_prefix)
        if china_futures_config.validation_by_symbol_prefix:
            for validation_rule in china_futures_config.validation_by_symbol_prefix:
                prefix = validation_rule.symbol_prefix.strip().upper()
                if not prefix:
                    continue
                merged_validation_by_prefix[prefix] = (
                    validation_rule.enforce_tick_size,
                    validation_rule.enforce_lot_size,
                )
        if merged_validation_by_prefix:
            for prefix, (tick_opt, lot_opt) in merged_validation_by_prefix.items():
                if hasattr(engine, "set_futures_validation_options_by_prefix"):
                    cast(Any, engine).set_futures_validation_options_by_prefix(
                        prefix,
                        tick_opt,
                        lot_opt,
                    )
                else:
                    logger.warning(
                        "set_futures_validation_options_by_prefix is not available "
                        "in current engine binary"
                    )
                    break

        merged_fee_by_prefix = dict(template_fee_by_prefix)
        if china_futures_config.fee_by_symbol_prefix:
            for fee_rule in china_futures_config.fee_by_symbol_prefix:
                prefix = fee_rule.symbol_prefix.strip().upper()
                if not prefix:
                    continue
                merged_fee_by_prefix[prefix] = float(fee_rule.commission_rate)
        if merged_fee_by_prefix:
            for prefix, commission_rate_value in merged_fee_by_prefix.items():
                if hasattr(engine, "set_futures_fee_rules_by_prefix"):
                    cast(Any, engine).set_futures_fee_rules_by_prefix(
                        prefix,
                        commission_rate_value,
                    )
                else:
                    logger.warning(
                        "set_futures_fee_rules_by_prefix is not available "
                        "in current engine binary"
                    )
                    break
        if china_futures_config.sessions:
            session_ranges: List[Tuple[str, str, TradingSession]] = []
            for session_rule in china_futures_config.sessions:
                session_ranges.append(
                    (
                        session_rule.start,
                        session_rule.end,
                        _parse_trading_session(session_rule.session),
                    )
                )
            if session_ranges:
                engine.set_market_sessions(session_ranges)
        elif china_futures_config.enforce_sessions:
            session_ranges = []
            for start, end, session_name in _china_futures_session_template(
                china_futures_config.session_profile
            ):
                session_ranges.append(
                    (
                        start,
                        end,
                        _parse_trading_session(session_name),
                    )
                )
            if session_ranges:
                engine.set_market_sessions(session_ranges)

    if china_options_config and has_options_instruments:
        if china_options_config.fee_by_symbol_prefix:
            for option_fee_rule in china_options_config.fee_by_symbol_prefix:
                prefix = option_fee_rule.symbol_prefix.strip().upper()
                if not prefix:
                    continue
                if hasattr(engine, "set_options_fee_rules_by_prefix"):
                    cast(Any, engine).set_options_fee_rules_by_prefix(
                        prefix,
                        float(option_fee_rule.commission_per_contract),
                    )
                else:
                    logger.warning(
                        "set_options_fee_rules_by_prefix is not available "
                        "in current engine binary"
                    )
                    break
        if china_options_config.sessions:
            option_session_ranges: List[Tuple[str, str, TradingSession]] = []
            for option_session_rule in china_options_config.sessions:
                option_session_ranges.append(
                    (
                        option_session_rule.start,
                        option_session_rule.end,
                        _parse_trading_session(option_session_rule.session),
                    )
                )
            if option_session_ranges and not (
                china_futures_config
                and has_futures_instruments
                and china_futures_config.sessions
            ):
                engine.set_market_sessions(option_session_ranges)

    # Apply Risk Config

    # 1. Start with config from BacktestConfig
    current_risk_config: Optional[RiskConfig] = None
    if config and config.strategy_config and config.strategy_config.risk:
        current_risk_config = config.strategy_config.risk

    # 2. If risk_config (dict or object) is provided, merge/override
    if risk_config:
        if current_risk_config is None:
            current_risk_config = RiskConfig()

        if isinstance(risk_config, RiskConfig):
            # If explicit RiskConfig object provided, it takes precedence over
            # partial fields?
            # Or should we merge?
            # Strategy: If it's a full object, use it as base, but this might discard
            # config.risk
            # Better strategy: Copy attributes from override to current
            for field in risk_config.__dataclass_fields__:
                val = getattr(risk_config, field)
                if val is not None:
                    setattr(current_risk_config, field, val)
        elif isinstance(risk_config, dict):
            # Update fields from dict
            for k, v in risk_config.items():
                if hasattr(current_risk_config, k):
                    setattr(current_risk_config, k, v)
                else:
                    logger.warning(f"Unknown risk config key: {k}")

    # 3. Apply if exists
    if current_risk_config:
        apply_risk_config(engine, current_risk_config)

    # Get current manager
    rm = engine.risk_manager
    engine.risk_manager = rm

    # 5. 添加标的
    # 解析 Instrument Config
    inst_conf_map = {}

    # Handle explicit Instrument objects passed via kwargs
    prebuilt_instruments = {}
    if "instruments" in kwargs:
        obs = kwargs["instruments"]
        if isinstance(obs, list):
            for o in obs:
                prebuilt_instruments[o.symbol] = o
        elif isinstance(obs, dict):
            prebuilt_instruments.update(obs)

    # From BacktestConfig
    if config and config.instruments_config:
        if isinstance(config.instruments_config, list):
            for c in config.instruments_config:
                if c.symbol not in inst_conf_map:
                    inst_conf_map[c.symbol] = c
        elif isinstance(config.instruments_config, dict):
            for k, v in config.instruments_config.items():
                if k not in inst_conf_map:
                    inst_conf_map[k] = v

    # Default values from kwargs
    default_multiplier = kwargs.get("multiplier", 1.0)
    default_margin_ratio = kwargs.get("margin_ratio", 1.0)
    default_tick_size = kwargs.get("tick_size", 0.01)
    default_asset_type = kwargs.get("asset_type", AssetType.Stock)

    # Option specific fields
    default_option_type = kwargs.get("option_type", None)
    default_strike_price = kwargs.get("strike_price", None)
    default_expiry_date = _normalize_expiry_date_yyyymmdd(
        kwargs.get("expiry_date", None)
    )
    default_settlement_type = kwargs.get("settlement_type", None)
    default_settlement_price = kwargs.get("settlement_price", None)

    def _parse_asset_type(val: Union[str, AssetType]) -> AssetType:
        if isinstance(val, AssetType):
            return val
        if isinstance(val, str):
            v_lower = val.strip().lower()
            if v_lower == "stock":
                return AssetType.Stock
            if v_lower in {"future", "futures"}:
                return AssetType.Futures
            if v_lower == "fund":
                return AssetType.Fund
            if v_lower == "option":
                return AssetType.Option
        raise ValueError(f"Unsupported asset_type: {val}")

    def _parse_option_type(val: Any) -> Any:
        if val is None:
            return None
        # OptionType might not be available in current binary
        try:
            from ..akquant import OptionType  # type: ignore

            if isinstance(val, str):
                if val.lower() == "call":
                    return OptionType.Call
                if val.lower() == "put":
                    return OptionType.Put
                raise ValueError(f"Unsupported option_type: {val}")
            if str(val).endswith(".Call"):
                return OptionType.Call
            if str(val).endswith(".Put"):
                return OptionType.Put
        except ImportError:
            pass
        if isinstance(val, str):
            v = val.strip().upper()
            if v in {"CALL", "PUT"}:
                return v
            raise ValueError(f"Unsupported option_type: {val}")
        return val

    def _parse_settlement_type(
        val: Any,
    ) -> Tuple[Any, Optional[InstrumentSettlementMode]]:
        if val is None:
            return None, None
        if isinstance(val, SettlementType):
            if val == SettlementType.Physical:
                raise ValueError("Unsupported settlement_type: Physical")
            return val, _settlement_type_to_upper_name(val)
        if isinstance(val, str):
            key = val.strip().lower()
            if key in {"cash", "cash_last_price"}:
                return SettlementType.Cash, "CASH"
            if key in {"settlement_price", "cash_settlement_price"}:
                return SettlementType.Cash, "SETTLEMENT_PRICE"
            if key in {"force_close", "forceclose"}:
                return SettlementType.ForceClose, "FORCE_CLOSE"
            raise ValueError(f"Unsupported settlement_type: {val}")
        raise TypeError("settlement_type must be SettlementType or str")

    def _match_futures_template(
        symbol: str,
    ) -> Optional[ChinaFuturesInstrumentTemplateConfig]:
        if (
            china_futures_config is None
            or not china_futures_config.instrument_templates_by_symbol_prefix
        ):
            return None
        symbol_upper = symbol.upper()
        best_template: Optional[ChinaFuturesInstrumentTemplateConfig] = None
        best_len = 0
        for tpl in china_futures_config.instrument_templates_by_symbol_prefix:
            prefix = tpl.symbol_prefix.strip().upper()
            if not prefix:
                continue
            if symbol_upper.startswith(prefix) and len(prefix) > best_len:
                best_template = tpl
                best_len = len(prefix)
        return best_template

    instrument_snapshots: Dict[str, InstrumentSnapshot] = {}

    for sym in symbols:
        # Priority: Pre-built Instrument > Config > Default
        if sym in prebuilt_instruments:
            prebuilt = prebuilt_instruments[sym]
            engine.add_instrument(prebuilt)
            instrument_snapshots[sym] = InstrumentSnapshot(
                symbol=sym,
                asset_type=_asset_type_to_upper_name(
                    getattr(prebuilt, "asset_type", "")
                ),
                multiplier=float(getattr(prebuilt, "multiplier", 1.0)),
                margin_ratio=float(getattr(prebuilt, "margin_ratio", 1.0)),
                tick_size=float(getattr(prebuilt, "tick_size", 0.01)),
                lot_size=float(getattr(prebuilt, "lot_size", 1.0)),
                settlement_type=_settlement_type_to_upper_name(
                    getattr(prebuilt, "settlement_type", None)
                ),
                settlement_price=(
                    float(getattr(prebuilt, "settlement_price"))
                    if getattr(prebuilt, "settlement_price", None) is not None
                    else None
                ),
            )
            continue

        # Determine lot_size for this symbol
        current_lot_size = None
        if isinstance(lot_size, int):
            current_lot_size = lot_size
        elif isinstance(lot_size, dict):
            current_lot_size = lot_size.get(sym)

        # Check specific config
        i_conf = inst_conf_map.get(sym)
        futures_template = _match_futures_template(sym)

        if i_conf:
            p_asset_type = _parse_asset_type(i_conf.asset_type)
            p_multiplier = i_conf.multiplier
            p_margin = i_conf.margin_ratio
            p_tick = i_conf.tick_size
            # If config has lot_size, use it, otherwise use global setting
            p_lot = (
                i_conf.lot_size
                if i_conf.lot_size is not None
                else float(current_lot_size or 1.0)
            )
            if futures_template and p_asset_type == AssetType.Futures:
                if i_conf.multiplier == 1 and futures_template.multiplier is not None:
                    p_multiplier = futures_template.multiplier
                if (
                    i_conf.margin_ratio == 1
                    and futures_template.margin_ratio is not None
                ):
                    p_margin = futures_template.margin_ratio
                if i_conf.tick_size == 0.01 and futures_template.tick_size is not None:
                    p_tick = futures_template.tick_size
                if i_conf.lot_size is None and futures_template.lot_size is not None:
                    p_lot = futures_template.lot_size

            p_opt_type = _parse_option_type(i_conf.option_type)
            p_strike = i_conf.strike_price
            p_expiry = _normalize_expiry_date_yyyymmdd(i_conf.expiry_date)
            p_underlying = i_conf.underlying_symbol
            p_settlement_type, p_settlement_mode = _parse_settlement_type(
                i_conf.settlement_type
            )
            p_settlement_price = i_conf.settlement_price
            static_attrs = getattr(i_conf, "static_attrs", {})
            if static_attrs is None:
                static_attrs = {}
            if not isinstance(static_attrs, dict):
                raise TypeError(
                    "InstrumentConfig.static_attrs must be Dict[str, scalar]"
                )
        else:
            if futures_template:
                p_asset_type = AssetType.Futures
                p_multiplier = (
                    futures_template.multiplier
                    if futures_template.multiplier is not None
                    else default_multiplier
                )
                p_margin = (
                    futures_template.margin_ratio
                    if futures_template.margin_ratio is not None
                    else default_margin_ratio
                )
                p_tick = (
                    futures_template.tick_size
                    if futures_template.tick_size is not None
                    else default_tick_size
                )
                p_lot = (
                    futures_template.lot_size
                    if futures_template.lot_size is not None
                    else float(current_lot_size or 1.0)
                )
            else:
                p_asset_type = default_asset_type
                p_multiplier = default_multiplier
                p_margin = default_margin_ratio
                p_tick = default_tick_size
                p_lot = float(current_lot_size or 1.0)

            p_opt_type = default_option_type
            p_strike = default_strike_price
            p_expiry = default_expiry_date
            p_underlying = None
            p_settlement_type, p_settlement_mode = _parse_settlement_type(
                default_settlement_type
            )
            p_settlement_price = default_settlement_price
            static_attrs = {}

        if p_asset_type != AssetType.Futures:
            p_settlement_type = None
            p_settlement_mode = None
            p_settlement_price = None
        if (
            p_settlement_mode == "SETTLEMENT_PRICE"
            and p_settlement_price is None
            and p_asset_type == AssetType.Futures
        ):
            raise ValueError(
                "settlement_price is required for "
                f"settlement_type=settlement_price ({sym})"
            )

        # Validate types before passing to Rust
        if p_lot is not None and not isinstance(p_lot, (int, float)):
            p_lot = 1.0  # Fallback

        # Ensure lot is float for Rust binding if expected
        p_lot_f: float = float(p_lot)

        instr = Instrument(
            sym,
            p_asset_type,
            p_multiplier,
            p_margin,
            p_tick,
            p_opt_type,
            p_strike,
            p_expiry,
            p_lot_f,
            p_underlying,
            p_settlement_type,
            p_settlement_price,
        )
        engine.add_instrument(instr)
        instrument_snapshots[sym] = InstrumentSnapshot(
            symbol=sym,
            asset_type=_asset_type_to_upper_name(p_asset_type),
            multiplier=float(p_multiplier),
            margin_ratio=float(p_margin),
            tick_size=float(p_tick),
            lot_size=float(p_lot_f),
            option_type=_option_type_to_upper_name(p_opt_type),
            strike_price=float(p_strike) if p_strike is not None else None,
            expiry_date=p_expiry,
            underlying_symbol=str(p_underlying) if p_underlying is not None else None,
            settlement_type=p_settlement_mode,
            settlement_price=(
                float(p_settlement_price) if p_settlement_price is not None else None
            ),
            static_attrs=dict(static_attrs),
        )

    for current_strategy in all_strategy_instances:
        current_strategy._set_instrument_snapshots(instrument_snapshots)

    # 6. 添加数据
    engine.add_data(feed)

    # 7. 运行回测
    logger.info("Running backtest via run_backtest()...")

    # 设置自动历史数据维护
    # Logic: effective_depth = max(strategy.warmup_period, inferred_warmup,
    #                              run_backtest(history_depth))
    strategy_warmup = getattr(strategy_instance, "warmup_period", 0)

    # Auto-infer from AST
    inferred_warmup = 0
    try:
        inferred_warmup = infer_warmup_period(type(strategy_instance))
        if inferred_warmup > 0:
            logger.info(f"Auto-inferred warmup period: {inferred_warmup}")
    except Exception as e:
        logger.debug(f"Failed to infer warmup period: {e}")

    # Determine final warmup period
    final_warmup = max(strategy_warmup, inferred_warmup, warmup_period)
    # Update strategy instance with the determined warmup period
    strategy_instance.warmup_period = final_warmup

    effective_depth = max(final_warmup, history_depth)

    if effective_depth > 0:
        for current_strategy in all_strategy_instances:
            current_strategy.set_history_depth(effective_depth)

    # 7.5 Prepare Indicators (Precompute mode only)
    if data_map_for_indicators:
        for current_strategy in all_strategy_instances:
            if _should_prepare_precomputed_indicators(current_strategy) and hasattr(
                current_strategy, "_prepare_indicators"
            ):
                current_strategy._prepare_indicators(data_map_for_indicators)

    engine_summary: str = ""
    try:
        engine_summary = str(engine.run(strategy_instance, show_progress))
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise e
    finally:
        if stream_on_event is not None and hasattr(engine, "clear_stream_callback"):
            try:
                cast(Any, engine).clear_stream_callback()
            except Exception as e:
                logger.debug(f"Failed to clear stream callback: {e}")
        if hasattr(strategy_instance, "_on_stop_internal"):
            try:
                strategy_instance._on_stop_internal()
            except Exception as e:
                logger.error(f"Error in on_stop: {e}")
        elif hasattr(strategy_instance, "on_stop"):
            try:
                strategy_instance.on_stop()
            except Exception as e:
                logger.error(f"Error in on_stop: {e}")
        for slot_strategy in slot_strategy_instances.values():
            if hasattr(slot_strategy, "_on_stop_internal"):
                try:
                    slot_strategy._on_stop_internal()
                except Exception as e:
                    logger.error(f"Error in slot on_stop: {e}")
            elif hasattr(slot_strategy, "on_stop"):
                try:
                    slot_strategy.on_stop()
                except Exception as e:
                    logger.error(f"Error in slot on_stop: {e}")

    result = BacktestResult(
        engine.get_results(),
        timezone=timezone,
        initial_cash=initial_cash,
        strategy=strategy_instance,
        engine=engine,
    )
    _attach_result_runtime_metadata(
        result=result,
        engine_summary=engine_summary,
        event_stats_snapshot=event_stats_snapshot,
        owner_strategy_id=effective_strategy_id,
        resolved_policy=resolved_policy,
    )
    analyzer_outputs: Dict[str, Dict[str, Any]] = {}
    if analyzer_manager.plugins:
        try:
            analyzer_outputs = analyzer_manager.on_finish(
                {
                    "engine": engine,
                    "strategy": strategy_instance,
                    "strategies": list(all_strategy_instances),
                    "slot_strategy_map": {
                        effective_strategy_id: strategy_instance,
                        **slot_strategy_instances,
                    },
                    "result": result,
                }
            )
        except Exception as e:
            logger.error(f"Analyzer on_finish error: {e}")
    result.analyzer_outputs = analyzer_outputs
    return result


def run_warm_start(
    checkpoint_path: str,
    data: Optional[BacktestDataInput] = None,
    show_progress: bool = True,
    symbols: Union[str, List[str], Tuple[str, ...], set[str]] = "BENCHMARK",
    strategy_runtime_config: Optional[
        Union[StrategyRuntimeConfig, Dict[str, Any]]
    ] = None,
    runtime_config_override: bool = True,
    strategy_id: Optional[str] = None,
    strategies_by_slot: Optional[
        Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
    ] = None,
    strategy_max_order_value: Optional[Dict[str, float]] = None,
    strategy_max_order_size: Optional[Dict[str, float]] = None,
    strategy_max_position_size: Optional[Dict[str, float]] = None,
    strategy_max_daily_loss: Optional[Dict[str, float]] = None,
    strategy_max_drawdown: Optional[Dict[str, float]] = None,
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None,
    strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None,
    strategy_priority: Optional[Dict[str, int]] = None,
    strategy_risk_budget: Optional[Dict[str, float]] = None,
    strategy_fill_policy: Optional[Dict[str, FillPolicy]] = None,
    strategy_slippage: Optional[Dict[str, SlippagePolicy]] = None,
    strategy_commission: Optional[Dict[str, CommissionPolicy]] = None,
    portfolio_risk_budget: Optional[float] = None,
    risk_budget_mode: str = "order_notional",
    risk_budget_reset_daily: bool = False,
    on_event: Optional[Callable[[BacktestStreamEvent], None]] = None,
    config: Optional[BacktestConfig] = None,
    **kwargs: Any,
) -> BacktestResult:
    """
    热启动回测 (Warm Start Backtest).

    注意：当前 run_warm_start 的策略实例来自 checkpoint 恢复，
    不会通过 strategy_source / strategy_loader 重新加载策略类。
    如需替换策略实现，请优先使用 run_backtest 或在恢复后通过
    strategies_by_slot 覆盖 slot 策略。

    故障速查可参考 docs/zh/advanced/runtime_config.md，
    英文文档参考 docs/en/advanced/runtime_config.md

    :param kwargs: 其他引擎配置参数 (如 commission_rate, stamp_tax_rate, t_plus_one)
    """
    import os

    from ..checkpoint import warm_start

    logger = get_logger()
    has_effective_handler = any(
        not isinstance(handler, logging.NullHandler) for handler in logger.handlers
    )
    if not has_effective_handler:
        register_logger(console=True, level="INFO")
        logger = get_logger()
    strategy_config = config.strategy_config if config is not None else None
    (
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
        _ignored_strategy_source,
        _ignored_strategy_loader,
        _ignored_strategy_loader_options,
    ) = _apply_strategy_config_overrides(
        strategy_config=strategy_config,
        strategy_id=strategy_id,
        strategies_by_slot=strategies_by_slot,
        strategy_max_order_value=strategy_max_order_value,
        strategy_max_order_size=strategy_max_order_size,
        strategy_max_position_size=strategy_max_position_size,
        strategy_max_daily_loss=strategy_max_daily_loss,
        strategy_max_drawdown=strategy_max_drawdown,
        strategy_reduce_only_after_risk=strategy_reduce_only_after_risk,
        strategy_risk_cooldown_bars=strategy_risk_cooldown_bars,
        strategy_priority=strategy_priority,
        strategy_risk_budget=strategy_risk_budget,
        strategy_fill_policy=strategy_fill_policy,
        strategy_slippage=strategy_slippage,
        strategy_commission=strategy_commission,
        portfolio_risk_budget=portfolio_risk_budget,
        strategy_runtime_config=strategy_runtime_config,
        strategy_source=None,
        strategy_loader=None,
        strategy_loader_options=None,
    )
    portfolio_risk_budget, risk_budget_mode = _validate_strategy_risk_inputs(
        strategies_by_slot=strategies_by_slot,
        strategy_max_order_value=strategy_max_order_value,
        strategy_max_order_size=strategy_max_order_size,
        strategy_max_position_size=strategy_max_position_size,
        strategy_max_daily_loss=strategy_max_daily_loss,
        strategy_max_drawdown=strategy_max_drawdown,
        strategy_reduce_only_after_risk=strategy_reduce_only_after_risk,
        strategy_risk_cooldown_bars=strategy_risk_cooldown_bars,
        strategy_priority=strategy_priority,
        strategy_risk_budget=strategy_risk_budget,
        portfolio_risk_budget=portfolio_risk_budget,
        risk_budget_mode=risk_budget_mode,
    )
    risk_budget_reset_daily = bool(risk_budget_reset_daily)
    prepared_stream_runtime = _prepare_stream_runtime(on_event=on_event, kwargs=kwargs)
    stream_on_event = prepared_stream_runtime.stream_on_event
    event_stats_snapshot = prepared_stream_runtime.event_stats_snapshot
    stream_progress_interval = prepared_stream_runtime.stream_progress_interval
    stream_equity_interval = prepared_stream_runtime.stream_equity_interval
    stream_batch_size = prepared_stream_runtime.stream_batch_size
    stream_max_buffer = prepared_stream_runtime.stream_max_buffer
    stream_error_mode = prepared_stream_runtime.stream_error_mode
    stream_mode = prepared_stream_runtime.stream_mode
    legacy_mode_override = "execution_mode" in kwargs
    legacy_timer_override = "timer_execution_policy" in kwargs
    has_fill_policy_override = "fill_policy" in kwargs
    _raise_if_legacy_execution_policy_used(
        legacy_mode_used=legacy_mode_override,
        legacy_timer_used=legacy_timer_override,
        api_name="run_warm_start",
    )
    fill_policy_override = cast(Optional[FillPolicy], kwargs.pop("fill_policy", None))
    timezone_name = str(kwargs.get("timezone") or "Asia/Shanghai")
    symbols, effective_symbols = _resolve_effective_symbols(
        symbols=symbols,
        kwargs=kwargs,
        api_name="run_warm_start",
    )

    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # 1. 准备数据源
    feed = None
    data_map_for_indicators: Dict[str, pd.DataFrame] = {}

    if isinstance(data, DataFeed):
        feed = data
    elif _is_data_feed_adapter(data):
        feed = DataFeed()
        adapter_data_map = _load_data_map_from_adapter(
            adapter=data,
            symbols=list(effective_symbols),
            start_time=kwargs.get("start_time"),
            end_time=kwargs.get("end_time"),
            timezone=timezone_name,
        )
        loaded_count = 0
        for sym, df in adapter_data_map.items():
            if not df.empty:
                df_prep = prepare_dataframe(df)
                data_map_for_indicators[sym] = df_prep
                arrays = df_to_arrays(df_prep, symbol=sym)
                feed.add_arrays(*arrays)  # type: ignore
                loaded_count += 1
        if loaded_count > 0:
            feed.sort()
    elif data is not None:
        # Convert DataFrame/List to DataFeed
        feed = DataFeed()
        symbols = list(effective_symbols)

        data_map = {}
        # Copied logic from run_backtest for data loading
        if isinstance(data, pd.DataFrame):
            if len(symbols) == 1:
                data_map = {symbols[0]: data}
            else:
                # Multi-index or strict format required?
                # For simplicity, assume single symbol if passed as DF
                data_map = {symbols[0]: data}
        elif isinstance(data, list) and data and isinstance(data[0], Bar):
            # Convert List[Bar] to DataFrame for indicators
            # We assume all bars are for the same symbol (or single symbol context)
            feed.add_bars(data)  # type: ignore

            # Construct DataFrame for indicator calculation
            # Group by symbol just in case
            bars_by_sym: Dict[str, List[Dict[str, Any]]] = {}
            for bar in data:
                if bar.symbol not in bars_by_sym:
                    bars_by_sym[bar.symbol] = []
                bars_by_sym[bar.symbol].append(
                    {
                        "timestamp": pd.Timestamp(bar.timestamp, unit="ns", tz="UTC"),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                )

            for sym, records in bars_by_sym.items():
                df = pd.DataFrame(records)
                if not df.empty:
                    df.set_index("timestamp", inplace=True)
                    df.sort_index(inplace=True)
                    data_map_for_indicators[sym] = df

        elif isinstance(data, dict):
            data_map = data
        else:
            data_map = {}

        loaded_count = 0
        for sym, df in data_map.items():
            if not df.empty:
                df = prepare_dataframe(df)
                data_map_for_indicators[sym] = df
                arrays = df_to_arrays(df, symbol=sym)
                feed.add_arrays(*arrays)  # type: ignore
                loaded_count += 1

        if loaded_count > 0:
            feed.sort()

    logger.info(f"Resuming from checkpoint: {checkpoint_path}")
    engine, strategy_instance = warm_start(checkpoint_path, feed)
    restored_strategy_id = str(
        getattr(strategy_instance, "_owner_strategy_id", "") or ""
    ).strip()
    restored_engine_strategy_id = ""
    if hasattr(engine, "get_default_strategy_id"):
        restored_engine_strategy_id = str(
            cast(Any, engine).get_default_strategy_id() or ""
        ).strip()
    effective_strategy_id = (
        str(strategy_id).strip()
        if strategy_id is not None and str(strategy_id).strip()
        else restored_strategy_id or restored_engine_strategy_id or "_default"
    )
    restored_slot_ids: List[str] = []
    slot_fetcher = None
    if hasattr(engine, "get_strategy_slot_ids"):
        slot_fetcher = cast(Any, engine).get_strategy_slot_ids
    elif hasattr(engine, "get_strategy_slots"):
        slot_fetcher = cast(Any, engine).get_strategy_slots
    if slot_fetcher is not None:
        try:
            slot_ids = slot_fetcher()
            if isinstance(slot_ids, list):
                restored_slot_ids = [
                    str(slot_id).strip() for slot_id in slot_ids if str(slot_id).strip()
                ]
        except Exception:
            restored_slot_ids = []

    restored_slot_strategy_instances: Dict[str, Strategy] = {}
    raw_restored_slot_strategies = getattr(strategy_instance, "_slot_strategies", None)
    if isinstance(raw_restored_slot_strategies, dict):
        for slot_key, slot_strategy in raw_restored_slot_strategies.items():
            slot_key_str = str(slot_key).strip()
            if not slot_key_str:
                continue
            if isinstance(slot_strategy, Strategy):
                restored_slot_strategy_instances[slot_key_str] = slot_strategy

    slot_strategy_instances = dict(restored_slot_strategy_instances)
    if strategies_by_slot:
        slot_strategy_instances = {}
        for slot_key, slot_strategy_input in strategies_by_slot.items():
            slot_key_str = str(slot_key).strip()
            if not slot_key_str:
                raise ValueError("strategy slot id cannot be empty")
            slot_strategy_instances[slot_key_str] = _build_strategy_instance(
                slot_strategy_input,
                {},
                False,
                logger,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )

    configured_slot_ids = [effective_strategy_id]
    source_slot_ids = (
        list(slot_strategy_instances.keys())
        if slot_strategy_instances
        else restored_slot_ids
    )
    for slot_key in source_slot_ids:
        if slot_key not in configured_slot_ids:
            configured_slot_ids.append(slot_key)
    normalized_strategy_fill_policy = _normalize_strategy_fill_policy_map(
        strategy_fill_policy,
        configured_slot_ids,
        logger,
    )
    normalized_strategy_slippage = _normalize_strategy_slippage_map(
        strategy_slippage,
        configured_slot_ids,
    )
    normalized_strategy_commission = _normalize_strategy_commission_map(
        strategy_commission,
        configured_slot_ids,
    )

    setattr(strategy_instance, "_owner_strategy_id", effective_strategy_id)
    for slot_key, slot_strategy in slot_strategy_instances.items():
        setattr(slot_strategy, "_owner_strategy_id", slot_key)
    setattr(strategy_instance, "_slot_strategies", dict(slot_strategy_instances))
    setattr(strategy_instance, "_strategy_slot_ids", list(configured_slot_ids))
    if normalized_strategy_fill_policy is not None:
        for current_strategy in [strategy_instance, *slot_strategy_instances.values()]:
            setattr(
                current_strategy,
                "_strategy_fill_policy_map",
                dict(normalized_strategy_fill_policy),
            )
    if normalized_strategy_slippage is not None:
        for current_strategy in [strategy_instance, *slot_strategy_instances.values()]:
            setattr(
                current_strategy,
                "_strategy_slippage_map",
                dict(normalized_strategy_slippage),
            )
    if normalized_strategy_commission is not None:
        for current_strategy in [strategy_instance, *slot_strategy_instances.values()]:
            setattr(
                current_strategy,
                "_strategy_commission_map",
                dict(normalized_strategy_commission),
            )

    if configured_slot_ids and hasattr(engine, "set_strategy_slots"):
        cast(Any, engine).set_strategy_slots(configured_slot_ids)
    if hasattr(engine, "set_default_strategy_id"):
        cast(Any, engine).set_default_strategy_id(effective_strategy_id)
    if hasattr(engine, "set_strategy_for_slot"):
        for slot_index, slot_id in enumerate(configured_slot_ids):
            assigned_strategy: Strategy
            if slot_id == effective_strategy_id:
                assigned_strategy = strategy_instance
            else:
                assigned_strategy = slot_strategy_instances.get(
                    slot_id, strategy_instance
                )
            cast(Any, engine).set_strategy_for_slot(slot_index, assigned_strategy)

    if "strategy_runtime_config" in kwargs:
        kwargs_runtime_config = kwargs.pop("strategy_runtime_config")
        if strategy_runtime_config is None:
            strategy_runtime_config = kwargs_runtime_config
    if strategy_runtime_config is not None and isinstance(strategy_instance, Strategy):
        _apply_strategy_runtime_config(
            strategy_instance,
            strategy_runtime_config,
            runtime_config_override,
            logger,
        )
        for slot_strategy in slot_strategy_instances.values():
            _apply_strategy_runtime_config(
                slot_strategy,
                strategy_runtime_config,
                runtime_config_override,
                logger,
            )
    if strategy_priority and hasattr(engine, "set_strategy_priorities"):
        normalized_strategy_priority: Dict[str, int] = {}
        for strategy_key, raw_priority in strategy_priority.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_priority contains empty strategy id")
            normalized_strategy_priority[strategy_key_str] = int(raw_priority)
        unknown_keys = sorted(
            set(normalized_strategy_priority.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_priority contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_priorities(normalized_strategy_priority)
    if strategy_risk_budget and hasattr(engine, "set_strategy_risk_budget_limits"):
        normalized_strategy_risk_budget: Dict[str, float] = {}
        for strategy_key, raw_budget in strategy_risk_budget.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_risk_budget contains empty strategy id")
            budget_value = float(raw_budget)
            if not pd.notna(budget_value) or budget_value < 0.0:
                raise ValueError(
                    f"strategy_risk_budget for {strategy_key_str} must be >= 0"
                )
            normalized_strategy_risk_budget[strategy_key_str] = budget_value
        unknown_keys = sorted(
            set(normalized_strategy_risk_budget.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_risk_budget contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_risk_budget_limits(
            normalized_strategy_risk_budget
        )
    if hasattr(engine, "set_portfolio_risk_budget_limit"):
        cast(Any, engine).set_portfolio_risk_budget_limit(portfolio_risk_budget)
    if hasattr(engine, "set_risk_budget_mode"):
        cast(Any, engine).set_risk_budget_mode(risk_budget_mode)
    if hasattr(engine, "set_risk_budget_reset_daily"):
        cast(Any, engine).set_risk_budget_reset_daily(risk_budget_reset_daily)
    if strategy_max_order_value and hasattr(
        engine, "set_strategy_max_order_value_limits"
    ):
        normalized_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_order_value.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_order_value contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_order_value for {strategy_key_str} must be >= 0"
                )
            normalized_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_order_value contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_order_value_limits(normalized_limits)
    if strategy_max_order_size and hasattr(
        engine, "set_strategy_max_order_size_limits"
    ):
        normalized_limits_by_size: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_order_size.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_order_size contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_order_size for {strategy_key_str} must be >= 0"
                )
            normalized_limits_by_size[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_limits_by_size.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_order_size contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_order_size_limits(normalized_limits_by_size)
    if strategy_max_position_size and hasattr(
        engine, "set_strategy_max_position_size_limits"
    ):
        normalized_position_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_position_size.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_max_position_size contains empty strategy id"
                )
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_position_size for {strategy_key_str} must be >= 0"
                )
            normalized_position_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_position_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_position_size contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_position_size_limits(
            normalized_position_limits
        )
    if strategy_max_daily_loss and hasattr(
        engine, "set_strategy_max_daily_loss_limits"
    ):
        normalized_daily_loss_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_daily_loss.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_daily_loss contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_daily_loss for {strategy_key_str} must be >= 0"
                )
            normalized_daily_loss_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_daily_loss_limits.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_daily_loss contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_daily_loss_limits(
            normalized_daily_loss_limits
        )
    if strategy_max_drawdown and hasattr(engine, "set_strategy_max_drawdown_limits"):
        normalized_drawdown_limits: Dict[str, float] = {}
        for strategy_key, raw_limit in strategy_max_drawdown.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError("strategy_max_drawdown contains empty strategy id")
            limit_value = float(raw_limit)
            if not pd.notna(limit_value) or limit_value < 0.0:
                raise ValueError(
                    f"strategy_max_drawdown for {strategy_key_str} must be >= 0"
                )
            normalized_drawdown_limits[strategy_key_str] = limit_value
        unknown_keys = sorted(
            set(normalized_drawdown_limits.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_max_drawdown contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_max_drawdown_limits(normalized_drawdown_limits)
    if strategy_reduce_only_after_risk and hasattr(
        engine, "set_strategy_reduce_only_after_risk"
    ):
        normalized_reduce_only_flags: Dict[str, bool] = {}
        for strategy_key, raw_flag in strategy_reduce_only_after_risk.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_reduce_only_after_risk contains empty strategy id"
                )
            normalized_reduce_only_flags[strategy_key_str] = bool(raw_flag)
        unknown_keys = sorted(
            set(normalized_reduce_only_flags.keys()).difference(
                set(configured_slot_ids)
            )
        )
        if unknown_keys:
            raise ValueError(
                "strategy_reduce_only_after_risk contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_reduce_only_after_risk(
            normalized_reduce_only_flags
        )
    if strategy_risk_cooldown_bars and hasattr(
        engine, "set_strategy_risk_cooldown_bars"
    ):
        normalized_cooldown_bars: Dict[str, int] = {}
        for strategy_key, raw_bars in strategy_risk_cooldown_bars.items():
            strategy_key_str = str(strategy_key).strip()
            if not strategy_key_str:
                raise ValueError(
                    "strategy_risk_cooldown_bars contains empty strategy id"
                )
            cooldown_bars = int(raw_bars)
            if cooldown_bars < 0:
                raise ValueError(
                    f"strategy_risk_cooldown_bars for {strategy_key_str} must be >= 0"
                )
            normalized_cooldown_bars[strategy_key_str] = cooldown_bars
        unknown_keys = sorted(
            set(normalized_cooldown_bars.keys()).difference(set(configured_slot_ids))
        )
        if unknown_keys:
            raise ValueError(
                "strategy_risk_cooldown_bars contains unknown strategy id(s): "
                + ",".join(unknown_keys)
            )
        cast(Any, engine).set_strategy_risk_cooldown_bars(normalized_cooldown_bars)

    all_strategy_instances = [strategy_instance, *slot_strategy_instances.values()]
    if data_map_for_indicators:
        all_dates: set[pd.Timestamp] = set()
        day_bounds: Dict[str, Tuple[int, int]] = {}
        for df in data_map_for_indicators.values():
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                local_index = _index_to_local_trading_days(
                    cast(pd.DatetimeIndex, df.index), timezone_name
                )
                dates = local_index.normalize().unique()
                all_dates.update(dates)
                grouped = df.groupby(local_index.normalize())
                for day_ts, day_df in grouped:
                    day_key = pd.Timestamp(day_ts).date().isoformat()
                    start_ns = int(day_df.index.min().value)
                    end_ns = int(day_df.index.max().value)
                    if day_key in day_bounds:
                        prev_start, prev_end = day_bounds[day_key]
                        day_bounds[day_key] = (
                            min(prev_start, start_ns),
                            max(prev_end, end_ns),
                        )
                    else:
                        day_bounds[day_key] = (start_ns, end_ns)

        for current_strategy in all_strategy_instances:
            if all_dates and hasattr(current_strategy, "_trading_days"):
                current_strategy._trading_days = sorted(list(all_dates))
            if hasattr(current_strategy, "_trading_day_bounds"):
                current_strategy._trading_day_bounds = day_bounds

    # Capture restored cash BEFORE running (for correct initial_market_value in result)
    restored_cash = engine.portfolio.cash
    logger.info(f"Restored engine cash: {restored_cash}")

    # 2.5 重新注册默认标的 (Instrument)
    # 引擎快照通常不包含静态配置 (Instrument)，
    # 因此需要为新数据中的标的重新注册默认配置。
    # 默认使用股票 (Stock) 类型，lot_size=1。
    # 如果需要自定义，请在策略 on_start 中处理或扩展 run_warm_start。
    from ..akquant import AssetType, Instrument

    symbols_to_add: set[str] = set()
    if data_map_for_indicators:
        symbols_to_add.update(data_map_for_indicators.keys())

    # 如果 data 是 List[Bar]，也收集其中的 symbol
    if isinstance(data, list) and data and isinstance(data[0], Bar):
        for bar in data:  # 只检查前几个可能不够，但通常数据是单一标的
            symbols_to_add.add(bar.symbol)
            # 优化: 如果列表很大，只检查第一个和最后一个? 或者假设单一标的?
            # 这里简单起见，只取第一个，假设列表是针对单一或少数几个标的
            break

    try:
        if hasattr(strategy_instance, "symbol"):
            s = strategy_instance.symbol
            if s:
                symbols_to_add.add(s)
    except Exception:
        # symbol property might raise error if no current bar/tick
        pass

    warm_start_instrument_snapshots: Dict[str, InstrumentSnapshot] = {}
    for sym in symbols_to_add:
        # 添加默认股票标的
        # ... (略)
        instr = Instrument(
            symbol=sym,
            asset_type=AssetType.Stock,
            multiplier=1.0,
            margin_ratio=1.0,
            tick_size=0.01,
            lot_size=1.0,  # 默认为 1，允许任意整数倍交易
        )
        engine.add_instrument(instr)
        warm_start_instrument_snapshots[sym] = InstrumentSnapshot(
            symbol=sym,
            asset_type="STOCK",
            multiplier=1.0,
            margin_ratio=1.0,
            tick_size=0.01,
            lot_size=1.0,
        )
        logger.info(f"Re-registered default instrument for warm start: {sym}")

    for current_strategy in all_strategy_instances:
        current_strategy._set_instrument_snapshots(warm_start_instrument_snapshots)

    # 2.6 Re-configure Market Model
    # Engine restoration might lose market model config if not in State.
    # Default to SimpleMarket (T+0) or ChinaMarket (T+1) based on kwargs.
    broker_profile_values = _resolve_broker_profile(
        cast(Optional[str], kwargs.get("broker_profile"))
    )
    commission_rate_value = cast(Optional[float], kwargs.get("commission_rate"))
    stamp_tax_rate_value = cast(
        Optional[float], kwargs.get("stamp_tax_rate", kwargs.get("stamp_tax"))
    )
    transfer_fee_rate_value = cast(
        Optional[float], kwargs.get("transfer_fee_rate", kwargs.get("transfer_fee"))
    )
    min_commission_value = cast(Optional[float], kwargs.get("min_commission"))
    (
        commission,
        stamp_tax,
        transfer_fee,
        min_commission,
    ) = _resolve_stock_fee_rules(
        commission_rate=commission_rate_value,
        stamp_tax_rate=stamp_tax_rate_value,
        transfer_fee_rate=transfer_fee_rate_value,
        min_commission=min_commission_value,
        broker_profile_values=broker_profile_values,
        strategy_config=strategy_config,
    )
    t_plus_one = kwargs.get("t_plus_one", False)

    if t_plus_one:
        # ChinaMarket implies T+1 and specific fee rules
        engine.use_china_market()
    else:
        # SimpleMarket implies T+0
        engine.use_simple_market(commission)

    # Apply fee rules if engine supports it
    # (and if not ChinaMarket which has fixed rules?)
    # ChinaMarket usually has hardcoded rules or defaults,
    # but set_stock_fee_rules overrides them?
    # Let's just set it.
    if hasattr(engine, "set_stock_fee_rules"):
        engine.set_stock_fee_rules(commission, stamp_tax, transfer_fee, min_commission)
        logger.info(f"Re-configured market fees: comm={commission}, stamp={stamp_tax}")
    resolved_policy_warm_start: Optional[ResolvedExecutionPolicy] = None
    if has_fill_policy_override:
        resolved_policy_warm_start = _resolve_execution_policy(
            execution_mode="next_open",
            timer_execution_policy="same_cycle",
            fill_policy=fill_policy_override,
            logger=logger,
        )
        if not hasattr(engine, "set_fill_policy"):
            raise RuntimeError(
                "Engine binary does not expose set_fill_policy; please rebuild bindings"
            )
        cast(Any, engine).set_fill_policy(
            resolved_policy_warm_start.price_basis,
            resolved_policy_warm_start.bar_offset,
            resolved_policy_warm_start.temporal,
        )
    if stream_on_event is not None:
        cast(Any, engine).set_stream_callback(stream_on_event)
        cast(Any, engine).set_stream_options(
            stream_progress_interval,
            stream_equity_interval,
            stream_batch_size,
            stream_max_buffer,
            stream_error_mode,
            stream_mode,
        )

    if hasattr(strategy_instance, "_on_start_internal"):
        strategy_instance._on_start_internal()
    elif hasattr(strategy_instance, "on_start"):
        if hasattr(strategy_instance, "is_restored") and strategy_instance.is_restored:
            if hasattr(strategy_instance, "on_resume"):
                strategy_instance.on_resume()
        strategy_instance.on_start()
    for slot_strategy in slot_strategy_instances.values():
        if hasattr(slot_strategy, "_on_start_internal"):
            slot_strategy._on_start_internal()
        elif hasattr(slot_strategy, "on_start"):
            if hasattr(slot_strategy, "is_restored") and slot_strategy.is_restored:
                if hasattr(slot_strategy, "on_resume"):
                    slot_strategy.on_resume()
            slot_strategy.on_start()

    if data_map_for_indicators:
        for current_strategy in all_strategy_instances:
            if _should_prepare_precomputed_indicators(current_strategy) and hasattr(
                current_strategy, "_prepare_indicators"
            ):
                try:
                    current_strategy._prepare_indicators(data_map_for_indicators)
                except Exception as e:
                    logger.error(f"Failed to update indicators for warm start: {e}")

    # 4. 运行
    engine_summary: str = ""
    try:
        engine_summary = str(engine.run(strategy_instance, show_progress))
    except Exception as e:
        logger.error(f"Warm start backtest failed: {e}")
        raise e
    finally:
        if stream_on_event is not None and hasattr(engine, "clear_stream_callback"):
            try:
                cast(Any, engine).clear_stream_callback()
            except Exception as e:
                logger.debug(f"Failed to clear stream callback: {e}")
        if hasattr(strategy_instance, "_on_stop_internal"):
            try:
                strategy_instance._on_stop_internal()
            except Exception as e:
                logger.error(f"Error in on_stop: {e}")
        elif hasattr(strategy_instance, "on_stop"):
            try:
                strategy_instance.on_stop()
            except Exception as e:
                logger.error(f"Error in on_stop: {e}")
        for slot_strategy in slot_strategy_instances.values():
            if hasattr(slot_strategy, "_on_stop_internal"):
                try:
                    slot_strategy._on_stop_internal()
                except Exception as e:
                    logger.error(f"Error in slot on_stop: {e}")
            elif hasattr(slot_strategy, "on_stop"):
                try:
                    slot_strategy.on_stop()
                except Exception as e:
                    logger.error(f"Error in slot on_stop: {e}")

    # 注意：这里的 initial_cash 可能不准确，因为它使用的是当前 cash
    # 但对于 BacktestResult 来说，重要的是 equity curve 的连续性
    # 我们使用之前捕获的 restored_cash 作为 reference
    result = BacktestResult(
        engine.get_results(),
        timezone=timezone_name,
        initial_cash=float(restored_cash),
        strategy=strategy_instance,
        engine=engine,
    )
    _attach_result_runtime_metadata(
        result=result,
        engine_summary=engine_summary,
        event_stats_snapshot=event_stats_snapshot,
        owner_strategy_id=effective_strategy_id,
        resolved_policy=resolved_policy_warm_start,
    )
    return result
