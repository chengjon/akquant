# AKQuant 总体设计方案与功能介绍

> 版本：v0.2.8 | 更新日期：2026-05-03 | 许可证：MIT

---

## 一、项目概述

AKQuant 是一款面向量化投研的高性能混合框架，采用 **Rust 核心引擎 + Python 接口层** 的双层架构。Rust 层负责所有性能敏感路径（回测引擎、撮合、风控、指标计算），通过 PyO3/maturin 编译为 Python C 扩展；Python 层提供策略开发、配置管理、因子分析、可视化、实盘交易等用户接口。

**核心设计目标：**

- **极致性能**：Rust 零开销抽象 + Zero-Copy 数据架构，回测速度远超纯 Python 框架
- **多资产支持**：股票（A 股）、期货、期权、加密货币、外汇，统一 API
- **生产级风控**：组合级/策略级/订单级三级风控体系，支持保证金账户
- **ML 原生集成**：内置 Walk-forward Validation 框架，无缝对接 PyTorch/sklearn/LightGBM/XGBoost
- **实盘对接**：CTP（期货）、MiniQMT（股票）、PTrade 等券商网关，模拟/实盘统一代码

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Python 应用层                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
│  │ Strategy │ │  Config  │ │  Factor  │ │   ML Adapters  │ │
│  │  基类     │ │  配置体系  │ │  因子引擎  │ │ PyTorch/sklearn│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬────────┘ │
│       │            │            │                │          │
│  ┌────┴─────┐ ┌────┴─────┐ ┌───┴──────┐ ┌──────┴───────┐  │
│  │ Gateway  │ │ Backtest │ │  Talib   │ │    Plot      │  │
│  │ 券商网关   │ │  回测入口  │ │ 技术指标   │ │   可视化      │  │
│  └──────────┘ └────┬─────┘ └──────────┘ └──────────────┘  │
│                     │                                        │
├─────────────────────┼─── PyO3 桥接 ──────────────────────────┤
│                     ▼                                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Rust 核心引擎                             │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐  │   │
│  │  │ Engine │ │Execution│ │  Risk  │ │  Indicators  │  │   │
│  │  │ 管道引擎│ │  撮合    │ │  风控   │ │  135 个指标   │  │   │
│  │  └────────┘ └────────┘ └────────┘ └──────────────┘  │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐  │   │
│  │  │Portfolio│ │ Market │ │Analysis│ │  Settlement  │  │   │
│  │  │ 组合管理│ │ 市场模型│ │  分析   │ │   结算管理    │  │   │
│  │  └────────┘ └────────┘ └────────┘ └──────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Rust-Python 桥接

Rust 代码（`src/`）通过 PyO3 编译为 C 扩展（`.so`/`.pyd`），以 `akquant.akquant` 模块名嵌入 Python 包。核心类（`Engine`、`Bar`、`Order`、`Trade`、`RiskManager` 等）均为 `#[pyclass]` 结构体，在 `src/lib.rs` 中注册。

构建配置（`pyproject.toml`）：
- `python-source = "python"` — Python 包根目录
- `module-name = "akquant.akquant"` — Rust 编译产物映射到包内模块

### 2.2 管道架构

引擎核心（`src/engine/core.rs`，约 1100 行）采用事件驱动管道，每个 Bar/Tick 按固定顺序经过 7 个处理器：

```
ChannelProcessor → DataProcessor → ExecutionProcessor(前) → StrategyProcessor
       ↑                                                         │
       └── CleanupProcessor ← StatisticsProcessor ← ExecutionProcessor(后) ←┘
```

| 处理器 | 职责 |
|--------|------|
| ChannelProcessor | 处理上一轮迭代产生的事件 |
| DataProcessor | 获取当前 Bar/Tick 数据 |
| ExecutionProcessor（前） | NextOpen/NextClose 模式的订单撮合 |
| StrategyProcessor | 调用用户的 `on_bar`/`on_tick`/`on_timer` |
| ExecutionProcessor（后） | CurrentClose 模式的订单撮合 |
| StatisticsProcessor | 记录权益/现金/保证金曲线 |
| CleanupProcessor | 清理已完成订单、过期订单 |

处理器定义在 `src/pipeline/`，由 `Engine::build_pipeline()` 组装。

---

## 三、核心模块详解

### 3.1 领域模型（`src/model/`）

| 结构体 | 说明 |
|--------|------|
| `Bar` | OHLCV 行情（时间戳、开高低收量、标的代码） |
| `Tick` | 逐笔行情（时间戳、价格、成交量、买卖盘） |
| `Order` | 订单全生命周期（方向、类型、数量、价格、触发价、状态、成交信息） |
| `Instrument` | 标的定义（资产类型、合约乘数、保证金率、最小价格变动、到期日等） |
| `Timer` | 定时器（时间戳、ID、优先级，最小堆调度） |

**订单类型**：Market、Limit、StopMarket、StopLimit、StopTrail、StopTrailLimit

**价格基准（PriceBasis）**：Open、Close、Ohlc4、Hl2、MidQuote、Typical、VwapBar — 决定订单撮合使用的价格

**时态策略（TemporalPolicy）**：SameCycle（当前 Bar 撮合）、NextEvent（下一事件撮合）

### 3.2 回测引擎（`src/engine/` + `python/akquant/backtest/`）

**Rust 侧**：
- `Engine` 结构体持有 `SharedState`（组合 + 订单管理器 + 数据源）、执行客户端、风控管理器、市场模型、结算管理器
- 支持多策略槽（`StrategySlot`），每个槽独立 `StrategyContext`、风控预算、持仓追踪
- 支持流式回调（streaming），带缓冲和背压机制
- 引擎快照通过 MessagePack 序列化，支持热启动（warm start）

**Python 侧**（入口函数 `run_backtest`）：

| 子模块 | 职责 |
|--------|------|
| `backtest/engine.py` | `run_backtest()` / `run_warm_start()` 入口（门面） |
| `backtest/_types.py` | 类型定义（TypedDict、Policy 类型） |
| `backtest/_execution.py` | 执行策略解析、流运行时 |
| `backtest/_instruments.py` | 资产类型/交易时段解析 |
| `backtest/_strategy_build.py` | FunctionalStrategy、策略实例构建 |
| `backtest/_validation.py` | 配置覆盖、风控验证 |
| `backtest/_data_loading.py` | 数据加载适配 |

### 3.3 执行/撮合（`src/execution/`）

| 撮合器 | 适用资产 | 特性 |
|--------|----------|------|
| `StockMatcher` | 股票 | T+1 可用持仓追踪、最小价格变动取整 |
| `FuturesMatcher` | 期货 | 合约乘数/最小变动验证、按前缀匹配规则 |
| `OptionMatcher` | 期权 | 期权撮合 |
| `CryptoMatcher` | 加密货币 | 简单委托 |
| `ForexMatcher` | 外汇 | 简单委托 |

`SimulatedExecutionClient`（823 行）是回测主力撮合器，按资产类型路由到对应 Matcher。支持：
- 滑点模型（零滑点、固定滑点、百分比滑点）
- 成交量限制
- Bar 内止损触发
- 穿透检查
- 自定义 Python Matcher（`PyExecutionMatcher`）

### 3.4 市场模型（`src/market/`）

`MarketModel` trait 抽象各市场的交易规则：

| 实现 | 市场 | 特性 |
|------|------|------|
| `ChinaMarket` | A 股 | T+1、涨跌停（10%/20%）、集合竞价、印花税 |
| `ChinaFuturesMarket` | 期货 | 保证金、结算价、按前缀配置手续费/合约规格 |
| `ChinaOptionsMarket` | 期权 | 期权保证金、到期结算 |
| `FundMarket` | 基金 | T+1 |
| `SimpleMarket` | 通用 | 无特殊规则 |

### 3.5 风控体系（`src/risk/`）

三级风控架构，可组合规则：

**订单级规则**：
- `MaxOrderSizeRule` — 单笔数量上限
- `MaxOrderValueRule` — 单笔金额上限
- `CashMarginRule` — 现金/保证金充足性检查

**持仓级规则**：
- `MaxPositionSizeRule` — 持仓数量上限
- `StockAvailablePositionRule` — T+1 可卖持仓检查
- `FuturesMarginRule` — 期货保证金充足性检查
- `OptionGreekRiskRule` — 期权 Greek 风控（Delta/Gamma/Vega 限额、按标的聚合、BSM 定价）

**组合级规则**：
- `MaxDailyLossRule` — 日内最大亏损
- `MaxDrawdownRule` — 最大回撤
- `MaxPositionPercentRule` — 单标的仓位占比上限
- `SectorConcentrationRule` — 行业集中度限制
- `MaxLeverageRule` — 杠杆上限
- `StopLossRule` — 止损

**策略槽风控**：每个策略槽独立配置风控预算（budget）、冷却期（cooldown）、仅减仓模式（reduce-only）、Greek 限额（slot_max_delta/gamma/vega）。

### 3.5.1 定价与 Greeks（`src/pricing/`）

BSM 模型为期权风控和策略分析提供数学基础：

| 函数 | 说明 |
|------|------|
| `bsm_price()` | 欧式期权理论价格 |
| `calculate_greeks()` | Delta/Gamma/Theta/Vega/Rho |
| `implied_volatility()` | Newton-Raphson 隐含波动率求解 |
| `calculate_option_greeks()` | Python 绑定 |
| `calculate_implied_volatility()` | IV 求解 Python 绑定 |

**保证金公式**：采用中国交易所标准 `Max(权利金 + Max(12%×标的 - OTM, 7%×标的), 权利金 + 标的×保证金率)`。

### 3.6 策略框架（`python/akquant/strategy*.py`）

用户通过继承 `Strategy` 基类开发策略：

```python
class MyStrategy(Strategy):
    def on_init(self):
        self.subscribe("600000")
    
    def on_bar(self, bar):
        if self.buy_condition(bar):
            self.buy(symbol=bar.symbol, quantity=100)
        elif self.sell_condition(bar):
            self.sell(symbol=bar.symbol, quantity=100)
```

**生命周期钩子**：
`on_init()` → `on_start()` → `on_bar()`/`on_tick()`/`on_timer()` → `on_order()`/`on_trade()` → `on_stop()` → `on_shutdown()`

**交易 API**（委托至 `strategy_trading_api.py`）：
- 基础：`buy()`、`sell()`、`short()`、`cover()`、`submit_order()`、`cancel_order()`
- 目标：`order_target()`、`order_target_value()`、`order_target_percent()`、`order_target_weights()`
- 查询：`get_position()`、`get_positions()`、`get_cash()`、`get_account()`、`get_open_orders()`

**订单组**（`strategy_order_groups.py`）：
- OCO（One-Cancels-Other）：组内任一成交自动撤销其余
- Bracket：进场成交后自动挂出止损/止盈并绑定 OCO

**辅助模块**：
| 模块 | 职责 |
|------|------|
| `strategy_history.py` | 历史数据访问（`get_history()`、`get_history_df()`） |
| `strategy_scheduler.py` | 定时器调度 |
| `strategy_ml.py` | ML 模型生命周期管理 |
| `strategy_logging.py` | 日志 |
| `strategy_time.py` | 时间工具 |
| `strategy_position.py` | 持仓查询 |

### 3.7 配置体系（`python/akquant/config.py`）

四级 dataclass 嵌套：

```
BacktestConfig          # 顶层：时间范围、标的列表、基准、时区、期货/期权专项配置
  └── StrategyConfig    # 账户级：初始资金、费率、滑点、多策略拓扑
        ├── InstrumentConfig  # 标的级：合约规格、费率覆盖
        └── RiskConfig        # 风控级：仓位/订单限制、回撤/止损阈值、保证金模式
```

支持**按标的覆盖**配置（不同标的可设不同的手续费、保证金率等）。中国市场专项配置：`ChinaFuturesConfig`（交易时段、费率模板、按前缀的 tick/lot 规则）、`ChinaOptionsConfig`（按合约前缀的期权费规则）。

### 3.8 技术指标（`src/indicators/` + `python/akquant/talib/`）

共 **135 个**指标，分六大类：

| 类别 | 数量 | 代表指标 |
|------|------|----------|
| 移动平均（moving_average） | 73 | SMA、EMA、DEMA、TEMA、KAMA、MAMA、WMA、MACD、数学变换 |
| 动量（momentum） | 7 | RSI、CMO、MOM、ROC、ROCP、ROCR、WILLR |
| 趋势（trend） | 19 | ADX、ADXR、AROON、CCI、SAR、STOCH、LINEARREG*、BETA、CORREL |
| 波动率（volatility） | 11 | ATR、NATR、STDDEV、Bollinger Bands、AVGPRICE、TYPPRICE |
| 成交量（volume） | 5 | OBV、AD、ADOSC、MFI、BOP |
| K 线形态（candlestick） | 20 | CDLDOJI、CDLHAMMER、CDL_ENGULFING、CDL_MORNINGSTAR 等 |

**双后端架构**：每个指标同时提供 Rust（高性能批量计算）和 Python（兼容 fallback）实现，通过 `talib/backend.py` 自动选择。Rust 侧支持批量数组处理（`update_many`）和逐值更新两种模式。

**增量更新**：`Indicator` 类（`python/akquant/indicator.py`）包装 Rust 指标，支持 `update()` 逐值更新和 pickle 序列化，适用于实盘流式场景。

Python 侧按职责拆分为 6 个子模块：

| 子模块 | 职责 |
|--------|------|
| `talib/funcs.py` | 门面 re-export（保持所有函数名可导入） |
| `talib/_dispatch.py` | Rust 调度层（`_run_rust_*` 系列辅助函数） |
| `talib/_math.py` | 数学/变换类指标 |
| `talib/_overlays.py` | 均线/叠加类指标 |
| `talib/_momentum.py` | 动量/价格类指标 |
| `talib/_trend.py` | 趋势类指标 |
| `talib/_candlestick.py` | K 线形态 |

### 3.9 因子引擎（`python/akquant/factor/`）

基于 Polars Lazy API 的因子表达式引擎，支持 Alpha101 风格公式：

```python
engine = FactorEngine()
result = engine.run_on_data(df, ["Rank(Ts_Mean(Close, 5))", "Ts_Std(Close, 20)"])
```

| 组件 | 职责 |
|------|------|
| `parser.py` | 表达式解析器，将字符串解析为 Polars 表达式 |
| `ops.py` | 25+ 算子（TS 类、CS 类、数学/逻辑类） |
| `engine.py` | 因子引擎，支持 parquet 数据加载、批量因子计算 |

**时序算子（TS）**：`ts_mean`、`ts_std`、`ts_max`、`ts_min`、`ts_sum`、`ts_corr`、`ts_cov`、`delay`、`delta`、`ts_rank`
**截面算子（CS）**：`rank`、`scale`、`cs_standardize`、`cs_neutralize`、`cs_winsorize`

### 3.10 ML 适配器（`python/akquant/ml/`）

| 适配器 | 框架 | 特性 |
|--------|------|------|
| `SklearnAdapter` | scikit-learn | 支持 `partial_fit` 增量学习 |
| `PyTorchAdapter` | PyTorch | 标准训练循环，增量/重训练模式切换 |
| `LightGBMAdapter` | LightGBM | 原生 API 训练 |
| `XGBoostAdapter` | XGBoost | 原生 API 训练 |

所有适配器共享 `ValidationConfig`（Walk-forward 验证配置：训练/测试窗口、滚动步长、增量标志）。`strategy_ml.py` 管理策略内的 ML 生命周期（自动配置、训练信号、模型切换、验证窗口）。

### 3.11 仓位管理器（`python/akquant/sizer.py`）

| 管理器 | 算法 |
|--------|------|
| `FixedSize` | 固定数量 |
| `PercentSizer` | 按可用资金百分比 |
| `AllInSizer` | 全仓 |
| `ATRSizer` | ATR 波动率动态调仓（单笔风险 / (ATR × 合约乘数)） |
| `KellySizer` | Kelly 公式（默认 half-Kelly） |
| `RiskParitySizer` | 风险平价（等风险贡献） |
| `EqualWeightSizer` | 等权分配 |

### 3.12 券商网关（`python/akquant/gateway/`）

**协议抽象**：
- `MarketGateway` — 行情接口（连接/断开/订阅/行情回调）
- `TraderGateway` — 交易接口（下单/撤单/查询/成交回报）
- `GatewayBundle` — 行情网关 + 交易网关 + 元数据

**统一模型**：`UnifiedOrderRequest`、`UnifiedOrderSnapshot`、`UnifiedTrade`、`UnifiedExecutionReport`、`UnifiedAccount`、`UnifiedPosition`

**已适配券商**：
| 网关 | 券商 | 资产类型 |
|------|------|----------|
| `ctp_adapter` + `ctp_native` | CTP 期货 | 期货 |
| `miniqmt` + `miniqmt_xtquant` | MiniQMT | 股票 |
| `ptrade` | PTrade | 股票（placeholder） |

**基础设施**：
- `factory.py` — 网关工厂，按 broker 名称创建 `GatewayBundle`
- `registry.py` — 插件式券商注册（`register_broker()`）
- `mapper.py` — 券商状态/错误码映射为统一枚举

### 3.13 优化引擎（`python/akquant/optimize/`）

| 子模块 | 功能 |
|--------|------|
| `_grid_search.py` | 参数网格搜索 |
| `_walk_forward.py` | Walk-Forward 滚动前进优化 |
| `_worker.py` | 单次回测执行、多进程支持 |
| `_data.py` | 数据准备、`OptimizationResult` 结果封装 |

### 3.14 可视化（`python/akquant/plot/`）

| 模块 | 功能 |
|------|------|
| `dashboard.py` | 权益/回撤/月度收益面板，支持 rangeselector 和 updatemenus |
| `comparison.py` | 多策略对比面板（权益叠加、回撤对比、指标表） |
| `report.py` | HTML 报告生成（门面） |
| `_chart_builder.py` | 图表 HTML（权益曲线、回撤、热力图） |
| `_table_builder.py` | 指标表格、基准对比、交易分析 |

---

## 四、数据流

### 4.1 回测流程

```
用户代码                    Python 层                         Rust 层
─────────                  ──────────                        ──────────
run_backtest(config)
    │
    ├── 解析配置
    ├── 加载数据 → DataFeed
    ├── 构建 Engine
    │   ├── 注册标的
    │   ├── 设置市场模型
    │   ├── 配置风控
    │   └── 设置执行策略
    ├── 注册策略槽
    │
    └── engine.run()
            │
            │                               PipelineRunner
            │  ◄── Bar/Tick 事件 ─────────►  7 阶段管道处理
            │                                    │
            │                               StrategyProcessor
            │  ─── on_bar(bar) ──────────►  用户策略回调
            │  ◄── buy/sell 订单 ─────────   交易 API 调用
            │                                    │
            │                               ExecutionProcessor
            │                               风控检查 → 撮合 → 成交
            │                                    │
            │                               StatisticsProcessor
            │                               记录权益/持仓快照
            │
    └── 组装 BacktestResult
        ├── PerformanceMetrics（收益率、Sharpe、最大回撤等）
        ├── 权益/现金/保证金曲线
        ├── 成交记录
        └── 持仓快照
```

### 4.2 实盘流程

```
LiveRunner
    ├── create_gateway_bundle() → GatewayBundle(行情网关 + 交易网关)
    ├── 创建 Engine（RealtimeExecutionClient）
    ├── 注册策略
    │
    └── 事件循环
        ├── 行情网关 → on_tick/on_bar → StrategyProcessor
        ├── 用户策略 → 下单 → RealtimeExecutionClient → 交易网关
        └── 交易网关 → 成交回报 → 更新持仓/权益
```

---

## 五、关键设计模式

### 5.1 门面模式（Facade Re-export）

大型 Python 文件拆分后，原文件成为门面（import hub），实际代码移至 `_` 前缀子模块。所有公共 import 路径保持不变：

```python
# talib/funcs.py（门面）
from ._math import ABS, SQRT, ...           # noqa: F401
from ._overlays import SMA, EMA, RSI, ...   # noqa: F401
from ._momentum import MACD, BBANDS, ...    # noqa: F401
```

### 5.2 管道模式（Pipeline）

引擎采用固定序列的处理器管道，每个处理器独立职责，通过 `Event` 枚举传递数据。

### 5.3 策略委托模式

`Strategy` 基类的交易方法委托至 `strategy_trading_api.py` 中的独立函数，订单组逻辑委托至 `strategy_order_groups.py`。保持 Strategy 类接口不变的同时降低单文件复杂度。

### 5.4 多策略槽（Strategy Slot）

引擎支持多个策略并发运行，每个策略通过 `StrategySlot` 获得独立的上下文、风控预算和持仓追踪，互不干扰。

---

## 六、测试体系

| 测试类别 | 覆盖范围 | 文件数 |
|----------|----------|--------|
| 引擎核心 | 订单生命周期、多资产、多策略、流式、热启动、保证金 | `test_engine.py` |
| 策略扩展 | 事件回调、订单组、定时器、ML 集成 | `test_strategy_extras.py` |
| 技术指标 | 后端精度、API 兼容性、K 线形态 | `test_talib_*.py` |
| 风控规则 | 组合级/策略级规则、强制平仓 | `test_account_risk_rules.py` |
| 网关集成 | CTP、MiniQMT、工厂、注册表 | `test_gateway_*.py` |
| 因子引擎 | 表达式解析、算子、多步执行 | `test_factor_*.py` |
| 黄金回归 | 算法变更检测 | `tests/golden/` |
| 文档验证 | API 示例、链接检查 | `test_docs_*.py` |

运行命令：
```bash
uv run pytest                                          # 全量测试
uv run pytest tests/test_engine.py -k "test_name"      # 单个测试
./scripts/cargo-test.sh -q                              # Rust 单元测试
uv run python tests/golden/runner.py --generate-baseline  # 更新黄金基线
```

---

## 七、构建与发布

```bash
uv sync                          # 安装依赖
uv run maturin develop           # 编译 Rust 扩展
uv run ruff check python/akquant # Lint
uv run mypy python/akquant       # 类型检查
./scripts/dev-check.sh           # 快速验证（build + lint + smoke）
```

发布流程：Tag-push → maturin-action → 多平台 wheel（Linux x86_64/aarch64/musl、Windows x64、macOS aarch64）→ PyPI 自动发布。

---

## 八、项目规模

| 层 | 代码行数 | 文件数 |
|----|----------|--------|
| Rust 核心 | ~25,000 | 40+ |
| Python 层 | ~29,000 | 60+ |
| 测试 | ~19,000 | 43 |
| **合计** | **~73,000** | **140+** |
