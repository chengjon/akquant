"""Backtest strategy building helpers and FunctionalStrategy class."""

import inspect
from dataclasses import fields
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
from ..analyzer_plugin import AnalyzerPlugin
from ..strategy import Strategy, StrategyRuntimeConfig
from ..utils.inspector import infer_warmup_period

_RUNTIME_CONFIG_FIELDS = {f.name for f in fields(StrategyRuntimeConfig)}


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


def _resolve_runtime_warmup_depth(
    strategy_instance: Strategy,
    history_depth: int,
    warmup_period: int,
    logger: Any,
) -> tuple[int, int]:
    """Resolve final warmup and effective history depth after strategy setup."""
    strategy_warmup = getattr(strategy_instance, "warmup_period", 0)

    inferred_warmup = 0
    try:
        inferred_warmup = infer_warmup_period(type(strategy_instance))
        if inferred_warmup > 0:
            logger.info(f"Auto-inferred warmup period: {inferred_warmup}")
    except Exception as exc:
        logger.debug(f"Failed to infer warmup period: {exc}")

    final_warmup = max(strategy_warmup, inferred_warmup, warmup_period)
    strategy_instance.warmup_period = final_warmup
    effective_depth = max(final_warmup, history_depth)
    return final_warmup, effective_depth


def _to_active_start_time_ns(
    start_time: Optional[Union[str, Any]],
) -> Optional[int]:
    """Normalize an optional active start time to UTC nanoseconds."""
    if start_time is None:
        return None
    return int(pd.Timestamp(start_time).value)


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
