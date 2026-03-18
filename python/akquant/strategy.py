import datetime as dt
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Deque,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    cast,
)

import numpy as np
import pandas as pd

from .akquant import (
    Bar,
    ExecutionMode,
    Order,
    StrategyContext,
    Tick,
    TimeInForce,
)
from .sizer import FixedSize, Sizer
from .strategy_events import (
    on_bar_event as _on_bar_event_impl,
)
from .strategy_events import (
    on_tick_event as _on_tick_event_impl,
)
from .strategy_events import (
    on_timer_event as _on_timer_event_impl,
)
from .strategy_framework_hooks import (
    call_user_callback as _call_user_callback_impl,
)
from .strategy_framework_hooks import (
    dispatch_shutdown_hooks as _dispatch_shutdown_hooks_impl,
)
from .strategy_framework_hooks import (
    ensure_framework_state as _ensure_framework_state_impl,
)
from .strategy_history import get_history as _get_history_impl
from .strategy_history import get_history_df as _get_history_df_impl
from .strategy_history import get_rolling_data as _get_rolling_data_impl
from .strategy_history import set_history_depth as _set_history_depth_impl
from .strategy_history import set_rolling_window as _set_rolling_window_impl
from .strategy_logging import log as _log_impl
from .strategy_ml import auto_configure_model as _auto_configure_model_impl
from .strategy_ml import on_train_signal as _on_train_signal_impl
from .strategy_order_events import (
    check_order_events as _check_order_events_impl,
)
from .strategy_order_events import (
    key_value as _key_value_impl,
)
from .strategy_order_events import (
    remember_trade_key as _remember_trade_key_impl,
)
from .strategy_order_events import (
    trade_dedupe_cache_limit as _trade_dedupe_cache_limit_impl,
)
from .strategy_order_events import (
    trade_event_key as _trade_event_key_impl,
)
from .strategy_position import Position
from .strategy_scheduler import add_daily_timer as _add_daily_timer_impl
from .strategy_scheduler import schedule as _schedule_impl
from .strategy_time import format_time as _format_time_impl
from .strategy_time import now as _now_impl
from .strategy_time import to_local_time as _to_local_time_impl
from .strategy_trading_api import (
    buy as _buy_impl,
)
from .strategy_trading_api import (
    buy_all as _buy_all_impl,
)
from .strategy_trading_api import (
    calculate_max_buy_qty as _calculate_max_buy_qty_impl,
)
from .strategy_trading_api import (
    cancel_all_orders as _cancel_all_orders_impl,
)
from .strategy_trading_api import (
    cancel_order as _cancel_order_impl,
)
from .strategy_trading_api import (
    close_position as _close_position_impl,
)
from .strategy_trading_api import (
    cover as _cover_impl,
)
from .strategy_trading_api import (
    get_account as _get_account_impl,
)
from .strategy_trading_api import (
    get_available_position as _get_available_position_impl,
)
from .strategy_trading_api import (
    get_cash as _get_cash_impl,
)
from .strategy_trading_api import (
    get_execution_capabilities as _get_execution_capabilities_impl,
)
from .strategy_trading_api import (
    get_open_orders as _get_open_orders_impl,
)
from .strategy_trading_api import (
    get_order as _get_order_impl,
)
from .strategy_trading_api import (
    get_portfolio_value as _get_portfolio_value_impl,
)
from .strategy_trading_api import (
    get_position as _get_position_impl,
)
from .strategy_trading_api import (
    get_positions as _get_positions_impl,
)
from .strategy_trading_api import (
    hold_bar as _hold_bar_impl,
)
from .strategy_trading_api import (
    order_target as _order_target_impl,
)
from .strategy_trading_api import (
    order_target_percent as _order_target_percent_impl,
)
from .strategy_trading_api import (
    order_target_value as _order_target_value_impl,
)
from .strategy_trading_api import (
    order_target_weights as _order_target_weights_impl,
)
from .strategy_trading_api import (
    resolve_symbol as _resolve_symbol_impl,
)
from .strategy_trading_api import (
    sell as _sell_impl,
)
from .strategy_trading_api import (
    short as _short_impl,
)
from .strategy_trading_api import (
    stop_buy as _stop_buy_impl,
)
from .strategy_trading_api import (
    stop_sell as _stop_sell_impl,
)
from .strategy_trading_api import (
    submit_order as _submit_order_impl,
)

if TYPE_CHECKING:
    from .indicator import Indicator
    from .ml.model import QuantModel


@dataclass
class StrategyRuntimeConfig:
    """策略运行时行为配置."""

    enable_precise_day_boundary_hooks: bool = False
    portfolio_update_eps: float = 0.0
    error_mode: Literal["raise", "continue", "legacy"] = "raise"
    re_raise_on_error: bool = True
    indicator_mode: Literal["incremental", "precompute"] = "precompute"

    def __post_init__(self) -> None:
        """校验并标准化配置."""
        self.portfolio_update_eps = float(self.portfolio_update_eps)
        if self.portfolio_update_eps < 0.0:
            raise ValueError("portfolio_update_eps must be >= 0")
        mode = str(self.error_mode).strip().lower()
        if mode not in {"raise", "continue", "legacy"}:
            raise ValueError("error_mode must be one of: raise, continue, legacy")
        self.error_mode = cast(Literal["raise", "continue", "legacy"], mode)
        indicator_mode = str(self.indicator_mode).strip().lower()
        if indicator_mode not in {"incremental", "precompute"}:
            raise ValueError("indicator_mode must be one of: incremental, precompute")
        self.indicator_mode = cast(Literal["incremental", "precompute"], indicator_mode)
        self.enable_precise_day_boundary_hooks = bool(
            self.enable_precise_day_boundary_hooks
        )
        self.re_raise_on_error = bool(self.re_raise_on_error)


class Strategy:
    """
    策略基类 (Base Strategy Class).

    采用事件驱动设计
    """

    ctx: Optional[StrategyContext]
    execution_mode: Optional[ExecutionMode]
    sizer: Sizer
    current_bar: Optional[Bar]
    current_tick: Optional[Tick]
    _history_depth: int
    # Rust maintains HistoryBuffer for indicator calculation.
    # Python side accesses it via self.ctx.history() (efficient copy).
    # No duplicate storage in Python.
    _precomputed_indicators: List["Indicator"]
    _incremental_indicators: Dict[str, Dict[str, Any]]
    _subscriptions: List[str]
    _last_prices: Dict[str, float]
    _rolling_train_window: int
    _rolling_step: int
    _bar_count: int
    _model_configured: bool
    model: Optional["QuantModel"]
    _known_orders: Dict[str, Order]
    _seen_trade_keys: set[Tuple[Any, ...]]
    _seen_trade_key_order: Deque[Tuple[Any, ...]]
    timezone: str = "Asia/Shanghai"
    warmup_period: int = 0
    _runtime_config: StrategyRuntimeConfig
    _last_event_type: str = ""  # "bar" or "tick"
    _hold_bars: "defaultdict[str, int]"
    _last_position_signs: "defaultdict[str, float]"
    _framework_last_session: Any
    _framework_last_local_date: Optional[dt.date]
    _framework_before_trading_done_date: Optional[dt.date]
    _framework_after_trading_done_date: Optional[dt.date]
    _framework_last_portfolio_state: Any
    _framework_portfolio_dirty: bool
    _framework_rejected_order_ids: set[str]
    _framework_stop_flushed: bool
    _framework_boundary_timers_registered: bool
    _trading_day_bounds: Dict[str, Tuple[int, int]]
    _oco_groups: Dict[str, set[str]]
    _oco_order_to_group: Dict[str, str]
    _use_engine_oco: bool
    _pending_engine_oco_groups: List[Tuple[str, str, str]]
    _use_engine_bracket: bool
    _pending_engine_bracket_plans: List[
        Tuple[
            str,
            Optional[float],
            Optional[float],
            Optional[TimeInForce],
            Optional[str],
            Optional[str],
        ]
    ]
    _pending_brackets: Dict[str, Dict[str, Any]]
    _order_group_seq: int

    _trading_days: List[pd.Timestamp]

    # Fee rates
    commission_rate: float
    min_commission: float
    stamp_tax_rate: float
    transfer_fee_rate: float
    lot_size: Any  # Can be int or Dict[str, int]

    def __new__(cls, *args: Any, **kwargs: Any) -> "Strategy":
        """Create a new Strategy instance."""
        instance = super().__new__(cls)
        # 初始化默认属性，确保 pickle 恢复前也有这些字段
        instance._is_restored = False
        instance.ctx = None
        instance.execution_mode = None
        instance.sizer = FixedSize(100)
        instance.current_bar = None
        instance.current_tick = None
        instance._precomputed_indicators = []
        instance._incremental_indicators = {}
        instance._subscriptions = []
        instance._last_prices = {}
        instance._known_orders = {}
        instance._seen_trade_keys = set()
        instance._seen_trade_key_order = deque()
        instance._hold_bars = defaultdict(int)
        instance._last_position_signs = defaultdict(float)
        instance.timezone = getattr(instance, "timezone", "Asia/Shanghai")
        raw_runtime_config = getattr(instance, "_runtime_config", None)
        class_enable_hooks = cls.__dict__.get(
            "enable_precise_day_boundary_hooks", False
        )
        class_portfolio_eps = cls.__dict__.get("portfolio_update_eps", 0.0)
        class_error_mode = cls.__dict__.get("error_mode", "raise")
        class_re_raise = cls.__dict__.get("re_raise_on_error", True)
        class_indicator_mode = cls.__dict__.get("indicator_mode", "precompute")
        if isinstance(raw_runtime_config, dict):
            instance.runtime_config = StrategyRuntimeConfig(**raw_runtime_config)
        elif isinstance(raw_runtime_config, StrategyRuntimeConfig):
            instance.runtime_config = StrategyRuntimeConfig(
                enable_precise_day_boundary_hooks=raw_runtime_config.enable_precise_day_boundary_hooks,
                portfolio_update_eps=raw_runtime_config.portfolio_update_eps,
                error_mode=raw_runtime_config.error_mode,
                re_raise_on_error=raw_runtime_config.re_raise_on_error,
                indicator_mode=raw_runtime_config.indicator_mode,
            )
        else:
            instance.runtime_config = StrategyRuntimeConfig(
                enable_precise_day_boundary_hooks=bool(class_enable_hooks),
                portfolio_update_eps=float(class_portfolio_eps),
                error_mode=cast(
                    Literal["raise", "continue", "legacy"], str(class_error_mode)
                ),
                re_raise_on_error=bool(class_re_raise),
                indicator_mode=cast(
                    Literal["incremental", "precompute"], str(class_indicator_mode)
                ),
            )
        instance._last_event_type = ""
        instance._trading_days = []

        # 历史数据配置
        instance._history_depth = 0
        instance.warmup_period = getattr(instance, "warmup_period", 0)

        # 滚动训练配置
        instance._rolling_train_window = 0
        instance._rolling_step = 0
        instance._bar_count = 0
        instance._model_configured = False
        instance._start_initialized = False

        # 初始化通常在 __init__ 中的属性，允许子类省略 super().__init__()
        instance.model = None

        # 默认费率配置
        instance.commission_rate = 0.0
        instance.min_commission = 0.0
        instance.stamp_tax_rate = 0.0
        instance.transfer_fee_rate = 0.0
        # lot_size 可以是 int (全局统一) 或 Dict[str, int] (按标的设置)
        # 默认 1，这是最通用的设置（适用于美股、加密货币等）。A股回测请务必设置为 100。
        instance.lot_size = 1
        instance._framework_last_session = None
        instance._framework_last_local_date = None
        instance._framework_before_trading_done_date = None
        instance._framework_after_trading_done_date = None
        instance._framework_last_portfolio_state = None
        instance._framework_portfolio_dirty = True
        instance._framework_rejected_order_ids = set()
        instance._framework_stop_flushed = False
        instance._framework_boundary_timers_registered = False
        instance._trading_day_bounds = {}
        instance._oco_groups = {}
        instance._oco_order_to_group = {}
        instance._use_engine_oco = False
        instance._pending_engine_oco_groups = []
        instance._use_engine_bracket = False
        instance._pending_engine_bracket_plans = []
        instance._pending_brackets = {}
        instance._order_group_seq = 0

        return instance

    def __init__(self) -> None:
        """初始化."""
        pass

    def __getstate__(self) -> Dict[str, Any]:
        """
        Pickle 序列化支持.

        排除运行时上下文 (ctx) 和临时对象 (current_bar, current_tick).
        """
        state = self.__dict__.copy()
        if "ctx" in state:
            del state["ctx"]
        if "current_bar" in state:
            del state["current_bar"]
        if "current_tick" in state:
            del state["current_tick"]
        if "_framework_last_session" in state:
            del state["_framework_last_session"]
        if "_framework_last_local_date" in state:
            del state["_framework_last_local_date"]
        if "_framework_before_trading_done_date" in state:
            del state["_framework_before_trading_done_date"]
        if "_framework_after_trading_done_date" in state:
            del state["_framework_after_trading_done_date"]
        if "_framework_last_portfolio_state" in state:
            del state["_framework_last_portfolio_state"]
        if "_framework_portfolio_dirty" in state:
            del state["_framework_portfolio_dirty"]
        if "_framework_rejected_order_ids" in state:
            del state["_framework_rejected_order_ids"]
        if "_framework_stop_flushed" in state:
            del state["_framework_stop_flushed"]
        if "_framework_boundary_timers_registered" in state:
            del state["_framework_boundary_timers_registered"]
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Pickle 反序列化支持."""
        self.__dict__.update(state)
        raw_runtime_config = self.__dict__.pop("runtime_config", None)
        if raw_runtime_config is not None:
            self.runtime_config = raw_runtime_config
        elif "_runtime_config" in self.__dict__:
            self.runtime_config = self.__dict__["_runtime_config"]
        else:
            self.runtime_config = StrategyRuntimeConfig(
                enable_precise_day_boundary_hooks=bool(
                    self.__dict__.pop("enable_precise_day_boundary_hooks", False)
                ),
                portfolio_update_eps=float(
                    self.__dict__.pop("portfolio_update_eps", 0.0)
                ),
                error_mode=cast(
                    Literal["raise", "continue", "legacy"],
                    str(self.__dict__.pop("error_mode", "raise")),
                ),
                re_raise_on_error=bool(self.__dict__.pop("re_raise_on_error", True)),
                indicator_mode=cast(
                    Literal["incremental", "precompute"],
                    str(self.__dict__.pop("indicator_mode", "precompute")),
                ),
            )
        self.ctx = None
        self.current_bar = None
        self.current_tick = None
        self._is_restored = True  # 标记为已恢复状态
        self._start_initialized = False
        if not hasattr(self, "_seen_trade_keys"):
            self._seen_trade_keys = set()
        if not hasattr(self, "_seen_trade_key_order"):
            self._seen_trade_key_order = deque()
        if not hasattr(self, "_oco_groups"):
            self._oco_groups = {}
        if not hasattr(self, "_oco_order_to_group"):
            self._oco_order_to_group = {}
        if not hasattr(self, "_use_engine_oco"):
            self._use_engine_oco = False
        if not hasattr(self, "_pending_engine_oco_groups"):
            self._pending_engine_oco_groups = []
        if not hasattr(self, "_use_engine_bracket"):
            self._use_engine_bracket = False
        if not hasattr(self, "_pending_engine_bracket_plans"):
            self._pending_engine_bracket_plans = []
        if not hasattr(self, "_pending_brackets"):
            self._pending_brackets = {}
        if not hasattr(self, "_order_group_seq"):
            self._order_group_seq = 0
        _ensure_framework_state_impl(self)

    @property
    def runtime_config(self) -> StrategyRuntimeConfig:
        """返回策略运行时配置."""
        cfg = getattr(self, "_runtime_config", None)
        if isinstance(cfg, StrategyRuntimeConfig):
            return cfg
        if isinstance(cfg, dict):
            self._runtime_config = StrategyRuntimeConfig(**cfg)
            return self._runtime_config
        self._runtime_config = StrategyRuntimeConfig()
        return self._runtime_config

    @runtime_config.setter
    def runtime_config(
        self, value: Union[StrategyRuntimeConfig, Dict[str, Any]]
    ) -> None:
        """设置策略运行时配置."""
        if isinstance(value, StrategyRuntimeConfig):
            self._runtime_config = StrategyRuntimeConfig(
                enable_precise_day_boundary_hooks=value.enable_precise_day_boundary_hooks,
                portfolio_update_eps=value.portfolio_update_eps,
                error_mode=value.error_mode,
                re_raise_on_error=value.re_raise_on_error,
                indicator_mode=value.indicator_mode,
            )
            return
        if isinstance(value, dict):
            self._runtime_config = StrategyRuntimeConfig(**value)
            return
        raise TypeError(
            "runtime_config must be StrategyRuntimeConfig or Dict[str, Any]"
        )

    @property
    def enable_precise_day_boundary_hooks(self) -> bool:
        """是否启用边界定时器精确交易日钩子."""
        return self.runtime_config.enable_precise_day_boundary_hooks

    @enable_precise_day_boundary_hooks.setter
    def enable_precise_day_boundary_hooks(self, value: bool) -> None:
        """设置边界定时器精确交易日钩子开关."""
        cfg = self.runtime_config
        self.runtime_config = StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=bool(value),
            portfolio_update_eps=cfg.portfolio_update_eps,
            error_mode=cfg.error_mode,
            re_raise_on_error=cfg.re_raise_on_error,
            indicator_mode=cfg.indicator_mode,
        )

    @property
    def portfolio_update_eps(self) -> float:
        """返回账户快照更新阈值."""
        return self.runtime_config.portfolio_update_eps

    @portfolio_update_eps.setter
    def portfolio_update_eps(self, value: float) -> None:
        """设置账户快照更新阈值."""
        cfg = self.runtime_config
        self.runtime_config = StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=cfg.enable_precise_day_boundary_hooks,
            portfolio_update_eps=float(value),
            error_mode=cfg.error_mode,
            re_raise_on_error=cfg.re_raise_on_error,
            indicator_mode=cfg.indicator_mode,
        )

    @property
    def error_mode(self) -> str:
        """返回错误处理模式."""
        return self.runtime_config.error_mode

    @error_mode.setter
    def error_mode(self, value: str) -> None:
        """设置错误处理模式."""
        cfg = self.runtime_config
        self.runtime_config = StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=cfg.enable_precise_day_boundary_hooks,
            portfolio_update_eps=cfg.portfolio_update_eps,
            error_mode=cast(Literal["raise", "continue", "legacy"], value),
            re_raise_on_error=cfg.re_raise_on_error,
            indicator_mode=cfg.indicator_mode,
        )

    @property
    def re_raise_on_error(self) -> bool:
        """返回是否在 on_error 后继续抛出异常."""
        return self.runtime_config.re_raise_on_error

    @re_raise_on_error.setter
    def re_raise_on_error(self, value: bool) -> None:
        """设置 on_error 后是否继续抛出异常."""
        cfg = self.runtime_config
        self.runtime_config = StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=cfg.enable_precise_day_boundary_hooks,
            portfolio_update_eps=cfg.portfolio_update_eps,
            error_mode=cfg.error_mode,
            re_raise_on_error=bool(value),
            indicator_mode=cfg.indicator_mode,
        )

    @property
    def indicator_mode(self) -> Literal["incremental", "precompute"]:
        """返回指标执行模式."""
        return self.runtime_config.indicator_mode

    @indicator_mode.setter
    def indicator_mode(self, value: Literal["incremental", "precompute"]) -> None:
        cfg = self.runtime_config
        self.runtime_config = StrategyRuntimeConfig(
            enable_precise_day_boundary_hooks=cfg.enable_precise_day_boundary_hooks,
            portfolio_update_eps=cfg.portfolio_update_eps,
            error_mode=cfg.error_mode,
            re_raise_on_error=cfg.re_raise_on_error,
            indicator_mode=value,
        )

    @property
    def is_restored(self) -> bool:
        """检查策略是否是从快照恢复的."""
        return getattr(self, "_is_restored", False)

    def on_start(self) -> None:
        """
        策略启动时调用.

        Warm Start 注意：如果策略是从快照恢复的，此方法仍会被调用。
        如果在此处初始化指标，请务必检查属性是否存在 (hasattr)，
        或者使用 self.is_restored 属性判断，避免覆盖已恢复的状态。
        """
        pass

    def on_resume(self) -> None:
        """
        策略从快照恢复时调用 (Warm Start).

        仅在 Warm Start 模式下调用，且在 on_start 之前调用。
        用于重新建立非持久化连接、加载外部资源等。
        """
        pass

    def _on_start_internal(self) -> None:
        """内部启动回调."""
        if self._start_initialized:
            return

        # 如果是恢复模式，先调用 on_resume
        if self.is_restored:
            self.on_resume()

        self.on_start()
        self._start_initialized = True

    def on_stop(self) -> None:
        """
        策略停止时调用.

        在此处进行资源清理或结果统计.
        """
        pass

    def _on_stop_internal(self) -> None:
        """内部停止回调，用于补发框架级结束钩子."""
        _ensure_framework_state_impl(self)
        _dispatch_shutdown_hooks_impl(self)
        _call_user_callback_impl(self, "on_stop")

    def log(self, msg: str, level: int = logging.INFO) -> None:
        """
        输出日志 (自动添加当前回测时间).

        :param msg: 日志内容
        :param level: 日志等级 (logging.INFO, logging.WARNING, etc.)
        """
        _log_impl(self, msg, level)

    @property
    def symbol(self) -> str:
        """获取当前正在处理的标的代码 (Proxy to current_bar/tick)."""
        return self._resolve_symbol(None)

    @property
    def close(self) -> float:
        """获取当前最新价 (Close 或 LastPrice)."""
        if self.current_bar:
            return self.current_bar.close
        elif self.current_tick:
            return self.current_tick.price
        return 0.0

    @property
    def open(self) -> float:
        """获取当前开盘价 (仅 Bar 模式有效)."""
        if self.current_bar:
            return self.current_bar.open
        return 0.0

    @property
    def high(self) -> float:
        """获取当前最高价 (仅 Bar 模式有效)."""
        if self.current_bar:
            return self.current_bar.high
        return 0.0

    @property
    def low(self) -> float:
        """获取当前最低价 (仅 Bar 模式有效)."""
        if self.current_bar:
            return self.current_bar.low
        return 0.0

    @property
    def volume(self) -> float:
        """获取当前成交量."""
        if self.current_bar:
            return self.current_bar.volume
        elif self.current_tick:
            return self.current_tick.volume
        return 0.0

    def schedule(
        self, trigger_time: Union[str, dt.datetime, pd.Timestamp], payload: str
    ) -> None:
        """
        注册单次定时任务 (Simplified).

        :param trigger_time: 触发时间 (支持 "2023-01-01 14:55:00", datetime, Timestamp)
        :param payload: 回调标识
        """
        _schedule_impl(self, trigger_time, payload)

    def add_daily_timer(self, time_str: str, payload: str) -> None:
        """
        注册每日定时任务 (Daily Timer).

        :param time_str: 时间字符串 (例如 "14:55:00")
        :param payload: 回调标识
        """
        _add_daily_timer_impl(self, time_str, payload)

    def to_local_time(self, timestamp: int) -> pd.Timestamp:
        """
        将 UTC 纳秒时间戳转换为本地时间 (Timestamp).

        :param timestamp: UTC 纳秒时间戳 (int64)
        :return: 本地时间 (pd.Timestamp)
        """
        return _to_local_time_impl(self, timestamp)

    def format_time(self, timestamp: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        将 UTC 纳秒时间戳格式化为本地时间字符串.

        :param timestamp: UTC 纳秒时间戳 (int64)
        :param fmt: 时间格式字符串
        :return: 格式化后的时间字符串
        """
        return _format_time_impl(self, timestamp, fmt)

    @property
    def now(self) -> Optional[pd.Timestamp]:
        """
        获取当前回测时间的本地时间表示.

        如果当前没有 Bar 或 Tick，则返回 None.
        """
        return _now_impl(self)

    def set_history_depth(self, depth: int) -> None:
        """
        设置历史数据回溯长度.

        :param depth: 保留的 Bar 数量 (0 表示不保留)
        """
        _set_history_depth_impl(self, depth)

    def set_rolling_window(self, train_window: int, step: int) -> None:
        """
        设置滚动训练窗口参数.

        :param train_window: 训练数据长度 (Bars)
        :param step: 滚动步长 (每隔多少个 Bar 触发一次训练)
        """
        _set_rolling_window_impl(self, train_window, step)

    def get_history(
        self, count: int, symbol: Optional[str] = None, field: str = "close"
    ) -> np.ndarray:
        """
        获取历史数据 (类似 Zipline data.history).

        :param count: 获取的数据长度 (必须 <= history_depth)
        :param symbol: 标的代码 (默认当前 Bar 的 symbol)
        :param field: 字段名 (open, high, low, close, volume)
        :return: Numpy 数组
        """
        return _get_history_impl(self, count, symbol, field)

    def get_history_df(self, count: int, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        获取历史数据 DataFrame (Open, High, Low, Close, Volume).

        :param count: 数据长度
        :param symbol: 标的代码
        :return: pd.DataFrame
        """
        return _get_history_df_impl(self, count, symbol)

    def get_rolling_data(
        self, length: Optional[int] = None, symbol: Optional[str] = None
    ) -> tuple[pd.DataFrame, Optional[pd.Series]]:
        """
        获取滚动训练数据.

        :param length: 数据长度 (默认使用 set_rolling_window 设置的 train_window)
        :param symbol: 标的代码
        :return: (X, y) 默认为 (DataFrame, None)
        """
        return _get_rolling_data_impl(self, length, symbol)

    def on_train_signal(self, context: Any) -> None:
        """
        滚动训练信号回调.

        默认实现：如果配置了 self.model，则自动执行数据准备和训练.

        :param context: 策略上下文 (通常是 self)
        """
        _on_train_signal_impl(self, context)

    def prepare_features(
        self, df: pd.DataFrame, mode: str = "training"
    ) -> Tuple[Any, Any]:
        """
        Prepare features and labels for ML model.

        Must be implemented by user if using auto-training.

        :param df: Raw dataframe from get_rolling_data
        :param mode: "training" or "inference".
                     If "training", return (X, y).
                     If "inference", return (X_last_row, None) or just X.
        :return: (X, y)
        """
        raise NotImplementedError(
            "You must implement prepare_features(self, df, mode) for auto-training"
        )

    def _auto_configure_model(self) -> None:
        """Apply model validation configuration if present."""
        _auto_configure_model_impl(self)

    def set_sizer(self, sizer: Sizer) -> None:
        """设置仓位管理器."""
        self.sizer = sizer

    def register_indicator(self, name: str, indicator: "Indicator") -> None:
        """
        Register an indicator.

        This allows accessing the indicator via self.name and ensures it is
        calculated before the backtest starts.
        """
        self.register_precomputed_indicator(name, indicator)

    def register_precomputed_indicator(self, name: str, indicator: "Indicator") -> None:
        """注册预计算指标."""
        if self.indicator_mode != "precompute":
            raise ValueError(
                "register_precomputed_indicator requires indicator_mode='precompute'"
            )
        if indicator not in self._precomputed_indicators:
            self._precomputed_indicators.append(indicator)
        setattr(self, name, indicator)

    def register_incremental_indicator(
        self,
        name: str,
        indicator: Any,
        source: str = "close",
        symbols: Optional[Union[str, List[str], Tuple[str, ...], set[str]]] = None,
    ) -> None:
        """注册增量指标."""
        if self.indicator_mode != "incremental":
            raise ValueError(
                "register_incremental_indicator requires indicator_mode='incremental'"
            )
        source_key = str(source).strip().lower()
        if source_key not in {"open", "high", "low", "close", "volume"}:
            raise ValueError("source must be one of: open, high, low, close, volume")
        symbol_filter = self._normalize_indicator_symbols(symbols)
        self._incremental_indicators[name] = {
            "indicator": indicator,
            "source": source_key,
            "symbols": symbol_filter,
        }
        setattr(self, name, indicator)

    def subscribe(self, instrument_id: str) -> None:
        """
        Subscribe to market data for an instrument.

        :param instrument_id: The instrument identifier (e.g., '600000').
        """
        if instrument_id not in self._subscriptions:
            self._subscriptions.append(instrument_id)

    def _prepare_indicators(self, data: Dict[str, pd.DataFrame]) -> None:
        """Pre-calculate indicators for precompute mode."""
        if self.indicator_mode != "precompute":
            return
        if not self._precomputed_indicators:
            return

        for ind in self._precomputed_indicators:
            for sym, df in data.items():
                # Calculate and cache inside indicator
                ind(df, sym)

    def _update_incremental_indicators(self, bar: Bar) -> None:
        if self.indicator_mode != "incremental":
            return
        if not self._incremental_indicators:
            return
        for item in self._incremental_indicators.values():
            symbol_filter = item["symbols"]
            if symbol_filter is not None and bar.symbol not in symbol_filter:
                continue
            ind = item["indicator"]
            source = item["source"]
            value = getattr(bar, source)
            ind.update(value)

    def _normalize_indicator_symbols(
        self,
        symbols: Optional[Union[str, List[str], Tuple[str, ...], set[str]]],
    ) -> Optional[set[str]]:
        if symbols is None:
            return None
        if isinstance(symbols, str):
            symbol_text = symbols.strip()
            if not symbol_text:
                raise ValueError("symbols cannot contain empty symbol")
            return {symbol_text}
        if isinstance(symbols, (list, tuple, set)):
            normalized: set[str] = set()
            for symbol in symbols:
                symbol_text = str(symbol).strip()
                if not symbol_text:
                    raise ValueError("symbols cannot contain empty symbol")
                normalized.add(symbol_text)
            if not normalized:
                raise ValueError("symbols cannot be empty")
            return normalized
        raise TypeError("symbols must be str, list[str], tuple[str, ...], set[str]")

    def on_order(self, order: Any) -> None:
        """
        订单状态更新回调.

        Args:
            order: 订单对象
        """
        pass

    def on_trade(self, trade: Any) -> None:
        """
        成交回调.

        Args:
            trade: 成交对象
        """
        pass

    def on_session_start(self, session: Any, timestamp: int) -> None:
        """会话开始回调."""
        pass

    def on_session_end(self, session: Any, timestamp: int) -> None:
        """会话结束回调."""
        pass

    def before_trading(self, trading_date: dt.date, timestamp: int) -> None:
        """交易日开始前回调."""
        pass

    def after_trading(self, trading_date: dt.date, timestamp: int) -> None:
        """交易日结束后回调."""
        pass

    def on_reject(self, order: Any) -> None:
        """拒单回调."""
        pass

    def on_portfolio_update(self, snapshot: Dict[str, Any]) -> None:
        """账户变化回调."""
        pass

    def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
        """错误回调."""
        pass

    def _check_order_events(self) -> None:
        _check_order_events_impl(self)

    def _trade_event_key(self, trade: Any) -> Tuple[Any, ...]:
        return _trade_event_key_impl(self, trade)

    def _key_value(self, value: Any) -> Any:
        return _key_value_impl(value)

    def _remember_trade_key(self, key: Tuple[Any, ...]) -> bool:
        return _remember_trade_key_impl(self, key)

    def _trade_dedupe_cache_limit(self) -> int:
        return _trade_dedupe_cache_limit_impl(self)

    def _on_bar_event(self, bar: Bar, ctx: StrategyContext) -> None:
        _on_bar_event_impl(self, bar, ctx)

    def _on_tick_event(self, tick: Tick, ctx: StrategyContext) -> None:
        _on_tick_event_impl(self, tick, ctx)

    def _on_timer_event(self, payload: str, ctx: StrategyContext) -> None:
        _on_timer_event_impl(self, payload, ctx)

    def on_bar(self, bar: Bar) -> None:
        """
        策略逻辑入口 (Bar 数据).

        用户应重写此方法.
        """
        pass

    @property
    def position(self) -> Position:
        """
        获取当前处理标的的持仓对象.

        支持常见的策略编写语法:
        if self.position.size == 0:
            ...
        """
        if self.ctx is None:
            raise RuntimeError("Context not ready")

        symbol = self._resolve_symbol(None)
        return Position(self.ctx, symbol)

    def on_tick(self, tick: Tick) -> None:
        """
        策略逻辑入口 (Tick 数据).

        用户应重写此方法.
        """
        pass

    def on_timer(self, payload: str) -> None:
        """
        策略逻辑入口 (Timer 事件).

        用户应重写此方法.
        """
        pass

    def _resolve_symbol(self, symbol: Optional[str] = None) -> str:
        return _resolve_symbol_impl(self, symbol)

    def get_position(self, symbol: Optional[str] = None) -> float:
        """
        获取指定标的的持仓数量.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)

        Returns:
            float: 持仓数量 (正数为多头, 负数为空头)
        """
        return _get_position_impl(self, symbol)

    def get_available_position(self, symbol: Optional[str] = None) -> float:
        """
        获取指定标的的可用持仓数量 (考虑 T+1 等限制).

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)

        Returns:
            float: 可用持仓数量
        """
        return _get_available_position_impl(self, symbol)

    def hold_bar(self, symbol: Optional[str] = None) -> int:
        """
        获取当前持仓持有的 Bar 数量.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)

        Returns:
            int: 持有的 Bar 数量. 如果未持仓，返回 0.
        """
        return _hold_bar_impl(self, symbol)

    def get_positions(self) -> Dict[str, float]:
        """
        获取所有持仓信息.

        Returns:
            Dict[str, float]: 持仓字典 {symbol: quantity}
        """
        return _get_positions_impl(self)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Any]:
        """
        获取当前未完成的订单.

        Args:
            symbol: 标的代码 (如果为 None，返回所有标的订单)

        Returns:
            List[Order]: 订单列表
        """
        return _get_open_orders_impl(self, symbol)

    def get_order(self, order_id: str) -> Optional[Any]:
        """
        获取指定订单详情.

        Args:
            order_id: 订单 ID

        Returns:
            Order: 订单对象，如果未找到则返回 None
        """
        return _get_order_impl(self, order_id)

    def get_account(self) -> Dict[str, float]:
        """
        获取账户资金详情快照.

        Returns:
            Dict: 包含以下字段:
                - cash: 可用资金
                - equity: 总权益 (现金 + 持仓市值)
                - market_value: 持仓总市值 (equity - cash)
                - frozen_cash: (预留) 冻结资金, 暂为 0.0
                - margin: (预留) 占用保证金, 暂为 0.0
        """
        return _get_account_impl(self)

    def get_trades(self) -> List[Any]:
        """
        获取所有历史成交记录 (Closed Trades).

        Returns:
            List[ClosedTrade]: 已平仓交易列表
        """
        if self.ctx:
            return self.ctx.closed_trades
        return []

    def cancel_order(self, order_id: str) -> None:
        """
        取消指定订单.

        Args:
            order_id: 订单 ID
        """
        _cancel_order_impl(self, order_id)

    def cancel_all_orders(self, symbol: Optional[str] = None) -> None:
        """
        取消当前所有未完成的订单.

        Args:
            symbol: 标的代码 (如果不填, 取消所有标的订单)
        """
        _cancel_all_orders_impl(self, symbol)

    def create_oco_order_group(
        self,
        first_order_id: str,
        second_order_id: str,
        group_id: Optional[str] = None,
    ) -> str:
        """
        创建 OCO 订单组.

        当组内任一订单成交时，自动撤销另一订单。
        """
        first = first_order_id.strip()
        second = second_order_id.strip()
        if not first or not second:
            raise ValueError("OCO order ids cannot be empty")
        if first == second:
            raise ValueError("OCO order ids must be different")

        if group_id is None or not str(group_id).strip():
            self._order_group_seq += 1
            group_id = f"oco-{self._order_group_seq}"
        group_key = str(group_id).strip()

        engine = getattr(self, "_engine", None)
        register_oco = getattr(engine, "register_oco_group", None)
        if callable(register_oco):
            try:
                register_oco(group_key, first, second)
                self._use_engine_oco = True
                return group_key
            except Exception:
                self._pending_engine_oco_groups.append((group_key, first, second))
                self._use_engine_oco = True
                return group_key

        self._detach_oco_order(first)
        self._detach_oco_order(second)

        self._oco_groups[group_key] = {first, second}
        self._oco_order_to_group[first] = group_key
        self._oco_order_to_group[second] = group_key
        return group_key

    def place_bracket_order(
        self,
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
        """
        创建 Bracket 订单.

        先提交进场单，待进场成交后自动挂出止损/止盈，并绑定 OCO。
        """
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if stop_trigger_price is None and take_profit_price is None:
            raise ValueError("stop_trigger_price or take_profit_price must be provided")

        entry_order_id = self.buy(
            symbol=symbol,
            quantity=quantity,
            price=entry_price,
            time_in_force=time_in_force,
            tag=entry_tag,
        )
        if not entry_order_id:
            raise RuntimeError("failed to submit bracket entry order")

        engine = getattr(self, "_engine", None)
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
                self._use_engine_bracket = True
                return entry_order_id
            except Exception:
                self._pending_engine_bracket_plans.append(
                    (
                        entry_order_id,
                        stop_trigger_price,
                        take_profit_price,
                        time_in_force,
                        stop_tag,
                        take_profit_tag,
                    )
                )
                self._use_engine_bracket = True
                return entry_order_id

        self._pending_brackets[entry_order_id] = {
            "symbol": symbol,
            "quantity": float(quantity),
            "stop_trigger_price": stop_trigger_price,
            "take_profit_price": take_profit_price,
            "time_in_force": time_in_force,
            "stop_tag": stop_tag,
            "take_profit_tag": take_profit_tag,
        }
        return entry_order_id

    def _process_order_groups(self, trade: Any) -> None:
        self._process_pending_bracket(trade)
        self._process_oco_trade(trade)

    def _process_pending_bracket(self, trade: Any) -> None:
        if self._use_engine_bracket:
            return
        order_id = str(getattr(trade, "order_id", "") or "")
        if not order_id:
            return

        bracket = self._pending_brackets.pop(order_id, None)
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
        time_in_force = cast(Optional[TimeInForce], bracket["time_in_force"])

        if stop_trigger_price is not None:
            stop_order_id = self.sell(
                symbol=symbol,
                quantity=quantity,
                trigger_price=float(stop_trigger_price),
                time_in_force=time_in_force,
                tag=cast(Optional[str], bracket["stop_tag"]),
            )

        if take_profit_price is not None:
            take_order_id = self.sell(
                symbol=symbol,
                quantity=quantity,
                price=float(take_profit_price),
                time_in_force=time_in_force,
                tag=cast(Optional[str], bracket["take_profit_tag"]),
            )

        if stop_order_id and take_order_id:
            self.create_oco_order_group(stop_order_id, take_order_id)

    def _process_oco_trade(self, trade: Any) -> None:
        if self._use_engine_oco:
            return
        order_id = str(getattr(trade, "order_id", "") or "")
        if not order_id:
            return

        group_id = self._oco_order_to_group.get(order_id)
        if not group_id:
            return

        group_orders = self._oco_groups.get(group_id, set())
        peer_orders = [oid for oid in group_orders if oid != order_id]
        for peer_order_id in peer_orders:
            self.cancel_order(peer_order_id)

        self._remove_oco_group(group_id)

    def _detach_oco_order(self, order_id: str) -> None:
        old_group = self._oco_order_to_group.get(order_id)
        if not old_group:
            return
        group_orders = self._oco_groups.get(old_group)
        if group_orders is not None:
            group_orders.discard(order_id)
            if len(group_orders) <= 1:
                self._remove_oco_group(old_group)
        self._oco_order_to_group.pop(order_id, None)

    def _remove_oco_group(self, group_id: str) -> None:
        group_orders = self._oco_groups.pop(group_id, set())
        for oid in group_orders:
            self._oco_order_to_group.pop(oid, None)

    def buy(
        self,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        trigger_price: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> str:
        """
        买入下单.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
            quantity: 数量 (如果不填, 使用 Sizer 计算)
            price: 限价 (None 为市价)
            time_in_force: 订单有效期
            trigger_price: 触发价 (止损/止盈)
            tag: 订单标签

        Returns:
            str: 订单 ID
        """
        return _buy_impl(
            self, symbol, quantity, price, time_in_force, trigger_price, tag
        )

    def sell(
        self,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        trigger_price: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> str:
        """
        卖出下单.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
            quantity: 数量 (如果不填, 默认卖出当前标的所有持仓)
            price: 限价 (None 为市价)
            time_in_force: 订单有效期
            trigger_price: 触发价 (止损/止盈)
            tag: 订单标签

        Returns:
            str: 订单 ID
        """
        return _sell_impl(
            self, symbol, quantity, price, time_in_force, trigger_price, tag
        )

    def submit_order(
        self,
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
    ) -> str:
        """
        统一下单接口.

        该接口在回测与实盘模式均可调用，实盘模式下会由 LiveRunner 注入增强能力。
        """
        return _submit_order_impl(
            self,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            trigger_price=trigger_price,
            tag=tag,
            client_order_id=client_order_id,
            order_type=order_type,
            extra=extra,
            broker_options=broker_options,
            trail_offset=trail_offset,
            trail_reference_price=trail_reference_price,
        )

    def can_submit_client_order(self, client_order_id: str) -> bool:
        """
        检查 client_order_id 是否可再次提交.

        该方法在 LiveRunner 的 broker_live 模式下会被注入真实实现。
        """
        _ = client_order_id
        return True

    def get_execution_capabilities(self) -> Dict[str, Any]:
        """获取当前执行能力描述."""
        return _get_execution_capabilities_impl(self)

    def stop_buy(
        self,
        symbol: Optional[str] = None,
        trigger_price: float = 0.0,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
    ) -> None:
        """
        发送止损买入单 (Stop Buy Order).

        当市价上涨突破 trigger_price 时触发买入.
        - 如果 price 为 None, 触发后转为市价单 (Stop Market).
        - 如果 price 不为 None, 触发后转为限价单 (Stop Limit).
        """
        _stop_buy_impl(self, symbol, trigger_price, quantity, price, time_in_force)

    def stop_sell(
        self,
        symbol: Optional[str] = None,
        trigger_price: float = 0.0,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
    ) -> None:
        """
        发送止损卖出单 (Stop Sell Order).

        当市价下跌跌破 trigger_price 时触发卖出.
        - 如果 price 为 None, 触发后转为市价单 (Stop Market).
        - 如果 price 不为 None, 触发后转为限价单 (Stop Limit).
        """
        _stop_sell_impl(self, symbol, trigger_price, quantity, price, time_in_force)

    def place_trailing_stop(
        self,
        symbol: str,
        quantity: float,
        trail_offset: float,
        side: str = "Sell",
        trail_reference_price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        tag: Optional[str] = None,
    ) -> str:
        """创建跟踪止损单 (StopTrail)."""
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if trail_offset <= 0:
            raise ValueError("trail_offset must be > 0")
        return self.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            time_in_force=time_in_force,
            tag=tag,
            order_type="StopTrail",
            trail_offset=trail_offset,
            trail_reference_price=trail_reference_price,
        )

    def place_trailing_stop_limit(
        self,
        symbol: str,
        quantity: float,
        price: float,
        trail_offset: float,
        side: str = "Sell",
        trail_reference_price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        tag: Optional[str] = None,
    ) -> str:
        """创建跟踪止损限价单 (StopTrailLimit)."""
        if quantity <= 0:
            raise ValueError("quantity must be > 0")
        if price <= 0:
            raise ValueError("price must be > 0")
        if trail_offset <= 0:
            raise ValueError("trail_offset must be > 0")
        return self.submit_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            tag=tag,
            order_type="StopTrailLimit",
            trail_offset=trail_offset,
            trail_reference_price=trail_reference_price,
        )

    def get_portfolio_value(self) -> float:
        """计算当前投资组合总价值 (现金 + 持仓市值)."""
        return _get_portfolio_value_impl(self)

    @property
    def equity(self) -> float:
        """
        获取当前账户总权益 (现金 + 持仓市值).

        等同于 get_portfolio_value().
        """
        return self.get_portfolio_value()

    def order_target(
        self,
        target: float,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        调整仓位到目标数量.

        :param target: 目标持仓数量 (例如 100, -100)
        :param symbol: 标的代码
        :param price: 限价 (可选)
        :param kwargs: 其他下单参数
        """
        _order_target_impl(self, target, symbol, price, **kwargs)

    def _calculate_max_buy_qty(self, symbol: str, price: float, cash: float) -> float:
        """
        计算考虑费率后的最大可买数量.

        :param symbol: 标的代码
        :param price: 交易价格
        :param cash: 可用资金
        :return: 最大可买数量
        """
        return _calculate_max_buy_qty_impl(self, symbol, price, cash)

    def order_target_value(
        self,
        target_value: float,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        调整仓位到目标价值.

        :param target_value: 目标持仓价值
        :param symbol: 标的代码
        :param price: 限价 (可选)
        :param kwargs: 其他下单参数
        """
        _order_target_value_impl(self, target_value, symbol, price, **kwargs)

    def order_target_percent(
        self,
        target_percent: float,
        symbol: Optional[str] = None,
        price: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        调整仓位到目标百分比.

        :param target_percent: 目标持仓比例 (0.5 = 50%)
        :param symbol: 标的代码
        :param price: 限价 (可选)
        :param kwargs: 其他下单参数
        """
        _order_target_percent_impl(self, target_percent, symbol, price, **kwargs)

    def order_target_weights(
        self,
        target_weights: Dict[str, float],
        price_map: Optional[Dict[str, float]] = None,
        liquidate_unmentioned: bool = False,
        allow_leverage: bool = False,
        rebalance_tolerance: float = 0.0,
        **kwargs: Any,
    ) -> None:
        """
        按多标的目标权重调仓.

        :param target_weights: 目标权重字典 {symbol: weight}
        :param price_map: 每个标的的委托价格字典（可选）
        :param liquidate_unmentioned: 是否清仓未出现在目标权重中的现有持仓
        :param allow_leverage: 是否允许目标权重和超过 1.0
        :param rebalance_tolerance: 调仓容忍阈值（按组合市值比例）
        :param kwargs: 其他下单参数
        """
        _order_target_weights_impl(
            self,
            target_weights,
            price_map,
            liquidate_unmentioned,
            allow_leverage,
            rebalance_tolerance,
            **kwargs,
        )

    def buy_all(self, symbol: Optional[str] = None) -> None:
        """
        全仓买入 (Buy All).

        使用当前所有可用资金买入.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
        """
        _buy_all_impl(self, symbol)

    def close_position(self, symbol: Optional[str] = None) -> None:
        """
        平仓 (Close Position).

        卖出/买入以抵消当前持仓.

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
        """
        _close_position_impl(self, symbol)

    def short(
        self,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        trigger_price: Optional[float] = None,
    ) -> None:
        """
        卖出开空 (Short Sell).

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
            quantity: 数量 (如果不填, 使用 Sizer 计算)
            price: 限价 (None 为市价)
            time_in_force: 订单有效期
            trigger_price: 触发价 (止损/止盈)
        """
        _short_impl(self, symbol, quantity, price, time_in_force, trigger_price)

    def cover(
        self,
        symbol: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        time_in_force: Optional[TimeInForce] = None,
        trigger_price: Optional[float] = None,
    ) -> None:
        """
        买入平空 (Buy to Cover).

        Args:
            symbol: 标的代码 (如果不填, 默认使用当前 Bar/Tick 的 symbol)
            quantity: 数量 (如果不填, 默认平掉当前标的所有空头持仓)
            price: 限价 (None 为市价)
            time_in_force: 订单有效期
            trigger_price: 触发价 (止损/止盈)
        """
        _cover_impl(self, symbol, quantity, price, time_in_force, trigger_price)

    def get_cash(self) -> float:
        """获取现金."""
        return _get_cash_impl(self)


class VectorizedStrategy(Strategy):
    """
    向量化策略基类 (Vectorized Strategy Base Class).

    支持预计算指标的高速回测模式.
    用户应在回测前使用 Pandas/Numpy 计算好所有指标,
    然后通过本类提供的高速游标访问机制在 on_bar 中读取.
    """

    def __init__(self, precalculated_data: Dict[str, Dict[str, np.ndarray]]) -> None:
        """
        Initialize VectorizedStrategy.

        :param precalculated_data: 预计算数据字典
                                  Structure: {symbol: {indicator_name: numpy_array}}
        """
        super().__init__()
        self.precalc = precalculated_data
        # 游标管理: {symbol: index}
        self.cursors: defaultdict[str, int] = defaultdict(int)

        # 默认禁用 Python 侧历史数据缓存以提升性能
        self.set_history_depth(0)

    def _on_bar_event(self, bar: Bar, ctx: StrategyContext) -> None:
        """Wrap the user on_bar handler internally."""
        super()._on_bar_event(bar, ctx)
        self.cursors[bar.symbol] += 1

    def get_value(self, name: str, symbol: Optional[str] = None) -> float:
        """
        获取当前 Bar 对应的预计算指标值.

        Args:
            name: 指标名称
            symbol: 标的代码 (如果不填, 默认使用当前 Bar 的 symbol)

        Returns:
            指标值 (float). 如果不存在或越界，返回 nan.
        """
        symbol = self._resolve_symbol(symbol)
        idx = self.cursors[symbol]

        try:
            return float(self.precalc[symbol][name][idx])
        except (KeyError, IndexError):
            return float("nan")
