# feed.resample / feed.replay API Draft

## API

```python
resampled = feed.resample(
    freq="15min",
    agg={"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"},
    label="right",
    closed="right",
)

replayed = feed.replay(
    freq="1h",
    align="session",
    day_mode="trading",
    emit_partial=False,
    session_windows=[("09:30", "11:30"), ("13:00", "15:00")],
)
```

## Current Minimal Delivery

- `BasePandasFeedAdapter` supports:
  - `resample(freq, agg=None, label="right", closed="right", emit_partial=True)`
  - `replay(freq, align="session", emit_partial=False, agg=None, label="right", closed="right")`
- Both return adapter objects that can be passed directly to `run_backtest(data=...)`.
- `replay(align="session")` supports per-trading-day partitioning, and drops each partition tail when `emit_partial=False`.
- `session_windows` can further split intraday sessions (for example, before/after lunch break) to avoid cross-session aggregation.
- `align` currently supports:
  - `session`: partition by trading day, with optional `session_windows`.
  - `day`: partition by day without `session_windows`, with configurable `day_mode`.
  - `global`: aggregate on the full timeline without day/session partitioning.
- `day_mode` currently supports:
  - `trading`: partition by local trading day under request timezone.
  - `calendar`: partition by UTC calendar day.
