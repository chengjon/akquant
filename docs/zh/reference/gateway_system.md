# AKQuant 交易网关系统架构与 CTP 实现

## 一、系统总览

AKQuant 网关系统采用 **"统一协议 + 券商适配器/网关实现"** 设计模式，通过 Python Protocol 定义统一的行情和交易接口，各券商实现各自的适配器或占位网关，策略层无需关心底层券商差异。

> **按当前仓库代码统计**：CTP 已具备行情、下单、撤单、订单/成交回报主链路；账户查询、持仓查询、broker 侧恢复同步尚未补齐。MiniQMT/PTrade 仍是内存占位实现。

### 1.1 目录结构

```
python/akquant/gateway/
├── __init__.py        # 公共 API 导出
├── base.py            # Protocol 协议定义 + GatewayBundle
├── models.py          # 统一数据模型（订单、成交、账户等）
├── mapper.py          # BrokerEventMapper: 状态/错误映射
├── factory.py         # create_gateway_bundle() 工厂函数
├── registry.py        # 自定义券商注册系统
├── ctp_native.py      # CTP 底层 SPI 实现（行情 + 交易）
├── ctp_adapter.py     # CTP 统一适配器（包装 native 层）
├── miniqmt.py         # MiniQMT 网关（内存占位实现）
└── ptrade.py          # PTrade 网关（内存占位实现）
```

### 1.2 支持的券商

| 券商 | 行情 | 交易 | 状态 |
|------|------|------|------|
| CTP (openctp-ctp) | `CTPMarketAdapter` | `CTPTraderAdapter` | 行情 + 下单/撤单/回报主链路已实现；账户/持仓/柜台查询恢复待补 |
| MiniQMT | `MiniQMTMarketGateway` | `MiniQMTTraderGateway` | 内存占位/待对接 |
| PTrade | `PTradeMarketGateway` | `PTradeTraderGateway` | 内存占位/待对接 |
| 自定义 | 通过 registry 注册 | 通过 registry 注册 | 用户扩展 |

---

## 二、统一协议层 (base.py)

### 2.1 MarketGateway Protocol

行情网关协议，定义所有行情源必须实现的方法：

```python
class MarketGateway(Protocol):
    def connect(self) -> None: ...          # 建立行情连接
    def disconnect(self) -> None: ...       # 断开行情连接
    def subscribe(self, symbols: Sequence[str]) -> None: ...   # 订阅合约
    def unsubscribe(self, symbols: Sequence[str]) -> None: ... # 取消订阅
    def on_tick(self, callback: Callable) -> None: ...  # 注册 Tick 回调
    def on_bar(self, callback: Callable) -> None: ...   # 注册 Bar 回调
    def start(self) -> None: ...            # 启动行情事件循环
```

### 2.2 TraderGateway Protocol

交易网关协议，定义所有交易通道必须实现的方法：

```python
class TraderGateway(Protocol):
    def connect(self) -> None: ...          # 建立交易连接
    def disconnect(self) -> None: ...       # 断开交易连接
    def place_order(self, req: UnifiedOrderRequest) -> str: ...       # 下单
    def cancel_order(self, broker_order_id: str) -> None: ...        # 撤单
    def query_order(self, broker_order_id: str) -> UnifiedOrderSnapshot | None: ...
    def query_trades(self, since: int | None = None) -> list[UnifiedTrade]: ...
    def query_account(self) -> UnifiedAccount | None: ...
    def query_positions(self) -> list[UnifiedPosition]: ...
    def on_order(self, callback) -> None: ...           # 订单状态回调
    def on_trade(self, callback) -> None: ...           # 成交回报回调
    def on_execution_report(self, callback) -> None: ... # 执行报告回调
    def sync_open_orders(self) -> list[UnifiedOrderSnapshot]: ...  # 同步未成交单
    def sync_today_trades(self) -> list[UnifiedTrade]: ...         # 同步当日成交
    def heartbeat(self) -> bool: ...       # 心跳检测
    def start(self) -> None: ...            # 启动交易事件循环
```

### 2.3 GatewayBundle

将行情网关和交易网关打包在一起的数据类：

```python
@dataclass
class GatewayBundle:
    market_gateway: MarketGateway              # 行情网关（必需）
    trader_gateway: TraderGateway | None = None # 交易网关（可选，paper 模式可为空）
    metadata: dict[str, Any] | None = None      # 元数据（如 {"broker": "ctp"}）
```

---

## 三、统一数据模型 (models.py)

所有网关共用以下标准化的数据结构：

| 模型 | 用途 | 关键字段 |
|------|------|----------|
| `UnifiedOrderStatus` | 订单生命周期枚举 | `NEW`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED` |
| `UnifiedErrorType` | 错误分类枚举 | `RETRYABLE`, `NON_RETRYABLE`, `RISK_REJECTED` |
| `UnifiedOrderRequest` | 下单请求 | `client_order_id`, `symbol`, `side`, `quantity`, `price`, `order_type`, `time_in_force`, `broker_options` |
| `UnifiedOrderSnapshot` | 订单状态快照 | `client_order_id`, `broker_order_id`, `status`, `filled_quantity`, `avg_fill_price`, `reject_reason` |
| `UnifiedTrade` | 成交记录 | `trade_id`, `broker_order_id`, `symbol`, `side`, `quantity`, `price` |
| `UnifiedExecutionReport` | 执行报告 | `broker_order_id`, `status`, `filled_quantity`, `avg_fill_price` |
| `UnifiedAccount` | 账户快照 | `account_id`, `equity`, `cash`, `available_cash` |
| `UnifiedPosition` | 持仓快照 | `symbol`, `quantity`, `available_quantity`, `avg_price` |

---

## 四、事件映射层 (mapper.py)

`BrokerEventMapper` 负责将各券商特有的状态码和错误信息映射为统一的 `UnifiedOrderStatus` 和 `UnifiedErrorType`。

### 4.1 状态映射

CTP 原始状态码到统一状态的映射关系：

| CTP 状态码 | 含义 | 统一状态 |
|-----------|------|----------|
| `"0"` | 全部成交 | `FILLED` |
| `"1"` | 部分成交还在队列中 | `PARTIALLY_FILLED` |
| `"2"` | 部分成交不在队列中 | `PARTIALLY_FILLED` |
| `"3"` | 未成交还在队列中 | `SUBMITTED` |
| `"4"` | 未成交不在队列中 | `SUBMITTED` |
| `"5"` | 已撤单 | `CANCELLED` |
| `"a"` | 未知 | `SUBMITTED` |
| `"b"` | 未知 | `SUBMITTED` |
| `"c"` | 未知 | `SUBMITTED` |

文本形式的状态同样支持映射（如 `"alltraded"` -> `FILLED`，`"parttradedqueueing"` -> `PARTIALLY_FILLED`）。

### 4.2 错误分类

| 错误类型 | 判定规则 |
|---------|---------|
| `RISK_REJECTED` | 错误码 `"2001"/"2002"/"risk"` 或消息含 `"risk"/"风控"` |
| `RETRYABLE` | 错误码 `"1001"/"1002"/"timeout"/"network"` 或消息含 `"timeout"/"network"/"连接"` |
| `NON_RETRYABLE` | 以上均不匹配时的默认分类 |

---

## 五、工厂与注册系统

### 5.1 工厂函数 (factory.py)

`create_gateway_bundle()` 是创建网关的主入口：

```python
def create_gateway_bundle(
    broker: str,           # "ctp" | "miniqmt" | "ptrade" | 自定义
    feed: DataFeed,        # AKQuant DataFeed 实例
    symbols: Sequence[str],# 合约列表
    use_aggregator: bool = True,  # 是否聚合成1分钟K线
    **kwargs,              # 券商特定参数
) -> GatewayBundle:
```

**解析优先级**：
1. 自定义注册表（`registry.py`）
2. 内置券商（`ctp` → `miniqmt` → `ptrade`）
3. 不匹配则抛出 `ValueError`

### 5.2 注册系统 (registry.py)

支持运行时注册自定义券商实现：

```python
from akquant.gateway import register_broker, unregister_broker, list_registered_brokers

# 注册自定义券商
register_broker("my_broker", lambda **kw: GatewayBundle(...))

# 查看已注册券商
list_registered_brokers()  # 返回 ["my_broker"]

# 注销
unregister_broker("my_broker")
```

---

## 六、CTP 详细实现（以 SimNow 示例配置说明）

CTP（Comprehensive Transaction Platform）是中国期货市场常见的柜台接入方式。本仓库中的 CTP 代码是**通用适配实现**，并未内置任何“华泰期货专属逻辑”；下文只用 SimNow 风格参数说明字段含义。

### 6.1 整体架构

CTP 网关采用**两层架构**：

```
┌──────────────────────────────────────────────────────┐
│                    策略层 (Strategy)                   │
│              on_bar() / on_order() / on_trade()       │
├──────────────────────────────────────────────────────┤
│                 统一适配器层 (Adapter)                  │
│           CTPTraderAdapter / CTPMarketAdapter          │
│     ┌─ execution_semantics_mode (strict/compatible)  ─┐│
│     └─ BrokerEventMapper 统一状态映射                 ─┘│
├──────────────────────────────────────────────────────┤
│                CTP 原生层 (Native SPI)                 │
│          CTPTraderGateway / CTPMarketGateway           │
│     ┌─ 继承 CThostFtdcTraderSpi / CThostFtdcMdSpi  ──┐│
│     └─ 通过 openctp_ctp 库调用 CTP API               ─┘│
├──────────────────────────────────────────────────────┤
│                 CTP 柜台前置机 (Front)                  │
│               tcp://<td-front> (交易前置)               │
│               tcp://<md-front> (行情前置)               │
└──────────────────────────────────────────────────────┘
```

### 6.2 示例 CTP 接入配置

```python
# SimNow 风格示例配置
CTP_CONFIG = {
    "broker": "ctp",
    "md_front": "tcp://<md-front>",        # 行情前置
    "td_front": "tcp://<td-front>",        # 交易前置
    "broker_id": "9999",
    "user_id": "your_user_id",
    "password": "your_password",
    "auth_code": "0000000000000000",
    "app_id": "simnow_client_test",
}
```

> **注意**：`md_front`/`td_front` 并未在代码中写死，具体地址取决于你接入的 CTP 环境。`factory.py` 只要求你显式传入这些参数。

### 6.3 交易连接生命周期

CTP 交易连接经过 4 步握手才能就绪：

```
                 CTPTraderGateway
                       │
    ┌──────────────────┼──────────────────┐
    │                  ▼                  │
    │    ① OnFrontConnected              │
    │       → connected = True            │
    │       → 发送 ReqAuthenticate        │
    │                  │                  │
    │                  ▼                  │
    │    ② OnRspAuthenticate             │
    │       → authenticated = True        │
    │       → 发送 ReqUserLogin           │
    │                  │                  │
    │                  ▼                  │
    │    ③ OnRspUserLogin                │
    │       → login_status = True         │
    │       → 获取 front_id / session_id  │
    │       → 初始化 order_ref            │
    │       → 发送 ReqSettlementInfoConfirm│
    │                  │                  │
    │                  ▼                  │
    │    ④ OnRspSettlementInfoConfirm    │
    │       → ready_to_trade = True       │
    │       ✅ 可以交易                    │
    └─────────────────────────────────────┘
```

**代码对应**（`ctp_native.py`）：

**步骤 1 — 前置连接**（第 233 行）：
```python
def OnFrontConnected(self) -> None:
    self.connected = True
    # 立即发送认证请求
    req = tdapi.CThostFtdcReqAuthenticateField()
    req.BrokerID = self.broker_id
    req.UserID = self.user_id
    req.AppID = self.app_id
    req.AuthCode = self.auth_code
    self.api.ReqAuthenticate(req, self.req_id)
```

**步骤 2 — 认证响应**（第 250 行）：
```python
def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfo, nRequestID, bIsLast):
    if pRspInfo is not None and pRspInfo.ErrorID != 0:
        print(f"Authentication failed: {pRspInfo.ErrorMsg}")
    self.authenticated = True
    # 认证成功后发送登录请求
    req = tdapi.CThostFtdcReqUserLoginField()
    req.BrokerID = self.broker_id
    req.UserID = self.user_id
    req.Password = self.password
    self.api.ReqUserLogin(req, self.req_id)
```

> **当前实现说明**：代码会在打印认证失败日志后继续将 `authenticated=True` 并发送 `ReqUserLogin`。这反映的是当前实现，而不是更严格的生产推荐语义。

**步骤 3 — 登录响应**（第 277 行）：
```python
def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
    self.login_status = True
    self.front_id = int(getattr(pRspUserLogin, "FrontID", 0) or 0)
    self.session_id = int(getattr(pRspUserLogin, "SessionID", 0) or 0)
    # 从 MaxOrderRef 恢复 order_ref，防止 OrderRef 冲突
    max_order_ref = str(getattr(pRspUserLogin, "MaxOrderRef", "")).strip()
    if max_order_ref.isdigit():
        self.order_ref = int(max_order_ref) + 1
    # 确认结算单（必须步骤，否则无法下单）
    req = tdapi.CThostFtdcSettlementInfoConfirmField()
    req.BrokerID = self.broker_id
    req.InvestorID = self.user_id
    self.api.ReqSettlementInfoConfirm(req, self.req_id)
```

**步骤 4 — 结算确认**（第 307 行）：
```python
def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast):
    if pRspInfo is None or pRspInfo.ErrorID == 0:
        self.ready_to_trade = True  # ✅ 交易通道就绪
```

**就绪判断**（第 121 行）：
```python
def can_trade(self) -> bool:
    return self.connected and self.login_status and self.ready_to_trade
```

### 6.4 行情连接生命周期

行情连接比交易简单，关键链路是“登录 + 订阅确认”：

```
    CTPMarketGateway
          │
    ┌─────┼─────┐
    │     ▼     │
    │ ① OnFrontConnected
    │    → connected = True
    │    → 发送 ReqUserLogin（行情无需认证）
    │     │     │
    │     ▼     │
    │ ② OnRspUserLogin
    │    → 登录成功
    │    → SubscribeMarketData(symbols)
    │     │     │
    │     ▼     │
    │ ③ OnRspSubMarketData
    │    → 订阅确认
    │    ✅ 开始接收行情
    └───────────┘
```

### 6.5 下单流程详解

#### 6.5.1 订单标识体系

CTP 使用复合键作为 `broker_order_id`：

```
格式: ctp-{front_id}-{session_id}-{order_ref}[-{order_sys_id}]
示例: ctp-1-12345678-42-000001
       │   │         │  └─ 交易所系统编号（成交回报后才有）
       │   │         └── 本地订单引用（自增）
       │   └──────────── 会话 ID（登录时分配）
       └──────────────── 前置 ID（登录时分配）
```

**对应代码**（`ctp_native.py` 第 445-468 行）：
```python
def _make_broker_order_id(self, *, front_id, session_id, order_ref, order_sys_id):
    base = f"ctp-{front_id}-{session_id}-{order_ref}"
    if order_sys_id:
        return f"{base}-{order_sys_id}"
    return base

def _parse_broker_order_id(self, broker_order_id):
    parts = broker_order_id.split("-")
    if len(parts) < 4 or parts[0] != "ctp":
        return {}
    return {
        "front_id": int(parts[1]),
        "session_id": int(parts[2]),
        "order_ref": parts[3],
        "order_sys_id": "-".join(parts[4:]) if len(parts) > 4 else "",
    }
```

#### 6.5.2 下单请求构建

`insert_order()` 方法（第 125-208 行）将统一订单请求映射为 CTP 字段：

```python
def insert_order(self, *, client_order_id, symbol, side, quantity,
                 price, order_type, time_in_force):
    # 1. 分配 order_ref 并建立映射
    order_ref_text = str(self.order_ref)
    self.order_ref += 1
    self.order_ref_to_client_order_id[order_ref_text] = client_order_id
    self.order_ref_to_symbol[order_ref_text] = symbol

    # 2. 构建 CTP 订单字段
    request = tdapi.CThostFtdcInputOrderField()
    request.BrokerID = self.broker_id
    request.InvestorID = self.user_id
    request.InstrumentID = symbol
    request.OrderRef = order_ref_text

    # 3. 方向映射
    request.Direction = (
        tdapi.THOST_FTDC_D_Buy if side.lower() == "buy"
        else tdapi.THOST_FTDC_D_Sell
    )

    # 4. 开仓标志（默认投机开仓）
    request.CombOffsetFlag = tdapi.THOST_FTDC_OF_Open
    request.CombHedgeFlag = tdapi.THOST_FTDC_HF_Speculation

    # 5. 订单类型与有效期映射
    if order_type == "market":
        request.OrderPriceType = tdapi.THOST_FTDC_OPT_AnyPrice  # 市价
        request.LimitPrice = 0.0
        request.TimeCondition = tdapi.THOST_FTDC_TC_IOC         # 立即成交否则取消
        request.VolumeCondition = tdapi.THOST_FTDC_VC_AV         # 任意数量
    else:
        request.OrderPriceType = tdapi.THOST_FTDC_OPT_LimitPrice # 限价
        request.LimitPrice = float(price)
        if time_in_force in {"IOC", "FAK", "FOK"}:
            request.TimeCondition = tdapi.THOST_FTDC_TC_IOC
            request.VolumeCondition = (
                tdapi.THOST_FTDC_VC_CV if time_in_force == "FOK"  # 全部数量
                else tdapi.THOST_FTDC_VC_AV                        # 任意数量
            )
        else:
            request.TimeCondition = tdapi.THOST_FTDC_TC_GFD  # 当日有效
            request.VolumeCondition = tdapi.THOST_FTDC_VC_AV

    # 6. 发送请求
    ret = self.api.ReqOrderInsert(request, self.req_id)
    if ret != 0:
        # 失败时清理映射
        self.order_ref_to_client_order_id.pop(order_ref_text, None)
        self.order_ref_to_symbol.pop(order_ref_text, None)
        raise RuntimeError(f"ReqOrderInsert failed with code={ret}")

    return {"broker_order_id": ..., "order_ref": order_ref_text, ...}
```

#### 6.5.3 订单类型映射总结

| 策略层 order_type | CTP OrderPriceType | CTP TimeCondition | CTP VolumeCondition | 说明 |
|------------------|-------------------|-------------------|---------------------|------|
| `"market"` | OPT_AnyPrice | TC_IOC | VC_AV | 市价单，立即成交否则取消 |
| `"limit"` + GTC/GFD | OPT_LimitPrice | TC_GFD | VC_AV | 限价单，当日有效 |
| `"limit"` + IOC/FAK | OPT_LimitPrice | TC_IOC | VC_AV | 限价单，立即成交否则取消，可部分成交 |
| `"limit"` + FOK | OPT_LimitPrice | TC_IOC | VC_CV | 限价单，全部成交否则取消 |

### 6.6 撤单流程

`cancel_order()` 方法（第 210-231 行）通过解析 `broker_order_id` 获取必要字段：

```python
def cancel_order(self, broker_order_id: str):
    parsed = self._parse_broker_order_id(broker_order_id)
    order_ref = parsed.get("order_ref", "")

    request = tdapi.CThostFtdcInputOrderActionField()
    request.BrokerID = self.broker_id
    request.InvestorID = self.user_id
    request.OrderRef = order_ref
    request.FrontID = int(parsed.get("front_id", self.front_id))
    request.SessionID = int(parsed.get("session_id", self.session_id))
    request.ActionFlag = tdapi.THOST_FTDC_AF_Delete  # 删除操作
    request.InstrumentID = self.order_ref_to_symbol.get(order_ref, "")

    ret = self.api.ReqOrderAction(request, self.req_id)
    if ret != 0:
        raise RuntimeError(f"ReqOrderAction failed with code={ret}")
```

### 6.7 事件回调机制

CTP 回调在 CTP 自己的守护线程中触发，通过注册的 handler 将事件传递给适配器层。

#### 6.7.1 订单状态回报 (OnRtnOrder)

```python
def OnRtnOrder(self, pOrder):
    payload = {
        "client_order_id": self.order_ref_to_client_order_id.get(order_ref, ""),
        "broker_order_id": self._make_broker_order_id(...),
        "symbol": self._to_text(pOrder.InstrumentID),
        "status": self._map_order_status(pOrder.OrderStatus),  # "0"→"filled" 等
        "filled_quantity": float(pOrder.VolumeTraded),
        "avg_fill_price": float(pOrder.LimitPrice),
        "reject_reason": self._to_text(pOrder.StatusMsg),
        "timestamp_ns": time.time_ns(),
        "order_ref": order_ref,
    }
    if self.order_callback:
        self.order_callback(payload)  # → 传递给 CTPTraderAdapter._handle_native_order_event
```

#### 6.7.2 成交回报 (OnRtnTrade)

```python
def OnRtnTrade(self, pTrade):
    payload = {
        "trade_id": self._to_text(pTrade.TradeID),
        "broker_order_id": self._make_broker_order_id(...),
        "client_order_id": self.order_ref_to_client_order_id.get(order_ref, ""),
        "symbol": self._to_text(pTrade.InstrumentID),
        "side": self._map_direction(pTrade.Direction),  # "0"→"Buy", "1"→"Sell"
        "quantity": float(pTrade.Volume),
        "price": float(pTrade.Price),
        "timestamp_ns": time.time_ns(),
    }
    if self.trade_callback:
        self.trade_callback(payload)  # → 传递给 CTPTraderAdapter._handle_native_trade_event
```

#### 6.7.3 拒单处理 (OnRspOrderInsert / OnErrRtnOrderInsert)

两种拒单场景均调用 `_emit_rejected_order()`：

- **OnRspOrderInsert**（第 329 行）：同步拒单响应（如参数校验失败）
- **OnErrRtnOrderInsert**（第 342 行）：异步拒单回报（如交易所风控拒绝）

### 6.8 统一适配器层 (CTPTraderAdapter)

`CTPTraderAdapter` 包装 `CTPTraderGateway`，提供统一协议接口，并增加执行语义控制。

#### 6.8.1 执行语义模式

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `"strict"` (默认) | 错误事件仅存储 reject_reason，等 CTP OnRtnOrder 回调时再应用 | 精确跟踪状态，适合正式交易 |
| `"compatible"` | 错误事件立即触发 rejected 状态 | 兼容性更好，适合测试环境 |

**strict 模式下的事件流**：
```
CTP OnErrRtnOrderInsert (拒单)
    → _handle_native_error_event
    → pending_reject_reasons[broker_order_id] = error_message  (仅存储)

CTP OnRtnOrder (订单回报)
    → _handle_native_order_event
    → 检查 pending_reject_reasons
    → 将 reject_reason 注入 payload
    → ingest_order_event (正式更新状态)
```

#### 6.8.2 订单生命周期管理

```
place_order()
    ├─ 检查 client_order_id 幂等性（活跃单返回已有 broker_order_id）
    ├─ 检查心跳 (heartbeat)
    ├─ 调用 native gateway.insert_order()
    ├─ 创建 UnifiedOrderSnapshot (SUBMITTED)
    ├─ 建立 client↔broker 映射
    ├─ 发射 order callback
    └─ 发射 execution_report callback

cancel_order()
    ├─ 调用 native gateway.cancel_order()
    ├─ [compatible 模式] 立即发射 CANCELLED 状态
    └─ [strict 模式] 等待 OnRtnOrder 回调

ingest_order_event() (被 native 回调调用)
    ├─ mapper.map_order_event() → UnifiedOrderSnapshot
    ├─ 更新 orders 字典
    ├─ 同步映射关系
    ├─ 发射 order callback
    ├─ 发射 execution_report
    └─ 终态订单清理映射
```

#### 6.8.3 映射关系管理

三种映射字典协同工作：

```python
client_to_broker_order_ids: dict[str, str]    # client_order_id → broker_order_id
broker_to_client_order_ids: dict[str, str]    # broker_order_id → client_order_id
order_ref_to_client_order_ids: dict[str, str] # CTP order_ref → client_order_id
```

终态订单（`FILLED`/`CANCELLED`/`REJECTED`）触发 `_cleanup_terminal_order_mapping()` 自动清理映射，防止内存泄漏。

#### 6.8.4 当前能力边界

以下能力在当前仓库里**尚未补成真实 broker 查询**：

| 方法 | 当前实现 | 说明 |
|------|----------|------|
| `query_account()` | 返回 `None` | 尚未接 CTP 资金查询 |
| `query_positions()` | 返回 `[]` | 尚未接 CTP 持仓查询 |
| `sync_open_orders()` | 返回适配器内存中的未终态订单 | 不是向柜台重查 |
| `sync_today_trades()` | 返回 `[]` | 尚未接 CTP 当日成交查询 |
| `heartbeat()` | 调用 `gateway.can_trade()` 或 `connected` | 只能反映当前连接就绪状态 |

### 6.9 行情数据处理 (CTPMarketGateway)

`OnRtnDepthMarketData`（第 621 行）处理两种模式：

**聚合模式**（`use_aggregator=True`，默认）：
```
CTP Tick → BarAggregator.on_tick(symbol, price, volume, ts)
         → 积累到 1 分钟后生成 Bar
         → feed.add_bar(bar)
```

**逐笔模式**（`use_aggregator=False`）：
```
CTP Tick → 计算 delta_volume
         → 创建单 Tick Bar (OHLC = price)
         → feed.add_bar(bar)
```

价格过滤：`price > 1e7` 或 `price <= 0` 的无效 Tick 被丢弃。

### 6.10 `broker_live` 下的线程模型

以下线程模型来自 `LiveRunner + CTP + trading_mode="broker_live"` 的组合路径，其中前两个线程属于 CTP 网关，后两个线程属于 `LiveRunner` 的通用 broker bridge：

```
┌─ Main Thread ─────────────────────────────────────────┐
│  LiveRunner.run()                                      │
│    └─ engine.run(strategy)  ← 阻塞，运行策略事件循环    │
├─ Daemon: "ctp-market" ────────────────────────────────┤
│  CTPMarketGateway.start()                              │
│    └─ api.Init() + api.Join()  ← 阻塞                 │
│        └─ OnRtnDepthMarketData 在此线程触发             │
├─ Daemon: "ctp-trader" ────────────────────────────────┤
│  CTPTraderGateway.start()                              │
│    └─ api.Init() + api.Join()  ← 阻塞                 │
│        └─ OnRtnOrder / OnRtnTrade 在此线程触发          │
├─ Daemon: "ctp-broker-dispatch" ───────────────────────┤
│  _broker_dispatch_loop()                               │
│    └─ 每 50ms 轮询事件队列，分发到策略回调               │
├─ Daemon: "ctp-broker-recovery" ───────────────────────┤
│  _broker_recovery_loop()                               │
│    └─ 每 1s 执行心跳检测 + 订单同步                     │
└────────────────────────────────────────────────────────┘
```

**线程安全**：CTP SPI 回调运行在 CTP 线程中；`LiveRunner` 通过 `_broker_event_lock` 保护的队列缓存事件，dispatch 线程从队列中取事件并分发到策略。策略的 `on_order`/`on_trade`/`on_execution_report` 运行在 dispatch 线程，不直接运行在 CTP SPI 线程。

### 6.11 心跳与重连

| 层级 | 机制 | 当前代码行为 |
|------|------|---------------|
| Native CTP 回调 | `OnFrontDisconnected` / `OnFrontConnected` | 维护 `connected/login_status/ready_to_trade` 等状态 |
| 状态追踪 | `can_trade()` | 检查 `connected AND login_status AND ready_to_trade` |
| LiveRunner | `_broker_recovery_loop` | 每 1s 调用 `heartbeat()`；失败时尝试 `connect()`，然后调用 `sync_open_orders()` / `sync_today_trades()` |
| 恢复同步 | `sync_open_orders()` | 当前仅回放适配器内存中的未终态订单 |
| 成交同步 | `sync_today_trades()` | 当前未实现真实 broker 查询，直接返回空列表 |

> **不要把当前实现理解为“完整的 broker 侧恢复”**。仓库中尚未实现 CTP 账户/持仓/当日成交/未结订单的柜台查询与对账恢复。

### 6.12 事件去重

LiveRunner 使用事件键进行去重：

```python
# 成交事件键
"trade:{trade_id}"

# 订单事件键
"order:{broker_order_id}:{status}:{filled_quantity}:{timestamp_ns}"

# 执行报告键
"execution_report:{broker_order_id}:{status}:{timestamp_ns}"
```

相同键的事件被忽略，防止网络抖动导致的重复处理。

### 6.13 完整使用示例

```python
from akquant import AssetType, Bar, Instrument, Strategy
from akquant.live import LiveRunner

class MyStrategy(Strategy):
    def on_bar(self, bar: Bar):
        pos = self.get_position(bar.symbol)
        if pos == 0:
            self.buy(bar.symbol, 1)
        elif pos > 0:
            self.sell(bar.symbol, 1)

    def on_order(self, order):
        print(f"订单更新: {order.symbol} {order.status}")

    def on_trade(self, trade):
        print(f"成交回报: {trade.symbol} {trade.side} {trade.quantity}@{trade.price}")

# 定义合约
instruments = [
    Instrument(
        symbol="au2606",
        asset_type=AssetType.Futures,
        multiplier=1000.0,
        margin_ratio=0.1,
        tick_size=0.02,
        lot_size=1,
    ),
]

# 创建并运行 (paper 模式，仅连接行情)
runner = LiveRunner(
    strategy_cls=MyStrategy,
    instruments=instruments,
    broker="ctp",
    md_front="tcp://180.168.146.187:10111",
    use_aggregator=True,    # 1分钟K线聚合
    trading_mode="paper",   # 模拟撮合
)
runner.run(cash=1_000_000, duration="1h")

# 实盘模式（broker_live）
runner_live = LiveRunner(
    strategy_cls=MyStrategy,
    instruments=instruments,
    broker="ctp",
    md_front="tcp://180.168.146.187:10111",
    td_front="tcp://180.168.146.187:10131",
    broker_id="9999",
    user_id="your_account",
    password="your_password",
    trading_mode="broker_live",  # 真实报单
)
runner_live.run(cash=1_000_000)
```

### 6.14 策略回测/实盘无感切换

策略通过 `trading_mode` 参数实现回测与实盘的切换，策略代码完全不变：

```python
# LiveRunner 内部切换逻辑
if self.trading_mode == "broker_live":
    self.engine.use_realtime_execution()   # 实盘：订单发往券商
else:
    self.engine.use_simulated_execution()  # 模拟：订单由引擎内部撮合
```

- **paper 模式**：只启动行情网关，订单由 Rust 引擎的模拟撮合器处理
- **broker_live 模式**：同时启动行情和交易网关，订单发往 CTP 前置

---

## 七、MiniQMT 与 PTrade 占位实现

MiniQMT 和 PTrade 目前为内存中的占位实现。它们实现了统一 `TraderGateway` 契约和本地事件注入口，但**并没有像 CTP 那样拆成 Native + Adapter 两层**。详见独立的 MiniQMT 文档。

---

## 八、总结

| 维度 | 设计决策 |
|------|----------|
| **架构模式** | 统一协议 + 券商适配器，策略与券商解耦 |
| **CTP 实现** | 两层架构：Native SPI + 统一 Adapter |
| **线程模型** | `broker_live` 下由 CTP 线程 + LiveRunner broker bridge 线程协同 |
| **可靠性** | 已有心跳检测、事件去重和本地状态回放；broker 侧查询恢复仍待补 |
| **执行语义** | strict（精确）/ compatible（兼容）两种模式 |
| **扩展性** | registry 注册系统支持运行时添加自定义券商 |

### broker_live 参数边界

`broker_live` 模式下的 `submit_order` 支持以下参数：

| 参数 | 状态 |
|------|------|
| `symbol`, `side`, `quantity`, `price` | ✅ 透传至 `UnifiedOrderRequest` |
| `order_type` | ✅ 仅支持 `Market` / `Limit`，其余 raise RuntimeError |
| `time_in_force` | ✅ 透传 |
| `broker_options` | ✅ 透传至 `UnifiedOrderRequest.broker_options` |
| `client_order_id` | ✅ 自动生成或透传 |
| `extra` | ❌ fail-closed，raise RuntimeError |
| `trigger_price` | ❌ fail-closed，raise RuntimeError |
| `trail_offset` / `trail_reference_price` | ❌ fail-closed，raise RuntimeError |
| `fill_policy` / `slippage` / `commission` | ❌ fail-closed，raise RuntimeError |

市场模型根据 `GatewayBundle.metadata["asset_class"]` 自动选择：`stock` → `use_china_market()`，`futures` → `use_china_futures_market()`。
| **切换成本** | `trading_mode` 一行切换回测/模拟/实盘 |
