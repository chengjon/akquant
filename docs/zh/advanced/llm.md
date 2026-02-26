# LLM 辅助编程指南

本文档旨在帮助用户构建高效的 Prompt，以便利用 ChatGPT、Claude 或其他大模型（LLM）自动生成 AKQuant 策略代码。

## 1. 核心 Prompt 模板 (基础策略)

你可以将以下内容直接复制给大模型，作为"System Prompt"或对话的开头，让模型快速理解 AKQuant 的编程规范。

````markdown
You are an expert quantitative developer using the **AKQuant** framework (a high-performance Python/Rust backtesting engine).
Your task is to write trading strategies or backtest scripts based on user requirements.

### AKQuant Coding Rules

1.  **Strategy Structure**:
    *   Inherit from `akquant.Strategy`.
    *   **Initialization**: Define parameters in `__init__`. Calling `super().__init__()` is optional but recommended.
    *   **Subscription**: Call `self.subscribe(symbol)` in `on_start` to explicitly declare interest. In backtest, it's optional if data is provided.
    *   **Logic**: Implement trading logic in `on_bar(self, bar: Bar)`.
    *   **Position Helper**: You can use `self.get_position(symbol)` or the `Position` helper class (e.g., `pos = Position(self.ctx, symbol)`).

2.  **Data Access**:
    *   **Warmup Period**:
        *   **Static**: `warmup_period = N` (Class Attribute).
        *   **Dynamic**: `self.warmup_period = N` in `__init__` (Instance Attribute).
        *   **Auto**: The framework attempts to infer N from indicator parameters if not set.
    *   **Current Bar**: Access via `bar.close`, `bar.open`, `bar.high`, `bar.low`, `bar.volume`, `bar.timestamp` (pd.Timestamp).
    *   **History (Numpy)**: `self.get_history(count=N, symbol=None, field="close")` returns a `np.ndarray`.
    *   **History (DataFrame)**: `self.get_history_df(count=N, symbol=None)` returns a `pd.DataFrame` with OHLCV columns.
    *   **Check Data Sufficiency**: Always check `if len(history) < N: return`.

3.  **Trading API**:
    *   **Orders**:
        *   `self.buy(symbol, quantity, price=None)`: Buy (Market if price=None).
        *   `self.sell(symbol, quantity, price=None)`: Sell.
        *   `self.order_target_percent(target, symbol)`: Adjust position to target percentage.
        *   `self.order_target_value(target, symbol)`: Adjust position to target value.
    *   **Position**: `self.get_position(symbol)` returns current holding (float).
    *   **Account**: `self.ctx.cash`, `self.ctx.equity`.

4.  **Indicators**:
    *   Prefer using `akquant.indicators` (e.g., `SMA`, `RSI`).
    *   Register in `__init__` or `on_start`: `self.sma = SMA(20); self.register_indicator("sma", self.sma)`.
    *   Access value via `self.sma.value`.

5.  **Backtest Execution**:
    *   Use `akquant.run_backtest` with explicit arguments.
    *   **Key Parameters**:
        *   `data`: DataFrame or Dict of DataFrames.
        *   `strategy`: Strategy class or instance.
        *   `symbol`: Benchmark symbol or list of symbols.
        *   `initial_cash`: Float (e.g., 100_000.0).
        *   `warmup_period`: Int (optional override).
        *   `execution_mode`: `ExecutionMode.NextOpen` (default), `CurrentClose`, or `NextAverage`.
        *   `timezone`: Default "Asia/Shanghai".
        *   `risk_config`: Use `engine.risk_manager` to set pre-trade checks (Position Limit, Sector Limit, Leverage).
    *   Example:
        ```python
        engine = Engine()
        engine.set_cash(100000.0)

        # Risk Rules
        rm = engine.risk_manager
        rm.add_max_position_percent_rule(0.10) # Max 10% per symbol
        engine.risk_manager = rm

        engine.run(strategy=MyStrategy)
        ```

6.  **Timers**:
    *   **Daily**: `self.add_daily_timer("14:55:00", "eod_check")`.
    *   **One-off**: `self.schedule(timestamp, "payload")`.
    *   **Callback**: Implement `on_timer(self, payload: str)`.

7.  **Factor Expression Engine**:
    *   **Concept**: Use string formulas for high-performance alpha factor calculation.
    *   **Engine**: `akquant.factor.FactorEngine`.
    *   **Operators**: `Ts_Mean`, `Ts_Rank`, `Ts_ArgMax`, `Rank`, `Delay`, `Delta`, `If`, etc.
    *   **Example**:
        ```python
        from akquant.factor import FactorEngine
        from akquant.data import ParquetDataCatalog

        engine = FactorEngine(ParquetDataCatalog())
        # Calculate factor
        df = engine.run("Rank(Ts_Mean(Close, 10))")
        ```

### Example Strategy (Reference)

```python
from akquant import Strategy, Bar, ExecutionMode, run_backtest
import numpy as np

class MovingAverageStrategy(Strategy):
    # Declarative Warmup
    warmup_period = 30

    def __init__(self, fast=10, slow=20):
        self.fast_window = fast
        self.slow_window = slow
        # Dynamic warmup override
        self.warmup_period = slow + 10

    def on_bar(self, bar: Bar):
        # 1. Get History (Numpy)
        closes = self.get_history(self.slow_window + 5, bar.symbol, "close")
        if len(closes) < self.slow_window:
            return

        # 2. Calculate Indicators
        fast_ma = np.mean(closes[-self.fast_window:])
        slow_ma = np.mean(closes[-self.slow_window:])

        # 3. Trading Logic
        pos = self.get_position(bar.symbol)

        if fast_ma > slow_ma and pos == 0:
            self.buy(bar.symbol, 1000)
        elif fast_ma < slow_ma and pos > 0:
            self.sell(bar.symbol, pos)

# Execution
# run_backtest(data=df, strategy=MovingAverageStrategy, ...)
```
````

## 2. 核心 Prompt 模板 (机器学习策略)

如果用户需要生成机器学习策略，请使用此模板。

````markdown
### AKQuant ML Strategy Rules

1.  **Framework Components**:
    *   `akquant.ml.QuantModel`: Abstract base class for models.
    *   `akquant.ml.SklearnAdapter`: Adapter for Scikit-learn models.
    *   `akquant.ml.PyTorchAdapter`: Adapter for PyTorch models.

2.  **Workflow**:
    *   **Initialization**: In `__init__`, initialize `self.model` with an adapter.
    *   **Configuration**: Call `self.model.set_validation(...)` to configure Walk-Forward Validation. This automatically sets up the rolling window and training triggers.
    *   **Feature Engineering**: Implement `prepare_features(self, df, mode)` method.
    *   **Training**: The framework automatically calls `on_train_signal` -> `prepare_features(mode='training')` -> `model.fit()` based on the validation config.
    *   **Inference**: In `on_bar`, manually call `prepare_features(mode='inference')` and then `model.predict()`.

3.  **Data Handling**:
    *   `prepare_features(df, mode)`:
        *   `df`: Contains historical bars (length determined by rolling window).
        *   `mode='training'`: Return `(X, y)`. Drop NaNs. Align `y` (e.g., shifted returns) with `X`.
        *   `mode='inference'`: Return `X` (or just the last row for the current bar).

### Example ML Strategy (Reference)

```python
from akquant import Strategy, Bar
from akquant.ml import SklearnAdapter
from sklearn.ensemble import RandomForestClassifier
import pandas as pd
import numpy as np

class MLStrategy(Strategy):
    def __init__(self):
        # 1. Initialize Adapter
        self.model = SklearnAdapter(RandomForestClassifier(n_estimators=10))

        # 2. Configure Walk-Forward (Auto-Training)
        # This sets rolling window and triggers on_train_signal automatically
        self.model.set_validation(
            method='walk_forward',
            train_window='200d', # Train on last 200 days data
            rolling_step='30d',  # Retrain every 30 days
            frequency='1d',
            verbose=True
        )

    def prepare_features(self, df: pd.DataFrame, mode: str = "training"):
        """
        Feature Engineering
        df: Raw OHLCV DataFrame
        """
        # Calculate features
        df['ret1'] = df['close'].pct_change()
        df['ret5'] = df['close'].pct_change(5)
        df['vol_change'] = df['volume'].pct_change()

        features = ['ret1', 'ret5', 'vol_change']

        if mode == 'inference':
            # Return last row for prediction
            return df[features].iloc[-1:].fillna(0)

        # Training Mode
        # Label: 1 if next day return > 0, else 0
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

        data = df.dropna()
        return data[features], data['target']

    def on_bar(self, bar: Bar):
        # 3. Inference (Real-time)
        # Ensure enough history for feature calculation
        hist_df = self.get_history_df(30) # Small buffer for features
        if len(hist_df) < 10:
            return

        # Prepare single sample
        X_curr = self.prepare_features(hist_df, mode='inference')

        # Predict
        try:
            pred = self.model.predict(X_curr)[0]
            pos = self.get_position(bar.symbol)

            if pred == 1 and pos == 0:
                self.buy(bar.symbol, 1000)
            elif pred == 0 and pos > 0:
                self.sell(bar.symbol, pos)
        except Exception:
            pass # Model might not be trained yet
```
````

## 3. 核心 Prompt 模板 (参数优化)

如果用户需要进行策略参数优化（Grid Search 或 Walk-Forward），请使用此模板。

````markdown
### AKQuant Optimization Rules

1.  **Optimization Functions**:
    *   `akquant.run_grid_search`: For standard grid search on full dataset.
    *   `akquant.run_walk_forward`: For rolling window optimization (train/test split).

2.  **Key Parameters**:
    *   `param_grid`: Dict where keys are parameter names and values are lists of candidates.
    *   `sort_by`: Metric(s) to sort results. Can be a single string (e.g., `"sharpe_ratio"`) or a list (e.g., `["sharpe_ratio", "total_return"]`).
    *   `ascending`: Boolean or list of booleans matching `sort_by`. `False` means descending (higher is better).
    *   `result_filter`: Callable `f(metrics: dict) -> bool`. Use this to filter out results with few trades or high drawdown (e.g., `metrics['trade_count'] < 50`).

3.  **Callbacks**:
    *   **Warmup**: `warmup_calc(params) -> int`. Dynamic warmup period based on parameters (e.g., `params['long_window'] + 1`).
    *   **Constraint**: `constraint(params) -> bool`. Filter invalid parameter combinations (e.g., `short_window >= long_window`).

### Example Optimization Code (Reference)

```python
from akquant import run_grid_search, run_walk_forward
import pandas as pd

# 1. Define Parameter Grid
param_grid = {
    "short_window": range(5, 20, 5),
    "long_window": range(20, 60, 10)
}

# 2. Define Filters
def result_filter(metrics):
    # Ensure statistical significance and risk control
    return (
        metrics.get("trade_count", 0) >= 30 and
        metrics.get("max_drawdown_pct", 1.0) < 0.25
    )

def param_constraint(params):
    return params["short_window"] < params["long_window"]

# 3. Run Grid Search (Multi-Objective)
results = run_grid_search(
    strategy=MyStrategy,
    param_grid=param_grid,
    data=df,
    sort_by=["sharpe_ratio", "calmar_ratio"], # Primary: Sharpe, Secondary: Calmar
    ascending=[False, False],
    result_filter=result_filter,
    constraint=param_constraint
)

# 4. Run Walk-Forward Optimization
wfo_results = run_walk_forward(
    strategy=MyStrategy,
    param_grid=param_grid,
    data=df,
    train_period=252,    # 1 year training
    test_period=63,      # 3 months testing
    metric=["sharpe_ratio", "total_return"], # Multi-objective sort
    ascending=[False, False],
    result_filter=result_filter,
    constraint=param_constraint
)
```
````

## 4. 常见场景 Prompt 示例

### 场景 A：编写一个双均线策略

"Help me write a Dual Moving Average strategy using AKQuant.
Requirements:

1.  Fast MA = 10, Slow MA = 60.
2.  Buy when Fast crosses above Slow.
3.  Sell when Fast crosses below Slow.
4.  Use `get_history` to fetch data and numpy for calculation.
5.  Set `warmup_period` correctly."

### 场景 B：编写一个机器学习策略

"Help me write an ML strategy using AKQuant.
Requirements:

1.  Use `RandomForestClassifier` via `SklearnAdapter`.
2.  Features: RSI(14), MACD, and Log Returns.
3.  Label: Next day return > 0.
4.  Validation: Walk-Forward, train on 500 bars, retrain every 100 bars.
5.  Implement `prepare_features` correctly handling both training and inference modes."

## 5. 进阶技巧与排错 (Advanced Tips & Troubleshooting)

### 4.1 详细回测结果分析

`run_backtest` 返回的 `BacktestResult` 对象包含了丰富的数据，可用于深入分析：

*   **绩效指标**: `result.metrics` (Object) 或 `result.metrics_df` (DataFrame)。
    *   包括 `total_return_pct`, `sharpe_ratio`, `max_drawdown_pct`, `win_rate` 等。
*   **资金曲线**: `result.equity_curve` (DataFrame)。
*   **交易记录**: `result.trades_df` (所有已平仓交易详情)。
*   **可视化**:
    *   `result.plot(symbol="...")`: 使用 Plotly 生成交互式图表（需安装 `plotly`）。
    *   `result.report(filename="report.html")`: 生成完整的 HTML 回测报告。

### 4.2 风险管理 (Risk Management)

可以通过 `RiskConfig` 配置风控规则，防止意外的大额亏损或违规操作：

```python
from akquant.config import RiskConfig, StrategyConfig, BacktestConfig

# 配置风控参数
risk_config = RiskConfig(
    safety_margin=0.0001,       # 资金安全垫
    max_order_size=10000,       # 单笔最大委托数量
    max_position_size=0.5,      # 单个标的最大持仓比例 (50%)
    restricted_list=["ST_STOCK"], # 限制交易名单
    stop_loss_threshold=0.8     # 账户级止损 (净值 < 0.8 * 初始资金则停止)
)

# 应用配置 (StrategyConfig 还可以配置滑点等)
strategy_config = StrategyConfig(
    risk=risk_config,
    slippage=0.0002,            # 2bp 滑点
    volume_limit_pct=0.1        # 限制成交量占比 10%
)
run_backtest(..., config=BacktestConfig(strategy_config=strategy_config))
```

### 4.3 常见错误排查

1.  **"History tracking is not enabled"**:
    *   **原因**: 未设置 `warmup_period` 或 `set_history_depth`，导致无法获取历史数据。
    *   **解决**: 在类定义中设置 `warmup_period = N` 或在 `__init__` 中设置 `self.warmup_period = N`。

2.  **"Context not ready"**:
    *   **原因**: 在 `__init__` 中调用了需要 Context 的方法（如 `get_history`, `buy`）。
    *   **解决**: 将逻辑移至 `on_start` 或 `on_bar` 中。

3.  **订单被拒绝 (Order Rejected)**:
    *   **原因**: 资金不足、触及风控限制、或者不在交易时段。
    *   **解决**: 检查 `result.orders_df` 中的 `reject_reason` 字段；调整 `initial_cash` 或 `risk_config`。
