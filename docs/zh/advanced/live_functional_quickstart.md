# Live 函数式策略上手手册

本文聚焦 LiveRunner 的函数式策略入口，帮助你在 `paper` 与 `broker_live` 两种模式下快速搭建最小闭环。

## 1. 适用场景

- 想保留 `on_bar(ctx, bar)` 风格，不继承 `Strategy` 类。
- 需要快速把回测中的函数式策略迁移到实时/仿真运行。
- 需要在 `broker_live` 下直接使用 `submit_order(...)`。

## 2. 两种运行模式

### 2.1 paper（撮合模拟）

推荐先用 paper 检查事件链路是否正常：

- 示例脚本：[38_live_functional_strategy_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/38_live_functional_strategy_demo.py)
- 典型参数：
  - `trading_mode="paper"`
  - `strategy_cls=on_bar`
  - `initialize/on_order/on_trade/on_timer/context`

### 2.2 broker_live（网关真实下单）

确认网关连通后切换到 broker_live：

- 示例脚本：[39_live_broker_submit_order_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/39_live_broker_submit_order_demo.py)
- 审计示例：[42_live_broker_event_audit_demo.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/42_live_broker_event_audit_demo.py)
- 关键点：
  - `trading_mode="broker_live"`
  - `on_bar` 中调用 `ctx.submit_order(...)`
  - 显式传入 `client_order_id` 便于幂等追踪
  - 可选 `on_broker_event` 统一落盘 `event_type/owner_strategy_id/payload`

## 3. 函数式入口模板

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

## 4. 常见排查

- `submit_order 尚未注入`
  - 原因：网关尚未完成交易侧绑定。
  - 处理：在 `on_bar` 中 `hasattr(ctx, "submit_order")` 判定后再下单。
- `duplicate active client_order_id`
  - 原因：重复提交活跃 client id。
  - 处理：每次下单生成新的 `client_order_id`。
- 有行情但无成交回调
  - 原因：交易网关未连通、风控拒单、最小变动价位/手数不合规。
  - 处理：优先检查 `on_order` 状态与拒单原因。

## 5. 建议上线流程

- 第一步：先跑 paper 模式，确认回调顺序与策略状态变更。
- 第二步：切换 broker_live，先用最小下单量做连通性验证。
- 第三步：稳定后再增加复杂逻辑（定时器、风控、分批下单）。
