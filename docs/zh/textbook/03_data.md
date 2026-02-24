# 第 3 章：金融数据获取与处理

## 3.1 AkShare：量化投资的开源数据基石

在量化投资中，数据质量决定了策略的上限 (Garbage In, Garbage Out)。对于中国市场，[AkShare](https://akshare.akfamily.xyz/) 是目前最流行的开源金融数据接口库。它提供了从股票、期货、期权、基金到宏观经济的全维度数据。

### 3.1.1 安装与验证

在第 1 章中我们已经安装了 `akshare`。可以通过以下命令验证版本：

```python
import akshare as ak
print(ak.__version__)
```

## 3.2 金融时间序列数据 (OHLCV)

量化回测中最基础的数据单元是 **K线 (Candlestick)**，通常包含以下字段，简称为 **OHLCV**：

*   **Open**: 开盘价
*   **High**: 最高价
*   **Low**: 最低价
*   **Close**: 收盘价
*   **Volume**: 成交量

### 3.2.1 复权 (Adjustment)

股票价格会受到**分红**、**配股**、**拆细**等除权除息行为的影响，导致价格出现断层。为了保证回测的连续性，必须对价格进行**复权**处理。

*   **前复权 (Forward Adjustment)**：以当前价格为基准，向前推算历史价格。**回测推荐使用前复权**，因为它保留了当前的真实价格水平，方便计算买入股数。
*   **后复权 (Backward Adjustment)**：以历史上市首日价格为基准，向后推算当前价格。适合计算长周期的收益率。
*   **不复权 (No Adjustment)**：原始价格。除权日会出现巨大的价格跳空，**严禁直接用于策略回测**。

#### 复权因子计算 (Adjustment Factor)

前复权价格的计算公式如下：

$$ P_{adj} = P_{raw} \times \frac{P_{today}}{P_{ex-right}} $$

其中 $P_{adj}$ 是复权后价格，$P_{raw}$ 是原始价格。对于分红（每股分红 $D$），除权价 $P_{ex-right} = P_{close} - D$。这意味着历史价格会相应**调低**，使得收益率曲线平滑连接。

### 3.2.2 数据频率 (Data Frequency)

量化回测通常使用不同频率的数据：

*   **Tick 数据**：逐笔成交数据（包含每一笔成交的时间、价格、量）。数据量极大，适合高频策略 (HFT)。
*   **Bar 数据 (OHLCV)**：将一段时间内的 Tick 聚合为一个数据点（如 1分钟 Bar、日线 Bar）。这是最常用的格式。
*   **Daily 数据**：日线数据。包含开高低收及成交量。适合中低频策略（如趋势跟踪、多因子选股）。

`akquant` 核心引擎基于 Bar 数据驱动，支持任意周期的 Bar（1分钟、5分钟、日线等）。

在 `akshare` 中获取前复权数据非常简单：

```python
import akshare as ak

# 获取浦发银行 (600000) 的日线数据，前复权
df = ak.stock_zh_a_hist(symbol="600000", period="daily", start_date="20200101", end_date="20231231", adjust="qfq")
print(df.head())
```

## 3.3 数据治理与 ETL 流程

在金融工程中，数据被视为核心资产。构建高质量的数据库需要严格遵循 **ETL (Extract, Transform, Load)** 流程。

### 3.3.1 数据清洗 (Data Cleaning)

原始数据通常包含噪音、缺失值甚至错误。常见的数据治理问题包括：

1.  **缺失值 (Missing Data)**：
    *   **原因**：停牌、数据源故障、非交易日。
    *   **处理**：前向填充 (Forward Fill)、插值法或直接剔除。
2.  **异常值 (Outliers)**：
    *   **原因**：乌龙指、数据录入错误。
    *   **处理**：使用 MAD (绝对中位差) 或 3$\sigma$ 原则识别并修正。
3.  **幸存者偏差 (Survivorship Bias)**：
    *   **定义**：如果在回测中只包含当前存在的股票，而忽略了历史上已退市的股票，会导致回测结果虚高（因为退市股票通常表现很差）。
    *   **对策**：必须维护包含所有历史退市股票的“全集数据库”。
4.  **前视偏差 (Look-ahead Bias)**：
    *   **定义**：在 $T$ 时刻做决策时，使用了 $T+1$ 时刻才能获得的数据（如使用当天的收盘价来决定当天的开盘买入）。
    *   **对策**：严格的时间戳对齐，使用 Point-in-Time (PIT) 数据库。

### 3.3.2 数据存储 (Storage)

对于高频或海量数据，CSV 并非最佳选择。推荐使用更高效的二进制格式：
*   **Parquet / Feather**：列式存储，读取速度快，压缩率高，Pandas 完美支持。
*   **HDF5**：适合大规模数值矩阵存储。
*   **KDB+ / DolphinDB**：专业的时序数据库 (Time Series Database)，适合机构级应用。

### 3.3.3 标准化字段定义

为了适配 `akquant` 引擎，所有数据必须被映射到以下标准字段：

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `date` | `pd.Timestamp` | 交易日期/时间 |
| `symbol` | `str` | 标的代码 (如 `sh600000`) |
| `open` | `float` | 开盘价 |
| `high` | `float` | 最高价 |
| `low` | `float` | 最低价 |
| `close` | `float` | 收盘价 |
| `volume` | `float` | 成交量 |

### 3.3.4 ETL 脚本示例

下面的代码演示了完整的 ETL 流程：从 AkShare 提取数据，清洗为标准格式，并保存为 Parquet 文件。

创建文件 `examples/textbook/ch02_data.py`：

```python
--8<-- "examples/textbook/ch02_data.py"
```

### 运行结果

```bash
python examples/textbook/ch02_data.py
```

你将在控制台看到数据清洗前后的对比，并在 `data/` 目录下找到生成的 `.parquet` 文件。

## 3.4 数据库设计 (Database Design)

随着数据量的增长，单纯的文件存储（CSV/Parquet）将难以满足查询需求。我们需要引入专业的数据库。

### 3.4.1 关系型数据库 (Relational DB)

*   **代表**：PostgreSQL, MySQL。
*   **适用**：资产基础信息（如股票代码、上市日期、行业分类）、交易账户信息（如资金流水、订单记录）。
*   **特点**：支持复杂关联查询 (JOIN)，事务一致性 (ACID) 强。

### 3.4.2 时序数据库 (Time-Series DB)

*   **代表**：ClickHouse, InfluxDB, DolphinDB。
*   **适用**：行情数据 (Tick/Bar)、高频因子数据。
*   **特点**：
    *   **写入快**：每秒可写入百万级数据点。
    *   **压缩率高**：列式存储，针对时间序列优化的压缩算法（如 Delta Encoding）。
    *   **聚合快**：计算“某股票过去一年的平均成交量”仅需毫秒级。

**ClickHouse 建表示例**：
```sql
CREATE TABLE kline_1m (
    date Date,
    datetime DateTime,
    symbol String,
    open Float32,
    high Float32,
    low Float32,
    close Float32,
    volume Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (symbol, datetime);
```

## 3.5 特征存储 (Feature Store)

在机器学习项目中，特征工程往往是最耗时的。为了避免重复计算，我们需要构建**特征存储 (Feature Store)**。

*   **离线存储 (Offline Store)**：存储历史特征（如过去 10 年的 5日均线），用于模型训练。通常基于数仓 (Hive) 或对象存储 (S3)。
*   **在线存储 (Online Store)**：存储最新特征（如当天的 5日均线），用于实盘预测。通常基于 Redis，要求低延迟读取。
*   **一致性**：保证训练和推理使用完全相同的特征计算逻辑。

## 3.6 实时数据流 (Real-time Stream)

在实盘交易中，我们需要处理实时推送的数据流。

*   **WebSocket**：建立持久连接，服务端主动推送数据。比轮询 (Polling) HTTP 接口效率高得多。
*   **消息队列 (Kafka/RabbitMQ)**：在数据源和策略引擎之间引入缓冲层。防止行情爆发时（如开盘瞬间）数据积压导致系统崩溃。

`akquant` 的实盘网关模块内置了 WebSocket 客户端，并自动处理断线重连和心跳保活。

---

**本章小结**：
