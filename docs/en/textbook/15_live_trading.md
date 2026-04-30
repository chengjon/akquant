# Chapter 15: Live Trading Systems and Operations

This chapter is currently maintained in Chinese first, but the notes below summarize the most important implementation details and current limits in the codebase.

- Chinese chapter: [第 15 章：实盘交易系统与运维](../../zh/textbook/15_live_trading.md)
- Textbook home: [Chinese textbook index](../../zh/textbook/index.md)
- Live execution semantics note:
  - CTP supports `execution_semantics_mode` with `strict` (default) and `compatible`.
  - In `strict`, terminal order states are confirmed by `OnRtnOrder` callbacks.
- Current built-in broker boundaries:
  - CTP implements the main live path for market data, place/cancel, and order/trade callbacks.
  - CTP still does not implement real broker-backed `query_account()`, `query_positions()`, or `sync_today_trades()`.
  - MiniQMT and PTrade are still in-memory placeholders in the current repository.
  - `LiveRunner` currently hardcodes `engine.use_china_futures_market()`; a real stock `broker_live` path for MiniQMT/PTrade still needs market-model work.
- Practice links:
  - Primary example: [examples/textbook/ch15_live_trading.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_live_trading.py)
  - Extended example: [examples/textbook/ch15_strategy_loader.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_strategy_loader.py)
  - Supplementary example: [examples/44_strategy_source_loader_demo.py](https://github.com/akfamily/akquant/blob/main/examples/44_strategy_source_loader_demo.py)
  - Guide: [Live Functional Quickstart Guide](../advanced/live_functional_quickstart.md)
  - Capability matrix: [Broker Capability Matrix](../advanced/broker_capability_matrix.md)
  - Chinese gateway detail: [AKQuant 交易网关系统架构与 CTP 实现](../../zh/reference/gateway_system.md)
  - Chinese MiniQMT status/migration note: [MiniQMT 交易网关现状与迁移方案](../../zh/reference/miniqmt_trading_impl.md)
