# Live Functional Strategy Quickstart

This guide focuses on function-style strategy entry with LiveRunner, covering both `paper` and `broker_live` modes.

## 1. When to use this

- You prefer `on_bar(ctx, bar)` style over subclassing `Strategy`.
- You want a fast migration path from function-style backtests to live sessions.
- You need direct `submit_order(...)` in `broker_live`.

## 2. Two runtime modes

### 2.1 paper (simulated matching)

Start with paper mode to verify callback flow:

- Example: [38_live_functional_strategy_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/38_live_functional_strategy_demo.py)
- Typical setup:
  - `trading_mode="paper"`
  - `strategy_cls=on_bar`
  - `initialize/on_order/on_trade/on_timer/context`

### 2.2 broker_live (real broker order routing)

Switch to broker_live after gateway connectivity is verified:

- Example: [39_live_broker_submit_order_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/39_live_broker_submit_order_demo.py)
- Audit example: [42_live_broker_event_audit_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/42_live_broker_event_audit_demo.py)
- Key points:
  - `trading_mode="broker_live"`
  - call `ctx.submit_order(...)` inside `on_bar`
  - pass explicit `client_order_id` for idempotency tracking
  - optional `on_broker_event` for unified `event_type/owner_strategy_id/payload` persistence

## 3. Function-style template

```python
def initialize(ctx):
    ctx.sent = False

def on_bar(ctx, bar):
    if not ctx.sent and hasattr(ctx, "submit_order"):
        ctx.submit_order(
            symbol=bar.symbol,
            side="Buy",
            quantity=1.0,
            client_order_id="demo-1",
            order_type="Market",
        )
        ctx.sent = True

runner = LiveRunner(
    strategy_cls=on_bar,
    initialize=initialize,
    on_order=on_order,
    on_trade=on_trade,
    on_timer=on_timer,
    context={"strategy_name": "demo"},
    instruments=instruments,
    broker="ctp",
    trading_mode="broker_live",
)
runner.run(duration="30s", show_progress=False)
```

## 4. Common troubleshooting

- `submit_order not injected yet`
  - Cause: trader gateway binding is not ready.
  - Fix: guard with `hasattr(ctx, "submit_order")` before placing.
- `duplicate active client_order_id`
  - Cause: reused active client id.
  - Fix: generate a fresh `client_order_id` for each new order.
- Market data arrives but no trades
  - Cause: trader gateway not connected, risk rejection, or invalid lot/tick constraints.
  - Fix: inspect `on_order` status and rejection reason first.

## 5. Suggested rollout

- Step 1: validate callback flow in paper mode.
- Step 2: run broker_live with minimum order size.
- Step 3: add advanced logic after connectivity is stable.
