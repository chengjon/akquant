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
    **kwargs: Any,
) -> BacktestResult
```

**Key Parameters:**

*   `data`: Backtest data. Supports a single DataFrame, or a `{symbol: DataFrame}` dictionary.
*   `strategy`: Strategy class or instance. Also supports passing an `on_bar` function (functional style).
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
3.  **Defaults**:
    *   If neither provides a value, system defaults are used.

#### 3. Risk Config Merging

The `risk_config` parameter has special handling logic designed to support a "Baseline + Override" pattern:

*   **Baseline**: First loads `config.strategy_config.risk` (if it exists).
*   **Override**: If `risk_config` parameter (dict or object) is provided, it overrides fields in the baseline configuration.
    *   This allows you to quickly adjust risk parameters for testing without modifying the main Config object, e.g., `run_backtest(..., risk_config={"max_position_pct": 0.5})`.

#### 4. Best Practices

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
*   `on_timer(payload: str)`: Triggered by timer.
*   `on_stop()`: Triggered when the strategy stops.
*   `on_train_signal(context)`: Triggered by rolling training signal (ML mode).

**Properties & Shortcuts:**

*   `self.symbol`: The symbol currently being processed.
*   `self.close`, `self.open`, `self.high`, `self.low`, `self.volume`: Current Bar/Tick price and volume.
*   `self.position`: Position object for current symbol, with `size` and `available` properties.
*   `self.now`: Current backtest time (`pd.Timestamp`).

**Trading Methods:**

*   `buy(symbol, quantity, price=None, ...)`: Buy. Market order if `price` is not specified.
*   `sell(symbol, quantity, price=None, ...)`: Sell.
*   `short(symbol, quantity, price=None, ...)`: Short sell.
*   `cover(symbol, quantity, price=None, ...)`: Buy to cover.
*   `stop_buy(symbol, trigger_price, quantity, ...)`: Stop buy (Stop Market). Triggers a market buy order when price breaks above `trigger_price`.
*   `stop_sell(symbol, trigger_price, quantity, ...)`: Stop sell (Stop Market). Triggers a market sell order when price drops below `trigger_price`.
*   `order_target_value(target_value, symbol, price=None)`: Adjust position to target value.
*   `order_target_percent(target_percent, symbol, price=None)`: Adjust position to target account percentage.
*   `close_position(symbol)`: Close position for a specific instrument.
*   `cancel_order(order_id: str)`: Cancel a specific order.
*   `cancel_all_orders(symbol)`: Cancel all pending orders for a specific instrument. If `symbol` is omitted, cancels all orders.

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
