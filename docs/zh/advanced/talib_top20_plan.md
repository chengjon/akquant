# TA-Lib 迁移优先指标 Top20

## 目标

- 覆盖高频迁移场景中的常用指标，优先减少策略迁移改造量。
- 建立统一指标注册表元数据：名称、参数、输出、warmup。

## 当前状态（2026-03）

- `akquant.talib` 已支持 `backend` 参数：`auto/python/rust`。
- 批次 A/B/C 已全部完成 Rust 下沉并通过回归测试。
- Top20 指标已全部实现双后端（Python/Rust）兼容。
- Top20 之外已新增批次 D 首批 5 项：`WMA/ADXR/CMO/TRANGE/BOP`。
- Top20 之外已新增批次 E 首批 5 项：`PPO/APO/ULTOSC/PLUS_DI/MINUS_DI`。
- Top20 之外已新增批次 F 首批 5 项：`DX/AD/ADOSC/AROON/AROONOSC`。
- Top20 之外已新增批次 G 首批 5 项：`TRIMA/STDDEV/VAR/LINEARREG/LINEARREG_SLOPE`。
- Top20 之外已新增批次 H 首批 5 项：`LINEARREG_INTERCEPT/LINEARREG_ANGLE/TSF/CORREL/BETA`。
- Top20 之外已新增批次 I 首批 5 项：`LINEARREG_R2/T3/MEDPRICE/TYPPRICE/WCLPRICE`。
- Top20 之外已新增批次 J 首批 5 项：`AVGPRICE/MIDPOINT/MIDPRICE/HT_TRENDLINE/MAMA`。
- Top20 之外已新增批次 K 首批 5 项：`MAX/MIN/MAXINDEX/MININDEX/MINMAX`。
- Top20 之外已新增批次 L 首批 5 项：`SUM/AVGDEV/RANGE/STDDEV扩展/VAR扩展`。
- Top20 之外已新增批次 M 首批 5 项：`MINMAXINDEX/ROCP/ROCR/ROCR100/COVAR`。
- Top20 之外已新增批次 N 首批 5 项：`LN/LOG10/SQRT/CEIL/FLOOR`。
- Top20 之外已新增批次 O 首批 5 项：`SIN/COS/TAN/ASIN/ACOS`。
- Top20 之外已新增批次 P 首批 5 项：`ATAN/SINH/COSH/TANH/EXP`。
- Top20 之外已新增批次 Q 首批 5 项：`ABS/SIGN/ADD/SUB/MULT`。
- Top20 之外已新增批次 R 首批 5 项：`DIV/MAX2/MIN2/CLIP/ROUND`。
- Top20 之外已新增批次 S 首批 5 项：`POW/MOD/CLAMP01/SQ/CUBE`。
- 兼容层的单输出与多输出结构均已稳定（如 `MACD/BBANDS/STOCH`）。

### 已支持指标矩阵

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| SMA | ✅ | ✅ | 单序列 |
| EMA | ✅ | ✅ | 单序列 |
| MACD | ✅ | ✅ | 三序列 `(macd, signal, hist)` |
| RSI | ✅ | ✅ | 单序列 |
| BBANDS | ✅ | ✅ | 三序列 `(upper, middle, lower)` |
| ATR | ✅ | ✅ | 单序列 |
| ROC | ✅ | ✅ | 单序列 |
| WILLR | ✅ | ✅ | 单序列 |
| CCI | ✅ | ✅ | 单序列 |
| ADX | ✅ | ✅ | 单序列 |
| STOCH | ✅ | ✅ | 双序列 `(slowk, slowd)` |
| MFI | ✅ | ✅ | 单序列 |
| OBV | ✅ | ✅ | 单序列 |
| TRIX | ✅ | ✅ | 单序列 |
| MOM | ✅ | ✅ | 单序列 |
| DEMA | ✅ | ✅ | 单序列 |
| TEMA | ✅ | ✅ | 单序列 |
| KAMA | ✅ | ✅ | 单序列 |
| NATR | ✅ | ✅ | 单序列 |
| SAR | ✅ | ✅ | 单序列 |

测试入口：
- [test_talib_compat.py](https://github.com/akfamily/akquant/blob/main/tests/test_talib_compat.py)
- [test_talib_backend.py](https://github.com/akfamily/akquant/blob/main/tests/test_talib_backend.py)

## Top20 清单（按迁移收益）

| 优先级 | 指标 | 分类 | 迁移价值 |
| :--- | :--- | :--- | :--- |
| 1 | SMA | Trend | 已内建，作为兼容基线 |
| 2 | EMA | Trend | 已内建，作为兼容基线 |
| 3 | MACD | Trend | 已内建，产出多值 |
| 4 | RSI | Momentum | 已内建，广泛使用 |
| 5 | BBANDS | Volatility | 已内建，三轨输出 |
| 6 | ATR | Volatility | 已内建，风控常用 |
| 7 | ADX | Trend | 趋势强度核心 |
| 8 | CCI | Momentum | 商品与择时常用 |
| 9 | STOCH | Momentum | KDJ 相关迁移核心 |
| 10 | WILLR | Momentum | 轻量超买超卖 |
| 11 | ROC | Momentum | 动量与因子常见 |
| 12 | MFI | Volume | 量价结合常用 |
| 13 | OBV | Volume | 趋势确认常用 |
| 14 | TRIX | Trend | 中频策略迁移常见 |
| 15 | MOM | Momentum | 原始动量基础 |
| 16 | DEMA | Trend | 平滑替代指标 |
| 17 | TEMA | Trend | 高频平滑常用 |
| 18 | KAMA | Trend | 自适应均线 |
| 19 | NATR | Volatility | ATR 归一化 |
| 20 | SAR | Trend | 止损跟踪常见 |

## 实施批次

- 批次 A：`ADX/CCI/STOCH/WILLR/ROC`（已完成）
- 批次 B：`MFI/OBV/TRIX/MOM/DEMA`（已完成）
- 批次 C：`TEMA/KAMA/NATR/SAR` + 参数兼容收敛（已完成）
- 批次 D：`WMA/ADXR/CMO/TRANGE/BOP`（已完成）
- 批次 E：`PPO/APO/ULTOSC/PLUS_DI/MINUS_DI`（已完成）
- 批次 F：`DX/AD/ADOSC/AROON/AROONOSC`（已完成）
- 批次 G：`TRIMA/STDDEV/VAR/LINEARREG/LINEARREG_SLOPE`（已完成）
- 批次 H：`LINEARREG_INTERCEPT/LINEARREG_ANGLE/TSF/CORREL/BETA`（已完成）
- 批次 I：`LINEARREG_R2/T3/MEDPRICE/TYPPRICE/WCLPRICE`（已完成）
- 批次 J：`AVGPRICE/MIDPOINT/MIDPRICE/HT_TRENDLINE/MAMA`（已完成）
- 批次 K：`MAX/MIN/MAXINDEX/MININDEX/MINMAX`（已完成）
- 批次 L：`SUM/AVGDEV/RANGE/STDDEV扩展/VAR扩展`（已完成）
- 批次 M：`MINMAXINDEX/ROCP/ROCR/ROCR100/COVAR`（已完成）
- 批次 N：`LN/LOG10/SQRT/CEIL/FLOOR`（已完成）
- 批次 O：`SIN/COS/TAN/ASIN/ACOS`（已完成）
- 批次 P：`ATAN/SINH/COSH/TANH/EXP`（已完成）
- 批次 Q：`ABS/SIGN/ADD/SUB/MULT`（已完成）
- 批次 R：`DIV/MAX2/MIN2/CLIP/ROUND`（已完成）
- 批次 S：`POW/MOD/CLAMP01/SQ/CUBE`（已完成）

## Top20 外扩展矩阵（批次 D）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| WMA | ✅ | ✅ | 单序列 |
| ADXR | ✅ | ✅ | 单序列 |
| CMO | ✅ | ✅ | 单序列 |
| TRANGE | ✅ | ✅ | 单序列 |
| BOP | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 E）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| PPO | ✅ | ✅ | 单序列 |
| APO | ✅ | ✅ | 单序列 |
| ULTOSC | ✅ | ✅ | 单序列 |
| PLUS_DI | ✅ | ✅ | 单序列 |
| MINUS_DI | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 F）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| DX | ✅ | ✅ | 单序列 |
| AD | ✅ | ✅ | 单序列 |
| ADOSC | ✅ | ✅ | 单序列 |
| AROON | ✅ | ✅ | 双序列 `(aroondown, aroonup)` |
| AROONOSC | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 G）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| TRIMA | ✅ | ✅ | 单序列 |
| STDDEV | ✅ | ✅ | 单序列 |
| VAR | ✅ | ✅ | 单序列 |
| LINEARREG | ✅ | ✅ | 单序列 |
| LINEARREG_SLOPE | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 H）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| LINEARREG_INTERCEPT | ✅ | ✅ | 单序列 |
| LINEARREG_ANGLE | ✅ | ✅ | 单序列 |
| TSF | ✅ | ✅ | 单序列 |
| CORREL | ✅ | ✅ | 单序列 |
| BETA | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 I）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| LINEARREG_R2 | ✅ | ✅ | 单序列 |
| T3 | ✅ | ✅ | 单序列 |
| MEDPRICE | ✅ | ✅ | 单序列 |
| TYPPRICE | ✅ | ✅ | 单序列 |
| WCLPRICE | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 J）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| AVGPRICE | ✅ | ✅ | 单序列 |
| MIDPOINT | ✅ | ✅ | 单序列 |
| MIDPRICE | ✅ | ✅ | 单序列 |
| HT_TRENDLINE | ✅ | ✅ | 单序列 |
| MAMA | ✅ | ✅ | 双序列 `(mama, fama)` |

## Top20 外扩展矩阵（批次 K）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| MAX | ✅ | ✅ | 单序列 |
| MIN | ✅ | ✅ | 单序列 |
| MAXINDEX | ✅ | ✅ | 单序列 |
| MININDEX | ✅ | ✅ | 单序列 |
| MINMAX | ✅ | ✅ | 双序列 `(min, max)` |

## Top20 外扩展矩阵（批次 L）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| SUM | ✅ | ✅ | 单序列 |
| AVGDEV | ✅ | ✅ | 单序列 |
| RANGE | ✅ | ✅ | 单序列 |
| STDDEV（参数扩展） | ✅ | ✅ | 单序列 |
| VAR（参数扩展） | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 M）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| MINMAXINDEX | ✅ | ✅ | 双序列 `(minindex, maxindex)` |
| ROCP | ✅ | ✅ | 单序列 |
| ROCR | ✅ | ✅ | 单序列 |
| ROCR100 | ✅ | ✅ | 单序列 |
| COVAR | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 N）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| LN | ✅ | ✅ | 单序列 |
| LOG10 | ✅ | ✅ | 单序列 |
| SQRT | ✅ | ✅ | 单序列 |
| CEIL | ✅ | ✅ | 单序列 |
| FLOOR | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 O）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| SIN | ✅ | ✅ | 单序列 |
| COS | ✅ | ✅ | 单序列 |
| TAN | ✅ | ✅ | 单序列 |
| ASIN | ✅ | ✅ | 单序列 |
| ACOS | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 P）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| ATAN | ✅ | ✅ | 单序列 |
| SINH | ✅ | ✅ | 单序列 |
| COSH | ✅ | ✅ | 单序列 |
| TANH | ✅ | ✅ | 单序列 |
| EXP | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 Q）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| ABS | ✅ | ✅ | 单序列 |
| SIGN | ✅ | ✅ | 单序列 |
| ADD | ✅ | ✅ | 单序列 |
| SUB | ✅ | ✅ | 单序列 |
| MULT | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 R）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| DIV | ✅ | ✅ | 单序列 |
| MAX2 | ✅ | ✅ | 单序列 |
| MIN2 | ✅ | ✅ | 单序列 |
| CLIP | ✅ | ✅ | 单序列 |
| ROUND | ✅ | ✅ | 单序列 |

## Top20 外扩展矩阵（批次 S）

| 指标 | Python backend | Rust backend | 输出形态 |
| :--- | :--- | :--- | :--- |
| POW | ✅ | ✅ | 单序列 |
| MOD | ✅ | ✅ | 单序列 |
| CLAMP01 | ✅ | ✅ | 单序列 |
| SQ | ✅ | ✅ | 单序列 |
| CUBE | ✅ | ✅ | 单序列 |

## 兼容层策略

- 提供 `akquant.talib` 命名空间。
- 参数命名与 TA-Lib 对齐。
- 输出结构保持可预测（单值/多值 tuple）。

## 指标说明与 warmup 速查

| 指标 | 常用参数 | 建议 warmup 长度 | 典型用途 |
| :--- | :--- | :--- | :--- |
| SMA | `timeperiod` | `timeperiod` | 趋势平滑基线 |
| EMA | `timeperiod` | `timeperiod` | 更快响应的趋势线 |
| MACD | `fastperiod/slowperiod/signalperiod` | `slowperiod + signalperiod - 2` | 趋势拐点与动量切换 |
| RSI | `timeperiod` | `timeperiod` | 超买超卖判断 |
| BBANDS | `timeperiod/nbdevup/nbdevdn` | `timeperiod` | 波动区间与均值回归 |
| ATR | `timeperiod` | `timeperiod` | 波动率风控与止损宽度 |
| ROC | `timeperiod` (`period` 别名) | `timeperiod` | 相对动量 |
| MOM | `timeperiod` (`period` 别名) | `timeperiod` | 绝对动量 |
| WILLR | `timeperiod` (`period` 别名) | `timeperiod` | 快速超买超卖 |
| CCI | `timeperiod/c` | `timeperiod` | 趋势偏离度 |
| ADX | `timeperiod` | `2 * timeperiod`（保守） | 趋势强度过滤 |
| STOCH | `fastk_period/slowk_period/slowd_period` | `fastk_period + slowk_period + slowd_period - 3` | KDJ 相关迁移 |
| MFI | `timeperiod` (`period` 别名) | `timeperiod + 1` | 量价动量 |
| OBV | 无强制参数 | `1` | 量能趋势确认 |
| TRIX | `timeperiod` (`period` 别名) | `3 * timeperiod - 2` | 去噪动量 |
| DEMA | `timeperiod` (`period` 别名) | `2 * timeperiod - 2` | 双指数平滑趋势 |
| TEMA | `timeperiod` (`period` 别名) | `3 * timeperiod - 2` | 三指数平滑趋势 |
| KAMA | `timeperiod` (`period` 别名) | `timeperiod` | 自适应趋势 |
| NATR | `timeperiod` (`period` 别名) | `timeperiod` | 标准化波动率 |
| SAR | `acceleration/maximum` | `2` | 跟踪止损与反转点 |

## TA-Lib -> AKQuant 映射与示例

```python
from akquant import talib as ta

close = df["close"].to_numpy()
high = df["high"].to_numpy()
low = df["low"].to_numpy()
volume = df["volume"].to_numpy()

# 批次 B
mfi = ta.MFI(high, low, close, volume, timeperiod=14, backend="rust")
obv = ta.OBV(close, volume, backend="rust")
trix = ta.TRIX(close, timeperiod=15, backend="rust")
mom = ta.MOM(close, period=10, backend="rust")
dema = ta.DEMA(close, timeperiod=20, backend="rust")

# 批次 C
tema = ta.TEMA(close, timeperiod=20, backend="rust")
kama = ta.KAMA(close, period=10, backend="rust")
natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")
sar = ta.SAR(high, low, acceleration=0.02, maximum=0.2, backend="rust")

# 多输出指标保持 tuple 结构
macd, signal, hist = ta.MACD(close, backend="rust")
upper, middle, lower = ta.BBANDS(close, timeperiod=20, backend="rust")
slowk, slowd = ta.STOCH(high, low, close, backend="rust")
```

迁移建议：
- 先固定 `backend="python"` 对齐原策略结果，再切换 `backend="rust"`。
- 迁移时优先校验 warmup 区段（前置 `NaN`）与输出结构（单序列或 tuple）。
- 使用 `period` 别名可减少旧脚本改造成本（如 `ROC/MOM/KAMA/NATR`）。
- 需要按场景做指标组合时，可直接参考 [指标组合实战手册](../guide/talib_indicator_playbook.md)。

## 使用示例（按策略场景）

### 趋势过滤 + 波动率控制

```python
ema_fast = ta.EMA(close, timeperiod=20, backend="rust")
ema_slow = ta.EMA(close, timeperiod=60, backend="rust")
adx = ta.ADX(high, low, close, timeperiod=14, backend="rust")
natr = ta.NATR(high, low, close, timeperiod=14, backend="rust")

trend_up = ema_fast[-1] > ema_slow[-1]
trend_strong = adx[-1] > 20
volatility_ok = natr[-1] < 4.0
```

### 均值回归 + 动量确认

```python
upper, middle, lower = ta.BBANDS(close, timeperiod=20, backend="rust")
rsi = ta.RSI(close, timeperiod=14, backend="rust")
mom = ta.MOM(close, period=10, backend="rust")

long_signal = close[-1] < lower[-1] and rsi[-1] < 30 and mom[-1] > 0
exit_signal = close[-1] > middle[-1]
```

### 趋势持有 + 跟踪止损

```python
sar = ta.SAR(high, low, acceleration=0.02, maximum=0.2, backend="rust")
atr = ta.ATR(high, low, close, timeperiod=14, backend="rust")

trailing_stop = sar[-1]
risk_width = 2.0 * atr[-1]
```

## 验收

- 指标输出与 TA-Lib 基线误差可控。
- 每个指标提供 warmup 说明与最小示例。
- 迁移文档提供“TA-Lib -> AKQuant”映射表。
