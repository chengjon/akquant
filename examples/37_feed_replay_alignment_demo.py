from typing import List

import pandas as pd
from akquant.feed_adapter import BasePandasFeedAdapter, FeedSlice


class InMemoryAdapter(BasePandasFeedAdapter):
    """In-memory adapter for demo datasets."""

    name = "in_memory"

    def __init__(self, frame: pd.DataFrame) -> None:
        """Initialize adapter from source frame."""
        self.frame = frame.copy()

    def load(self, request: FeedSlice) -> pd.DataFrame:
        """Load one symbol slice."""
        frame = self.frame[
            self.frame["symbol"].astype(str) == str(request.symbol)
        ].copy()
        frame = self.normalize(frame, request.symbol)
        return self._clip_time_range(frame, request.start_time, request.end_time)


def _make_session_frame(symbol: str) -> pd.DataFrame:
    morning = pd.date_range(
        "2024-01-01 11:10:00",
        periods=20,
        freq="min",
        tz="Asia/Shanghai",
    )
    afternoon = pd.date_range(
        "2024-01-01 13:00:00",
        periods=10,
        freq="min",
        tz="Asia/Shanghai",
    )
    timestamps = list(morning) + list(afternoon)
    prices: List[float] = [100.0 + i * 0.1 for i in range(len(timestamps))]
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": prices,
            "high": [p + 0.2 for p in prices],
            "low": [p - 0.2 for p in prices],
            "close": [p + 0.1 for p in prices],
            "volume": [100.0] * len(timestamps),
            "symbol": [symbol] * len(timestamps),
        }
    )


def _make_day_mode_frame(symbol: str) -> pd.DataFrame:
    timestamps = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-02 07:55:00", tz="Asia/Shanghai"),
            pd.Timestamp("2024-01-02 08:05:00", tz="Asia/Shanghai"),
        ]
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [10.0, 11.0],
            "high": [10.2, 11.2],
            "low": [9.8, 10.8],
            "close": [10.1, 11.1],
            "volume": [100.0, 120.0],
            "symbol": [symbol, symbol],
        }
    )


def _print_frame(title: str, frame: pd.DataFrame) -> None:
    print(f"\n{title}")
    print(f"rows={len(frame)}")
    if frame.empty:
        print("(empty)")
        return
    print(frame[["open", "high", "low", "close", "volume", "symbol"]])


if __name__ == "__main__":
    symbol = "ALIGN"
    session_adapter = InMemoryAdapter(_make_session_frame(symbol))
    day_mode_adapter = InMemoryAdapter(_make_day_mode_frame(symbol))

    session_default = session_adapter.replay(
        freq="15min",
        align="session",
        emit_partial=False,
    ).load(FeedSlice(symbol=symbol, timezone="Asia/Shanghai"))
    session_split = session_adapter.replay(
        freq="15min",
        align="session",
        emit_partial=False,
        session_windows=[("09:30", "11:30"), ("13:00", "15:00")],
    ).load(FeedSlice(symbol=symbol, timezone="Asia/Shanghai"))
    global_result = session_adapter.replay(
        freq="15min",
        align="global",
        emit_partial=False,
    ).load(FeedSlice(symbol=symbol, timezone="Asia/Shanghai"))

    day_trading = day_mode_adapter.replay(
        freq="1D",
        align="day",
        day_mode="trading",
        emit_partial=True,
    ).load(FeedSlice(symbol=symbol, timezone="Asia/Shanghai"))
    day_calendar = day_mode_adapter.replay(
        freq="1D",
        align="day",
        day_mode="calendar",
        emit_partial=True,
    ).load(FeedSlice(symbol=symbol, timezone="Asia/Shanghai"))

    _print_frame("session align (default)", session_default)
    _print_frame("session align + session_windows", session_split)
    _print_frame("global align", global_result)
    _print_frame("day align + trading mode", day_trading)
    _print_frame("day align + calendar mode", day_calendar)

    print("\nDone.")
