# 多策略迁移指南

本指南面向“从单策略脚本平滑升级到多策略 slot 执行”的用户，提供阶段化迁移清单、参数对照、验收标准与常见排障路径。

## 1. 适用范围

- 当前使用 `run_backtest(strategy=...)` 的单策略用户。
- 需要在同一账户下运行多个策略并做归属分析的用户。
- 需要在热启动场景下保持多策略风控状态连续的用户。

## 2. 迁移前确认

在开始改造前，建议先确认：

- 账户模型：你接受“共享账户模型”（非独立子账户）。
- 归属粒度：你希望按策略查看订单/成交/拒单统计。
- 风控动作：是否需要启用仅平仓和冷却 bars。
- 运行方式：是否会使用快照恢复（`run_warm_start`）。

## 3. 参数迁移清单

从单策略迁移到多策略时，核心参数如下：

- `strategy_id`：主策略归属 ID。
- `strategies_by_slot`：额外 slot -> 策略映射。
- `strategy_max_order_value` / `strategy_max_order_size` / `strategy_max_position_size`。
- `strategy_max_daily_loss` / `strategy_max_drawdown`。
- `strategy_reduce_only_after_risk`。
- `strategy_risk_cooldown_bars`。

规则：

- 所有策略级映射参数都必须以已配置的 strategy_id 为键。
- 键为空、未知策略键、负值阈值会触发参数校验失败。

## 4. 推荐迁移步骤

## 4.1 第一步：先做“单策略归属化”

先保持只有一个策略，仅补 `strategy_id`，验证归属字段和报告输出：

```python
result = run_backtest(
    data=data,
    strategy=MyStrategy,
    symbol="TEST",
    strategy_id="alpha",
    show_progress=False,
)
```

验收点：

- `orders_df` / `trades_df` 有归属列。
- 报告可正常渲染，策略级统计可读。

## 4.2 第二步：引入 slot

在主策略外增加 `strategies_by_slot`：

```python
result = run_backtest(
    data=data,
    strategy=AlphaStrategy,
    symbol="TEST",
    strategy_id="alpha",
    strategies_by_slot={"beta": BetaStrategy},
    show_progress=False,
)
```

验收点：

- `owner_strategy_id` 出现多个策略值。
- 各策略订单数量与预期一致。

## 4.3 第三步：配置策略级风控动作

按策略键配置限额与动作：

```python
result = run_backtest(
    data=data,
    strategy=AlphaStrategy,
    symbol="TEST",
    strategy_id="alpha",
    strategies_by_slot={"beta": BetaStrategy},
    strategy_max_order_size={"alpha": 10, "beta": 20},
    strategy_reduce_only_after_risk={"alpha": True, "beta": False},
    strategy_risk_cooldown_bars={"alpha": 2, "beta": 0},
    show_progress=False,
)
```

验收点：

- 风控触发后拒单原因可解释。
- `reduce_only` / `cooldown` 拒单文案在 `orders_df.reject_reason` 可见。

## 4.4 第四步：验证热启动连续性

- 保存快照后使用 `run_warm_start` 恢复。
- 检查恢复后的默认策略 ID、slot 集合、风控动作状态是否连续。

## 5. 最小验收矩阵

- 单策略（无 `strategy_id`）回测结果与旧版一致。
- 单策略（有 `strategy_id`）归属字段正确。
- 多 slot 下各策略归属与拒单统计正确。
- 风控触发后仅平仓/冷却动作生效。
- 热启动恢复后行为连续。

## 6. 常见问题

## 6.1 报错“unknown strategy id”

原因：

- 风控映射参数中的键不在 `strategy_id + strategies_by_slot` 集合中。

处理：

- 对齐策略键；保证所有映射键来自已注册 slot。

## 6.2 热启动后归属不一致

原因：

- 使用了旧快照或恢复后未正确复用默认策略归属。

处理：

- 确认使用新版本快照。
- 对照结果中的归属字段与 slot 配置检查恢复链路。

## 6.3 图表与 DataFrame 统计不一致

排查顺序：

1. 先看 `orders_df.reject_reason`。
2. 再看策略级分析函数输出。
3. 最后核对报告图表分支是否进入空数据回退。

## 7. 推荐阅读

- 热启动指南：`docs/zh/advanced/warm_start.md`
