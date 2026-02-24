"""
第 10 章：可视化与报告 (Visualization).

本示例展示了如何将回测结果可视化，生成包含权益曲线、回撤图和日收益分布的综合图表。
AKQuant 内置了基于 `matplotlib` 的绘图工具，可以一键生成专业级报表。

依赖：
需要安装 matplotlib: `pip install matplotlib`

演示内容：
1. 运行一个简单的策略。
2. 使用 `aq.plot_result` 生成可视化图表。
3. 保存图表为图片文件。
"""

import akquant as aq
import numpy as np
import pandas as pd
from akquant import Bar, Strategy


# 模拟数据生成
def generate_mock_data(length: int = 500) -> pd.DataFrame:
    """生成模拟数据."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=length, freq="D")

    # 构造一个有趋势的数据，让曲线好看一些
    trend = np.linspace(100, 150, length)
    noise = np.cumsum(np.random.randn(length))
    prices = trend + noise

    df = pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices + 1,
            "low": prices - 1,
            "close": prices,
            "volume": 100000,
            "symbol": "MOCK_PLOT",
        }
    )
    return df


class PlotStrategy(Strategy):
    """可视化演示策略."""

    def __init__(self) -> None:
        """初始化策略."""
        super().__init__()
        self.ma_window = 20
        self.warmup_period = 20

    def on_bar(self, bar: Bar) -> None:
        """收到 Bar 事件的回调."""
        symbol = bar.symbol
        closes = self.get_history(
            count=self.ma_window + 1, symbol=symbol, field="close"
        )
        if len(closes) < self.ma_window + 1:
            return

        ma = closes[:-1][-self.ma_window :].mean()
        pos = self.get_position(symbol)

        # 简单的均线突破
        if bar.close > ma and pos == 0:
            self.order_target_percent(0.95, symbol)
        elif bar.close < ma and pos > 0:
            self.close_position(symbol)


if __name__ == "__main__":
    df = generate_mock_data()

    print("开始运行第 11 章可视化示例...")
    result = aq.run_backtest(
        strategy=PlotStrategy, data=df, initial_cash=100_000, commission_rate=0.0003
    )

    print("回测完成，正在生成图表...")

    try:
        # 使用 akquant 内置的绘图函数
        # filename: 如果指定，将保存为文件而不是直接弹窗显示
        aq.plot_result(
            result,
            filename="backtest_report.png",
            title="Moving Average Strategy Performance",
        )
        print("图表已保存至: backtest_report.png")

        # 如果在 Jupyter Notebook 中，可以直接显示
        # result.plot()

    except ImportError:
        print("绘图失败: 请确保安装了 matplotlib (pip install matplotlib)")
    except Exception as e:
        print(f"绘图过程中发生错误: {e}")
