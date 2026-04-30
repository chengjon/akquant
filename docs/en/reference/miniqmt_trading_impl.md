# MiniQMT Trading Status and Migration Notes

This page is maintained in Chinese first.

- Chinese full page: [MiniQMT 交易网关现状与迁移方案](../../zh/reference/miniqmt_trading_impl.md)
- Related code:
  - `python/akquant/gateway/miniqmt.py`
  - `python/akquant/gateway/factory.py`
  - `python/akquant/live.py`

## Current Status

- The built-in `MiniQMTTraderGateway` is still an in-memory placeholder.
- Orders, trades, and account snapshots are kept in process memory by default.
- `query_account()` is constructor-argument backed.
- `query_positions()` currently returns `[]`.
- `heartbeat()` currently reflects only local `connected` state.
- `ingest_order_event()` and `ingest_trade_event()` are the current extension points.
- `MiniQMTMarketGateway` is also a placeholder and does not automatically drive `DataFeed`.

## Recommended Migration Shape

- Keep `MiniQMTTraderGateway` as the unified protocol layer in phase 1.
- Add an optional bridge layer for xtquant/QMT integration.
- Avoid introducing a separate `MiniQMTTraderAdapter` in the first migration phase unless the bridge becomes too complex.

## Additional Contracts Needed Beyond `gateway/miniqmt.py`

- Add broker-level market selection so stock live trading can use `use_china_market()` instead of the current futures-only path.
- Extend the live submit contract if broker-specific order fields must be passed through.
- Define real recovery semantics for `heartbeat()`, `sync_open_orders()`, and `sync_today_trades()`.
- Implement real account/position queries if strategy logic depends on broker-backed balances or T+1 checks.
- Add a real market-data bridge if MiniQMT live data must drive `on_bar()` / `DataFeed`.
- Add dedicated tests for bridge mapping, recovery, and audit paths.

