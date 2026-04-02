"""Test custom matcher functionality."""

from typing import Optional

import akquant as aq
import pandas as pd
from akquant import AssetType, Bar, Instrument, Order, OrderStatus, Strategy, Trade


class CustomStockMatcher:
    """Custom stock matcher for testing."""

    def match(
        self,
        order: Order,
        event: Bar,
        instrument: Instrument,
        bar_index: int,
    ) -> Optional[Trade]:
        """Match order at the event close price and return a Trade or None."""
        if not hasattr(event, "close"):
            return None

        # Simple match logic: fill at close price
        fill_price = event.close

        # Update order status
        order.status = OrderStatus.Filled
        order.filled_quantity = order.quantity
        order.average_filled_price = fill_price

        # Create trade
        trade = Trade(
            id=f"trade_{order.id}",
            order_id=order.id,
            symbol=order.symbol,
            price=fill_price,
            quantity=order.quantity,
            side=order.side,
            timestamp=event.timestamp,
            commission=0.0,
            bar_index=bar_index,
        )
        print(
            f"[CustomMatcher] Filled order {order.id} at {fill_price}, "
            f"bar_index={bar_index}"
        )
        return trade


# 2. Setup Data
dates = pd.date_range("2024-01-01", periods=10, freq="D")
data = pd.DataFrame(
    {
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0,
        "volume": 1000,
        "symbol": "TEST",
    },
    index=dates,
)


# 3. Setup Strategy
class TestStrategy(Strategy):
    """Minimal strategy to trigger buy/sell for matcher testing."""

    def on_start(self) -> None:
        """Initialize internal counter."""
        self.count = 0

    def on_bar(self, bar: Bar) -> None:
        """Place orders on specific bars to exercise the matcher."""
        # Buy on first bar, Sell on second bar (bar index 0 and 1)
        # Note: on_bar is called for each bar.
        # Bar 0: Buy. Match on Bar 1.
        # Bar 1: Position is 100. Sell. Match on Bar 2.

        if self.count == 0:
            print(f"Sending Buy Order at {bar.timestamp}")
            self.buy(self.symbol, 100)
        elif self.count == 2:
            print(f"Sending Sell Order at {bar.timestamp}")
            self.sell(self.symbol, 100)

        self.count += 1


# 4. Run Backtest with custom matcher
print("Running backtest with custom matcher...")
custom_matchers = {AssetType.Stock: CustomStockMatcher()}

result = aq.run_backtest(
    strategy=TestStrategy,
    data=data,
    symbols="TEST",
    initial_cash=100000,
    custom_matchers=custom_matchers,
    asset_type=AssetType.Stock,  # Ensure instrument is stock
)

print("-" * 20)
print("Trades DF (Closed Trades):")
print(result.trades_df)

# Also check executions/orders
print("-" * 20)
print("Executions:")
if hasattr(result, "executions"):
    for exec in result.executions:
        print(exec)

if not result.trades_df.empty or (
    hasattr(result, "executions") and len(result.executions) > 0
):
    print("SUCCESS: Trades/Executions generated.")
else:
    print("FAILURE: No trades generated.")
