# Strategy Guide

This document aims to help strategy developers quickly master how to write strategies in AKQuant.

## 1. Core Concepts (Glossary)

For those new to quantitative trading, here are some basic terms:

*   **Bar (Candlestick)**: Contains market data for a specific time period (e.g., 1 minute, 1 day), primarily including 5 data points:
    *   **Open**: Opening price
    *   **High**: Highest price
    *   **Low**: Lowest price
    *   **Close**: Closing price
    *   **Volume**: Trading volume
*   **Strategy**: Your trading robot. Its core job is to continuously watch the market (`on_bar`) and then decide whether to `buy` or `sell`.
*   **Context**: The robot's "notebook" and "toolbox". It records how much cash and how many positions are currently held, and provides tools for placing orders.
*   **Position**: The quantity of stocks or futures you currently hold. A positive number indicates a long position (buying to hold), and a negative number indicates a short position (selling borrowed securities).
*   **Backtest**: Historical simulation. Testing your strategy using past data to see how much money it would have made if executed in the past.

## 2. Strategy Lifecycle

A strategy goes through the following stages from start to finish:

*   `__init__`: Python object initialization, suitable for defining parameters.
*   `on_start`: Called when the strategy starts. You **must** use `self.subscribe()` here to subscribe to data, and you can also register indicators here.
*   `on_bar`: Triggered when each Bar closes (core trading logic).
*   `on_tick`: Triggered when each Tick arrives (high-frequency/order book strategies).
*   `on_order`: Triggered when order status changes (e.g., Submitted, Filled, Cancelled).
*   `on_trade`: Triggered when a trade execution report is received.
*   `on_reject`: Triggered when an order enters `Rejected` status.
*   `on_session_start` / `on_session_end`: Triggered on session transitions.
*   `before_trading` / `after_trading`: Daily trading hooks.
*   `on_portfolio_update`: Triggered when portfolio snapshot changes.
*   `on_error`: Triggered when user callback raises an exception, then exception is re-raised by default.
*   `on_timer`: Called when a timer triggers (needs manual registration).
    > Recommended: Use `self.add_daily_timer("14:55:00", "payload")`.
*   `on_stop`: Called when the strategy stops, suitable for resource cleanup or result statistics (refer to Backtrader `stop` / Nautilus `on_stop`).
*   `on_train_signal`: Triggered for rolling training signals (only in ML mode).

### 2.1 Callback Dispatch Contract

For each `bar/tick/timer` event, AKQuant dispatches callbacks in this order:

1. `on_order` / `on_trade` (plus `on_reject` when status is `Rejected`)
2. Framework hooks (`on_session_*`, `before_trading`/`after_trading`, `on_portfolio_update`)
3. User event callback (`on_bar` / `on_tick` / `on_timer`)

Notes:

* `on_reject` is emitted once per order id when the order first becomes `Rejected`.
* `before_trading` is emitted once per local trading date when session enters `Normal`.
* `after_trading` is emitted once per local trading date when leaving `Normal`, or on next event if day rollover occurs first.
* Set `self.enable_precise_day_boundary_hooks = True` to enable boundary-timer based precise day hooks.
* `on_portfolio_update` is incremental: emitted once at initialization, then only on order/trade or position-relevant price changes.
* Use `self.portfolio_update_eps` to filter tiny equity/cash changes (default `0.0`).
* During stop phase, pending `on_session_end` / `after_trading` are flushed before `on_stop`.
* `on_error` receives `(error, source, payload)`. Prefer `self.error_mode = "raise" | "continue"` (default `raise`). `self.re_raise_on_error` remains as fallback for compatibility.
* Prefer `self.runtime_config = StrategyRuntimeConfig(...)` as a unified runtime switch entry.
* Legacy alias fields and `runtime_config` stay synchronized automatically.

## 3. Utilities

AKQuant provides a set of utilities to simplify strategy development.

### 3.1 Logging

Use `self.log()` to output logs with the current **backtest timestamp**, which is useful for debugging.

```python
def on_bar(self, bar):
    # Automatically adds timestamp, e.g., [2023-01-01 09:30:00] Signal: Buy
    self.log("Signal: Buy")

    # Support logging level
    import logging
    self.log("Insufficient funds", level=logging.WARNING)
```

### 3.2 Data Access (Syntactic Sugar)

The `Strategy` class provides properties for quick access to current Bar/Tick data:

| Property | Description | Original Code |
| :--- | :--- | :--- |
| `self.symbol` | Current symbol | `bar.symbol` / `tick.symbol` |
| `self.close` | Current price | `bar.close` / `tick.price` |
| `self.open` | Current open price | `bar.open` (0 in Tick mode) |
| `self.high` | Current high price | `bar.high` (0 in Tick mode) |
| `self.low` | Current low price | `bar.low` (0 in Tick mode) |
| `self.volume` | Current volume | `bar.volume` / `tick.volume` |

**Example**:
```python
def on_bar(self, bar):
    # Old way
    if bar.close > bar.open: ...

    # New way (Cleaner)
    if self.close > self.open:
        self.buy(self.symbol, 100)
```

### 3.3 Timer

In addition to the low-level `schedule` method, AKQuant provides more convenient ways to register timers:

*   **`add_daily_timer(time_str, payload)`**: Triggers daily at a specified time.
    *   **Live Mode Supported**: Pre-generates triggers in Backtest mode; Automatically schedules the next trigger daily in Live mode.
*   **`schedule(trigger_time, payload)`**: Triggers once at a specified datetime.

```python
def on_start(self):
    # Daily check at 14:55:00
    self.add_daily_timer("14:55:00", "daily_check")

    # Specific event
    self.schedule("2023-01-01 09:30:00", "special_event")

def on_timer(self, payload):
    if payload == "daily_check":
        self.log("Running daily check...")
```

### 3.4 Recommended Cross-Section Pattern

AKQuant triggers `on_bar` in single-event flow. For cross-sectional tasks such as rotation, ranking, and scoring across symbols, place decision logic in `on_timer`.

Recommended flow:

1. Define the `universe` in `on_start` and register a daily timer.
2. Compute cross-sectional scores in `on_timer`.
3. Rebalance in `on_timer` so each decision timestamp runs once.

```python
class CrossSectionStrategy(Strategy):
    def __init__(self, lookback=20):
        self.lookback = lookback
        self.universe = ["sh600519", "sz000858", "sh601318"]
        self.warmup_period = lookback + 1

    def on_start(self):
        self.add_daily_timer("14:55:00", "rebalance")

    def on_timer(self, payload):
        if payload != "rebalance":
            return
        scores = {}
        for symbol in self.universe:
            closes = self.get_history(count=self.lookback, symbol=symbol, field="close")
            if len(closes) < self.lookback:
                return
            scores[symbol] = (closes[-1] - closes[0]) / closes[0]
        best = max(scores, key=scores.get)
        self.order_target_percent(target_percent=0.95, symbol=best)
```

Full runnable sample: `examples/strategies/05_stock_momentum_rotation_timer.py`.

### 3.5 Cross-Section Plan B: Execute After Collecting One Timestamp

If your strategy has no fixed rebalance time and `on_timer` is not convenient, collect symbols by timestamp in `on_bar`, then run cross-sectional logic once when the slice is complete.

```python
from collections import defaultdict

class CrossSectionBucketStrategy(Strategy):
    def __init__(self, lookback=20):
        self.lookback = lookback
        self.universe = ["sh600519", "sz000858", "sh601318"]
        self.warmup_period = lookback + 1
        self.pending = defaultdict(set)

    def on_bar(self, bar):
        self.pending[bar.timestamp].add(bar.symbol)
        if len(self.pending[bar.timestamp]) < len(self.universe):
            return
        self.pending.pop(bar.timestamp, None)
        scores = {}
        for symbol in self.universe:
            closes = self.get_history(count=self.lookback, symbol=symbol, field="close")
            if len(closes) < self.lookback:
                return
            scores[symbol] = (closes[-1] - closes[0]) / closes[0]
        best = max(scores, key=lambda s: scores[s])
        self.order_target_percent(target_percent=0.95, symbol=best)
```

Full runnable sample: `examples/strategies/06_stock_momentum_rotation_bucket.py`.

### 3.6 Decision Matrix (A vs B)

| Dimension | Plan A: Unified `on_timer` | Plan B: Execute after timestamp completion |
| :--- | :--- | :--- |
| Trigger | Fixed rebalance time (e.g., 14:55) | Event-driven, when one slice is complete |
| Robustness | High, independent from symbol arrival order | Medium, needs buffering and missing-symbol handling |
| Complexity | Low, centralized decision path | Medium, requires `timestamp -> symbols` state |
| Best for | Daily/timed rebalances, production default | Cross-section without stable rebalance time |
| Common risk | Timer time not aligned with data frequency | Missing symbols can prevent trigger |

Recommendation: use Plan A by default; use Plan B only when a stable rebalance time cannot be defined.

### 3.7 Cross-Section Pitfall Checklist

*   **Suspensions / missing bars**: Plan B may not trigger if some symbols have no bar at a timestamp; add timeout fallback or minimum-valid-sample execution.
*   **Universe drift**: If constituents change but your universe list is stale, weights and ranks diverge from target; refresh periodically and track effective date.
*   **Rebalance time vs execution mode mismatch**: With `execution_mode="next_open"`, close-time signals are filled on the next bar; under `current_close`, also define `timer_execution_policy` (or `fill_policy.temporal`) to make timer fill timing explicit.
*   **Insufficient history windows**: Newly listed or recently resumed symbols may fail window requirements; check `len(closes)` and skip invalid samples.
*   **Position convergence lag**: Multi-asset sell-then-buy cycles can leave partial allocations in one event; use target-position APIs and converge again on next cycle.

For full pre-live checks, see: [Cross-Section Strategy Playbook Checklist](cross_section_checklist.md).

## 4. Choosing a Strategy Style {: #style-selection }

AKQuant provides two styles of strategy development interfaces:

For style selection guidance, see [Strategy Style Decision Guide](../advanced/strategy_style_decision.md).

| Feature | Class-based Style (Recommended) | Function-based Style |
| :--- | :--- | :--- |
| **Definition** | Inherit from `akquant.Strategy` | Define `initialize` + `on_bar` (required), optional `on_start` / `on_stop` / `on_tick` / `on_order` / `on_trade` / `on_timer` |
| **Scenarios** | Complex strategies, need to maintain internal state, production | Rapid prototyping, migrating Zipline/Backtrader strategies |
| **Structure** | Object-oriented, good logic encapsulation | Script-like, simple and intuitive |
| **API Call** | `self.buy()`, `self.ctx` | `ctx.buy()`, pass `ctx` as parameter |

### 4.1 Function-style Callback Trigger Conditions

| Callback | Trigger Condition | Notes |
| :--- | :--- | :--- |
| `on_bar(ctx, bar)` | Backtest feed emits Bar events | Required entry callback for function-style strategies |
| `on_start(ctx)` | Backtest starts | Aligns with class-style `on_start` lifecycle |
| `on_stop(ctx)` | Backtest ends | Aligns with class-style `on_stop` lifecycle |
| `on_tick(ctx, tick)` | Backtest feed emits Tick events | Tick callbacks are not triggered in bar-only datasets |
| `on_order(ctx, order)` | Order state changes are observed in strategy context | Triggered before event callback in each event loop |
| `on_trade(ctx, trade)` | Trade reports appear in `recent_trades` | Trade dedupe applies to avoid repeated callbacks |
| `on_timer(ctx, payload)` | A timer is scheduled and fired | Includes both one-shot and daily timer payloads |

### 4.2 Related Examples

*   Function-style callback baseline: `examples/23_functional_callbacks_demo.py`
*   Function-style tick callback simulation: `examples/24_functional_tick_simulation_demo.py`
*   LiveRunner supports function-style entry and multi-slot orchestration: `LiveRunner(strategy_cls=on_bar, strategy_id="alpha", strategies_by_slot={"beta": OtherStrategy}, initialize=..., on_tick=..., on_order=..., on_trade=..., on_timer=...)`
*   For backtest multi-slot and strategy-level risk mapping, prefer centralized `BacktestConfig(strategy_config=StrategyConfig(...))`: `docs/en/advanced/multi_strategy_guide.md`
*   broker_live function-style submit example: `examples/39_live_broker_submit_order_demo.py`
*   Function-style multi-slot + risk example: `examples/40_functional_multi_slot_risk_demo.py`
*   LiveRunner multi-slot orchestration example: `examples/41_live_multi_slot_orchestration_demo.py`
*   Output markers:
    *   `done_functional_callbacks_demo`
    *   `done_functional_tick_simulation_demo`

## 4. Writing Class-based Strategies {: #class-based }

This is the recommended way to write strategies in AKQuant, offering a clear structure and easy extensibility.

```python
from akquant import Strategy, Bar
import numpy as np

class MyStrategy(Strategy):
    def __init__(self, ma_window=20):
        # Note: The Strategy class uses __new__ for initialization, subclasses do not need to call super().__init__()
        self.ma_window = ma_window

    def on_start(self):
        # Explicitly subscribe to data
        self.subscribe("600000")

    def on_bar(self, bar: Bar):
        # 1. Get historical data (Online mode)
        # Get the last N closing prices
        history = self.get_history(count=self.ma_window, symbol=bar.symbol, field="close")

        # Check if data is sufficient
        if len(history) < self.ma_window:
            return

        # Calculate Moving Average
        ma_value = np.mean(history)

        # 2. Trading Logic
        # Get current position
        pos = self.get_position(bar.symbol)

        if bar.close > ma_value and pos == 0:
            self.buy(symbol=bar.symbol, quantity=100)
        elif bar.close < ma_value and pos > 0:
            self.sell(symbol=bar.symbol, quantity=100)
```

## 5. Orders & Execution

### 4.1 Order Lifecycle

In AKQuant, order status transitions are as follows:

1.  **New**: Order object is created.
2.  **Submitted**: Order has been sent to the exchange/simulation matching engine.
3.  **Accepted**: (Live mode) Exchange confirms receipt of the order.
4.  **Filled**: Order is fully filled.
    *   **PartiallyFilled**: Partially filled (`filled_quantity < quantity`).
5.  **Cancelled**: Order has been cancelled.
6.  **Rejected**: Order rejected by risk control or exchange (e.g., insufficient funds, exceeding price limits).

### 5.2 Common Trading Commands

*   **Market Order**:
    ```python
    self.buy(symbol="AAPL", quantity=100) # Market Buy
    self.sell(symbol="AAPL", quantity=100) # Market Sell
    ```
*   **Limit Order**:
    Executes at a specified price, only when the market price is at or better than the specified price.
    ```python
    self.buy(symbol="AAPL", quantity=100, price=150.0) # Limit Buy at 150
    ```
*   **Stop Order**:
    Converts to a market order when the market price touches the trigger price (`trigger_price`).
    ```python
    # Stop Sell (Market) when price drops below 140
    self.stop_sell(symbol="AAPL", quantity=100, trigger_price=140.0)
    ```
*   **Target Orders**:
    Automatically calculates buy/sell quantities to adjust the position to a target value.
    ```python
    # Adjust position to 50% of total assets
    self.order_target_percent(target_percent=0.5, symbol="AAPL", price=None)

    # Adjust holding to 1000 shares (Buy 1000 if 0, Sell 1000 if 2000)
    self.order_target_value(target_value=1000 * price, symbol="AAPL") # Note: API does not support target_share directly yet, simulate with value
    ```
    Rebalance multiple symbols with a single target-weight call:
    ```python
    self.order_target_weights(
        target_weights={"AAPL": 0.4, "MSFT": 0.3, "GOOGL": 0.2},
        liquidate_unmentioned=True,
        rebalance_tolerance=0.01,
    )
    ```
    By default the sum of weights must be `<= 1.0`; set `allow_leverage=True` to allow higher aggregate exposure.
    Orders are submitted sell-first and then buy-second to reduce cash-lock conflicts during rotation.
*   **Cancel Order**:
    ```python
    self.cancel_order(order_id) # Cancel specific order
    self.cancel_all_orders()    # Cancel all open orders
    ```

### 5.3 Execution Modes

Set via `engine.set_execution_mode(mode)` (or pass `execution_mode` parameter in `run_backtest`):

*   **NextOpen (Default)**: Signals are matched at the Open of the *next* Bar. This is a more rigorous backtesting method, aligning with live trading logic (place order after today's close, match at tomorrow's open).
*   **CurrentClose**: Signals are matched immediately at the Close of the *current* Bar. Suitable for special strategies using closing prices for settlement, or scenarios where next-day data is unavailable.

### 5.4 Event Callbacks {: #callbacks }

AKQuant provides a callback mechanism similar to Backtrader for tracking order status and trade records.

#### 5.4.1 Order Status Callback (`on_order`)

Triggered when order status changes (e.g., from `New` to `Submitted`, or to `Filled`).

```python
from akquant import OrderStatus

def on_order(self, order):
    if order.status == OrderStatus.Filled:
        print(f"Order Filled: {order.symbol} Side: {order.side} Qty: {order.filled_quantity}")
    elif order.status == OrderStatus.Cancelled:
        print(f"Order Cancelled: {order.id}")
```

#### 5.4.2 Trade Execution Callback (`on_trade`)

Triggered when a real trade occurs. Unlike `on_order`, `on_trade` contains specific execution price, quantity, and commission information.

```python
def on_trade(self, trade):
    print(f"Trade Execution: {trade.symbol} Price: {trade.price} Qty: {trade.quantity} Comm: {trade.commission}")
```

### 5.5 Account & Position Query

In addition to `get_position`, you can query more account information:

*   **`self.equity`**: Current account equity (Cash + Market Value of Positions).
*   **`self.get_trades()`**: Get all historical closed trades.
*   **`self.get_open_orders()`**: Get current open orders.
*   **`self.get_available_position(symbol)`**: Get available position (considering T+1 rule).

## 6. Risk Management

AKQuant has a built-in Rust-level risk manager that can simulate exchange or broker risk control rules during backtesting.

```python
from akquant import RiskConfig

# Set after Engine initialization
risk_config = RiskConfig()
risk_config.active = True
risk_config.max_order_value = 1_000_000.0  # Max 1 million per order
risk_config.max_position_size = 5000       # Max 5000 shares per symbol
risk_config.restricted_list = ["ST_STOCK"] # Blacklist (Symbol)
risk_config.max_account_drawdown = 0.20    # Reject new orders after 20% drawdown
risk_config.max_daily_loss = 0.05          # Reject new orders after 5% daily loss
risk_config.stop_loss_threshold = 0.80     # Reject new orders if equity < 80% baseline

engine.risk_manager.config = risk_config # Apply config
```

If an order violates risk rules, functions like `self.buy()` will return `None` or the generated order status will be directly `Rejected`, and the reason will be recorded in the logs.

You can also pass account-level rules directly in `run_backtest`:

```python
from akquant import run_backtest
from akquant.config import RiskConfig

result = run_backtest(
    data=data,
    strategy=MyStrategy,
    risk_config=RiskConfig(
        max_account_drawdown=0.20,
        max_daily_loss=0.05,
        stop_loss_threshold=0.80,
    ),
)
```

Suggested account-level presets (starting points):

| Profile | `max_account_drawdown` | `max_daily_loss` | `stop_loss_threshold` |
| :--- | :--- | :--- | :--- |
| Conservative | `0.10` | `0.02` | `0.90` |
| Balanced | `0.20` | `0.05` | `0.80` |
| Aggressive | `0.30` | `0.08` | `0.70` |

Start from the balanced preset, then tighten or loosen values based on observed volatility and turnover.

## 6. Using High-Performance Indicators {: #indicatorset }

AKQuant includes commonly used technical indicators built into the Rust layer. They use Incremental Calculation to avoid repeated full recalculations, resulting in extremely high performance.

Supported Indicators: `SMA`, `EMA`, `MACD`, `RSI`, `BollingerBands`, `ATR`.

### 7.1 Registration and Usage

AKQuant follows a dual-platform and single-strategy style. Each strategy must explicitly set `indicator_mode` and use the matching registration API:

* `indicator_mode="precompute"` + `register_precomputed_indicator(...)`
* `indicator_mode="incremental"` + `register_incremental_indicator(...)`

```python
from akquant import Bar, SMA, Strategy

class IndicatorStrategy(Strategy):
    def __init__(self):
        self.indicator_mode = "precompute"
        self.sma20 = SMA(20)
        self.register_precomputed_indicator("sma20", self.sma20)

    def on_start(self):
        self.subscribe("AAPL")

    def on_bar(self, bar: Bar):
        val = self.sma20.get_value(bar.symbol, bar.timestamp)
        if bar.close > val:
            self.buy(bar.symbol, 100)
```

```python
from akquant import Bar, SMA, Strategy

class IncrementalIndicatorStrategy(Strategy):
    def __init__(self):
        self.indicator_mode = "incremental"
        self.sma20 = SMA(20)
        self.register_incremental_indicator(
            "sma20",
            self.sma20,
            source="close",
            symbols=["AAPL"],
        )

    def on_bar(self, bar: Bar):
        if bar.symbol != "AAPL":
            return
        val = self.sma20.value
        if val is None:
            return
        if bar.close > val:
            self.buy(bar.symbol, 100)
```

## 7. Strategy Cookbook

### 7.1 Trailing Stop

```python
class TrailingStopStrategy(Strategy):
    def __init__(self):
        self.highest_price = 0.0
        self.trailing_percent = 0.05 # 5% trailing stop

    def on_bar(self, bar):
        pos = self.get_position(bar.symbol)

        if pos > 0:
            # Update highest price
            self.highest_price = max(self.highest_price, bar.high)

            # Check drawdown
            drawdown = (self.highest_price - bar.close) / self.highest_price
            if drawdown > self.trailing_percent:
                print(f"Trailing Stop Triggered: High {self.highest_price}, Current {bar.close}")
                self.close_position(bar.symbol)
                self.highest_price = 0.0 # Reset
        else:
            # Entry logic (Example)
            if bar.close > 100:
                self.buy(bar.symbol, 100)
                self.highest_price = bar.close # Initialize highest price
```

### 7.2 Intraday Exit

```python
class IntradayStrategy(Strategy):
    def on_bar(self, bar):
        # Assuming bar.timestamp is nanosecond timestamp
        # Convert to datetime (requires import datetime)
        dt = datetime.fromtimestamp(bar.timestamp / 1e9)

        # Force exit at 14:55 daily
        if dt.hour == 14 and dt.minute >= 55:
            if self.get_position(bar.symbol) != 0:
                self.close_position(bar.symbol)
            return

        # Other trading logic...
```

### 7.3 OCO and Bracket Helpers

AKQuant provides helper APIs for linked order management:

*   `self.create_oco_order_group(first_order_id, second_order_id, group_id=None)`
    *   Binds two orders as OCO (One-Cancels-the-Other).
    *   Once either order is filled, the peer order is canceled automatically.
*   `self.place_bracket_order(symbol, quantity, entry_price=None, stop_trigger_price=None, take_profit_price=None, ...)`
    *   Submits a bracket structure in one call.
    *   After entry fill, stop-loss and take-profit exits are submitted automatically; when both exits exist, they are linked as OCO.

```python
from akquant import OrderStatus, Strategy

class BracketHelperStrategy(Strategy):
    def __init__(self):
        self.entry_order_id = ""

    def on_bar(self, bar):
        if self.get_position(bar.symbol) > 0 or self.entry_order_id:
            return

        self.entry_order_id = self.place_bracket_order(
            symbol=bar.symbol,
            quantity=100,
            stop_trigger_price=bar.close * 0.98,
            take_profit_price=bar.close * 1.04,
            entry_tag="entry",
            stop_tag="stop",
            take_profit_tag="take",
        )

    def on_order(self, order):
        if order.id == self.entry_order_id and order.status in (
            OrderStatus.Cancelled,
            OrderStatus.Rejected,
        ):
            self.entry_order_id = ""
```

### 7.4 Trailing Stop Helpers

If you want to express a moving stop line directly in strategy logic, use these helpers:

*   `self.place_trailing_stop(symbol, quantity, trail_offset, side="Sell", trail_reference_price=None, ...)`
    *   Executes as market order after trigger (`StopTrail -> Market`).
*   `self.place_trailing_stop_limit(symbol, quantity, price, trail_offset, side="Sell", trail_reference_price=None, ...)`
    *   Executes as limit order after trigger (`StopTrailLimit -> Limit`).

```python
from akquant import Strategy

class TrailingHelperStrategy(Strategy):
    def __init__(self):
        self.trailing_order_id = ""

    def on_bar(self, bar):
        if self.get_position(bar.symbol) == 0:
            self.buy(bar.symbol, 100)
            self.trailing_order_id = self.place_trailing_stop(
                symbol=bar.symbol,
                quantity=100,
                trail_offset=1.5,
                side="Sell",
                trail_reference_price=bar.close,
                tag="trail-stop",
            )
```

For a full runnable script, see `examples/36_trailing_orders.py`.

### 7.5 Multi-Asset Rotation {: #multi-asset }

```python
class RotationStrategy(Strategy):
    def on_bar(self, bar):
        # Note: on_bar is triggered for each symbol
        # If cross-sectional comparison is needed, it is recommended to process in on_timer or after collecting all bars
        # This shows simple independent processing
        pass

    def on_timer(self, payload):
        # Assume a daily timer is registered
        # Get current prices of all subscribed symbols
        scores = {}
        # Actually should iterate over watchlist or subscribed symbols
        # Note: self.ctx.positions contains current positions, but we might want to check all watched symbols
        for symbol in self.ctx.positions.keys():
             hist = self.get_history(20, symbol)
             scores[symbol] = hist[-1] / hist[0] # 20-day momentum

        # Sort and rebalance...
```

## 8. Mixed Asset Backtesting Configuration

AKQuant supports mixed trading of multiple assets such as stocks, futures, and options within the same strategy. Different assets usually have different attributes (e.g., contract multiplier, margin ratio, tick size).

Using `InstrumentConfig` allows you to conveniently configure these attributes for each instrument.

### 8.1 Configuration Steps

1.  **Prepare Data**: Prepare data (DataFrame or CSV) for each instrument.
2.  **Create Config**: Use `InstrumentConfig` to define parameters for non-stock assets.
3.  **Run Backtest**: Pass the configuration to the `instruments_config` parameter of `run_backtest`.

### 8.2 Configuration Example

Suppose we want to backtest a portfolio containing "Stock A" and "Stock Index Futures IF":

```python
from akquant import BacktestConfig, InstrumentConfig, run_backtest

# 1. Define Futures Configuration
future_config = InstrumentConfig(
    symbol="IF2301",          # Instrument Symbol
    asset_type="FUTURES",     # Asset Type: STOCK, FUTURES, OPTION
    multiplier=300.0,         # Contract Multiplier (300 per point)
    margin_ratio=0.1,         # Margin Ratio (10%)
    tick_size=0.2             # Tick Size
)

# 2. Run Backtest
# Note: Unconfigured instruments (e.g., STOCK_A) will use default parameters (Stock, Multiplier 1, Margin 100%)
config = BacktestConfig(instruments_config=[future_config])
run_backtest(
    data=data_dict,
    strategy=MyStrategy,
    config=config, # Pass config object
    # ...
)
```

For detailed code, please refer to the [Mixed Asset Backtest Example](examples.md).
