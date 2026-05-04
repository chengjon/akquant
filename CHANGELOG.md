# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.9] - 2026-05-04

### Added
- **TWAP Fill Strategy**: Multi-bar time-weighted order splitting via `twap_window` price basis. New `TwapScheduler` in `src/execution/twap.rs` splits parent orders into even child slices across N bars. Supports per-strategy and per-order TWAP config (`fill_policy.twap_bars`, `fill_twap_bars` parameter on `buy()`/`sell()`). Post-match cap approach ensures correct average price and partial fill tracking. 3 behavioral tests.
- **TensorFlowAdapter**: `ml/model.py` now includes `TensorFlowAdapter` for tf.keras models with incremental/non-incremental training, predict, save/load support.
- **60 Candlestick Patterns**: Batches 1–5 complete (CDLDOJI, CDLHAMMER, ..., CDLSTICKSANDWICH), bringing total Rust indicators to 178.
- **Hilbert Transform Indicators**: `HT_DCPERIOD`, `HT_DCPHASE`, `HT_PHASOR` — Ehlers adaptive cycle analysis.
- **Option Greek Risk Control**: `OptionGreekRiskRule` with BSM pricing, Delta/Gamma/Vega limits (portfolio + per-slot), Newton-Raphson IV solver, exchange-standard margin formula.
- **Fill Policy Extensions**: `MidQuote`, `Typical`, `VwapBar` price basis support in `set_fill_policy()`.
- **Asset Modules**: Python packages for `futures`, `stock`, `option`, `fund` — models, rules, calculation interfaces.
- **Sizers**: `ATRSizer`, `KellySizer`, `RiskParitySizer`, `EqualWeightSizer`.
- **ML Adapters**: `LightGBMAdapter`, `XGBoostAdapter`, `TensorFlowAdapter`.
- **Indicator Incremental Update**: `EMA.update()`, `RSI.update()`, `MACD.update()` with pickle support.
- **Visualization**: `plot_comparison()` multi-strategy panels, dashboard rangeselector/updatemenus.
- **Gateway Boundary**: broker metadata market model selection, `broker_options` field, fail-closed guards, `QMTXtQuantBridge` migration warning.

### Changed
- **File restructuring**: Large Python files split into sub-modules via facade re-export pattern.
- `run_backtest` always uses unified stream core; `on_event` callback for real-time events.
- Futures fee Engine API naming standardized to `set_futures_fee_rules*`.

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
