# 执行语义切换（已完成）

本文档作为历史记录，说明 legacy 执行参数向三轴 `fill_policy`
的迁移已完成。

## 当前公开模型

- `price_basis`: `open | close | ohlc4 | hl2`
- `bar_offset`: `0 | 1`
- `temporal`: `same_cycle | next_event`

统一配置写法：

```python
fill_policy={"price_basis":"...", "bar_offset": 0_or_1, "temporal":"..."}
```

## 当前状态

- `run_backtest` / `run_warm_start` 已拒绝 legacy 执行参数。
- `legacy_execution_policy_compat` 已移除。
- `AKQ_LEGACY_EXECUTION_POLICY_COMPAT` 回滚路径已移除。
- 内部兼容映射仅作为实现细节保留（internal，非公开 API）。

## 基线校验命令

```bash
uv run ruff check .
uv run mypy .
uv run pytest -q
```

## 三轴配置参考（公开口径）

| 场景 | 三轴 `fill_policy` |
| :--- | :--- |
| next-open 风格成交 | `{"price_basis":"open","bar_offset":1,"temporal":"same_cycle"}` |
| current-close 风格成交 | `{"price_basis":"close","bar_offset":0,"temporal":"same_cycle"}` |
| 下一根收盘价成交 | `{"price_basis":"close","bar_offset":1,"temporal":"same_cycle"}` |
| 下一根 OHLC 均价成交 | `{"price_basis":"ohlc4","bar_offset":1,"temporal":"same_cycle"}` |
| 下一根 HL2 成交 | `{"price_basis":"hl2","bar_offset":1,"temporal":"same_cycle"}` |

## 收口结论

- 迁移工作已完成。
- 公开执行语义以三轴模型为唯一主路径。
- 本文件不再作为在途发布清单，仅作历史说明。
