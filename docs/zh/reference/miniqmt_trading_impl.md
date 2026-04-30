# MiniQMT 交易网关现状与迁移方案

> **状态**：按当前仓库代码审阅，MiniQMT 仍是内存占位实现。本文将“当前已实现事实”和“对接真实 QMT 的迁移草案”分开描述。

---

## 一、当前实现状态

MiniQMT 网关（`python/akquant/gateway/miniqmt.py`）目前是**内存占位实现**，不连接任何外部券商系统。它实现了 `TraderGateway` 所需的统一接口，并提供 `ingest_order_event()` / `ingest_trade_event()` 两个外部事件注入口；所有订单、成交、账户数据默认都只存在当前进程内存中。

### 1.1 类结构

```
MiniQMTMarketGateway          MiniQMTTraderGateway
├── connect()                  ├── connect()
├── disconnect()               ├── disconnect()
├── subscribe()                ├── place_order()
├── unsubscribe()              ├── cancel_order()
├── on_tick()                  ├── query_order()
├── on_bar()                   ├── query_trades()
└── start()                    ├── query_account()
                               ├── query_positions()
                               ├── on_order()
                               ├── on_trade()
                               ├── on_execution_report()
                               ├── sync_open_orders()
                               ├── sync_today_trades()
                               ├── heartbeat()
                               ├── ingest_order_event()   ← 外部事件入口
                               ├── ingest_trade_event()    ← 外部事件入口
                               └── start()
```

### 1.2 当前实现细节

#### 行情网关 (MiniQMTMarketGateway)

- `connect()` / `disconnect()`：仅设置 `self.connected` 布尔标志
- `subscribe()` / `unsubscribe()`：维护 `self.symbols` 列表
- `start()` 仅调用 `connect()`，不会启动任何真实行情循环
- 当前类本身不会向 `DataFeed` 推送 Tick/Bar；若要接真实行情，桥接层必须自己写入 `feed` 或复用聚合逻辑

#### 交易网关 (MiniQMTTraderGateway)

**订单管理**（纯内存）：

```python
def place_order(self, req: UnifiedOrderRequest) -> str:
    # 1. 幂等性检查
    if self.enforce_client_order_id_uniqueness:
        existing = self.client_to_broker_order_ids.get(req.client_order_id)
        if existing and 活跃单: return existing  # 返回已有

    # 2. 生成 broker_order_id
    broker_order_id = f"miniqmt-{req.client_order_id}-{self._order_seq}"

    # 3. 创建 SUBMITTED 快照
    snapshot = UnifiedOrderSnapshot(status=UnifiedOrderStatus.SUBMITTED, ...)

    # 4. 发射 order + execution_report 回调
    self._emit_order(snapshot)
    self._emit_execution_report(report)

    return broker_order_id
```

**撤单**：
```python
def cancel_order(self, broker_order_id: str):
    order = self.orders.get(broker_order_id)
    if order:
        order.status = UnifiedOrderStatus.CANCELLED
        self._emit_order(order)
        self._emit_execution_report(report)
        self._cleanup_terminal_order_mapping(order)  # 终态清理映射
```

**账户查询**（从构造参数读取）：
```python
def query_account(self):
    return UnifiedAccount(
        account_id=self.kwargs.get("account_id", "miniqmt"),
        equity=self.kwargs.get("equity", 0.0),
        cash=self.kwargs.get("cash", 0.0),
        available_cash=self.kwargs.get("available_cash", 0.0),
    )
```

**持仓查询**：
```python
def query_positions(self) -> list[UnifiedPosition]:
    return []
```

**外部事件注入**：
```python
def ingest_order_event(self, payload: dict) -> UnifiedOrderSnapshot:
    """外部系统（如真实 QMT 回调）可通过此方法注入订单事件"""
    snapshot = self.mapper.map_order_event(payload)  # 统一映射
    self.orders[snapshot.broker_order_id] = snapshot
    self._emit_order(snapshot)
    self._emit_execution_report(report)
    return snapshot

def ingest_trade_event(self, payload: dict) -> UnifiedTrade:
    """外部系统可通过此方法注入成交事件"""
    trade = self.mapper.map_trade_event(payload)
    self.trades.append(trade)
    self._emit_trade(trade)
    return trade
```

### 1.3 订单 ID 格式

```
格式: miniqmt-{client_order_id}-{seq}
示例: miniqmt-strat1-au2606-buy-1
       │       │              └── 自增序列号
       │       └── 客户端订单 ID
       └── 前缀标识
```

### 1.4 配置参数

| 参数 | 默认值 | 用途 |
|------|--------|------|
| `account_id` | `"miniqmt"` | 账户 ID |
| `equity` | `0.0` | 总资产 |
| `cash` | `0.0` | 现金 |
| `available_cash` | `0.0` | 可用现金 |
| `enforce_client_order_id_uniqueness` | `True` | 是否强制客户端订单 ID 唯一 |
| `event_mapper` | `create_default_mapper()` | 事件映射器 |

---

## 二、QMT (迅投) 技术背景

> **说明**：本节涉及 `xtquant` / `xttrader` / `xtdata` 的接口名称与行为，均属于**外部 SDK 假设**，仓库内没有对应实现或测试。真正迁移前，必须以你手头的 QMT/xtquant 版本文档和样例代码复核。

### 2.1 QMT 是什么

QMT（Quantitative Market Trading）是迅投科技开发的量化交易平台，华鑫证券、国金证券等多家券商提供 QMT 接入。MiniQMT 是其轻量版本，支持通过 Python API 进行程序化交易。

### 2.2 QMT 接入方式对比

| 接入方式 | 说明 | AKQuant 适用性 |
|---------|------|---------------|
| **xtquant** (Python 库) | QMT 官方 Python SDK，通过本地 QMT 客户端中转 | 主要对接路径 |
| **QMT 客户端 + 文件交互** | 通过文件系统传递订单和回报 | 备选方案 |
| **券商定制 API** | 部分券商提供 REST/WebSocket 接口 | 依赖券商 |

### 2.3 xtquant 核心接口

```python
from xtquant import xttrader, xtconstant
from xtquant.xttype import StockAccount

# 连接
session_id = xttrader.connect(path)  # 连接 QMT 客户端

# 下单
order_id = xttrader.order_stock(
    account,           # StockAccount 对象
    stock_code,        # "SH.600000" 格式
    xtconstant.STOCK_BUY,  # 买卖方向
    amount,            # 数量
    xtconstant.FIX_PRICE,  # 订单类型
    price,             # 价格
    strategy_name,     # 策略名
    order_remark,      # 订单备注
)

# 撤单
xttrader.cancel_order_stock(session_id, order_id)

# 查询
orders = xttrader.query_stock_orders(account, is_cancelable=True)
trades = xttrader.query_stock_trades(account)
positions = xttrader.query_stock_positions(account)
assets = xttrader.query_stock_assets(account)

# 注册回调
class TraderCallback:
    def on_order_stock_async_response(self, response): ...
    def on_stock_order(self, order): ...
    def on_stock_trade(self, trade): ...
    def on_stock_position(self, position): ...
    def on_stock_asset(self, asset): ...

xttrader.register_callback(session_id, TraderCallback())
```

### 2.4 代码格式差异

| 维度 | QMT (xtquant) | AKQuant 统一模型 |
|------|---------------|-----------------|
| 股票代码 | `"SH.600000"` / `"SZ.000001"` | `"600000"` / `"000001"` |
| 买卖方向 | `xtconstant.STOCK_BUY` / `STOCK_SELL` | `"buy"` / `"sell"` |
| 订单类型 | `xtconstant.FIX_PRICE` / `MARKET_BEST5_TO_CANCEL` | `"limit"` / `"market"` |
| 账户 | `StockAccount("account_id")` | `UnifiedAccount` |
| 订单状态 | `xtconstant.ORDER_UNCONFIRMED` / `ORDER_CONFIRMED` 等 | `UnifiedOrderStatus` 枚举 |

---

## 三、对接方案

### 3.1 推荐架构

第一阶段建议**不要新增 `MiniQMTTraderAdapter`**。当前工厂和 `LiveRunner` 已经把 `MiniQMTTraderGateway` 当作统一交易网关使用，最小改动路径是：

1. 保留现有 `MiniQMTTraderGateway` 作为统一协议实现层。
2. 新增一个可选的 `QMTXtQuantBridge`，专门负责外部 SDK 调用、字段转换和回调注册。
3. 在 `MiniQMTTraderGateway` 内部根据是否配置 bridge 决定走“真实 QMT”还是“内存占位”。

这样可以最小化对 `factory.py`、`LiveRunner`、现有测试和占位回退路径的影响。

### 3.2 方案概览

```
┌─────────────────────────────────────────────────────┐
│                  AKQuant 策略层                       │
├─────────────────────────────────────────────────────┤
│         MiniQMTTraderGateway（保留，统一协议层）        │
│  ┌─ place_order/cancel/query/sync/heartbeat       ─┐│
│  └─ ingest_order_event / ingest_trade_event       ─┘│
├─────────────────────────────────────────────────────┤
│             xtquant 桥接层 (新增)                     │
│  ┌─ QMTXtQuantBridge                              ──┐│
│  │  ├─ 连接 QMT 客户端 (xttrader.connect)           ││
│  │  ├─ 注册回调 (TraderCallback)                    ││
│  │  ├─ 代码格式转换 (SH.600000 ↔ 600000)            ││
│  │  ├─ client_order_id ↔ native_order_id 映射       ││
│  │  └─ 事件转发 → ingest_order/trade_event          ││
│  └─────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│            QMT 客户端 (本地运行)                      │
│          xtquant / xttrader                          │
└─────────────────────────────────────────────────────┘
```

### 3.3 实现步骤

#### 步骤 1：创建 xtquant 桥接类

```python
# python/akquant/gateway/miniqmt_xtquant.py (新文件)

from xtquant import xttrader, xtconstant
from xtquant.xttype import StockAccount


class QMTXtQuantBridge:
    """桥接 xtquant SDK 与 AKQuant MiniQMT 网关。"""

    # QMT 状态 → AKQuant 统一状态
    STATUS_MAP = {
        xtconstant.ORDER_UNCONFIRMED: "submitted",
        xtconstant.ORDER_CONFIRMED: "submitted",
        xtconstant.ORDER_SUCCEEDED: "filled",
        xtconstant.ORDER_CANCELLED: "cancelled",
        xtconstant.ORDER_REJECTED: "rejected",
        xtconstant.ORDER_PARTSUCC: "partially_filled",
    }

    def __init__(self, qmt_path: str, account_id: str):
        self.session_id = xttrader.connect(qmt_path)
        self.account = StockAccount(account_id)
        self.client_to_native_order_ids: dict[str, str] = {}
        self.native_to_client_order_ids: dict[str, str] = {}
        xttrader.register_callback(self.session_id, self._create_callback())

    def _format_symbol(self, symbol: str) -> str:
        """AKQuant → QMT: '600000' → 'SH.600000'"""
        if "." in symbol:
            return symbol
        if symbol.startswith("6"):
            return f"SH.{symbol}"
        return f"SZ.{symbol}"

    def _strip_symbol(self, qmt_code: str) -> str:
        """QMT → AKQuant: 'SH.600000' → '600000'"""
        return qmt_code.split(".")[-1] if "." in qmt_code else qmt_code

    def place_native_order(self, client_order_id, symbol, side, quantity, price, order_type):
        """下单并返回 native order_id，同时保存映射。"""
        qmt_symbol = self._format_symbol(symbol)
        qmt_side = xtconstant.STOCK_BUY if side == "buy" else xtconstant.STOCK_SELL
        qmt_type = (
            xtconstant.FIX_PRICE if order_type == "limit"
            else xtconstant.MARKET_BEST5_TO_CANCEL
        )
        native_order_id = xttrader.order_stock(
            self.account, qmt_symbol, qmt_side, int(quantity),
            qmt_type, price, "akquant", "akquant-order"
        )
        self.client_to_native_order_ids[str(client_order_id)] = str(native_order_id)
        self.native_to_client_order_ids[str(native_order_id)] = str(client_order_id)
        return native_order_id

    def resolve_client_order_id(self, native_order_id) -> str:
        return self.native_to_client_order_ids.get(str(native_order_id), "")

    def cancel_native_order(self, order_id):
        """撤单"""
        xttrader.cancel_order_stock(self.session_id, order_id)
```

桥接层最少还需要补上：

- 平台/依赖检查：非 Windows 或缺少 `xtquant` 时给出清晰错误，而不是在 import 时直接炸掉。
- 查询包装：把 QMT 的“可撤订单、当日成交、持仓、资金”查询统一包装成 MiniQMT 网关可消费的结构。
- 回调注册：把 QMT 原始回调转成 `ingest_order_event()` / `ingest_trade_event()` 所需 payload。

#### 步骤 2：实现 TraderCallback

```python
class QMTCallback:
    """QMT 异步回调 → 转发到 MiniQMT 网关"""

    def __init__(self, gateway: MiniQMTTraderGateway, bridge: QMTXtQuantBridge):
        self.gateway = gateway
        self.bridge = bridge

    def on_stock_order(self, order):
        symbol = self.bridge._strip_symbol(order.stock_code)
        status = QMTXtQuantBridge.STATUS_MAP.get(order.order_status, "submitted")
        client_order_id = self.bridge.resolve_client_order_id(order.order_id)
        self.gateway.ingest_order_event({
            "client_order_id": client_order_id,
            "broker_order_id": f"miniqmt-{order.order_id}",
            "symbol": symbol,
            "status": status,
            "filled_quantity": order.traded_volume,
            "avg_fill_price": order.traded_price,
            "reject_reason": order.order_remark,
            "timestamp_ns": int(order.order_time * 1e9),
        })

    def on_stock_trade(self, trade):
        symbol = self.bridge._strip_symbol(trade.stock_code)
        client_order_id = self.bridge.resolve_client_order_id(trade.order_id)
        self.gateway.ingest_trade_event({
            "trade_id": str(trade.traded_id),
            "broker_order_id": f"miniqmt-{trade.order_id}",
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": "buy" if trade.order_type in [xtconstant.STOCK_BUY] else "sell",
            "quantity": trade.traded_volume,
            "price": trade.traded_price,
            "timestamp_ns": int(trade.traded_time * 1e9),
        })
```

#### 步骤 3：扩展 MiniQMTTraderGateway

在 `MiniQMTTraderGateway` 中加入可选 `bridge` 支持：

```python
def place_order(self, req: UnifiedOrderRequest) -> str:
    # ... 现有幂等性检查 ...

    if self.bridge is not None:
        # 有桥接层时，调用真实 QMT API，并保留 client_order_id → native order_id 关系
        native_order_id = self.bridge.place_native_order(
            client_order_id=req.client_order_id,
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            price=req.price,
            order_type=req.order_type,
        )
        broker_order_id = f"miniqmt-{native_order_id}"
    else:
        # 无桥接层，内存模拟
        broker_order_id = f"miniqmt-{req.client_order_id}-{self._order_seq}"

    # ... 后续创建 snapshot、发射回调 ...
```

除 `place_order()` 外，还需要一起补齐：

- `cancel_order()`：`broker_order_id -> native_order_id` 的解析与撤单调用。
- `query_account()` / `query_positions()`：bridge 存在时走真实查询；无 bridge 时保留当前占位行为。
- `sync_open_orders()` / `sync_today_trades()`：bridge 存在时向 QMT 查询并映射为统一模型，而不是只返回本地内存。
- `heartbeat()`：bridge 存在时检查 QMT 会话是否有效，不能继续只看 `self.connected`。

#### 步骤 4：更新工厂函数

在 `factory.py` 中增加 MiniQMT 桥接配置：

```python
if broker_key == "miniqmt":
    trader_gateway = MiniQMTTraderGateway(**kwargs)
    # 如果提供了 QMT 配置，按需创建桥接
    qmt_path = kwargs.get("qmt_path")
    if qmt_path:
        from .miniqmt_xtquant import QMTXtQuantBridge
        trader_gateway.bridge = QMTXtQuantBridge(
            qmt_path=qmt_path,
            account_id=kwargs.get("account_id", ""),
        )
```

> **实现建议**：这里应采用懒加载和清晰报错，因为当前 `pyproject.toml` 并没有 `xtquant` 相关依赖项。

### 3.4 使用示例（对接后）

```python
from akquant import AssetType, Instrument, Strategy
from akquant.live import LiveRunner

class StockStrategy(Strategy):
    def on_bar(self, bar):
        pos = self.get_position(bar.symbol)
        if pos == 0 and self._should_buy(bar):
            self.buy(bar.symbol, 100)  # 股票最小单位 100 股

instruments = [
    Instrument(symbol="600000", asset_type=AssetType.Stock, lot_size=100),
    Instrument(symbol="000001", asset_type=AssetType.Stock, lot_size=100),
]

# MiniQMT broker_live 迁移示意
runner = LiveRunner(
    strategy_cls=StockStrategy,
    instruments=instruments,
    broker="miniqmt",
    trading_mode="broker_live",
    gateway_options={
        "qmt_path": "C:/国金QMT/userdata_mini",
        "account_id": "your_account_id",
        "equity": 1_000_000,
    },
)
runner.run(cash=1_000_000)
```

> **注意**：这段代码是“完成 bridge 与股票市场模型改造之后”的目标形态，不是当前仓库可直接运行的现状。同时，`LiveRunner` 当前并不接受 `qmt_path`、`account_id`、`equity` 这类顶层命名参数，MiniQMT 特定参数必须通过 `gateway_options={...}` 传入。

---

## 四、行情对接方案

MiniQMT 行情目前也是占位实现。对接 xtquant 行情的方案：

### 4.1 xtquant 行情接口

```python
from xtquant import xtdata

# 订阅行情
xtdata.subscribe_quote(
    stock_list=["SH.600000", "SZ.000001"],
    callback=on_tick_callback,
)

# 获取 K 线
bars = xtdata.get_market_data(
    field_list=["open", "high", "low", "close", "volume"],
    stock_list=["SH.600000"],
    period="1m",
    count=100,
)
```

### 4.2 桥接方案

```python
class QMTMarketBridge:
    def __init__(self, gateway: MiniQMTMarketGateway):
        self.gateway = gateway

    def on_tick(self, data):
        """xtdata 回调 → 转换后写入 AKQuant 行情链路"""
        for symbol, tick_data in data.items():
            stripped = symbol.split(".")[-1]
            price = tick_data.get("lastPrice", 0)
            volume = tick_data.get("volume", 0)
            ts = time.time_ns()

            # 关键点：仅调用 tick_callback 不足以驱动 LiveRunner/Engine。
            # 真正需要的是复用 CTPMarketGateway 的思路，把数据写入 feed
            # 或使用聚合器生成 Bar 后 feed.add_bar(bar)。
            if self.gateway.tick_callback:
                self.gateway.tick_callback(
                    {"symbol": stripped, "price": price, "volume": volume, "timestamp_ns": ts}
                )
```

这里需要特别注意：

- `LiveRunner` 当前是通过 `DataFeed` 消费实时行情，不会自动消费 `MarketGateway.on_tick()` 回调。
- 因此 MiniQMT 行情桥接若只调用 `tick_callback`，策略仍然收不到可驱动 `on_bar()` 的实时数据。
- 真实实现应当像 `CTPMarketGateway` 一样，直接写入 `feed`，或者在桥接层内部使用 `BarAggregator` 生成 Bar 后调用 `feed.add_bar()`。

---

## 五、需要注意的问题

### 5.1 QMT 限制

| 限制 | 说明 |
|------|------|
| **必须本地运行 QMT 客户端** | xtquant 通过本地 QMT 客户端中转，不支持直连券商服务器 |
| **Windows Only** | QMT 客户端仅支持 Windows，Linux 需通过 Wine 或远程调用 |
| **交易时段限制** | 只能在交易时段下单，集合竞价和盘中规则需遵守 |
| **A股 T+1** | 当日买入不能当日卖出 |
| **最小交易单位** | 股票 100 股，ETF 100 份，与期货不同 |
| **订单号格式** | QMT 的 order_id 与 CTP 的 broker_order_id 格式不同 |

### 5.2 代码映射关键点

```
股票代码格式转换：
  AKQuant: "600000" (纯数字)
  QMT:     "SH.600000" (带市场前缀)
  规则: 6开头 → SH, 0/3开头 → SZ

订单状态映射：
  QMT ORDER_UNCONFIRMED → SUBMITTED
  QMT ORDER_CONFIRMED   → SUBMITTED
  QMT ORDER_SUCCEEDED   → FILLED
  QMT ORDER_PARTSUCC    → PARTIALLY_FILLED
  QMT ORDER_CANCELLED   → CANCELLED
  QMT ORDER_REJECTED    → REJECTED
```

### 5.3 风险控制

- MiniQMT 当前实现没有真实的风控检查，对接后需增加：
  - 订单数量校验（A 股 100 的整数倍）
  - 涨跌停价格校验
  - 可用资金检查
  - T+1 卖出限制检查

### 5.4 `LiveRunner` / Engine 侧还需补充的内容

如果你要把 MiniQMT 真正迁移成可运行的股票实盘路径，只改 `gateway/miniqmt.py` 还不够，还需要补这些外围契约：

1. **股票市场配置**：`LiveRunner.run()` 当前固定调用 `engine.use_china_futures_market()`；MiniQMT 迁移需要新增 broker 级市场选择，至少让 `miniqmt/ptrade` 可以走 `use_china_market()`。
2. **额外下单字段**：当前 `broker_live` 注入的 `submit_order()` 只支持标准字段，额外 broker 字段会被直接拒绝。如果 xtquant 需要 `strategy_name`、`order_remark` 或更细的价格类型，需要同步扩展 live 下单契约。
3. **统一审计**：建议把 `on_broker_event` 的用法写进 MiniQMT 文档，便于多策略归因、落盘和问题排查。
4. **恢复语义**：需要明确 `heartbeat()`、`sync_open_orders()`、`sync_today_trades()` 的数据来源是“QMT 客户端查询”而不是“本地内存回放”。
5. **账户/持仓闭环**：如果策略依赖真实资金、可用持仓或 T+1 校验，就必须接通 `query_account()` / `query_positions()`。

### 5.5 依赖与部署

- 当前 `pyproject.toml` 没有 `xtquant` optional dependency，需要补安装说明或按平台拆分依赖。
- 需要在 import 时做 graceful fallback，避免非 Windows 环境直接导入失败。
- 需要补运行前检查：QMT 客户端路径、账号登录状态、本地会话可用性。

### 5.6 测试与验收

至少补以下测试：

- `client_order_id ↔ native_order_id ↔ broker_order_id` 映射正确。
- 重复提交时返回已有活动订单，不重复报单。
- QMT 回调乱序、重复回调、断线重连后的去重与恢复。
- `sync_open_orders()` / `sync_today_trades()` 确实来自 QMT 查询，不是本地缓存。
- 非 Windows / 缺少 `xtquant` 时能给出清晰错误。
- MiniQMT 行情桥接能真正驱动 `DataFeed`，而不是只触发一个孤立的 callback。

---

## 六、文件变更清单

对接 MiniQMT 真实交易预计需要修改/新增的文件如下。其中示例脚本草案已补充到当前工作区，但仍只代表迁移示意，不代表真实 QMT 链路已经实现：

| 文件 | 操作 | 说明 |
|------|------|------|
| `gateway/miniqmt_xtquant.py` | **新增** | xtquant 桥接层 |
| `gateway/miniqmt.py` | **修改** | 增加 bridge 支持，place_order 调用真实 API |
| `gateway/factory.py` | **修改** | 增加 qmt_path 参数处理 |
| `live.py` | **修改** | MiniQMT 股票市场配置、必要时扩展 broker_live 下单契约 |
| `pyproject.toml` / 安装文档 | **修改** | 说明或管理 `xtquant` 依赖 |
| `tests/test_gateway_miniqmt_xtquant.py` | **新增** | 桥接层测试 |
| `tests/test_live_runner_broker_bridge.py` | **修改/新增** | MiniQMT 恢复、映射、审计路径测试 |
| `examples/06_live_trading_miniqmt.py` | **已补充（草案）** | MiniQMT 使用示例；当前仅演示占位模式与未来桥接参数形态 |

---

## 七、迁移前必须确认的决策

1. **架构决策**：第一阶段是否坚持“保留 `MiniQMTTraderGateway` + 新增 bridge”的最小改动方案。
2. **行情优先级**：若只迁移交易，不迁移行情，文档里必须明确 `MiniQMTMarketGateway` 仍是占位实现。
3. **订单扩展字段**：是否需要在 `broker_live` 路径开放 QMT 专有下单参数；如果需要，改动范围会扩到 `LiveRunner` 与对外 API。
4. **恢复与对账范围**：只做最小下单闭环，还是一起补齐账户、持仓、当日成交、未结订单同步。
5. **平台策略**：是否只支持 Windows 原生运行，还是要同时支持远程调用/Wine/代理进程方案。
