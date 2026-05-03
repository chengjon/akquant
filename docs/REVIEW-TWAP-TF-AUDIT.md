# REVIEW-TWAP-TF 审计意见

审计日期：2026-05-03

说明：
- 仓库中未找到 `REVIEW-TWAP-TWAP.md`
- 本次实际审阅对象为 [REVIEW-TWAP-TF.md](/opt/claude/akquant/REVIEW-TWAP-TF.md)

## 结论

`TensorFlowAdapter` 和 `TWAP` 的配置/接口层大体已经落地，但 `TWAP Fill Strategy` 还不能认定为“已经实现”。

更准确地说：
- `TensorFlowAdapter`：基本已实现
- `TWAP` 类型扩展、Python 绑定、参数校验：大部分已实现
- `TWAP` 核心成交行为：存在实质性缺陷，当前不能证明按文档描述工作

## 主要问题

### 1. TWAP 截断时机错误，可能直接把首笔成交截成 0

关键代码：
- [src/execution/common.rs](/opt/claude/akquant/src/execution/common.rs:317)
- [src/execution/simulated.rs](/opt/claude/akquant/src/execution/simulated.rs:236)
- [src/execution/simulated.rs](/opt/claude/akquant/src/execution/simulated.rs:260)

现状是：
- matcher 先按整笔可成交量计算 `trade_qty`
- matcher 先更新 `order.filled_quantity`
- 之后 `simulated.rs` 才做 TWAP `slice_quantity()` 截断
- 截断时使用的是 `twap_order.quantity - twap_order.filled_quantity`

这意味着 `remaining` 取到的很可能已经是“本次候选成交之后的剩余量”，首笔成交时甚至可能直接变成 `0`，从而把 `trade.quantity` 截成 `0`。

这不是边界问题，是核心逻辑错误。文档中关于“每个 bar 限制成交量并跨 bar 部分成交”的实现描述，目前不能成立。

### 2. TWAP bar 计数存在 off-by-one

关键代码：
- [src/execution/simulated.rs](/opt/claude/akquant/src/execution/simulated.rs:186)
- [src/execution/twap.rs](/opt/claude/akquant/src/execution/twap.rs:31)
- [src/execution/twap.rs](/opt/claude/akquant/src/execution/twap.rs:86)

现状是：
- 每个 `Bar` 事件进入撮合前，先执行 `self.twap_scheduler.on_bar()`
- TWAP 订单不是下单时注册，而是首次命中候选成交后才注册
- 注册时 `bars_elapsed = 0`
- 切片公式使用 `num_bars - bars_elapsed + 1`

结果是：
- `twap_bars = 5` 的首个可成交 bar，会按 6 份来切，而不是文档写的 5 份

即使修掉第 1 个问题，这里也仍然会导致分配周期比预期多一根 bar。

### 3. Python 侧对 TWAP 的支持并未完全打通

关键代码：
- [python/akquant/backtest/_execution.py](/opt/claude/akquant/python/akquant/backtest/_execution.py:78)
- [python/akquant/backtest/_types.py](/opt/claude/akquant/python/akquant/backtest/_types.py:52)
- [python/akquant/backtest/_validation.py](/opt/claude/akquant/python/akquant/backtest/_validation.py:437)
- [python/akquant/strategy_trading_api.py](/opt/claude/akquant/python/akquant/strategy_trading_api.py:520)
- [python/akquant/backtest/__init__.pyi](/opt/claude/akquant/python/akquant/backtest/__init__.pyi:51)

具体问题：
- `_execution.py` 已接受 `twap_window` 和 `twap_bars`
- 但 `_types.py` 里的 `FillPolicy` 没有 `twap_bars`
- `backtest/__init__.pyi` 仍把 `twap_window` 放在 `ExperimentalPriceBasis`
- `_normalize_strategy_fill_policy_map()` 归一化后会丢掉 `twap_bars`
- 订单级 `fill_policy` 归一化仍只允许 `open/close/ohlc4/hl2`，不接受 `twap_window`

所以文档中“Python 层修改”只能算部分完成，不能算完整打通。

## 已实现部分

### TensorFlowAdapter 已基本落地

关键代码：
- [python/akquant/ml/model.py](/opt/claude/akquant/python/akquant/ml/model.py:308)
- [python/akquant/ml/__init__.py](/opt/claude/akquant/python/akquant/ml/__init__.py:1)

已确认：
- `TensorFlowAdapter` 类存在
- `fit/predict/save/load` 已实现
- `tensorflow` 采用方法内导入
- 保存了 `initial_weights`，支持非增量训练前重置
- 处理了 `list/tuple` 输出
- 模块导出已加上

### 引擎绑定和参数校验已大体落地

关键代码：
- [src/model/types.rs](/opt/claude/akquant/src/model/types.rs:235)
- [src/engine/python.rs](/opt/claude/akquant/src/engine/python.rs:689)
- [tests/test_fill_policy.py](/opt/claude/akquant/tests/test_fill_policy.py:71)

已确认：
- `PriceBasis::TwapWindow` 已添加
- `ExecutionPolicyCore.twap_bars` 已添加
- `set_fill_policy(..., twap_bars=0)` 已暴露到 Python
- `get_fill_policy()` 已返回 4 元组
- `twap_window` 的基础参数校验测试已存在

## 测试情况

本次核对时确认到的事实：
- `tests/test_fill_policy.py` 共 10 个测试，实跑通过
- `tests/test_engine.py` 当前收集到 161 个测试，数量与原文一致

但需要强调：
- 现有测试主要覆盖 `set_fill_policy/get_fill_policy`、参数校验、roundtrip
- 没有看到覆盖 “TWAP 订单在多个 bar 中逐步成交直到完成” 的行为测试

因此文档中“TWAP 已实现且测试覆盖完成”的表述偏乐观。

## 审计结论建议

建议把原文结论从“已实现”调整为：

> `TensorFlowAdapter` 已基本实现。`TWAP` 的类型、绑定和参数校验已完成，但核心撮合切片逻辑仍存在缺陷，暂不能认定功能已按设计完成。

## 本次核对时使用的验证

- 代码静态核对：Rust / Python / stub / tests
- 运行验证：
  - `pytest -q tests/test_fill_policy.py`，结果 `10 passed`
  - `pytest -q tests/test_engine.py -q --collect-only`，结果 `161`
  - 最小回测探针验证 `twap_window + twap_bars=5`，观察到订单未按预期发生分 bar 成交
