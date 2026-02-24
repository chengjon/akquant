"""
第 8 章：参数优化与过拟合 (Optimization & Overfitting).

本示例展示了如何使用 AKQuant 的网格搜索 (Grid Search) 功能来寻找最优的策略参数。
同时，我们也会探讨过度优化带来的风险。

策略逻辑：
- 依然使用双均线策略 (MA_Short vs MA_Long)
- 优化目标：寻找夏普比率 (Sharpe Ratio) 最高的参数组合
    - short_window: [3, 5, 10]
    - long_window: [15, 20, 30, 60]

AKQuant 特性：
- `run_grid_search`: 自动多进程并行回测，极大提高优化效率。
"""

from typing import Any, List

import akquant as aq
import numpy as np
import pandas as pd
from akquant import Bar, Strategy


# 模拟数据生成
def generate_mock_data(length: int = 1000) -> pd.DataFrame:
    """生成模拟数据."""
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", periods=length, freq="D")
    prices = 100 + np.cumsum(np.random.randn(length))
    df = pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices + 1,
            "low": prices - 1,
            "close": prices,
            "volume": 100000,
            "symbol": "MOCK",
        }
    )
    return df


class OptStrategy(Strategy):
    """参数优化演示策略."""

    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        """初始化策略."""
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        # 动态设置 warmup_period，确保足够计算最长的均线
        self.warmup_period = long_window + 1

    def on_bar(self, bar: Bar) -> None:
        """收到 Bar 事件的回调."""
        symbol = bar.symbol
        closes = self.get_history(
            count=self.long_window + 1, symbol=symbol, field="close"
        )
        if len(closes) < self.long_window + 1:
            return

        history_closes = closes[:-1]
        ma_short = history_closes[-self.short_window :].mean()
        ma_long = history_closes[-self.long_window :].mean()

        pos = self.get_position(symbol)

        if ma_short > ma_long and pos == 0:
            self.order_target_percent(0.95, symbol)
        elif ma_short < ma_long and pos > 0:
            self.close_position(symbol)


if __name__ == "__main__":
    df = generate_mock_data()

    print("开始运行第 8 章参数优化示例...")
    print("正在进行网格搜索 (Grid Search)...")

    # 定义参数网格
    # 键名必须与策略 __init__ 中的参数名一致
    param_grid = {"short_window": [3, 5, 10], "long_window": [15, 20, 30, 60]}

    # 运行网格搜索
    # max_workers: 并行进程数，默认根据 CPU 核心数自动设置
    # metric: 优化目标指标，默认为 sharpe_ratio
    results: Any = aq.run_grid_search(
        strategy=OptStrategy,
        data=df,
        param_grid=param_grid,
        initial_cash=100_000,
        commission_rate=0.0003,
        max_workers=4,  # 限制为 4 个进程
    )

    print("\n" + "=" * 40)
    print("优化结果 (按夏普比率排序)")
    print("=" * 40)

    # OptimizationResult 对象包含所有参数组合的回测结果
    # 我们可以将其转换为 DataFrame 方便查看
    df_results = pd.DataFrame(results)

    # 按照 sharpe_ratio 降序排列
    # 注意：AKQuant 的结果中，metrics 是一个字典
    # 我们需要展开它

    # 提取关键指标
    summary: List[Any] = []
    for res in results:
        params = res.params
        metrics = res.metrics

        # metrics 可能是 BacktestResult 对象或者字典，视版本而定
        # run_grid_search 通常返回一个包含 params 和 metrics 的轻量级对象
        # 这里假设 metrics 是一个字典，包含 sharpe_ratio 等

        # 实际上 aq.run_grid_search 返回的是 List[OptimizationResult]
        # OptimizationResult.metrics 是一个 PerformanceMetrics 对象或字典

        # 让我们直接打印最优结果
        pass

    # 简单起见，我们直接打印前 3 名
    # run_grid_search 返回的结果通常已经按默认指标排序了 (如果内部实现了的话)
    # 但为了保险，我们手动排序

    # 假设 results 是 List[OptimizationResult]
    # OptimizationResult(params={'short_window': 3, 'long_window': 15}, metrics=...)

    sorted_results = sorted(
        results,
        key=lambda x: x.metrics.sharpe_ratio
        if hasattr(x.metrics, "sharpe_ratio")
        else x.metrics.get("sharpe_ratio", -999),
        reverse=True,
    )

    print(f"{'Short':<6} {'Long':<6} {'Sharpe':<10} {'Return':<10} {'MaxDD':<10}")
    print("-" * 50)

    for res in sorted_results[:5]:
        p = res.params
        m = res.metrics

        # 兼容不同版本的属性访问
        sharpe = getattr(m, "sharpe_ratio", m.get("sharpe_ratio", 0))
        ret = getattr(m, "total_return_pct", m.get("total_return_pct", 0))
        dd = getattr(m, "max_drawdown_pct", m.get("max_drawdown_pct", 0))

        print(
            f"{p['short_window']:<6} {p['long_window']:<6} "
            f"{sharpe:<10.2f} {ret:<10.2f}% {dd:<10.2f}%"
        )

    print("\n" + "=" * 40)
    print("最佳参数组合:")
    best = sorted_results[0]
    print(best.params)
