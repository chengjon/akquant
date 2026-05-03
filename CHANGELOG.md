# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **File restructuring**: Large Python files split into sub-modules for maintainability. All public import paths preserved via facade re-export.
  - `backtest/engine.py` (4384→2950 lines): extracted `_types`, `_execution`, `_instruments`, `_strategy_build`, `_validation`, `_data_loading`
  - `talib/funcs.py` (3907→120 lines): extracted `_dispatch`, `_math`, `_overlays`, `_momentum`, `_trend`, `_candlestick`
  - `plot/report.py` (1993→300 lines): extracted `_svg_assets`, `_chart_builder`, `_table_builder`
  - `optimize.py` (1072 lines → `optimize/` package): split into `_data`, `_worker`, `_grid_search`, `_walk_forward`
  - `strategy.py` (2032→1865 lines): extracted `strategy_types`, `strategy_order_groups`
  - `live.py` (1129→1069 lines): extracted `live_helpers`

### Added
- `run_backtest` now supports optional `on_event` callback and can emit stream events directly.
- Added `ChinaOptionsConfig` with prefix-level option fee configuration (`fee_by_symbol_prefix`).
- Added Engine API `set_options_fee_rules_by_prefix(symbol_prefix, commission_per_contract)`.
- **Fill Policy**: `PriceBasis` extended with `MidQuote` (HL/2), `Typical` (HLC/3), `VwapBar` (single-bar VWAP) — `set_fill_policy()` now accepts `"mid_quote"`, `"typical"`, `"vwap_bar"`.
- **K-line Patterns**: 20 candlestick pattern indicators in Rust with Python wrappers — Batch 1: `CDLDOJI`, `CDLHAMMER`, `CDLHANGINGMAN`, `CDL_ENGULFING`, `CDL_HARAMI`, `CDL_MORNINGSTAR`, `CDL_EVENINGSTAR`, `CDL_3BLACKCROWS`, `CDL_3WHITESOLDIERS`, `CDL_SHOOTINGSTAR`; Batch 2: `CDLPIERCING`, `CDLDARKCLOUDCOVER`, `CDLHARAMICROSS`, `CDLMARUBOZU`, `CDLKICKING`, `CDLSPINNINGTOP`, `CDLRISEFALL3METHODS`, `CDLTHRUSTING`, `CDLINNECK`, `CDLONNECK` — returning +100 (bullish), -100 (bearish), 0 (no pattern).
- **Visualization**: `plot_comparison()` for multi-strategy comparison panels (equity overlay, drawdown, metrics table). Dashboard `rangeselector` buttons (1M/3M/6M/1Y/ALL) and `updatemenus` display toggle. Report template supports `comparison_results` parameter.
- **Asset Modules**: Python packages for `futures`, `stock`, `option`, `fund` — each with models, rules, and calculation interfaces (commission, margin, T+N checks).
- **Sizers**: `ATRSizer`, `KellySizer`, `RiskParitySizer`, `EqualWeightSizer` added to `sizer.py`.
- **ML Adapters**: `LightGBMAdapter`, `XGBoostAdapter` added to `ml/model.py`.
- **Indicator Incremental Update**: `EMA.update()`, `RSI.update()`, `MACD.update()` with pickle serialization support.
- **Gateway Boundary**: `factory.py` uses broker metadata `asset_class` for market model selection. `UnifiedOrderRequest` includes `broker_options`. Fail-closed guards for unsupported advanced order params. `QMTXtQuantBridge` emits `FutureWarning`. `bridge_url` raises `NotImplementedError`.
- **FUNCTION_TREE.md**: Project-wide function tree documentation.

### Changed
- `run_backtest_stream` is removed; stream scenarios should call `run_backtest(..., on_event=...)`.
- `run_backtest` always uses the unified stream core; runtime rollback flag `_engine_mode` is removed.
- Futures fee Engine API naming is standardized to `set_futures_fee_rules*`; legacy `set_future_fee_rules*` is removed.

## [0.1.13] - 2026-02-09

### Added
- Incremental learning support for `SklearnAdapter` (via `partial_fit`) and `PyTorchAdapter` (via weight reset control).
- `incremental` parameter in `ValidationConfig`.
- Updated `ml_guide.md` with new features and clarified API signatures.

### Changed
- `PyTorchAdapter` now defaults to `incremental=False` for strict Walk-Forward Validation.

## [0.1.12] - Previous Release
- Basic implementation of `BarAggregator`.
- Rust-based performance optimizations.
- Zero-copy data access via PyO3.
