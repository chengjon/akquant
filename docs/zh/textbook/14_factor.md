# 第 14 章：高性能因子挖掘与表达式引擎

## 1. 为什么需要因子表达式？

在量化投研（尤其是 Alpha 因子研究）中，研究员的核心痛点往往不是“如何写代码”，而是“如何快速验证想法”。

*   **传统方式**：手写 20 行 Python/Pandas 代码来实现一个动量因子，处理繁琐的数据对齐、缺失值填充和窗口计算。
*   **现代方式**：使用一行公式 `Rank(Ts_Mean(Close, 5))` 即可完成计算。

因子表达式引擎（Expression Engine）的出现，将研究员从底层的工程细节中解放出来，专注于因子的**数学逻辑**本身。

## 2. AKQuant 因子引擎架构

AKQuant 内置的 `akquant.factor` 模块基于 Rust 实现的 **Polars** 库，提供了远超 Pandas 的计算性能。

### 2.1 设计哲学与行业标准 (Design Philosophy)

AKQuant 采用了 **DSL (领域特定语言)** 的设计模式，这在顶级量化机构和开源框架中是非常主流的实现方式：

1.  **WorldQuant BRAIN**: 定义了行业标准的算子命名（如 `Ts_Mean`, `Rank`）。AKQuant 沿用了这一规范，让熟悉 WQ 的用户可以零成本迁移。
2.  **DolphinDB**: 高频时序数据库，通过 `streamEngineParser` 解析类似的字符串表达式，构建高性能计算流水线。
3.  **Microsoft Qlib**: 微软推出的 AI 量化平台，同样内置了表达式引擎（Expression Engine），支持如 `Ref($close, 1)` 的语法。

这种设计的核心优势在于**解耦**：用户只需通过字符串描述“算什么”（What），而无需关心底层的“怎么算”（How）。底层的计算引擎可以从 Pandas 升级为 Polars，甚至将来升级为 GPU 计算，而用户的因子代码完全不需要修改。

### 2.2 核心特性

*   **极速计算**：利用 Polars 的 Lazy API 和多线程并行计算能力。
*   **防止未来函数**：封装好的时序算子（如 `Ts_Mean`）强制执行窗口逻辑，避免用到未来数据。
*   **Alpha101 风格**：支持 WorldQuant 风格的经典因子语法。

## 3. 快速上手

### 3.1 准备数据

因子引擎需要标准化的面板数据（Panel Data）。

```python
import akshare as ak
import pandas as pd
from akquant.data import ParquetDataCatalog

# 初始化数据目录
catalog = ParquetDataCatalog("./data_catalog")

# 下载数据 (以平安银行和宁德时代为例)
symbols = ["sh600001", "sz300750"]
for symbol in symbols:
    df = ak.stock_zh_a_daily(symbol=symbol, start_date="20230101", end_date="20230601", adjust="hfq")
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    catalog.write(symbol, df)
```

### 3.2 计算因子

```python
from akquant.factor import FactorEngine

# 初始化引擎
engine = FactorEngine(catalog)

# 1. 计算单个动量因子
# 逻辑：过去 5 天收盘价均值的横截面排名
df = engine.run("Rank(Ts_Mean(Close, 5))")
print(df.head())

# 2. 批量计算多个因子
expressions = [
    "Ts_Mean(Close, 5)",             # 时序均值
    "Rank(Volume)",                  # 截面成交量排名
    "Rank(Ts_Corr(Close, Volume, 10))" # 量价相关性排名
]
df_batch = engine.run_batch(expressions)
```

## 4. 算子详解

### 4.1 时序算子 (Time-Series)

在时间维度上对每只股票独立计算。支持别名（如 `Mean` 等同于 `Ts_Mean`）。

| 算子 | 别名 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `Ts_Mean(X, d)` | `Mean` | 移动平均 | `Ts_Mean(Close, 5)` |
| `Ts_Std(X, d)` | `Std` | 移动标准差 | `Ts_Std(Close, 20)` |
| `Ts_Max(X, d)` | `Max` | 移动最大值 | `Ts_Max(High, 10)` |
| `Ts_Min(X, d)` | `Min` | 移动最小值 | `Ts_Min(Low, 10)` |
| `Ts_Sum(X, d)` | `Sum` | 移动求和 | `Ts_Sum(Volume, 5)` |
| `Ts_ArgMax(X, d)` | `ArgMax` | 过去 d 天最大值距离当前的天数 (0=当前) | `Ts_ArgMax(Close, 5)` |
| `Ts_ArgMin(X, d)` | `ArgMin` | 过去 d 天最小值距离当前的天数 (0=当前) | `Ts_ArgMin(Close, 5)` |
| `Ts_Rank(X, d)` | - | 当前值在过去 d 天窗口内的百分比排名 (0~1) | `Ts_Rank(Close, 5)` |
| `Delta(X, d)` | - | 差分 (今日 - d日前) | `Delta(Close, 1)` |
| `Delay(X, d)` | `Ref` | 滞后 (d日前的数值) | `Delay(Close, 1)` |
| `Ts_Corr(X, Y, d)` | `Corr` | 滚动相关系数 | `Ts_Corr(Close, Volume, 20)` |
| `Ts_Cov(X, Y, d)` | `Cov` | 滚动协方差 | `Ts_Cov(Close, Open, 20)` |

### 4.2 截面算子 (Cross-Sectional)

在同一时间点上对所有股票进行计算。

| 算子 | 说明 | 示例 |
| :--- | :--- | :--- |
| `Rank(X)` | 百分比排名 (0~1) | `Rank(Close)` |
| `Scale(X)` | 归一化 (Sum abs = 1) | `Scale(Close)` |

### 4.3 逻辑与数学算子

| 算子 | 说明 | 示例 |
| :--- | :--- | :--- |
| `If(Cond, A, B)` | 条件判断 | `If(Close > Open, 1, -1)` |
| `Sign(X)` | 符号函数 (1, 0, -1) | `Sign(Return)` |
| `Abs(X)` | 绝对值 | `Abs(Close - Open)` |
| `Log(X)` | 自然对数 | `Log(Volume)` |
| `SignedPower(X, e)` | 保持符号的幂运算 | `SignedPower(Return, 2)` |

### 4.4 基础运算

因子表达式支持标准的数学运算符：

*   **算术运算**：`+`, `-`, `*`, `/`
*   **比较运算**：`>`, `<`, `>=`, `<=`, `==`, `!=`

示例：
```python
# 收盘价相对于开盘价的涨幅
(Close - Open) / Open

# 如果收盘价大于 5 日均线，返回 1，否则返回 0
If(Close > Ts_Mean(Close, 5), 1, 0)
```

## 5. 实战：常用因子编写范例

为了帮助大家更好地理解如何编写因子，这里列举了几种常见的因子逻辑及其对应的表达式。

### 5.1 趋势类因子 (Trend)

**逻辑**：如果是上涨趋势，则做多；下跌趋势，则做空。

*   **均线突破**：收盘价在 20 日均线之上。
    ```python
    If(Close > Ts_Mean(Close, 20), 1, -1)
    ```
*   **MACD 简化版**：短期均线减去长期均线。
    ```python
    Ts_Mean(Close, 5) - Ts_Mean(Close, 20)
    ```
*   **新高因子**：当前价格接近过去 60 天的最高价。
    ```python
    Close / Ts_Max(Close, 60)
    ```

### 5.2 反转类因子 (Reversion)

**逻辑**：涨多了会跌，跌多了会涨。

*   **RSI 简化版**：过去 6 天的涨幅（Rank化）。
    ```python
    -1 * Rank(Delta(Close, 6))
    ```
*   **乖离率 (Bias)**：收盘价偏离均线的程度（越偏离越容易回归）。
    ```python
    -1 * (Close - Ts_Mean(Close, 20)) / Ts_Mean(Close, 20)
    ```

### 5.3 波动率类因子 (Volatility)

**逻辑**：捕捉价格的剧烈波动或平静期。

*   **波动率**：过去 20 天的标准差。
    ```python
    -1 * Ts_Std(Close, 20)  # 低波因子通常表现更好，所以乘以 -1
    ```
*   **量价相关性**：价格和成交量的相关性。
    ```python
    # 典型的 Alpha#6 逻辑：放量下跌或缩量上涨
    -1 * Ts_Corr(Close, Volume, 10)
    ```

### 5.4 复杂逻辑组合

*   **量价背离**：价格创新高但成交量没有创新高。
    ```python
    # 价格在近 20 天高位，但成交量不在高位
    If((Close == Ts_Max(Close, 20)) & (Volume < Ts_Mean(Volume, 20)), 1, 0)
    ```

### 5.5 高级时序特征 (Advanced Time-Series)

利用 `Ts_ArgMax`, `Ts_ArgMin`, `Ts_Rank` 可以构建更精细的时序特征。

*   **高点距离 (Days Since Max)**：距离过去 20 天最高价的天数。如果今天是最高价，则为 0。
    ```python
    Ts_ArgMax(High, 20)
    ```
*   **低点距离 (Days Since Min)**：距离过去 20 天最低价的天数。如果今天是最低价，则为 0。
    ```python
    Ts_ArgMin(Low, 20)
    ```
*   **价格分位数 (Price Rank)**：当前价格在过去 20 天内的百分比排名（0~1）。这类似于 **Stochastic Oscillator (KDJ 中的 K 值)** 的变体。
    ```python
    Ts_Rank(Close, 20)
    ```
*   **Alpha #13 (WorldQuant 简化版)**：成交量加权的收盘价排名的协方差。
    ```python
    # 原始逻辑较为复杂，这里展示利用 Ts_Rank 的组合
    -1 * Rank(Ts_Cov(Rank(Close), Rank(Volume), 5))
    ```

## 6. 进阶：挖掘 Alpha 因子

通过组合上述算子，我们可以复现经典的 Alpha 因子。例如 **Alpha #6** (参考 WorldQuant)：

$$
-1 \times \text{Corr}(\text{Open}, \text{Volume}, 10)
$$

在 AKQuant 中对应的表达式为：

```python
expr = "-1 * Ts_Corr(Open, Volume, 10)"
df = engine.run(expr)
```

## 7. 课后练习

1.  尝试使用 AKShare 下载更多股票的数据（如沪深300成分股）。
2.  实现并计算一个动量反转因子：`Rank(Ts_Mean(Close, 5)) - Rank(Ts_Mean(Close, 20))`。
3.  思考：如果不进行数据对齐（停牌处理），直接计算时序因子会有什么风险？
