# 期权风控指南

AKQuant 内置了完整的期权 Greek 风控体系，适用于中国 A 股 ETF 期权（50ETF、300ETF、500ETF 等），支持 **Delta/Gamma/Vega 限额**检查，采用 **Black-Scholes-Merton** 模型进行定价与 Greeks 计算。

## 1. 为什么需要 Greek 风控

中国券商对期权交易者实施分级限额制度。即使不考虑券商要求，管理组合的 Greek 敞口也是量化交易的核心风控环节：

- **Delta**：衡量标的价格变动对期权价值的影响（方向敞口）
- **Gamma**：衡量 Delta 对标的价格变动的敏感度（非线性风险）
- **Vega**：衡量隐含波动率变动对期权价值的影响（波动率敞口）

## 2. Greeks 计算 API

### calculate_option_greeks

```python
from akquant import calculate_option_greeks

# ATM 看涨期权 Greeks
g = calculate_option_greeks(
    underlying_price=2.5,      # 标的当前价格
    strike=2.5,                # 行权价
    time_to_expiry_years=0.25, # 到期时间（年化，约 3 个月）
    risk_free_rate=0.02,       # 无风险利率（2%）
    volatility=0.25,           # 年化波动率（25%）
    option_type="CALL",        # "CALL" 或 "PUT"
)

print(f"Delta: {g.delta:.4f}")   # 方向敞口
print(f"Gamma: {g.gamma:.4f}")   # 非线性风险
print(f"Theta: {g.theta:.4f}")   # 时间衰减（每日）
print(f"Vega:  {g.vega:.4f}")    # 波动率敏感度
print(f"Rho:   {g.rho:.4f}")     # 利率敏感度
print(f"Price: {g.price:.4f}")   # BSM 理论价格
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `underlying_price` | float | 标的资产当前价格 |
| `strike` | float | 行权价 |
| `time_to_expiry_years` | float | 距到期年化时间（如 3 个月 = 0.25） |
| `risk_free_rate` | float | 年化无风险利率（如 0.02 表示 2%） |
| `volatility` | float | 年化波动率（如 0.25 表示 25%） |
| `option_type` | str | `"CALL"` 或 `"PUT"` |

### 返回字段

| 字段 | 说明 |
|------|------|
| `delta` | 标的价格变动 1 元，期权价值变动量 |
| `gamma` | 标的价格变动 1 元，delta 变动量 |
| `theta` | 每过 1 天，期权价值变动量（负值表示损耗） |
| `vega` | 隐含波动率上升 1%，期权价值变动量 |
| `rho` | 无风险利率上升 1%，期权价值变动量 |
| `price` | BSM 模型理论价格 |

### calculate_implied_volatility

从市场价格反推隐含波动率：

```python
from akquant import calculate_implied_volatility

iv = calculate_implied_volatility(
    market_price=0.15,          # 期权市场价格
    underlying_price=2.5,       # 标的价格
    strike=2.5,                 # 行权价
    time_to_expiry_years=0.25,  # 到期时间
    risk_free_rate=0.02,        # 无风险利率
    option_type="CALL",         # "CALL" 或 "PUT"
    # 以下为可选参数：
    # initial_guess=0.2,        # 初始猜测值（默认 0.2）
    # max_iterations=100,        # 最大迭代次数
    # tolerance=1e-8,            # 收敛精度
)

if iv is not None:
    print(f"隐含波动率: {iv:.2%}")
else:
    print("未能收敛")
```

## 3. Greek 风控配置

### 配置字段

在 `RiskConfig` 中设置 Greek 限额：

```python
from akquant import run_backtest, Strategy
from akquant.config import BacktestConfig, StrategyConfig, RiskConfig

risk_config = RiskConfig(
    # 组合级 Greek 限额
    max_portfolio_delta=100.0,   # 组合 Delta 绝对值上限
    max_portfolio_gamma=50.0,    # 组合 Gamma 绝对值上限
    max_portfolio_vega=20.0,     # 组合 Vega 绝对值上限

    # 策略 Slot 级 Greek 限额（多策略时按 slot 独立限制）
    slot_max_delta=30.0,         # 单策略 Delta 上限
    slot_max_gamma=15.0,         # 单策略 Gamma 上限
    slot_max_vega=8.0,           # 单策略 Vega 上限

    # Greek 计算参数
    option_risk_free_rate=0.02,          # 无风险利率
    option_default_volatility=0.25,      # 默认波动率
    option_greek_per_underlying=True,    # 按标的聚合（True）或组合级聚合（False）
)
```

### 配置字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_portfolio_delta` | float? | None | 组合 Delta 绝对值上限 |
| `max_portfolio_gamma` | float? | None | 组合 Gamma 绝对值上限 |
| `max_portfolio_vega` | float? | None | 组合 Vega 绝对值上限 |
| `slot_max_delta` | float? | None | 单策略 Delta 上限 |
| `slot_max_gamma` | float? | None | 单策略 Gamma 上限 |
| `slot_max_vega` | float? | None | 单策略 Vega 上限 |
| `option_risk_free_rate` | float | 0.02 | Greek 计算使用的无风险利率 |
| `option_default_volatility` | float | 0.25 | Greek 计算使用的默认波动率 |
| `option_greek_per_underlying` | bool | True | True = 按标的分别检查限额 |

### 按标的 vs 组合聚合

- **按标的聚合**（`option_greek_per_underlying=True`，默认）：分别计算每个标的（如 510050、510300）的 Greek 总量，每个标的独立检查限额。适合同时交易多只 ETF 期权的场景。
- **组合级聚合**（`option_greek_per_underlying=False`）：汇总所有标的的 Greek，检查组合总量。适合只交易单只 ETF 期权的场景。

## 4. 风控触发示例

当订单会导致 Greek 超限时，订单将被拒绝：

```python
class OptionStrategy(Strategy):
    def on_bar(self, bar):
        # 尝试买入期权
        self.buy(symbol=bar.symbol, quantity=1000)

# 如果买入后 Delta 超过 max_portfolio_delta，将触发拒绝：
# Risk: Option Greek breach — portfolio delta 120.50 exceeds limit 100.00 (group: 510050)
```

### 在策略中处理风控拒绝

```python
from akquant import OrderStatus

class SafeOptionStrategy(Strategy):
    def on_order(self, order):
        if order.status == OrderStatus.Rejected:
            if "Greek" in order.reject_reason:
                # Greek 风控触发，可降低仓位
                print(f"Greek 风控触发: {order.reject_reason}")
```

## 5. 保证金计算

AKQuant 采用中国交易所标准保证金公式：

### 空头期权保证金

```
Call 空头:
  OTM = max(0, 行权价 - 标的价格)
  保证金 = max(权利金 + max(0.12×标的价格 - OTM, 0.07×标的价格),
               权利金 + 标的价格 × 保证金比例)

Put 空头:
  OTM = max(0, 标的价格 - 行权价)
  保证金 = max(权利金 + max(0.12×标的价格 - OTM, 0.07×标的价格),
               权利金 + 标的价格 × 保证金比例)
```

### calculate_option_margin

```python
from akquant.option.queries import calculate_option_margin

# 卖出看涨期权保证金
margin = calculate_option_margin(
    quantity=-10,               # 空头为负数
    option_price=0.15,          # 期权价格
    underlying_price=2.5,       # 标的价格
    multiplier=10000,           # 合约乘数
    margin_ratio=0.2,           # 保证金比例
    is_short=True,              # 是否空头
    strike=2.5,                 # 行权价（用于交易所标准公式）
    option_type="CALL",         # 期权类型
)
print(f"所需保证金: {margin:.2f}")
```

多头期权保证金为 0（只需支付权利金）。

## 6. 注意事项

- **仅支持欧式期权**：BSM 模型仅适用于欧式期权。中国 A 股 ETF 期权（50ETF、300ETF、500ETF 等）均为欧式期权，可直接使用。
- **默认波动率**：风控使用配置的 `option_default_volatility` 计算希腊值，而非市场隐含波动率。如需使用 IV，可通过 `calculate_implied_volatility()` 先求解再传入。
- **已过期期权**：到期日已过的期权仅计算内在 Delta（Call ITM=1, OTM=0），Gamma/Vega 为 0。
- **缺少标的价格**：如果标的当前价格缺失，该期权持仓的 Greeks 将被跳过（不参与限额检查）。
- **限额为 None 时跳过**：只有明确设置了限额值，才会启用对应的检查。
