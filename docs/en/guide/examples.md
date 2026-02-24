# Examples Collection

## 1. Basic Examples

*   [Quick Start](../start/quickstart.md): Complete workflow covering manual data backtesting and AKShare data backtesting.
*   [Simple SMA Strategy](strategy.md#class-based): Demonstrates how to write a strategy in class style and perform simple trading logic in `on_bar`.

> Data Source Convention: Unless otherwise specified (e.g. simulated data), examples on this page default to using AKShare to fetch real market data.

## 2. Advanced Examples

*   **Zipline Style Strategy**: Demonstrates how to write strategies using functional API (`initialize`, `on_bar`), suitable for users migrating from Zipline.
    *   Refer to [Strategy Guide](strategy.md#style-selection).

*   **Multi-Asset Backtest**:
    *   **Futures Strategy**: Demonstrates futures backtest configuration (margin, multiplier). Refer to [Strategy Guide](strategy.md#multi-asset).
    *   **Option Strategy**: Demonstrates option backtest configuration (premium, per contract fee). Refer to [Strategy Guide](strategy.md#multi-asset).

*   **Vectorized Indicators**:
    *   Demonstrates how to use `IndicatorSet` to pre-calculate indicators to improve backtest speed. Refer to [Strategy Guide](strategy.md#indicatorset).

### Fetching A-Share Daily Data with AKShare (stock_zh_a_daily)

```python
import akshare as ak
import pandas as pd
from akquant import run_backtest

df = ak.stock_zh_a_daily(symbol="sz000001", adjust="qfq")
if "date" not in df.columns:
    df = df.reset_index().rename(columns={"index": "date"})
df.columns = [c.lower() for c in df.columns]
if "time" in df.columns and "date" not in df.columns:
    df = df.rename(columns={"time": "date"})
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize("Asia/Shanghai")
df["symbol"] = "000001"
cols = ["date", "open", "high", "low", "close", "volume", "symbol"]
df = df[cols].sort_values("date").reset_index(drop=True)

# result = run_backtest(data=df, strategy=DualSMAStrategy, lot_size=100)
```

## 3. Common Strategies

Here are some common quantitative strategy implementations that you can use directly in your projects. We provide detailed logic explanations for each strategy to help you understand the core concepts.

### 3.1 Dual Moving Average Strategy

[View Full Source](https://github.com/akfamily/akquant/blob/main/examples/strategies/01_stock_dual_moving_average.py)

**Core Concept**:
The Dual Moving Average strategy uses two moving averages (SMA) with different periods to determine market trends.

- **Golden Cross**: Short-term SMA crosses above Long-term SMA -> Buy.
- **Death Cross**: Short-term SMA crosses below Long-term SMA -> Sell.

**AKQuant Features**:

- Using `get_history` to fetch historical data (including current Bar).
- A-Share trading rules (1 lot = 100 shares).

```python
class DualMovingAverageStrategy(Strategy):
    def __init__(self, short_window=5, long_window=20):
        self.short_window = short_window
        self.long_window = long_window
        # Warmup period setting
        self.warmup_period = long_window

    def on_bar(self, bar):
        # Fetch historical data including current Bar
        closes = self.get_history(count=self.long_window, symbol=bar.symbol, field="close")

        if len(closes) < self.long_window:
            return

        # Calculate MAs
        short_ma = np.mean(closes[-self.short_window:])
        long_ma = np.mean(closes[-self.long_window:])

        current_pos = self.get_position(bar.symbol)

        # Golden Cross -> Buy
        if short_ma > long_ma and current_pos == 0:
            self.order_target_percent(symbol=bar.symbol, target_percent=0.95)

        # Death Cross -> Sell
        elif short_ma < long_ma and current_pos > 0:
            self.close_position(symbol=bar.symbol)
```

### 3.2 Grid Trading Strategy

[View Full Source](https://github.com/akfamily/akquant/blob/main/examples/strategies/02_stock_grid_trading.py)

**Core Concept**:
A mechanical trading strategy based on price fluctuations.

- **Buy Dip**: Buy a portion for every X% price drop.
- **Sell Rally**: Sell a portion for every X% price rise.
- **Suitable for**: Oscillating markets.

**AKQuant Features**:

- Managing custom state variables (`self.last_trade_price`) inside `on_bar`.
- Complex position management.

```python
class GridTradingStrategy(Strategy):
    def __init__(self, grid_pct=0.03, lot_size=100):
        self.grid_pct = grid_pct
        self.trade_lot = lot_size
        self.last_trade_price = {}

    def on_bar(self, bar):
        symbol = bar.symbol
        close = bar.close

        # Initial Position
        if symbol not in self.last_trade_price:
            self.buy(symbol=symbol, quantity=10 * self.trade_lot)
            self.last_trade_price[symbol] = close
            return

        last_price = self.last_trade_price[symbol]
        change_pct = (close - last_price) / last_price

        # Buy Dip
        if change_pct <= -self.grid_pct:
            self.buy(symbol=symbol, quantity=self.trade_lot)
            self.last_trade_price[symbol] = close

        # Sell Rally
        elif change_pct >= self.grid_pct:
            current_pos = self.get_position(symbol)
            if current_pos >= self.trade_lot:
                self.sell(symbol=symbol, quantity=self.trade_lot)
                self.last_trade_price[symbol] = close
```

### 3.3 ATR Breakout Strategy

[View Full Source](https://github.com/akfamily/akquant/blob/main/examples/strategies/03_stock_atr_breakout.py)

**Core Concept**:
Uses ATR (Average True Range) to build price channels and capture trend breakouts.

- **Upper Band**: Previous Close + k * ATR
- **Lower Band**: Previous Close - k * ATR
- **Breakout**: Price > Upper Band -> Buy.
- **Breakdown**: Price < Lower Band -> Sell.

**AKQuant Features**:

- **Avoiding Look-ahead Bias**: Use `get_history` and slice with `[:-1]` to exclude the current Bar, using strictly historical data to calculate today's breakout thresholds.

```python
class AtrBreakoutStrategy(Strategy):
    def __init__(self, period=20, k=2.0):
        self.period = period
        self.k = k
        self.warmup_period = period + 1

    def on_bar(self, bar):
        # Fetch N+1 data points
        req_count = self.period + 1
        h_closes = self.get_history(count=req_count, field="close")

        if len(h_closes) < req_count:
            return

        # Exclude current Bar (last element)
        closes = h_closes[:-1]

        # ... (ATR calculation logic) ...
        atr = calculate_atr(closes) # Pseudo-code

        # Calculate bands based on YESTERDAY's close
        prev_close = closes[-1]
        upper_band = prev_close + self.k * atr
        lower_band = prev_close - self.k * atr

        # Trading Logic
        if bar.close > upper_band:
            self.buy(quantity=500)
        elif bar.close < lower_band:
            self.close_position()
```

### 3.4 Momentum Rotation Strategy

[View Full Source](https://github.com/akfamily/akquant/blob/main/examples/strategies/04_stock_momentum_rotation.py)

**Core Concept**:
Hold the asset with the strongest recent momentum (return) among a pool of assets.

- Calculate momentum for candidates periodically (e.g., daily).
- Sell weak assets and buy the strongest one.

**AKQuant Features**:

- **Multi-Asset Data**: Passing `Dict[str, DataFrame]` to the engine.
- **Cross-Asset Comparison**: Iterating `self.symbols` and calling `get_history` for each.
- **Target Position**: Using `order_target_percent` for easy rotation.

```python
class MomentumRotationStrategy(Strategy):
    def __init__(self, lookback_period=20):
        self.lookback_period = lookback_period
        self.symbols = ["sh600519", "sz000858"] # Maotai vs Wuliangye
        self.warmup_period = lookback_period + 1

    def on_bar(self, bar):
        # Run rotation logic only once per day (on the last symbol)
        if bar.symbol != self.symbols[-1]:
            return

        # 1. Calculate Momentum
        momentums = {}
        for s in self.symbols:
            closes = self.get_history(count=self.lookback_period, symbol=s, field="close")
            # Momentum = (Current - Previous) / Previous
            mom = (closes[-1] - closes[0]) / closes[0]
            momentums[s] = mom

        # 2. Select Best
        best_symbol = max(momentums, key=momentums.get)

        # 3. Rotate
        current_pos_symbol = self.get_current_holding_symbol() # Pseudo-code

        if current_pos_symbol != best_symbol:
            if current_pos_symbol:
                self.close_position(current_pos_symbol)
            # Target 95% position
            self.order_target_percent(target_percent=0.95, symbol=best_symbol)
```

### 3.5 Use Adjusted Series for Signals, Real Prices for Execution

When your data provides `adj_close` or `adj_factor`, you can fetch adjusted series directly via `get_history(symbol=..., field="adj_close", n)` for signal computation, while matching and valuation still use real `close`. See `examples/16_adj_returns_signal.py`.

```python
class AdjSignal(Strategy):
    warmup_period = 5
    def on_bar(self, bar):
        try:
            x = self.get_history(2, bar.symbol, "adj_close")
        except Exception:
            return
        if x is None or len(x) < 2:
            return
        r = x[-1] / x[-2] - 1.0
        pos = self.get_position(bar.symbol)
        if pos == 0 and r > 0:
            self.buy(bar.symbol, 100)
        elif pos > 0 and r < 0:
            self.close_position(bar.symbol)
```

## 4. Other AKShare Examples

The `examples/` directory contains more scripts demonstrating AKShare integration:

*   **[11_plot_visualization.py](https://github.com/akfamily/akquant/blob/main/examples/11_plot_visualization.py)**:
    *   Complete workflow: Fetch data -> Backtest -> Visualize.
    *   Demonstrates how to generate professional HTML reports.

*   **[14_multi_frequency.py](https://github.com/akfamily/akquant/blob/main/examples/14_multi_frequency.py)**:
    *   **Mixed Frequency**: Combining Daily (for trend) and Minute (for execution) data.
    *   Note: Uses synthetic minute data derived from AKShare daily data for demonstration.

*   **[15_plot_intraday.py](https://github.com/akfamily/akquant/blob/main/examples/15_plot_intraday.py)**:
    *   **Intraday Simulation**: Generates synthetic minute-level data from AKShare daily data.
    *   Demonstrates high-frequency backtesting capabilities.

*   **[17_readme_demo.py](https://github.com/akfamily/akquant/blob/main/examples/17_readme_demo.py)**:
    *   A simple, standalone script for the README demonstration.
    *   Good for a quick "Hello World" test.
