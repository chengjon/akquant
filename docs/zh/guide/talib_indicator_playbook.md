# 指标组合实战手册

本手册提供 `akquant.talib` 在策略实战中的组合方式、调参顺序与排错要点，面向“从 TA-Lib 迁移到 AKQuant”以及“新策略快速起步”两类场景。

## 0. 运行示例

```bash
python examples/45_talib_indicator_playbook_demo.py
python examples/45_talib_indicator_playbook_demo.py --data-source akshare --symbol sh600000 --start-date 20240101 --end-date 20260301
```

## 1. 快速起步

```python
from akquant import talib as ta

close = df["close"].to_numpy()
high = df["high"].to_numpy()
low = df["low"].to_numpy()
volume = df["volume"].to_numpy()

ema_fast = ta.EMA(close, timeperiod=20, backend="rust")
ema_slow = ta.EMA(close, timeperiod=60, backend="rust")
adx = ta.ADX(high, low, close, timeperiod=14, backend="rust")
natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")
```

## 2. 组合模板

| 目标 | 推荐组合 | 触发逻辑骨架 |
| :--- | :--- | :--- |
| 趋势跟随 | `EMA + ADX + NATR` | 趋势方向 + 趋势强度 + 波动过滤 |
| 均值回归 | `BBANDS + RSI + MOM` | 偏离带宽 + 超买超卖 + 短动量确认 |
| 量价确认 | `OBV + MFI + ROC` | 价格方向先行，成交量信号放行 |
| 跟踪止损 | `SAR + ATR` | 趋势持有 + 动态止损宽度 |

```python
upper, middle, lower = ta.BBANDS(close, timeperiod=20, backend="rust")
rsi = ta.RSI(close, timeperiod=14, backend="rust")
mom = ta.MOM(close, period=10, backend="rust")

long_signal = close[-1] < lower[-1] and rsi[-1] < 30 and mom[-1] > 0
exit_signal = close[-1] > middle[-1]
```

## 3. 调参顺序

建议固定以下顺序，避免参数空间爆炸：

1. 先定交易风格：趋势或均值回归。
2. 再定主信号：`EMA/BBANDS/SAR` 之一。
3. 再定过滤器：`ADX/RSI/MOM` 之一。
4. 最后定风险参数：`ATR/NATR` 阈值与止损系数。

## 4. warmup 与输出形态

- 大多数指标在 warmup 区段会返回 `NaN`，应先做空值过滤再下单。
- 多输出指标保持 tuple 结构：
  - `MACD -> (macd, signal, hist)`
  - `BBANDS -> (upper, middle, lower)`
  - `STOCH -> (slowk, slowd)`

```python
macd, signal, hist = ta.MACD(close, backend="rust")
if macd.size == 0:
    return
if not (macd[-1] == macd[-1] and signal[-1] == signal[-1]):
    return
```

## 5. 常见误区

- 只看单指标，不做趋势强度过滤，导致震荡期反复交易。
- 忽略 warmup 区段，直接使用尾值触发信号。
- 将参数一次性全局搜索，导致样本内过拟合。
- 迁移时直接切换 `rust`，未先与 `python` 基线对齐。

## 6. 迁移清单

1. 保持 TA-Lib 函数签名不变，先跑 `backend="python"`。
2. 验证输出结构与 warmup 一致后，再切到 `backend="rust"`。
3. 对支持 `period` 别名的指标优先沿用旧参数名。
4. 用固定样本建立最小回归测试。

相关文档：
- [TA-Lib Top20 迁移计划](../advanced/talib_top20_plan.md)
- [第 5 章：策略开发实战](../textbook/05_strategy.md)
- [可运行示例：45_talib_indicator_playbook_demo.py](https://github.com/akfamily/akquant/blob/main/examples/45_talib_indicator_playbook_demo.py)
