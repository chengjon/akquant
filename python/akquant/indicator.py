from collections import deque
from typing import Any, Callable, Dict

import pandas as pd


class Indicator:
    """Wrapper for technical indicators."""

    def __init__(self, name: str, fn: Callable, **kwargs: Any) -> None:
        """Initialize the Indicator."""
        self.name = name
        self.fn = fn
        self.kwargs = kwargs
        self._data: Dict[str, pd.Series] = {}  # symbol -> series
        self._current_value: float = float("nan")

    def update(self, value: float) -> float:
        """Update indicator value (incremental)."""
        raise NotImplementedError(
            "Incremental update not implemented for this indicator."
        )

    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Calculate indicator on a DataFrame."""
        if symbol in self._data:
            return self._data[symbol]

        # Assume fn takes a series/df and returns a series
        # If kwargs contains column names, extract them
        # This is a simplified version of powerful DSL
        try:
            result = self.fn(df, **self.kwargs)
        except Exception:
            # Try passing column if specified in kwargs
            # e.g. rolling_mean(df['close'], window=5)
            # This part is tricky to generalize without a full DSL,
            # so we start simple: user passes a lambda or function that takes df
            result = self.fn(df)

        if not isinstance(result, pd.Series):
            # Try to convert if it's not a Series (e.g. numpy array)
            result = pd.Series(result, index=df.index)

        self._data[symbol] = result
        return result

    def get_value(self, symbol: str, timestamp: Any) -> float:
        """
        Get indicator value at specific timestamp (or latest before it).

        Uses asof lookup which is efficient for sorted time series.
        """
        if symbol not in self._data:
            return float("nan")

        series = self._data[symbol]
        # Assuming series index is datetime
        try:
            # Handle integer timestamp (nanoseconds)
            ts = timestamp
            if isinstance(timestamp, (int, float)):
                ts = pd.Timestamp(timestamp, unit="ns", tz="UTC")

            # Handle Timezone Mismatch
            if isinstance(series.index, pd.DatetimeIndex):
                if series.index.tz is None and getattr(ts, "tzinfo", None) is not None:
                    ts = ts.tz_localize(None)
                elif (
                    series.index.tz is not None and getattr(ts, "tzinfo", None) is None
                ):
                    ts = ts.tz_localize("UTC").tz_convert(series.index.tz)

            return float(series.asof(ts))  # type: ignore[arg-type]
        except Exception:
            return float("nan")


class IndicatorSet:
    """Collection of indicators for easy management."""

    def __init__(self) -> None:
        """Initialize the IndicatorSet."""
        self._indicators: Dict[str, Indicator] = {}

    def add(self, name: str, fn: Callable, **kwargs: Any) -> None:
        """Add an indicator to the set."""
        self._indicators[name] = Indicator(name, fn, **kwargs)

    def get(self, name: str) -> Indicator:
        """Get an indicator by name."""
        return self._indicators[name]

    def calculate_all(self, df: pd.DataFrame, symbol: str) -> Dict[str, pd.Series]:
        """Calculate all indicators for the given dataframe."""
        results = {}
        for name, ind in self._indicators.items():
            results[name] = ind(df, symbol)
        return results


class SMA(Indicator):
    """Simple Moving Average."""

    def __init__(self, window: int) -> None:
        """Initialize SMA."""
        super().__init__("sma", self._calc_sma)
        self.window = window
        self._cache: Dict[str, pd.Series] = {}  # symbol -> series
        self._current_value = float("nan")
        self._buffer: deque = deque()
        self._sum = 0.0

    def _calc_sma(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(self.window).mean()

    def update(self, value: float) -> float:
        """Update with new value (incremental)."""
        if pd.isna(value):
            return self._current_value

        if len(self._buffer) == self.window:
            removed = self._buffer.popleft()
            self._sum -= removed

        self._buffer.append(value)
        self._sum += value

        if len(self._buffer) == self.window:
            self._current_value = self._sum / self.window
        else:
            self._current_value = float("nan")

        return self._current_value

    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Calculate SMA."""
        result = df["close"].rolling(self.window).mean()
        self._cache[symbol] = result
        return result

    @property
    def value(self) -> float:
        """Get current value (requires strategy context injection)."""
        # This relies on Strategy injecting itself or data
        # For now, we use a simple mechanism:
        # Strategy calls update() or sets current_bar
        return self._current_value

    def __getstate__(self) -> Dict[str, Any]:
        """Pickle support."""
        state = self.__dict__.copy()
        # Don't save cache to save space, or save it if we want full state
        # For warm start, we might want to clear cache and re-calculate on new data
        # BUT, if we want to support 'streaming' updates later, we need state.
        # For current DataFrame-based indicator, re-calculation is fast.
        state["_cache"] = {}
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Unpickle support."""
        self.__dict__.update(state)


class EMA(Indicator):
    """Exponential Moving Average."""

    def __init__(self, window: int) -> None:
        """Initialize EMA."""
        super().__init__("ema", self._calc_ema)
        self.window = window
        self.alpha = 2.0 / (window + 1)
        self._cache: Dict[str, pd.Series] = {}
        self._current_value = float("nan")
        self._initialized = False

    def _calc_ema(self, df: pd.DataFrame) -> pd.Series:
        return df["close"].ewm(span=self.window, adjust=False).mean()

    def update(self, value: float) -> float:
        """Update with new value (incremental)."""
        if pd.isna(value):
            return self._current_value

        if not self._initialized:
            self._current_value = value
            self._initialized = True
        else:
            self._current_value = (
                self.alpha * value
                + (1 - self.alpha) * self._current_value
            )

        return self._current_value

    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Calculate EMA."""
        result = df["close"].ewm(span=self.window, adjust=False).mean()
        self._cache[symbol] = result
        return result

    @property
    def value(self) -> float:
        """Get current value."""
        return self._current_value

    def __getstate__(self) -> Dict[str, Any]:
        """Pickle support."""
        state = self.__dict__.copy()
        state["_cache"] = {}
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Unpickle support."""
        self.__dict__.update(state)


class RSI(Indicator):
    """Relative Strength Index."""

    def __init__(self, window: int = 14) -> None:
        """Initialize RSI."""
        super().__init__("rsi", self._calc_rsi)
        self.window = window
        self._cache: Dict[str, pd.Series] = {}
        self._current_value = float("nan")
        self._prev_value: float = float("nan")
        self._avg_gain: float = 0.0
        self._avg_loss: float = 0.0
        self._count: int = 0

    def _calc_rsi(self, df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.window, min_periods=self.window).mean()
        avg_loss = loss.rolling(self.window, min_periods=self.window).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        return 100 - 100 / (1 + rs)

    def update(self, value: float) -> float:
        """Update with new value (incremental)."""
        if pd.isna(value):
            return self._current_value

        self._count += 1

        if self._count == 1:
            self._prev_value = value
            self._current_value = float("nan")
            return self._current_value

        change = value - self._prev_value
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._prev_value = value

        if self._count <= self.window:
            self._avg_gain += gain
            self._avg_loss += loss
            if self._count == self.window:
                self._avg_gain /= self.window
                self._avg_loss /= self.window
                if self._avg_loss == 0:
                    self._current_value = 100.0
                else:
                    rs = self._avg_gain / self._avg_loss
                    self._current_value = 100.0 - 100.0 / (1 + rs)
            else:
                self._current_value = float("nan")
        else:
            self._avg_gain = (self._avg_gain * (self.window - 1) + gain) / self.window
            self._avg_loss = (self._avg_loss * (self.window - 1) + loss) / self.window
            if self._avg_loss == 0:
                self._current_value = 100.0
            else:
                rs = self._avg_gain / self._avg_loss
                self._current_value = 100.0 - 100.0 / (1 + rs)

        return self._current_value

    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Calculate RSI."""
        result = self._calc_rsi(df)
        self._cache[symbol] = result
        return result

    @property
    def value(self) -> float:
        """Get current value."""
        return self._current_value

    def __getstate__(self) -> Dict[str, Any]:
        """Pickle support."""
        state = self.__dict__.copy()
        state["_cache"] = {}
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Unpickle support."""
        self.__dict__.update(state)


class MACD(Indicator):
    """Moving Average Convergence Divergence."""

    def __init__(
        self, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> None:
        """Initialize MACD."""
        super().__init__("macd", self._calc_macd)
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self._cache: Dict[str, pd.Series] = {}
        self._current_value = float("nan")
        self._fast_ema: float = float("nan")
        self._slow_ema: float = float("nan")
        self._signal_line: float = float("nan")
        self._histogram: float = float("nan")
        self._fast_alpha = 2.0 / (fast + 1)
        self._slow_alpha = 2.0 / (slow + 1)
        self._signal_alpha = 2.0 / (signal + 1)
        self._fast_initialized = False
        self._slow_initialized = False
        self._signal_initialized = False

    def _calc_macd(self, df: pd.DataFrame) -> pd.Series:
        fast_ema = df["close"].ewm(span=self.fast, adjust=False).mean()
        slow_ema = df["close"].ewm(span=self.slow, adjust=False).mean()
        return fast_ema - slow_ema

    def update(self, value: float) -> float:
        """Update with new value (incremental)."""
        if pd.isna(value):
            return self._current_value

        # Update fast EMA
        if not self._fast_initialized:
            self._fast_ema = value
            self._fast_initialized = True
        else:
            self._fast_ema = (
                self._fast_alpha * value
                + (1 - self._fast_alpha) * self._fast_ema
            )

        # Update slow EMA
        if not self._slow_initialized:
            self._slow_ema = value
            self._slow_initialized = True
        else:
            self._slow_ema = (
                self._slow_alpha * value
                + (1 - self._slow_alpha) * self._slow_ema
            )

        # Compute MACD line
        macd_line = self._fast_ema - self._slow_ema

        # Update signal line (EMA of MACD line)
        if not self._signal_initialized:
            self._signal_line = macd_line
            self._signal_initialized = True
        else:
            self._signal_line = (
                self._signal_alpha * macd_line
                + (1 - self._signal_alpha) * self._signal_line
            )

        self._histogram = macd_line - self._signal_line
        self._current_value = macd_line
        return self._current_value

    def __call__(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Calculate MACD line."""
        result = self._calc_macd(df)
        self._cache[symbol] = result
        return result

    @property
    def value(self) -> float:
        """Get current MACD line value."""
        return self._current_value

    @property
    def signal_line(self) -> float:
        """Get current signal line value."""
        return self._signal_line

    @property
    def histogram(self) -> float:
        """Get current histogram value."""
        return self._histogram

    def __getstate__(self) -> Dict[str, Any]:
        """Pickle support."""
        state = self.__dict__.copy()
        state["_cache"] = {}
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Unpickle support."""
        self.__dict__.update(state)
