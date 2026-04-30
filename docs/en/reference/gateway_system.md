# Gateway System Architecture and CTP Notes

This page is maintained in Chinese first.

- Chinese full page: [AKQuant 交易网关系统架构与 CTP 实现](../../zh/reference/gateway_system.md)
- Related code:
  - `python/akquant/gateway/base.py`
  - `python/akquant/gateway/factory.py`
  - `python/akquant/gateway/mapper.py`
  - `python/akquant/gateway/ctp_adapter.py`
  - `python/akquant/gateway/ctp_native.py`
  - `python/akquant/live.py`

## Current Built-in Boundary

- CTP is the built-in gateway with the implemented live path for market data, place/cancel, and order/trade callbacks.
- `factory.py` returns `CTPMarketAdapter`; it returns `CTPTraderAdapter` only when trader connection parameters are present.
- `CTPTraderAdapter` supports `execution_semantics_mode="strict"` and `"compatible"`.
- `query_account()` currently returns `None`.
- `query_positions()` currently returns `[]`.
- `sync_today_trades()` currently returns `[]`.
- `sync_open_orders()` currently replays adapter memory open orders; it is not a true broker re-query.

## LiveRunner Notes

- `broker_live` injects broker submit/cancel capability through the LiveRunner broker bridge.
- The recovery loop calls `heartbeat()`, `connect()`, `sync_open_orders()`, and `sync_today_trades()`, but real recovery quality depends on each gateway implementation.
- `LiveRunner.run()` currently hardcodes `engine.use_china_futures_market()`.

## MiniQMT and PTrade

- The built-in MiniQMT and PTrade gateways are still in-memory placeholders in the current repository.
- They implement the unified gateway contract, but they are not real broker integrations today.

