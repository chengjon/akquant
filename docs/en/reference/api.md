# API Reference

This API documentation covers the core classes and methods of AKQuant.

## 1. High-Level API

### `akquant.run_backtest`

The most commonly used backtest entry function, encapsulating the initialization and configuration process of the engine.

```python
def run_backtest(
    data: Optional[Union[pd.DataFrame, Dict[str, pd.DataFrame], List[Bar]]] = None,
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
    **kwargs: Any,
) -> BacktestResult
```

**Key Parameters:**

*   `data`: Backtest data. Supports a single DataFrame, a `{symbol: DataFrame}` dictionary, `List[Bar]`, or any object implementing `DataFeedAdapter.load(request)`.
*   `strategy`: Strategy class or instance. Also supports passing an `on_bar` function (functional style).
*   `initialize` / `on_start` / `on_stop`: Functional-strategy lifecycle callbacks for initialization, start, and stop stages.
*   `symbol`: Symbol or list of symbols.
*   `initial_cash`: Initial cash (default 1,000,000.0).
*   `execution_mode`: Execution mode.
    *   `ExecutionMode.NextOpen`: Match at next Bar Open (Default).
    *   `ExecutionMode.CurrentClose`: Match at current Bar Close.
*   `t_plus_one`: Enable T+1 trading rule (Default False). If enabled, it forces usage of China Market Model.
*   `slippage`: Global slippage (Default 0.0). E.g., 0.0001 means 1bp (0.01%) slippage, using percent model.
*   `volume_limit_pct`: Volume limit percentage (Default 0.25). Limits single trade to not exceed this percentage of the bar's total volume.
*   `warmup_period`: Strategy warmup period. Specifies the length of historical data (number of Bars) to preload for indicator calculation.
*   `start_time` / `end_time`: Backtest start/end time.
*   `config`: `BacktestConfig` object for centralized configuration.
*   `instruments_config`: Instrument configuration. Used to set parameters for non-stock assets like futures/options (e.g., multiplier, margin ratio).
    *   Accepts `List[InstrumentConfig]` or `{symbol: InstrumentConfig}`.
*   `risk_config`: Risk configuration. Supports dict (e.g., `{"max_position_pct": 0.1}`) or `RiskConfig` object. Overrides fields in `config.strategy_config.risk` if both are provided.
*   `strategy_id`: Primary strategy ownership id. Default `_default`.
*   `strategies_by_slot`: Optional multi-strategy mapping. Keys are slot ids and values are strategy class/instance/functional callback used by slot-iterative execution.
*   `strategy_max_order_size` / `strategy_max_order_value` / `strategy_max_position_size`: Optional strategy-level risk maps keyed by strategy id.
*   `strategy_max_daily_loss` / `strategy_max_drawdown`: Optional strategy-level stop maps keyed by strategy id.
*   `strategy_reduce_only_after_risk` / `strategy_risk_cooldown_bars`: Optional post-risk behavior maps keyed by strategy id.
*   `strategy_priority` / `strategy_risk_budget` / `portfolio_risk_budget`: Optional scheduling/budget controls.
*   `risk_budget_mode` / `risk_budget_reset_daily`: Risk budget accounting mode and reset policy.
*   `analyzer_plugins`: Optional analyzer plugin list. Plugins receive `on_start/on_bar/on_trade/on_finish` callbacks and final outputs are stored in `result.analyzer_outputs`.
*   `on_event`: Optional stream callback. When omitted, an internal no-op callback keeps legacy blocking return semantics; when provided, runtime events are emitted.

### `akquant.run_warm_start`

Resume a backtest from snapshot state and continue execution.

```python
def run_warm_start(
    checkpoint_path: str,
    data: Optional[BacktestDataInput] = None,
    show_progress: bool = True,
    symbol: Union[str, List[str]] = "BENCHMARK",
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

`run_warm_start` uses the same strategy-slot and strategy-level risk parameters as `run_backtest`.
For these fields, priority is:

1. explicit function arguments
2. `config.strategy_config`
3. restored/default values

**DataFeedAdapter Usage (Multi-Timeframe):**

```python
import akquant as aq

base = aq.CSVFeedAdapter(path_template="/data/{symbol}.csv")

feed_15m = base.resample(freq="15min", emit_partial=False)
feed_replay = base.replay(
    freq="1h",
    align="session",            # session | day | global
    day_mode="trading",         # effective only when align='day': trading | calendar
    emit_partial=False,
    session_windows=[("09:30", "11:30"), ("13:00", "15:00")],  # session only
)

result = aq.run_backtest(
    data=feed_replay,
    strategy=MyStrategy,
    symbol="000001",
    show_progress=False,
)
```

*   `align="session"`: Partition by trading day, optionally with `session_windows`.
*   `align="day"`: Partition by day without `session_windows`; `day_mode` supports `trading/calendar`.
*   `align="global"`: Aggregate on the full timeline without day partitioning.

**Compatibility & Migration Notes:**

*   Prefer migrating realtime UI/logging/alerting to `run_backtest(..., on_event=...)`.
*   Stream use cases are unified under `run_backtest(..., on_event=...)`.
*   Since Phase 5, runtime rollback flags are removed; use release-level rollback when needed.
*   Phase-4 observation window and go/no-go gates are documented in [Unified Stream Core Checklist](../advanced/stream_observability.md).

**Phase-5 Migration FAQ:**

*   Is `run_backtest` renamed? No, the public entry name stays unchanged.
*   Can `run_backtest` still be called without `on_event`? Yes, and result-return semantics stay the same.
*   How do we roll back in production? Use release-level rollback; `_engine_mode` runtime fallback is removed.

### Stream Parameters & Events (`run_backtest`)

**Key Parameters:**

*   `on_event`: Stream callback receiving `BacktestStreamEvent` (required).
*   `stream_progress_interval`: Sampling interval for `progress` events (positive int).
*   `stream_equity_interval`: Sampling interval for `equity` events (positive int).
*   `stream_batch_size`: Flush threshold for buffered events (positive int).
*   `stream_max_buffer`: Maximum buffered events (positive int).
*   `stream_error_mode`: Callback exception handling policy.
    *   `"continue"`: Continue backtest on callback errors and report summary in
        final `finished` event.
    *   `"fail_fast"`: Stop immediately and raise once callback throws.
*   `stream_mode`: Stream mode.
    *   `"observability"`: observability-oriented mode with sampling and non-critical dropping under backpressure.
    *   `"audit"`: audit-oriented mode with sampling disabled and blocking backpressure for non-critical events.
*   `strategy_id` (forwarded via `**kwargs`): Tags trading events and results with strategy ownership. Default is `_default`.

**Event Schema (`BacktestStreamEvent`):**

*   `run_id`: Stream run id.
*   `seq`: Monotonic event sequence.
*   `ts`: Event timestamp in nanoseconds.
*   `event_type`: Event type.
*   `symbol`: Related symbol (nullable for some events).
*   `level`: Event level (e.g., `info`, `warn`, `error`).
*   `payload`: Event payload as string key-value map.

**Common `event_type` values:**

*   Lifecycle: `started`, `finished`
*   Sampled updates: `progress`, `equity`
*   Trading: `order`, `trade`, `risk`
*   Runtime failure: `error`
*   Market data: `tick`

**Common trading payload fields (`order`/`trade`/`risk`):**

*   `owner_strategy_id`: Strategy ownership id (default `_default`).
*   `order_id`: Order id (`order`/`trade`/`risk`).
*   `symbol`: Symbol (`order`/`risk`).
*   `status`: Order status (`order`).
*   `filled_qty`: Filled quantity (`order`).
*   `trade_id`: Trade id (`trade`).
*   `price`: Fill price (`trade`).
*   `quantity`: Fill quantity (`trade`).
*   `reason`: Risk rejection reason (`risk`).

**Common `finished.payload` fields:**

*   `status`: `completed` or `failed`
*   `processed_events`: Number of processed events
*   `total_trades`: Number of trades
*   `callback_error_count`: Total callback errors
*   `dropped_event_count`: Total number of events dropped under backpressure
*   `dropped_event_count_by_type`: Dropped count grouped by event type (`event=count` comma-separated)
*   `stream_mode`: Effective stream mode (`observability` or `audit`)
*   `sampling_enabled`: Whether sampling is enabled (`true`/`false`)
*   `backpressure_policy`: Backpressure policy (`drop_non_critical` or `block`)
*   `last_callback_error`: Latest callback error message (when present)
*   `reason`: Failure reason (when present)

### `akquant.BacktestConfig`

Data class for centralized backtest configuration.

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

Configuration at the strategy level, including capital, fees, and risk.

```python
@dataclass
class StrategyConfig:
    initial_cash: float = 100000.0
    commission_rate: float = 0.0
    stamp_tax_rate: float = 0.0
    transfer_fee_rate: float = 0.0
    min_commission: float = 0.0

    # Execution
    enable_fractional_shares: bool = False
    round_fill_price: bool = True
    slippage: float = 0.0
    volume_limit_pct: float = 0.25
    exit_on_last_bar: bool = True

    # Position Sizing
    max_long_positions: Optional[int] = None
    max_short_positions: Optional[int] = None

    risk: Optional[RiskConfig] = None

    # Multi-strategy topology & strategy-level controls
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

A data class used to configure the properties of a single instrument.

```python
@dataclass
class InstrumentConfig:
    symbol: str
    asset_type: str = "STOCK"  # "STOCK", "FUTURES", "FUND", "OPTION"
    multiplier: float = 1.0    # Contract multiplier
    margin_ratio: float = 1.0  # Margin ratio (0.1 means 10% margin)
    tick_size: float = 0.01    # Minimum price variation
    lot_size: int = 1          # Minimum trade unit

    # Costs & Execution (Asset Specific)
    commission_rate: Optional[float] = None
    min_commission: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    transfer_fee_rate: Optional[float] = None
    slippage: Optional[float] = None

    # Option specific
    option_type: Optional[str] = None  # "CALL" or "PUT"
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None
    underlying_symbol: Optional[str] = None

### Configuration System Explained

AKQuant provides a flexible configuration system that allows users to set backtest parameters in multiple ways.

#### 1. Hierarchy

Configuration objects are organized in a tree structure, with `BacktestConfig` as the top-level entry point:

```text
BacktestConfig (Simulation Scenario)
├── StrategyConfig (Strategy & Account)
│   ├── initial_cash
│   ├── commission_rate (Default)
│   ├── slippage (Default)
│   └── RiskConfig (Risk Rules)
│       ├── safety_margin
│       └── max_position_pct
└── InstrumentConfig (Asset Properties)
    ├── multiplier
    └── commission_rate (Asset-specific override)
```

#### 2. Priority

Parameter resolution in `run_backtest` follows this priority order (highest to lowest):

1.  **Explicit Arguments**:
    *   Parameters passed directly to `run_backtest` have the highest priority.
    *   Example: `run_backtest(start_time="2022-01-01")` overrides `config.start_time`.
2.  **Configuration Objects**:
    *   If explicit arguments are `None`, values are read from `config` (`BacktestConfig`).
    *   Multi-strategy fields can be centralized in `config.strategy_config`
        (`strategy_id`, `strategies_by_slot`, `strategy_max_*`, `strategy_priority`,
        `strategy_risk_budget`, `portfolio_risk_budget`).
3.  **Defaults**:
    *   If neither provides a value, system defaults are used.

#### 3. Risk Config Merging

The `risk_config` parameter has special handling logic designed to support a "Baseline + Override" pattern:

*   **Baseline**: First loads `config.strategy_config.risk` (if it exists).
*   **Override**: If `risk_config` parameter (dict or object) is provided, it overrides fields in the baseline configuration.
    *   This allows you to quickly adjust risk parameters for testing without modifying the main Config object, e.g., `run_backtest(..., risk_config={"max_position_pct": 0.5})`.

#### 4. Strategy Runtime Config Injection

`run_backtest` and `run_warm_start` support `strategy_runtime_config`:

*   Accepted formats: `StrategyRuntimeConfig` or `dict`.
*   Purpose: Inject runtime behavior switches without modifying strategy class code.
*   Example: `run_backtest(..., strategy_runtime_config={"error_mode": "continue"})`.
*   Validation: Unknown keys and invalid values fail fast with field-level errors.
*   Conflict handling: `runtime_config_override=True` applies external config; `False` keeps strategy-side config.
*   The same conflict rules apply consistently to both `run_backtest` and `run_warm_start`.
*   Conflict warnings are deduplicated per strategy instance for identical conflict payloads.
*   Priority rule: explicit `strategy_runtime_config` parameter has higher priority than forwarded config maps.
*   Troubleshooting quick lookup: see [Runtime Config Guide](../advanced/runtime_config.md).

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

#### 5. Best Practices

*   **Simple Scripts**: Use flat parameters of `run_backtest` directly (e.g., `initial_cash`, `start_time`).
*   **Production/Complex Strategies**: Build a complete `BacktestConfig` object for version control and reuse.
*   **Parameter Tuning**: When using `run_grid_search`, modify the Config object or pass override parameters as needed.

### `akquant.RiskConfig`

Configuration for risk management.

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

    # Account Level Risk
    max_account_drawdown: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_threshold: Optional[float] = None
```
    lot_size: int = 1          # Minimum trading unit
    # Option specific
    option_type: Optional[str] = None  # "CALL" or "PUT"
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None  # YYYY-MM-DD
```

## 2. Strategy Development (Strategy)

### `akquant.Strategy`

Strategy base class. Users should inherit from this class and override callback methods.

**Callback Methods:**

*   `on_start()`: Triggered when the strategy starts. Used for subscription (`subscribe`) and indicator registration.
*   `on_bar(bar: Bar)`: Triggered when a Bar closes.
*   `on_tick(tick: Tick)`: Triggered when a Tick arrives.
*   `on_order(order)`: Triggered when order state changes.
*   `on_trade(trade)`: Triggered when trade report arrives.
*   `on_reject(order)`: Triggered once when an order becomes `Rejected`.
*   `on_session_start(session, timestamp)`: Triggered on session transition start.
*   `on_session_end(session, timestamp)`: Triggered on session transition end.
*   `before_trading(trading_date, timestamp)`: Triggered once when entering Normal session each local day.
*   `after_trading(trading_date, timestamp)`: Triggered when leaving Normal session, or replayed on next event after day rollover.
*   `on_portfolio_update(snapshot)`: Triggered when cash/equity/position snapshot changes.
*   `on_error(error, source, payload=None)`: Triggered when user callback raises, then exception is re-raised by default.
*   `on_timer(payload: str)`: Triggered by timer.
*   `on_stop()`: Triggered when the strategy stops.
*   `on_train_signal(context)`: Triggered by rolling training signal (ML mode).

**Properties & Shortcuts:**

*   `self.symbol`: The symbol currently being processed.
*   `self.close`, `self.open`, `self.high`, `self.low`, `self.volume`: Current Bar/Tick price and volume.
*   `self.position`: Position object for current symbol, with `size` and `available` properties.
*   `self.now`: Current backtest time (`pd.Timestamp`).
*   `self.runtime_config`: Runtime behavior config object (`StrategyRuntimeConfig`).
*   `self.enable_precise_day_boundary_hooks`: Enable boundary timer based precise day hooks (default `False`).
*   `self.portfolio_update_eps`: Snapshot threshold; changes below it skip `on_portfolio_update` (default `0.0`).
*   `self.error_mode`: Error handling mode, `"raise"` or `"continue"` (default `"raise"`).
*   `self.re_raise_on_error`: Whether to re-raise user callback exception after `on_error` (default `True`).

**Trading Methods:**

*   `buy(symbol, quantity, price=None, ...)`: Buy. Market order if `price` is not specified.
*   `sell(symbol, quantity, price=None, ...)`: Sell.
*   `short(symbol, quantity, price=None, ...)`: Short sell.
*   `cover(symbol, quantity, price=None, ...)`: Buy to cover.
*   `stop_buy(symbol, trigger_price, quantity, ...)`: Stop buy (Stop Market). Triggers a market buy order when price breaks above `trigger_price`.
*   `stop_sell(symbol, trigger_price, quantity, ...)`: Stop sell (Stop Market). Triggers a market sell order when price drops below `trigger_price`.
*   `submit_order(..., order_type="StopTrail", trail_offset=..., trail_reference_price=None)`: Submit a trailing stop order. `trail_offset` must be greater than 0.
*   `submit_order(..., order_type="StopTrailLimit", price=..., trail_offset=..., trail_reference_price=None)`: Submit a trailing stop-limit order. `price` and `trail_offset` are required.
*   `place_trailing_stop(symbol, quantity, trail_offset, side="Sell", trail_reference_price=None, ...) -> str`: Helper for trailing stop orders, promoted to market order when triggered.
*   `place_trailing_stop_limit(symbol, quantity, price, trail_offset, side="Sell", trail_reference_price=None, ...) -> str`: Helper for trailing stop-limit orders, promoted to limit order when triggered.
*   `order_target_value(target_value, symbol, price=None)`: Adjust position to target value.
*   `order_target_percent(target_percent, symbol, price=None)`: Adjust position to target account percentage.
*   `order_target_weights(target_weights, price_map=None, liquidate_unmentioned=False, allow_leverage=False, rebalance_tolerance=0.0, ...)`: Rebalance a multi-asset portfolio by target weights.
    *   `target_weights` is `{symbol: weight}` and by default requires total weight `<= 1.0`.
    *   `liquidate_unmentioned=True` sets all existing non-mentioned positions to target `0`.
    *   Orders are submitted in sell-first then buy-second order to reduce cash-lock conflicts.
    *   `rebalance_tolerance` skips tiny drifts by portfolio-value ratio to reduce churn.
*   `close_position(symbol)`: Close position for a specific instrument.
*   `cancel_order(order_id: str)`: Cancel a specific order.
*   `cancel_all_orders(symbol)`: Cancel all pending orders for a specific instrument. If `symbol` is omitted, cancels all orders.
*   `create_oco_order_group(first_order_id, second_order_id, group_id=None) -> str`: Create an OCO order group. Once one order is filled, the peer order is canceled automatically.
*   `place_bracket_order(symbol, quantity, entry_price=None, stop_trigger_price=None, take_profit_price=None, ...) -> str`: Create a bracket order. The entry order is submitted first, then stop-loss/take-profit exits are submitted after entry fill; if both exits exist, they are linked as OCO automatically.

**Data & Utilities:**

*   `get_history(count, symbol, field="close") -> np.ndarray`: Get history data array (Zero-Copy). Supports `open/high/low/close/volume` and any numeric extra fields (e.g., `adj_close`, `adj_factor`).
*   `get_history_df(count, symbol) -> pd.DataFrame`: Get history data DataFrame (OHLCV).
*   `get_position(symbol) -> float`: Get current position size.
*   `get_cash() -> float`: Get current available cash.
*   `get_account() -> Dict[str, float]`: Get account snapshot. Includes `cash` (available), `equity` (total equity), `market_value` (position value), plus `frozen_cash` and `margin` (reserved fields, currently 0).
*   `get_order(order_id) -> Order`: Get details of a specific order.
*   `get_open_orders(symbol) -> List[Order]`: Get list of open orders.
*   `subscribe(instrument_id: str)`: Subscribe to market data. Must be called explicitly for multi-asset backtesting or live trading to receive `on_tick`/`on_bar` callbacks.
*   `log(msg: str, level: int)`: Log with timestamp.
*   `schedule(trigger_time, payload)`: Register a one-time timer task.
*   `add_daily_timer(time_str, payload)`: Register a daily timer task.

**Machine Learning Support:**

*   `set_rolling_window(train_window, step)`: Set rolling training window.
*   `get_rolling_data(length, symbol)`: Get rolling training data (X, y).
*   `prepare_features(df, mode)`: (Override required) Feature engineering and label generation.

### `akquant.Bar`

Bar data object.

*   `timestamp`: Unix timestamp (nanoseconds).
*   `open`, `high`, `low`, `close`, `volume`: OHLCV data.
*   `symbol`: Instrument symbol.

## 3. Core Engine

### `akquant.Engine`

The main entry point for the backtesting engine (usually used implicitly via `run_backtest`).

**Configuration Methods:**

*   `set_timezone(offset: int)`: Set timezone offset.
*   `use_simulated_execution()` / `use_realtime_execution()`: Set execution environment.
*   `set_execution_mode(mode)`: Set matching mode.
*   `set_history_depth(depth)`: Set history data cache length.

**Market & Fee Configuration:**

*   `use_simple_market()`: Enable simple market.
*   `use_china_market()`: Enable China market.
*   `set_stock_fee_rules(commission, stamp_tax, transfer_fee, min_commission)`: Set fee rules.

### `akquant.gateway` Custom Broker Registry

You can plug in a custom broker by name through the registry without editing built-in factory branches.

**Registry APIs:**

*   `register_broker(name, builder)`: Register a broker builder.
*   `unregister_broker(name)`: Unregister a broker.
*   `get_broker_builder(name)`: Resolve a broker builder.
*   `list_registered_brokers()`: List currently registered brokers.

**Builder signature:**

```python
def builder(
    feed: DataFeed,
    symbols: Sequence[str],
    use_aggregator: bool,
    **kwargs: Any,
) -> GatewayBundle:
    ...
```

**Example:**

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

## 4. Trading Objects

### `akquant.Order`

*   `id`: Order ID.
*   `symbol`: Instrument symbol.
*   `side`: `OrderSide.Buy` / `OrderSide.Sell`.
*   `order_type`: `OrderType.Market` / `OrderType.Limit` etc.
*   `status`: `OrderStatus.New` / `Filled` / `Cancelled` etc.
*   `quantity` / `filled_quantity`: Order / Filled quantity.
*   `average_filled_price`: Average filled price.

### `akquant.Instrument`

Contract definition.

```python
Instrument(
    symbol="AAPL",
    asset_type=AssetType.Stock,
    multiplier=1.0,
    margin_ratio=1.0,
    tick_size=0.01,
    option_type=None,
    strike_price=None,
    expiry_date=None,
    lot_size=1,
    underlying_symbol=None,
    settlement_type=None
)
```

## 5. Portfolio & Risk

### `akquant.RiskConfig`

Risk configuration.

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

    # Account Level Risk
    max_account_drawdown: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_threshold: Optional[float] = None
```

Account-level field semantics:

*   `max_account_drawdown`: Maximum drawdown limit in 0~1 ratio. Drawdown is measured against historical peak equity; once breached, new order requests are rejected.
*   `max_daily_loss`: Daily loss limit in 0~1 ratio. Loss is measured against equity at the first risk check of the trading day; once breached, new order requests are rejected.
*   `stop_loss_threshold`: Equity stop-loss threshold in 0~1 ratio. If current equity falls below `baseline_equity_at_rule_activation * threshold`, new order requests are rejected.

Rejection reasons are available in `orders_df.reject_reason`.

## 6. Analysis

### `akquant.BacktestResult`

Backtest result object.

**Properties:**

*   `metrics_df`: Performance metrics DataFrame.
*   `trades_df`: Trade history DataFrame.
*   `orders_df`: Order history DataFrame.
*   `positions_df`: Daily position details.
*   `equity_curve`: Equity curve.
*   `cash_curve`: Cash curve.

**Analysis Methods:**

*   `exposure_df(freq="D")`: Portfolio exposure decomposition (net/gross/leverage).
*   `attribution_df(by="symbol", use_net=True, top_n=None)`: Grouped attribution by symbol/tag.
*   `capacity_df(freq="D")`: Capacity proxy metrics (order count, fill rates, turnover).
*   `orders_by_strategy()`: Strategy-ownership order aggregation by `owner_strategy_id`.
*   `executions_by_strategy()`: Strategy-ownership execution aggregation by `owner_strategy_id`.

```python
orders_by_strategy = result.orders_by_strategy()
executions_by_strategy = result.executions_by_strategy()

# Common columns
# orders_by_strategy:
# - owner_strategy_id, order_count, filled_order_count,
#   ordered_quantity, filled_quantity, ordered_value, filled_value,
#   fill_rate_qty, fill_rate_value
#
# executions_by_strategy:
# - owner_strategy_id, execution_count, total_quantity,
#   total_notional, total_commission, avg_fill_price
```
