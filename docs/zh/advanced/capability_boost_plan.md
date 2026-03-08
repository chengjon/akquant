# 能力补强路线图（按收益排序）

本文档将六个补强方向整理为可执行方案，目标是在保持 AKQuant 现有性能优势的同时，快速补齐与 backtrader 在生态和易用性上的差距。

## 目标与原则

- 目标：3 个版本周期内完成 P0/P1 主干能力，P2 形成可扩展插件生态雏形。
- 原则：先补“交易语义完整性”，再补“数据与连接器广度”，最后扩展“指标与分析生态”。
- 约束：不破坏现有 `Strategy` API 兼容；新增能力默认可选开启。
- 验收：每个能力都提供最小可用 API、示例、测试、迁移说明。

## 优先级拆解

## 优先补强（按收益排序）摘要

| 优先级 | 能力项 | 当前差距 | 收益判断 |
| :--- | :--- | :--- | :--- |
| P0 | 原生复杂订单族 | 仅 `Market/Limit/StopMarket/StopLimit`，`OCO/Bracket` 仍偏策略层拼装 | 直接提升交易语义完整性，最影响策略迁移体验 |
| P1 | 统一数据源适配层 | 回测入口虽灵活，但数据接入依赖用户 ETL | 降低接入门槛，扩大可用数据生态 |
| P1 | 多时间框架重采样/重放 | 多频策略仍依赖手工 `pandas.resample` | 明显减少样板代码，统一多时框语义 |
| P1 | Broker 生态国际化 | 官方适配器覆盖偏本地生态 | 提升实盘可达性与国际用户覆盖 |
| P2 | 指标库规模与兼容层 | 内建指标偏核心集合 | 降低 backtrader/TA-Lib 迁移成本 |
| P2 | 分析器插件生态 | 分析能力强但扩展接口不足 | 形成社区插件增长飞轮 |

## 关键代码入口映射

- P0 原生复杂订单族
  - 核心类型定义：[types.rs](file:///Users/albert/Documents/trae_projects/akquant/src/model/types.rs)
  - 复杂订单示例：[06_complex_orders.py](file:///Users/albert/Documents/trae_projects/akquant/examples/06_complex_orders.py)
- P1 统一数据源适配层
  - API 文档入口：[api.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/reference/api.md)
  - 数据入口实现：[data.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/data.py)
- P1 多时间框架重采样/重放
  - 现有多频示例：[14_multi_frequency.py](file:///Users/albert/Documents/trae_projects/akquant/examples/14_multi_frequency.py)
- P1 Broker 生态国际化
  - 工厂入口：[factory.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/gateway/factory.py)
  - 注册入口：[registry.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/gateway/registry.py)
- P2 指标库规模与兼容层
  - 指标实现入口：[indicators.rs](file:///Users/albert/Documents/trae_projects/akquant/src/indicator/indicators.rs)
- P2 分析器插件生态
  - 对外说明入口：[README.md](file:///Users/albert/Documents/trae_projects/akquant/README.md)

### P0：原生复杂订单族

现状：
- 核心订单类型集中在 `Market/Limit/StopMarket/StopLimit`。
- `OCO/Bracket` 目前主要由策略层逻辑拼装。

目标：
- 在引擎层引入统一的订单图（Order Graph）与关联订单状态机。
- 原生支持 `OCO/Bracket/StopTrail/StopTrailLimit`。

工作包：
- `WP0-1` 订单模型扩展：在 Rust 类型层新增复合订单定义与关联关系字段。
- `WP0-2` 撮合联动：任一子单状态变化触发图内规则（取消、激活、跟随更新）。
- `WP0-3` Python API：保留现有 `create_oco_order_group/place_bracket_order`，补齐 `trail` 系列接口。
- `WP0-4` 回放一致性：回测与实盘路径共享同一状态迁移规则。

验收标准：
- 复杂订单全链路单测 + 回测集成测试通过。
- 在相同行情下，策略层手写 OCO 与引擎原生 OCO 行为一致。
- 文档、示例、迁移指南齐全。

---

### P1：统一数据源适配层

现状：
- 回测入口主要消费 `DataFrame/Dict/List[Bar]`。
- 数据准备依赖用户自行 ETL。

目标：
- 建立官方 `Feed Adapter` 层与标准缓存协议，降低数据接入门槛。

工作包：
- `WP1-1` 统一数据契约：定义 `DataFeedAdapter` 抽象（schema、timezone、corporate action）。
- `WP1-2` 官方适配器首批：`CSV/Parquet/Yahoo`。
- `WP1-3` 增量适配器第二批：`IB/Oanda/Polygon/ClickHouse`。
- `WP1-4` 缓存规范：目录布局、版本签名、过期策略、重建命令。

验收标准：
- 同一标的同一区间，从任意官方适配器拉取后可无缝回测。
- 适配器均提供最小示例和错误诊断信息。
- 新增 `feed validate` 或等价校验入口。

---

### P1：多时间框架内建重采样/重放

现状：
- 多频策略常依赖 `pandas.resample` 手工处理后双路喂数。

目标：
- 在 feed 层提供内建 `resample/replay`，减少样板代码并保证一致语义。

工作包：
- `WP1-5` `feed.resample(freq, agg=...)`：统一聚合规则和边界处理。
- `WP1-6` `feed.replay(freq, align=...)`：以低频节奏重放高频流。
- `WP1-7` 多时框事件对齐：统一时区、会话、缺口补齐策略。

验收标准：
- 示例策略无需手写 pandas 重采样即可运行。
- 重采样结果与 pandas 基线在允许误差内一致。
- 支持回测与实时流路径一致调用方式。

---

### P1：Broker 生态国际化

现状：
- 内置 broker 更偏本地生态，注册机制已具备但官方适配器覆盖面不足。

目标：
- 补齐国际常用连接器，先实现“行情 + 下单 + 回报”最小闭环。

工作包：
- `WP1-8` 官方优先顺序：`IB -> Oanda -> CCXT`。
- `WP1-9` 能力矩阵：明确每个 broker 支持的订单类型、TIF、账户字段。
- `WP1-10` 连接器测试桩：离线模拟网关 + 契约测试。

验收标准：
- 每个官方 broker 提供最小实盘/仿真示例。
- 下单、撤单、成交回报在统一 API 下可运行。
- 能力缺失时返回可解释错误而非静默降级。

---

### P2：指标库规模与兼容层

现状：
- 内建指标仍偏核心集合，生态规模与 backtrader 有差距。

目标：
- 扩容内建指标并提供 TA-Lib 兼容层，降低迁移成本。

工作包：
- `WP2-1` 指标注册表：统一命名、参数、元数据、输出维度。
- `WP2-2` TA-Lib 兼容包装：优先覆盖高频使用指标。
- `WP2-3` 指标一致性校验：对比 pandas/TA-Lib 基线输出。

验收标准：
- 核心迁移指标清单覆盖率达标。
- 指标文档自动生成，含参数和 warmup 说明。
- 指标性能基准不回退。

---

### P2：分析器插件生态

现状：
- 分析结果强，但以固定输出为主，可扩展性不足。

目标：
- 提供 Analyzer 插件接口与社区分发机制，形成可持续扩展生态。

工作包：
- `WP2-4` Analyzer 生命周期接口：`on_start/on_bar/on_trade/on_finish`。
- `WP2-5` 插件注册与发现：本地包、entry points、版本约束。
- `WP2-6` 官方首批插件：风险分解、容量评估、归因扩展。

验收标准：
- 第三方 analyzer 可在不改内核代码情况下接入。
- 报告层支持挂载插件输出。
- 插件示例仓与模板可用。

## 版本节奏建议

- `v0.A (4~6 周)`：完成 P0（复杂订单引擎化）+ 文档迁移。
- `v0.B (4~6 周)`：完成 P1 的数据适配首批与多时框基础 API。
- `v0.C (4~6 周)`：完成 P1 的 broker 国际化首批闭环。
- `v0.D (4~6 周)`：推进 P2（指标兼容层 + Analyzer 插件接口）。

## 风险与缓解

- 风险：复杂订单状态机引入边界条件爆炸。
  - 缓解：状态转移表驱动实现 + 属性测试（property-based test）。
- 风险：不同 broker 语义不一致导致 API 表面一致但行为分叉。
  - 缓解：能力矩阵显式暴露 + 缺失能力强校验失败。
- 风险：数据适配器质量不均导致回测漂移。
  - 缓解：统一数据契约校验与回放基线测试。

## 立即执行清单（本周）

- 建立 `ComplexOrderGraph` 设计文档与状态转移表。见 [complex_order_graph.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/complex_order_graph.md)
- 定义 `DataFeedAdapter` 抽象接口与最小 CSV/Parquet 适配器草案。见 [data_feed_adapter_spec.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/data_feed_adapter_spec.md) 与 [feed_adapter.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/feed_adapter.py)
- 输出 `feed.resample/feed.replay` API 草案并锁定事件对齐语义。见 [multi_timeframe_feed_api.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/multi_timeframe_feed_api.md)
- 起草 `Broker Capability Matrix` 模板并先覆盖 IB/Oanda/CCXT。见 [broker_capability_matrix.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/broker_capability_matrix.md)
- 盘点 TA-Lib 迁移优先指标 Top20 清单。见 [talib_top20_plan.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/talib_top20_plan.md)
- 定义 Analyzer 插件最小生命周期接口与示例模板。见 [analyzer_plugin_spec.md](file:///Users/albert/Documents/trae_projects/akquant/docs/zh/advanced/analyzer_plugin_spec.md) 与 [analyzer_plugin.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/analyzer_plugin.py)
