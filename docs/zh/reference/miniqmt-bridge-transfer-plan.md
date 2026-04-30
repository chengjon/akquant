# MiniQMT 桥接层抽离转移方案

> 状态：待审核
> 日期：2026-04-30
> 背景：akquant 当前内嵌了 xtquant SDK 直连代码（`miniqmt_xtquant.py`），应将 SDK 交互层转移到 miniQMT 独立项目，akquant 仅通过 HTTP API 对接。需要特别注意：miniQMT 内部以 `/api/v1/task/*` 为 canonical contract，但 akquant 侧仍要求稳定的 broker-facing 提交/查询语义，不能只做“SDK 调用方式替换”。

---

## 1. 现状

### akquant 当前结构

```
python/akquant/gateway/
├── miniqmt.py              # MiniQMTTraderGateway（统一协议层）
├── miniqmt_xtquant.py      # QMTXtQuantBridge（直接调用 xtquant SDK）
└── factory.py              # 工厂，根据 qmt_path 参数创建桥接
```

- `QMTXtQuantBridge` 直接 `import xtquant`，调用 `xttrader.order_stock()` 等原生 API
- 仅在 Windows + QMT 客户端安装环境下可用
- akquant 运行环境通常是 Linux，与 xtquant SDK 的 Windows 依赖冲突

### miniQMT 当前结构

```
miniQMT/bridge/
├── app/
│   ├── main.py             # 当前应用入口（仍承载 Settings/TaskStore/QmtService）
│   ├── models.py           # HTTP contract models
│   └── routes/
│       ├── capabilities.py
│       ├── health.py
│       ├── qmt.py          # legacy broker facade
│       └── task.py         # canonical task contract
└── pyproject.toml
```

- miniQMT 定位：Windows 上运行的 HTTP bridge 服务，封装 xtquant SDK 对外暴露 REST API
- 当前 bridge 代码仍以**内存 TaskStore + 模拟 QmtService** 为主，`qmt.py` 与 `task.py` 已拆分，但还没有完成 SQLite WAL + `TaskService` / `qmt_service.py` 的计划结构
- v1 计划（Phase A）：`task/execute` + `task/result` contract kernel + SQLite 持久化
- Phase B：原生 xtquant callback → task result 映射

### 两者重叠

核心重叠点是 **xtquant SDK 的直接调用逻辑**，但跨项目转移时还必须保留以下契约：

- akquant `place_order()` 仍需同步拿到稳定的提交标识，并建立 `client_order_id ↔ broker_order_id`
- query / recovery 语义不能退化成“只有 task receipt，没有 broker-facing 查询闭环”
- 符号格式、native order id、回调映射的职责边界要在 HTTP 边界重新定义

---

## 2. 转移方案

### 2.1 转移到 miniQMT 的内容

以下 akquant `miniqmt_xtquant.py` 中的逻辑，应被 miniQMT 的 `qmt_service.py` Phase A/B 吸收：

| akquant 当前代码 | miniQMT 对应位置 | 说明 |
|---|---|---|
| `_get_xttrader()` 懒导入 | `qmt_service.py` 的 `connect()` | miniQMT 已规划 connect + 平台检查 |
| `STATUS_MAP`（xtconstant 映射） | `qmt_service.py` | Phase B 回调映射需要此表 |
| `format_symbol` / `strip_symbol` | `qmt_service.py` 的 `normalize_symbol_*` | 注意符号格式差异（见 2.3） |
| `place_native_order()` | `qmt_service.py` 的 `submit_order()` | miniQMT 已规划此 seam |
| `cancel_native_order()` | `qmt_service.py` | Phase B 扩展 |
| `query_account()` / `query_positions()` | `qmt_service.py` 的 `query_assets()` / `query_positions()` | miniQMT 已规划 |
| `_QMTCallback` 回调类 | miniQMT Phase B | 原生 xtquant callback → task result 映射 |
| `heartbeat()` | `qmt_service.py` 的 `heartbeat()` | miniQMT 已规划 |

### 2.2 akquant 侧的改动

`QMTXtQuantBridge` 从 **xtquant 直连模式** 改为 **miniQMT HTTP 客户端模式**。但改造后的 bridge 仍需满足 akquant 现有 `MiniQMTTraderGateway` 的同步契约：`place_native_order()` 不能只返回“task 已受理”，还必须返回一个可立即绑定的稳定 broker/native order id。

miniQMT 内部应继续以 `/api/v1/task/*` 为 canonical path；但对 akquant 侧，建议优先保留 `/api/v1/broker/qmt/orders*` compatibility facade，并由该 facade 委派到 task core，再同步返回稳定的 `native_order_id`（或一个可无损还原为 native id 的字段）。否则，akquant bridge 需要在 `place_native_order()` 内部自行执行“`task/execute` + 轮询 `task/result` 直到拿到可绑定 identity”的逻辑，复杂度更高。

```python
# 改造前：直接调用 xtquant SDK（仅 Windows 可用）
class QMTXtQuantBridge:
    def place_native_order(self, ...):
        xt = _get_xttrader()
        return xt.order_stock(...)

# 改造后：调用 miniQMT HTTP API（跨平台）
class QMTXtQuantBridge:
    def __init__(self, bridge_url: str, bridge_token: str, ...):
        self._base_url = bridge_url
        self._headers = {"Authorization": f"Bearer {bridge_token}"}

    def place_native_order(
        self, *, client_order_id, symbol, side, quantity, price, order_type
    ):
        qmt_symbol = self.format_symbol(symbol)
        resp = httpx.post(
            f"{self._base_url}/api/v1/broker/qmt/orders",
            headers=self._headers,
            json={
                "request_id": uuid.uuid4().hex,
                "client_order_id": client_order_id,
                "symbol": qmt_symbol,
                "side": side,
                "quantity": int(quantity),
                "price": str(price),
                "order_type": order_type,
            },
        )
        data = resp.json()
        # 必须同步拿到稳定的 native id，供 akquant 立即绑定与撤单
        return int(data["native_order_id"])
```

**`LiveRunner` / `factory.py` 参数变化**：

```python
# 改造前
runner = LiveRunner(
    broker="miniqmt",
    trading_mode="broker_live",
    gateway_options={
        "qmt_path": "C:/QMT/userdata_mini",
        "account_id": "xxx",
    },
)

# 改造后
runner = LiveRunner(
    broker="miniqmt",
    trading_mode="broker_live",
    gateway_options={
        "bridge_url": "http://windows-host:8000",  # miniQMT bridge 地址
        "bridge_token": "xxx",                     # Bearer token
    },
)
```

注意：

- 当前 akquant `LiveRunner` **并不接受** `bridge_url` / `bridge_token` 顶层参数，broker 特定配置仍需走 `gateway_options={...}`
- 除非同步修改 `LiveRunner.__init__` 签名，否则本文档与示例都必须维持 `gateway_options` 写法
- miniQMT v1 计划目前是 single-account mode，是否继续从 akquant 显式传 `account_id`，需要以 miniQMT 实际 contract 为准
- 当前 akquant `cancel_order()` 仍按整数 native id 解析 `broker_order_id`，因此 miniQMT facade 若只返回任意字符串 `external_order_id`，还需要同步修改 akquant 的 `broker_order_id` 编码与解析规则

### 2.3 符号格式差异

需要明确各层的符号格式约定：

| 场景 | 格式 | 示例 |
|---|---|---|
| akquant 内部 | 纯数字 | `600000` |
| miniQMT contract（对外） | `code.market` | `600000.SH` |
| xtquant / miniQMT 当前默认对接口径 | `code.market` | `600000.SH` |

桥接层（`QMTXtQuantBridge`）负责在 akquant 格式（`600000`）和 miniQMT 格式（`600000.SH`）之间转换；miniQMT 的 `QmtService` 默认也应先按 `600000.SH` 与 xtquant 对接，不应预设 `SH.600000` 才是唯一正确的内部格式。只有当真实运行时证明某个 xtquant API 仅接受 `SH.600000` 时，才在 `qmt_service.py` 内部对该 API 做局部转换。也就是说：

- `code.market` 是 **miniQMT 对外 contract**
- `600000.SH` 也是 **miniQMT 当前默认内部对接口径**
- `SH.600000` 只能视为 **经运行时证据证实后的局部兼容细节**
- akquant 不应直接暴露或依赖 `SH.600000` 作为跨进程 contract
- miniQMT 可以兼容接收 `600000.SH`、`SH.600000`，也可以在已知市场范围内接收简写 `600000`
- 但 `600000` 本质上是缺少 market 信息的便捷输入，不能与 `600000.SH` / `SH.600000` 视为同等级 contract
- miniQMT 的返回值、持久化、日志、task result、broker facade 回显应统一归一化为 `600000.SH`

推荐把符号处理拆成两层：

- **输入兼容层**：接收多种用户输入，立即归一化
- **contract / persistence 层**：统一只使用 `600000.SH`

其中 `600000` 简写仅应在以下前提下允许：

- 当前账户 / 路由范围能稳定推断 market
- 该推断规则已被写入 contract 文档与测试
- 若无法唯一推断，应直接报错，而不是隐式猜测

`format_symbol` 方法需调整映射规则：

```python
# 改造前：akquant → xtquant（SH.600000 格式）
def format_symbol(symbol: str) -> str:
    if symbol.startswith("6"):
        return f"SH.{symbol}"

# 改造后：akquant → miniQMT（600000.SH 格式）
def format_symbol(symbol: str) -> str:
    if symbol.startswith("6"):
        return f"{symbol}.SH"
```

### 2.4 保留与联动修改范围

以下代码仍保留在 akquant，但其中一部分需要**联动修改**，不能简单理解为“完全不动”：

- **基本不变**
  - `models.py` — `UnifiedOrderSnapshot` 等统一模型
  - `mapper.py` — `BrokerEventMapper`
  - `base.py` — Gateway Protocol 定义
- **需要联动修改**
  - `miniqmt.py` — `MiniQMTTraderGateway` 仍保留统一协议层职责，但 bridge 改为 HTTP 后，需要重新明确 `place_order()` 的同步返回、`cancel_order()`、`query_account()`、`query_positions()`、`heartbeat()`、`sync_open_orders()`、`sync_today_trades()` 的远端语义
  - `factory.py` — 不只是改参数名，还要改 bridge 的构造条件、配置项读取与失败策略
  - `tests/test_gateway_miniqmt_xtquant.py` — mock bridge 测试应保留，但 bridge 行为将从“直接调 xtquant”切换为“HTTP client + contract mapping”
  - `examples/06_live_trading_miniqmt.py` — 示例需同步改成 `gateway_options={"bridge_url": ..., "bridge_token": ...}`

额外说明：

- 本次“桥接层转移”**并不会自动解决** akquant 当前 `LiveRunner.run()` 固定 `use_china_futures_market()` 的问题
- 本次“桥接层转移”**也不会自动解决** `submit_order(extra=...)` 仍拒绝 broker 专有字段的问题

---

## 3. 执行步骤

### 前置条件

- miniQMT Phase A 完成（`qmt_service.py` seam + task contract kernel + SQLite 持久化）
- miniQMT legacy `/api/v1/broker/qmt/orders*` facade 已委派到 task core，并能**同步返回稳定的 native order id**（或一个可无损还原为 native id 的字段）
- miniQMT 至少提供账户、持仓、订单/成交查询所需的 broker-facing contract；否则 akquant 侧无法补齐 `query_account()` / `query_positions()` / 恢复闭环
- miniQMT 的 Bearer auth、contract version、single-account scope 已固定，不再随 route 临时漂移
- 如果迁移目标包含 `broker_live` 恢复线程，则需同时明确 `sync_open_orders()` / `sync_today_trades()` 的远端数据来源与查询路径

### 步骤

1. **miniQMT 侧吸收 xtquant SDK 逻辑**
   - 将 akquant 的 `STATUS_MAP`、懒导入、`place_native_order`、`cancel_native_order`、查询方法、回调类等逻辑整合进 `qmt_service.py`
   - 保持 miniQMT 的符号格式（`code.market`），并默认以此对接 xtquant；若个别 xtquant API 有例外，再在 `qmt_service.py` 内局部转换
   - 在 HTTP / facade 入口增加 symbol normalize 前置层，兼容 `600000.SH`、`SH.600000`，并仅在可稳定推断 market 时接收 `600000`
   - `qmt.py` 中 legacy broker facade 应全部委派到 canonical task core，不再自建第二套 execution truth
   - facade 需要继续向 akquant 同步返回稳定的 native order id，不能只返回 task receipt

2. **akquant 改造 `QMTXtQuantBridge`**
   - 删除所有 `from xtquant import ...` 导入
   - 删除 `_get_xttrader()`、`_QMTCallback` 等 xtquant 相关代码
   - 新增 `httpx` 依赖
   - 改为 HTTP 客户端，调用 miniQMT REST API
   - 保留 `place_native_order()` 的同步返回契约；若底层只提供 `/task/execute`，则 bridge 需自己封装“execute + poll until stable identity”
   - 调整 `format_symbol` 符号转换规则
   - 增加明确的 fail-closed 错误处理：bridge 已配置但服务不可用时，直接报错，不自动回退到 in-memory 模式

3. **akquant 联动更新 `MiniQMTTraderGateway` 与 `factory.py`**
   - `factory.py` 参数从 `qmt_path` 改为 `bridge_url` + `bridge_token`（保留 `gateway_options` 入口）
   - `MiniQMTTraderGateway` 需要重新定义 HTTP bridge 模式下的 `query_account()`、`query_positions()`、`heartbeat()`、`sync_open_orders()`、`sync_today_trades()` 语义
   - 禁止在 `broker_live` 下因 bridge 不可用而静默落回本地占位实现

4. **更新测试**
   - 删除 `test_gateway_miniqmt_xtquant.py` 中依赖 xtquant 导入状态的测试
   - 新增 HTTP mock 测试（使用 `httpx.MockTransport` 或 `respx`）
   - 保留符号转换测试（调整预期格式）
   - 保留 `TestGatewayBridgeIntegration` 和 `TestNativeOrderIdParsing`，但预期需改成 HTTP contract 映射后的行为
   - 补充 bridge 不可用、auth/version 不匹配、task receipt 无法补齐 stable identity 的失败测试
   - 若要支持恢复线程，还需补 `sync_open_orders()` / `sync_today_trades()` 的查询与去重测试

5. **更新示例 `examples/06_live_trading_miniqmt.py`**
   - 配置参数从 `qmt_path` 改为 `gateway_options={"bridge_url": ..., "bridge_token": ...}`

6. **单独记录未被本次转移解决的外围缺口**
   - `LiveRunner.run()` 当前固定 `engine.use_china_futures_market()`
   - `submit_order(extra=...)` 当前仍拒绝 broker 专有字段
   - MiniQMTMarketGateway 仍是占位实现，不会自动驱动 `DataFeed`

### 供 AI 阅读的迁移文件清单

建议后续 AI 按“**先读 miniQMT contract 计划，再读 akquant 契约，再搬运 xtquant 细节**”的顺序处理，避免只复制代码、不补契约。

#### A. 优先阅读：miniQMT 侧的目标文档与现有实现

| 路径 | 角色 | 用途 |
|---|---|---|
| `/mnt/d/MyCode3/miniQMT/DOCS/项目说明/2026-04-30-miniqmt-v1-contract-kernel-implementation-plan.md` | **最高优先级规范** | 定义 canonical `/api/v1/task/*`、Phase A/Phase B 边界、auth/version/task store 目标结构 |
| `/mnt/d/MyCode3/miniQMT/FUNCTION_TREE.md` | **功能边界地图** | 区分现状/计划/后续/非目标，避免把 xtdata 行情能力误并入本次迁移 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/main.py` | **当前 bridge 主实现** | 现有 `Settings` / `TaskStore` / `QmtService` 都还在这里，迁移时需要拆分出去 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/models.py` | **当前 HTTP contract model** | 查看 `OrderRequest`、`TaskExecuteRequest`、`TaskResultResponse` 等当前 shape |
| `/mnt/d/MyCode3/miniQMT/bridge/app/routes/task.py` | **canonical task route 现状** | 查看当前 `/api/v1/task/execute` / `task/result` 行为，与计划差距 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/routes/qmt.py` | **legacy facade 现状** | 查看当前 `/api/v1/broker/qmt/orders*` 是否已经能委派到 task core |
| `/mnt/d/MyCode3/miniQMT/bridge/app/routes/capabilities.py` | **contract metadata 现状** | 查看 capabilities 对外暴露情况 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/routes/health.py` | **health contract 现状** | 查看健康检查返回字段 |
| `/mnt/d/MyCode3/miniQMT/bridge/pyproject.toml` | **依赖入口** | 迁移 HTTP client / test 依赖前先看当前 bridge 依赖组织 |

#### B. 可迁移或可改写吸收：akquant 侧 xtquant 直连实现

| 路径 | 分类 | 可吸收内容 | 迁移时注意 |
|---|---|---|---|
| `python/akquant/gateway/miniqmt_xtquant.py` | **主要迁移来源** | 懒导入、平台检查、`STATUS_MAP`、symbol 转换、下单/撤单/query 包装、callback seam | 不要原样照搬“xtquant 直连假设”；miniQMT 对外 contract 固定 `code.market`，内部也默认先按该格式对接 |
| `tests/test_gateway_miniqmt_xtquant.py` | **测试迁移来源** | symbol conversion、bridge integration、native order id parsing、ImportError 行为 | 测试预期要从“xtquant 直连”切到“HTTP contract + native id 映射” |
| `docs/zh/reference/miniqmt_trading_impl.md` | **迁移背景参考** | 第一阶段保留 `MiniQMTTraderGateway`、bridge 可选、恢复/审计/市场模型缺口说明 | 这是 akquant 内部迁移草案，不是 miniQMT 的规范文档 |
| `examples/06_live_trading_miniqmt.py` | **示例参考** | 用户侧配置形态、`gateway_options` 用法、占位/真实路径差异 | 当前示例已明确是草案，不代表真实链路已打通 |

#### C. 必须同步阅读：akquant 侧不能被破坏的契约文件

| 路径 | 契约点 | 为什么必须读 |
|---|---|---|
| `python/akquant/gateway/miniqmt.py` | `place_order()`、`cancel_order()`、`query_account()`、`query_positions()`、`heartbeat()`、`sync_open_orders()`、`sync_today_trades()` | 决定 HTTP bridge 改造后 akquant 仍要求什么同步/恢复语义 |
| `python/akquant/gateway/factory.py` | bridge 构造条件与参数入口 | 当前 MiniQMT bridge 由 `gateway_options` 驱动，不是 `LiveRunner` 顶层参数 |
| `python/akquant/live.py` | `_build_gateway_kwargs()`、`submit_order` 注入、recovery loop、market selection | 明确 `gateway_options` 入口、`extra broker fields` 拒绝点、恢复线程依赖、股票市场模型缺口 |
| `python/akquant/gateway/base.py` | `TraderGateway` Protocol | 明确 MiniQMT bridge 迁移后仍需满足哪些 query/sync 方法 |
| `python/akquant/gateway/models.py` | `UnifiedOrderRequest` / `UnifiedOrderSnapshot` / `UnifiedTrade` / `UnifiedAccount` / `UnifiedPosition` | 明确 akquant 侧统一模型 shape，避免 bridge route 返回字段漂移 |
| `python/akquant/gateway/mapper.py` | 订单/成交/执行报告映射 | 如果 miniQMT 最终也走 callback 注入，这里的统一映射思路要保留 |
| `tests/test_live_runner_broker_bridge.py` | submit / owner binding / recovery / callback 期望 | 这是 akquant `broker_live` 行为的关键回归面 |
| `docs/zh/reference/gateway_system.md` | broker bridge 线程与恢复说明 | 便于理解为什么 `sync_open_orders()` / `sync_today_trades()` 不能省略 |
| `docs/zh/reference/manual.md` | 当前 MiniQMT 文档边界 | 防止迁移后文档与代码语义再次漂移 |

#### D. miniQMT 侧建议新增或重点落地的目标文件

| 路径 | 目标角色 | 来源 |
|---|---|---|
| `/mnt/d/MyCode3/miniQMT/bridge/app/qmt_service.py` | 吸收 xtquant SDK 直连逻辑的主落点 | 主要吸收 `miniqmt_xtquant.py` |
| `/mnt/d/MyCode3/miniQMT/bridge/app/task_service.py` | task core 与 legacy facade 之间的统一编排层 | 以 implementation plan 为准 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/task_store.py` | SQLite WAL 持久化任务存储 | 以 implementation plan 为准 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/settings.py` | Bearer、contract version、DB path 等设置 | 以 implementation plan 为准 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/security.py` | Bearer / version guard | 以 implementation plan 为准 |
| `/mnt/d/MyCode3/miniQMT/bridge/app/time_utils.py` | UTC `Z` 时间戳 helper | 以 implementation plan 为准 |
| `/mnt/d/MyCode3/miniQMT/bridge/tests/test_qmt_service.py` | QMT seam 测试 | 应从 akquant xt bridge 测试中吸收核心断言 |
| `/mnt/d/MyCode3/miniQMT/bridge/tests/test_task_contract.py` | task contract 回归 | 确保 canonical contract 与 legacy facade 不再漂移 |
| `/mnt/d/MyCode3/miniQMT/bridge/tests/test_legacy_qmt_routes.py` | legacy facade 回归 | 确保 `/broker/qmt/orders*` 对 akquant 仍可用 |

#### E. 建议 AI 的最小阅读顺序

1. 先读本文件和 miniQMT v1 implementation plan，明确 canonical contract 与 legacy facade 的角色分工。
2. 再读 `FUNCTION_TREE.md`，确认本次迁移只处理交易 bridge，不扩到 xtdata 行情。
3. 然后读 miniQMT 当前 `bridge/app/main.py`、`routes/task.py`、`routes/qmt.py`，确认现状缺口。
4. 再读 akquant 的 `miniqmt_xtquant.py`，只吸收 xtquant SDK 交互细节，不照搬对外 contract。
5. 再读 akquant 的 `miniqmt.py`、`factory.py`、`live.py`，补上同步返回、恢复、`gateway_options`、fail-closed 这些契约约束。
6. 最后用 `tests/test_gateway_miniqmt_xtquant.py` 与 `tests/test_live_runner_broker_bridge.py` 反推迁移后必须保住的行为。

---

## 4. 转移后的架构

```
┌─────────────────────────┐       HTTP        ┌─────────────────────────┐
│       akquant (Linux)   │  ←─────────────→   │   miniQMT (Windows)    │
│                         │                    │                         │
│  MiniQMTTraderGateway   │                    │  FastAPI bridge service │
│       ↕                 │                    │       ↕                 │
│  QMTXtQuantBridge       │   REST API         │  QmtService             │
│  (HTTP client)          │   Bearer token     │  (xtquant SDK 封装)     │
│       ↕                 │                    │       ↕                 │
│  Unified Models         │                    │  xttrader / xtdata      │
│  BrokerEventMapper      │                    │  SQLite task store      │
└─────────────────────────┘                    └─────────────────────────┘
```

### 职责边界

| 职责 | 归属 |
|---|---|
| xtquant SDK 导入、连接、原生调用 | miniQMT |
| 订单/成交回调处理 | miniQMT（Phase B） |
| 任务持久化、contract kernel | miniQMT |
| 认证、contract version 管理 | miniQMT |
| canonical `/api/v1/task/*` | miniQMT |
| legacy `/api/v1/broker/qmt/orders*` facade | miniQMT（对 akquant 暂保留） |
| 统一交易协议（UnifiedOrder 等） | akquant |
| 策略 → 订单 → 事件映射 | akquant |
| 风控、仓位管理 | akquant |
| 符号格式转换（`600000` ↔ `600000.SH`） | akquant 桥接层 |
| 必要时的局部 `code.market` ↔ `market.code` 兼容转换 | miniQMT `QmtService`（仅限被运行时证据证实的 xtquant API） |

---

## 5. 风险与注意事项

- **miniQMT Phase A 未完成前，akquant 当前的 xtquant 直连代码应保留**，作为过渡方案
- `place_order()` 的同步返回契约不能丢。akquant 当前会在返回后立即绑定 `client_order_id ↔ broker_order_id`，因此 miniQMT facade 或 akquant HTTP bridge 必须同步补齐稳定 identity
- 符号格式需明确分层：miniQMT 可以兼容多种输入格式，但对外返回、持久化和日志应统一为 `600000.SH`；只有运行时证实存在特例 API 时，才在 `qmt_service.py` 内局部转成 `SH.600000`
- HTTP 调用引入网络延迟，对高频策略需评估影响
- miniQMT 服务不可用时，akquant 在 `broker_live` 下应 **fail closed**（直接报错），不要自动回退到 in-memory 模式
- 如果 miniQMT 只完成 Phase A receipt，而未补齐 query / callback / recovery contract，则 akquant 迁移后仍然不能视为“完成真实 broker_live 闭环”
- 本方案只解决“xtquant 交互层迁移”，**不解决** akquant 当前股票市场模型切换、broker 专有下单字段透传、以及 MiniQMT 行情桥接缺口
