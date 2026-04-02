# Execution Policy Cutover (Completed)

This document is retained as a historical record of the migration from legacy
execution parameters to unified three-axis `fill_policy`.

## Final Public Model

- `price_basis`: `open | close | ohlc4 | hl2`
- `bar_offset`: `0 | 1`
- `temporal`: `same_cycle | next_event`

User-facing configuration is unified as:

```python
fill_policy={"price_basis": "...", "bar_offset": 0_or_1, "temporal": "..."}
```

## Current State

- `run_backtest` / `run_warm_start` reject legacy execution parameters.
- `legacy_execution_policy_compat` is removed.
- `AKQ_LEGACY_EXECUTION_POLICY_COMPAT` rollback path is removed.
- Internal compatibility mapping may still exist only as implementation detail (internal, non-public API).

## Validation Baseline

Recommended regression commands:

```bash
uv run ruff check .
uv run mypy .
uv run pytest -q
```

## Three-Axis Reference (Public Naming)

| Scenario | Three-axis `fill_policy` |
| :--- | :--- |
| Next-open style fill | `{"price_basis":"open","bar_offset":1,"temporal":"same_cycle"}` |
| Current-close style fill | `{"price_basis":"close","bar_offset":0,"temporal":"same_cycle"}` |
| Next-bar close fill | `{"price_basis":"close","bar_offset":1,"temporal":"same_cycle"}` |
| Next-bar OHLC average fill | `{"price_basis":"ohlc4","bar_offset":1,"temporal":"same_cycle"}` |
| Next-bar HL2 fill | `{"price_basis":"hl2","bar_offset":1,"temporal":"same_cycle"}` |

## Exit Record

- Migration is completed.
- Public execution semantics are three-axis only.
- This file is informational and no longer an active rollout checklist.
