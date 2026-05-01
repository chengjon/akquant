# AKQuant 功能开发路线图

> 生成日期：2026-05-01
> 基于当前工作树的代码扫描结果（包含 gateway 收口中的在途改动）

---

## 1. 优先级分类

| 优先级 | 含义 |
|--------|------|
| **P0** | 阻塞核心流程，影响用户正常使用 |
| **P1** | 重要功能缺口，影响覆盖面或生产可用性 |
| **P2** | 体验优化，扩展能力，可延后 |
| **P3** | 锦上添花，长期规划 |

---

## 2. P0 — Rust Engine Python 绑定补齐

43 个跳过的测试全部因为 Rust 引擎未暴露 Python API。这些测试的脚手架已就绪，只需在 Rust 侧完成绑定。

### 2.1 策略级风控绑定（19 项）

**文件**: `src/engine/core.rs` → `src/lib.rs` 暴露到 Python

| 方法 | 说明 |
|------|------|
| `set_strategy_max_order_value_limits` | 策略级单笔限额 |
| `set_strategy_max_order_size_limits` | 策略级单笔数量限额 |
| `set_strategy_max_position_size_limits` | 策略级持仓限额 |
| `set_strategy_max_daily_loss_limits` | 策略级日损失限额 |
| `set_strategy_max_drawdown_limits` | 策略级回撤限额 |
| `set_strategy_reduce_only_after_risk` | 策略级只减仓标记 |
| `set_strategy_risk_cooldown_bars` | 策略级冷却 K 线数 |

**测试文件**: `tests/test_engine.py` (19 个 skipped)
**相关 Python 代码**: `python/akquant/risk.py` 的 `apply_risk_config()` 使用 `hasattr` 防御

### 2.2 多策略 Slot 绑定（3 项）

| 方法 | 说明 |
|------|------|
| `set_strategy_slots` | 注册策略 slot id 列表 |
| `set_default_strategy_id` | 默认策略 id |
| `set_strategy_for_slot` | 绑定策略实例到 slot |

### 2.3 策略优先级与冷却（4 项）

| 方法 | 说明 |
|------|------|
| `set_strategy_priorities` | 策略优先级 |
| `set_strategy_risk_budget_limits` | 策略级风险预算 |
| `set_portfolio_risk_budget_limit` | 组合级风险预算 |
| `set_risk_budget_mode` / `set_risk_budget_reset_daily` | 预算模式与重置 |

### 2.4 填充策略（2 项）

| 方法 | 说明 |
|------|------|
| `set_fill_policy` | 成交策略配置 |
| 预留填充基差 `mid_quote` / `vwap_window` / `twap_window` | `python/akquant/backtest/engine.py:148,177` — 预留字符串但 raise NotImplementedError |

### 2.5 期货/期权手续费（3 项）

| 方法 | 说明 |
|------|------|
| `set_futures_prefix_fee` | 期货手续费率 |
| `set_options_prefix_fee` | 期权手续费率 |
| `validate_futures_prefix` | 期货合约前缀校验 |

---

## 3. P1 — 资产类模块 Python 封装

### 3.1 空模块填充

以下四个模块目前只有空 `__init__.py`，无任何 Python 层逻辑。Rust 侧已有对应功能（golden 测试中 `futures_margin`、`option_basic` 通过）。

| 模块 | 路径 | 需要封装的能力 |
|------|------|----------------|
| `futures` | `python/akquant/futures/` | 保证金计算、合约乘数、交割规则、结算价 |
| `stock` | `python/akquant/stock/` | T+1 规则、涨跌停、ST 标记、板块分类 |
| `option` | `python/akquant/option/` | Greeks 计算、行权规则、波动率曲面 |
| `fund` | `python/akquant/fund/` | NAV 计算、份额申购赎回规则 |

### 3.2 实施路径

1. 先从 `futures` 开始（有 golden 测试参照）
2. 每个模块结构：`__init__.py` + `models.py`（数据类）+ `rules.py`（交易规则）+ `queries.py`（查询接口）
3. 封装 Rust 引擎已暴露的 API，不重新实现

---

## 4. P1 — Gateway 完善

### 4.1 Gateway 契约与边界收口（进行中）

**当前状态**:
- `factory.py` 已按 broker metadata 区分 `asset_class`，`LiveRunner.run()` 会根据 `GatewayBundle.metadata` 选择 `use_china_market()` / `use_china_futures_market()`
- `UnifiedOrderRequest` 已增加 `broker_options` 字段，broker_live 注入的 `submit_order` 也已补齐 `broker_options`、`slippage`、`commission` 等公开参数入口，避免直接 `TypeError`
- `bridge_url` 入口已预留并明确 `raise NotImplementedError`，`QMTXtQuantBridge` 构造时会发 `FutureWarning` 标记迁移边界
- 现有测试已覆盖市场模型选择、`broker_options` 透传、`bridge_url` guard、`FutureWarning`、以及 `extra` / `trigger_price` / trailing / `fill_policy` / `slippage` / `commission` 的 fail-closed

**剩余收口项**:
- ~~在 broker_live 路径中补上对未支持 `order_type` 的显式限制~~ ✅ (55dc386)
- ~~校准 `get_execution_capabilities()` 的输出~~ ✅ (55dc386)
- ~~同步 `docs/zh/reference/gateway_system.md`~~ ✅ 补充 `broker_options` 字段与参数边界表
- ~~统一 `docs/zh/reference/gateway-completion-and-boundary-plan.md`、路线图与实现现状~~ ✅

**相关文件**:
- `python/akquant/live.py`
- `python/akquant/gateway/factory.py`
- `python/akquant/gateway/models.py`
- `python/akquant/gateway/miniqmt.py`
- `python/akquant/gateway/miniqmt_xtquant.py`
- `tests/test_live_runner_broker_bridge.py`
- `tests/test_gateway_factory.py`
- `tests/test_gateway_miniqmt_xtquant.py`
- `docs/zh/reference/gateway-completion-and-boundary-plan.md`

### 4.2 MiniQMT 行情网关

**当前状态**:
- `MiniQMTMarketGateway` 仍是 placeholder，`connect()` 只设置布尔值，不驱动 `DataFeed`
- 结合当前边界规划，不应在 akquant 内继续加深新的长期 xtquant 直连路径；行情能力的长期形态应与 miniQMT bridge 对齐

**需要实现**:
- 优先定义 miniQMT bridge 侧的行情 contract（HTTP 轮询或 WebSocket 推送）
- 将 tick/bar 数据推入 `DataFeed`
- 支持 `on_tick` / `on_bar` 回调
- 如果必须先做临时直连验证，应限制为过渡性验证层，不作为长期默认架构

**前置条件**: miniQMT 需要先明确市场数据 bridge contract；akquant 侧再按该 contract 接入

### 4.3 MiniQMT HTTP Bridge 对接

**当前状态**:
- `factory.py` 的 `bridge_url` 入口已预留，当前明确 `raise NotImplementedError`
- 当前仓库仍保留 xtquant 直连版 `QMTXtQuantBridge`，并通过 `FutureWarning` 标记其为过渡方案
- `MiniQMTTraderGateway` 已具备桥接插口，后续可替换为 HTTP client 版本

**需要实现**:
- `BridgeClient` 类：HTTP 调用 `POST /api/v1/task/execute`、`GET /api/v1/task/result/{id}`
- 替代当前直连 xtquant 的 `QMTXtQuantBridge`
- symbol 归一化：akquant `600000` ↔ bridge `600000.SH`
- `place_order()` 同步拿到稳定 `native_order_id`（或可无损还原为 native id 的字段），不能退化成只有 task receipt
- 明确 auth / contract version / single-account scope，避免 bridge contract 在接入后继续漂移

**前置条件**: miniQMT Phase A 完成

### 4.4 PTrade 真实对接

**当前状态**: 全部 placeholder，无真实券商连接。

**需要实现**:
- PTrade SDK 的 Python 封装（或 HTTP bridge 模式）
- 行情 + 交易双通道
- 认证与重连机制

**备注**: 依赖 PTrade 券商 SDK 可用性，执行顺序晚于 4.1/4.2/4.3

---

## 5. P1 — 回测引擎填充策略

### 5.1 预留填充基差实现

**文件**: `python/akquant/backtest/engine.py:148,177`

| 填充基差 | 说明 | 实施建议 |
|----------|------|----------|
| `mid_quote` | 使用买卖中间价成交 | 需要买卖盘数据支持 |
| `vwap_window` | 时间窗口加权平均价 | 需要分笔或分钟数据 |
| `twap_window` | 时间窗口等权平均价 | 按时间切片拆单 |

**前置条件**: Rust 侧 Engine 支持 `set_fill_policy` 绑定

---

## 6. P2 — 仓位管理器扩展

**文件**: `python/akquant/sizer.py`

**已有**: `FixedSize`、`PercentSizer`、`AllInSizer`

**可扩展**:

| Sizer | 说明 |
|-------|------|
| `ATRSizer` | 基于 ATR 波动率动态调仓 |
| `KellySizer` | Kelly 公式仓位计算 |
| `RiskParitySizer` | 风险平价分配 |
| `EqualWeightSizer` | 等权分配（多标的场景） |

---

## 7. P2 — 技术指标扩展

**文件**: `python/akquant/talib/`

**已有**: 103 个 Rust 后端指标函数

**可扩展**:
- K 线形态识别（CDL* 系列，约 60 个）
- 周期指标（HT_DCPERIOD、HT_DCPHASE、HT_PHASOR）
- 统计函数（BETA、CORREL、LINEARREG 等）

**实施路径**: 在 `src/indicators/` 中增加 Rust 实现，通过 `src/lib.rs` 注册到 Python

---

## 8. P2 — Indicator 增量更新

**文件**: `python/akquant/indicator.py`

**当前**: 仅 `SMA` 子类实现了 `update()` 增量更新，其他指标未实现。

**需要实现**:
- `EMA.update()` — 指数移动平均增量公式
- `RSI.update()` — RSI 增量更新
- `MACD.update()` — MACD 增量更新
- 基类 `Indicator.update()` 保留 NotImplementedError，子类各自实现

---

## 9. P2 — ML 适配器扩展

**文件**: `python/akquant/ml/model.py`

**已有**: `SklearnAdapter`、`PyTorchAdapter`

**可扩展**:

| 适配器 | 说明 |
|--------|------|
| `LightGBMAdapter` | LightGBM 原生 API（非 sklearn wrapper） |
| `XGBoostAdapter` | XGBoost 原生 API |
| `TensorFlowAdapter` | TensorFlow/Keras 模型 |

**备注**: XGBoost/LightGBM 的 sklearn 兼容接口已可通过 `SklearnAdapter` 使用，原生适配器可提供更好的训练控制

---

## 10. P3 — 可视化增强

**文件**: `python/akquant/plot/`

**可扩展**:
- 实时交易仪表盘（WebSocket 推送）
- 交互式回测浏览器（代替静态 HTML）
- 策略对比面板（多策略叠加展示）

---

## 11. 实施顺序建议

```
Phase 1 (P0) ── Rust 绑定补齐
  ├── 2.1 策略级风控绑定 (19 项)
  ├── 2.2 多策略 Slot 绑定 (3 项)
  ├── 2.3 优先级/冷却/预算 (4 项)
  ├── 2.4 填充策略 (2 项)
  └── 2.5 期货/期权手续费 (3 项)

Phase 2 (P1) ── Gateway 收口 + 资产类模块
  ├── 4.1 Gateway 契约与边界收口
  ├── 3.x futures/stock/option/fund Python 封装
  ├── 5.x 填充策略实现 (mid_quote/vwap/twap)
  ├── 4.2 MiniQMT 行情网关
  ├── 4.3 MiniQMT HTTP Bridge 对接 (依赖 miniQMT Phase A)
  └── 4.4 PTrade 真实对接 (在 MiniQMT 之后)

Phase 3 (P2) ── 扩展能力
  ├── 6.x Sizer 扩展 (ATR/Kelly/RiskParity)
  ├── 7.x TA-Lib 指标扩展
  ├── 8.x Indicator 增量更新
  └── 9.x ML 适配器扩展

Phase 4 (P3) ── 体验优化
  └── 10.x 可视化增强
```

---

## 12. 跳过测试清单

以下测试因 Rust 绑定未暴露而跳过，完成后应取消跳过：

```bash
uv run pytest tests/test_engine.py -k "skip" --collect-only -q 2>/dev/null | grep "<"
```

总计 43 项，分布在 `tests/test_engine.py` 中。

---

## 维护规则

- 每完成一个功能项，更新本文档对应行的状态标记
- 每次变更优先级或新增功能项，同步更新实施顺序
- 本文档与 CLAUDE.md 配合使用，不替代 CLAUDE.md
