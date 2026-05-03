# AKQuant 功能开发路线图

> 生成日期：2026-05-01
> 更新日期：2026-05-03
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

## 2. ~~P0 — Rust Engine Python 绑定补齐~~ ✅ 已完成

> 原 43 个 skipped tests 全部通过（161 passed, 0 skipped）。所有策略级风控、多策略 Slot、优先级/预算、填充策略、手续费前缀方法已在 `src/engine/python.rs` 的 `#[pymethods]` 块中暴露。

### 2.1 策略级风控绑定（19 项） ✅

| 方法 | 状态 |
|------|------|
| `set_strategy_max_order_value_limits` | ✅ 已暴露 |
| `set_strategy_max_order_size_limits` | ✅ 已暴露 |
| `set_strategy_max_position_size_limits` | ✅ 已暴露 |
| `set_strategy_max_daily_loss_limits` | ✅ 已暴露 |
| `set_strategy_max_drawdown_limits` | ✅ 已暴露 |
| `set_strategy_reduce_only_after_risk` | ✅ 已暴露 |
| `set_strategy_risk_cooldown_bars` | ✅ 已暴露 |

### 2.2 多策略 Slot 绑定（3 项） ✅

| 方法 | 状态 |
|------|------|
| `set_strategy_slots` | ✅ 已暴露 |
| `set_default_strategy_id` | ✅ 已暴露 |
| `set_strategy_for_slot` | ✅ 已暴露 |

### 2.3 策略优先级与冷却（4 项） ✅

| 方法 | 状态 |
|------|------|
| `set_strategy_priorities` | ✅ 已暴露 |
| `set_strategy_risk_budget_limits` | ✅ 已暴露 |
| `set_portfolio_risk_budget_limit` | ✅ 已暴露 |
| `set_risk_budget_mode` / `set_risk_budget_reset_daily` | ✅ 已暴露 |

### 2.4 填充策略（2 项） ✅

| 方法 | 状态 |
|------|------|
| `set_fill_policy` / `get_fill_policy` | ✅ 已暴露 |
| 预留填充基差 `mid_quote` / `vwap_window` / `twap_window` | 仍为 NotImplementedError（P1 填充策略实现） |

### 2.5 期货/期权手续费（3 项） ✅

| 方法 | 状态 |
|------|------|
| `set_futures_fee_rules_by_prefix` | ✅ 已暴露 |
| `set_options_fee_rules_by_prefix` | ✅ 已暴露 |
| `set_futures_validation_options_by_prefix` | ✅ 已暴露 |

---

## 3. ~~P1 — 资产类模块 Python 封装~~ ✅ 已完成

> 四个资产类模块已全部实现，含 41 个单元测试。公式与 Rust 侧 `src/market/` 和 `src/margin/calculator.rs` 一致。

### 3.1 已实现模块

| 模块 | 路径 | 已封装的能力 |
|------|------|----------------|
| `futures` | `python/akquant/futures/` | `FuturesContract`, `FuturesFeeConfig`, `calculate_commission`, `calculate_margin`, `calculate_notional`, `resolve_commission_rate`, `is_t_plus_zero` |
| `stock` | `python/akquant/stock/` | `StockInfo`, `StockFeeConfig`, `calculate_commission`（含印花税）, `is_t_plus_one` |
| `option` | `python/akquant/option/` | `OptionContract`, `OptionFeeConfig`, `calculate_commission`, `calculate_option_margin`（long=0 / short 公式）, `is_t_plus_zero` |
| `fund` | `python/akquant/fund/` | `FundInfo`, `FundFeeConfig`, `calculate_commission`, `is_t_plus_one` |

每个模块结构：`__init__.py` + `models.py`（数据类）+ `rules.py`（交易规则）+ `queries.py`（计算接口）

---

## 4. ~~P1 — 期权 Greek 风控~~ ✅ 已完成

> BSM 定价模块、Greeks 风控规则、IV 求解器、交易所标准保证金公式、per-slot Greek 预算全部实现并通过测试（Rust 104 passed / Python 760 passed / Golden 4 passed）。

### 4.1 BSM 定价与 Greeks 模块 ✅

**文件**: `src/pricing/bsm.rs`, `src/pricing/python.rs`

| 函数 | 说明 |
|------|------|
| `normal_cdf` / `normal_pdf` | Abramowitz-Stegun 近似（误差 <7.5e-8） |
| `bsm_price()` | 欧式期权理论价格（T=0 返回内在价值） |
| `calculate_greeks()` | Delta/Gamma/Theta/Vega/Rho 计算 |
| `time_to_expiry()` | YYYYMMDD → 年化时间 |
| `implied_volatility()` | Newton-Raphson IV 求解（可配置初始值/迭代/容差） |

Python 绑定：`calculate_option_greeks()`、`calculate_implied_volatility()`、`PyGreeksResult` pyclass

### 4.2 RiskConfig Greek 字段 ✅

**文件**: `src/risk/config.rs`, `python/akquant/config.py`, `python/akquant/risk.py`

新增 9 个字段：`max_portfolio_delta/gamma/vega`（组合级）、`slot_max_delta/gamma/vega`（策略槽级）、`option_risk_free_rate`、`option_default_volatility`、`option_greek_per_underlying`

### 4.3 OptionGreekRiskRule 实现 ✅

**文件**: `src/risk/option.rs`（25→~360 行，从空壳重写为完整实现）

- 按标的聚合或组合级别 Greek 聚合（BSM 定价 × quantity × multiplier）
- 组合级限制检查 + per-slot Greek 预算检查
- 已过期期权回退到内在 Delta（Call ITM=1, OTM=0）
- 引擎管道中 `check_strategy_slot_greek_limit()` 已接入 `process_order_request()`

### 4.4 交易所标准保证金公式 ✅

**文件**: `src/margin/calculator.rs`, `python/akquant/option/queries.py`

中国交易所标准公式：`Max(权利金 + Max(12%×标的 - OTM, 7%×标的), 权利金 + 标的×保证金率)`，Long 返回 0。

### 4.5 测试与示例 ✅

- Rust 单元测试：BSM 精度、Put-Call Parity、Greeks 边界值、风控限制、保证金计算
- Golden 回归测试：`tests/golden/` 新增 `option_greek_risk` 场景
- 示例：`examples/49_etf_option_greek_risk.py`
- 文档：`docs/zh/guide/option_risk.md`

---

## 5. P1 — Gateway 完善

### 5.1 Gateway 契约与边界收口（当前工作树已基本完成，待合并）

**当前状态**:
- `factory.py` 已按 broker metadata 区分 `asset_class`，`LiveRunner.run()` 会根据 `GatewayBundle.metadata` 选择 `use_china_market()` / `use_china_futures_market()`
- `UnifiedOrderRequest` 已增加 `broker_options` 字段，broker_live 注入的 `submit_order` 也已补齐 `broker_options`、`slippage`、`commission` 等公开参数入口，避免直接 `TypeError`
- `bridge_url` 入口已预留并明确 `raise NotImplementedError`，`QMTXtQuantBridge` 构造时会发 `FutureWarning` 标记迁移边界
- `broker_live` 已对未支持 `order_type` 做显式限制；`get_execution_capabilities()` 也已补充 `supported_order_types`、`broker_options`、`unsupported_params`
- 现有测试已覆盖市场模型选择、`broker_options` 透传、`bridge_url` guard、`FutureWarning`、`order_type` 限制，以及 `extra` / `trigger_price` / trailing / `fill_policy` / `slippage` / `commission` 的 fail-closed

**后续动作**:
- 将当前工作树中的 gateway 收口改动合并到主线
- 合并后把 5.1 从”活跃收口项”降为”已完成里程碑”，避免路线图继续把它当成主要缺口
- 后续若 broker_live 新增真实高级订单能力，再单列新 roadmap 项，不复用当前 fail-closed 收口项

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

### 5.2 MiniQMT 行情网关

**当前状态**:
- `MiniQMTMarketGateway` 仍是 placeholder，`connect()` 只设置布尔值，不驱动 `DataFeed`
- 结合当前边界规划，不应在 akquant 内继续加深新的长期 xtquant 直连路径；行情能力的长期形态应与 miniQMT bridge 对齐

**需要实现**:
- 优先定义 miniQMT bridge 侧的行情 contract（HTTP 轮询或 WebSocket 推送）
- 将 tick/bar 数据推入 `DataFeed`
- 支持 `on_tick` / `on_bar` 回调
- 如果必须先做临时直连验证，应限制为过渡性验证层，不作为长期默认架构

**前置条件**: miniQMT 需要先明确市场数据 bridge contract；akquant 侧再按该 contract 接入

### 5.3 MiniQMT HTTP Bridge 对接

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

### 5.4 PTrade 真实对接

**当前状态**: 全部 placeholder，无真实券商连接。

**需要实现**:
- PTrade SDK 的 Python 封装（或 HTTP bridge 模式）
- 行情 + 交易双通道
- 认证与重连机制

**备注**: 依赖 PTrade 券商 SDK 可用性，执行顺序晚于 4.2/4.3

---

## 6. ~~P1 — 回测引擎填充策略~~ ✅ 部分完成

### 6.1 已实现填充基差

**文件**: `src/model/types.rs`, `src/execution/common.rs`, `src/engine/python.rs`

| 填充基差 | 说明 | 状态 |
|----------|------|------|
| `open` | 开盘价成交 | ✅ 已有 |
| `close` | 收盘价成交 | ✅ 已有 |
| `ohlc4` | OHLC 均价 | ✅ 已有 |
| `hl2` | (H+L)/2 | ✅ 已有 |
| `mid_quote` | (H+L)/2 中间价 | ✅ 新增 |
| `typical` | (H+L+C)/3 典型价 | ✅ 新增 |
| `vwap_bar` | 单 bar VWAP 近似 | ✅ 新增 |
| `twap` | 多 bar 时间加权拆单 | 待实现（需 ExecutionProcessor 架构改动） |

---

## 7. ~~P2 — 仓位管理器扩展~~ ✅ 已完成

**文件**: `python/akquant/sizer.py`

**已有**: `FixedSize`、`PercentSizer`、`AllInSizer`

**已扩展**:

| Sizer | 说明 |
|-------|------|
| `ATRSizer` | 基于 ATR 波动率动态调仓 |
| `KellySizer` | Kelly 公式仓位计算（默认 half-Kelly） |
| `RiskParitySizer` | 风险平价分配 |
| `EqualWeightSizer` | 等权分配（多标的场景） |

---

## 8. ~~P2 — 技术指标扩展~~ ✅ 部分完成

**文件**: `python/akquant/talib/`, `src/indicators/candlestick.rs`

**已有**: 103 个 Rust 后端指标函数

**已扩展 — K 线形态识别（Batch 1, 10 个）**:

| 形态 | 说明 | 返回值 |
|------|------|--------|
| `CDLDOJI` | 十字星 | +100 |
| `CDLHAMMER` | 锤子线（看涨反转） | +100 |
| `CDLHANGINGMAN` | 上吊线（看跌反转） | -100 |
| `CDL_ENGULFING` | 吞没形态 | +100/-100 |
| `CDL_HARAMI` | 孕线形态 | +100/-100 |
| `CDL_MORNINGSTAR` | 晨星（看涨反转） | +100 |
| `CDL_EVENINGSTAR` | 暮星（看跌反转） | -100 |
| `CDL_3BLACKCROWS` | 三只乌鸦（看跌） | -100 |
| `CDL_3WHITESOLDIERS` | 三白兵（看涨） | +100 |
| `CDL_SHOOTINGSTAR` | 射击之星（看跌反转） | -100 |

**仍可扩展**:
- K 线形态 Batch 2+（剩余 ~50 个 CDL* 系列）
- 周期指标（HT_DCPERIOD、HT_DCPHASE、HT_PHASOR）
- 统计函数（BETA、CORREL、LINEARREG 等）

**实施路径**: 在 `src/indicators/` 中增加 Rust 实现，通过 `src/lib.rs` 注册到 Python

---

## 9. ~~P2 — Indicator 增量更新~~ ✅ 已完成

**文件**: `python/akquant/indicator.py`

**已实现**:
- `EMA.update()` — alpha=2/(window+1) 指数移动平均增量公式
- `RSI.update()` — 平滑涨跌均值增量更新，window+1 个值后返回有效值
- `MACD.update()` — fast/slow EMA 增量 + signal line + histogram
- 所有指标支持 `__getstate__`/`__setstate__` pickle 序列化

---

## 10. ~~P2 — ML 适配器扩展~~ ✅ 部分完成

**文件**: `python/akquant/ml/model.py`

**已有**: `SklearnAdapter`、`PyTorchAdapter`

**已扩展**:

| 适配器 | 说明 |
|--------|------|
| `LightGBMAdapter` | LightGBM 原生 API（lazy import），save_model/load_model |
| `XGBoostAdapter` | XGBoost 原生 API（DMatrix），save_model/load_model |

**未扩展**:

| 适配器 | 说明 |
|--------|------|
| `TensorFlowAdapter` | TensorFlow/Keras 模型 |

---

## 11. ~~P3 — 可视化增强~~ ✅ 部分完成

**文件**: `python/akquant/plot/`

**已实现**:
- `plot_comparison()` 策略对比面板（多策略权益/回撤/指标叠加）
- Dashboard `rangeselector`（1M/3M/6M/1Y/ALL）和 `updatemenus` 显示控制
- Report 模板支持 `comparison_results` 参数

**可继续扩展**:
- 实时交易仪表盘（WebSocket 推送）
- 交互式回测浏览器（代替静态 HTML）
- Jupyter FigureWidget 集成

---

## 12. 实施顺序建议

```
Phase 1 (P0) ── Rust 绑定补齐 ✅ 已完成
  ├── 2.1 策略级风控绑定 (19 项) ✅
  ├── 2.2 多策略 Slot 绑定 (3 项) ✅
  ├── 2.3 优先级/冷却/预算 (4 项) ✅
  ├── 2.4 填充策略 (2 项) ✅
  └── 2.5 期货/期权手续费 (3 项) ✅

Phase 2 (P1) ── Gateway 收口 + 资产类模块 + 期权风控
  ├── 5.1 Gateway 契约与边界收口 ✅
  ├── 3.x futures/stock/option/fund Python 封装 ✅
  ├── 4.x 期权 Greek 风控 ✅ (BSM/Greeks/IV/保证金/per-slot)
  ├── 6.x 填充策略实现 (mid_quote/vwap/twap) — 待 Rust Engine 支持
  ├── 5.2 MiniQMT 行情网关 (依赖 miniQMT)
  ├── 5.3 MiniQMT HTTP Bridge 对接 (依赖 miniQMT Phase A)
  └── 5.4 PTrade 真实对接 (在 MiniQMT 之后)

Phase 3 (P2) ── 扩展能力
  ├── 7.x Sizer 扩展 (ATR/Kelly/RiskParity) ✅
  ├── 8.x TA-Lib 指标扩展 ✅ Batch 1 (10 CDL) — 可继续 Batch 2+
  ├── 9.x Indicator 增量更新 ✅
  └── 10.x ML 适配器扩展 (LightGBM/XGBoost) ✅

Phase 4 (P3) ── 体验优化
  └── 11.x 可视化增强
```

---

## 13. ~~跳过测试清单~~ ✅ 已全部通过

原 43 项 skipped tests 已全部通过（`tests/test_engine.py`: 161 passed, 0 skipped）。原因是已编译的二进制文件已包含所有 `#[pymethods]` 绑定。

---

## 维护规则

- 每完成一个功能项，更新本文档对应行的状态标记
- 每次变更优先级或新增功能项，同步更新实施顺序
- 本文档与 CLAUDE.md 配合使用，不替代 CLAUDE.md
