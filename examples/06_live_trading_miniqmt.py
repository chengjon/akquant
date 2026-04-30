# -*- coding: utf-8 -*-
"""
AKQuant + MiniQMT example.

Current repository status:
  - In-memory placeholder mode works for strategy wiring/tests.
  - Real QMT bridge mode is not implemented in the current built-in MiniQMT gateway.

The commented broker_live block below is kept only as a migration sketch to show
the intended `gateway_options` shape once a real bridge and stock market-model
support are added.
"""

from datetime import datetime
from typing import Any

from akquant import AssetType, Bar, Instrument, Strategy

try:
    from akquant.live import LiveRunner
except ImportError as e:
    print(f"Error importing LiveRunner: {e}")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# 1. Strategy
# ---------------------------------------------------------------------------
class SimpleStockStrategy(Strategy):
    """Simple stock trading strategy for demonstration."""

    def __init__(self) -> None:
        super().__init__()
        self._bar_count = 0

    def on_start(self) -> None:
        print("[Strategy] Started")

    def on_bar(self, bar: Bar) -> None:
        self._bar_count += 1
        dt = datetime.fromtimestamp(bar.timestamp / 1e9)
        print(
            f"[Strategy] ON_BAR | {dt} | {bar.symbol} | "
            f"Close: {bar.close} | Vol: {bar.volume}"
        )

        pos = self.get_position(bar.symbol)

        # Simple logic: alternate buy/sell every 5 bars
        if self._bar_count % 5 == 0:
            if pos == 0:
                print(f"[Strategy] BUY 100 {bar.symbol}")
                self.buy(bar.symbol, 100)
            elif pos > 0:
                print(f"[Strategy] SELL 100 {bar.symbol}")
                self.sell(bar.symbol, 100)

    def on_order(self, order: Any) -> None:
        print(
            f"[Strategy] ON_ORDER | {order.symbol} | "
            f"{order.side} | {order.status} | "
            f"Filled: {order.filled_quantity}"
        )

    def on_trade(self, trade: Any) -> None:
        print(
            f"[Strategy] ON_TRADE | {trade.symbol} | "
            f"{trade.side} | {trade.quantity}@{trade.price}"
        )


# ---------------------------------------------------------------------------
# 2. Main
# ---------------------------------------------------------------------------
def main() -> None:
    instruments = [
        Instrument(
            symbol="600000",
            asset_type=AssetType.Stock,
            multiplier=1.0,
            margin_ratio=1.0,
            tick_size=0.01,
            lot_size=100,
            option_type=None,
            strike_price=None,
            expiry_date=None,
        ),
        Instrument(
            symbol="000001",
            asset_type=AssetType.Stock,
            multiplier=1.0,
            margin_ratio=1.0,
            tick_size=0.01,
            lot_size=100,
            option_type=None,
            strike_price=None,
            expiry_date=None,
        ),
    ]

    # --- Mode A: In-memory (no real broker) ---
    runner = LiveRunner(
        strategy_cls=SimpleStockStrategy,
        instruments=instruments,
        broker="miniqmt",
        trading_mode="paper",
    )
    print("[Main] Running in paper mode (in-memory, no real broker)...")
    # runner.run(cash=1_000_000, duration="5m")

    # --- Mode B: future QMT bridge sketch (not available today) ---
    # Keep this commented until MiniQMT real-broker integration is implemented.
    # Even after the bridge exists, MiniQMT stock broker_live still needs
    # LiveRunner/engine market-model work in the current repository.
    #
    # runner_live = LiveRunner(
    #     strategy_cls=SimpleStockStrategy,
    #     instruments=instruments,
    #     broker="miniqmt",
    #     trading_mode="broker_live",
    #     gateway_options={
    #         "qmt_path": "C:/QMT/userdata_mini",
    #         "account_id": "your_account_id",
    #     },
    # )
    # runner_live.run(cash=1_000_000)


if __name__ == "__main__":
    main()
