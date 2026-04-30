# AKQuant 功能手册

> 版本：0.2.8 | 架构：Rust 核心 (PyO3/maturin) + Python 编排层 | Python >= 3.10

AKQuant 是一个高性能量化交易框架，以 **纯库** 形式提供（无 CLI 命令），所有功能通过 Python API 调用。本文档按类别完整列出所有用户可用的功能接口。

---

## 目录

- [1. Rust 暴露类型 (PyO3)](#1-rust-暴露类型-pyo3)
- [2. 策略开发 (Strategy 基类)](#2-策略开发-strategy-基类)
- [3. 回测引擎](#3-回测引擎)
- [4. 参数优化](#4-参数优化)
- [5. 实盘/模拟交易 (LiveRunner)](#5-实盘模拟交易-liverunner)
- [6. 券商网关 (Gateway)](#6-券商网关-gateway)
- [7. 多策略 Slot 系统](#7-多策略-slot-系统)
- [8. 风控系统 (RiskConfig)](#8-风控系统-riskconfig)
- [9. 数据适配器](#9-数据适配器)
- [10. 因子/指标系统](#10-因子指标系统)
- [11. 配置系统](#11-配置系统)
- [12. 参数 DSL](#12-参数-dsl)
- [13. 仓位管理 (Sizer)](#13-仓位管理-sizer)
- [14. 检查点与热恢复](#14-检查点与热恢复)
- [15. 绘图与可视化](#15-绘图与可视化)
- [16. 分析器插件系统](#16-分析器插件系统)
- [17. ML 集成](#17-ml-集成)
- [18. 工具函数](#18-工具函数)
- [19. TA-Lib 封装](#19-ta-lib-封装)

---

## 1. Rust 暴露类型 (PyO3)

通过 PyO3 从 Rust 核心直接暴露给 Python 的高性能类型，在 `src/lib.rs` 中注册。

### 数据类型

| 类 | 说明 |
|----|------|
| `Bar` | OHLCV K 线数据 |
| `Tick` | Tick 级价格数据 |
| `DataFeed` | 行情数据容器 |
| `BarAggregator` | Tick 聚合为 Bar |
| `from_arrays()` | 从 numpy 数组创建 Bar |

### 订单与成交类型

| 类 | 说明 |
|----|------|
| `Order` | 订单对象 |
| `Trade` | 成交对象 |
| `OrderType` | 订单类型枚举 |
| `OrderRole` | 订单角色枚举 |
| `OrderSide` | 买/卖方向枚举 |
| `OrderStatus` | 订单生命周期枚举 |
| `TimeInForce` | 订单有效期枚举 |

### 合约类型

| 类 | 说明 |
|----|------|
| `AssetType` | 资产类型：STOCK / FUTURES / FUND / OPTION |
| `OptionType` | 期权方向：CALL / PUT |
| `SettlementType` | 交割方式：CASH / SETTLEMENT_PRICE / FORCE_CLOSE |
| `Instrument` | 合约规格定义 |
| `CorporateAction` | 公司行为事件 |
| `CorporateActionType` | 公司行为类型枚举 |
| `TradingSession` | 交易时段定义 |

### 引擎与上下文

| 类 | 说明 |
|----|------|
| `Engine` | 核心回撮合引擎 |
| `StrategyContext` | 策略运行时上下文 |

### 组合与分析

| 类 | 说明 |
|----|------|
| `Portfolio` | 组合状态追踪器 |
| `PerformanceMetrics` | 绩效指标计算 |
| `BacktestResult` | 回测结果容器 |
| `TradePnL` | 逐笔盈亏 |
| `ClosedTrade` | 已平仓交易记录 |
| `LiquidationAudit` | 强平审计记录 |

### 风控

| 类 | 说明 |
|----|------|
| `RiskManager` | 风控检查引擎 |
| `RiskConfig` | 风控配置 |

### 指标

通过 `indicators::register_py_classes(m)` 动态注册的 Rust 原生技术指标实现。

---

## 2. 策略开发 (Strategy 基类)

文件：`python/akquant/strategy.py`

### 2.1 生命周期钩子

```python
class Strategy:
    def on_start(self) -> None: ...
    def on_resume(self) -> None: ...                           # 热恢复回调
    def on_stop(self) -> None: ...
    def on_bar(self, bar: Bar) -> None: ...                    # K 线事件（主入口）
    def on_tick(self, tick: Tick) -> None: ...                 # Tick 事件
    def on_timer(self, payload: str) -> None: ...              # 定时器事件
    def on_order(self, order: Any) -> None: ...                # 订单状态更新
    def on_trade(self, trade: Any) -> None: ...                # 成交回调
    def on_session_start(self, session: Any, timestamp: int) -> None: ...
    def on_session_end(self, session: Any, timestamp: int) -> None: ...
    def before_trading(self, trading_date: dt.date, timestamp: int) -> None: ...
    def on_daily_rebalance(self, trading_date: dt.date, timestamp: int) -> None: ...
    def after_trading(self, trading_date: dt.date, timestamp: int) -> None: ...
    def on_reject(self, order: Any) -> None: ...               # 订单拒绝回调
    def on_portfolio_update(self, snapshot: Dict[str, Any]) -> None: ...
    def on_error(self, error: Exception, source: str, payload: Any = None) -> None: ...
    def prepare_features(self, df: pd.DataFrame, mode: str = "training") -> Tuple[Any, Any]: ...
    def on_train_signal(self, context: Any) -> None: ...       # ML 训练信号
```

### 2.2 下单 API

#### 基础下单

```python
buy(self, symbol=None, quantity=None, price=None, time_in_force=None,
    trigger_price=None, tag=None, fill_policy=None, slippage=None,
    commission=None) -> str                       # 返回 order_id

sell(self, symbol=None, quantity=None, price=None, time_in_force=None,
     trigger_price=None, tag=None, fill_policy=None, slippage=None,
     commission=None) -> str                      # 返回 order_id

short(self, symbol=None, quantity=None, price=None, time_in_force=None,
      trigger_price=None) -> None

cover(self, symbol=None, quantity=None, price=None, time_in_force=None,
      trigger_price=None) -> None
```

#### 便捷下单

```python
buy_all(self, symbol=None) -> None                # 全仓买入
close_position(self, symbol=None) -> None         # 平仓
```

#### 条件单

```python
stop_buy(self, symbol=None, trigger_price=0.0, quantity=None,
         price=None, time_in_force=None) -> None

stop_sell(self, symbol=None, trigger_price=0.0, quantity=None,
          price=None, time_in_force=None) -> None

place_trailing_stop(self, symbol, quantity, trail_offset, side="Sell",
                    trail_reference_price=None, time_in_force=None,
                    tag=None) -> str

place_trailing_stop_limit(self, symbol, quantity, price, trail_offset,
                          side="Sell", trail_reference_price=None,
                          time_in_force=None, tag=None) -> str

place_bracket_order(self, symbol, quantity, entry_price=None,
                    stop_trigger_price=None, take_profit_price=None,
                    time_in_force=None, entry_tag=None, stop_tag=None,
                    take_profit_tag=None) -> str
```

#### 通用下单

```python
submit_order(self, symbol=None, side="Buy", quantity=None, price=None,
             time_in_force=None, trigger_price=None, tag=None,
             client_order_id=None, order_type=None, extra=None,
             broker_options=None, trail_offset=None,
             trail_reference_price=None, fill_policy=None,
             slippage=None, commission=None) -> str
```

### 2.3 目标仓位 API

```python
order_target(self, target: float, symbol=None, price=None, **kwargs) -> None
order_target_value(self, target_value: float, symbol=None, price=None, **kwargs) -> None
order_target_percent(self, target_percent: float, symbol=None, price=None, **kwargs) -> None
order_target_weights(self, target_weights: Dict[str, float], price_map=None,
                     liquidate_unmentioned=False, allow_leverage=False,
                     rebalance_tolerance=0.0, **kwargs) -> None
rebalance_to_topn(self, scores: Dict[str, float], top_n: int, *,
                  weight_mode="equal", long_only=True, min_score=None,
                  liquidate_unmentioned=True, allow_leverage=False,
                  rebalance_tolerance=0.0, **kwargs) -> List[str]
```

### 2.4 订单管理

```python
cancel_order(self, order_id: str) -> None
cancel_all_orders(self, symbol=None) -> None
create_oco_order_group(self, first_order_id: str, second_order_id: str,
                       group_id=None) -> str
can_submit_client_order(self, client_order_id: str) -> bool
```

### 2.5 组合与持仓查询

```python
get_position(self, symbol=None) -> float
get_available_position(self, symbol=None) -> float
get_positions(self) -> Dict[str, float]
get_portfolio_value(self) -> float
get_cash(self) -> float
get_account(self) -> Dict[str, Any]
# get_account() 返回: cash, equity, market_value, frozen_cash, margin,
#               borrowed_cash, short_market_value, maintenance_ratio,
#               account_mode, accrued_interest, daily_interest
get_trades(self) -> List[Any]
get_open_orders(self, symbol=None) -> List[Any]
get_order(self, order_id: str) -> Optional[Any]
get_execution_capabilities(self) -> Dict[str, Any]
hold_bar(self, symbol=None) -> int            # 当前持仓持续 Bar 数
```

### 2.6 合约查询

```python
get_instrument(self, symbol: str) -> InstrumentSnapshot
get_instruments(self, symbols=None) -> Dict[str, InstrumentSnapshot]
get_instrument_field(self, symbol: str, field: str) -> Any
get_instrument_config(self, symbol: str, fields=None) -> Union[Any, Dict, InstrumentSnapshot]
subscribe(self, instrument_id: str) -> None
```

### 2.7 历史数据访问

```python
set_history_depth(self, depth: int) -> None
get_history(self, count: int, symbol=None, field="close") -> np.ndarray
get_history_df(self, count: int, symbol=None) -> pd.DataFrame
get_history_map(self, count: int, symbols, field="close") -> Dict[str, np.ndarray]
set_rolling_window(self, train_window: int, step: int) -> None
get_rolling_data(self, length=None, symbol=None) -> tuple[pd.DataFrame, Optional[pd.Series]]
```

### 2.8 指标注册

```python
register_indicator(self, name: str, indicator: Indicator) -> None
register_precomputed_indicator(self, name: str, indicator: Indicator) -> None
register_incremental_indicator(self, name: str, indicator: Any, source="close",
                               symbols=None) -> None
```

### 2.9 调度与时间

```python
schedule(self, trigger_time: Union[str, dt.datetime, pd.Timestamp], payload: str) -> None
add_daily_timer(self, time_str: str, payload: str) -> None
to_local_time(self, timestamp: int) -> pd.Timestamp
format_time(self, timestamp: int, fmt="%Y-%m-%d %H:%M:%S") -> str
set_sizer(self, sizer: Sizer) -> None
log(self, msg: str, level=logging.INFO) -> None
```

### 2.10 ML 集成

```python
is_model_ready(self) -> bool
current_validation_window(self) -> Optional[Dict[str, Any]]
_auto_configure_model(self) -> None
```

### 2.11 属性访问

```python
strategy.symbol    -> str                  # 当前 Bar/Tick 标的
strategy.close     -> float                # 最新收盘/最新价
strategy.open      -> float                # 当前 Bar 开盘价
strategy.high      -> float                # 当前 Bar 最高价
strategy.low       -> float                # 当前 Bar 最低价
strategy.volume    -> float                # 当前 Bar/Tick 成交量
strategy.now       -> Optional[pd.Timestamp]  # 当前回测时间
strategy.position  -> Position             # 当前标持仓对象
strategy.equity    -> float                # 组合权益
strategy.is_restored -> bool               # 热恢复标志
strategy.runtime_config -> StrategyRuntimeConfig  # 运行时配置
```

### 2.12 向量化策略

```python
class VectorizedStrategy(Strategy):
    def __init__(self, precalculated_data: Dict[str, Dict[str, np.ndarray]]) -> None
    def get_value(self, name: str, symbol=None) -> float  # 基于游标的数据访问
```

### 2.13 数据类

```python
@dataclass
class StrategyRuntimeConfig:
    enable_precise_day_boundary_hooks: bool = False
    portfolio_update_eps: float = 0.0
    error_mode: Literal["raise", "continue", "legacy"] = "raise"
    re_raise_on_error: bool = True
    indicator_mode: Literal["incremental", "precompute"] = "precompute"

@dataclass(frozen=True)
class InstrumentSnapshot:
    symbol: str
    asset_type: InstrumentAssetTypeName
    multiplier: float
    margin_ratio: float
    tick_size: float
    lot_size: float
    option_type: Optional[InstrumentOptionTypeName]
    strike_price: Optional[float]
    expiry_date: Optional[int]
    underlying_symbol: Optional[str]
    settlement_type: Optional[InstrumentSettlementMode]
    settlement_price: Optional[float]
    static_attrs: Dict[str, InstrumentStaticValue]
```

---

## 3. 回测引擎

文件：`python/akquant/backtest/engine.py`

### 3.1 入口函数

#### `run_backtest()`

```python
def run_backtest(
    data,                                          # 行情数据 (DataFrame/dict/catalog)
    strategy=None,                                 # 策略类或实例
    symbols=None,                                  # 标的列表
    initial_cash=1_000_000.0,
    commission_rate=0.0,
    stamp_tax_rate=0.0,
    transfer_fee_rate=0.0,
    min_commission=0.0,
    slippage=0.0,
    volume_limit_pct=0.0,
    timezone="Asia/Shanghai",
    t_plus_one=True,
    initialize=None,                               # 回调: fn(strategy)
    on_start=None,                                 # 回调
    on_stop=None,                                  # 回调
    on_tick=None,                                  # 回调
    on_order=None,                                 # 回调
    on_trade=None,                                 # 回调
    on_timer=None,                                 # 回调
    context=None,                                  # 外部上下文
    history_depth=0,
    warmup_period=0,
    lot_size=1,
    show_progress=True,
    start_time=None,
    end_time=None,
    catalog_path=None,
    config: Optional[BacktestConfig] = None,       # 统一配置
    custom_matchers=None,
    risk_config=None,
    strategy_runtime_config=None,
    runtime_config_override=None,
    strategy_id=None,                              # 多策略 Slot ID
    strategies_by_slot=None,                       # Dict[str, Strategy] 多策略
    strategy_max_position_size=None,               # 按策略净持仓限制
    strategy_max_order_size=None,                  # 按策略单笔限制
    strategy_max_order_value=None,                 # 按策略单笔市值限制
    strategy_max_daily_loss=None,                  # 按策略日损限制
    strategy_max_drawdown=None,                    # 按策略回撤限制
    strategy_reduce_only_after_risk=None,          # 按策略风险后仅平仓
    strategy_risk_cooldown_bars=None,              # 按策略风险冷却 Bar 数
    strategy_priority=None,                        # 按策略优先级
    strategy_risk_budget=None,                     # 按策略累计风险预算
    portfolio_risk_budget=None,                    # 组合级风控预算
    risk_budget_mode="order_notional",             # "order_notional" | "trade_notional"
    analyzer_plugins=None,                         # List[AnalyzerPlugin]
    on_event=None,                                 # 通用事件回调
    broker_profile=None,                           # 预设券商配置
    fill_policy=None,                              # FillPolicy 或 make_fill_policy()
    strict_strategy_params=False,
    **kwargs,
) -> BacktestResult
```

#### `run_warm_start()`

```python
def run_warm_start(
    checkpoint_path: str,                          # 快照文件路径
    data,                                          # 接续行情数据
    show_progress=True,
    symbols=None,
    strategy_runtime_config=None,
    # ... 其余参数同 run_backtest()
) -> BacktestResult
```

### 3.2 成交策略

```python
def make_fill_policy(
    price_basis: str = "close",        # "open", "close", "vwap", "high", "low", "next_open"
    temporal: str = "current_bar",      # "current_bar", "next_bar"
    bar_offset: int = 0,               # 执行偏移 Bar 数
) -> FillPolicy
```

**组合示例：**

| price_basis | temporal | 含义 |
|-------------|----------|------|
| `close` | `current_bar` | 当前 Bar 收盘价成交（默认） |
| `open` | `next_bar` | 下一 Bar 开盘价成交 |
| `vwap` | `current_bar` | 当前 Bar VWAP 成交 |

### 3.3 预设券商配置

| 配置名 | 说明 |
|--------|------|
| `cn_stock_miniqmt` | 对齐 MiniQMT 基础口径的 A 股仿真配置 |
| `cn_stock_t1_low_fee` | T+1 低费率股票配置 |
| `cn_stock_sim_high_slippage` | 高滑点模拟配置 |

### 3.4 回测结果分析

文件：`python/akquant/backtest/result.py`

#### 权益与收益曲线

```python
backtest_result.equity_curve          -> pd.Series       # 逐 Bar 权益
backtest_result.equity_curve_daily    -> pd.Series       # 日权益
backtest_result.cash_curve            -> pd.Series       # 逐 Bar 现金
backtest_result.cash_curve_daily      -> pd.Series       # 日现金
backtest_result.margin_curve          -> pd.Series       # 逐 Bar 保证金
backtest_result.margin_curve_daily    -> pd.Series       # 日保证金
backtest_result.daily_returns         -> pd.Series       # 日收益率
```

#### DataFrame 数据

```python
backtest_result.trades_df             -> pd.DataFrame    # 全部成交
backtest_result.orders_df             -> pd.DataFrame    # 全部订单
backtest_result.executions_df         -> pd.DataFrame    # 执行明细
backtest_result.positions_df          -> pd.DataFrame    # 持仓快照
backtest_result.metrics_df            -> pd.DataFrame    # 绩效指标
backtest_result.liquidation_audit_df  -> pd.DataFrame    # 强平审计
```

#### 分析方法

```python
backtest_result.exposure_df(freq="D")                           -> pd.DataFrame  # 持仓暴露
backtest_result.attribution_df(by="symbol", use_net=True, top_n=20) -> pd.DataFrame  # 归因分析
backtest_result.capacity_df(freq="D")                           -> pd.DataFrame  # 容量分析
backtest_result.orders_by_strategy()                            -> pd.DataFrame  # 多策略订单
backtest_result.executions_by_strategy()                        -> pd.DataFrame  # 多策略执行
backtest_result.top_reject_reasons(top_n=10)                    -> pd.DataFrame  # 拒单原因 Top N
backtest_result.risk_rejections_by_strategy()                   -> pd.DataFrame  # 风控拒单统计
backtest_result.risk_rejections_trend(freq="D")                 -> pd.DataFrame  # 风控拒单趋势
backtest_result.risk_rejections_trend_by_strategy(freq="D")     -> pd.DataFrame  # 按策略风控趋势
backtest_result.get_event_stats()                               -> Dict[str, Any]  # 事件统计
```

#### 报告与绘图

```python
backtest_result.plot(**kwargs)                         # 交互式图表
backtest_result.report()                               # 文本绩效报告
backtest_result.to_quantstats()                        # QuantStats 集成
backtest_result.report_quantstats(html_path=None)      # HTML QuantStats 报告
```

---

## 4. 参数优化

文件：`python/akquant/optimize.py`

### 4.1 网格搜索

```python
def run_grid_search(
    strategy,                                     # 策略类
    param_grid: Dict[str, List[Any]],             # 参数网格
    data,                                         # 行情数据
    max_workers=None,                             # 并行工作数
    sort_by: str = "sharpe_ratio",                # 排序指标
    ascending: bool = False,
    return_df: bool = True,                       # 返回 DataFrame 还是列表
    warmup_calc=None,
    constraint: Optional[Callable] = None,        # 筛选: fn(result) -> bool
    result_filter: Optional[Callable] = None,
    timeout=None,
    max_tasks_per_child=None,
    db_path=None,                                 # SQLite 结果持久化
    forward_worker_logs=False,
    **kwargs,
) -> Union[pd.DataFrame, List[OptimizationResult]]
```

### 4.2 滚动前向优化

```python
def run_walk_forward(
    strategy,
    param_grid: Dict[str, List[Any]],
    data,
    train_period: int,                            # 训练窗口 (Bar 数)
    test_period: int,                             # 测试窗口 (Bar 数)
    metric: str = "sharpe_ratio",
    ascending: bool = False,
    initial_cash=1_000_000.0,
    warmup_period=0,
    warmup_calc=None,
    constraint=None,
    result_filter=None,
    compounding=False,
    timeout=None,
    max_tasks_per_child=None,
    **kwargs,
) -> pd.DataFrame
```

### 4.3 优化结果

```python
@dataclass
class OptimizationResult:
    params: Dict[str, Any]          # 参数组合
    metrics: Dict[str, float]       # 绩效指标
    duration: float                 # 耗时（秒）
    error: Optional[str]            # 错误信息
```

---

## 5. 实盘/模拟交易 (LiveRunner)

文件：`python/akquant/live.py`

```python
class LiveRunner:
    def __init__(
        self,
        strategy_cls,                              # 策略类 / 实例 / 函数式 on_bar
        instruments: List[Instrument],             # 合约对象列表
        strategy_source=None,
        strategy_loader=None,
        strategy_loader_options=None,
        strategy_id=None,
        strategies_by_slot=None,
        md_front: str = "",
        td_front: Optional[str] = None,
        broker_id: str = "",
        user_id: str = "",
        password: str = "",
        app_id: str = "",
        auth_code: str = "",
        use_aggregator: bool = True,
        broker: str = "ctp",                       # "ctp" | "miniqmt" | "ptrade"
        trading_mode: str = "paper",               # "paper" | "broker_live"
        gateway_options: Optional[Dict] = None,
        initialize=None,
        on_start=None,
        on_stop=None,
        on_tick=None,
        on_order=None,
        on_trade=None,
        on_timer=None,
        context=None,
        strategy_max_order_value=None,
        strategy_max_order_size=None,
        strategy_max_position_size=None,
        strategy_max_daily_loss=None,
        strategy_max_drawdown=None,
        strategy_reduce_only_after_risk=None,
        strategy_risk_cooldown_bars=None,
        strategy_priority=None,
        strategy_risk_budget=None,
        portfolio_risk_budget=None,
        risk_budget_mode="order_notional",
        risk_budget_reset_daily=False,
        on_broker_event=None,                      # 券商事件回调
    )

    def run(self, cash: float = 1_000_000.0,
            show_progress: bool = False,
            duration=None) -> None                 # 启动实盘/模拟会话
```

**trading_mode 说明：**

| 模式 | 说明 |
|------|------|
| `paper` | 模拟交易（本地撮合） |
| `broker_live` | 实盘交易（走券商通道；当前内置主链路以 CTP 为主） |

---

## 6. 券商网关 (Gateway)

文件：`python/akquant/gateway/__init__.py`

### 6.1 支持的券商

| 券商 | 市场 | 工厂默认返回 | 当前状态 |
|------|------|-------------|----------|
| **CTP** | 期货 | `CTPMarketAdapter` + `CTPTraderAdapter` | 行情、下单、撤单、订单/成交回报主链路已实现 |
| **MiniQMT** | 股票 | `MiniQMTMarketGateway` + `MiniQMTTraderGateway` | 内存占位实现，未接真实 QMT |
| **PTrade** | 通用 | `PTradeMarketGateway` + `PTradeTraderGateway` | 内存占位实现，未接真实柜台 |

### 6.2 核心网关类型

```python
class MarketGateway: ...              # 行情接口（抽象）
class TraderGateway: ...              # 交易接口（抽象）
class GatewayBundle: ...              # 行情+交易组合
```

### 6.3 统一数据模型

```python
UnifiedOrderRequest        # 跨券商下单请求
UnifiedOrderSnapshot       # 订单状态快照
UnifiedTrade               # 成交回报
UnifiedAccount             # 账户状态
UnifiedPosition            # 持仓状态
UnifiedExecutionReport     # 执行报告
UnifiedOrderStatus         # 订单状态枚举
UnifiedErrorType           # 错误分类
```

### 6.4 网关注册与工厂

```python
def create_gateway_bundle(broker, feed, symbols, use_aggregator=False, **kwargs) -> GatewayBundle
def register_broker(name: str, builder: Callable) -> None
def unregister_broker(name: str) -> None
def get_broker_builder(name: str) -> Callable
def list_registered_brokers() -> List[str]
```

### 6.5 CTP 适配器

```python
CTPMarketAdapter           # factory 默认返回：CTP 行情 -> 统一格式
CTPTraderAdapter           # factory 默认返回：CTP 交易 -> 统一格式
CTPMarketGateway           # native SPI 行情实现
CTPTraderGateway           # native SPI 交易实现
```

### 6.6 当前实现边界

- `CTPTraderAdapter.query_account()` 当前返回 `None`。
- `CTPTraderAdapter.query_positions()` 当前返回空列表。
- `CTPTraderAdapter.sync_today_trades()` 当前返回空列表。
- `CTPTraderAdapter.sync_open_orders()` 当前只回放适配器内存中的未终态订单，不是向柜台重查。
- `MiniQMT` / `PTrade` 当前虽然实现了统一 `TraderGateway` 接口，但默认只维护进程内存里的订单、成交和账户占位数据。
- `MiniQMTMarketGateway` / `PTradeMarketGateway` 当前不会自动把实时行情写入 `DataFeed`。

### 6.7 事件映射

```python
class BrokerEventMapper: ...
def create_default_mapper() -> BrokerEventMapper
```

---

## 7. 多策略 Slot 系统

多个策略共享一个引擎，各自独立的仓位/风控/资金限制。

### 配置方式

```python
# 在 run_backtest() 中通过以下参数配置多策略：
strategies_by_slot: Dict[str, Strategy]     # Slot ID -> 策略实例
strategy_max_position_size: Dict[str, float] # 按策略净持仓数量上限
strategy_max_order_size: Dict[str, float]   # 按策略单笔数量上限
strategy_max_order_value: Dict[str, float]  # 按策略单笔市值上限
strategy_max_daily_loss: Dict[str, float]   # 按策略日损限制
strategy_max_drawdown: Dict[str, float]     # 按策略回撤限制
strategy_priority: Dict[str, int]           # 按策略执行优先级
strategy_risk_budget: Dict[str, float]      # 按策略累计风险预算
portfolio_risk_budget: float                # 组合级风控预算
risk_budget_mode: str                       # "order_notional" | "trade_notional"
```

### 风控预算模式

| 模式 | 说明 |
|------|------|
| `order_notional` | 按下单名义金额累计消耗策略/组合风险预算 |
| `trade_notional` | 按实际成交名义金额累计消耗策略/组合风险预算 |

### 结果分析

```python
backtest_result.orders_by_strategy()         # 按策略查看订单
backtest_result.executions_by_strategy()     # 按策略查看执行
backtest_result.risk_rejections_by_strategy()  # 按策略查看风控拒单
```

---

## 8. 风控系统 (RiskConfig)

文件：`python/akquant/config.py` + `python/akquant/risk.py`

### 8.1 RiskConfig 配置项

```python
@dataclass
class RiskConfig:
    # 开关
    active: Optional[bool] = None                    # 是否启用风控
    check_cash: Optional[bool] = None                # 是否检查资金

    # 静态限制
    max_order_size: Optional[float] = None           # 单笔最大数量
    max_order_value: Optional[float] = None          # 单笔最大市值
    max_position_size: Optional[float] = None        # 单标的最大持仓
    max_position_pct: Optional[float] = None         # 单标的最大持仓占比
    restricted_list: Optional[List[str]] = None      # 限制交易标的列表

    # 动态规则
    max_account_drawdown: Optional[float] = None     # 最大账户回撤
    max_daily_loss: Optional[float] = None           # 最大日亏损
    stop_loss_threshold: Optional[float] = None      # 止损阈值

    # 融资融券
    account_mode: Optional[str] = None               # "cash" | "margin"
    enable_short_sell: Optional[bool] = None         # 允许融券
    initial_margin_ratio: Optional[float] = None     # 初始保证金比率
    maintenance_margin_ratio: Optional[float] = None # 维持保证金比率
    financing_rate_annual: Optional[float] = None    # 融资年利率
    borrow_rate_annual: Optional[float] = None       # 融券年利率
    allow_force_liquidation: Optional[bool] = None   # 允许强平
    liquidation_priority: Optional[str] = None       # 强平优先级
    safety_margin: Optional[float] = None            # 安全边际

    # 行业集中度
    sector_concentration: Optional[Tuple] = None     # 行业集中度限制
```

### 8.2 风控应用

```python
from akquant.risk import apply_risk_config

# 将 Python RiskConfig 应用到 Rust RiskManager
apply_risk_config(engine, risk_config)
```

---

## 9. 数据适配器

文件：`python/akquant/feed_adapter.py`

### 9.1 适配器类

| 适配器 | 用途 |
|--------|------|
| `CSVFeedAdapter(path)` | 从 CSV 文件加载行情 |
| `ParquetFeedAdapter(path)` | 从 Parquet 文件加载行情 |
| `ResampledFeedAdapter(source_adapter, freq)` | 重采样（如 1min -> 5min） |
| `ReplayFeedAdapter(source_adapter, freq)` | 回放（Tick 级逐条模拟） |

### 9.2 链式调用

```python
from akquant.feed_adapter import ParquetFeedAdapter

# Parquet -> 重采样到5分钟 -> 回放为1分钟
adapter = ParquetFeedAdapter("data.parquet").resample("5min").replay("1min")
```

### 9.3 FeedSlice

```python
@dataclass
class FeedSlice:
    symbol: str
    data: pd.DataFrame
```

### 9.4 数据目录

文件：`python/akquant/data.py`

```python
class ParquetDataCatalog:
    def write(self, symbol: str, df: pd.DataFrame) -> None   # 写入
    def read(self, symbol: str) -> pd.DataFrame               # 读取
    def list_symbols(self) -> List[str]                       # 列出所有标的

class DataLoader:
    def load(self, source) -> Dict[str, pd.DataFrame]         # 加载（带缓存）
    def df_to_bars(self, df, symbol) -> List[Bar]             # DataFrame -> Bar 列表
```

---

## 10. 因子/指标系统

文件：`python/akquant/indicator.py`

### 10.1 指标框架

```python
class Indicator:
    def __init__(self, name: str, fn: Callable, **kwargs)
    def update(self, value: float) -> float           # 增量更新
    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series  # 批量预计算
    def get_value(self, symbol: str, timestamp) -> float

class IndicatorSet:
    def add(self, name: str, fn: Callable, **kwargs)  # 添加指标
    def get(self, name: str) -> Indicator              # 获取指标
    def calculate_all(self, df, symbol) -> Dict[str, pd.Series]  # 批量计算
```

### 10.2 双模式指标

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `precompute` | 批量 DataFrame 计算 | 回测、研究 |
| `incremental` | 逐 Bar 流式更新 | 实盘、大数量回测 |

通过 `StrategyRuntimeConfig.indicator_mode` 或策略注册时选择模式。

### 10.3 Rust 原生指标

内置高性能指标（SMA, EMA, RSI, MACD, Bollinger 等），通过 PyO3 直接暴露。

---

## 11. 配置系统

文件：`python/akquant/config.py`

### 11.1 BacktestConfig

```python
@dataclass
class BacktestConfig:
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    strategy_config: Optional[StrategyConfig] = None
    instruments: Optional[List[Dict]] = None
    instruments_config: Optional[List[InstrumentConfig]] = None
    china_futures: Optional[ChinaFuturesConfig] = None
    china_options: Optional[ChinaOptionsConfig] = None
    benchmark: Optional[str] = None
    timezone: str = "Asia/Shanghai"
    show_progress: bool = True
    history_depth: int = 0
    bootstrap_samples: int = 1000
```

### 11.2 StrategyConfig

```python
@dataclass
class StrategyConfig:
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0
    stamp_tax_rate: float = 0.0
    transfer_fee_rate: float = 0.0
    min_commission: float = 0.0
    slippage: float = 0.0
    volume_limit_pct: float = 0.0
    enable_fractional_shares: bool = False
    round_fill_price: bool = True
    exit_on_last_bar: bool = False
    indicator_mode: str = "precompute"
    max_long_positions: Optional[int] = None
    max_short_positions: Optional[int] = None
    risk: Optional[RiskConfig] = None
    # 多策略拓扑字段
    strategy_id: Optional[str] = None
    strategies_by_slot: Optional[Dict[str, Any]] = None
    strategy_max_position_size: Optional[Dict[str, float]] = None
    strategy_max_order_size: Optional[Dict[str, float]] = None
    strategy_max_order_value: Optional[Dict[str, float]] = None
    strategy_max_daily_loss: Optional[Dict[str, float]] = None
    strategy_max_drawdown: Optional[Dict[str, float]] = None
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None
    strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None
    strategy_priority: Optional[Dict[str, int]] = None
    strategy_risk_budget: Optional[Dict[str, float]] = None
    portfolio_risk_budget: Optional[float] = None
    risk_budget_mode: str = "order_notional"
```

### 11.3 InstrumentConfig

```python
@dataclass
class InstrumentConfig:
    symbol: str
    asset_type: str = "STOCK"
    multiplier: float = 1.0
    margin_ratio: float = 1.0
    tick_size: float = 0.01
    lot_size: float = 1.0
    commission_rate: Optional[float] = None
    option_type: Optional[str] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[int] = None
    settlement_type: Optional[str] = None
```

### 11.4 中国市场专用配置

```python
ChinaFuturesConfig                  # 期货时段/费率模板
ChinaFuturesFeeConfig               # 手续费/开平仓费结构
ChinaFuturesSessionConfig           # 交易时段定义
ChinaFuturesInstrumentTemplateConfig  # 合约模板
ChinaFuturesValidationConfig        # 手数/跳价验证
ChinaOptionsConfig                  # 期权时段/费率配置
ChinaOptionsFeeConfig               # 期权费结构
ChinaOptionsSessionConfig           # 期权交易时段
```

---

## 12. 参数 DSL

文件：`python/akquant/params.py`

### 12.1 参数定义

```python
from akquant.params import ParamModel, IntParam, FloatParam, BoolParam, ChoiceParam, DateRangeParam

class MyParams(ParamModel):
    fast_period: int = IntParam(10, ge=1, le=200, description="快线周期")
    slow_period: int = IntParam(30, ge=1, le=500, description="慢线周期")
    direction: str = ChoiceParam("long", choices=["long", "short", "both"])
    use_stop: bool = BoolParam(True)
    date_range: DateRange = DateRangeParam(description="回测区间")
```

### 12.2 工具函数

```python
def model_to_schema(model_cls: type[ParamModel]) -> dict          # 生成 JSON Schema
def validate_payload(model_cls, payload: Mapping) -> ParamModel   # 校验参数
def to_runtime_kwargs(model: ParamModel) -> dict                  # 自动展开 date_range -> start_time/end_time
```

### 12.3 参数适配器

文件：`python/akquant/params_adapter.py`

```python
def resolve_param_model(strategy) -> Optional[type[ParamModel]]
def get_strategy_param_schema(strategy) -> Optional[dict]
def validate_strategy_params(strategy, payload) -> Optional[ParamModel]
def extract_runtime_kwargs(strategy, payload) -> dict
def build_param_grid_from_search_space(model_cls, search_space: Dict) -> Dict[str, List]
```

---

## 13. 仓位管理 (Sizer)

文件：`python/akquant/sizer.py`

```python
class Sizer(ABC):
    def size(self, strategy, symbol, price, cash) -> float

class FixedSizer(Sizer):          # 别名 FixedSize
    def __init__(self, size: int = 100)

class PercentSizer(Sizer):
    def __init__(self, percents: float = 0.95)

class AllInSizer(Sizer):          # 使用全部可用资金
```

**使用方式：**

```python
strategy.set_sizer(PercentSizer(0.1))  # 每次使用 10% 资金
```

---

## 14. 检查点与热恢复

文件：`python/akquant/checkpoint.py`

```python
def save_snapshot(engine, strategy, filepath: str) -> None       # 保存快照
def warm_start(filepath: str, data_feed) -> Tuple[Engine, Strategy]  # 恢复快照
```

**使用流程：**

1. 在回测或实盘中调用 `save_snapshot()` 保存当前状态
2. 使用 `run_warm_start()` 或 `warm_start()` 恢复
3. 策略的 `on_resume()` 钩子被调用，`is_restored` 为 `True`

---

## 15. 绘图与可视化

文件：`python/akquant/plot/__init__.py`

```python
from akquant.plot import (
    plot_dashboard,                # 完整权益/回撤仪表盘
    plot_strategy,                 # 策略概览
    plot_trades_distribution,      # 交易盈亏分布
    plot_pnl_vs_duration,          # 盈亏 vs 持仓时间
    plot_report,                   # 综合报告
    plot_result,                   # plot_dashboard 别名
)

# 使用方式
result = run_backtest(...)
result.plot()                       # 等同于 plot_dashboard(result)
result.report()                     # 文本报告
result.report_quantstats()          # HTML 量化报告
```

**基于 Plotly** 的交互式图表，支持导出 HTML。

---

## 16. 分析器插件系统

文件：`python/akquant/analyzer_plugin.py`

```python
class AnalyzerPlugin(Protocol):
    def on_start(self, context: dict) -> None: ...
    def on_bar(self, bar, context: dict) -> None: ...
    def on_trade(self, trade, context: dict) -> None: ...
    def on_finish(self, result, context: dict) -> None: ...

class AnalyzerManager:
    def register(self, plugin: AnalyzerPlugin) -> None
```

**使用方式：**

```python
class MyPlugin:
    def on_bar(self, bar, context):
        # 自定义逐 Bar 分析逻辑
        ...

run_backtest(data, strategy, analyzer_plugins=[MyPlugin()])
```

---

## 17. ML 集成

文件：`python/akquant/ml/model.py`

```python
class QuantModel:
    # ML 模型包装器，用于策略集成
    # 支持滚动前向验证生命周期
    # Active/pending 模型切换
```

**策略端集成：**

```python
class MyStrategy(Strategy):
    def prepare_features(self, df, mode="training"):
        # 特征工程
        ...
    def on_train_signal(self, context):
        # 训练信号触发
        ...
```

---

## 18. 工具函数

文件：`python/akquant/utils/__init__.py`

```python
def fetch_akshare_symbol(symbol: str) -> pd.DataFrame  # 从 AKShare 获取行情
def format_metric_value(key: str, value) -> str         # 格式化指标显示
def load_bar_from_df(df, symbol) -> List[Bar]           # DataFrame -> Bar 列表
def prepare_dataframe(df) -> pd.DataFrame               # 标准化列名
```

**日志：**

文件：`python/akquant/log.py`

```python
def get_logger() -> logging.Logger
def register_logger(logger: logging.Logger) -> None
```

**策略加载器：**

文件：`python/akquant/strategy_loader.py`

```python
def register_strategy_loader(loader: Callable) -> None
def resolve_strategy_input(strategy_input) -> Any     # 解析类/路径/实例
```

---

## 19. TA-Lib 封装

文件：`python/akquant/talib/__init__.py`

完整 TA-Lib 函数绑定（~115K 行），封装 TA-Lib C 库的技术分析函数。

**涵盖的指标类别：**

| 类别 | 示例指标 |
|------|---------|
| 趋势指标 | SMA, EMA, MACD, SAR, ADX |
| 动量指标 | RSI, Stochastic, CCI, Williams %R |
| 波动率指标 | Bollinger Bands, ATR, Standard Deviation |
| 成交量指标 | OBV, MFI, Chaikin A/D |
| 周期指标 | Hilbert Transform, EPA, EPHC |
| 价格指标 | Typical Price, Weighted Close |
| 统计指标 | Beta, Correlation, Linear Regression |

**使用方式：**

```python
from akquant.talib import SMA, EMA, RSI, MACD, BBANDS

# 在策略中使用
sma = SMA(close_prices, timeperiod=20)
```

---

## 附录：核心架构模式

| 模式 | 说明 |
|------|------|
| **双模式指标** | `precompute`（批量 DataFrame）/ `incremental`（逐 Bar 流式） |
| **多策略 Slot** | 多策略共享引擎，独立仓位/风控/预算 |
| **Fill Policy 抽象** | `price_basis` x `temporal` x `bar_offset` 覆盖常见回测成交模型 |
| **Gateway 抽象** | 统一 `GatewayBundle` + 券商适配器/占位网关（CTP/MiniQMT/PTrade） |
| **热恢复** | Pickle 快照 + `on_resume()` 生命周期钩子 |
| **参数 DSL** | Pydantic 模型 + 自动 JSON Schema + 网格搜索集成 |
| **Pipeline 架构** | Rust 引擎通过固定 Processor 链处理每根 Bar |
| **Market Model** | `MarketModel` trait 抽象市场规则（T+1、涨跌停、交易时段） |
