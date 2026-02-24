# 第 13 章：策略可视化与报表分析

数据可视化 (Data Visualization) 不仅是展示结果的手段，更是**探索性数据分析 (Exploratory Data Analysis, EDA)** 的核心工具。通过高质量的图表，我们可以直观地识别策略的风险特征、收益来源以及潜在的过拟合迹象。本章将介绍如何使用 `akquant` 及第三方工具生成专业的量化回测报告。

## 13.1 可视化原则与核心图表

### 13.1.1 权益曲线 (Equity Curve)

最基础的图表，展示账户总资产随时间的变化。

*   **线性坐标 (Linear Scale)**：适合短期回测。
*   **对数坐标 (Logarithmic Scale)**：适合长期回测。在对数坐标下，直线的斜率代表复利增长率，且能清晰展示早期的波动（避免被后期的指数增长掩盖）。

### 13.1.2 水下曲线 (Underwater Plot)

专门用于展示**回撤 (Drawdown)** 的深度和持续时间。

*   **Y轴**：当前净值距离历史最高点的百分比跌幅（0% ~ -100%）。
*   **阴影面积**：反映了投资者承受痛苦的“时间和空间”。
*   **分析**：重点关注**回撤修复期 (Recovery Period)**。如果修复期过长（如超过 1 年），说明策略可能已经失效。

### 13.1.3 收益分布图 (Return Distribution)

展示日收益率的直方图 (Histogram) 和核密度估计 (KDE)。

*   **尖峰肥尾 (Fat Tails)**：金融数据的典型特征。关注分布的**左尾 (Left Tail)**，那是“黑天鹅”藏身之处。
*   **偏度 (Skewness)**：
    *   **正偏 (Positive Skew)**：小亏大赚（趋势策略）。
    *   **负偏 (Negative Skew)**：小赚大亏（套利策略/卖期权）。

## 13.2 高级分析图表

### 13.2.1 月度热力图 (Monthly Heatmap)

将收益率按年份和月份排列成矩阵，用颜色深浅表示收益高低。

*   **用途**：识别**季节性 (Seasonality)** 和**策略衰退**。
*   **特征**：如果某一年份全是绿色（亏损），可能意味着市场风格发生了根本性转变。

### 13.2.2 滚动指标 (Rolling Metrics)

静态指标（如全周期夏普）可能掩盖局部的剧烈波动。

*   **滚动波动率**：观察市场恐慌时策略的风险暴露。
*   **滚动夏普**：观察策略表现的稳定性。

## 13.3 AKQuant 内置绘图工具

`akquant` 提供了简洁的 API，基于 `matplotlib` 生成核心图表。

### 13.3.1 基础绘图

```python
import akquant as aq
import matplotlib.pyplot as plt

# 运行回测
result = aq.run_backtest(...)

# 绘制权益曲线和回撤图
aq.plot_result(result, title="Strategy Performance")
plt.show()
```

### 13.3.2 交互式图表 (Plotly)

在 Jupyter Notebook 环境中，推荐使用交互式图表，可以缩放、拖拽，查看具体某天的持仓。

```python
# 生成 HTML 交互式报告
result.plot(engine="plotly", filename="backtest.html")
```

## 13.4 第三方工具集成：QuantStats

`akquant` 完美支持 `QuantStats`，这是一个强大的 Python 量化分析库，能生成媲美专业基金的 Tearsheet。

### 13.4.1 安装与使用

```bash
pip install quantstats
```

### 13.4.2 生成综合报告

```python
import quantstats as qs

# 1. 获取收益率序列 (pd.Series)
returns = result.metrics_df.loc['daily_returns']
# 注意：akquant result 对象通常需要转换，这里假设有一个辅助方法
# 或者直接从 equity curve 计算:
returns = result.equity_curve.pct_change().dropna()

# 2. 生成 HTML 报告
qs.reports.html(
    returns,
    benchmark="000300.SH", # 对比沪深300
    output='stats.html',
    title='Alpha Strategy Report'
)
```

## 13.5 完整示例代码

下面的代码演示了如何运行策略，并分别使用 `akquant` 内置工具和 `QuantStats` 生成可视化报告。

```python
--8<-- "examples/textbook/ch13_visualization.py"
```

## 13.6 专业 K 线图绘制 (Professional Candlestick Charts)

虽然折线图能展示大致趋势，但量化交易员更习惯看 K 线图 (Candlestick)。Python 中最专业的库是 `mplfinance`。

### 13.6.1 基础 K 线与成交量

```python
import mplfinance as mpf

# 准备数据 (必须包含 Open, High, Low, Close, Volume 列)
df.index.name = 'Date'

# 绘制蜡烛图 + 成交量
mpf.plot(df, type='candle', volume=True, style='yahoo')
```

### 13.6.2 叠加买卖点信号

在 K 线图上标注买入 (Buy) 和卖出 (Sell) 信号，直观复盘交易逻辑。

```python
# 生成买卖点标记
buys = [price if sig == 1 else np.nan for price, sig in zip(df['low'], df['buy_signal'])]
sells = [price if sig == -1 else np.nan for price, sig in zip(df['high'], df['sell_signal'])]

# 添加到副图
apds = [
    mpf.make_addplot(buys, type='scatter', markersize=100, marker='^', color='r'),
    mpf.make_addplot(sells, type='scatter', markersize=100, marker='v', color='g')
]

mpf.plot(df, addplot=apds)
```

## 13.7 3D 波动率曲面 (3D Volatility Surface)

对于期权交易员，仅仅看 IV 曲线是不够的，我们需要看到整个曲面（Strike x Expiry）。

```python
from mpl_toolkits.mplot3d import Axes3D

fig = plt.figure(figsize=(10, 6))
ax = fig.add_subplot(111, projection='3d')

# X: 行权价, Y: 到期时间, Z: 隐含波动率
ax.plot_surface(X, Y, Z, cmap='viridis')

ax.set_xlabel('Strike Price')
ax.set_ylabel('Time to Expiry')
ax.set_zlabel('Implied Volatility')
```
**观察要点**：

*   **Smile/Skew**：沿 Strike 轴的弯曲程度。
*   **Term Structure**：沿 Time 轴的倾斜程度。

## 13.8 交易分析图表 (Trade Analysis)

### 13.8.1 MAE/MFE 散点图

最大不利偏离 (MAE) 与最大有利偏离 (MFE) 的散点图是优化止盈止损的神器。

*   **X轴**：MAE（最大浮亏）。
*   **Y轴**：最终盈亏 (PnL)。
*   **分析**：
    *   如果大量盈利交易的 MAE 都很小（如 < 1%），说明入场点非常精准。
    *   如果亏损交易的 MAE 很大，说明止损设置过宽，或者执行拖沓。
    *   **黄金法则**：截断亏损 (Cut Loss)，让利润奔跑 (Let Profit Run)。这就意味着在图上，左下角的点（止损单）应该密集且受控，右上角的点（盈利单）应该发散且无上限。

## 13.6 专业 K 线图绘制 (Professional Candlestick Charts)

虽然折线图能展示大致趋势，但量化交易员更习惯看 K 线图 (Candlestick)。Python 中最专业的库是 `mplfinance`。

### 13.6.1 基础 K 线与成交量

```python
import mplfinance as mpf

# 准备数据 (必须包含 Open, High, Low, Close, Volume 列)
df.index.name = 'Date'

# 绘制蜡烛图 + 成交量
mpf.plot(df, type='candle', volume=True, style='yahoo')
```

### 13.6.2 叠加买卖点信号

在 K 线图上标注买入 (Buy) 和卖出 (Sell) 信号，直观复盘交易逻辑。

```python
# 生成买卖点标记
buys = [price if sig == 1 else np.nan for price, sig in zip(df['low'], df['buy_signal'])]
sells = [price if sig == -1 else np.nan for price, sig in zip(df['high'], df['sell_signal'])]

# 添加到副图
apds = [
    mpf.make_addplot(buys, type='scatter', markersize=100, marker='^', color='r'),
    mpf.make_addplot(sells, type='scatter', markersize=100, marker='v', color='g')
]

mpf.plot(df, addplot=apds)
```

## 13.7 3D 波动率曲面 (3D Volatility Surface)

对于期权交易员，仅仅看 IV 曲线是不够的，我们需要看到整个曲面（Strike x Expiry）。

```python
from mpl_toolkits.mplot3d import Axes3D

fig = plt.figure(figsize=(10, 6))
ax = fig.add_subplot(111, projection='3d')

# X: 行权价, Y: 到期时间, Z: 隐含波动率
ax.plot_surface(X, Y, Z, cmap='viridis')

ax.set_xlabel('Strike Price')
ax.set_ylabel('Time to Expiry')
ax.set_zlabel('Implied Volatility')
```
**观察要点**：

*   **Smile/Skew**：沿 Strike 轴的弯曲程度。
*   **Term Structure**：沿 Time 轴的倾斜程度。

## 13.8 交易分析图表 (Trade Analysis)

### 13.8.1 MAE/MFE 散点图

最大不利偏离 (MAE) 与最大有利偏离 (MFE) 的散点图是优化止盈止损的神器。

*   **X轴**：MAE（最大浮亏）。
*   **Y轴**：最终盈亏 (PnL)。
*   **分析**：
    *   如果大量盈利交易的 MAE 都很小（如 < 1%），说明入场点非常精准。
    *   如果亏损交易的 MAE 很大，说明止损设置过宽，或者执行拖沓。
    *   **黄金法则**：截断亏损 (Cut Loss)，让利润奔跑 (Let Profit Run)。这就意味着在图上，左下角的点（止损单）应该密集且受控，右上角的点（盈利单）应该发散且无上限。

---

**本章小结**：
一张好的图表胜过千言万语。通过多维度的可视化分析，我们不仅能向投资者展示策略的**收益能力**，更能诚实地剖析策略的**风险特征**。记住：**不要试图用图表掩盖风险，而要用图表揭示风险**。
