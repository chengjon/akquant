# API 参考

本 API 文档涵盖了 AKQuant 的核心类和方法。

快速跳转：

*   [LiveRunner broker_live 执行语义](#live-broker-semantics)

## 1. 高级入口 (High-Level API)

### `akquant.run_backtest`

最常用的回测入口函数，封装了引擎的初始化和配置过程。

```python
def run_backtest(
    data: Optional[Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar]]] = None,
    strategy: Union[Type[Strategy], Strategy, Callable[[Any, Bar], None], None] = None,
    symbol: Union[str, List[str]] = "BENCHMARK",
    symbols: Optional[Union[str, List[str]]] = None,
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
    context: Optional[Dict[str, Any]] = None,
    history_depth: Optional[int] = None,
    warmup_period: int = 0,
    lot_size: Union[int, Dict[str, int], None] = None,
    show_progress: Optional[bool] = None,
    start_time: Optional[Union[str, Any]] = None,
    end_time: Optional[Union[str, Any]] = None,
    config: Optional[BacktestConfig] = None,
    instruments_config: Optional[Union[List[InstrumentConfig], Dict[str, InstrumentConfig]]] = None,
    custom_matchers: Optional[Dict[AssetType, Any]] = None,
    risk_config: Optional[Union[Dict[str, Any], RiskConfig]] = None,
    strategies_by_slot: Optional[Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]] = None,
    on_event: Optional[Callable[[BacktestStreamEvent], None]] = None,
    broker_profile: Optional[str] = None,
    timer_execution_policy: Literal["same_cycle", "next_event"] = "same_cycle",
    fill_policy: Optional[Dict[str, str]] = None,
    strict_strategy_params: bool = True,
    **kwargs: Any,
) -> BacktestResult
```

### `akquant.run_grid_search`

参数网格搜索入口，用于批量回测并按指标排序返回最优参数组合。

```python
def run_grid_search(
    strategy: Type[Strategy],
    param_grid: Dict[str, Sequence[Any]],
    data: Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar]],
    sort_by: Union[str, List[str]] = "sharpe_ratio",
    ascending: Union[bool, List[bool]] = False,
    return_df: bool = True,
    result_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    constraint: Optional[Callable[[Dict[str, Any]], bool]] = None,
    max_workers: Optional[int] = None,
    show_progress: bool = True,
    timeout: Optional[float] = None,
    max_tasks_per_child: Optional[int] = None,
    db_path: Optional[str] = None,
    forward_worker_logs: bool = False,
    **kwargs: Any,
) -> Union[pd.DataFrame, List[OptimizationResult]]
```

**关键参数补充:**

*   `forward_worker_logs`: 并行优化时是否将子进程策略日志回传到主进程。
    *   `False`：吞吐优先，日志可能在主进程不可见。
    *   `True`：启用日志聚合，便于排障。
*   `strict_strategy_params`: 通过 `**kwargs` 传递给 `run_backtest`（默认在 `run_grid_search` 内为 `True`）。
    *   严格校验 `param_grid` 与策略构造参数匹配关系；
    *   参数不匹配时快速失败，避免静默回退。

### `akquant.run_walk_forward`

滚动优化入口。按窗口执行“样本内参数优化 + 样本外验证”，并拼接样本外资金曲线。

```python
def run_walk_forward(
    strategy: Type[Strategy],
    param_grid: Mapping[str, Sequence[Any]],
    data: pd.DataFrame,
    train_period: int,
    test_period: int,
    metric: Union[str, List[str]] = "sharpe_ratio",
    ascending: Union[bool, List[bool]] = False,
    initial_cash: float = 100_000.0,
    warmup_period: int = 0,
    warmup_calc: Optional[Any] = None,
    constraint: Optional[Any] = None,
    result_filter: Optional[Any] = None,
    compounding: bool = False,
    timeout: Optional[float] = None,
    max_tasks_per_child: Optional[int] = None,
    **kwargs: Any,
) -> pd.DataFrame
```

**关键参数补充:**

*   `**kwargs` 会透传到 `run_grid_search`（样本内优化阶段）与 `run_backtest`（样本外验证阶段）。
*   因此，`forward_worker_logs` 可用于控制样本内并行优化日志回传。
*   同时，`strict_strategy_params` 会在优化与回测阶段保持严格参数校验语义（默认严格）。

### `akquant.run_warm_start`

从快照恢复并继续运行回测（支持多策略 slot 执行）。

```python
def run_warm_start(
    checkpoint_path: str,
    data: Optional[BacktestDataInput] = None,
    show_progress: bool = True,
    symbol: Union[str, List[str]] = "BENCHMARK",
    symbols: Optional[Union[str, List[str]]] = None,
    strategy_runtime_config: Optional[Union[StrategyRuntimeConfig, Dict[str, Any]]] = None,
    runtime_config_override: bool = True,
    strategy_id: Optional[str] = None,
    strategies_by_slot: Optional[Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]] = None,
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
    risk_budget_mode: Literal["order_notional", "trade_notional"] = "order_notional",
    risk_budget_reset_daily: bool = False,
    on_event: Optional[Callable[[BacktestStreamEvent], None]] = None,
    config: Optional[BacktestConfig] = None,
    **kwargs: Any,
) -> BacktestResult
```

**关键参数:**

*   `data`: 回测数据。支持单个 DataFrame，`{symbol: DataFrame}` 字典，`List[Bar]`，或实现 `DataFeedAdapter.load(request)` 的对象。
*   `strategy`: 策略类、策略实例，或 `on_bar` 函数（函数式编程风格）。
*   `initialize` / `on_start` / `on_stop`: 函数式策略生命周期回调，分别对应初始化、启动、停止阶段。
*   `symbols`: 推荐参数。标的代码或代码列表。
*   `symbol`: 兼容参数。仅在未传 `symbols` 时生效。
*   `initial_cash`: 初始资金 (默认 1,000,000.0)。
*   `execution_mode`: 执行模式。
    *   `ExecutionMode.NextOpen`: 下一 Bar 开盘价成交 (默认)。
    *   `ExecutionMode.CurrentClose`: 当前 Bar 收盘价成交。
*   `timer_execution_policy`: 定时器事件成交时序策略（主要用于 `CurrentClose`）。
    *   `"same_cycle"`: 在当前 `timer` 事件周期内撮合。
    *   `"next_event"`: 延后到下一条行情事件再撮合。
*   `fill_policy`: 统一成交语义配置（优先级高于 `execution_mode` 与 `timer_execution_policy`）。
    *   `price_basis`: `next_open`、`current_close`、`ohlc4`（OHLC 平均价）或 `hl2`（高低中价）。
    *   预留（暂未实现）: `mid_quote`、`vwap_window`、`twap_window`（当前会抛出 `NotImplementedError`）。
    *   `temporal`: `same_cycle` 或 `next_event`。
*   `strict_strategy_params`: 是否严格校验策略构造参数（默认 `True`）。
    *   当传入策略不接受的参数时会立即抛错；
    *   推荐保持默认值，避免参数错配被静默忽略导致回测结果偏差。
*   `t_plus_one`: 是否启用 T+1 交易规则 (默认 False)。如果启用，将强制使用中国市场模型。
*   `slippage`: 全局滑点 (默认 0.0)。例如 0.0001 代表 1bp (0.01%) 的滑点，采用百分比模型。
*   `volume_limit_pct`: 成交量限制比例 (默认 0.25)。限制单笔成交不超过该 Bar 总成交量的百分比。
*   `warmup_period`: 策略预热期。指定需要预加载的历史数据长度（Bar 数量），用于计算指标。
*   `start_time` / `end_time`: 回测开始/结束时间。
*   `config`: `BacktestConfig` 配置对象，用于集中管理配置。
*   `instruments_config`: 标的配置。用于设置期货/期权等非股票资产的参数（如乘数、保证金）。
*   `lot_size`: 最小交易单位。如果是 `int`，应用于所有标的；如果是字典，按标的匹配。
*   `custom_matchers`: 自定义撮合器字典。
*   `risk_config`: 风控配置。支持字典 (e.g., `{"max_position_pct": 0.1}`) 或 `RiskConfig` 对象。如果同时提供了 `config.strategy_config.risk`，此参数将覆盖其中的同名字段。
*   `strategies_by_slot`: 可选多策略映射。键为 slot id，值为策略类/实例/函数式 on_bar 回调；用于启用 slot 迭代执行。
*   `analyzer_plugins`: 可选 Analyzer 插件列表。插件接收 `on_start/on_bar/on_trade/on_finish` 生命周期回调，结果汇总到 `result.analyzer_outputs`。
*   `on_event`: 可选事件回调。不传时内部使用 no-op 回调并保持阻塞返回语义；传入时可实时消费事件。
*   `broker_profile`: 可选 broker 参数模板，用于快速注入费率/滑点/最小手数等默认值。内置模板：`cn_stock_miniqmt`、`cn_stock_t1_low_fee`、`cn_stock_sim_high_slippage`。

**执行语义迁移映射：**

| 旧参数组合 | 新参数写法 |
| :--- | :--- |
| `execution_mode="next_open"` | `fill_policy={"price_basis":"next_open","temporal":"same_cycle"}` |
| `execution_mode="current_close", timer_execution_policy="same_cycle"` | `fill_policy={"price_basis":"current_close","temporal":"same_cycle"}` |
| `execution_mode="current_close", timer_execution_policy="next_event"` | `fill_policy={"price_basis":"current_close","temporal":"next_event"}` |
| `execution_mode="next_average"` | `fill_policy={"price_basis":"ohlc4","temporal":"same_cycle"}` |
| `execution_mode="next_high_low_mid"` | `fill_policy={"price_basis":"hl2","temporal":"same_cycle"}` |

**DataFeedAdapter 用法（多时间框）:**

```python
import akquant as aq

base = aq.CSVFeedAdapter(path_template="/data/{symbol}.csv")

feed_15m = base.resample(freq="15min", emit_partial=False)
feed_replay = base.replay(
    freq="1h",
    align="session",            # session | day | global
    day_mode="trading",         # 仅 align='day' 时生效: trading | calendar
    emit_partial=False,
    session_windows=[("09:30", "11:30"), ("13:00", "15:00")],  # 仅 align='session'
)

result = aq.run_backtest(
    data=feed_replay,
    strategy=MyStrategy,
    symbols="000001",
    show_progress=False,
)
```

*   `align="session"`: 按交易日分区，可叠加 `session_windows`。
*   `align="day"`: 按日分区，不接收 `session_windows`；`day_mode` 支持 `trading/calendar`。
*   `align="global"`: 按全局时间轴聚合，不按交易日切段。
*   参数建议：优先使用 `symbols`。若同时传入 `symbol` 和 `symbols`，仅当 `symbol="BENCHMARK"` 时视作兼容写法，其它情况会报错。
*   弃用进度：当前版本中，仅传 `symbol` 会触发 `DeprecationWarning`；后续小版本将移除 `symbol` 参数，请提前迁移到 `symbols`。

**兼容与迁移说明:**

*   推荐逐步将实时 UI / 日志 / 告警接入迁移到 `run_backtest(..., on_event=...)`。
*   流式场景统一使用 `run_backtest(..., on_event=...)`。
*   在 PyCharm 中若未开启终端仿真，原生进度条可能不可见；可开启 `Emulate terminal in output console` 或改用 `on_event` 的 `progress` 事件输出文本进度。
*   阶段 5 后不再提供运行时参数级回滚开关；如需回滚请使用版本级回滚策略。
*   阶段 4 观察窗口与推进门槛请参考：[流式统一内核观察清单](../advanced/stream_observability.md)。

**阶段 5 迁移 FAQ:**

*   `run_backtest` 是否改名？不改名，调用方式保持不变。
*   `run_backtest` 是否仍可不传 `on_event`？可以，不传时仍返回同样的结果对象语义。
*   PyCharm 看不到进度条怎么办？先确认 `show_progress=True`，并在 Run 配置中开启 `Emulate terminal in output console`；若仍不可见，使用 `on_event` 消费 `progress` 事件打印文本进度。
*   线上出现问题如何回退？使用版本级回滚，不再支持 `_engine_mode` 参数级回切。
*   还可以继续用 `symbol` 吗？可以但已进入弃用阶段，会有 `DeprecationWarning`，建议尽快替换为 `symbols`。

### 流式参数与事件 (`run_backtest`)

**关键参数:**

*   `on_event`: 流式事件回调函数（必传），参数为 `BacktestStreamEvent`。
*   `stream_progress_interval`: `progress` 事件采样间隔（正整数）。
*   `stream_equity_interval`: `equity` 事件采样间隔（正整数）。
*   `stream_batch_size`: 事件批量刷新阈值（正整数）。
*   `stream_max_buffer`: 缓冲区上限（正整数）。
*   `stream_error_mode`: 回调异常处理策略。
    *   `"continue"`: 回调报错后继续回测，并在结束事件中回传统计信息。
    *   `"fail_fast"`: 回调首次报错后立即终止，并抛出异常。
*   `stream_mode`: 流式模式。
    *   `"observability"`: 观测模式，允许采样与非关键事件背压丢弃。
    *   `"audit"`: 审计模式，禁用采样并采用阻塞背压（不丢弃非关键事件）。
*   `strategy_id`（通过 `**kwargs` 透传）: 为交易相关事件与结果打上策略归属，默认 `_default`。

**事件结构 (`BacktestStreamEvent`):**

*   `run_id`: 本次流式回测 ID。
*   `seq`: 事件序号（单调递增）。
*   `ts`: 事件时间戳（纳秒）。
*   `event_type`: 事件类型。
*   `symbol`: 关联标的（部分事件为空）。
*   `level`: 事件级别（如 `info`、`warn`、`error`）。
*   `payload`: 事件内容字典（字符串键值）。

**常见 `event_type`:**

*   生命周期: `started`, `finished`
*   采样更新: `progress`, `equity`
*   交易相关: `order`, `trade`, `risk`
*   运行异常: `error`
*   行情流: `tick`

**交易事件 payload 常用字段 (`order`/`trade`/`risk`):**

*   `owner_strategy_id`: 策略归属 ID（默认 `_default`）。
*   `order_id`: 订单 ID（`order`/`trade`/`risk`）。
*   `symbol`: 标的代码（`order`/`risk`）。
*   `status`: 订单状态（`order`）。
*   `filled_qty`: 订单已成交量（`order`）。
*   `trade_id`: 成交 ID（`trade`）。
*   `price`: 成交价格（`trade`）。
*   `quantity`: 成交数量（`trade`）。
*   `reason`: 风控拒绝原因（`risk`）。

**`finished.payload` 常用字段:**

*   `status`: `completed` 或 `failed`
*   `processed_events`: 已处理事件数
*   `total_trades`: 总成交笔数
*   `callback_error_count`: 回调报错次数
*   `dropped_event_count`: 背压丢弃事件总数
*   `dropped_event_count_by_type`: 按事件类型聚合的丢弃计数（`event=count` 逗号拼接）
*   `stream_mode`: 当前流式模式（`observability` 或 `audit`）
*   `sampling_enabled`: 是否启用采样（`true`/`false`）
*   `backpressure_policy`: 背压策略（`drop_non_critical` 或 `block`）
*   `last_callback_error`: 最近一次回调报错信息（存在时提供）
*   `reason`: 失败原因（存在时提供）

### `akquant.BacktestConfig`

用于集中配置回测参数的数据类。

```python
@dataclass
class BacktestConfig:
    strategy_config: StrategyConfig
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    instruments: Optional[List[str]] = None
    instruments_config: Optional[Union[List[InstrumentConfig], Dict[str, InstrumentConfig]]] = None
    benchmark: Optional[str] = None
    timezone: str = "Asia/Shanghai"
    show_progress: bool = True
    history_depth: int = 0

    # Analysis & Bootstrap
    bootstrap_samples: int = 1000
    bootstrap_sample_size: Optional[int] = None
    analysis_config: Optional[Dict[str, Any]] = None

```

### `akquant.StrategyConfig`

策略层面的配置，包含资金、费率和风控。

```python
@dataclass
class StrategyConfig:
    initial_cash: float = 100000.0

    # 费率
    commission_rate: float = 0.0
    stamp_tax_rate: float = 0.0
    transfer_fee_rate: float = 0.0
    min_commission: float = 0.0

    # 执行
    enable_fractional_shares: bool = False
    round_fill_price: bool = True       # 是否对成交价进行最小变动价位取整
    slippage: float = 0.0               # 全局滑点 (e.g. 0.0002 for 2 bps)
    volume_limit_pct: float = 0.25      # 成交量限制 (e.g. 0.25 for 25% of bar volume)
    exit_on_last_bar: bool = True       # 是否在回测结束时自动平仓

    # 持仓限制
    max_long_positions: Optional[int] = None
    max_short_positions: Optional[int] = None

    # 风控
    risk: Optional[RiskConfig] = None

    # 多策略拓扑与策略级风控
    strategy_id: Optional[str] = None
    strategies_by_slot: Optional[Dict[str, Any]] = None
    strategy_max_order_value: Optional[Dict[str, float]] = None
    strategy_max_order_size: Optional[Dict[str, float]] = None
    strategy_max_position_size: Optional[Dict[str, float]] = None
    strategy_max_daily_loss: Optional[Dict[str, float]] = None
    strategy_max_drawdown: Optional[Dict[str, float]] = None
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None
    strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None
    strategy_priority: Optional[Dict[str, int]] = None
    strategy_risk_budget: Optional[Dict[str, float]] = None
    portfolio_risk_budget: Optional[float] = None
```

### `akquant.InstrumentConfig`

用于配置单个标的属性的数据类。

```python
@dataclass
class InstrumentConfig:
    symbol: str
    asset_type: Union[
        Literal["STOCK", "FUTURES", "FUND", "OPTION"],
        InstrumentAssetTypeEnum
    ] = InstrumentAssetTypeEnum.STOCK
    multiplier: float = 1.0    # 合约乘数
    margin_ratio: float = 1.0  # 保证金率 (0.1 表示 10% 保证金)
    tick_size: float = 0.01    # 最小变动价位
    lot_size: int = 1          # 最小交易单位

    # 费率与执行 (资产专用)
    commission_rate: Optional[float] = None
    min_commission: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    transfer_fee_rate: Optional[float] = None
    slippage: Optional[float] = None

    # 期权相关
    option_type: Optional[
        Union[Literal["CALL", "PUT"], InstrumentOptionTypeEnum]
    ] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[Union[int, date, datetime]] = None
    underlying_symbol: Optional[str] = None
    settlement_type: Optional[
        Union[
            Literal["cash", "settlement_price", "force_close"],
            InstrumentSettlementTypeEnum
        ]
    ] = None
    settlement_price: Optional[float] = None
```

常用枚举（均可在 `akquant` 顶层直接访问）：

- `InstrumentAssetTypeEnum`: `STOCK` / `FUTURES` / `FUND` / `OPTION`
- `InstrumentOptionTypeEnum`: `CALL` / `PUT`
- `InstrumentSettlementTypeEnum`: `CASH` / `SETTLEMENT_PRICE` / `FORCE_CLOSE`

示例：

```python
conf = akquant.InstrumentConfig(
    symbol="IF2506",
    asset_type=akquant.InstrumentAssetTypeEnum.FUTURES,
    settlement_type=akquant.InstrumentSettlementTypeEnum.CASH,
)
```

### `akquant.InstrumentSnapshot`

策略侧可访问的标的静态属性快照对象（由引擎注入，通常通过 `Strategy.get_instrument*` 读取）。

```python
@dataclass(frozen=True)
class InstrumentSnapshot:
    symbol: str
    asset_type: Literal["STOCK", "FUTURES", "FUND", "OPTION"]
    multiplier: float
    margin_ratio: float
    tick_size: float
    lot_size: float
    option_type: Optional[Literal["CALL", "PUT"]] = None
    strike_price: Optional[float] = None
    expiry_date: Optional[int] = None  # YYYYMMDD
    underlying_symbol: Optional[str] = None
    settlement_type: Optional[Literal["CASH", "SETTLEMENT_PRICE", "FORCE_CLOSE"]] = None
    settlement_price: Optional[float] = None
    static_attrs: Dict[str, Union[str, int, float, bool]] = field(default_factory=dict)
```

要点：

*   `expiry_date` 使用 `int(YYYYMMDD)` 语义。
*   快照在 `on_start` 即可访问。
*   建议在策略中通过 `get_instrument` / `get_instrument_config` / `get_instrument_field` 访问。

### 配置系统详解 (Configuration System)

AKQuant 提供了灵活的配置系统，允许用户通过多种方式设置回测参数。

#### 1. 配置层级 (Hierarchy)

配置对象采用树状结构组织，`BacktestConfig` 是顶层入口：

```text
BacktestConfig (回测场景)
├── StrategyConfig (策略与账户)
│   ├── initial_cash (初始资金)
│   ├── commission_rate (默认佣金)
│   ├── slippage (默认滑点)
│   └── RiskConfig (风控规则)
│       ├── safety_margin (安全垫)
│       └── max_position_pct (持仓限制)
└── InstrumentConfig (资产属性)
    ├── multiplier (合约乘数)
    └── commission_rate (资产专用佣金，覆盖 StrategyConfig)
```

中国期货扩展配置位于 `BacktestConfig.china_futures`，用于管理前缀级规则：

- `instrument_templates_by_symbol_prefix`: 品种模板（乘数/保证金/tick/手数/费率）
- `fee_by_symbol_prefix`: 品种费率覆盖
- `validation_by_symbol_prefix`: 品种撮合校验开关覆盖
- `enforce_sessions`: 是否严格按交易时段控制成交
- `session_profile`: 中国期货会话模板（`CN_FUTURES_DAY`=`CN_FUTURES_COMMODITY_DAY` / `CN_FUTURES_CFFEX_STOCK_INDEX_DAY` / `CN_FUTURES_CFFEX_BOND_DAY` / `CN_FUTURES_NIGHT_23` / `CN_FUTURES_NIGHT_01` / `CN_FUTURES_NIGHT_0230`）

配置对象采用“构造即校验”：

- `symbol_prefix` 为空会直接报错
- 模板数值范围非法（如 `multiplier <= 0`）会直接报错
- 同一列表内前缀重复会报错并标注冲突项索引

#### 2. 参数优先级 (Priority)

`run_backtest` 函数的参数解析遵循以下优先级（由高到低）：

1.  **显式参数 (Explicit Arguments)**:
    *   直接传递给 `run_backtest` 的参数优先级最高。
    *   例如：`run_backtest(start_time="2022-01-01")` 会覆盖 `config.start_time`。
2.  **配置对象 (Config Objects)**:
    *   如果显式参数为 `None`，则从 `config` (`BacktestConfig`) 中读取。
    *   多策略字段可集中配置在 `config.strategy_config`（如 `strategy_id`、
        `strategies_by_slot`、`strategy_max_*`、`strategy_priority`、
        `strategy_risk_budget`、`portfolio_risk_budget`）。
3.  **默认值 (Defaults)**:
    *   如果上述两者都未提供，则使用系统默认值。

中国期货扩展（`BacktestConfig.china_futures`）推荐使用以下优先级口径：

| 配置项 | 高优先级 | 中优先级 | 默认值 |
|---|---|---|---|
| 合约参数（乘数/保证金/tick/手数） | `InstrumentConfig` 显式字段 | `instrument_templates_by_symbol_prefix` | `run_backtest` 默认参数 |
| 品种费率 | `fee_by_symbol_prefix` | 模板 `commission_rate` | `StrategyConfig.commission_rate` |
| 品种校验开关 | `validation_by_symbol_prefix` | 模板 `enforce_tick_size / enforce_lot_size` | 全局 `ChinaFuturesConfig.enforce_*` |
| 交易时段 | `china_futures.sessions` 显式配置 | `session_profile` 模板 | ChinaMarket 默认会话 |
| 市场路由 | `use_china_futures_market=False` 或混合资产回落 | `use_china_futures_market=True` 且纯期货 | `use_simple_market` |

口径说明：

*   同级规则冲突时，以显式规则覆盖模板规则。
*   撮合校验路径按更具体前缀优先（更长匹配优先）。

中国期权扩展配置位于 `BacktestConfig.china_options`，用于管理中国期权费率：

- `fee_per_contract`: 全局每张合约手续费
- `fee_by_symbol_prefix`: 按品种前缀覆盖每张合约手续费
- `use_china_market`: 是否切换到 ChinaMarket
- `sessions`: 可选时段覆盖（不与期货会话配置冲突时生效）

中国期权扩展推荐使用以下优先级口径：

| 配置项 | 高优先级 | 中优先级 | 默认值 |
|---|---|---|---|
| 期权费率（按张） | `fee_by_symbol_prefix` | `fee_per_contract` | `set_option_fee_rules` 默认配置 |
| 市场路由 | `use_china_market=True` | 混合资产时自动 ChinaMarket | `use_simple_market` |

期货 vs 期权配置能力对照：

| 能力维度 | 中国期货（`china_futures`） | 中国期权（`china_options`） |
|---|---|---|
| 路由开关 | `use_china_futures_market` | `use_china_market` |
| 全局费率 | `StrategyConfig.commission_rate` 或模板费率 | `fee_per_contract` |
| 前缀费率覆盖 | `fee_by_symbol_prefix` | `fee_by_symbol_prefix` |
| 合约参数模板 | 支持（乘数/保证金/tick/手数） | 不支持 |
| 撮合校验开关 | 支持（tick/手数，含前缀覆盖） | 不支持 |
| 会话覆盖 | 支持（`sessions`） | 支持（`sessions`） |
| 前缀匹配策略 | 更长前缀优先 | 更长前缀优先 |

股票配置推荐使用以下优先级口径：

| 配置项 | 高优先级 | 中优先级 | 默认值 |
|---|---|---|---|
| 股票费率（佣金/印花税/过户费/最低佣金） | `InstrumentConfig` 单标的费率字段 | `StrategyConfig` 全局费率字段 | `run_backtest` 内置默认值 |
| 交易单位（`lot_size`） | `InstrumentConfig.lot_size`（显式设置） | `run_backtest(lot_size=...)` 全局设置 | `1` |
| 市场制度（T+1） | `run_backtest(t_plus_one=...)` 显式参数 | `Engine.set_t_plus_one(...)` 引擎设置 | `False` |
| 市场模型 | `use_china_market()` | `use_simple_market()` | 引擎默认市场配置 |

股票侧说明：

*   当前股票没有按代码前缀的模板层（不像期货的 `china_futures` 前缀模板）。
*   生产场景建议优先用 `InstrumentConfig` 精确配置重点股票，再用 `StrategyConfig` 作为全局兜底。

#### 3. 风控配置合并 (Risk Config Merging)

`risk_config` 参数的处理逻辑比较特殊，旨在支持“基准配置 + 快速覆盖”的模式：

*   **基准**: 首先加载 `config.strategy_config.risk`（如果存在）。
*   **覆盖**: 如果提供了 `risk_config` 参数（字典或对象），它将覆盖基准配置中的同名字段。
    *   这允许你在不修改 Config 对象的情况下，通过 `run_backtest(..., risk_config={"max_position_pct": 0.5})` 快速调整风控参数进行测试。

#### 4. 策略运行时配置注入 (Strategy Runtime Config Injection)

`run_backtest` 与 `run_warm_start` 支持 `strategy_runtime_config` 参数：

*   支持 `StrategyRuntimeConfig` 对象或 `dict`。
*   用于在不修改策略类代码的前提下注入运行时行为开关。
*   示例：`run_backtest(..., strategy_runtime_config={"error_mode": "continue"})`。
*   校验行为：未知字段或非法值会快速失败，并给出字段级错误信息。
*   冲突处理：`runtime_config_override=True` 时应用外部配置；`False` 时保留策略侧配置。
*   上述冲突规则在 `run_backtest` 与 `run_warm_start` 中保持一致。
*   对同一策略实例、同一冲突内容，告警日志会自动去重。
*   优先级规则：显式传入的 `strategy_runtime_config` 参数高于转发配置映射中的同名配置。
*   故障速查入口：参考 [Runtime Config 指南](../advanced/runtime_config.md)。

```python
from akquant import StrategyRuntimeConfig, run_backtest

result = run_backtest(
    data=data,
    strategy=MyStrategy,
    strategy_runtime_config=StrategyRuntimeConfig(
        error_mode="continue",
        portfolio_update_eps=1.0,
    ),
)
```

#### 5. 最佳实践 (Best Practices)

*   **简单脚本**: 直接使用 `run_backtest` 的扁平参数（如 `initial_cash`, `start_time`）。
*   **生产/复杂策略**: 构建完整的 `BacktestConfig` 对象，以便于版本管理和复用。
*   **页面化参数输入**: 在策略类中声明 `PARAM_MODEL`（`akquant.ParamModel`），并使用 `get_strategy_param_schema` / `validate_strategy_params` 完成前后端参数联动与校验。
*   **参数调优**: 使用 `run_grid_search` 时，通常通过修改 Config 对象或传入 override 参数来实现。

## 2. 策略开发 (Strategy)

### `akquant.Strategy`

策略基类。用户应继承此类并重写回调方法。

**回调方法:**

*   `on_start()`: 策略启动时触发。用于订阅 (`subscribe`) 和注册指标。
*   `on_bar(bar: Bar)`: K 线闭合时触发。
*   `on_tick(tick: Tick)`: Tick 到达时触发。
*   `on_order(order: Order)`: 订单状态更新时触发（如成交、取消、拒绝）。
*   `on_trade(trade: Trade)`: 订单成交时触发。
*   `on_reject(order: Order)`: 订单首次进入 `Rejected` 时触发一次。
*   `on_session_start(session, timestamp)`: 会话切换开始时触发。
*   `on_session_end(session, timestamp)`: 会话切换结束时触发。
*   `before_trading(trading_date, timestamp)`: 每个本地交易日首次进入 Normal 会话时触发一次。
*   `on_daily_rebalance(trading_date, timestamp)`: 交易日调仓钩子，每个交易日最多触发一次。
*   `after_trading(trading_date, timestamp)`: 离开 Normal 会话时触发；若先跨日则在下一事件补发。
*   `on_portfolio_update(snapshot)`: 账户快照变化时触发。
*   `on_error(error, source, payload=None)`: 用户回调抛异常时触发，默认触发后继续抛出。
*   `on_timer(payload: str)`: 定时器触发。
*   `on_stop()`: 策略停止时触发。
*   `on_train_signal(context)`: 滚动训练信号触发 (ML 模式)。

**属性与快捷访问:**

*   `self.symbol`: 当前正在处理的标的代码。
*   `self.close`, `self.open`, `self.high`, `self.low`, `self.volume`: 当前 Bar/Tick 的价格和成交量。
*   `self.position`: 当前标的持仓辅助对象 (`Position`)，包含 `size` 和 `available` 属性。
*   `self.now`: 当前回测时间 (`pd.Timestamp`)。
*   `self.runtime_config`: 运行时行为配置对象 (`StrategyRuntimeConfig`)。
*   `self.enable_precise_day_boundary_hooks`: 是否启用边界定时器精确交易日钩子（默认 `False`）。
*   `self.portfolio_update_eps`: 账户快照更新阈值，低于该变化量不触发 `on_portfolio_update`（默认 `0.0`）。
*   `self.error_mode`: 错误处理模式，`"raise"` 或 `"continue"`（默认 `"raise"`）。
*   `self.re_raise_on_error`: 用户回调异常后是否继续抛出（默认 `True`）。
*   `self.ctx`: 策略上下文 (`StrategyContext`)，提供底层 API 访问。

**交易方法:**

*   `buy(symbol, quantity, price=None, trigger_price=None, ...)`: 买入（开多/平空）。
    *   如果不指定 `price`，则为市价单。
    *   如果指定 `price`，则为限价单。
    *   如果指定 `trigger_price`，则为止损/止盈单 (Stop Market)。
*   `sell(symbol, quantity, price=None, trigger_price=None, ...)`: 卖出（平多/开空）。参数同上。
*   `submit_order(..., order_type="StopTrail", trail_offset=..., trail_reference_price=None)`: 提交跟踪止损单。`trail_offset` 必须大于 0。
*   `submit_order(..., order_type="StopTrailLimit", price=..., trail_offset=..., trail_reference_price=None)`: 提交跟踪止损限价单。`price` 与 `trail_offset` 必填。
*   `submit_order(..., broker_options={...})`: 可选 broker 扩展参数透传（回测阶段仅记录在订单对象 `order.broker_options` 上，便于联调与审计）。
*   `place_trailing_stop(symbol, quantity, trail_offset, side="Sell", trail_reference_price=None, ...) -> str`: 跟踪止损助手，触发后按市价执行。
*   `place_trailing_stop_limit(symbol, quantity, price, trail_offset, side="Sell", trail_reference_price=None, ...) -> str`: 跟踪止损限价助手，触发后按限价执行。
*   `order_target_weights(target_weights, price_map=None, liquidate_unmentioned=False, allow_leverage=False, rebalance_tolerance=0.0, ...)`: 按多标的目标权重调仓。
    *   `target_weights` 形如 `{symbol: weight}`，默认要求权重和不超过 `1.0`。
    *   `liquidate_unmentioned=True` 时，会将未出现在目标字典中的现有持仓目标设为 `0`。
    *   执行顺序为先卖后买，减少现金约束导致的调仓失败。
    *   `rebalance_tolerance` 按组合市值比例跳过小偏差，降低无效换手。
*   `cancel_order(order_id: str)`: 撤销指定订单。
*   `cancel_all_orders(symbol)`: 取消指定标的的所有挂单。如果不指定 `symbol`，则取消所有挂单。
*   `create_oco_order_group(first_order_id, second_order_id, group_id=None) -> str`: 创建 OCO 订单组。组内任一订单成交后，另一订单会被自动撤单。
*   `place_bracket_order(symbol, quantity, entry_price=None, stop_trigger_price=None, take_profit_price=None, ...) -> str`: 创建 Bracket 订单。先提交进场单，进场成交后自动提交止损/止盈；当止损与止盈同时存在时会自动绑定 OCO。

**数据与工具:**

*   `get_history(count, symbol, field="close") -> np.ndarray`: 获取历史数据数组 (Zero-Copy)。
*   `get_history_map(count, symbols, field="close") -> Dict[str, np.ndarray]`: 批量获取多个标的历史数据。
*   `rebalance_to_topn(scores, top_n, weight_mode="equal", ...) -> List[str]`: 根据打分选取 TopN 并执行调仓，支持等权或按分数归一化。
*   `get_history_df(count, symbol) -> pd.DataFrame`: 获取历史数据 DataFrame (OHLCV)。
*   `get_position(symbol) -> float`: 获取当前持仓量。
*   `get_available_position(symbol) -> float`: 获取可用持仓量。
*   `get_positions() -> Dict[str, float]`: 获取所有标的持仓。
*   `hold_bar(symbol) -> int`: 获取当前持仓持有的 Bar 数量。
*   `get_cash() -> float`: 获取当前可用资金。
*   `get_account() -> Dict[str, float]`: 获取账户详情快照 (`cash`, `equity`, `market_value`)。
*   `get_order(order_id) -> Order`: 获取指定订单详情。
*   `get_open_orders(symbol) -> List[Order]`: 获取当前未完成订单列表。
*   `get_trades() -> List[ClosedTrade]`: 获取所有已平仓交易记录。
*   `subscribe(instrument_id: str)`: 订阅行情。
*   `log(msg: str, level: int)`: 输出带时间戳的日志。
*   `schedule(trigger_time, payload)`: 注册单次定时任务。
*   `add_daily_timer(time_str, payload)`: 注册每日定时任务。
*   `to_local_time(timestamp) -> pd.Timestamp`: 将 UTC 时间戳转换为本地时间。
*   `format_time(timestamp, fmt) -> str`: 格式化时间戳。

**标的静态属性 API（推荐）:**

*   `get_instrument(symbol) -> InstrumentSnapshot`: 获取单个标的静态属性快照。
*   `get_instruments(symbols=None) -> Dict[str, InstrumentSnapshot]`: 获取多个标的静态属性快照字典；`symbols=None` 时返回全部。
*   `get_instrument_field(symbol, field) -> Any`: 获取单个标的字段值。
*   `get_instrument_config(symbol, fields=None) -> Union[Any, Dict[str, Any], InstrumentSnapshot]`: 兼容接口；支持整对象、单字段或多字段读取。

说明：

*   这些接口在 `on_start` 即可使用（启动阶段已注入快照）。
*   推荐优先使用这些接口读取静态属性，而不是依赖 `bar.extra`。

**机器学习支持:**

*   `set_rolling_window(train_window, step)`: 设置滚动训练窗口。
*   `get_rolling_data(length, symbol)`: 获取滚动训练数据 (X, y)。
*   `prepare_features(df, mode)`: (需重写) 特征工程与标签生成。

### `akquant.Bar`

K 线数据对象。

*   `timestamp`: Unix 时间戳 (纳秒)。
*   `open`, `high`, `low`, `close`, `volume`: OHLCV 数据。
*   `symbol`: 标的代码。
*   `extra`: 扩展数据字典 (`Dict[str, float]`)。
*   `timestamp_str`: 时间字符串。

### `akquant.Tick`

Tick 数据对象。

*   `timestamp`: Unix 时间戳 (纳秒)。
*   `price`: 最新价。
*   `volume`: 成交量。
*   `symbol`: 标的代码。

### `akquant.live.LiveRunner`（broker_live 执行语义） {: #live-broker-semantics }

实盘 broker 路由可通过 `gateway_options` 传入网关特定参数：

```python
runner = LiveRunner(
    strategy_cls=on_bar,
    instruments=instruments,
    broker="ctp",
    trading_mode="broker_live",
    gateway_options={"execution_semantics_mode": "strict"},
)
```

`gateway_options.execution_semantics_mode`：

| 取值 | 默认值 | 行为 | 推荐场景 |
| :--- | :--- | :--- | :--- |
| `strict` | 是 | `Cancelled` / `Rejected` / `Filled` 等终态由订单回报 (`OnRtnOrder`) 最终确认。错误回报会先缓存拒单原因，再在后续订单回报中补齐。 | 生产实盘 |
| `compatible` | 否 | 在部分错误/撤单路径允许本地立即推进终态，以兼容历史行为。 | 迁移过渡 |

严格模式注意事项：

*   撤单请求发送成功不等于 `Cancelled`，需等待 `OnRtnOrder(Cancelled)`。
*   收到错误回报不等于 `Rejected`，最终状态以订单回报为准。

## 3. 核心引擎 (Core)

### `akquant.Engine`

回测引擎的主入口 (通常通过 `run_backtest` 隐式使用)。

**配置方法:**

*   `set_timezone(offset: int)`: 设置时区偏移。
*   `use_simulated_execution()` / `use_realtime_execution()`: 设置执行环境。
*   `set_execution_mode(mode)`: 设置撮合模式。
*   `set_history_depth(depth)`: 设置历史数据缓存长度。

**市场与费率配置:**

*   `use_simple_market()`: 启用简单市场。
*   `use_china_market()`: 启用中国市场 (股票)。
*   `use_china_futures_market()`: 启用中国期货市场。
*   `set_stock_fee_rules(commission, stamp_tax, transfer_fee, min_commission)`: 设置股票费率。
*   `set_futures_fee_rules(commission_rate)`: 设置期货费率。
*   `set_futures_fee_rules_by_prefix(symbol_prefix, commission_rate)`: 设置期货品种前缀费率。
*   `set_futures_validation_options(enforce_tick_size, enforce_lot_size)`: 设置期货撮合前校验开关。
*   `set_futures_validation_options_by_prefix(symbol_prefix, enforce_tick_size, enforce_lot_size)`: 设置期货品种前缀校验开关。
*   `set_fund_fee_rules(...)`: 设置基金费率。
*   `set_option_fee_rules(...)`: 设置期权费率。
*   `set_slippage(type, value)`: 设置滑点 (Fixed 或 Percent)。
*   `set_volume_limit(limit)`: 设置成交量限制 (如 0.1 表示不超过 Bar 成交量的 10%)。
*   `set_market_sessions(sessions)`: 设置交易时段。

命名约定说明：

*   期货费率接口统一使用复数命名 `set_futures_fee_rules*`。
*   旧单数命名 `set_future_fee_rules*` 已移除，不再对外暴露。

### `akquant.gateway` 自定义 Broker 注册

可通过注册表机制按名称接入自定义 broker，而无需修改内置工厂分支。

**注册表 API:**

*   `register_broker(name, builder)`: 注册 broker 构建函数。
*   `unregister_broker(name)`: 取消注册 broker。
*   `get_broker_builder(name)`: 查询 broker 构建函数。
*   `list_registered_brokers()`: 获取当前已注册 broker 列表。

**Builder 签名:**

```python
def builder(
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool,
    **kwargs: Any,
) -> GatewayBundle:
    ...
```

**示例:**

```python
from akquant import DataFeed
from akquant.gateway import create_gateway_bundle, register_broker

register_broker("demo", demo_builder)
bundle = create_gateway_bundle(
    broker="demo",
    feed=DataFeed(),
    symbols=["000001.SZ"],
)
```

## 4. 交易对象 (Trading Objects)

### `akquant.Order`

*   `id`: 订单 ID。
*   `symbol`: 标的代码。
*   `side`: `OrderSide.Buy` / `OrderSide.Sell`。
*   `order_type`: `OrderType.Market` / `OrderType.Limit` / `StopMarket` 等。
*   `status`: `OrderStatus.New` / `Filled` / `Cancelled` 等。
*   `quantity` / `filled_quantity`: 委托/成交数量。
*   `price`: 委托价格。
*   `average_filled_price`: 成交均价。
*   `trigger_price`: 触发价格。
*   `time_in_force`: 有效期 (`GTC`, `IOC`, `FOK`, `Day`)。
*   `created_at` / `updated_at`: 时间戳。
*   `tag`: 标签。
*   `reject_reason`: 拒绝原因。

### `akquant.Trade`

单次成交记录（一个订单可能对应多次成交）。

*   `id`: 成交 ID。
*   `order_id`: 对应订单 ID。
*   `symbol`: 标的代码。
*   `side`: 方向。
*   `quantity`: 成交数量。
*   `price`: 成交价格。
*   `commission`: 手续费。
*   `timestamp`: 成交时间。

### `akquant.ClosedTrade`

已平仓交易记录（开仓+平仓的完整周期）。

*   `entry_time` / `exit_time`: 开/平仓时间。
*   `entry_price` / `exit_price`: 开/平仓价格。
*   `quantity`: 数量。
*   `pnl`: 盈亏金额。
*   `return_pct`: 收益率。
*   `duration`: 持仓时间。
*   `mae` / `mfe`: 最大不利/有利变动。

## 5. 投资组合与风控 (Portfolio & Risk)

### `akquant.RiskConfig`

风控配置。

```python
@dataclass
class RiskConfig:
    active: bool = True
    safety_margin: float = 0.0001
    max_order_size: Optional[float] = None
    max_order_value: Optional[float] = None
    max_position_size: Optional[float] = None
    restricted_list: Optional[List[str]] = None
    max_position_pct: Optional[float] = None
    sector_concentration: Optional[Union[float, tuple]] = None

    # 账户级风控
    max_account_drawdown: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_threshold: Optional[float] = None
```

账户级字段说明：

*   `max_account_drawdown`: 最大回撤阈值（0~1 小数）。以历史权益峰值为基准，当前权益回撤超过阈值后，新的下单请求会被拒绝。
*   `max_daily_loss`: 单日亏损阈值（0~1 小数）。以当日首次风控检查时的权益为基准，当日亏损超过阈值后，新的下单请求会被拒绝。
*   `stop_loss_threshold`: 账户净值止损阈值（0~1 小数）。当当前权益低于“规则首次生效时权益 × 阈值”后，新的下单请求会被拒绝。

这些拒单原因会体现在 `orders_df.reject_reason` 字段中。

## 6. 结果分析 (Analysis)

### `akquant.BacktestResult`

回测结果对象。

**属性:**

*   `metrics_df`: 绩效指标表格 (Sharpe, Drawdown 等)。
*   `trades_df`: 所有平仓交易记录表格。
*   `orders_df`: 所有委托记录表格。
*   `executions_df`: 所有成交流水表格（优先使用 Rust IPC/dict 快速导出）。
*   `positions_df`: 每日持仓详情。
*   `equity_curve`: 权益曲线 (List[Tuple[timestamp, value]])。
*   `trades`: `ClosedTrade` 对象列表。
*   `executions`: `Trade` 对象列表 (所有成交流水)。
*   `snapshots`: 每日 `PositionSnapshot` 列表。

**分析方法:**

*   `exposure_df(freq="D")`: 组合暴露分解（净暴露、总暴露、杠杆）。
*   `attribution_df(by="symbol", use_net=True, top_n=None)`: 按 symbol/tag 做归因汇总。
*   `capacity_df(freq="D")`: 容量代理指标（订单数、成交率、换手）。
*   `orders_by_strategy()`: 按 `owner_strategy_id` 聚合订单统计。
*   `executions_by_strategy()`: 按 `owner_strategy_id` 聚合成交流水统计。
*   `get_event_stats()`: 返回流式事件统计摘要（如 `processed_events`、`dropped_event_count`、`callback_error_count`、`backpressure_policy`、`stream_mode`）。

```python
orders_by_strategy = result.orders_by_strategy()
executions_by_strategy = result.executions_by_strategy()

# 常用字段示例
# orders_by_strategy:
# - owner_strategy_id, order_count, filled_order_count,
#   ordered_quantity, filled_quantity, ordered_value, filled_value,
#   fill_rate_qty, fill_rate_value
#
# executions_by_strategy:
# - owner_strategy_id, execution_count, total_quantity,
#   total_notional, total_commission, avg_fill_price

event_stats = result.get_event_stats()
# 常见字段:
# - processed_events, dropped_event_count, callback_error_count,
#   backpressure_policy, stream_mode, reason
```
