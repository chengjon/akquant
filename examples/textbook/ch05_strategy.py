"""
第 4 章：构建第一个策略 (Strategy).

本示例详细展示了一个完整策略的结构，重点介绍：
1. **策略生命周期**：`__init__`, `on_start`, `on_bar`, `on_stop`
2. **数据获取**：使用 `get_history` 获取过去 N 天的数据
3. **交易接口**：使用 `buy`, `sell` 和 `order_target_percent`
4. **日志记录**：使用 `self.log` 记录关键信息

策略逻辑 (双均线改进版)：
- 计算 5日均线 (MA5) 和 20日均线 (MA20)
- 金叉 (MA5 > MA20) 且无持仓 -> 买入
- 死叉 (MA5 < MA20) 且有持仓 -> 卖出
- 增加风控：如果亏损超过 5%，强制止损
"""

import akquant as aq
import numpy as np
import pandas as pd
from akquant import Bar, Strategy


# 模拟数据生成 (与第3章相同，方便复现)
def generate_mock_data(length: int = 500) -> pd.DataFrame:
    """生成模拟数据."""
    np.random.seed(42)
    dates = pd.date_range(start="2022-01-01", periods=length, freq="D")
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


class MyFirstStrategy(Strategy):
    """第一个策略示例."""

    # --------------------------------------------------------------------------
    # 1. 初始化 (Initialization)
    # --------------------------------------------------------------------------
    def __init__(
        self, short_window: int = 5, long_window: int = 20, stop_loss_pct: float = 0.05
    ) -> None:
        """策略初始化函数. 在这里定义策略的参数和内部变量.

        注意：此时回测引擎尚未启动，无法访问 context。
        """
        super().__init__()

        # 策略参数
        self.short_window = short_window
        self.long_window = long_window
        self.stop_loss_pct = stop_loss_pct

        # 内部状态变量
        self.entry_price = 0.0  # 记录开仓价格

        # 设置预热期 (Warmup Period)
        # 引擎会在正式回测前预加载数据，确保 get_history 能获取到足够的数据
        self.warmup_period = long_window

    # --------------------------------------------------------------------------
    # 2. 启动回调 (On Start)
    # --------------------------------------------------------------------------
    def on_start(self) -> None:
        """回测开始时触发. 此时引擎已就绪，可以进行一些初始化操作."""
        self.log("策略启动！")
        self.log(
            f"参数设置: MA{self.short_window} vs MA{self.long_window}, "
            f"止损={self.stop_loss_pct:.1%}"
        )

    # --------------------------------------------------------------------------
    # 3. Bar 数据回调 (On Bar) - 核心逻辑
    # --------------------------------------------------------------------------
    def on_bar(self, bar: Bar) -> None:
        """每根 K 线走完时触发."""
        symbol = bar.symbol

        # 3.1 获取历史数据
        # count=21 表示获取过去 21 根 Bar (包含当前这根)
        closes = self.get_history(
            count=self.long_window + 1, symbol=symbol, field="close"
        )

        # 再次检查数据长度 (防御性编程)
        if len(closes) < self.long_window + 1:
            return

        # 3.2 计算技术指标
        # 使用切片 [:-1] 排除当前 Bar，只用截止到昨天的数据计算信号 (避免未来函数)
        # 这里的逻辑假设我们在今天收盘后计算信号，明天开盘交易
        history_closes = closes[:-1]
        ma_short = history_closes[-self.short_window :].mean()
        ma_long = history_closes[-self.long_window :].mean()

        # 3.3 获取账户信息
        current_pos = self.get_position(symbol)

        # 3.4 交易逻辑

        # 情况 A: 持仓中 -> 检查止损或死叉
        if current_pos > 0:
            # 计算浮动盈亏比例
            pnl_pct = (bar.close - self.entry_price) / self.entry_price

            # 止损检查
            if pnl_pct < -self.stop_loss_pct:
                self.log(f"触发止损! 当前亏损: {pnl_pct:.2%}")
                self.close_position(symbol)  # 清仓
                return

            # 死叉卖出
            if ma_short < ma_long:
                self.log(
                    f"死叉卖出 (MA{self.short_window}={ma_short:.2f} < "
                    f"MA{self.long_window}={ma_long:.2f})"
                )
                self.close_position(symbol)  # 清仓

        # 情况 B: 空仓中 -> 检查金叉
        elif current_pos == 0:
            if ma_short > ma_long:
                self.log(
                    f"金叉买入 (MA{self.short_window}={ma_short:.2f} > "
                    f"MA{self.long_window}={ma_long:.2f})"
                )

                # 使用 order_target_percent 买入 95% 的资金
                self.order_target_percent(0.95, symbol)

                # 记录开仓价格 (近似值，实际成交价要等订单成交后才知道，这里暂用
                # 收盘价代替)
                self.entry_price = bar.close

    # --------------------------------------------------------------------------
    # 4. 结束回调 (On Stop)
    # --------------------------------------------------------------------------
    def on_stop(self) -> None:
        """回测结束时触发. 常用于统计结果或资源释放."""
        self.log("策略停止。")


if __name__ == "__main__":
    df = generate_mock_data()

    print("开始运行第 4 章示例策略...")
    result = aq.run_backtest(
        strategy=MyFirstStrategy,
        data=df,
        initial_cash=100_000,
        commission_rate=0.0003,  # 万三手续费
    )

    # 打印最终资金
    metrics = result.metrics_df
    end_value = (
        metrics.loc["end_market_value", "value"]
        if "end_market_value" in metrics.index
        else 0.0
    )
    print(f"回测结束，最终权益: {float(str(end_value)):.2f}")
