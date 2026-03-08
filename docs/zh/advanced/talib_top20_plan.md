# TA-Lib 迁移优先指标 Top20

## 目标

- 覆盖高频迁移场景中的常用指标，优先减少策略迁移改造量。
- 建立统一指标注册表元数据：名称、参数、输出、warmup。

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

- 批次 A：`ADX/CCI/STOCH/WILLR/ROC`
- 批次 B：`MFI/OBV/TRIX/MOM/DEMA`
- 批次 C：`TEMA/KAMA/NATR/SAR` + 参数兼容收敛

## 兼容层策略

- 提供 `akquant.talib` 命名空间。
- 参数命名与 TA-Lib 对齐。
- 输出结构保持可预测（单值/多值 tuple）。

## 验收

- 指标输出与 TA-Lib 基线误差可控。
- 每个指标提供 warmup 说明与最小示例。
- 迁移文档提供“TA-Lib -> AKQuant”映射表。
