# 第 14 章：高性能因子挖掘与表达式引擎

## 本章实践入口

- 主示例：[examples/textbook/ch14_factor.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch14_factor.py)
- 进阶示例：[examples/16_adj_returns_signal.py](https://github.com/akfamily/akquant/blob/main/examples/16_adj_returns_signal.py)
- 对应指南：[因子指南](../guide/factor.md)

## 快速运行与验收

```bash
python examples/textbook/ch14_factor.py
```

验收要点：

1. 脚本可完成至少一个表达式因子的计算与输出。
2. 能对同一数据集运行多个因子并比较结果差异。
3. 拆分复杂表达式后，结果可逐步复现并便于排障。

## 1. 本章你会得到什么

这一章聚焦一件事：让你能稳定写出**可解释、可调试、可批量运行**的因子表达式。

学完后你应该能做到：

1. 用 1 行表达式快速验证一个 Alpha 想法。
2. 区分 TS / CS / EL 三类算子并避免语义误用。
3. 对复杂表达式进行拆步调试，而不是“盲猜哪里错了”。
4. 用 `run_batch` 批量计算并理解它的性能取舍。

> 本章讲“怎么思考与实战”，算子清单与排障速查请看 [因子表达式引擎指南](../guide/factor.md)。

## 2. 为什么表达式模式更适合因子研究

在 Alpha 研究中，研究员真正需要的是“低成本试错”。

- 传统方式：每个因子都写一段 DataFrame 逻辑，重复处理分组、对齐、窗口和缺失值。
- 表达式方式：先写出数学结构，再交给引擎执行，例如 `Rank(Ts_Mean(Close, 5))`。

核心收益是解耦：

- 你只描述“算什么”。
- 引擎负责“怎么算”（解析、执行计划、并行优化）。

## 3. 十分钟上手：从 0 到可运行

### 3.1 准备最小数据

```python
import akshare as ak
import pandas as pd
from akquant.data import ParquetDataCatalog

catalog = ParquetDataCatalog("./data_catalog")

symbols = ["sh600000", "sz300750"]
for symbol in symbols:
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        start_date="20230101",
        end_date="20230601",
        adjust="hfq",
    )
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    catalog.write(symbol, df)
```

### 3.2 跑通三个层次

```python
from akquant.factor import FactorEngine

engine = FactorEngine(catalog)

# 单层表达式：先确认基础计算正确
df_ts = engine.run("Ts_Mean(Close, 5)")

# 嵌套表达式：再确认跨分区语义
df_nested = engine.run("Rank(Ts_Mean(Close, 5))")

# 批量表达式：最后再进行规模化
df_batch = engine.run_batch(
    [
        "Ts_Mean(Close, 5)",
        "Rank(Volume)",
        "Rank(Ts_Corr(Close, Volume, 10))",
    ]
)
```

### 3.3 结果先看三列

先只看这三件事，再看绩效：

1. `date` 是否连续且顺序正确。
2. `symbol` 是否完整覆盖样本池。
3. `factor_value` 是否存在异常常数、全 NaN 或极端离群。

## 4. 表达式写作三板斧

### 4.1 第一板斧：先单层，后嵌套

不要一开始就写五层嵌套，建议按顺序：

1. 先验证内层（例如 `Ts_Mean(Close, 5)`）。
2. 再包外层（例如 `Rank(...)`）。
3. 最后再加条件或组合项（例如 `If(...)`）。

### 4.2 第二板斧：按分区语义写

- **TS（时序）**：按 `symbol` 分组滚动。
- **CS（截面）**：按 `date` 分组横截面。
- **EL（元素级）**：逐元素变换，不引入分组窗口。

经验规则：

- 你在问“过去 d 根 K 线”时，优先 TS。
- 你在问“同一天谁强谁弱”时，优先 CS。
- 你在问“单点映射关系”时，优先 EL。

### 4.3 第三板斧：复杂式子拆成步骤

例如表达式：

```python
Rank(Ts_Corr(Close, Volume, 10))
```

建议先验证：

```python
Ts_Corr(Close, Volume, 10)
```

再验证外层 `Rank(...)`。拆步后，定位错误和性能问题都更快。

## 5. 常用因子模板（可直接改参数）

### 5.1 趋势类

- 均线突破：

```python
If(Close > Ts_Mean(Close, 20), 1, -1)
```

- 新高强度：

```python
Close / Ts_Max(Close, 60)
```

### 5.2 反转类

- 短期反转：

```python
-1 * Rank(Delta(Close, 6))
```

- 乖离回归：

```python
-1 * (Close - Ts_Mean(Close, 20)) / Ts_Mean(Close, 20)
```

### 5.3 波动率与量价类

- 低波偏好：

```python
-1 * Ts_Std(Close, 20)
```

- 量价相关：

```python
-1 * Ts_Corr(Close, Volume, 10)
```

### 5.4 组合类

- 动量反转：

```python
Rank(Ts_Mean(Close, 5)) - Rank(Ts_Mean(Close, 20))
```

- 量价背离：

```python
If((Close == Ts_Max(Close, 20)) & (Volume < Ts_Mean(Volume, 20)), 1, 0)
```

## 6. 调试与性能：最实用的工作流

### 6.1 排错顺序（建议固定）

1. 列名是否可映射（`Close`/`close` 可以，`ClosePrice` 需要真实存在）。
2. 窗口 `d` 是否大于可用历史长度。
3. 数据是否有大量 NaN 或停牌空洞。
4. 是否一次写了过深嵌套导致难以定位。

### 6.2 为什么嵌套表达式会慢

当出现 `CS(TS(...))` 或 `TS(CS(...))`，引擎会拆成多步并物化中间结果，换来正确语义与可调试性。

这不是额外负担，而是对“结果可解释”的必要成本。遇到慢查询时，先拆步验证再考虑并行/批量策略。

### 6.3 `run_batch` 的正确使用场景

`run_batch` 适合：

- 多个候选因子同批计算。
- 统一样本池、统一时间段对比。

`run_batch` 不适合：

- 单个复杂表达式的微观调试（先用 `run` 更清晰）。

## 7. 数据质量与时区注意事项

1. 默认时区为 `Asia/Shanghai`。
2. 非 A 股场景需要显式设置 `timezone`。
3. 时间列必须显式 `tz_localize`，避免隐式时区偏移。
4. 停牌或缺失日期建议先做交易日对齐，再做滚动窗口计算。

> 时区细节请参考 [时区处理指南](../advanced/timezone.md)。

## 8. 从原理到实践：引擎到底做了什么

当你调用：

```python
engine.run("Rank(Ts_Mean(Close, 5))")
```

内部过程可以理解为三步：

1. **Parser**：把字符串转为抽象语法结构。
2. **Planner**：识别 TS/CS/EL，必要时自动拆步。
3. **Executor**：按步骤执行并在关键节点物化中间结果。

这一机制直接决定了两个实践建议：

- 调试优先拆步。
- 优化优先减少不必要的跨分区嵌套。

## 本章小结

1. 因子表达式引擎把研究重点从代码细节转向因子语义本身。
2. TS、CS、EL 的分区语义是保证结果正确性的核心前提。
3. 可解释、可拆步、可批量是高效因子研究的三项基本能力。

## 常见错误与排查

1. 表达式报错：优先核对字段名、窗口长度与函数入参类型。
2. 结果异常噪声：检查停牌缺失、时区和交易日对齐是否正确。
3. 运行性能退化：拆分深层嵌套并减少不必要中间物化。

## 课后练习

1. 计算并比较三个因子：`Ts_Mean(Close, 5)`、`Ts_Std(Close, 20)`、`Rank(Volume)`。
2. 复现动量反转：`Rank(Ts_Mean(Close, 5)) - Rank(Ts_Mean(Close, 20))`，观察不同窗口参数下的分布变化。
3. 构造一个“先 TS 再 CS”的复合因子，并写出对应的拆步验证流程。
4. 思考：如果不做停牌对齐，`Ts_Rank` 与 `Ts_Mean` 的语义会如何偏离你的预期。
