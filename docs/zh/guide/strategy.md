# 策略编写指南

本文档旨在帮助策略开发者快速掌握 AKQuant 的策略编写方法。

## 1. 核心概念 (Glossary)

对于量化交易的新手，这里有一些基础术语的解释：

*   **Bar (K线)**: 包含了某一段时间（如1分钟、1天）内的市场行情，主要包含 5 个数据：
    *   **Open**: 开盘价
    *   **High**: 最高价
    *   **Low**: 最低价
    *   **Close**: 收盘价
    *   **Volume**: 成交量
*   **Strategy (策略)**: 你的交易机器人。它的核心工作就是不断地看行情 (on_bar)，然后决定买 (buy) 还是卖 (sell)。
*   **Context (上下文)**: 机器人的“记事本”和“工具箱”。里面记录了当前有多少钱 (cash)、有多少股票 (positions)，也提供了下单的工具。
*   **Position (持仓)**: 你当前持有的股票或期货数量。正数表示多头（买入持有），负数表示空头（借券卖出）。
*   **Backtest (回测)**: 历史模拟。用过去的数据来测试你的策略，看看如果过去这么做，能赚多少钱。

## 2. 策略生命周期

一个策略从开始到结束，会经历以下几个阶段：

* `__init__`: Python 对象初始化，适合定义参数。
* `on_start`: 策略启动时调用，**必须**在此处使用 `self.subscribe()` 订阅数据，也可在此注册指标。
* `on_bar`: 每一根 K 线闭合时触发 (核心交易逻辑)。
* `on_tick`: 每一个 Tick 到达时触发 (高频/盘口策略)。
* `on_order`: 订单状态变化时触发 (如提交、成交、取消)。
* `on_trade`: 收到成交回报时触发。
* `on_timer`: 定时器触发时调用 (需手动注册)。
*   `on_stop`: 策略停止时调用，适合进行资源清理或结果统计。
*   `on_train_signal`: 滚动训练触发信号 (仅在 ML 模式下触发)。

## 3. 风险管理 (Risk Management)

AKQuant 内置了强大的预交易风控模块，支持在 Engine 层面拦截不合规的订单。

你可以在回测脚本中（Engine 初始化后）配置这些规则：

```python
from akquant import Engine

engine = Engine()
# ... 添加数据 ...

# 获取风控管理器 (注意：PyO3 返回的是副本，修改后需赋值回去)
rm = engine.risk_manager

# 1. 单标的持仓上限 (例如 10%)
# 如果买入导致某标的持仓市值占总权益超过 10%，则拒绝订单
rm.add_max_position_percent_rule(0.10)

# 2. 行业集中度限制 (例如科技股不超过 20%)
# 需要提供 Symbol -> Sector 的映射字典
sector_map = {"AAPL": "Tech", "MSFT": "Tech", "XOM": "Energy"}
rm.add_sector_concentration_rule(0.20, sector_map)

# 3. 总杠杆率熔断 (例如 1.5倍)
# 总敞口 / 总权益 > 1.5 时拒绝开仓
# 对于高杠杆策略，建议关闭默认的现金检查 (check_cash=False)
rm.config.check_cash = False
rm.add_max_leverage_rule(1.5)

# 应用配置
engine.risk_manager = rm

# 运行回测
engine.run(strategy=MyStrategy)
```

## 4. 常用工具 (Utilities)

AKQuant 提供了一系列便捷工具来简化策略开发。

### 3.1 日志记录 (Logging)

使用 `self.log()` 可以输出带有当前**回测时间戳**的日志，方便调试和记录。

```python
def on_bar(self, bar):
    # 自动添加时间戳，例如: [2023-01-01 09:30:00] 信号触发: 买入
    self.log("信号触发: 买入")

    # 支持指定日志级别
    import logging
    self.log("资金不足", level=logging.WARNING)
```

### 3.2 便捷数据访问 (Data Access)

为了减少代码冗余，`Strategy` 类提供了当前 Bar/Tick 数据的快捷访问属性：

| 属性 | 说明 | 对应原始代码 |
| :--- | :--- | :--- |
| `self.symbol` | 当前标的代码 | `bar.symbol` / `tick.symbol` |
| `self.close` | 当前最新价 | `bar.close` / `tick.price` |
| `self.open` | 当前开盘价 | `bar.open` (Tick 模式为 0) |
| `self.high` | 当前最高价 | `bar.high` (Tick 模式为 0) |
| `self.low` | 当前最低价 | `bar.low` (Tick 模式为 0) |
| `self.volume` | 当前成交量 | `bar.volume` / `tick.volume` |

**示例**：
```python
def on_bar(self, bar):
    # 旧写法
    if bar.close > bar.open: ...

    # 新写法 (更简洁)
    if self.close > self.open:
        self.buy(self.symbol, 100)
```

### 3.3 定时器 (Timer)

除了底层的 `schedule` 方法，AKQuant 提供了更便捷的定时任务注册方式：

*   **`add_daily_timer(time_str, payload)`**: 每天在指定时间触发。
    *   **支持实盘**: 在回测模式下预生成所有触发时间；在实盘模式下，每日自动调度下一次触发。
*   **`schedule(trigger_time, payload)`**: 在指定时间点（一次性）触发。

```python
def on_start(self):
    # 每天 14:55:00 触发收盘检查
    self.add_daily_timer("14:55:00", "daily_check")

    # 在特定日期时间触发
    self.schedule("2023-01-01 09:30:00", "special_event")

def on_timer(self, payload):
    if payload == "daily_check":
        self.log("Running daily check...")
```

## 5. 策略风格选择 {: #style-selection }

AKQuant 提供了两种风格的策略开发接口：

| 特性 | 类风格 (推荐) | 函数风格 |
| :--- | :--- | :--- |
| **定义方式** | 继承 `akquant.Strategy` | 定义 `initialize` 和 `on_bar` 函数 |
| **适用场景** | 复杂策略、需要维护内部状态、生产环境 | 快速原型验证、迁移 Zipline/Backtrader 策略 |
| **代码结构** | 面向对象，逻辑封装性好 | 脚本化，简单直观 |
| **API 调用** | `self.buy()`, `self.ctx` | `ctx.buy()`, `ctx` 作为参数传递 |

## 6. 编写类风格策略 (Class-based) {: #class-based }

这是 AKQuant 推荐的策略编写方式，结构清晰，易于扩展。

### 6.1 数据预热 (Warmup Period)

在计算技术指标（如 MA, RSI）时，需要一定长度的历史数据。AKQuant 提供了 `warmup_period` 机制来自动处理数据预加载。

*   **静态设置 (推荐)**: 在类中定义 `warmup_period = N`。
*   **动态设置**: 在 `__init__` 中设置 `self.warmup_period = N`。
*   **自动推断**: 如果使用内置指标，框架会尝试自动计算所需长度（但显式设置更安全）。

### 6.2 历史数据获取

*   **`self.get_history(count, ...)`**: 返回 `numpy.ndarray`，性能最高，适合计算指标。
*   **`self.get_history_df(count, ...)`**: 返回 `pandas.DataFrame`，包含 OHLCV，适合复杂分析。

### 6.3 完整示例

```python
from akquant import Strategy, Bar
import numpy as np

class MyStrategy(Strategy):
    # 声明需要的预热数据长度 (例如 20日均线需要至少 20 根 Bar)
    warmup_period = 20

    def __init__(self, ma_window=20):
        # 注意: Strategy 类使用了 __new__ 进行初始化，子类不再需要调用 super().__init__()
        self.ma_window = ma_window
        # 如果参数影响预热长度，可以动态覆盖
        self.warmup_period = ma_window + 5

    def on_start(self):
        # 显式订阅数据
        self.subscribe("600000")

    def on_bar(self, bar: Bar):
        # 1. 获取历史数据
        # 返回 numpy array: [close_t-N, ..., close_t-1, close_t]
        history = self.get_history(count=self.ma_window, symbol=bar.symbol, field="close")

        # 检查数据是否足够 (虽然 warmup_period 会保证，但防御性编程是好习惯)
        if len(history) < self.ma_window:
            return

        # 计算均线
        ma_value = np.mean(history)

        # 2. 交易逻辑
        # 获取当前持仓 (使用 Position Helper 或 get_position)
        pos = self.get_position(bar.symbol)

        if bar.close > ma_value and pos == 0:
            self.buy(symbol=bar.symbol, quantity=100)
        elif bar.close < ma_value and pos > 0:
            self.sell(symbol=bar.symbol, quantity=100)
```

## 7. 订单与交易详解 (Orders & Execution)

### 7.1 订单生命周期

在 AKQuant 中，订单状态流转如下：

1.  **New**: 订单对象被创建。
2.  **Submitted**: 订单已发送给交易所/仿真撮合引擎。
3.  **Accepted**: (实盘模式) 交易所确认接收订单。
4.  **Filled**: 订单全部成交。
    *   **PartiallyFilled**: 部分成交 (目前状态码统一为 Filled，需通过 `filled_quantity` 判断)。
5.  **Cancelled**: 订单已取消。
6.  **Rejected**: 订单被风控或交易所拒绝 (如资金不足、超出涨跌停)。

### 7.2 常用交易指令

*   **市价单 (Market Order)**:
    *   `self.buy(symbol, quantity)`
    *   `self.sell(symbol, quantity)`
    *   以当前市场最优价格立即成交，保证成交速度，不保证价格。

*   **限价单 (Limit Order)**:
    *   `self.buy(symbol, quantity, price=10.5)`
    *   只有当市场价格 <= 10.5 时才买入。

*   **目标仓位 (Target Order)**:
    *   `self.order_target(target=100, symbol="AAPL")`: 调整持仓数量至 100 股。
    *   `self.order_target_percent(target_percent=0.5, symbol="AAPL")`: 调整持仓至总资产的 50%。
    *   `self.order_target_value(target_value=10000, symbol="AAPL")`: 调整持仓至 10000 元市值。

*   **撤单 (Cancel Order)**:
    *   `self.cancel_order(order_id)`: 撤销指定订单。
    *   `self.cancel_all_orders()`: 撤销当前所有未成交订单。

### 6.3 市场规则与 T+1 (Market Rules)

在 A 股市场回测中，**T+1 交易规则**是一个非常重要的限制：**当天买入的股票，第二个交易日才能卖出**。

#### 启用 T+1
默认情况下，AKQuant 使用 T+0 规则（便于美股或期货回测）。如需启用 T+1，请在 `run_backtest` 中设置：

```python
# 启用 T+1 规则 (适用于 A 股)
akquant.run_backtest(
    ...,
    t_plus_one=True,
    commission_rate=0.0003,
    stamp_tax_rate=0.001  # 配合印花税设置
)
```

#### 对策略逻辑的影响
启用 T+1 后，你需要区分**总持仓**和**可用持仓**：

*   **`self.get_position(symbol)`**: 返回总持仓（包含今日买入未解锁的部分）。
*   **`self.ctx.get_available_position(symbol)`**: 返回**可用持仓**（即今日可卖出的数量）。
    > 推荐使用 `Position` 辅助类：
    > ```python
    > pos = self.position  # 获取当前 symbol 的 Position 对象
    > print(pos.size)      # 总持仓
    > print(pos.available) # 可用持仓
    > ```

**示例代码**：

```python
def on_bar(self, bar: Bar):
    # 使用 Position Helper
    pos = self.position

    # 卖出逻辑：必须检查可用持仓
    if signal_sell and pos.available > 0:
        self.sell(bar.symbol, pos.available)
```

> **注意**：如果你在 T+1 模式下尝试卖出超过 `available` 的数量，订单会被风控模块（Risk Manager）**拒绝 (Rejected)**，并提示 "Insufficient available position"。

### 6.4 账户与持仓查询

除了 `get_position`，你还可以查询更多账户信息：

*   **`self.ctx.cash`**: 当前账户可用资金。
*   **`self.ctx.equity`**: 当前账户总权益（现金 + 持仓市值）。
*   **`self.get_trades()`**: 获取历史所有已平仓交易记录（Closed Trades）。
*   **`self.get_open_orders()`**: 获取当前未成交订单。

## 7. 进阶功能

### 7.1 事件回调

除了 `on_bar`，你还可以重写其他回调函数来处理更精细的逻辑：

*   `on_order(self, order)`: 订单状态更新时触发。
*   `on_trade(self, trade)`: 订单成交时触发。

### 7.2 指标 (Indicators)

AKQuant 支持**自动发现**机制，你可以直接在 `__init__` 中将指标赋值给 `self` 属性，系统会自动完成注册。

```python
from akquant import Strategy
from akquant.indicators import SMA, RSI

class IndicatorStrategy(Strategy):
    def __init__(self):
        # 方式 1: 自动注册 (推荐)
        # 只要赋值给 self.xxx，系统会自动发现并计算
        self.sma20 = SMA(20)
        self.rsi14 = RSI(14)

    def on_start(self):
        self.subscribe("AAPL")

        # 方式 2: 手动注册 (传统方式)
        # self.register_indicator("sma20", SMA(20))

    def on_bar(self, bar: Bar):
        # 直接通过属性访问指标值
        if bar.close > self.sma20.value:
            self.buy(bar.symbol, 100)

        # 或者通过 get_value 获取历史值
        # val = self.sma20.get_value(bar.symbol, bar.timestamp)
```
