import pandas as pd
from akquant import Bar, OrderStatus, Strategy, run_backtest


class PartialFillOpenOrderStrategy(Strategy):
    """Strategy for verifying partial-fill status semantics."""

    def __init__(self) -> None:
        """Initialize state."""
        super().__init__()
        self.bar_count = 0
        self.observed_partial = False
        self.open_order_counts: list[int] = []

    def on_bar(self, bar: Bar) -> None:
        """Place one oversized order and track open-order status."""
        self.bar_count += 1
        open_orders = self.get_open_orders(bar.symbol)
        self.open_order_counts.append(len(open_orders))

        if any(o.status == OrderStatus.PartiallyFilled for o in open_orders):
            self.observed_partial = True

        if self.bar_count == 1:
            self.buy(bar.symbol, 100)


def test_partial_filled_status_and_open_orders_visibility() -> None:
    """Partial fills should expose PartiallyFilled status and remain open."""
    data = []
    for i in range(3):
        data.append(
            Bar(
                timestamp=pd.Timestamp(f"2023-01-0{i + 1} 10:00:00").value,
                open=10.0,
                high=10.0,
                low=10.0,
                close=10.0,
                volume=100.0,
                symbol="TEST",
            )
        )

    result = run_backtest(
        data=data,
        strategy=PartialFillOpenOrderStrategy,
        symbols="TEST",
        initial_cash=100000.0,
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        fill_policy={"price_basis": "close", "temporal": "same_cycle"},
        lot_size=1,
        volume_limit_pct=0.1,
        show_progress=False,
    )

    strategy = result.strategy
    assert strategy is not None
    assert strategy.open_order_counts[0] == 0
    assert strategy.observed_partial
    assert strategy.open_order_counts[-1] >= 1

    orders_df = result.orders_df
    assert not orders_df.empty
    order = orders_df.iloc[0]
    assert order["status"] == "partiallyfilled"
    assert 0.0 < order["filled_quantity"] < order["quantity"]
