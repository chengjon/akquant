# 第 8 章：期权定价与波动率策略

期权 (Options) 是金融工程皇冠上的明珠。它不仅是一种非线性 (Non-linear) 的衍生品，更是交易“波动率 (Volatility)”和“时间 (Time)”的工具。本章将从经典的 Black-Scholes-Merton (BSM) 定价模型出发，深入剖析希腊字母 (Greeks) 的数学含义与风控应用，并展示如何在 `akquant` 中构建专业的期权策略。

## 8.1 期权基础与定价理论 (Pricing Theory)

### 8.1.1 核心要素

期权赋予买方在未来特定时间 ($T$) 以特定价格 ($K$) 买入或卖出标的资产 ($S$) 的**权利**。

*   **Call (看涨)**：$Payoff = \max(S_T - K, 0)$
*   **Put (看跌)**：$Payoff = \max(K - S_T, 0)$
*   **Moneyness (实虚值状态)**：
    *   **ITM (实值)**：具有内在价值 ($Call: S > K$)。
    *   **ATM (平值)**：$S \approx K$。
    *   **OTM (虚值)**：无内在价值 ($Call: S < K$)。

### 8.1.2 Black-Scholes-Merton (BSM) 模型

BSM 模型是现代期权定价的基石。对于欧式看涨期权 (European Call)，其定价公式为：

$$ C = S N(d_1) - K e^{-rT} N(d_2) $$

其中：

*   $N(\cdot)$：标准正态分布累积分布函数。
*   $d_1 = \frac{\ln(S/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}$
*   $d_2 = d_1 - \sigma\sqrt{T}$
*   $\sigma$：标的资产收益率的波动率。

**模型洞察**：期权价格取决于五个变量：$S, K, T, r, \sigma$。其中前四个是市场可观测的，唯独**波动率 ($\sigma$)** 是未知的，需要估计。

## 8.2 希腊字母 (The Greeks)

希腊字母是期权价格关于各变量的偏导数，量化了期权的风险暴露。

### 8.2.1 Delta ($\Delta$)：方向风险

$$ \Delta = \frac{\partial C}{\partial S} $$

*   **含义**：标的价格变化 1 单位，期权价格变化多少。
*   **特性**：Call $\Delta \in (0, 1)$, Put $\Delta \in (-1, 0)$。ATM Call $\Delta \approx 0.5$。
*   **应用**：**Delta Neutral Hedging**。通过持有 $-N \times \Delta$ 份标的资产，使组合的总 Delta 为 0，从而免疫小幅价格波动风险，纯粹赚取时间价值或波动率收益。

### 8.2.2 Gamma ($\Gamma$)：凸性风险

$$ \Gamma = \frac{\partial^2 C}{\partial S^2} = \frac{\partial \Delta}{\partial S} $$

*   **含义**：Delta 随标的价格的变化率。Gamma 越大，Delta 变化越快，对冲越困难。
*   **特性**：ATM 期权 Gamma 最大。临近到期时，ATM Gamma 会急剧飙升 (Pin Risk)。

### 8.2.3 Theta ($\Theta$)：时间衰减

$$ \Theta = \frac{\partial C}{\partial T} $$

*   **含义**：时间每流逝一天，期权价值损失多少。
*   **特性**：期权买方通常是 Theta 负值（消耗时间），卖方是 Theta 正值（赚取时间）。

### 8.2.4 Vega ($\nu$)：波动率风险

$$ \nu = \frac{\partial C}{\partial \sigma} $$

*   **含义**：波动率变化 1%，期权价格变化多少。
*   **特性**：长期限 (Long-term) 期权的 Vega 更大。

## 8.3 波动率曲面 (Volatility Surface)

### 8.3.1 隐含波动率 (Implied Volatility, IV)

如果我们把市场上的期权价格 $C_{market}$ 代入 BSM 公式，反推出的 $\sigma$ 即为**隐含波动率 (IV)**。IV 代表了市场对未来波动的预期。

### 8.3.2 波动率微笑 (Volatility Smile)

BSM 模型假设 $\sigma$ 为常数，但实际上，不同行权价 ($K$) 的期权 IV并不同：

*   **Smile/Skew**：通常 OTM Put 的 IV 高于 ATM，形成“偏斜 (Skew)”，反映了市场对暴跌风险的恐惧（黑天鹅定价）。
*   **Term Structure**：不同到期日的 IV 也不同。

## 8.4 策略示例：备兑看涨 (Covered Call)

这是一种最基础的收益增强策略，适合长期看好但认为短期横盘的标的。

**构建**：

1.  **持有标的** (Long Underlying)。
2.  **卖出 OTM Call** (Short Call)。

**逻辑**：

*   **若上涨**：收益被行权价封顶 (Capped Upside)。
*   **若横盘**：赚取 Call 的权利金 (Theta Income)，降低持仓成本。
*   **若下跌**：权利金提供了一定的安全垫 (Downside Buffer)。

### 8.4.1 代码实现

```python
--8<-- "examples/textbook/ch08_options.py"
```

## 8.5 希腊字母深入 (Advanced Greeks)

除了 Delta, Gamma, Theta, Vega 这四个主要风险维度，专业交易员还需要关注二阶甚至三阶导数。

1.  **Vanna ($\frac{\partial \Delta}{\partial \sigma}$)**：
    *   Delta 对波动率的敏感度。
    *   **应用**：当波动率上升时，OTM Call 的 Delta 会增加（变得更有可能变为 ITM），而 ITM Call 的 Delta 会减小。做市商需要根据 Vanna 调整 Delta 对冲头寸。

2.  **Vomma ($\frac{\partial \nu}{\partial \sigma}$)**：
    *   Vega 对波动率的敏感度（Vega 的凸性）。
    *   **应用**：买入 Vomma（通常是买入 OTM 期权）可以在波动率飙升时获得加速度收益。

3.  **Charm ($\frac{\partial \Delta}{\partial T}$)**：
    *   Delta 对时间的敏感度。
    *   **应用**：随着到期日临近，OTM 期权的 Delta 会加速衰减至 0，ITM 期权的 Delta 会加速收敛至 1。周末效应（Weekend Effect）往往会导致 Charm 风险暴露。

## 8.6 常见期权策略组合

期权的魅力在于通过组合构建出任意形状的损益曲线 (Payoff)。

### 8.6.1 跨式组合 (Straddle)

*   **构建**：买入 ATM Call + 买入 ATM Put（相同 $K$, 相同 $T$）。
*   **观点**：**做多波动率**。认为市场即将发生大行情（如财报发布、重大政策），但不确定方向。
*   **风险**：如果市场横盘，损失全部权利金（Theta 损耗极大）。

### 8.6.2 宽跨式组合 (Strangle)

*   **构建**：买入 OTM Call + 买入 OTM Put。
*   **观点**：同 Straddle，但成本更低，需要的波动幅度更大。
*   **应用**：彩票型策略，博取黑天鹅事件。

### 8.6.3 垂直价差 (Vertical Spread)

*   **牛市价差 (Bull Spread)**：买入低行权价 Call ($K_L$)，卖出高行权价 Call ($K_H$)。
*   **熊市价差 (Bear Spread)**：买入高行权价 Put ($K_H$)，卖出低行权价 Put ($K_L$)。
*   **特点**：收益有限，风险也有限。通过卖出期权降低了权利金成本，是方向性交易的首选。

### 8.6.4 铁以此组合 (Iron Condor)

*   **构建**：卖出 OTM Put Spread + 卖出 OTM Call Spread。
    *   卖出 Put $K_1$ (低)，买入 Put $K_2$ (更低) 保护。
    *   卖出 Call $K_3$ (高)，买入 Call $K_4$ (更高) 保护。
*   **观点**：**做空波动率**。认为市场将在 $[K_1, K_3]$ 区间内震荡。
*   **特点**：收租策略。只要标的不大涨大跌，就能稳赚权利金。

## 8.7 动态对冲：Gamma Scalping

这是一种利用 Gamma 属性，通过不断调整 Delta 对冲来获利的策略。

1.  **构建**：买入跨式组合 (Long Straddle)，保持 Delta 中性。
2.  **上涨时**：Gamma $> 0$，Delta 变大（如 $0 \rightarrow 0.2$）。为了保持中性，**卖出** 0.2 份标的。
3.  **下跌时**：Gamma $> 0$，Delta 变小（如 $0 \rightarrow -0.2$）。为了保持中性，**买入** 0.2 份标的。

**结果**：
在对冲过程中，我们一直在**“高抛低吸”**标的资产。

*   如果市场波动足够大，Gamma Scalping 赚取的利润将超过 Theta 损耗（权利金的时间衰减）。
*   如果市场死水一潭，Gamma 利润不足以覆盖 Theta 成本，策略亏损。

## 8.8 引擎配置与实战细节

### 8.8.1 合约配置

在 `akquant` 中，配置期权合约需指定 `option_type`, `strike_price` 和 `expiry_date`。

```python
from akquant import InstrumentConfig, OptionType

# 配置某个月份的购 4000 合约
opt_config = InstrumentConfig(
    symbol="MO2309-C-4000",
    asset_type="OPTION",
    option_type=OptionType.CALL,
    strike_price=4000.0,
    expiry_date="2023-09-15"
)
```

### 8.8.2 保证金计算

期权卖方（义务方）需要缴纳保证金。`akquant` 支持交易所标准的保证金计算公式：

$$ Margin = \text{权利金} + \max(12\% \times S - \text{虚值额}, 7\% \times S) $$

这意味着卖出期权的杠杆并不是固定的，而是随着标的价格变化而动态变化的。策略必须预留足够的现金以防**追加保证金 (Margin Call)**。

## 8.9 波动率套利 (Volatility Arbitrage)

波动率套利的核心在于交易**隐含波动率 (IV)** 与**已实现波动率 (RV)** 之间的差价。

$$ Profit \approx \text{Vega} \times (IV_{sold} - IV_{bought}) + \frac{1}{2} \text{Gamma} \times (RV^2 - IV^2) $$

*   **做空波动率**：当 $IV > RV$ 时，卖出跨式组合 (Short Straddle)，并进行 Delta 对冲。如果市场实际波动小于 IV 预示的波动，则赚取 Vega 差价。
*   **Vanna-Volga 方法**：利用市场上的三个主要报价（ATM, 25-Delta Call, 25-Delta Put）来构建整个波动率曲面，寻找定价错误的期权。

## 8.10 尾部风险对冲 (Tail Risk Hedging)

黑天鹅事件（如 2020 年疫情熔断）虽然罕见，但足以摧毁整个投资组合。

*   **Put Buying**：定期买入深度虚值 (Deep OTM) Put。虽然长期亏损权利金（像买保险一样），但在崩盘时能获得百倍回报，对冲股票多头的亏损。
*   **VIX Call**：买入 VIX 看涨期权。VIX 指数通常与股市负相关。

---

**本章小结**：
期权交易不仅是对方向的判断，更是对概率分布的交易。理解 BSM 模型和 Greeks 是构建高级波动率策略（如跨式套利 Straddle、蝶式套利 Butterfly）的前提。掌握了本章内容，你已经迈入了专业量化交易的门槛。
