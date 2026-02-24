# 第 5 章：策略开发实战 (Strategy Implementation)

在理解了事件驱动引擎的原理后，我们来动手构建一个真正可用的交易策略。本章将详细拆解策略代码的结构，重点介绍**策略生命周期 (Lifecycle)**、**交易接口 (Trading API)** 以及如何实现复杂的**风控逻辑**。

## 5.1 策略类结构与继承

一个标准的 `akquant` 策略通常继承自 `akquant.Strategy` 基类，并重写以下几个核心回调方法 (Callbacks)：

1.  `__init__`: **构造函数**。定义策略参数和内部变量。
2.  `on_start`: **初始化钩子**。回测开始前触发，常用于订阅数据、设置风控参数。
3.  `on_bar`: **事件处理钩子**。每根 K 线走完时触发，这是策略逻辑的核心入口。
4.  `on_stop`: **结束钩子**。回测结束时触发，常用于清理资源或统计结果。

### 5.1.1 示例代码：带止损的双均线策略

我们以一个增强版的双均线策略为例，增加了**固定比例止损**逻辑。

```python
--8<-- "examples/textbook/ch05_strategy.py"
```

## 5.2 深入理解生命周期 (Lifecycle Management)

### 5.2.1 `__init__` vs `on_start`

*   `__init__`: 此时策略实例刚被创建，回测引擎尚未完全启动，你无法访问 `self.ctx` (Context) 或账户信息。只能做一些纯 Python 层面的变量初始化（如 `self.ma_window = 20`）。
*   `on_start`: 此时引擎已就绪 (Ready State)。你可以安全地调用 `self.log()`, `self.get_position()` 等依赖引擎上下文的 API。

### 5.2.2 `on_bar` 的执行流 (Execution Flow)

`on_bar` 是策略的心脏。它的标准执行流程如下：

1.  **数据获取 (Data Ingestion)**：使用 `self.get_history()` 获取所需的历史数据窗口。
2.  **信号计算 (Signal Generation)**：基于历史数据计算技术指标 (如 MA, RSI)。
3.  **状态检查 (State Inspection)**：获取当前持仓 (`self.get_position`) 和账户资金。
4.  **决策逻辑 (Decision Making)**：根据指标和持仓状态，判断是否买入或卖出。
5.  **订单执行 (Order Routing)**：调用下单函数 (`self.buy`, `self.sell` 等)。

## 5.3 交易接口详解 (Trading API)

`akquant` 提供了多种便捷的下单接口，底层会自动处理报单验证和资金冻结。

### 5.3.1 `order_target_percent(symbol, target)`

这是最常用的接口，实现了**目标仓位管理**。它会自动计算需要买入或卖出的数量，使持仓达到目标比例。

*   `target=0.5`: 买入直到持仓占总资产的 50%。
*   `target=0.0`: 清仓卖出所有持仓。
*   `target=-0.5`: (期货/融券) 卖空直到空头仓位占 50%。

### 5.3.2 `buy(symbol, quantity)` / `sell(symbol, quantity)`

最基础的原子接口，直接指定买卖数量。

*   `quantity`: 必须为正数。
*   对于股票，数量通常需要是 100 的倍数 (手数)，引擎会自动向下取整。

### 5.3.3 `close_position(symbol)`

一键平仓。无论当前持有多头还是空头，都会发出相反方向的市价单将其平掉。

## 5.4 高级策略模式 (Advanced Patterns)

在实际开发中，简单的双均线往往不够用。我们需要更复杂的策略模式。

### 5.4.1 多因子选股 (Multi-Factor Selection)

在多标的回测中（例如全市场选股），我们需要遍历所有标的，计算因子得分，然后构建组合。

**设计模式**：
1.  **每日定时任务**：使用 `schedule_function` 或在 `on_bar` 中检查是否是每日收盘。
2.  **横截面计算**：获取所有标的当日收盘价。
3.  **排序与筛选**：根据因子值排序，选出 Top N。
4.  **调仓**：卖出不在 Top N 的标的，买入新进入 Top N 的标的。

```python
def on_bar(self, bar):
    # 仅在每日收盘前执行 (假设日线数据)
    # 遍历所有关注的标的
    scores = {}
    for symbol in self.universe:
        # 计算因子...
        score = ...
        scores[symbol] = score

    # 排序选股
    target_symbols = sorted(scores, key=scores.get, reverse=True)[:10]

    # 调仓逻辑...
```

### 5.4.2 状态机策略 (Finite State Machine)

对于复杂的择时策略，使用状态机可以清晰地管理逻辑。

*   **State 0 (空仓)**: 等待入场信号。
*   **State 1 (持有)**: 监控止损/止盈。
*   **State 2 (加仓)**: 盈利加仓。
*   **State 3 (冷却)**: 止损后暂停交易一段时间。

```python
class FSMStrategy(Strategy):
    def __init__(self):
        self.state = "EMPTY"
        self.cooldown_counter = 0

    def on_bar(self, bar):
        if self.state == "EMPTY":
            if self.signal_buy():
                self.buy(bar.symbol, 100)
                self.state = "HOLDING"

        elif self.state == "HOLDING":
            if self.check_stop_loss():
                self.close_position(bar.symbol)
                self.state = "COOLDOWN"
                self.cooldown_counter = 5

        elif self.state == "COOLDOWN":
            self.cooldown_counter -= 1
            if self.cooldown_counter <= 0:
                self.state = "EMPTY"
```

## 5.5 自定义指标开发 (Custom Indicators)

虽然 `akquant` 内置了常用的 TA-Lib 指标，但在实战中，我们经常需要开发私有指标。

### 5.5.1 继承 `Indicator` 基类

所有的指标都应继承自 `akquant.Indicator`，并实现 `update` 方法。这种设计支持**增量计算 (Incremental Calculation)**，避免了每次重算整个历史序列的浪费。

```python
class MyMomentum(Indicator):
    def __init__(self, period=10):
        super().__init__()
        self.period = period
        self.history = []

    def update(self, value):
        self.history.append(value)
        if len(self.history) > self.period:
            self.history.pop(0)

        if len(self.history) < self.period:
            return float('nan')

        return self.history[-1] - self.history[0]
```

### 5.5.2 在策略中使用

```python
def __init__(self):
    self.my_mom = MyMomentum(period=10)

def on_bar(self, bar):
    mom_value = self.my_mom.update(bar.close)
    if not math.isnan(mom_value) and mom_value > 0:
        # Do something...
```

## 5.6 高级风控管理 (Risk Management)

风控是量化交易的生命线。除了基本的止损，我们还需要更高级的仓位管理技术。

### 5.6.1 凯利公式 (Kelly Criterion)

凯利公式用于计算在胜率和赔率已知的情况下，最优的下注比例。

$$ f^* = \frac{bp - q}{b} = \frac{p(b+1) - 1}{b} $$

其中：
*   $f^*$：最优仓位比例。
*   $b$：赔率（盈亏比）。
*   $p$：胜率。
*   $q$：败率 ($1-p$)。

**实战应用**：
通常使用**半凯利 (Half-Kelly)**，即只使用凯利公式计算出仓位的一半，以应对参数估计的不确定性。

### 5.6.2 波动率目标 (Volatility Targeting)

这是对冲基金最常用的风控手段。目标是保持组合的年化波动率恒定（例如 15%）。

$$ Weight_t = \frac{\text{Target Vol}}{\text{Realized Vol}_t} $$

*   当市场波动率低时，加杠杆，提高资金利用率。
*   当市场波动率高时，降仓位，控制风险暴露。

```python
# 示例：波动率目标仓位管理
current_vol = np.std(returns[-20:]) * np.sqrt(252) # 年化波动率
target_vol = 0.15 # 目标 15% 波动率

leverage = target_vol / current_vol
# 限制最大杠杆
leverage = min(leverage, 1.5)

self.order_target_percent(symbol, leverage)
```

## 5.7 事件回调处理 (Event Handling)

除了 `on_bar`，`akquant` 还提供了丰富的事件回调，让你能精确控制交易流程。

### 5.7.1 `on_order_status`

当订单状态发生变化时（如从 `Pending` 变为 `Filled`，或被交易所 `Rejected`）触发。

```python
def on_order_status(self, order: Order):
    if order.status == OrderStatus.FILLED:
        self.log(f"订单成交: {order.symbol} {order.filled_qty} @ {order.avg_price}")
    elif order.status == OrderStatus.REJECTED:
        self.log(f"订单被拒: {order.reason}", level="ERROR")
        # 可以在这里实现重试逻辑
```

### 5.7.2 `on_trade`

当发生实际成交时触发。与 `on_order_status` 的区别在于，一笔大单可能会分多次成交，每次成交都会触发 `on_trade`，而 `on_order_status` 通常只在状态跃迁时触发。

---

**本章小结**：

### 5.6.3 止损逻辑 (Stop-Loss)

本章示例展示了一个简单的**固定比例止损**：

```python
# 计算浮动盈亏比例
pnl_pct = (bar.close - self.entry_price) / self.entry_price

# 止损检查
if pnl_pct < -self.stop_loss_pct:
    self.log(f"触发止损! 当前亏损: {pnl_pct:.2%}")
    self.close_position(symbol) # 清仓
```

## 5.8 调试与日志 (Debugging & Logging)

策略开发中最痛苦的莫过于逻辑不符合预期。`akquant` 提供了完善的日志系统。

*   `self.log(msg)`: 会自动打上当前回测时间的标签 `[2023-01-05 15:00:00] msg`。
*   **断点调试**: 由于 `akquant` 是纯 Python/Rust 混合，你完全可以在 PyCharm/VSCode 中打断点调试 `on_bar` 逻辑。

---

**小结**：通过本章的学习，你已经掌握了编写一个完整策略所需的所有基础知识，包括生命周期管理、交易接口、高级模式和风控逻辑。下一章，我们将进入实战环节，探讨中国 A 股特有的交易规则（T+1、涨跌停）在回测中如何处理。
