# AKQuant 能力补强计划（用户视角）

本文档不是内部开发草案，而是面向用户的“能力现状 + 近期补强方向”看板。

## 更新信息

- 更新时间（UTC+8）：2026-03-13 00:00
- 口径版本号：plan-baseline-v1
- 数据来源口径：基于当前仓库已落地能力与回归测试，重点参考 `src/`、`python/akquant/`、`tests/` 以及本目录专题文档。

## 更新原则

- 先解决用户成功率最高频问题，再扩展生态范围。
- 保持主接口兼容，不做破坏性迁移。
- 每一项都给“现状、证据、下一步”。

## 能力看板（基于本仓库当前状态）

| 方向 | 当前状态 | 证据入口 | 下一步 |
| :--- | :--- | :--- | :--- |
| 指标兼容与迁移 | 已形成完整体系：Top20 完成，扩展到批次 T，总计 103 指标 | [indicators.rs](https://github.com/akfamily/akquant/blob/main/src/indicators.rs), [talib_top20_plan.md](./talib_top20_plan.md), [rust_indicator_reference.md](../guide/rust_indicator_reference.md) | 持续补充场景模板与教学材料 |
| 复杂订单语义 | 策略层助手可用（`OCO/Bracket/Trailing`），类型已覆盖 `StopTrail/StopTrailLimit` | [strategy.py](https://github.com/akfamily/akquant/blob/main/python/akquant/strategy.py), [types.rs](https://github.com/akfamily/akquant/blob/main/src/model/types.rs) | 继续下沉到订单管理层图模型 |
| 数据适配与多时框 | `DataFeedAdapter`、`CSV/Parquet`、`resample/replay/align` 已可用 | [feed_adapter.py](https://github.com/akfamily/akquant/blob/main/python/akquant/feed_adapter.py), [multi_timeframe_feed_api.md](./multi_timeframe_feed_api.md) | 扩展官方适配器与校验工具 |
| Broker 扩展 | `ctp/miniqmt/ptrade` + registry 机制已成型 | [factory.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/factory.py), [registry.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/registry.py) | 推进国际 broker 最小闭环 |
| Analyzer 插件生态 | 插件协议与回测接入已落地 | [analyzer_plugin.py](https://github.com/akfamily/akquant/blob/main/python/akquant/analyzer_plugin.py), [analyzer_plugin_spec.md](./analyzer_plugin_spec.md) | 增加插件分发与版本约束 |
| 流式统一内核 | 已支持保持 `run_backtest` 入口不变并接入 `on_event` | [README.md](https://github.com/akfamily/akquant/blob/main/README.md), [stream_observability.md](./stream_observability.md) | 持续完善可观测性与告警 |

## 对用户最有价值的近期重点

### P0：复杂订单引擎化

- 目标：把复杂订单从“策略手写联动”升级为“引擎原生状态机”。
- 用户收益：回测与实盘行为更一致，减少策略端胶水逻辑。

### P1：数据生态与多时框产品化

- 目标：新增官方适配器 + 数据质量校验入口。
- 用户收益：数据接入更稳、时区/重复索引问题更早发现。
- 相关文档： [data_feed_adapter_spec.md](./data_feed_adapter_spec.md)

### P1：Broker 国际化闭环

- 目标：逐步形成 `IB -> Oanda -> CCXT` 的统一交易语义模板。
- 用户收益：策略可迁移性更强，跨市场成本更低。
- 相关文档： [broker_capability_matrix.md](./broker_capability_matrix.md)

### P2：指标与插件生态增长

- 目标：把“能力可用”升级为“学习与复用成本更低”。
- 用户收益：更快上手、更容易复现、更容易二次扩展。
- 相关文档： [rust_indicator_reference.md](../guide/rust_indicator_reference.md), [indicator_scenario_quickref.md](../guide/indicator_scenario_quickref.md)

## 版本节奏建议

- `v0.A`：复杂订单图模型最小可用。
- `v0.B`：数据适配扩展与校验入口。
- `v0.C`：国际 broker 首批最小闭环。
- `v0.D`：插件分发与指标教学资料完善。

## 你现在可以怎么用

1. 先用当前稳定能力跑通策略闭环（数据 -> 回测 -> 分析）。
2. 再按四象限速查表补强信号结构（主信号/过滤器/风控）。
3. 最后根据路线图挑选“与你业务最相关”的下一阶段能力。

推荐入口：

- [AKQuant 指标全量说明（103 个）](../guide/rust_indicator_reference.md)
- [按策略场景选指标速查表（四象限）](../guide/indicator_scenario_quickref.md)
- [指标组合实战手册](../guide/talib_indicator_playbook.md)
