# TA-Lib Top20 Plan

This page is currently maintained in Chinese first.

- Chinese page: [TA-Lib 迁移优先指标 Top20](../../zh/advanced/talib_top20_plan.md)
- Related docs:
  - [Capability Boost Plan](capability_boost_plan.md)
  - [Examples](../guide/examples.md)

## Current Status

- Top20 indicators are available on both backends (`python` and `rust`).
- Migration batches A/B/C are completed.
- Compatibility layer keeps TA-Lib-like signatures and tuple output contracts.

## Migration Examples

```python
from akquant import talib as ta

close = df["close"].to_numpy()
high = df["high"].to_numpy()
low = df["low"].to_numpy()
volume = df["volume"].to_numpy()

mfi = ta.MFI(high, low, close, volume, timeperiod=14, backend="rust")
obv = ta.OBV(close, volume, backend="rust")
tema = ta.TEMA(close, timeperiod=20, backend="rust")
natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")
sar = ta.SAR(high, low, acceleration=0.02, maximum=0.2, backend="rust")
```

## Strategy Combinations

```python
ema_fast = ta.EMA(close, timeperiod=20, backend="rust")
ema_slow = ta.EMA(close, timeperiod=60, backend="rust")
adx = ta.ADX(high, low, close, timeperiod=14, backend="rust")
natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")

trend_up = ema_fast[-1] > ema_slow[-1]
trend_strong = adx[-1] > 20
volatility_ok = natr[-1] < 4.0
```

For detailed warmup notes, parameter aliases, and full mapping table, use the Chinese page as the source of truth:
- [TA-Lib 迁移优先指标 Top20](../../zh/advanced/talib_top20_plan.md)
- [指标组合实战手册](../../zh/guide/talib_indicator_playbook.md)
