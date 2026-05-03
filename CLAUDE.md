# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AKQuant is a high-performance quantitative trading framework with a **Rust core engine** exposed to Python via PyO3/maturin. The Python layer provides strategy development, backtesting, factor analysis, and live trading interfaces. Bilingual codebase (Chinese/English).

## Build & Development Commands

```bash
# Setup
uv sync
uv run maturin develop          # Compile Rust extension (must run after Rust changes)

# Lint & Type Check
uv run ruff check python/akquant tests
uv run mypy python/akquant

# Tests
uv run pytest                                  # All Python tests
uv run pytest tests/test_engine.py -k "test_name"  # Single test by name
uv run pytest tests/golden/test_golden.py      # Golden (regression) tests
./scripts/cargo-test.sh -q                     # Rust unit tests (handles macOS dylib path)

# Quick Verification (build + lint + smoke tests)
./scripts/dev-check.sh

# Documentation Quality
uv run python scripts/check_docs_links.py
uv run python scripts/check_docs_api_examples.py

# Pre-commit (runs ruff, mypy, doc checks)
uv run pre-commit run --all-files

# Generate Python type stubs
cargo run --bin stub_gen
```

## Architecture

### Rust-Python Bridge

Rust core (`src/`) compiles to a C extension via PyO3. Key classes (`Engine`, `Bar`, `Order`, `Trade`, `RiskManager`) are `#[pyclass]` structs registered in `src/lib.rs`. The Python package at `python/akquant/` imports the compiled `.so`/`.pyd` as `akquant.akquant`. The module layout in `pyproject.toml` (`python-source = "python"`, `module-name = "akquant.akquant"`) maps Rust output into the Python package.

### Pipeline Architecture

The engine (`src/engine/core.rs`, ~1100 lines) processes each bar through a fixed sequence of processors:

1. ChannelProcessor (events from previous iteration)
2. DataProcessor (fetch Bar/Tick)
3. ExecutionProcessor (pre-strategy order matching for NextOpen/NextClose modes)
4. StrategyProcessor (invoke user's `on_bar`/`on_tick`/`on_timer`)
5. ExecutionProcessor (post-strategy matching for CurrentClose mode)
6. StatisticsProcessor (equity/cash curves)
7. CleanupProcessor

Processors are defined in `src/pipeline/` and composed in `Engine::build_pipeline()`.

### Multi-Asset / Multi-Market

- `MarketModel` trait (`src/market/core.rs`) abstracts market rules (T+1, price limits, sessions)
- Implementations: `ChinaMarket` (A-share), `SimpleMarket` (generic), plus futures/options/funds models
- `ExecutionClient` trait (`src/execution/mod.rs`) abstracts order execution
- Per-asset matchers in `src/execution/`: `stock.rs`, `futures.rs`, `option.rs`, `crypto.rs`, `forex.rs`

### Strategy Slot System

Multiple concurrent strategies via `StrategySlot` structs, each with its own `StrategyContext`, risk budget, position tracking, and per-strategy risk limits. The bridge between Rust engine and Python strategy is `StrategyContext` (`src/context.rs`).

### Python Layer Structure

- `strategy.py` + `strategy_types.py` + `strategy_order_groups.py` — `Strategy` base class, runtime config, OCO/bracket logic
- `backtest/engine.py` (facade) + `_types`, `_execution`, `_instruments`, `_strategy_build`, `_validation`, `_data_loading` — `run_backtest()` entry point
- `config.py` — Nested config: `BacktestConfig` → `StrategyConfig` → `RiskConfig`, with per-instrument overrides
- `factor/` — Factor expression engine using Polars Lazy API (Alpha101-style expressions)
- `talib/funcs.py` (facade) + `_dispatch`, `_math`, `_overlays`, `_momentum`, `_trend`, `_candlestick` — TA-Lib dual backend (Python/Rust), 135 indicators
- `gateway/` — Broker gateway abstractions (CTP, PTrade, MiniQMT) for live trading
- `live.py` + `live_helpers.py` — `LiveRunner` for paper/live trading
- `optimize/` (package) — Grid search & walk-forward optimization
- `plot/report.py` (facade) + `_svg_assets`, `_chart_builder`, `_table_builder` — Plotly-based visualization & HTML reports

### Key Rust Modules

| Module | Purpose |
|--------|---------|
| `src/engine/` | Core backtest orchestrator, pipeline |
| `src/model/` | Domain models: Bar, Order, Instrument, trade types |
| `src/data/` | DataFeed, BarAggregator, batch array conversion |
| `src/execution/` | Order matching per asset type |
| `src/market/` | Market-specific rules (China A-share, futures, options) |
| `src/risk/` | Risk management (max drawdown, daily loss, position limits) |
| `src/analysis/` | BacktestResult, PerformanceMetrics |
| `src/statistics/` | Equity/cash/margin curves, position snapshots |
| `src/indicators/` | Rust-native TA indicators (135 total: moving_average, momentum, trend, volatility, volume, candlestick) |
| `src/margin/` | Margin calculators (futures, options) |
| `src/settlement/` | Settlement managers (expiry, option handlers) |
| `src/pipeline/` | Event-driven pipeline processor definitions |

### File Splitting Pattern

Large Python files use a **facade re-export** pattern: the original file becomes a thin import hub, actual code lives in `_`-prefixed sub-modules. All public import paths are preserved. When editing a facade file, all re-export imports must use `# noqa: F401` to prevent ruff from removing them. Splitting principles are documented in `.claude/plans/file-splitting-principles.md`.

## Git Workflow

- `main` branch: stable, matches PyPI releases
- `dev` branch: active development; all PRs target `dev`
- Commit format: Conventional Commits (`feat:`, `fix:`, `chore:`)

## Testing Notes

- Golden tests (`tests/golden/`) detect algorithmic regressions by comparing against locked baselines
- If an intentional algorithm change shifts baselines: `uv run python tests/golden/runner.py --generate-baseline` (explain in PR)
- Rust tests require `./scripts/cargo-test.sh` (not bare `cargo test`) due to macOS dylib path handling

## Code Style

- Python: PEP 8, enforced by ruff; line-length 88; target Python 3.10+
- Type annotations required (enforced by mypy with `disallow_untyped_defs = true`)
- Docstrings: PEP 257 convention (ruff rule D, with D100/D104 ignored)
- Rust: edition 2024

## Release

Tag-push triggers multi-platform wheel builds (Linux x86_64/aarch64/musl, Windows x64, macOS aarch64) via `maturin-action`, published to PyPI automatically.
