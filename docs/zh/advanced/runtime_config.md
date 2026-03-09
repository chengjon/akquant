# Runtime Config 指南

本文介绍如何在回测入口侧控制策略运行时行为，而无需修改策略类代码。

## 1. 解决什么问题

通过 `strategy_runtime_config`，可以在调用处注入运行时开关：

- 错误处理模式（`error_mode`）
- 账户更新阈值（`portfolio_update_eps`）
- 精确交易日边界钩子（`enable_precise_day_boundary_hooks`）
- 兼容模式开关（`re_raise_on_error`）

该能力同时支持：

- `run_backtest(...)`
- `run_warm_start(...)`

## 2. 基础用法

```python
from akquant import StrategyRuntimeConfig, run_backtest

result = run_backtest(
    data=data,
    strategy=MyStrategy,
    strategy_runtime_config=StrategyRuntimeConfig(
        error_mode="continue",
        portfolio_update_eps=1.0,
    ),
)
```

也可以直接传 `dict`：

```python
result = run_backtest(
    data=data,
    strategy=MyStrategy,
    strategy_runtime_config={"error_mode": "continue"},
)
```

## 3. 参数行为对照表

| 字段 | 类型 | 默认值 | 常见用途 | 非法输入行为 |
|---|---|---|---|---|
| `error_mode` | `"raise" \| "continue" \| "legacy"` | `"raise"` | 控制用户回调异常处理策略 | 抛出 `ValueError` |
| `portfolio_update_eps` | `float`（`>= 0`） | `0.0` | 过滤微小资产波动噪声 | 抛出 `ValueError` |
| `enable_precise_day_boundary_hooks` | `bool` | `False` | 启用基于边界定时器的精确日内钩子 | 按 `bool` 规则转换 |
| `re_raise_on_error` | `bool` | `True` | 在 `error_mode="legacy"` 下作为兼容兜底 | 按 `bool` 规则转换 |

## 4. 冲突优先级

当策略侧配置与外部配置冲突时，由 `runtime_config_override` 决定：

- `runtime_config_override=True`（默认）：应用外部配置
- `runtime_config_override=False`：保留策略侧配置

同一策略实例、同一冲突内容的告警会自动去重。

## 5. 常见误用与排障

- `strategy_runtime_config` 传入未知字段会快速失败，并给出字段级错误。
- `portfolio_update_eps` 传负值会触发校验错误。
- 同一策略实例重复运行时，相同冲突告警可能只出现一次，这是去重行为。
- 当 `runtime_config_override=False` 时，即使传入外部配置也不会覆盖策略侧配置。

## 6. 热启动注入

从快照恢复时也可以覆盖运行时行为：

```python
result = run_warm_start(
    checkpoint_path="snapshot.pkl",
    data=new_data,
    symbol="TEST",
    strategy_runtime_config={"error_mode": "continue"},
)
```

冲突处理规则与 `run_backtest` 完全一致。

## 7. 端到端示例

可直接运行：

- [22_strategy_runtime_config_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/22_strategy_runtime_config_demo.py)

另见：[热启动指南](warm_start.md)。

预期输出标记：

- `scenario1_done`
- `scenario2_exception=...`
- `scenario3_done`

## 8. 故障速查清单

| 现象 / 错误信息 | 常见原因 | 快速修复 |
|---|---|---|
| `strategy_runtime_config contains unknown fields: ...` | 注入字典包含未知字段 | 删除未支持字段，仅保留文档中的字段名 |
| `invalid strategy_runtime_config: portfolio_update_eps must be >= 0` | `portfolio_update_eps` 传了负值 | 将 `portfolio_update_eps` 设置为 `0` 或正数 |
| 传了 runtime 配置但策略行为没变化 | 启用了 `runtime_config_override=False` | 改为 `runtime_config_override=True` 或移除该参数 |
| 冲突告警只出现一次 | 告警按“同一策略实例 + 同一冲突内容”去重 | 这是预期行为；如需重复观察可新建策略实例 |
| 热启动后仍抛出回调异常 | 恢复后的策略配置生效，外部覆盖未应用 | 传入 `strategy_runtime_config={"error_mode": "continue"}` 且确保 `runtime_config_override=True` |
