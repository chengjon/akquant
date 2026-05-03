"""Backtest type definitions (extracted from engine.py)."""

import logging
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
)

import pandas as pd

from .. import akquant as _akquant_module
from ..akquant import (
    Bar,
    DataFeed,
)
from ..feed_adapter import DataFeedAdapter

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
