"""
ETF 期权 Greek 风控示例.

演示:
1. calculate_option_greeks() 计算 Delta/Gamma/Theta/Vega/Rho
2. RiskConfig 配置 Greek 限额 (max_portfolio_delta)
3. 订单因超限被风控拒绝
4. calculate_implied_volatility() 隐含波动率求解
5. calculate_option_margin() 保证金计算
"""

import pandas as pd
from akquant import (
    BacktestConfig,
    Bar,
    InstrumentConfig,
    Strategy,
    StrategyConfig,
    calculate_implied_volatility,
    calculate_option_greeks,
    run_backtest,
)
from akquant.config import RiskConfig
from akquant.option.queries import calculate_option_margin


# ---------------------------------------------------------------------------
# Part 1: Greeks 计算
# ---------------------------------------------------------------------------
def demo_greeks() -> None:
    """计算 ATM / OTM 看涨和看跌期权的 Greeks."""
    print("=" * 60)
    print("Part 1: Option Greeks 计算 (BSM 模型)")
    print("=" * 60)

    underlying = 2.5  # ETF 标的价格
    strike_atm = 2.5
    strike_otm = 2.6
    ttm = 0.25  # 3 个月到期
    r = 0.02
    vol = 0.25

    for label, strike, opt_type in [
        ("ATM 看涨", strike_atm, "CALL"),
        ("OTM 看涨", strike_otm, "CALL"),
        ("ATM 看跌", strike_atm, "PUT"),
        ("OTM 看跌", 2.4, "PUT"),
    ]:
        g = calculate_option_greeks(underlying, strike, ttm, r, vol, opt_type)
        print(f"\n{label} (K={strike}, T={ttm}年, σ={vol}):")
        print(f"  理论价格 = {g.price:.4f}")
        print(f"  Delta    = {g.delta:.4f}")
        print(f"  Gamma    = {g.gamma:.4f}")
        print(f"  Theta    = {g.theta:.4f}")
        print(f"  Vega     = {g.vega:.4f}")
        print(f"  Rho      = {g.rho:.4f}")


# ---------------------------------------------------------------------------
# Part 2: 带有 Greek 风控限制的回测策略
# ---------------------------------------------------------------------------
class GreekLimitedStrategy(Strategy):
    """买入看涨期权策略, 受 Delta 限额约束."""

    def on_bar(self, bar: Bar) -> None:
        """K线回调: 当标的价格上穿均线时买入看涨期权."""
        if bar.symbol != "CALL_ATM":
            return

        # 已持仓则不再买入
        if self.get_position("CALL_ATM") > 0:
            return

        qty = 10  # 10 张合约
        print(f"[{bar.timestamp_str}] 尝试买入 {qty} 张 CALL_ATM @ {bar.close:.4f}")
        self.buy("CALL_ATM", qty)


def demo_greek_risk_backtest() -> None:
    """运行带有 max_portfolio_delta 限制的回测."""
    print("\n" + "=" * 60)
    print("Part 2: Greek 风控回测 (max_portfolio_delta=50)")
    print("=" * 60)

    # 构造合成数据: 标的与期权
    dates = pd.date_range("2024-01-02", periods=60, freq="1min")
    base_price = 2.5

    data_call = pd.DataFrame({
        "timestamp": dates,
        "open": [0.12] * 60,
        "high": [0.13] * 60,
        "low": [0.11] * 60,
        "close": [0.12] * 60,
        "volume": [500] * 60,
        "symbol": "CALL_ATM",
    })
    data_ul = pd.DataFrame({
        "timestamp": dates,
        "open": [base_price] * 60,
        "high": [base_price + 0.01] * 60,
        "low": [base_price - 0.01] * 60,
        "close": [base_price] * 60,
        "volume": [10000] * 60,
        "symbol": "ETF_50",
    })

    risk_config = RiskConfig(
        max_portfolio_delta=50.0,  # 组合 Delta 上限
        option_default_volatility=0.25,
        option_risk_free_rate=0.02,
    )

    config = BacktestConfig(
        strategy_config=StrategyConfig(
            initial_cash=500_000.0,
            risk=risk_config,
        ),
        instruments_config=[
            InstrumentConfig(
                symbol="CALL_ATM",
                asset_type="OPTION",
                multiplier=10000.0,
                margin_ratio=0.1,
                tick_size=0.0001,
                option_type="CALL",
                strike_price=2.5,
                expiry_date=20240322,
                underlying_symbol="ETF_50",
                settlement_type="cash",
            ),
            InstrumentConfig(
                symbol="ETF_50",
                asset_type="STOCK",
                multiplier=1.0,
                margin_ratio=1.0,
                tick_size=0.001,
            ),
        ],
    )

    result = run_backtest(
        data={"CALL_ATM": data_call, "ETF_50": data_ul},
        strategy=GreekLimitedStrategy,
        config=config,
        commission_rate=0.0,
        show_progress=False,
    )

    print("\n--- 订单结果 ---")
    for order in result.orders:
        status = order.status
        reason = order.reject_reason or "-"
        print(f"  ID={order.id}  {order.symbol}  qty={order.quantity}  "
              f"status={status}  reject_reason={reason}")

    print(f"\n最终资金: {result.metrics.end_market_value:.2f}")


# ---------------------------------------------------------------------------
# Part 3: 隐含波动率求解
# ---------------------------------------------------------------------------
def demo_iv() -> None:
    """从市场价格反推隐含波动率."""
    print("\n" + "=" * 60)
    print("Part 3: 隐含波动率求解 (Newton-Raphson)")
    print("=" * 60)

    # 先用已知参数生成理论价格
    underlying = 2.5
    strike = 2.5
    ttm = 0.25
    r = 0.02
    true_vol = 0.30  # 真实波动率 30%

    g = calculate_option_greeks(underlying, strike, ttm, r, true_vol, "CALL")
    market_price = g.price
    print(f"真实波动率 = {true_vol:.2%}  ->  理论价格 = {market_price:.4f}")

    # 反推 IV
    iv = calculate_implied_volatility(
        market_price, underlying, strike, ttm, r, "CALL"
    )
    if iv is not None:
        print(f"隐含波动率 = {iv:.4f} ({iv:.2%})")
        print(f"误差       = {abs(iv - true_vol):.2e}")
    else:
        print("IV 求解失败: 未收敛")


# ---------------------------------------------------------------------------
# Part 4: 保证金计算
# ---------------------------------------------------------------------------
def demo_margin() -> None:
    """展示卖方保证金计算 (中国交易所标准公式)."""
    print("\n" + "=" * 60)
    print("Part 4: 保证金计算 (卖方)")
    print("=" * 60)

    # 买方保证金为 0
    margin_long = calculate_option_margin(
        quantity=1, option_price=0.15, underlying_price=2.5,
        multiplier=10000, margin_ratio=0.2, is_short=False,
    )
    print(f"买方保证金 (long): {margin_long:,.2f}")

    # 卖方: ATM 看涨
    margin_short_call = calculate_option_margin(
        quantity=-1, option_price=0.15, underlying_price=2.5,
        multiplier=10000, margin_ratio=0.2, is_short=True,
        strike=2.5, option_type="CALL",
    )
    print(f"卖方保证金 (short ATM Call, K=2.5): {margin_short_call:,.2f}")

    # 卖方: OTM 看涨
    margin_short_otm = calculate_option_margin(
        quantity=-1, option_price=0.08, underlying_price=2.5,
        multiplier=10000, margin_ratio=0.2, is_short=True,
        strike=2.6, option_type="CALL",
    )
    print(f"卖方保证金 (short OTM Call, K=2.6): {margin_short_otm:,.2f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """运行全部示例."""
    demo_greeks()
    demo_greek_risk_backtest()
    demo_iv()
    demo_margin()
    print("\n全部示例运行完毕。")


if __name__ == "__main__":
    main()
