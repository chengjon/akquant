import datetime as dt_module
import os
import sys
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
    TypedDict,
    Union,
    cast,
)

import pandas as pd

from ..akquant import (
    AssetType,
    Bar,
    DataFeed,
    Engine,
    ExecutionMode,
    Instrument,
)
from ..analyzer_plugin import AnalyzerManager, AnalyzerPlugin
from ..config import BacktestConfig, RiskConfig
from ..data import ParquetDataCatalog
from ..feed_adapter import DataFeedAdapter, FeedSlice
from ..log import get_logger, register_logger
from ..risk import apply_risk_config
from ..strategy import Strategy, StrategyRuntimeConfig
from ..utils import df_to_arrays, prepare_dataframe
from ..utils.inspector import infer_warmup_period
from .result import BacktestResult

_RUNTIME_CONFIG_FIELDS = {f.name for f in fields(StrategyRuntimeConfig)}


class BacktestStreamEvent(TypedDict):
    """Backtest stream event payload."""

    run_id: str
    seq: int
    ts: int
    event_type: str
    symbol: Optional[str]
    level: str
    payload: Dict[str, str]


BacktestDataInput = Union[
    pd.DataFrame, Dict[str, pd.DataFrame], List[Bar], DataFeed, DataFeedAdapter
]


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
        try:
            return cast(Strategy, strategy(**strategy_kwargs))
        except TypeError as e:
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
    symbol: Union[str, List[str]] = "BENCHMARK",
    initial_cash: Optional[float] = None,
    commission_rate: Optional[float] = None,
    stamp_tax_rate: float = 0.0,
    transfer_fee_rate: float = 0.0,
    min_commission: float = 0.0,
    slippage: Optional[float] = None,
    volume_limit_pct: Optional[float] = None,
    execution_mode: Union[ExecutionMode, str] = ExecutionMode.NextOpen,
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
    portfolio_risk_budget: Optional[float] = None,
    risk_budget_mode: str = "order_notional",
    risk_budget_reset_daily: bool = False,
    analyzer_plugins: Optional[Sequence[AnalyzerPlugin]] = None,
    on_event: Optional[Callable[[BacktestStreamEvent], None]] = None,
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
    :param symbol: 标的代码
    :param initial_cash: 初始资金 (默认 1,000,000.0)
    :param commission_rate: 佣金率 (默认 0.0)
    :param stamp_tax_rate: 印花税率 (仅卖出, 默认 0.0)
    :param transfer_fee_rate: 过户费率 (默认 0.0)
    :param min_commission: 最低佣金 (默认 0.0)
    :param slippage: 滑点 (默认 0.0)
    :param volume_limit_pct: 成交量限制比例 (默认 0.25)
    :param execution_mode: 执行模式 (ExecutionMode.NextOpen 或 "next_open")
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
    :param portfolio_risk_budget: 可选账户级累计风险预算上限
    :param risk_budget_mode: 风险预算口径，支持 order_notional/trade_notional
    :param risk_budget_reset_daily: 风险预算是否按交易日重置
    :param analyzer_plugins: Analyzer 插件列表，
                             接收 on_start/on_bar/on_trade/on_finish 生命周期事件
    :param on_event: 可选流式事件回调。阶段 5 后 `run_backtest` 始终走统一事件内核；
                     不传时内部使用 no-op 回调并保持返回语义不变。
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
    risk_budget_mode = str(risk_budget_mode).strip().lower()
    if risk_budget_mode not in {"order_notional", "trade_notional"}:
        raise ValueError(
            "risk_budget_mode must be 'order_notional' or 'trade_notional'"
        )
    risk_budget_reset_daily = bool(risk_budget_reset_daily)
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
    effective_strategy_id = strategy_id or "_default"
    original_stream_handler = stream_on_event

    def wrapped_stream_on_event(event: BacktestStreamEvent) -> None:
        event_type = str(event.get("event_type", ""))
        if event_type in {"order", "trade", "risk"}:
            payload_obj = event.get("payload", {})
            if isinstance(payload_obj, dict):
                owner_strategy_id = payload_obj.get("owner_strategy_id")
                if owner_strategy_id is None or str(owner_strategy_id) == "":
                    patched_event = dict(event)
                    patched_payload = dict(payload_obj)
                    patched_payload["owner_strategy_id"] = effective_strategy_id
                    patched_event["payload"] = cast(Dict[str, str], patched_payload)
                    original_stream_handler(cast(BacktestStreamEvent, patched_event))
                    return
        original_stream_handler(event)

    stream_on_event = wrapped_stream_on_event
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

    # 0. 设置默认值 (如果未传入且未在 Config 中设置)
    # 优先级: 参数 > Config > 默认值

    # Defaults
    DEFAULT_INITIAL_CASH = 1_000_000.0
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
        if stamp_tax_rate == 0.0:
            stamp_tax_rate = config.strategy_config.stamp_tax_rate
        if transfer_fee_rate == 0.0:
            transfer_fee_rate = config.strategy_config.transfer_fee_rate
        if min_commission == 0.0:
            min_commission = config.strategy_config.min_commission

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
    if not logger.handlers:
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

    # Update kwargs if needed by strategy (optional, can be removed if strategies
    # don't need it)
    if start_time:
        kwargs["start_time"] = start_time
    if end_time:
        kwargs["end_time"] = end_time

        # 注意: initial_cash, commission_rate, timezone, show_progress, history_depth
        # 已经在上方通过优先级逻辑处理过了，这里不需要再覆盖

        # Risk Config injection handled later

    # Handle strategy_params explicitly
    if "strategy_params" in kwargs:
        s_params = kwargs.pop("strategy_params")
        if isinstance(s_params, dict):
            kwargs.update(s_params)
    if strategy_runtime_config is None and "strategy_runtime_config" in kwargs:
        strategy_runtime_config = kwargs.pop("strategy_runtime_config")

    strategy_kwargs = dict(kwargs)
    strategy_instance = _build_strategy_instance(
        strategy,
        strategy_kwargs,
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
            slot_strategy_instances[slot_key_str] = _build_strategy_instance(
                slot_strategy_input,
                dict(strategy_kwargs),
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

    if isinstance(symbol, str):
        symbols = [symbol]
    elif isinstance(symbol, (list, tuple)):
        symbols = list(symbol)
    else:
        symbols = ["BENCHMARK"]

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
    setattr(strategy_instance, "_analyzer_manager", analyzer_manager)

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

            # Try to infer symbol from DataFrame if not explicitly provided or default
            if (
                not symbols or symbols == ["BENCHMARK"]
            ) and "symbol" in df_input.columns:
                unique_symbols = df_input["symbol"].unique()
                if len(unique_symbols) == 1:
                    inferred = unique_symbols[0]
                    if symbols == ["BENCHMARK"]:
                        symbols = [inferred]
                    else:
                        if inferred not in symbols:
                            symbols.append(inferred)

            target_symbol = symbols[0] if symbols else "BENCHMARK"
            df = prepare_dataframe(df_input)
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

        catalog = ParquetDataCatalog()
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
    if hasattr(strategy_instance, "_trading_days") and data_map_for_indicators:
        all_dates: set[pd.Timestamp] = set()
        day_bounds: Dict[str, Tuple[int, int]] = {}
        for df in data_map_for_indicators.values():
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                dates = df.index.normalize().unique()
                all_dates.update(dates)
                grouped = df.groupby(df.index.normalize())
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
            if hasattr(current_strategy, "_trading_days") and all_dates:
                current_strategy._trading_days = sorted(list(all_dates))
            if hasattr(current_strategy, "_trading_day_bounds"):
                current_strategy._trading_day_bounds = day_bounds

    # 3.5 Pre-calculate indicators
    # Inject data into indicators so they can be accessed in on_bar via get_value()
    if data_map_for_indicators:
        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "_indicators"):
                for symbol_key, df_val in data_map_for_indicators.items():
                    for ind in current_strategy._indicators:
                        try:
                            ind(df_val, symbol_key)
                        except Exception as e:
                            logger.error(
                                f"Failed to calculate indicator {ind.name} "
                                f"for {symbol_key}: {e}"
                            )

    # 4. 配置引擎
    engine = Engine()
    setattr(strategy_instance, "_engine", engine)
    if analyzer_manager.plugins:
        try:
            analyzer_manager.on_start(
                {
                    "engine": engine,
                    "strategy": strategy_instance,
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

    # ... (ExecutionMode logic)
    if isinstance(execution_mode, str):
        mode_map = {
            "next_open": ExecutionMode.NextOpen,
            "current_close": ExecutionMode.CurrentClose,
        }
        mode = mode_map.get(execution_mode.lower())
        if not mode:
            logger.warning(
                f"Unknown execution mode '{execution_mode}', defaulting to NextOpen"
            )
            mode = ExecutionMode.NextOpen
        engine.set_execution_mode(mode)
    else:
        engine.set_execution_mode(execution_mode)

    # 4.1 市场规则配置
    # 如果启用了 T+1，必须使用 ChinaMarket
    if t_plus_one:
        # T+1 必须使用 ChinaMarket
        engine.use_china_market()
        engine.set_t_plus_one(True)
    else:
        # T+0 模式
        # 使用SimpleMarket（支持佣金率和印花税）
        engine.use_simple_market(commission_rate)

    engine.set_force_session_continuous(True)
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

    if "option_commission" in kwargs:
        engine.set_option_fee_rules(kwargs["option_commission"])

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
    default_expiry_date = kwargs.get("expiry_date", None)

    def _parse_asset_type(val: Union[str, AssetType]) -> AssetType:
        if isinstance(val, AssetType):
            return val
        if isinstance(val, str):
            v_lower = val.lower()
            if "stock" in v_lower:
                return AssetType.Stock
            if "future" in v_lower:
                return AssetType.Futures
            if "fund" in v_lower:
                return AssetType.Fund
            if "option" in v_lower:
                return AssetType.Option
        return AssetType.Stock

    def _parse_option_type(val: Any) -> Any:
        # OptionType might not be available in current binary
        try:
            from ..akquant import OptionType  # type: ignore

            if isinstance(val, str):
                if val.lower() == "call":
                    return OptionType.Call
                if val.lower() == "put":
                    return OptionType.Put
        except ImportError:
            pass
        return val

    def _parse_expiry(val: Any) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            # If value is too large for i64 (nanoseconds since epoch),
            # return None or clamp?
            # Rust i64 max is 9223372036854775807
            # Let's just cast to int, Python handles large ints but PyO3 conversion
            # might fail if it exceeds Rust's i64 range.
            i_val = int(val)
            if abs(i_val) > 9223372036854775000:
                return None
            return i_val
        if isinstance(val, str):
            try:
                # Convert string date to nanosecond timestamp
                ts_val = int(pd.Timestamp(val).value)
                # Check for Rust i64 range roughly (year 2262)
                if abs(ts_val) > 9223372036854775000:
                    return None
                return ts_val
            except Exception:
                pass
        return None

    for sym in symbols:
        # Priority: Pre-built Instrument > Config > Default
        if sym in prebuilt_instruments:
            engine.add_instrument(prebuilt_instruments[sym])
            continue

        # Determine lot_size for this symbol
        current_lot_size = None
        if isinstance(lot_size, int):
            current_lot_size = lot_size
        elif isinstance(lot_size, dict):
            current_lot_size = lot_size.get(sym)

        # Check specific config
        i_conf = inst_conf_map.get(sym)

        if i_conf:
            p_asset_type = _parse_asset_type(i_conf.asset_type)
            p_multiplier = i_conf.multiplier
            p_margin = i_conf.margin_ratio
            p_tick = i_conf.tick_size
            # If config has lot_size, use it, otherwise use global setting
            p_lot = i_conf.lot_size if i_conf.lot_size != 1 else (current_lot_size or 1)

            p_opt_type = _parse_option_type(i_conf.option_type)
            p_strike = i_conf.strike_price
            p_expiry = _parse_expiry(i_conf.expiry_date)
            p_underlying = i_conf.underlying_symbol
        else:
            p_asset_type = default_asset_type
            p_multiplier = default_multiplier
            p_margin = default_margin_ratio
            p_tick = default_tick_size
            p_lot = current_lot_size or 1

            p_opt_type = default_option_type
            p_strike = default_strike_price
            p_expiry = _parse_expiry(default_expiry_date)
            p_underlying = None

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
        )
        engine.add_instrument(instr)

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

    # 7.5 Prepare Indicators (Vectorized Pre-calculation)
    if data_map_for_indicators:
        for current_strategy in all_strategy_instances:
            if hasattr(current_strategy, "_prepare_indicators"):
                current_strategy._prepare_indicators(data_map_for_indicators)

    try:
        engine.run(strategy_instance, show_progress)
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
    analyzer_outputs: Dict[str, Dict[str, Any]] = {}
    if analyzer_manager.plugins:
        try:
            analyzer_outputs = analyzer_manager.on_finish(
                {
                    "engine": engine,
                    "strategy": strategy_instance,
                    "result": result,
                }
            )
        except Exception as e:
            logger.error(f"Analyzer on_finish error: {e}")
    result.analyzer_outputs = analyzer_outputs
    setattr(result, "_owner_strategy_id", effective_strategy_id)
    return result


def run_warm_start(
    checkpoint_path: str,
    data: Optional[BacktestDataInput] = None,
    show_progress: bool = True,
    symbol: Union[str, List[str]] = "BENCHMARK",
    strategy_runtime_config: Optional[
        Union[StrategyRuntimeConfig, Dict[str, Any]]
    ] = None,
    runtime_config_override: bool = True,
    **kwargs: Any,
) -> BacktestResult:
    """
    热启动回测 (Warm Start Backtest).

    故障速查可参考 docs/zh/advanced/runtime_config.md，
    英文文档参考 docs/en/advanced/runtime_config.md

    :param kwargs: 其他引擎配置参数 (如 commission_rate, stamp_tax, t_plus_one)
    """
    import os

    from ..checkpoint import warm_start

    logger = get_logger()

    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # 1. 准备数据源
    feed = None
    data_map_for_indicators: Dict[str, pd.DataFrame] = {}

    if isinstance(data, DataFeed):
        feed = data
    elif _is_data_feed_adapter(data):
        feed = DataFeed()
        symbols = [symbol] if isinstance(symbol, str) else symbol
        adapter_data_map = _load_data_map_from_adapter(
            adapter=data,
            symbols=list(symbols),
            start_time=kwargs.get("start_time"),
            end_time=kwargs.get("end_time"),
            timezone=kwargs.get("timezone"),
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
        symbols = [symbol] if isinstance(symbol, str) else symbol

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

    # 2. 恢复引擎和策略
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
        restored_strategy_id or restored_engine_strategy_id or "_default"
    )
    setattr(strategy_instance, "_owner_strategy_id", effective_strategy_id)
    restored_slot_ids: List[str] = []
    if hasattr(engine, "get_strategy_slots"):
        try:
            slot_ids = cast(Any, engine).get_strategy_slots()
            if isinstance(slot_ids, list):
                restored_slot_ids = [
                    str(slot_id).strip() for slot_id in slot_ids if str(slot_id).strip()
                ]
        except Exception:
            restored_slot_ids = []
    if restored_slot_ids and hasattr(engine, "set_strategy_slots"):
        cast(Any, engine).set_strategy_slots(restored_slot_ids)
    if hasattr(engine, "set_default_strategy_id"):
        cast(Any, engine).set_default_strategy_id(effective_strategy_id)
    if hasattr(engine, "set_strategy_for_slot"):
        for slot_index in range(max(len(restored_slot_ids), 1)):
            cast(Any, engine).set_strategy_for_slot(slot_index, strategy_instance)

    if strategy_runtime_config is None and "strategy_runtime_config" in kwargs:
        strategy_runtime_config = kwargs.pop("strategy_runtime_config")
    if strategy_runtime_config is not None and isinstance(strategy_instance, Strategy):
        _apply_strategy_runtime_config(
            strategy_instance,
            strategy_runtime_config,
            runtime_config_override,
            logger,
        )

    if hasattr(strategy_instance, "_trading_days") and data_map_for_indicators:
        all_dates: set[pd.Timestamp] = set()
        day_bounds: Dict[str, Tuple[int, int]] = {}
        for df in data_map_for_indicators.values():
            if not df.empty and isinstance(df.index, pd.DatetimeIndex):
                dates = df.index.normalize().unique()
                all_dates.update(dates)
                grouped = df.groupby(df.index.normalize())
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

        if all_dates:
            strategy_instance._trading_days = sorted(list(all_dates))
        if hasattr(strategy_instance, "_trading_day_bounds"):
            strategy_instance._trading_day_bounds = day_bounds

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
        logger.info(f"Re-registered default instrument for warm start: {sym}")

    # 2.6 Re-configure Market Model
    # Engine restoration might lose market model config if not in State.
    # Default to SimpleMarket (T+0) or ChinaMarket (T+1) based on kwargs.
    commission = kwargs.get("commission_rate", 0.0)
    stamp_tax = kwargs.get("stamp_tax", 0.0)
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
        transfer_fee = kwargs.get("transfer_fee", 0.0)
        min_commission = kwargs.get("min_commission", 5.0)
        engine.set_stock_fee_rules(commission, stamp_tax, transfer_fee, min_commission)
        logger.info(f"Re-configured market fees: comm={commission}, stamp={stamp_tax}")

    # 3. 预计算指标 (如果新数据可用)
    # 这允许策略在新数据上计算指标
    if hasattr(strategy_instance, "_prepare_indicators") and data_map_for_indicators:
        # 注意: 这里的 _prepare_indicators 可能会重新计算整个序列的指标
        # 如果指标库支持增量更新最好，如果不支持，这里会全量重算
        # 但由于 Engine 内部只处理 snapshot_time 之后的事件，交易逻辑是增量的
        try:
            strategy_instance._prepare_indicators(data_map_for_indicators)
        except Exception as e:
            logger.error(f"Failed to update indicators for warm start: {e}")

    if hasattr(strategy_instance, "_on_start_internal"):
        strategy_instance._on_start_internal()
    elif hasattr(strategy_instance, "on_start"):
        if hasattr(strategy_instance, "is_restored") and strategy_instance.is_restored:
            if hasattr(strategy_instance, "on_resume"):
                strategy_instance.on_resume()
        strategy_instance.on_start()

    # 4. 运行
    try:
        engine.run(strategy_instance, show_progress)
    except Exception as e:
        logger.error(f"Warm start backtest failed: {e}")
        raise e
    finally:
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

    # 注意：这里的 initial_cash 可能不准确，因为它使用的是当前 cash
    # 但对于 BacktestResult 来说，重要的是 equity curve 的连续性
    # 我们使用之前捕获的 restored_cash 作为 reference
    result = BacktestResult(
        engine.get_results(),
        timezone="UTC",  # TODO: Store timezone in snapshot
        initial_cash=float(restored_cash),
        strategy=strategy_instance,
        engine=engine,
    )
    setattr(result, "_owner_strategy_id", effective_strategy_id)
    return result
