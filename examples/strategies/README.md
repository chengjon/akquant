# 常用策略示例 (Common Strategies)

本目录包含一系列常用量化策略的实现代码，旨在帮助用户快速上手 AKQuant 策略开发。

这些示例展示了如何结合 [AKShare](https://github.com/akfamily/akshare) 获取数据并进行回测，但也适用于其他数据源。

## 核心提示 (Key Concepts)

在使用 AKQuant 编写策略时，请注意以下核心机制：

1.  **数据获取 (`get_history`)**:
    -   `self.get_history(count=N)` 返回的是**包含当前 Bar** 的最近 N 条数据。
    -   **计算均线 (MA)**: 直接使用 `get_history(N)` 即可（包含今日收盘价）。
    -   **计算突破信号 (Breakout)**: 如果需要基于*昨日*收盘价计算指标（避免未来函数），请获取 `N+1` 条数据并切片 `[:-1]` 剔除当前 Bar。

2.  **多标的回测**:
    -   `run_backtest` 的 `data` 参数支持传入字典 `{symbol: DataFrame}`。
    -   在策略中通过 `self.get_history(..., symbol=s)` 获取指定标的数据。

## 案例列表

### 1. [01_stock_dual_moving_average.py](./01_stock_dual_moving_average.py) - A股双均线策略
- **目标**: 演示如何获取单只股票（如平安银行 sz000001）的历史数据。
- **策略**: 双均线策略 (Golden Cross / Death Cross)。
- **核心点**:
    - 数据清洗与复权处理 (`adjust="qfq"`).
    - `get_history` 的基本使用（包含当前 Bar 数据用于计算当日 MA）。

### 2. [02_stock_grid_trading.py](./02_stock_grid_trading.py) - 股票网格交易
- **目标**: 演示股票网格交易策略逻辑。
- **策略**: 动态网格策略，价格下跌分批买入，上涨分批卖出。
- **核心点**:
    - `on_bar` 中的持仓状态管理。
    - 复杂交易逻辑的实现（基于上次成交价的网格）。

### 3. [03_stock_atr_breakout.py](./03_stock_atr_breakout.py) - 股票 ATR 通道策略
- **目标**: 演示基于波动率的通道突破策略。
- **策略**: ATR 通道突破策略。
- **核心点**:
    - **避免未来函数**: 演示如何剔除当前 Bar 数据来计算基于历史的指标（ATR/通道上下轨）。
    - 波动率指标计算。

### 4. [04_stock_momentum_rotation.py](./04_stock_momentum_rotation.py) - 多股票轮动
- **目标**: 演示多只股票（如 贵州茅台 vs 五粮液）的数据获取与组合管理。
- **策略**: 动量轮动策略 (Momentum Rotation)。
- **核心点**:
    - 多标的数据传入 (`Dict[str, DataFrame]`).
    - 跨标的动量比较与换仓逻辑.
    - `order_target_percent` 的正确使用。

## 使用方法

直接运行对应的 Python 脚本即可：

```bash
python examples/strategies/01_stock_dual_moving_average.py
```
