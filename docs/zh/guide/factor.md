# 因子表达式引擎 (Factor Expression Engine)

AKQuant 内置了高性能的因子表达式引擎 (`akquant.factor`)，允许用户通过简洁的字符串公式定义复杂的 Alpha 因子。底层基于 Rust 实现的 **Polars** 库，提供极高的计算性能和并行处理能力。

## 核心特性

*   **极速计算**: 基于 Polars Lazy API，自动优化查询计划，利用 Rust 多线程并行计算。
*   **简洁语法**: 使用类 WorldQuant Alpha101 的公式语法，如 `Rank(Ts_Mean(Close, 5))`。
*   **防止未来函数**: 封装好的时序算子（如 `Ts_Mean`）自动处理窗口和偏移，减少手写代码引入未来数据的风险。
*   **自动对齐**: 引擎自动处理面板数据（Panel Data）的对齐和分组（Group By Symbol/Date）。

## 设计原理与行业参考 (Design Philosophy)

AKQuant 的因子引擎采用了经典的 **DSL (Domain Specific Language)** 设计模式，通过字符串解析（AST Parsing）和算子映射（Operator Mapping）将用户的业务逻辑转换为底层的计算图。这种设计在量化金融领域被广泛采用：

1.  **WorldQuant BRAIN**: 作为公式化 Alpha 的鼻祖，其 Alpha Compiler 定义了行业标准的算子命名（如 `Ts_Mean`, `Rank`）。AKQuant 遵循这一命名规范，降低用户的学习迁移成本。
2.  **DolphinDB**: 高性能时序数据库，采用 `streamEngineParser` 解析类似的因子表达式，构建流批一体的计算流水线。
3.  **Microsoft Qlib**: AI 量化平台，其 Expression Engine 同样支持如 `Ref($close, 1)` 的字符串语法，通过缓存和向量化计算提升效率。
4.  **Zipline**: 虽然主要使用 Python 对象，但其 Pipeline API 构建依赖图（Graph）的思想与 AKQuant 利用 Polars Lazy Execution 构建计算图的核心理念是一致的。

AKQuant 站在巨人的肩膀上，结合了 **Polars (Rust)** 的现代化高性能计算引擎，使得在 Python 中也能获得接近 C++ 的因子计算效率，同时保持了 Python 代码的简洁与灵活性。

## 快速开始

### 1. 准备数据

因子引擎默认使用 `ParquetDataCatalog` 读取数据。为了确保因子引擎能正确工作，您需要将数据整理为面板（Panel）格式，并确保包含以下关键列：

*   **`symbol`** (String): 标的代码，用于区分不同的资产（分组计算）。
*   **`date`** (Datetime): 日期或时间戳，用于时间序列排序和对齐。
*   **OHLCV 字段**: 如 `open`, `high`, `low`, `close`, `volume` 等，用于因子计算。

**示例：使用 AKShare 获取 A 股数据并写入**

AKQuant 与 [AKShare](https://akshare.akfamily.xyz/) 完美兼容。你可以使用 AKShare 获取真实的历史行情数据，并将其整理为 AKQuant 所需的格式。

```python
import akshare as ak
import pandas as pd
from akquant.data import ParquetDataCatalog

# 1. 初始化数据目录
catalog = ParquetDataCatalog("./data_catalog")

# 2. 准备股票列表 (例如: 贵州茅台, 宁德时代, 招商银行)
symbols = ["sh600519", "sz300750", "sh600036"]

print("开始下载数据...")
for symbol in symbols:
    print(f"Downloading {symbol}...")

    # 使用 AKShare 获取日线数据 (需安装: pip install akshare)
    # adjust="hfq" 表示后复权，适合回测
    df = ak.stock_zh_a_daily(symbol=symbol, start_date="20230101", end_date="20231231", adjust="hfq")

    if df.empty:
        print(f"Warning: No data for {symbol}")
        continue

    # 添加 symbol 列 (akquant 需要此列进行分组计算)
    df["symbol"] = symbol

    # 确保 date 列是 datetime 类型并设为索引
    # AKShare 返回的数据包含 open, high, low, close, volume 等标准字段
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)

    # 写入 Parquet 目录
    catalog.write(symbol, df)

print("数据准备完成！目录: ./data_catalog")
```

### 2. 计算因子

```python
from akquant.factor import FactorEngine

# 初始化引擎
engine = FactorEngine(catalog)

# 计算单个因子
# 返回包含 [date, symbol, factor_value] 的 DataFrame
df = engine.run("Rank(Ts_Mean(Close, 10))")
print(df.head())

# 批量计算因子
df_batch = engine.run_batch([
    "Ts_Mean(Close, 5)",
    "Rank(Volume)",
    "If(Close > Open, 1, 0)"
])
```

## 算子参考 (Operators)

表达式支持变量（列名，不区分大小写，如 `Close`, `open`）和常数。

### 时序算子 (Time Series)

在时间维度上对每个标的（Symbol）独立计算。

| 算子 | 说明 | 示例 |
| :--- | :--- | :--- |
| `Ts_Mean(X, d)` | 过去 `d` 天的移动平均 | `Ts_Mean(Close, 5)` |
| `Ts_Std(X, d)` | 过去 `d` 天的移动标准差 | `Ts_Std(Close, 20)` |
| `Ts_Max(X, d)` | 过去 `d` 天的最大值 | `Ts_Max(High, 10)` |
| `Ts_Min(X, d)` | 过去 `d` 天的最小值 | `Ts_Min(Low, 10)` |
| `Ts_Sum(X, d)` | 过去 `d` 天的求和 | `Ts_Sum(Volume, 5)` |
| `Ts_ArgMax(X, d)` | 过去 `d` 天最大值距离当前的天数 (0=当前) | `Ts_ArgMax(Close, 5)` |
| `Ts_ArgMin(X, d)` | 过去 `d` 天最小值距离当前的天数 (0=当前) | `Ts_ArgMin(Close, 5)` |
| `Ts_Rank(X, d)` | 当前值在过去 `d` 天窗口内的百分比排名 (0~1) | `Ts_Rank(Close, 5)` |
| `Ts_Corr(X, Y, d)` | 过去 `d` 天 X 和 Y 的相关系数 | `Ts_Corr(Close, Volume, 20)` |
| `Ts_Cov(X, Y, d)` | 过去 `d` 天 X 和 Y 的协方差 | `Ts_Cov(Close, Open, 20)` |
| `Delay(X, d)` | 滞后 `d` 天的值 (Ref) | `Delay(Close, 1)` |
| `Delta(X, d)` | 差分: `X(t) - X(t-d)` | `Delta(Close, 1)` |

### 截面算子 (Cross Sectional)

在同一时间截面上对所有标的进行计算。

| 算子 | 说明 | 示例 |
| :--- | :--- | :--- |
| `Rank(X)` | 百分比排名 (0 到 1) | `Rank(Ts_Mean(Close, 5))` |
| `Scale(X)` | 归一化，使 `sum(abs(X)) = 1` | `Scale(Close)` |

### 逻辑与数学算子 (Math & Logic)

| 算子 | 说明 | 示例 |
| :--- | :--- | :--- |
| `Log(X)` | 自然对数 | `Log(Volume)` |
| `Abs(X)` | 绝对值 | `Abs(Return)` |
| `Sign(X)` | 符号函数 (1, 0, -1) | `Sign(Close - Open)` |
| `SignedPower(X, e)` | 保持符号的幂运算 | `SignedPower(Close, 2)` |
| `If(Cond, A, B)` | 条件判断 (If-Else) | `If(Close > Open, 1, -1)` |

### 基础运算

支持加减乘除 `+`, `-`, `*`, `/` 以及比较运算符 `>`, `<`, `>=`, `<=`, `==`, `!=`。

示例：
```
(Close - Open) / Open
```

## 进阶技巧 (Advanced Tips)

### 1. 数据对齐与填充 (Alignment & Padding)

因子引擎底层使用 Polars 的 `LazyFrame` 进行计算。在进行时序计算（如 `Ts_Mean`）时，Polars 会对每个 `symbol` 分组内的数据进行操作。
**注意**: 如果某些日期的交易数据缺失（例如停牌），`rolling` 窗口计算可能会基于物理行数（Row-based）而非时间（Time-based）。为了确保精确性，建议在写入数据前对数据进行日历填充（Reindex）。

### 2. 智能日期列识别 (Smart Date Column Detection)

`FactorEngine` 在加载数据时会自动识别时间列。如果数据中包含以下列名之一，引擎会自动将其重命名为 `date` 并进行对齐：
*   `date`
*   `index`
*   `datetime`
*   `__index_level_0__` (Pandas 默认索引名)

这意味着您可以直接使用 Pandas `to_parquet` 导出的包含索引的文件，而无需手动重置索引列名。

### 3. 内存优化 (Memory Optimization)

`FactorEngine` 采用 Lazy Evaluation（惰性求值）模式：
1.  `engine.run()` 时并不会立即加载所有数据到内存。
2.  Polars 会构建查询计划，只读取计算所需的列（Projection Pushdown）。
3.  例如计算 `Ts_Mean(Close, 5)` 时，引擎只会读取 `symbol`, `date`, `close` 列，忽略 `open`, `high` 等其他列，极大节省内存。

### 4. 复合因子示例

你可以将多个算子嵌套使用，构建复杂的 Alpha 因子：

*   **量价背离**: `Ts_Corr(Close, Volume, 20)` (价格与成交量的相关性)
*   **动量反转**: `Rank(Ts_Mean(Close, 5)) - Rank(Ts_Mean(Close, 20))` (短期动量减去长期动量)
*   **波动率调整后的动量**: `Ts_Mean(Close, 20) / Ts_Std(Close, 20)`

## 常见问题 (FAQ)

**Q: 支持日内数据（分钟线）吗？**
A: 支持。只要 `date` 列包含时间戳即可。时序算子（如 `Ts_Mean`）是基于窗口长度（行数）计算的，对于分钟线，`d=60` 代表过去 60 个分钟 bar。

**Q: 如何处理停牌数据？**
A: 建议在数据入库前填充停牌日的记录（使用前值填充或 NaN）。如果数据中直接缺失该日期，`rolling` 函数会跳过该日期，直接取上一行数据作为 `t-1`，这在逻辑上可能不符合预期。

**Q: 为什么我的结果全是 NaN？**
A:
1.  检查窗口大小 `d` 是否大于数据长度（Warmup 期）。
2.  检查数据中是否包含大量 NaN。
3.  检查列名是否拼写正确（如 `Close` vs `close`，引擎会自动转小写，但如果数据列名是 `ClosePrice` 则无法匹配）。
