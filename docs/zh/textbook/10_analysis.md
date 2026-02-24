# 第 10 章：策略评价体系与风险指标

回测结束后，我们得到了一系列交易记录和资金曲线。如何科学地解读这些数据？如何判断一个策略是否具有统计显著性 (Statistical Significance)？本章将建立一套完整的量化策略评价体系，深入解析收益、风险以及风险调整后收益的核心指标。

## 10.1 收益类指标 (Return Metrics)

### 10.1.1 累计收益与年化收益

*   **累计收益率 (Total Return)**：策略全周期的绝对收益。

    $$ R_{total} = \frac{V_{end} - V_{start}}{V_{start}} $$

*   **年化收益率 (CAGR)**：复合年均增长率，用于对比不同时间跨度的策略。

    $$ R_{annual} = (1 + R_{total})^{\frac{365}{D}} - 1 $$

    其中 $D$ 为回测天数。

### 10.1.2 超额收益 (Alpha)

$$ \alpha = R_p - [R_f + \beta (R_m - R_f)] $$

Alpha 代表了策略剔除市场风险（Beta）后，通过选股或择时能力获得的**超额收益**。它是量化投资者终极追求的目标。

## 10.2 风险类指标 (Risk Metrics)

### 10.2.1 波动率 (Volatility)

收益率标准差的年化值，反映策略的稳定性。

$$ \sigma_{annual} = \sigma_{daily} \times \sqrt{252} $$

### 10.2.2 最大回撤 (Max Drawdown)

策略在任一时间点，从历史最高点 (Peak) 到当前点的最大跌幅。

$$ MDD = \max_{t} \left( \frac{Peak_t - V_t}{Peak_t} \right) $$

**学术意义**：最大回撤衡量了投资者在最坏情况下的损失。如果 MDD > 50%，通常意味着策略失效或资金爆仓。

### 10.2.3 下行风险 (Downside Deviation)

与标准差不同，下行偏差仅计算收益率低于目标收益（通常为 0 或无风险利率）的部分。

$$ \sigma_d = \sqrt{\frac{1}{N} \sum_{i=1}^N \min(R_i - R_{target}, 0)^2} $$

这符合投资者的直觉：**只有亏损才是风险，上涨的波动是惊喜。**

## 10.3 风险调整后收益 (Risk-Adjusted Return)

### 10.3.1 夏普比率 (Sharpe Ratio)

衡量每承担一单位总风险（波动率），能获得多少超额收益。

$$ \text{Sharpe} = \frac{E(R_p) - R_f}{\sigma_p} $$

*   **评价标准**：> 1.0 为良好，> 2.0 为优秀，> 3.0 通常意味着过拟合或高频策略。
*   **局限性**：假设收益率服从正态分布，且将上行波动也视为风险。

### 10.3.2 索提诺比率 (Sortino Ratio)

对夏普比率的改进，分母仅使用下行标准差。

$$ \text{Sortino} = \frac{E(R_p) - R_f}{\sigma_d} $$

对于趋势跟踪策略（通常具有正偏度，即大赚小亏），Sortino 比率通常高于 Sharpe 比率。

### 10.3.3 卡玛比率 (Calmar Ratio)

衡量收益与最大回撤的关系。

$$ \text{Calmar} = \frac{R_{annual}}{|MDD|} $$

这是实盘中最受关注的指标。如果 Calmar < 1，意味着要忍受 30% 的回撤才能换来 30% 的收益，性价比极低。

## 10.4 交易行为分析 (Trade Analysis)

除了资金曲线，我们还需要深入分析每一笔交易 (Trade)。

### 10.4.1 胜率与盈亏比

*   **胜率 (Win Rate)**：盈利交易次数 / 总交易次数。
*   **盈亏比 (P/L Ratio)**：平均盈利金额 / 平均亏损金额。

**凯利公式 (Kelly Criterion)** 揭示了二者与最佳仓位 ($f$) 的关系：

$$ f = \frac{p(b+1) - 1}{b} = p - \frac{q}{b} $$

其中 $p$ 为胜率，$b$ 为盈亏比，$q=1-p$。

*   **趋势策略**：低胜率 (30-40%) + 高盈亏比 (3:1)。
*   **均值回归**：高胜率 (60-70%) + 低盈亏比 (1:1)。

### 10.4.2 MAE 与 MFE

*   **MAE (Maximum Adverse Excursion)**：最大不利偏离。持仓期间出现的最大浮亏。用于优化**止损**。
*   **MFE (Maximum Favorable Excursion)**：最大有利偏离。持仓期间出现的最大浮盈。用于优化**止盈**。

## 10.5 AKQuant 结果解析

`akquant.run_backtest` 返回的 `BacktestResult` 对象包含了上述所有指标。

### 10.5.1 `metrics_df` 解析

```python
metrics = result.metrics_df
sharpe = metrics.loc["sharpe_ratio", "value"]
calmar = metrics.loc["calmar_ratio", "value"]
```
注意：`akquant` 在计算年化指标时，默认假设一年 252 个交易日。

### 10.5.2 `trades_df` 解析

```python
trades = result.trades_df
# 计算胜率
win_rate = len(trades[trades['pnl'] > 0]) / len(trades)
# 计算平均盈亏比
avg_profit = trades[trades['pnl'] > 0]['pnl'].mean()
avg_loss = abs(trades[trades['pnl'] < 0]['pnl'].mean())
pl_ratio = avg_profit / avg_loss
```

### 10.5.3 代码示例

下面的代码演示了如何运行策略并生成详细的性能分析报告。

```python
--8<-- "examples/textbook/ch10_analysis.py"
```

## 10.6 归因分析 (Attribution Analysis)

当你发现策略赚钱了，你需要知道这钱是从哪里来的。**归因分析**旨在将总收益分解为不同的来源，以便评估策略的真实能力。

### 10.6.1 Brinson 模型

这是最经典的归因模型，主要用于股票多头组合。它将超额收益分解为：

1.  **资产配置收益 (Allocation Effect)**：来自于超配表现好的行业/板块，低配表现差的行业。

    $$ R_{allocation} = \sum (w_{p,i} - w_{b,i}) \times (R_{b,i} - R_b) $$

    其中 $w_{p,i}$ 是组合在行业 $i$ 的权重，$w_{b,i}$ 是基准在行业 $i$ 的权重。

2.  **个股选择收益 (Selection Effect)**：来自于在行业内选择了表现优异的个股。

    $$ R_{selection} = \sum w_{b,i} \times (R_{p,i} - R_{b,i}) $$

3.  **交互效应 (Interaction Effect)**：来自于配置与选股的共同作用（例如重仓了一个恰好表现优异的行业，且在该行业选到了牛股）。

### 10.6.2 因子归因 (Factor Attribution)

基于多因子模型（如 Barra 或 Fama-French），将收益分解为**因子暴露 (Factor Exposure)** 和 **特质收益 (Specific Return)**。

$$ R_p = \sum \beta_k F_k + \alpha $$

*   **$\beta_k F_k$**：由于承担了风格因子（如市值、动量、波动率）风险而获得的补偿。这部分通常被认为是“Smart Beta”，可以通过低成本 ETF 获得。
*   **$\alpha$**：剔除所有风格因子后的残差收益。这才是真正的阿尔法，代表了基金经理独特的选股能力。

如果你的策略跑赢了指数，但经 Barra 归因后发现 $\alpha \approx 0$，说明你的超额收益完全来自于风格暴露（例如这一年小盘股涨得好，而你恰好买了很多小盘股）。这种收益是不稳定的，因为风格会轮动。

## 10.7 高级风险指标 (Advanced Risk Metrics)

### 10.7.1 在险价值 (Value at Risk, VaR)

VaR 回答了一个直观的问题：**“在 95% 的置信度下，明天的最大亏损是多少？”**

$$ P(L > VaR_{\alpha}) = 1 - \alpha $$

*   **参数法 (Parametric VaR)**：假设收益率服从正态分布 $N(\mu, \sigma)$。

    $$ VaR_{95\%} = \mu - 1.65 \sigma $$

*   **历史模拟法 (Historical Simulation)**：直接取历史收益率分布的分位数（如第 5% 分位数）。不假设分布形态，能捕捉肥尾风险。
*   **蒙特卡洛模拟 (Monte Carlo)**：通过随机模拟生成成千上万条路径，计算亏损分布。

### 10.7.2 条件在险价值 (CVaR / Expected Shortfall)

VaR 只能告诉我们“坏情况”的边界，但没告诉我们“如果真的发生了坏情况，会亏多少”。CVaR 计算的是**超过 VaR 阈值的损失的期望值**。

$$ CVaR_{\alpha} = E[L | L > VaR_{\alpha}] $$

CVaR 具有更好的数学性质（它是次可加的，即分散化一定能降低 CVaR），因此在机构风控中逐渐取代 VaR 成为主流。

## 10.8 统计显著性检验 (Statistical Significance)

看到一个夏普比率为 2.0 的策略，它是真的优秀，还是仅仅因为运气好？

### 10.8.1 夏普比率的 t 检验

我们可以对夏普比率进行假设检验。原假设 $H_0$：策略的真实夏普比率 $SR = 0$。

统计量 $t$ 值为：

$$ t = \frac{\widehat{SR} \times \sqrt{N-1}}{\sqrt{1 - \gamma_3 \widehat{SR} + \frac{\gamma_4 - 1}{4} \widehat{SR}^2}} $$

（注：这是考虑了偏度 $\gamma_3$ 和峰度 $\gamma_4$ 的调整公式，如果假设正态分布，分母简化为 1）

通常要求 $t > 2$ (95% 置信度) 甚至 $t > 3$ (99% 置信度) 才认为策略有效。

### 10.8.2 概率夏普比率 (Probabilistic Sharpe Ratio, PSR)

由 Bailey 和 de Prado 提出，PSR 计算的是**真实夏普比率大于基准夏普比率（如 0）的概率**。

$$ \widehat{PSR}(SR^*) = Z\left( \frac{(\widehat{SR} - SR^*) \sqrt{N-1}}{\sqrt{1 - \gamma_3 \widehat{SR} + \frac{\gamma_4 - 1}{4} \widehat{SR}^2}} \right) $$

其中 $Z$ 是标准正态分布的累积分布函数。

PSR 考虑了非正态性（偏度和峰度）以及样本长度。对于高频策略（$N$ 很大），即使夏普略低，PSR 也可能很高；对于低频策略，需要极高的夏普才能通过 PSR 检验。

## 10.9 交易成本与换手率

忽视交易成本是回测中最常见的陷阱。

### 10.9.1 换手率 (Turnover Rate)

$$ Turnover = \frac{\sum |Value_{buy}| + \sum |Value_{sell}|}{2 \times Average\_Equity} $$

*   **日换手率**：高频策略可能高达 100% 甚至更高。
*   **年换手率**：中低频策略通常在 2-10 倍。

### 10.9.2 盈亏平衡成本 (Break-even Cost)

这是策略能承受的最大单边成本。

$$ Break\_even = \frac{Total\_Return}{2 \times Total\_Turnover} $$

如果你的策略年化收益 20%，年换手率 10 倍（双边 20 倍），那么每笔交易的平均利润只有 $20\% / 20 = 1\%$。如果加上滑点和佣金超过 1%，策略就会亏损。

**经验法则**：

*   **低频趋势**：要求单笔平均盈利 > 1% (100bps)。
*   **短线反转**：要求单笔平均盈利 > 0.2% (20bps)。
*   **高频做市**：要求单笔平均盈利 > 0.01% (1bps)，且必须有极低的费率支持。

---

**本章小结**：
本章建立了一套严谨的策略评价体系。我们不仅要关注“赚了多少”，更要关注“是怎么赚的”（胜率 vs 盈亏比）以及“承担了多少风险”（夏普、最大回撤）。量化投资的核心在于**风险管理**，而非单纯的收益最大化。
