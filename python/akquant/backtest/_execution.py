"""Backtest execution policy resolution and stream runtime preparation."""

import logging
from typing import Any, Callable, Dict, Literal, Optional, Union, cast

from ._types import (
    _DEFAULT_FILL_BAR_OFFSET,
    _RESERVED_FILL_PRICE_BASIS,
    _RUNTIME_MODE_CURRENT_CLOSE,
    _RUNTIME_MODE_NEXT_AVERAGE,
    _RUNTIME_MODE_NEXT_CLOSE,
    _RUNTIME_MODE_NEXT_HIGH_LOW_MID,
    _RUNTIME_MODE_NEXT_OPEN,
    _SUPPORTED_FILL_BAR_OFFSET,
    _SUPPORTED_FILL_PRICE_BASIS,
    _SUPPORTED_FILL_TEMPORAL,
    BacktestStreamEvent,
    FillPolicy,
    PreparedStreamRuntime,
    ResolvedExecutionPolicy,
)


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
    resolved_twap_bars = 0
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
                "open, close, ohlc4, hl2, twap_window; "
                "reserved: mid_quote, vwap_window"
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
        elif raw_basis == "twap_window":
            if raw_offset != 1:
                raise ValueError("fill_policy(twap_window) requires bar_offset=1")
            twap_bars = fill_policy.get("twap_bars")
            if twap_bars is None or int(twap_bars) <= 0:
                raise ValueError(
                    "fill_policy(twap_window) requires twap_bars > 0"
                )
            resolved_twap_bars = int(twap_bars)
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
        twap_bars=resolved_twap_bars,
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
    result: Any,
    engine_summary: Any,
    event_stats_snapshot: dict[str, Any],
    owner_strategy_id: str,
    resolved_policy: ResolvedExecutionPolicy | None,
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
        result.resolved_execution_policy = dict(
            getattr(result, "_resolved_execution_policy")
        )
