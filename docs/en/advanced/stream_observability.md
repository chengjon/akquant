# Unified Stream Core: Phase-4 Observation Checklist

This checklist defines the observation window after unifying `run_backtest` on the stream-first core, so the team can decide whether to proceed to removing legacy blocking code branches.

## 1. Observation Window

- Recommended duration: `2~4` weeks, or at least `2` internal release cycles.
- Minimum coverage:
  - Single-symbol and multi-symbol backtests
  - Short and long runs
  - Calls without `on_event` (default) and with `on_event` (stream-consuming)

## 2. Required Metrics

### 2.1 Stability

- Backtest failure rate (per run): must not exceed pre-migration baseline.
- Callback error rate (`callback_error_count > 0` ratio): must be explainable and reproducible.
- Critical event integrity: `started` and `finished` must always be paired.

### 2.2 Result Consistency

- Sample replay consistency:
  - Total return (`total_return`)
  - Max drawdown (`max_drawdown`)
  - Trade count (`len(trades)`)
- Pass criterion: no systematic drift against baseline; tiny float-level deviation is acceptable.

### 2.3 Performance

- Backtest latency P50/P95: no material regression.
- Peak memory: no abnormal growth.
- Event throughput (with `on_event`): no sustained backlog under high-frequency cases.

### 2.4 User Experience

- Zero-change compatibility rate for existing `run_backtest(...)` callers: target `100%`.
- Migration-related ticket volume: trending down or staying low.

## 3. Go / No-Go Gates

Proceed to Phase 5 only when all are met:

- No P0/P1 regressions for `2` consecutive release cycles.
- Consistency sampling passes without systematic drift.
- Performance metrics show no significant baseline regression.
- No new compatibility-breaking feedback on `run_backtest`.

Hold Phase 5 when any of the following occurs:

- Non-trivial result divergence cannot be mitigated quickly.
- Significant performance regression without short-term fix.
- Multiple user-blocking incidents directly related to the unified core.

## 4. Rollback and Safety Net

- Since Phase 5, rollback is release-level and no runtime rollback flag is provided.
- Each rollback should record:
  - Trigger condition
  - Impact scope
  - Fix plan and target version for returning to unified core

## 5. Phase-5 Readiness

- Confirm internal call paths default to unified core.
- Use `run_backtest(..., on_event=...)` as the explicit stream semantic entry.
- Publish release notes clarifying Phase 5 removes internal branching only, without changing public API behavior.
