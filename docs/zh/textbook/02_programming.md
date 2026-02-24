# 第 2 章：编程生存指南 (Programming Survival Guide)

量化投资是金融与计算机的交叉学科。对于金融背景的同学来说，编程往往是最大的拦路虎。本章不求把你培养成软件工程师，只求教给你在量化战场上**生存**所需的最小技能集。

## 2.1 Python for Quant

Python 之所以成为量化领域的霸主，归功于其强大的科学计算生态。你必须熟练掌握以下三个库：**Pandas**, **NumPy**, **Matplotlib**。

### 2.1.1 Pandas: 表格处理神器

Pandas 是 Python 中的 Excel，但比 Excel 强大得多。它有两个核心数据结构：
*   **Series**: 一列数据（带索引）。
*   **DataFrame**: 一张表格（多列数据，带行索引和列索引）。

在量化中，我们通常将时间 (`datetime`) 作为索引，这样的 DataFrame 被称为**时间序列 (Time Series)**。

**核心操作**：

1.  **索引与切片 (Slicing)**:
    *   `df.loc["2023-01-01":"2023-01-31"]`: 获取一月的所有数据。
    *   `df.iloc[-1]`: 获取最后一行数据。

2.  **重采样 (Resampling)**:
    *   `df.resample("1W").last()`: 将日线数据转换为周线数据（取每周最后一天）。
    *   `df.resample("5min").ohlc()`: 将 Tick 数据聚合为 5分钟 K 线。

3.  **滚动窗口 (Rolling)**:
    *   `df["close"].rolling(20).mean()`: 计算 20 日移动平均线 (MA20)。
    *   `df["close"].rolling(20).std()`: 计算 20 日波动率。

4.  **缺失值处理 (Handling Missing Data)**:
    *   `df.fillna(method="ffill")`: 前向填充（用昨天的数据填补今天的空缺），这是金融数据最常用的填充方式。
    *   `df.dropna()`: 直接丢弃包含空值的行。

### 2.1.2 NumPy: 向量化思维

这是初学者最难转变的思维定势。
*   **人类思维 (Loop)**：逐行读取数据，计算，写入下一行。
*   **量化思维 (Vectorization)**：操作整个向量（列）。

**示例**：计算 100 万个数据的平方。
*   **Loop**: 写一个 100 万次的循环。慢，代码冗余。
*   **Vector**: `arr ** 2`。一行代码，底层由 C/Fortran 优化，速度比 Loop 快 10-100 倍。

**广播机制 (Broadcasting)**:
NumPy 允许不同形状的数组进行数学运算。例如 `prices - 100`，会自动将 100 减去数组中的每一个元素。

### 2.1.3 Matplotlib: 数据可视化

虽然现在有 Plotly 等交互式库，但 Matplotlib 依然是基础。
`akquant` 的 `plot_result` 就是基于 Matplotlib 开发的。

**常用功能**:
*   `plt.plot(x, y)`: 绘制折线图。
*   `plt.bar(x, y)`: 绘制柱状图。
*   `plt.subplots()`: 创建多子图（例如上图画 K 线，下图画成交量）。

## 2.2 Rust 概念入门 (Conceptual)

`akquant` 的底层回测引擎是由 Rust 编写的。你不需要会写 Rust，但了解其核心概念有助于你理解报错信息和 API 设计。

### 2.2.1 为什么是 Rust?

*   **速度**: 与 C++ 相当，比 Python 快 10-100 倍。这对于遍历数百万根 K 线的回测至关重要。
*   **安全**: Rust 的编译器极其严格，杜绝了“空指针异常”和“内存泄漏”。这意味着 `akquant` 极其稳定，很难崩溃。

### 2.2.2 内存安全与所有权 (Ownership)

在 Python 中，不仅有垃圾回收 (GC)，变量还只是对象的引用。
在 Rust 中，每个值都有一个**所有者 (Owner)**。
*   **Move**: 当你把值赋给另一个变量时，所有权就转移了，原来的变量失效。这避免了“悬垂指针”。
*   **Borrow**: 你可以“借用”数据（引用），但必须遵守规则（同一时间只能有一个可变借用）。

这听起来很复杂，但在 `akquant` 的 Python 接口中，你通常感受不到它的存在，因为底层已经处理好了。

### 2.2.3 类型系统 (Type System)

Python 是动态类型（变量可以是任何东西），Rust 是静态类型（变量类型必须确定）。

*   **`Option<T>`**: 代表“可能有值，也可能为空”。对应 Python 的 `Optional[T]` 或 `None`。
    *   在策略中，`get_position(symbol)` 返回的可能就是 `Option`：如果没持仓，返回 `None`。
*   **`Result<T, E>`**: 代表“成功返回 T，或失败返回错误 E”。
    *   下单函数可能会返回 `Result`，你需要检查是否下单成功。

## 2.3 工程化思维 (Engineering Mindset)

写策略不仅仅是写数学公式，更是构建一个软件系统。

### 2.3.1 版本控制 (Git)

永远不要把文件命名为 `strategy_final_v2_really_final.py`。
学会使用 **Git** 来管理代码的历史版本。
*   `git init`: 初始化仓库。
*   `git add .` & `git commit -m "update strategy"`: 保存快照。
*   `git checkout`: 回滚到之前的版本。

### 2.3.2 调试技巧 (Debugging)

*   **Print Debugging**: 最简单但最有效。在关键位置打印变量值。
*   **断点调试**: 使用 VS Code 的调试功能，设置断点，单步执行，查看变量状态。这比 print 高效得多。

## 2.4 向量化进阶 (Advanced Vectorization)

在量化中，速度就是生命。除了基本的数组运算，你还需要掌握更高级的技巧。

### 2.4.1 条件选择：`np.where`

替代 Python 的 `if-else`。
```python
# 如果收益率 > 0，标记为 1 (Win)，否则为 0 (Loss)
wins = np.where(returns > 0, 1, 0)
```

### 2.4.2 快速查找：`np.searchsorted`

在一个有序数组中查找插入位置（二分查找），复杂度 $O(\log N)$。
这在回测撮合引擎中非常有用：比如查找订单价格在 LOB 中的位置。

### 2.4.3 表达式加速：`pd.eval`

Pandas 在计算复杂表达式时会产生大量中间临时变量，占用内存且拖慢速度。`pd.eval` 使用 NumExpr 后端，一次性计算整个表达式。

```python
# 传统写法
df['result'] = (df['A'] + df['B']) * (df['C'] - df['D'])

# 加速写法
df.eval('result = (A + B) * (C - D)', inplace=True)
```

## 2.5 设计模式 (Design Patterns)

虽然量化代码不像企业级软件那么庞大，但良好的设计模式能让策略更易扩展。

1.  **工厂模式 (Factory)**：用于创建不同类型的对象。
    *   例如 `IndicatorFactory.create("RSI", period=14)`，根据字符串创建具体的指标对象，避免写一堆 `if type == "RSI": ... elif ...`。
2.  **单例模式 (Singleton)**：确保全局只有一个实例。
    *   例如 `GlobalConfig` 或 `Logger`，整个回测系统中只需要一份配置。
3.  **观察者模式 (Observer)**：解耦事件源与处理逻辑。
    *   `akquant` 的核心架构就是观察者模式。`EventBus` 是被观察者，`Strategy` 和 `RiskManager` 是观察者。当有新行情 (`MarketEvent`) 时，总线通知所有观察者，而不是硬编码调用 `strategy.on_bar()`。

## 2.6 并行计算 (Parallel Computing)

Python 的全局解释器锁 (GIL) 限制了多线程的 CPU 密集型任务。但在参数优化 (Grid Search) 时，我们可以利用多进程 (Multiprocessing) 跑满所有 CPU 核心。

```python
from multiprocessing import Pool

def backtest_one_param(param):
    # 回测逻辑...
    return sharpe_ratio

if __name__ == '__main__':
    params = [10, 20, 30, ..., 100]
    with Pool(processes=8) as pool:
        results = pool.map(backtest_one_param, params)
```

`akquant` 的优化模块已内置了并行计算支持。

## 2.4 向量化进阶 (Advanced Vectorization)

在量化中，速度就是生命。除了基本的数组运算，你还需要掌握更高级的技巧。

### 2.4.1 条件选择：`np.where`

替代 Python 的 `if-else`。
```python
# 如果收益率 > 0，标记为 1 (Win)，否则为 0 (Loss)
wins = np.where(returns > 0, 1, 0)
```

### 2.4.2 快速查找：`np.searchsorted`

在一个有序数组中查找插入位置（二分查找），复杂度 $O(\log N)$。
这在回测撮合引擎中非常有用：比如查找订单价格在 LOB 中的位置。

### 2.4.3 表达式加速：`pd.eval`

Pandas 在计算复杂表达式时会产生大量中间临时变量，占用内存且拖慢速度。`pd.eval` 使用 NumExpr 后端，一次性计算整个表达式。

```python
# 传统写法
df['result'] = (df['A'] + df['B']) * (df['C'] - df['D'])

# 加速写法
df.eval('result = (A + B) * (C - D)', inplace=True)
```

## 2.5 设计模式 (Design Patterns)

虽然量化代码不像企业级软件那么庞大，但良好的设计模式能让策略更易扩展。

1.  **工厂模式 (Factory)**：用于创建不同类型的对象。
    *   例如 `IndicatorFactory.create("RSI", period=14)`，根据字符串创建具体的指标对象，避免写一堆 `if type == "RSI": ... elif ...`。
2.  **单例模式 (Singleton)**：确保全局只有一个实例。
    *   例如 `GlobalConfig` 或 `Logger`，整个回测系统中只需要一份配置。
3.  **观察者模式 (Observer)**：解耦事件源与处理逻辑。
    *   `akquant` 的核心架构就是观察者模式。`EventBus` 是被观察者，`Strategy` 和 `RiskManager` 是观察者。当有新行情 (`MarketEvent`) 时，总线通知所有观察者，而不是硬编码调用 `strategy.on_bar()`。

## 2.6 并行计算 (Parallel Computing)

Python 的全局解释器锁 (GIL) 限制了多线程的 CPU 密集型任务。但在参数优化 (Grid Search) 时，我们可以利用多进程 (Multiprocessing) 跑满所有 CPU 核心。

```python
from multiprocessing import Pool

def backtest_one_param(param):
    # 回测逻辑...
    return sharpe_ratio

if __name__ == '__main__':
    params = [10, 20, 30, ..., 100]
    with Pool(processes=8) as pool:
        results = pool.map(backtest_one_param, params)
```

`akquant` 的优化模块已内置了并行计算支持。

## 2.7 代码演练

下面的脚本演示了 Pandas 和 NumPy 的核心操作，以及如何在 Python 中使用 Type Hints 模拟强类型编程。

```python
--8<-- "examples/textbook/ch02_programming.py"
```

---

**小结**：编程是量化投资的工具，而非目的。不要沉迷于各种炫酷的语法糖，**Pandas + NumPy** 足以解决 90% 的数据处理问题。熟练掌握它们，你的量化之路就成功了一半。
