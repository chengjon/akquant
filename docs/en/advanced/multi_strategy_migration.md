# Multi-Strategy Migration Guide

This guide helps you migrate from single-strategy scripts to multi-slot execution with a practical checklist, parameter mapping, acceptance criteria, and troubleshooting order.

## 1. When to Use This Guide

- You currently run `run_backtest(strategy=...)` in single-strategy mode.
- You want strategy ownership analytics in a shared account.
- You need post-risk actions (`reduce_only`, cooldown) per strategy.
- You use warm-start and need state continuity across snapshots.

## 2. Pre-Migration Checklist

Before migration, confirm:

- account model: shared account is acceptable
- ownership granularity: strategy-level split is required
- risk actions: reduce-only and cooldown requirements are clear
- runtime mode: warm-start continuity is required or not

## 3. Parameter Mapping

Key parameters for migration:

- `strategy_id`
- `strategies_by_slot`
- `strategy_max_order_value` / `strategy_max_order_size` / `strategy_max_position_size`
- `strategy_max_daily_loss` / `strategy_max_drawdown`
- `strategy_reduce_only_after_risk`
- `strategy_risk_cooldown_bars`

Rules:

- all strategy-level maps must use configured strategy ids as keys
- empty keys, unknown keys, or negative thresholds fail fast

## 4. Recommended Migration Steps

## 4.1 Step 1: Single Strategy Ownership

Keep one strategy and add `strategy_id` first:

```python
result = run_backtest(
    data=data,
    strategy=MyStrategy,
    symbol="TEST",
    strategy_id="alpha",
    show_progress=False,
)
```

Checks:

- ownership columns appear in `orders_df` / `trades_df`
- report output remains stable

## 4.2 Step 2: Add Slots

Introduce `strategies_by_slot`:

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

Checks:

- multiple `owner_strategy_id` values appear
- per-strategy order counts are expected

## 4.3 Step 3: Add Strategy-Level Risk Actions

Configure per-strategy limits and actions:

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

Checks:

- reject reasons are interpretable
- reduce-only and cooldown reasons are visible in `orders_df.reject_reason`

## 4.4 Step 4: Validate Warm-Start Continuity

- save snapshot and resume via `run_warm_start`
- verify default strategy id, slot topology, and risk runtime states are preserved

## 5. Minimum Acceptance Matrix

- single strategy without `strategy_id` stays backward-compatible
- single strategy with `strategy_id` has correct ownership data
- multi-slot ownership and reject stats are correct
- reduce-only and cooldown behavior works after risk triggers
- warm-start continuity remains intact

## 6. Common Issues

## 6.1 “unknown strategy id” validation errors

Cause:

- strategy-level risk map keys are not in configured strategy ids.

Fix:

- align all map keys with `strategy_id + strategies_by_slot`.

## 6.2 Ownership mismatch after warm-start

Cause:

- old snapshot or inconsistent restored default strategy ownership.

Fix:

- use snapshots from current version
- verify restored slot topology and ownership fields

## 6.3 Report vs DataFrame mismatch

Troubleshooting order:

1. inspect `orders_df.reject_reason`
2. inspect strategy-level analysis outputs
3. inspect report fallback/data-present branch behavior

## 7. Further Reading

- `docs/en/advanced/warm_start.md`
