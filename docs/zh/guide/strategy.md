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
* `on_start`: 策略启动时调用，**必须**在此处使用 `self.subscribe()` 订阅数据，也可在此注册指标。如果是热启动，需注意不要覆盖已恢复的状态。
* `on_resume`: **仅在热启动时调用**（在 `on_start` 之前）。用于处理从快照恢复后的特殊逻辑。
* `on_bar`: 每一根 K 线闭合时触发 (核心交易逻辑)。
* `on_tick`: 每一个 Tick 到达时触发 (高频/盘口策略)。
* `on_order`: 订单状态变化时触发 (如提交、成交、取消)。
* `on_trade`: 收到成交回报时触发。
* `on_reject`: 订单进入 `Rejected` 状态时触发。
* `on_session_start` / `on_session_end`: 会话切换时触发。
* `before_trading` / `after_trading`: 交易日级钩子。
* `on_daily_rebalance`: 交易日调仓钩子（每天最多一次，适合横截面轮动）。
* `on_portfolio_update`: 账户快照变化时触发。
* `on_error`: 用户回调抛异常时触发，默认触发后继续抛出异常。
* `on_timer`: 定时器触发时调用 (需手动注册)。
*   `on_stop`: 策略停止时调用，适合进行资源清理或结果统计。
*   `on_train_signal`: 滚动训练触发信号 (仅在 ML 模式下触发)。

### 2.1 回调触发契约

对于每个 `bar/tick/timer` 事件，框架按以下顺序分发回调：

1. `on_order` / `on_trade`（若拒单则额外触发 `on_reject`）
2. 框架钩子（`on_session_*`、`before_trading`/`after_trading`、`on_portfolio_update`）
3. 用户事件回调（`on_bar` / `on_tick` / `on_timer`）

说明：

* `on_reject` 对同一订单 id 只触发一次。
* `before_trading` 在本地交易日首次进入 Normal 会话时触发一次。
* `on_daily_rebalance` 与 `before_trading` 同一阶段触发，每个交易日最多触发一次。
* `after_trading` 在离开 Normal 会话时触发；若先跨日再收到事件，会在下一事件补发上一交易日的 `after_trading`。
* 若需要更精确的交易日边界触发，可在策略中设置 `self.enable_precise_day_boundary_hooks = True`。
* `on_portfolio_update` 采用增量触发：初始化时触发一次，后续仅在订单/成交或持仓相关价格变化时触发。
* 可通过 `self.portfolio_update_eps` 过滤微小资产波动（默认 `0.0`，即不过滤）。
* 停止阶段会在 `on_stop` 之前补发待触发的 `on_session_end` / `after_trading`。
* `on_error` 参数为 `(error, source, payload)`，推荐通过 `self.error_mode = "raise" | "continue"` 控制行为（默认 `raise`）。`self.re_raise_on_error` 仍兼容，作为兜底开关。
* 推荐使用 `self.runtime_config = StrategyRuntimeConfig(...)` 统一配置上述行为开关。
* 旧别名字段与 `runtime_config` 会自动保持同步。

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

# 4. 账户最大回撤限制 (例如 20%)
# 当前权益相对历史峰值回撤超过阈值时，拒绝新订单
rm.add_max_drawdown_rule(0.20)

# 5. 单日亏损限制 (例如 5%)
# 当日权益相对当日首个风控检查时点下跌超过阈值时，拒绝新订单
rm.add_max_daily_loss_rule(0.05)

# 6. 账户净值止损阈值 (例如 80%)
# 当前权益低于“规则首次生效时权益 * 阈值”时，拒绝新订单
rm.add_stop_loss_rule(0.80)

# 应用配置
engine.risk_manager = rm

# 运行回测
engine.run(strategy=MyStrategy)
```

通过 `run_backtest` 统一入口也可直接配置账户级风控：

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

账户级参数建议（可作为起步值）：

| 风格 | `max_account_drawdown` | `max_daily_loss` | `stop_loss_threshold` |
| :--- | :--- | :--- | :--- |
| 保守 | `0.10` | `0.02` | `0.90` |
| 中性 | `0.20` | `0.05` | `0.80` |
| 激进 | `0.30` | `0.08` | `0.70` |

建议先从“中性”起步，再根据策略波动与换手逐步收紧或放宽。

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

### 3.4 横截面策略推荐范式 (Cross-Section Pattern)

AKQuant 的 `on_bar` 按“单事件流”逐条触发。若你要做多标的横截面比较（轮动、排序、打分），推荐优先使用 `on_daily_rebalance`，由框架保证“每天最多一次”的触发语义。

推荐步骤：

1. 在 `on_start` 中定义 `universe` 并订阅标的。
2. 在 `on_daily_rebalance` 中遍历 `universe` 计算分数。
3. 在 `on_daily_rebalance` 中统一选股与调仓。

```python
class CrossSectionStrategy(Strategy):
    def __init__(self, lookback=20):
        self.lookback = lookback
        self.universe = ["sh600519", "sz000858", "sh601318"]
        self.warmup_period = lookback + 1

    def on_start(self):
        for symbol in self.universe:
            self.subscribe(symbol)

    def on_daily_rebalance(self, trading_date, timestamp):
        history_map = self.get_history_map(
            count=self.lookback,
            symbols=self.universe,
            field="close",
        )
        scores = {}
        for symbol, closes in history_map.items():
            if len(closes) < self.lookback:
                continue
            scores[symbol] = (closes[-1] - closes[0]) / closes[0]
        if not scores:
            return
        self.rebalance_to_topn(
            scores=scores,
            top_n=2,
            weight_mode="score",
            long_only=False,
        )
```

完整示例见：`examples/strategies/05_stock_momentum_rotation_timer.py`（on_daily_rebalance）与 `examples/strategies/07_stock_momentum_rotation_on_timer.py`（on_timer 固定时点）。

### 3.5 横截面方案 B：收齐同 timestamp 后执行

当策略没有固定调仓时点（不方便用 `on_timer`）时，可在 `on_bar` 中先缓存同一时间片的标的，收齐后再执行一次横截面逻辑。

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

完整示例见：`examples/strategies/06_stock_momentum_rotation_bucket.py`。

### 3.6 方案选型对照 (A vs B)

| 维度 | 方案 A：`on_timer` 统一执行 | 方案 B：收齐 `timestamp` 后执行 |
| :--- | :--- | :--- |
| 触发方式 | 固定时点触发（如 14:55） | 事件驱动，时间片收齐触发 |
| 稳健性 | 高，不依赖到达顺序 | 中，需维护缓存并处理缺失 |
| 实现复杂度 | 低，逻辑集中 | 中，需管理 `timestamp -> symbols` |
| 适用场景 | 日频/定时调仓、生产默认 | 无固定调仓时点的横截面策略 |
| 常见风险 | 定时器时间与数据频率不匹配 | 某些标的缺失导致不触发 |

建议：优先使用方案 A；只有在无法定义稳定调仓时点时再采用方案 B。

### 3.7 横截面常见坑位清单

*   **停牌/缺失数据**：某些标的当日无 Bar 时，方案 B 可能不触发；可设置超时降级，或允许“有效样本数达阈值”即执行。
*   **Universe 漂移**：成分股调整后若仍用旧列表，会出现权重与真实池不一致；建议定期刷新并记录生效日期。
*   **调仓时点与执行模式错配**：例如 `execution_mode="next_open"` 时，收盘时点信号会在下一根撮合；`current_close` 下还需结合 `timer_execution_policy`（或 `fill_policy.temporal`）明确 timer 是否当期成交。
*   **历史长度不足**：新上市或停牌恢复标的数据窗口不完整；评分前统一做 `len(closes)` 检查并跳过不足样本。
*   **仓位未收敛**：多标的先卖后买若资金未及时释放，可能导致买入不足；可采用目标仓位 API 并在下一时点二次收敛。

完整上线检查可参考：[横截面策略实战清单](cross_section_checklist.md)。

## 5. 策略风格选择 {: #style-selection }

AKQuant 提供了两种风格的策略开发接口：

风格选择建议可参考：[策略风格决策指南](../advanced/strategy_style_decision.md)。

| 特性 | 类风格 (推荐) | 函数风格 |
| :--- | :--- | :--- |
| **定义方式** | 继承 `akquant.Strategy` | 定义 `initialize` + `on_bar`（必选），可选 `on_start` / `on_stop` / `on_tick` / `on_order` / `on_trade` / `on_timer` |
| **适用场景** | 复杂策略、需要维护内部状态、生产环境 | 快速原型验证、迁移 Zipline/Backtrader 策略 |
| **代码结构** | 面向对象，逻辑封装性好 | 脚本化，简单直观 |
| **API 调用** | `self.buy()`, `self.ctx` | `ctx.buy()`, `ctx` 作为参数传递 |

### 5.1 函数式回调触发前提

| 回调 | 触发前提 | 说明 |
| :--- | :--- | :--- |
| `on_bar(ctx, bar)` | 回测数据流产生 Bar 事件 | 函数式策略的必选主回调 |
| `on_start(ctx)` | 回测启动时触发 | 对齐类策略 `on_start` 生命周期 |
| `on_stop(ctx)` | 回测结束时触发 | 对齐类策略 `on_stop` 生命周期 |
| `on_tick(ctx, tick)` | 回测数据流产生 Tick 事件 | 仅 Bar 数据集不会触发 Tick 回调 |
| `on_order(ctx, order)` | 策略上下文中观察到订单状态变化 | 每轮事件循环中先于主事件回调触发 |
| `on_trade(ctx, trade)` | `recent_trades` 中出现成交回报 | 框架会进行成交去重，避免重复触发 |
| `on_timer(ctx, payload)` | 已注册的定时器到点触发 | 支持单次定时与每日定时 payload |

### 5.2 相关示例

*   函数式回调基础示例：`examples/23_functional_callbacks_demo.py`
*   函数式 Tick 回调模拟示例：`examples/24_functional_tick_simulation_demo.py`
*   LiveRunner 支持函数式入口与多 slot 编排：`LiveRunner(strategy_cls=on_bar, strategy_id="alpha", strategies_by_slot={"beta": OtherStrategy}, initialize=..., on_tick=..., on_order=..., on_trade=..., on_timer=...)`
*   回测多 slot 与策略级风控映射建议使用集中式 `BacktestConfig(strategy_config=StrategyConfig(...))`：`docs/zh/advanced/multi_strategy_guide.md`
*   broker_live 函数式下单示例：`examples/39_live_broker_submit_order_demo.py`
*   函数式多策略 slot + 风控示例：`examples/40_functional_multi_slot_risk_demo.py`
*   LiveRunner 多策略 slot 编排示例：`examples/41_live_multi_slot_orchestration_demo.py`
*   运行后可分别观察输出标记：
    *   `done_functional_callbacks_demo`
    *   `done_functional_tick_simulation_demo`

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
    *   **PartiallyFilled**: 订单部分成交（`filled_quantity < quantity`）。
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
    *   `self.order_target_weights(target_weights={"AAPL":0.4,"MSFT":0.3}, liquidate_unmentioned=True, rebalance_tolerance=0.01)`: 按多标的权重统一调仓。
        *   默认权重和不超过 `1.0`，如需超过请设置 `allow_leverage=True`。
        *   执行顺序为先卖后买，减少现金占用导致的买入失败。

```python
def on_timer(self, payload: str):
    weights = {"sh600519": 0.35, "sz000858": 0.25, "sh601318": 0.20}
    self.order_target_weights(
        target_weights=weights,
        liquidate_unmentioned=True,
        rebalance_tolerance=0.01,
    )
```

*   **撤单 (Cancel Order)**:
    *   `self.cancel_order(order_id)`: 撤销指定订单。
    *   `self.cancel_all_orders()`: 撤销当前所有未成交订单。

### 7.3 OCO 与 Bracket 助手

AKQuant 提供了两组交易助手，减少策略中手写订单联动逻辑：

*   `self.create_oco_order_group(first_order_id, second_order_id, group_id=None)`
    *   把两个订单绑定为 OCO（One-Cancels-the-Other）。
    *   任一订单成交后，另一订单会自动撤销。
*   `self.place_bracket_order(symbol, quantity, entry_price=None, stop_trigger_price=None, take_profit_price=None, ...)`
    *   一次性提交 Bracket 结构。
    *   进场单成交后，自动挂出止损/止盈；当止损与止盈同时存在时自动绑定 OCO。

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

### 7.4 Trailing Stop 助手

如果你需要在策略里直接表达“随价格移动的止损线”，可以使用以下助手：

*   `self.place_trailing_stop(symbol, quantity, trail_offset, side="Sell", trail_reference_price=None, ...)`
    *   触发后按市价执行（`StopTrail -> Market`）。
*   `self.place_trailing_stop_limit(symbol, quantity, price, trail_offset, side="Sell", trail_reference_price=None, ...)`
    *   触发后按限价执行（`StopTrailLimit -> Limit`）。

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

完整可运行脚本见：`examples/36_trailing_orders.py`。

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

`on_trade` 与 `get_trades()` 的语义不同：

*   `on_trade(self, trade)` 接收的是当前事件步内的增量成交回报（适合做实时响应）。
*   `self.get_trades()` 返回的是累计“已平仓”交易（Closed Trades），未平仓时不会出现在这个列表里。

推荐模式：

```python
class MyStrategy(Strategy):
    def __init__(self):
        self.recent_exec_count = 0

    def on_trade(self, trade):
        self.recent_exec_count += 1
        print("incremental trade:", trade.order_id, trade.symbol, trade.quantity)

    def on_stop(self):
        closed = self.get_trades()
        print("closed trades:", len(closed))
```

## 7. 进阶功能

### 7.1 事件回调

除了 `on_bar`，你还可以重写其他回调函数来处理更精细的逻辑：

*   `on_order(self, order)`: 订单状态更新时触发。
*   `on_trade(self, trade)`: 订单成交时触发。

### 7.2 指标 (Indicators)

AKQuant 采用“平台双主流、策略单主流”模式。每个策略需要显式设置 `indicator_mode`，并使用对应注册接口：

*   `indicator_mode="precompute"` + `register_precomputed_indicator(...)`
*   `indicator_mode="incremental"` + `register_incremental_indicator(...)`

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

## 8. 高级特性：热启动 (Warm Start)

AKQuant 支持**热启动 (Warm Start)** 功能，允许你保存回测状态并在未来恢复。这对于长周期分段回测、滚动训练或模拟实盘环境非常有用。

### 8.1 核心机制

*   **保存快照**: 使用 `save_snapshot` 将引擎状态保存到文件。
*   **恢复运行**: 使用 `run_warm_start` 从快照恢复并继续运行。

### 8.2 策略适配

为了支持热启动，策略类提供了 `on_resume` 生命周期钩子和 `is_restored` 属性。

*   **`on_resume()`**: 仅在从快照恢复时调用（在 `on_start` 之前）。
*   **`self.is_restored`**: 布尔值，指示当前策略实例是否是从快照恢复的。

**示例代码**：

```python
def on_start(self):
    # 1. 初始化指标 (仅在冷启动时)
    if not self.is_restored:
        self.sma = SMA(30)
    else:
        self.log("Resumed from snapshot. Indicators retained.")

    # 2. 注册指标 (必须执行)
    self.register_indicator("sma", self.sma)

    # 3. 订阅行情 (必须执行)
    self.subscribe(self.symbol)
```

更多详细信息，请参阅 [热启动指南](../advanced/warm_start.md)。
```
