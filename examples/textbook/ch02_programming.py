"""
第 2 章：编程生存指南 (Programming Survival Guide).

本章旨在为非计算机专业的金融学生提供一份极简的编程“生存指南”。
我们将重点介绍 Python 中数据分析最常用的三个库：Pandas, NumPy 和 Matplotlib。
同时，简要介绍 Rust 的类型系统概念，帮助你阅读 AKQuant 的源码。

演示内容：
1. **Pandas**:
    - 基础：DataFrame 创建、索引、切片。
    - 进阶：重采样 (Resample)、滚动窗口 (Rolling)、缺失值处理 (Fillna)。
2. **NumPy**: 向量化计算 (Vectorization) 的威力。
3. **Matplotlib**: 绘制 K 线图和均线。
4. **Type Hints**: 即使在 Python 中，类型提示也能救你一命。
"""

import time
from typing import Optional

import numpy as np
import pandas as pd


# ==========================================
# 1. Pandas: 金融数据的 Excel
# ==========================================
def pandas_crash_course() -> None:
    """Pandas 速成教程."""
    print("\n=== Pandas Crash Course ===")

    # 1.1 创建时间序列数据
    dates = pd.date_range(start="2023-01-01", periods=15, freq="D")
    df = pd.DataFrame(
        {
            "close": [
                100,
                101,
                102,
                99,
                98,
                103,
                105,
                104,
                106,
                108,
                np.nan,
                110,
                112,
                111,
                113,
            ],  # 包含一个 NaN
            "volume": np.random.randint(1000, 2000, 15),
        },
        index=dates,
    )

    print("原始数据 (Head):")
    print(df.head(3))

    # 1.2 缺失值处理
    # ffill (forward fill): 用前一个有效值填充
    df_filled = df.ffill()
    print("\n缺失值处理 (ffill):")
    print(df_filled.loc["2023-01-10":"2023-01-12"])  # type: ignore

    # 1.3 滚动窗口 (Rolling Window)
    # 计算 5日均线
    df["ma5"] = df["close"].rolling(window=5).mean()
    print("\n滚动窗口 (MA5):")
    print(df.tail(3))

    # 1.4 重采样 (Resample)
    # 将日线转为 5日线 (周线近似)
    df_5d = df.resample("5D").agg({"close": "last", "volume": "sum"})
    print("\n重采样 (5日线):")
    print(df_5d)


# ==========================================
# 2. NumPy: 向量化计算 (Vectorization)
# ==========================================
def numpy_vs_loop() -> None:
    """NumPy 向量化计算对比."""
    print("\n=== NumPy vs Loop ===")

    # 创建一个大数组 (100万数据)
    arr = np.random.rand(1_000_000)

    # 任务：计算所有元素的平方

    # 方法 A: 循环 (慢)
    # res = []
    # for x in arr:
    #     res.append(x**2)

    # 方法 B: 向量化 (快)
    # 就像 Excel 中整列操作一样，底层由 C/Fortran 优化

    start = time.time()
    _ = arr**2
    print(f"NumPy 平方计算耗时: {time.time() - start:.6f} 秒")


# ==========================================
# 3. Type Hints: 类型提示 (模拟 Rust)
# ==========================================
def rust_concepts_in_python(price: Optional[float]) -> float:
    """
    Rust 极其强调类型安全。虽然 Python 是动态语言，但我们可以通过 Type Hints 模拟.

    :param price: Optional[float] 对应 Rust 的 Option<f64>
                  意味着 price 可能是 float，也可能是 None (Rust 中的 None)
    :return: float
    """
    if price is None:
        return 0.0
    return price * 1.1  # 涨 10%


if __name__ == "__main__":
    pandas_crash_course()
    numpy_vs_loop()
    print("\n=== Type Hints Demo ===")
    print(f"Option<f64>: {rust_concepts_in_python(100.0)}")
    print(f"Option::None: {rust_concepts_in_python(None)}")
