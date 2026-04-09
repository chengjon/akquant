"""
Walk-Forward Optimization (WFO) 示例.

演示如何使用 akquant 内置的 WFO 功能来评估策略的稳健性。
相比于普通的网格搜索，WFO 能更真实地模拟策略在未知数据上的表现，减少过拟合风险。
"""

from typing import Any, Dict

import numpy as np
import pandas as pd
from akquant import Bar, Strategy, run_walk_forward


class DualMovingAverageStrategy(Strategy):
    """双均线策略."""

    def __init__(self, short_window: int, long_window: int):
        """初始化策略.

        Args:
            short_window: 短期窗口
            long_window: 长期窗口
        """
        self.short_window = short_window
        self.long_window = long_window

    def on_bar(self, bar: Bar) -> None:
        """处理 Bar 数据.

        Args:
            bar: Bar 数据
        """
        # 获取历史收盘价
        hist = self.get_history(count=self.long_window + 1, field="close")
        if len(hist) < self.long_window:
            return

        closes = hist
        ma_short = np.mean(closes[-self.short_window :])
        ma_long = np.mean(closes[-self.long_window :])

        prev_ma_short = np.mean(closes[-self.short_window - 1 : -1])
        prev_ma_long = np.mean(closes[-self.long_window - 1 : -1])

        position = self.get_position(bar.symbol)

        # 金叉买入
        if prev_ma_short <= prev_ma_long and ma_short > ma_long:
            if position == 0:
                self.buy(bar.symbol, 100)

        # 死叉卖出
        elif prev_ma_short >= prev_ma_long and ma_short < ma_long:
            if position > 0:
                self.sell(bar.symbol, 100)


def warmup_calc(params: Dict[str, Any]) -> int:
    """动态计算预热期: 长期窗口 + 1."""
    return int(params["long_window"] + 1)


def param_constraint(params: Dict[str, Any]) -> bool:
    """参数约束: 短期窗口必须小于长期窗口."""
    return bool(params["short_window"] < params["long_window"])


if __name__ == "__main__":
    # 1. 生成模拟数据 (随机游走)
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", end="2023-12-31", freq="D")
    data_map: dict[str, pd.DataFrame] = {}
    for index, symbol in enumerate(["DEMO_A", "DEMO_B"]):
        returns = np.random.normal(0.0002 + index * 0.00005, 0.02, len(dates))
        price = (100 + index * 10) * np.cumprod(1 + returns)
        df = pd.DataFrame(
            {
                "date": dates,
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": 10000,
                "symbol": symbol,
            }
        )
        data_map[symbol] = df.set_index("date")

    print("Data loaded:", {symbol: frame.shape for symbol, frame in data_map.items()})

    # 2. 定义参数网格
    param_grid = {
        "short_window": [5, 10, 20],
        "long_window": [20, 40, 60, 100],
    }

    # 3. 运行 Walk-Forward Optimization
    # 训练窗口: 250天 (约1年)
    # 测试窗口: 60天 (约3个月)
    # 这样每3个月重新优化一次参数
    print("\nRunning Walk-Forward Optimization...")
    wfo_results = run_walk_forward(
        strategy=DualMovingAverageStrategy,
        param_grid=param_grid,
        data=data_map,
        train_period=250,
        test_period=60,
        metric="sharpe_ratio",  # 优化目标: 夏普比率
        initial_cash=100_000.0,
        warmup_calc=warmup_calc,
        constraint=param_constraint,
        compounding=False,  # 不使用复利拼接 (简单累加盈亏)
        symbols=list(data_map.keys()),
    )

    if not wfo_results.empty:
        print("\n=== WFO Results Summary ===")
        print(wfo_results.head())
        print(wfo_results.tail())

        # 计算总收益
        final_equity = wfo_results["equity"].iloc[-1]
        total_return = (final_equity - 100_000) / 100_000
        print(f"\nFinal Equity: {final_equity:,.2f}")
        print(f"Total Return: {total_return:.2%}")

        # 打印参数变化历史
        print("\nParameter Changes:")
        # 按每个测试窗口的第一行打印
        window_starts = wfo_results.groupby(["train_start", "train_end"]).first()
        for idx, row in window_starts.iterrows():
            print(
                f"Train[{idx[0].date()} - {idx[1].date()}] -> "  # type: ignore
                f"Params(short={row['short_window']}, long={row['long_window']})"
            )

    else:
        print("WFO returned no results.")
