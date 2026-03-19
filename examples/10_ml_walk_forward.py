from typing import Any, cast

import numpy as np
import pandas as pd
from akquant.akquant import Bar
from akquant.backtest import run_backtest
from akquant.ml import SklearnAdapter
from akquant.strategy import Strategy
from sklearn.linear_model import LogisticRegression  # type: ignore


class WalkForwardStrategy(Strategy):
    """
    Demo strategy for Walk-forward Validation.

    Uses a logistic regression model to predict price direction.
    """

    def __init__(self) -> None:
        """Initialize the strategy."""
        super().__init__()

        # 1. Initialize model
        self.model = SklearnAdapter(LogisticRegression())

        # 2. Configure Walk-forward Validation
        # Framework automatically handles data slicing and retraining
        self.model.set_validation(
            method="walk_forward",
            train_window=50,  # Use last 50 bars for training
            rolling_step=10,  # Retrain every 10 bars
            frequency="1m",
            verbose=True,  # Print training logs
        )

        # Ensure we have enough history for features + training
        self.set_history_depth(60)

        print("WalkForwardStrategy initialized")

    def on_train_signal(self, context: Any) -> None:
        """Override on_train_signal to skip training during warmup."""
        if self._bar_count < 50:
            return
        super().on_train_signal(context)

    def prepare_features(
        self, df: pd.DataFrame, mode: str = "training"
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Feature Engineering (Shared by Training and Prediction).

        Returns X, y (y can be None/Invalid for prediction).
        """
        X = pd.DataFrame()
        X["ret1"] = df["close"].pct_change()
        X["ret2"] = df["close"].pct_change(2)
        # Remove fillna(0) to avoid treating padded NaNs as valid zero returns
        # X = X.fillna(0)

        # Construct Label y (Next period return)
        # shift(-1) moves future return to current row
        future_ret = df["close"].pct_change().shift(-1)

        # Combine into one DataFrame to align drops
        data = pd.concat([X, future_ret.rename("future_ret")], axis=1)

        # Drop rows with NaN features (e.g. from history padding or initial pct_change)
        data = data.dropna(subset=["ret1", "ret2"])

        if mode == "training":
            # For training, we must have a valid future return
            data = data.dropna(subset=["future_ret"])

        # Calculate y on valid data
        y = (data["future_ret"] > 0).astype(int)
        X_clean = data[["ret1", "ret2"]]

        return cast(pd.DataFrame, X_clean), cast(pd.Series, y)

    def on_bar(self, bar: Bar) -> None:
        """
        Handle bar event.

        :param bar: Current bar data
        """
        if self.model is None:
            return

        # Check if model is trained
        # A simple heuristic: check if we have passed the first training window
        if self._bar_count < 50:
            return

        # 3. Real-time Prediction
        # Reuse logic: Get recent history -> Extract features
        hist_df = self.get_history_df(5)

        # Manually calculate features for the last bar (or reuse prepare_features if
        # designed carefully)
        # Here we do it manually for efficiency/clarity or reuse prepare_features with
        # a trick

        # Reuse attempt:
        # prepare_features drops the last row (because of shift(-1)).
        # This means we can't use it directly to get the *current* feature vector for
        # *next* prediction?
        # Wait, to predict t+1, we need features at t.
        # prepare_features(df) -> X[t], y[t] (where y[t] is return at t+1).
        # We need X[t].
        # But prepare_features does X.iloc[:-1]. It drops X[t] because y[t] is
        # unknown!

        # So we need a separate feature extraction or a mode.
        # Let's stick to manual extraction for prediction in this demo,
        # or implement a flexible prepare_features.

        current_ret1 = (bar.close - hist_df["close"].iloc[-2]) / hist_df["close"].iloc[
            -2
        ]
        current_ret2 = (bar.close - hist_df["close"].iloc[-3]) / hist_df["close"].iloc[
            -3
        ]

        X_curr = pd.DataFrame([[current_ret1, current_ret2]], columns=["ret1", "ret2"])
        X_curr = X_curr.fillna(0)

        try:
            # Predict
            pred_prob = self.model.predict(X_curr)
            signal = (
                pred_prob[0] if isinstance(pred_prob, (list, np.ndarray)) else pred_prob
            )

            print(f"Bar {bar.timestamp}: Pred Signal = {signal:.4f}")

            if signal > 0.55:
                self.buy(bar.symbol, 100)
            elif signal < 0.45:
                self.sell(bar.symbol, 100)
        except Exception:
            # Model might not be fitted yet
            pass


if __name__ == "__main__":
    # 生成合成数据
    dates = pd.date_range(start="2023-01-01", periods=20000, freq="1min")
    # 随机漫步价格
    price = 100 + np.cumsum(np.random.randn(20000))
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": price,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": 1000,
            "symbol": "TEST",
        }
    )

    # 运行回测
    print("Running Walk-Forward Validation Backtest...")
    run_backtest(
        data=df,
        strategy=WalkForwardStrategy,
        symbols="TEST",
        lot_size=1,
        execution_mode="current_close",
        history_depth=60,  # Explicitly pass history depth to ensure engine enables it
    )
    print("Backtest finished.")
