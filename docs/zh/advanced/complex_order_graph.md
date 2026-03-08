# ComplexOrderGraph 设计草案

## 设计目标

- 在引擎层表达复杂订单之间的联动关系，而非依赖策略层手写回调。
- 统一支持 `OCO / Bracket / StopTrail / StopTrailLimit`。
- 让回测与实盘共享同一状态转移语义。

## 核心模型

### 节点（Order Node）

- `node_id`: 订单节点 ID
- `order_id`: 底层订单 ID
- `role`: `Entry | StopLoss | TakeProfit | TrailStop | TrailStopLimit`
- `state`: `Pending | Active | Filled | Cancelled | Rejected | Expired`

### 边（Order Edge）

- `from_node_id`
- `to_node_id`
- `relation`: `Cancels | Activates | UpdatesTrigger`
- `condition`: 触发条件表达式（如 `Filled`、`PartiallyFilled>=x`）

### 图（ComplexOrderGraph）

- `graph_id`
- `graph_type`: `OCO | Bracket | Trail`
- `nodes`
- `edges`
- `status`: `Open | Completed | Failed | Cancelled`

## 事件与驱动

- 输入事件：`OrderAccepted / OrderPartiallyFilled / OrderFilled / OrderCancelled / OrderRejected / MarketTick`
- 处理流程：
  - 定位 `order_id -> node`
  - 更新节点状态
  - 执行图规则（取消同组、激活子单、更新 trailing trigger）
  - 写回订单管理器与事件总线

## 状态转移表

| 当前状态 | 事件 | 下一个状态 | 图动作 |
| :--- | :--- | :--- | :--- |
| Pending | OrderAccepted | Active | 无 |
| Pending | OrderRejected | Rejected | 若为 Entry，整图 Failed |
| Active | OrderPartiallyFilled | Active | 可选：按比例激活子单 |
| Active | OrderFilled | Filled | 执行关联边 |
| Active | OrderCancelled | Cancelled | 执行关联边 |
| Active | OrderRejected | Rejected | 执行关联边 |
| Active | MarketTick (Trail) | Active | 更新 trigger/limit |
| Filled | 任意 | Filled | 无 |
| Cancelled | 任意 | Cancelled | 无 |
| Rejected | 任意 | Rejected | 无 |

## 规则模板

### OCO

- 两个节点均 `Active`。
- 任一节点 `Filled` 后，对方节点执行 `Cancels`。

### Bracket

- `Entry` 初始 `Active`，`StopLoss/TakeProfit` 初始 `Pending`。
- `Entry Filled` 后，`Activates` 两个退出节点。
- `StopLoss` 与 `TakeProfit` 之间自动建立 `OCO`。

### StopTrail / StopTrailLimit

- 节点维持动态 `trigger_price`。
- `MarketTick` 驱动 `UpdatesTrigger`。
- 触发后转入 `Market` 或 `Limit` 执行路径。

## 与现有结构对接

- 类型层：扩展 `src/model/types.rs` 的 `OrderType` 与关系模型。
- 订单层：在 `src/model/order.rs` 增加 `graph_id / parent_order_id / role`。
- 管理层：在 `src/order_manager.rs` 增加 `ComplexOrderGraphManager`。
- 执行层：在 `src/execution/common.rs` 触发图规则求值。

## 验收测试清单

- OCO 任一成交后另一单必须撤销。
- Bracket 进场成交后自动激活退出单。
- Trail 在连续上涨/下跌时 trigger 方向更新正确。
- 回测路径与实盘模拟路径输出一致的状态序列。
