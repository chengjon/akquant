"""
第 1 章：快速开始 (Quickstart).

本示例演示了使用 AKQuant 进行量化回测的最基础流程。
为了展示真实的交易结果，我们将实现一个经典的**双均线策略 (Dual Moving Average)**。

策略逻辑：
1. 计算 5 日均线 (MA5) 和 20 日均线 (MA20)。
2. 金叉买入：当 MA5 上穿 MA20，且当前无持仓时，满仓买入。
3. 死叉卖出：当 MA5 下穿 MA20，且当前有持仓时，清仓卖出。
"""

import akquant as aq
import numpy as np
import pandas as pd
from akquant import Bar, Strategy

try:
    import akshare as ak

    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False


def get_data() -> pd.DataFrame:
    """
    步骤 1: 数据获取.

    优先使用 akshare 获取浦发银行 (600000) 的历史日线数据。
    若未安装 akshare，则使用合成数据。
    """
    if HAS_AKSHARE:
        print("正在获取数据 (akshare)...")
        df = ak.stock_zh_a_daily(
            symbol="sh600000", start_date="20200101", end_date="20231231", adjust="qfq"
        )
        df["symbol"] = "600000"
        if "date" not in df.columns:
            df = df.reset_index().rename(columns={"index": "date"})
        return df  # type: ignore

    print("未安装 akshare，使用合成数据...")
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", periods=500, freq="D")
    prices = 10 + np.cumsum(np.random.randn(500) * 0.1)
    return pd.DataFrame(
        {
            "date": dates,
            "open": prices + np.random.rand(500) * 0.2,
            "high": prices + 0.3,
            "low": prices - 0.3,
            "close": prices,
            "volume": 1000000,
            "symbol": "600000",
        }
    )


class DualMAStrategy(Strategy):
    """
    步骤 2: 策略定义.

    双均线策略实现。
    """

    def __init__(self) -> None:
        """策略初始化."""
        super().__init__()
        self.short_window = 5
        self.long_window = 20
        self.warmup_period = self.long_window

    def on_start(self) -> None:
        """策略初始化时调用."""
        print("策略初始化...")

    def on_bar(self, bar: Bar) -> None:
        """核心交易逻辑."""
        symbol = bar.symbol

        # 1. 获取历史数据
        closes = self.get_history(count=self.long_window, symbol=symbol, field="close")

        # 2. 计算均线
        ma5_curr = closes[-self.short_window :].mean()
        ma20_curr = closes[-self.long_window :].mean()

        # 3. 获取持仓
        position = self.get_position(symbol)

        # 4. 交易信号
        if ma5_curr > ma20_curr and position == 0:
            print(
                f"[{bar.timestamp_str}] 金叉买入 (MA5={ma5_curr:.2f}, "
                f"MA20={ma20_curr:.2f})"
            )
            self.order_target_percent(0.95, symbol)

        elif ma5_curr < ma20_curr and position > 0:
            print(
                f"[{bar.timestamp_str}] 死叉卖出 (MA5={ma5_curr:.2f}, "
                f"MA20={ma20_curr:.2f})"
            )
            self.order_target_percent(0.0, symbol)


if __name__ == "__main__":
    # 1. 准备数据
    df = get_data()

    # 2. 运行回测
    print("开始回测...")
    result = aq.run_backtest(
        strategy=DualMAStrategy,
        data=df,
        initial_cash=100_000,
        commission_rate=0.0003,
        stamp_tax_rate=0.001,
        lot_size=100,
    )

    # 3. 打印结果
    print("\n" + "=" * 30)
    print("回测结果摘要")
    print("=" * 30)
    print(result)
