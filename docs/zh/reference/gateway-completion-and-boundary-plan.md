# akquant Gateway 功能补全与 miniQMT 边界分割 — 实施方案

> 状态：待审核（v2，根据审核反馈修正）
> 日期：2026-04-30

---

## 背景

akquant gateway 层存在三个功能缺口，同时需要为 miniQMT 桥接层未来迁出做准备：

1. **市场模型硬编码为期货** — `LiveRunner.run()` 第 232 行无条件调用 `use_china_futures_market()`，股票类 broker（miniqmt、ptrade）错误使用 T+0 规则
2. **broker_live 注入的 `submit_order` 签名与基类不一致** — 基类有 `broker_options` 参数（`strategy.py:1680`，`strategy_trading_api.py:429`），但 `live.py:638` 注入的闭包只有 `extra`，缺少 `broker_options`。策略按文档传 `broker_options=` 在 broker_live 下会直接 TypeError
3. **miniQMT 桥接边界未标记** — `miniqmt_xtquant.py` 无任何迁移提示，`factory.py` 未准备 `bridge_url` 入口

本次修改不涉及 miniQMT 功能迁移（依赖 miniQMT Phase A 完成），只做 akquant 侧的功能补全和边界标记。

---

## Change 1: 市场模型选择 — 根据 broker 的 asset_class 自动匹配

### 问题

`python/akquant/live.py` 第 232-233 行：

```python
self.engine.use_china_futures_market()
self.engine.set_force_session_continuous(True)
```

无条件使用期货市场模型（T+0），股票类 broker（miniqmt、ptrade）应使用 `use_china_market()`（T+1、印花税、过户费、交易时段）。

Engine 提供三种市场模型：
- `use_simple_market(commission_rate)` — 24/7、T+0、无税
- `use_china_market()` — T+1/T+0、印花税、过户费、交易时段
- `use_china_futures_market()` — ChinaMarket + T+0

### 方案

#### 1.1 `factory.py` — 每个 broker 的 metadata 增加 `asset_class`

```python
# ctp 分支
return GatewayBundle(
    market_gateway=market_gateway,
    trader_gateway=trader_gateway,
    metadata={"broker": "ctp", "asset_class": "futures"},
)

# miniqmt 分支
return GatewayBundle(
    market_gateway=market_gateway,
    trader_gateway=miniqmt_trader_gateway,
    metadata={"broker": "miniqmt", "asset_class": "stock"},
)

# ptrade 分支
return GatewayBundle(
    market_gateway=market_gateway,
    trader_gateway=ptrade_trader_gateway,
    metadata={"broker": "ptrade", "asset_class": "stock"},
)
```

自定义注册的 broker 不含 `asset_class`，走默认值 `"futures"`。

#### 1.2 `live.py` — 替换硬编码为 `_select_market_model(bundle)` 方法

新增方法：

```python
def _select_market_model(self, bundle: GatewayBundle) -> None:
    asset_class = (bundle.metadata or {}).get("asset_class", "futures")
    if asset_class == "stock":
        self.engine.use_china_market()
    else:
        self.engine.use_china_futures_market()
    self.engine.set_force_session_continuous(True)
```

**位置调整**：当前硬编码在第 232 行（bundle 在第 237 行才创建），需要将 `_select_market_model` 调用移到 `create_gateway_bundle()` 之后：

```python
# 删除第 232-233 行的硬编码
bundle = create_gateway_bundle(...)
self._select_market_model(bundle)    # 新增：在 bundle 创建之后调用
```

#### 1.3 新增测试

**`tests/test_gateway_factory.py`**（3 个）：
- `test_factory_sets_futures_asset_class_for_ctp` — 验证 ctp metadata
- `test_factory_sets_stock_asset_class_for_miniqmt` — 验证 miniqmt metadata
- `test_factory_sets_stock_asset_class_for_ptrade` — 验证 ptrade metadata

**`tests/test_live_runner_broker_bridge.py`** — 新增 `TestMarketModelSelection` 类（3 个）：
- `test_selects_china_market_for_stock_broker` — mock engine，验证 `use_china_market()` 被调用
- `test_selects_china_futures_market_for_futures_broker` — 验证 `use_china_futures_market()` 被调用
- `test_defaults_to_futures_when_asset_class_missing` — metadata 无 asset_class，验证默认期货

#### 1.4 影响范围

- `factory.py`：3 行 metadata 改动
- `live.py`：新增 1 个方法（约 6 行），删除 2 行硬编码，新增 1 行调用
- 测试：新增 6 个测试

---

## Change 2: 对齐 `submit_order` 契约，支持 `broker_options`，未支持参数保持 fail-closed

### 问题

**签名不对齐**：

| 参数 | 基类 `Strategy.submit_order`（`strategy.py:1668`） | 注入的 `_submit_order`（`live.py:638`） |
|---|---|---|
| `broker_options` | 有（第 1680 行） | **无** |
| `trail_offset` | 有（第 1681 行） | 无（`_ = trigger_price` 丢弃） |
| `trail_reference_price` | 有（第 1682 行） | 无 |
| `fill_policy` | 有（第 1683 行） | 无 |
| `slippage` | 有（第 1684 行） | 无 |
| `commission` | 有（第 1685 行） | 无 |

策略按文档 API 调用 `submit_order(broker_options={...})`、`submit_order(slippage={...})`、`submit_order(commission={...})` 等公开参数时，在 broker_live 模式下会因注入函数缺少这些参数而直接 TypeError。

**`UnifiedOrderRequest` 缺少对应字段**：模型类没有 `broker_options` 字段，无法承载 broker 专有参数。

**当前 `extra` 本来就不支持**：
```python
# strategy_trading_api.py:440-442
if extra:
    raise RuntimeError(
        "extra broker fields are not supported in current execution mode"
    )
```

也就是说，本次变更的目标是补齐 `broker_options` 契约，不是把 `extra` 扩展成可用通道。

**不能把未实现能力改成静默忽略**：当前各 broker gateway 真正下游实现的仍主要是 `Market/Limit + price + time_in_force` 这一层。`trigger_price`、跟踪单、`fill_policy`、`slippage`、`commission` 如果只是“签名接受但内部丢弃”，会把当前显式失败变成静默语义漂移，风险更高。

### 方案

#### 2.1 `models.py` — `UnifiedOrderRequest` 增加 `broker_options` 字段

```python
from dataclasses import dataclass
from typing import Any            # 新增导入
from enum import Enum

@dataclass
class UnifiedOrderRequest:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = "Market"
    time_in_force: str = "GTC"
    broker_options: dict[str, Any] | None = None    # 新增：与公开 API 对齐
```

使用 `broker_options` 而非 `extra`，与基类 `Strategy.submit_order` 签名和文档主契约一致。默认值为 `None`，不破坏任何现有构造。

#### 2.2 `live.py` — 对齐注入签名，只透传 `broker_options`，其余未支持参数显式拒绝

修改 `_install_broker_order_submitter` 中的 `_submit_order` 闭包：

```python
def _submit_order(
    symbol: str,
    side: str,
    quantity: float,
    price: float | None = None,
    client_order_id: str | None = None,
    order_type: str = "Market",
    time_in_force: str = "GTC",
    trigger_price: float | None = None,
    tag: str | None = None,
    extra: dict[str, Any] | None = None,
    broker_options: dict[str, Any] | None = None,   # 新增：与基类对齐
    trail_offset: float | None = None,               # 新增
    trail_reference_price: float | None = None,      # 新增
    fill_policy: Any | None = None,                   # 新增
    slippage: Any | None = None,                      # 新增
    commission: Any | None = None,                    # 新增
) -> str:
    _ = tag
    if extra:
        raise RuntimeError(
            "extra broker fields are not supported in current broker_live mode"
        )
    if trigger_price is not None:
        raise RuntimeError(
            "trigger_price is not supported in current broker_live mode"
        )
    if trail_offset is not None or trail_reference_price is not None:
        raise RuntimeError(
            "trailing orders are not supported in current broker_live mode"
        )
    if fill_policy is not None or slippage is not None or commission is not None:
        raise RuntimeError(
            "fill_policy/slippage/commission are not supported in current broker_live mode"
        )
    if str(order_type).strip().lower() not in {"market", "limit"}:
        raise RuntimeError(
            "current broker_live gateways support only Market and Limit orders"
        )

    request_client_order_id = client_order_id or self._next_client_order_id()
    ...
    request = UnifiedOrderRequest(
        client_order_id=request_client_order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
        time_in_force=time_in_force,
        broker_options=broker_options,    # 透传
    )
    ...
```

关键变更：
1. 新增 `broker_options`、`trail_offset`、`trail_reference_price`、`fill_policy`、`slippage`、`commission` 参数，避免公开 API 参数在 broker_live 下直接 TypeError
2. `broker_options` 是本次唯一新增透传到 `UnifiedOrderRequest` 的 broker 扩展字段
3. `extra` 继续显式拒绝，与共享 `strategy_trading_api.submit_order()` 的现状保持一致
4. `trigger_price`、跟踪单参数、`fill_policy`、`slippage`、`commission` 在当前 broker_live 中继续 fail-closed，返回清晰 RuntimeError，而不是静默忽略
5. `order_type` 明确限制为当前 gateway 真正支持的 `Market` / `Limit`，避免 `StopTrail` 等值被下游误当成普通限价单

#### 2.3 `miniqmt.py` — bridge 调用透传 broker_options

```python
# place_order() 中 bridge 调用
native_id = self._bridge.place_native_order(
    symbol=req.symbol,
    side=req.side,
    quantity=req.quantity,
    price=req.price,
    order_type=req.order_type,
    broker_options=req.broker_options,    # 新增
)
```

#### 2.4 `miniqmt_xtquant.py` — 签名增加 broker_options 参数

```python
def place_native_order(
    self,
    *,
    symbol: str,
    side: str,
    quantity: float,
    price: float | None,
    order_type: str,
    broker_options: dict[str, Any] | None = None,    # 新增，内部忽略
) -> int:
```

CTP、PTrade gateway 的 `place_order()` 接收含 `broker_options` 的 `UnifiedOrderRequest` 但不使用，无需改动。

#### 2.5 新增测试

**`tests/test_live_runner_broker_bridge.py`**（5 个）：
- `test_live_runner_submitter_accepts_broker_options` — 验证 `submit_order(broker_options={...})` 不再 TypeError
- `test_live_runner_submitter_passes_broker_options_to_gateway` — 验证 `broker_options` 到达 trader gateway
- `test_live_runner_submitter_rejects_extra_like_shared_api` — 验证 `extra` 继续显式拒绝，而不是静默接受
- `test_live_runner_submitter_rejects_unsupported_advanced_params` — 验证 `trigger_price` / `trail_offset` / `fill_policy` / `slippage` / `commission` 走清晰 RuntimeError，而不是 TypeError 或 silent drop
- `test_live_runner_submitter_rejects_unsupported_order_type` — 验证 `StopTrail` 等未实现类型不会被误下成普通限价单

**`tests/test_gateway_miniqmt_xtquant.py`**：
- 更新 `test_place_order_routes_through_bridge` 传入 `broker_options` 并验证传递

#### 2.6 影响范围

- `models.py`：新增 1 行导入 + 1 行字段
- `live.py`：注入闭包增加 6 个参数 + 新增显式校验分支 + 修改 2 行构造
- `miniqmt.py`：修改 1 行
- `miniqmt_xtquant.py`：修改 1 行签名
- `docs/zh/reference/gateway_system.md`：同步补充 `UnifiedOrderRequest.broker_options` 字段说明
- 测试：新增 5 个 + 修改 1 个

---

## Change 3: 标记 miniQMT 桥接迁移边界

### 问题

`miniqmt_xtquant.py` 包含 xtquant SDK 直连代码，按转移方案应迁至 miniQMT 独立项目，但当前无任何标记。`factory.py` 也未准备 `bridge_url` 入口。

### 方案

#### 3.1 `miniqmt_xtquant.py` — 构造时发 FutureWarning（非模块级）

不在模块级发 warning（原因：`from __future__ import annotations` 必须在文件最前面，且模块缓存命中后 warning 不稳定）。改为在 `QMTXtQuantBridge.__init__()` 中发 `FutureWarning`：

```python
import warnings

class QMTXtQuantBridge:
    def __init__(self, qmt_path: str, account_id: str, gateway: Any) -> None:
        if not HAS_XTQUANT:
            raise ImportError(...)
        warnings.warn(
            "QMTXtQuantBridge is scheduled for migration to the miniQMT project. "
            "Once miniQMT Phase A is complete, this module will be replaced by an "
            "HTTP bridge client. See docs/zh/reference/miniqmt-bridge-transfer-plan.md.",
            FutureWarning,
            stacklevel=2,
        )
        self.gateway = gateway
        ...
```

使用 `FutureWarning`（而非 `DeprecationWarning`）的原因：`DeprecationWarning` 默认被 Python 过滤，用户看不到。`FutureWarning` 默认显示，更适合主动通知。

同时更新模块 docstring 标注迁移计划。

#### 3.2 `factory.py` — miniqmt 分支增加 `bridge_url` 守卫

```python
if broker_key == "miniqmt":
    # Future: HTTP bridge mode (requires miniQMT Phase A)
    bridge_url = kwargs.get("bridge_url")
    if bridge_url:
        raise NotImplementedError(
            "HTTP bridge mode is not yet available. "
            "Complete miniQMT Phase A first. "
            "See docs/zh/reference/miniqmt-bridge-transfer-plan.md"
        )

    # Current: direct xtquant mode (or in-memory)
    market_gateway = MiniQMTMarketGateway(...)
    ...
```

检测到 `bridge_url` 参数时 raise `NotImplementedError`，明确告知用户需要等 miniQMT Phase A。现有 `qmt_path` 直连模式不受影响。

#### 3.3 新增测试

**`tests/test_gateway_miniqmt_xtquant.py`**（1 个）：
- `test_bridge_construction_emits_future_warning` — 构造 `QMTXtQuantBridge`（需 xtquant 可用时）时验证 `FutureWarning`。若 xtquant 不可用则跳过（`pytest.mark.skipif(not HAS_XTQUANT)`）

**`tests/test_gateway_factory.py`**（1 个）：
- `test_miniqmt_bridge_url_raises_not_implemented` — 传入 `bridge_url` 验证 `NotImplementedError`

#### 3.4 影响范围

- `miniqmt_xtquant.py`：修改 docstring + `__init__` 中新增 3 行 warning
- `factory.py`：新增 5 行 bridge_url 守卫
- 测试：新增 2 个

---

## Commit 顺序

| # | 标题 | 核心文件 |
|---|------|---------|
| 1 | `feat(live): select market model based on broker asset_class` | factory.py, live.py, test_gateway_factory.py, test_live_runner_broker_bridge.py |
| 2 | `feat(gateway): align broker_live submit_order contract, add broker_options` | models.py, live.py, miniqmt.py, miniqmt_xtquant.py, docs, tests |
| 3 | `feat(gateway): mark miniqmt_xtquant for migration, add bridge_url guard` | miniqmt_xtquant.py, factory.py, tests |

每次提交后均运行全量测试确认通过。

---

## 验证方式

```bash
uv run pytest tests/test_gateway_factory.py tests/test_live_runner_broker_bridge.py tests/test_gateway_miniqmt_xtquant.py tests/test_gateway_mapper.py tests/test_gateway_callbacks.py tests/test_gateway_registry.py tests/test_gateway_ctp_adapter.py -v
uv run ruff check python/akquant/gateway/ python/akquant/live.py tests/
```

---

## 不在本次范围内

- MiniQMTMarketGateway 的实际行情桥接（仍为占位实现）
- `miniqmt_xtquant.py` 的实际迁移（依赖 miniQMT Phase A 完成）
- `LiveRunner.run()` 的 end-to-end 集成测试
- CTP gateway 的 `query_account()` / `query_positions()` 实现
- `extra` 的语义扩展：本次仍保持“不支持”，只补齐 `broker_options` 作为 broker 扩展参数通道
- `trigger_price`、跟踪单、`fill_policy`、`slippage`、`commission` 的 broker_live 真实落地：本次仅补齐签名并改为显式拒绝，不扩展底层 gateway 能力
