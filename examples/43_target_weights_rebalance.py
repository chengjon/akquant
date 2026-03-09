from __future__ import annotations

from collections import defaultdict

import akquant as aq
import pandas as pd
from akquant import Bar, Strategy


def _build_symbol_df(
    symbol: str, timestamps: list[pd.Timestamp], closes: list[float]
) -> pd.DataFrame:
    rows = []
    for ts, close in zip(timestamps, closes):
        rows.append(
            {
                "date": ts,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 10000.0,
                "symbol": symbol,
            }
        )
    return pd.DataFrame(rows)


def make_data() -> dict[str, pd.DataFrame]:
    """Build deterministic multi-symbol demo data."""
    timestamps = list(
        pd.date_range("2024-01-02 10:00:00", periods=6, freq="D", tz="Asia/Shanghai")
    )
    return {
        "AAA": _build_symbol_df(
            "AAA", timestamps, [10.0, 10.2, 10.4, 10.5, 10.4, 10.3]
        ),
        "BBB": _build_symbol_df("BBB", timestamps, [10.0, 9.9, 9.8, 9.9, 10.0, 10.1]),
        "CCC": _build_symbol_df("CCC", timestamps, [10.0, 10.1, 10.0, 9.9, 9.8, 9.7]),
    }


class TargetWeightsRebalanceStrategy(Strategy):
    """Minimal target-weights rebalance demo."""

    def __init__(self, symbols: list[str]) -> None:
        """Initialize timestamp bucket and rebalance state."""
        super().__init__()
        self.symbols = symbols
        self.pending: dict[int, set[str]] = defaultdict(set)
        self.rebalance_count = 0

    def on_bar(self, bar: Bar) -> None:
        """Run rebalance once per complete timestamp."""
        bucket = self.pending[bar.timestamp]
        bucket.add(bar.symbol)
        if len(bucket) < len(self.symbols):
            return
        self.pending.pop(bar.timestamp, None)

        if self.rebalance_count == 0:
            weights = {"AAA": 0.6, "BBB": 0.3}
        elif self.rebalance_count == 1:
            weights = {"AAA": 0.2, "BBB": 0.6, "CCC": 0.1}
        else:
            weights = {"BBB": 0.7}

        self.order_target_weights(
            target_weights=weights,
            liquidate_unmentioned=True,
            rebalance_tolerance=0.01,
        )
        self.rebalance_count += 1


def main() -> None:
    """Run demo and print key outputs."""
    symbols = ["AAA", "BBB", "CCC"]
    result = aq.run_backtest(
        data=make_data(),
        strategy=TargetWeightsRebalanceStrategy,
        symbols=symbols,
        symbol="BENCHMARK",
        initial_cash=100000.0,
        commission_rate=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        min_commission=0.0,
        lot_size=1,
        execution_mode="current_close",
        show_progress=False,
    )

    print("final_positions")
    print(result.positions.iloc[-1])
    print("final_equity")
    print(float(result.equity_curve.iloc[-1]))


if __name__ == "__main__":
    main()
