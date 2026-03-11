# 能力补强路线图（2026-03 本地状态更新）

本文档基于当前仓库代码与测试现状更新，替换早期“草案视角”为“已落地 + 待补强”视角。

## 更新原则

- 保持 `Strategy` API 兼容，不引入破坏性重构。
- 先推进“可直接提升用户成功率”的能力，再推进生态扩张。
- 每个方向均给出状态、证据入口、下一阶段目标。

## 能力状态总览

| 方向 | 当前状态 | 代码/测试证据 | 下一步优先级 |
| :--- | :--- | :--- | :--- |
| 复杂订单语义 | **部分完成**：`OCO/Bracket/Trailing` 在策略层助手可用，`OrderType` 已含 `StopTrail/StopTrailLimit` | [strategy.py](https://github.com/akfamily/akquant/blob/main/python/akquant/strategy.py), [types.rs](https://github.com/akfamily/akquant/blob/main/src/model/types.rs), [test_strategy_extras.py](https://github.com/akfamily/akquant/blob/main/tests/test_strategy_extras.py) | P0 |
| 统一数据适配层 | **已落地 v1**：`DataFeedAdapter` + `CSV/Parquet` + `run_backtest(data=adapter)` | [feed_adapter.py](https://github.com/akfamily/akquant/blob/main/python/akquant/feed_adapter.py), [test_feed_adapter.py](https://github.com/akfamily/akquant/blob/main/tests/test_feed_adapter.py) | P1 |
| 多时间框架重采样/重放 | **已落地 v1**：`resample/replay`、`align/day_mode/session_windows` 可用并有测试 | [feed_adapter.py](https://github.com/akfamily/akquant/blob/main/python/akquant/feed_adapter.py), [test_feed_adapter.py](https://github.com/akfamily/akquant/blob/main/tests/test_feed_adapter.py), [multi_timeframe_feed_api.md](./multi_timeframe_feed_api.md) | P1 |
| Broker 可扩展与本地接入 | **已落地 v1**：内置 `ctp/miniqmt/ptrade` + 注册机制 + 桥接测试 | [factory.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/factory.py), [registry.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/registry.py), [test_gateway_registry.py](https://github.com/akfamily/akquant/blob/main/tests/test_gateway_registry.py), [test_live_runner_broker_bridge.py](https://github.com/akfamily/akquant/blob/main/tests/test_live_runner_broker_bridge.py) | P1 |
| 指标库与 TA-Lib 迁移 | **批次 A/B/C 已完成**：Top20（`ADX/CCI/STOCH/WILLR/ROC/MFI/OBV/TRIX/MOM/DEMA/TEMA/KAMA/NATR/SAR`）已双后端可用 | [indicators.rs](https://github.com/akfamily/akquant/blob/main/src/indicators.rs), [funcs.py](https://github.com/akfamily/akquant/blob/main/python/akquant/talib/funcs.py), [test_talib_backend.py](https://github.com/akfamily/akquant/blob/main/tests/test_talib_backend.py), [talib_top20_plan.md](./talib_top20_plan.md) | P2 |
| Analyzer 插件生态 | **已落地 v1**：插件协议 + `run_backtest(analyzer_plugins=...)` + 输出落地 | [analyzer_plugin.py](https://github.com/akfamily/akquant/blob/main/python/akquant/analyzer_plugin.py), [backtest/engine.py](https://github.com/akfamily/akquant/blob/main/python/akquant/backtest/engine.py), [test_engine.py](https://github.com/akfamily/akquant/blob/main/tests/test_engine.py), [analyzer_plugin_spec.md](./analyzer_plugin_spec.md) | P2 |
| 流式统一内核 | **阶段 5 已完成迁移语义**：保持 `run_backtest` 入口不变，支持 `on_event` | [README.md](https://github.com/akfamily/akquant/blob/main/README.md), [stream_observability.md](./stream_observability.md), [test_engine.py](https://github.com/akfamily/akquant/blob/main/tests/test_engine.py) | 持续观察 |

## 分方向更新

### P0：复杂订单引擎化（从“策略助手”走向“引擎原生图”）

现状：
- 用户侧已可直接使用 OCO、Bracket、Trailing 助手。
- 复杂订单联动仍主要在策略层管理，尚未完全下沉为引擎原生订单图。

本阶段目标：
- 在订单管理层引入可复用的 `ComplexOrderGraph` 状态机。
- 统一回测与实盘桥接中的复杂订单状态迁移语义。

代码入口：
- [strategy.py](https://github.com/akfamily/akquant/blob/main/python/akquant/strategy.py)
- [types.rs](https://github.com/akfamily/akquant/blob/main/src/model/types.rs)
- [order_manager.rs](https://github.com/akfamily/akquant/blob/main/src/order_manager.rs)
- [complex_order_graph.md](./complex_order_graph.md)

验收标准：
- OCO/Bracket/Trail 在“策略助手路径”与“引擎图路径”行为一致。
- 复杂订单联动逻辑不依赖策略端手写回调。

### P1：数据接入与多时框（从“草案”升级为“产品化”）

现状：
- `DataFeedAdapter`、`CSVFeedAdapter`、`ParquetFeedAdapter`、`resample/replay` 已在主干可用并有回归测试。
- 当前短板从“有没有”转为“生态覆盖与校验工具不足”。

本阶段目标：
- 增加官方适配器 `Yahoo`（以及后续 `IB/Oanda/Polygon/ClickHouse` 分批推进）。
- 增加 `feed validate` 等价校验入口（schema、时区、重复索引、缺失值、企业行为字段）。
- 补齐缓存目录规范与重建命令。

代码入口：
- [feed_adapter.py](https://github.com/akfamily/akquant/blob/main/python/akquant/feed_adapter.py)
- [test_feed_adapter.py](https://github.com/akfamily/akquant/blob/main/tests/test_feed_adapter.py)
- [data_feed_adapter_spec.md](./data_feed_adapter_spec.md)

验收标准：
- 官方适配器输出统一 schema，可直接回测。
- 多时框聚合在关键场景与 pandas 基线误差可控。

### P1：Broker 生态国际化（从“可注册”走向“可交易”）

现状：
- 本地生态适配器与 registry 机制已成型。
- 国际 broker 仍处于能力矩阵与方案阶段。

本阶段目标：
- 优先落地 `IB -> Oanda -> CCXT` 的最小交易闭环（行情、下单、回报、撤单、账户）。
- 用契约测试固定 `TIF/订单类型/错误码` 语义。

代码入口：
- [factory.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/factory.py)
- [registry.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/registry.py)
- [broker_capability_matrix.md](./broker_capability_matrix.md)
- [custom_broker_registry.md](./custom_broker_registry.md)

验收标准：
- 每个官方 broker 有最小可运行示例与契约测试。
- 缺失能力可解释失败，不做静默降级。

### P2：指标兼容与插件生态（从“接口可用”走向“生态可增长”）

现状：
- 指标层已完成批次 A/B/C，Top20 指标已全部接入 `akquant.talib` 的 `rust` backend。
- Analyzer 插件生命周期已接入回测主流程并可输出结果。

本阶段目标：
- 将 Top20 指标补齐 warmup 说明、参数别名与迁移映射示例。
- 增加 analyzer 插件分发能力（entry points、版本约束、模板仓）。

代码入口：
- [indicators.rs](https://github.com/akfamily/akquant/blob/main/src/indicators.rs)
- [talib_top20_plan.md](./talib_top20_plan.md)
- [analyzer_plugin.py](https://github.com/akfamily/akquant/blob/main/python/akquant/analyzer_plugin.py)
- [analyzer_plugin_spec.md](./analyzer_plugin_spec.md)

验收标准：
- 指标输出与基线工具（TA-Lib/pandas）偏差可控。
- 第三方 analyzer 能以插件包形式接入并在报告层展示。

## 版本节奏建议（更新）

- `v0.A (4~6 周)`：P0 复杂订单引擎图最小可用 + 回放一致性测试。
- `v0.B (4~6 周)`：P1 数据生态扩展（Yahoo + feed 校验入口 + 缓存规范）。
- `v0.C (4~6 周)`：P1 broker 国际化首批闭环（IB/Oanda 至少其一可用）。
- `v0.D (4~6 周)`：P2 指标兼容层文档收敛（warmup/映射/示例）+ analyzer 插件分发最小闭环。

## 风险与缓解

- 风险：复杂订单状态机边界爆炸。
  - 缓解：状态转移表驱动 + 属性测试 + 回放对齐测试。
- 风险：不同 broker 语义不一致导致“表面统一”。
  - 缓解：能力矩阵显式化 + 契约测试 + 缺失能力强失败。
- 风险：数据适配质量差异导致回测漂移。
  - 缓解：统一校验入口 + 关键场景基线集。

## 立即执行清单（本轮）

- 将复杂订单“图模型”落地到订单管理层最小实现。
- 增加 `YahooFeedAdapter` 与对应单测/示例。
- 新增 `feed validate` 命令或等价 API（先覆盖 schema 与时区校验）。
- 为 IB/Oanda/CCXT 生成统一契约测试模板并优先接入 1 个官方实现。
- 为 Top20 指标补齐 warmup/参数别名迁移示例并建立统一对照测试清单。
- 增加 analyzer 插件 entry points 发现与版本约束原型。
