# Broker Capability Matrix

## Field Definitions

- `market_data`: Market data integration capability (`Tick` / `Bar`)
- `order_entry`: Supported order entry styles
- `cancel`: Order cancel support
- `execution_report`: Order/trade callback support
- `account`: Account / position query support
- `tif`: Supported `TimeInForce` values
- `notes`: Semantic differences or implementation limits

## Capability Matrix

| Broker | market_data | order_entry | cancel | execution_report | account | tif | notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IB | Tick/Bar | Market/Limit/Stop/StopLimit | Yes | Yes | Yes | DAY/GTC/IOC | Priority external integration |
| Oanda | Tick/Bar | Market/Limit/Stop | Yes | Yes | Yes | GTC/GTD/FOK/IOC | FX/CFD semantics |
| CCXT | Tick/Bar(exchange-dependent) | Market/Limit(main) | Yes | Yes | Yes | exchange-dependent | Usually needs exchange-specific layering |
| CTP | Tick/Bar | Market/Limit(mapped) | Yes | Yes | No | GFD/IOC/FAK/FOK(mapped) | Market data + place/cancel/order/trade callback path implemented; account, position, trade replay, and true broker query recovery are still missing |
| MiniQMT | No (placeholder) | Market/Limit(placeholder) | Yes (placeholder) | Yes (placeholder) | Partial (account from constructor args, positions empty) | DAY/GTC (placeholder) | Pure in-memory placeholder today, not connected to real QMT |
| PTrade | No (placeholder) | Market/Limit(placeholder) | Yes (placeholder) | Yes (placeholder) | Partial (account from constructor args, positions empty) | DAY/GTC (placeholder) | Pure in-memory placeholder today, not connected to a real broker |

## Unified Error Contract

- `UNSUPPORTED_ORDER_TYPE`
- `UNSUPPORTED_TIF`
- `BROKER_DISCONNECTED`
- `BROKER_RATE_LIMITED`
- `BROKER_REJECTED`

## Minimum Production Acceptance

- Market data subscription succeeds and produces observable callbacks.
- Order placement receives status updates and trade callbacks.
- Cancel requests can be traced to a final state.
- Account and position queries return non-empty broker-backed structures.

> Note: the list above is a production acceptance target, not a statement that every built-in broker already satisfies it. In the current codebase, CTP does not yet satisfy the account/position requirement, and MiniQMT/PTrade do not yet satisfy the real market data requirement.

## Related Code

- [factory.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/factory.py)
- [registry.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/registry.py)
- [base.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/base.py)

## Related Docs

- [Custom Broker Registry](custom_broker_registry.md)
- [Custom Broker Production Checklist](custom_broker_production_checklist.md)
- Chinese detail page: [Broker Capability Matrix（模板 + 首批填充）](../../zh/advanced/broker_capability_matrix.md)
