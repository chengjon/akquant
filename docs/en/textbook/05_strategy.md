# Chapter 5: Strategy Development in Practice

This chapter is currently maintained in Chinese first.

- Chinese chapter: [第 5 章：策略开发实战 (Strategy Implementation)](../../zh/textbook/05_strategy.md)
- Textbook home: [Chinese textbook index](../../zh/textbook/index.md)
- Practice links:
  - Primary example: [examples/textbook/ch05_strategy.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch05_strategy.py)
  - Extended example: [examples/23_functional_callbacks_demo.py](https://github.com/akfamily/akquant/blob/main/examples/23_functional_callbacks_demo.py)
  - Indicator playbook example: [examples/45_talib_indicator_playbook_demo.py](https://github.com/akfamily/akquant/blob/main/examples/45_talib_indicator_playbook_demo.py)
  - Real-data mode: `python examples/45_talib_indicator_playbook_demo.py --data-source akshare --symbol sh600000 --start-date 20240101 --end-date 20260301`
  - Guide: [Strategy Guide](../guide/strategy.md)

## TA-Lib Backend Usage

```python
from akquant import talib as ta

close = df["close"].to_numpy()
high = df["high"].to_numpy()
low = df["low"].to_numpy()
volume = df["volume"].to_numpy()

rsi_py = ta.RSI(close, timeperiod=14, backend="python")
rsi_rs = ta.RSI(close, timeperiod=14, backend="rust")
mfi_rs = ta.MFI(high, low, close, volume, timeperiod=14, backend="rust")
tema_rs = ta.TEMA(close, timeperiod=20, backend="rust")
```

## Indicator Selection Template

- Trend-following: `EMA + ADX + NATR`
- Mean-reversion: `BBANDS + RSI`
- Volume confirmation: `OBV + MFI + ROC`
- Trailing risk control: `SAR + ATR`

```python
import numpy as np
from akquant import talib as ta

ema_fast = ta.EMA(close, timeperiod=20, backend="rust")
ema_slow = ta.EMA(close, timeperiod=60, backend="rust")
adx = ta.ADX(high, low, close, timeperiod=14, backend="rust")

if np.isnan(ema_fast[-1]) or np.isnan(adx[-1]):
    return
if ema_fast[-1] > ema_slow[-1] and adx[-1] >= 20:
    self.buy(symbol, 100)
```

For complete Chinese content including warmup handling and migration tips:
- [第 5 章：策略开发实战 (Strategy Implementation)](../../zh/textbook/05_strategy.md)
- [指标组合实战手册](../../zh/guide/talib_indicator_playbook.md)
