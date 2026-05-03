# AKQuant 功能树

> 更新日期：2026-05-03
> 基于 v0.2.8 开发分支代码扫描

**[总体设计方案与功能介绍](docs/zh/reference/design-overview.md)** — 完整的架构说明、模块详解、数据流与设计模式文档。

---

## 1. Rust 引擎 (`src/`)

### 1.1 核心引擎 (`src/engine/`)
| 类/功能 | 说明 |
|---------|------|
| `Engine` (pyclass) | 回测引擎主入口，Python 绑定 |
| `core.rs` | 管道式处理器编排 (~1100 行) |
| `python.rs` | PyO3 方法暴露给 Python |

### 1.2 领域模型 (`src/model/`)
| 类/功能 | 说明 |
|---------|------|
| `Bar`, `Tick`, `Timer` | 行情事件 |
| `Order`, `Trade` | 订单/成交 |
| `Instrument` | 标的定义（lot_size, price_tick 等） |
| `OrderType` | Market, Limit, StopMarket, StopLimit, StopTrail, StopTrailLimit |
| `PriceBasis` | Open, Close, Ohlc4, Hl2, **MidQuote**, **Typical**, **VwapBar** |
| `TimeInForce` | GTC, IOC, FOK |
| `ExecutionPolicy` | 价格基准 + bar 偏移 + 时态模式 |

### 1.3 执行 (`src/execution/`)
| 模块 | 说明 |
|------|------|
| `common.rs` | 通用撮合逻辑（穿透检查、Bar 内止损、滑点） |
| `stock.rs` | A 股撮合（T+1、涨跌停、整手） |
| `futures.rs` | 期货撮合（保证金、多头/空头） |
| `option.rs` | 期权撮合 |
| `crypto.rs` | 加密货币撮合 |
| `forex.rs` | 外汇撮合 |

### 1.4 市场模型 (`src/market/`)
| 类 | 说明 |
|----|------|
| `SimpleMarket` | 通用市场模型 |
| `ChinaMarket` | A 股（T+1、涨跌停 10%/20%、集合竞价） |
| `ChinaFuturesMarket` | 期货（保证金、结算） |
| `ChinaOptionsMarket` | 期权 |
| `FundMarket` | 基金（T+1） |

### 1.5 风控 (`src/risk/`)
| 功能 | 说明 |
|------|------|
| `RiskManager` (pyclass) | 组合级风控 |
| 策略级风控 | max_order_value, max_order_size, max_position_size, max_daily_loss, max_drawdown |
| **`OptionGreekRiskRule`** | **期权 Greek 风控（Delta/Gamma/Vega 限额、按标的聚合、per-slot 预算、BSM 定价）** |
| 期货保证金风控 | `FuturesMarginRule` — 保证金检查 |
| 策略 Slot | 多策略并发，优先级/预算/冷却 |
| 风险预算模式 | portfolio budget, strategy budget, daily reset |

### 1.6 技术指标 (`src/indicators/`)
| 子模块 | 指标数 | 代表指标 |
|--------|--------|----------|
| `moving_average` | 73 | SMA, EMA, DEMA, TEMA, KAMA, MAMA, WMA, MACD, 数学函数 |
| `momentum` | 7 | RSI, CMO, MOM, ROC, ROCP, ROCR, WILLR |
| `trend` | 19 | ADX, ADXR, AROON, CCI, SAR, STOCH, LINEARREG*, BETA, CORREL |
| `volatility` | 11 | ATR, NATR, STDDEV, BollingerBands, AVGPRICE, TYPPRICE |
| `volume` | 5 | AD, ADOSC, BOP, MFI, OBV |
| **`candlestick`** | **20** | **CDLDOJI, CDLHAMMER, CDLHANGINGMAN, CDL_ENGULFING, CDL_HARAMI, CDL_MORNINGSTAR, CDL_EVENINGSTAR, CDL_3BLACKCROWS, CDL_3WHITESOLDIERS, CDL_SHOOTINGSTAR, CDLPIERCING, CDLDARKCLOUDCOVER, CDLHARAMICROSS, CDLMARUBOZU, CDLKICKING, CDLSPINNINGTOP, CDLRISEFALL3METHODS, CDLTHRUSTING, CDLINNECK, CDLONNECK** |
| **合计** | **135** | |

### 1.7 定价与 Greeks (`src/pricing/`)
| 功能 | 说明 |
|------|------|
| `bsm_price()` | Black-Scholes-Merton 欧式期权定价 |
| `calculate_greeks()` | Delta/Gamma/Theta/Vega/Rho 计算 |
| `implied_volatility()` | Newton-Raphson 隐含波动率求解 |
| `time_to_expiry()` | YYYYMMDD → 年化时间转换 |
| `calculate_option_greeks()` (Python) | Python 绑定，策略可直接调用 |
| `calculate_implied_volatility()` (Python) | IV 求解 Python 绑定 |

### 1.8 其他 Rust 模块
| 模块 | 说明 |
|------|------|
| `src/data/` | DataFeed, BarAggregator, 批量数组转换 |
| `src/analysis/` | BacktestResult, PerformanceMetrics |
| `src/statistics/` | 权益/现金/保证金曲线、持仓快照 |
| `src/margin/` | 保证金计算器（期货、**交易所标准期权保证金公式**） |
| `src/settlement/` | 结算管理（到期、期权处理） |
| `src/pipeline/` | 事件驱动管道处理器 |
| `src/portfolio.rs` | 组合管理（持仓、现金、权益） |
| `src/order_manager.rs` | 订单生命周期管理 |
| `src/context.rs` | StrategyContext（Rust↔Python 桥接） |

---

## 2. Python 层 (`python/akquant/`)

### 2.1 策略框架
| 文件 | 说明 |
|------|------|
| `strategy.py` | `Strategy` 基类：on_bar, on_tick, on_timer, on_order |
| `strategy_types.py` | `StrategyRuntimeConfig`, `InstrumentSnapshot`, 类型别名 |
| `strategy_order_groups.py` | OCO / Bracket 订单组逻辑 |
| `strategy_order_events.py` | 订单事件（成交去重、键值记忆） |
| `strategy_trading_api.py` | 交易 API：buy, sell, order, cancel 等 |
| `strategy_events.py` | 事件系统 |
| `strategy_framework_hooks.py` | 框架钩子（on_start, on_stop, on_resume） |
| `strategy_ml.py` | ML 集成（信号预测、特征生成） |
| `strategy_position.py` | 持仓查询 |
| `strategy_scheduler.py` | 定时器调度 |
| `strategy_loader.py` | 策略加载器（文件路径、模块字符串、加密外部加载） |
| `strategy_history.py` | 历史数据访问 |
| `strategy_logging.py` | 日志 |
| `strategy_time.py` | 时间工具 |

### 2.2 回测引擎
| 文件 | 说明 |
|------|------|
| `backtest/engine.py` | `run_backtest()` / `run_warm_start()` 入口（门面 re-export） |
| `backtest/_types.py` | TypedDict、Policy 类型、解析函数 |
| `backtest/_execution.py` | 执行策略、流运行时、元数据附加 |
| `backtest/_instruments.py` | 资产/交易时段解析 |
| `backtest/_strategy_build.py` | FunctionalStrategy、策略实例构建 |
| `backtest/_validation.py` | 配置覆盖、风控验证、策略参数标准化 |
| `backtest/_data_loading.py` | 数据适配器辅助 |
| `backtest/result.py` | `BacktestResult`, `PerformanceMetrics`, 指标计算 |

### 2.3 配置
| 文件 | 说明 |
|------|------|
| `config.py` | BacktestConfig → StrategyConfig → RiskConfig，支持按标的覆盖 |

### 2.4 数据
| 文件 | 说明 |
|------|------|
| `data.py` | 数据加载接口 |
| `feed_adapter.py` | DataFeed 适配器（CSV、数据库等） |

### 2.5 资产类模块
| 模块 | 文件 | 能力 |
|------|------|------|
| `futures/` | models, rules, queries | FuturesContract, 保证金/手续费/名义价值计算 |
| `stock/` | models, rules | StockInfo, 手续费（含印花税）, T+1 判断 |
| `option/` | models, rules, queries | OptionContract, 期权保证金, 手续费, T+0 判断 |
| `fund/` | models, rules | FundInfo, 手续费, T+1 判断 |

### 2.6 技术指标 (TA-Lib 兼容)
| 文件 | 说明 |
|------|------|
| `talib/funcs.py` | 门面 re-export（保持所有函数名可导入） |
| `talib/_dispatch.py` | Rust 调度层（`_run_rust_*` 系列辅助函数） |
| `talib/_math.py` | 数学/变换类指标（LN, SQRT, EXP, ABS, ...） |
| `talib/_overlays.py` | 均线类指标（SMA, EMA, RSI, WMA, ...） |
| `talib/_momentum.py` | 动量/价格类指标（ATR, MACD, BBANDS, SAR, ...） |
| `talib/_trend.py` | 趋势类指标（ADX, AROON, CCI, STOCH, ...） |
| `talib/_candlestick.py` | K线形态（CDLDOJI, CDLHAMMER, ... 20 个） |
| `talib/__init__.py` | 公开导出 |
| `talib/backend.py` | 后端选择逻辑 (rust/python/auto) |
| `talib/core.py` | 内部辅助 |
| `indicator.py` | 增量更新版本：EMA, RSI, MACD（支持 update() 和 pickle） |

### 2.7 因子引擎
| 文件 | 说明 |
|------|------|
| `factor/engine.py` | 因子表达式求值 |
| `factor/ops.py` | 因子操作符库 |
| `factor/parser.py` | 表达式解析器 |

### 2.8 ML 适配器
| 适配器 | 说明 |
|--------|------|
| `SklearnAdapter` | scikit-learn，支持 partial_fit |
| `PyTorchAdapter` | PyTorch，增量学习控制 |
| `LightGBMAdapter` | LightGBM 原生 API |
| `XGBoostAdapter` | XGBoost 原生 API |

### 2.9 仓位管理器
| Sizer | 说明 |
|-------|------|
| `FixedSize` | 固定数量 |
| `PercentSizer` | 按权益百分比 |
| `AllInSizer` | 全仓 |
| `ATRSizer` | ATR 波动率动态调仓 |
| `KellySizer` | Kelly 公式（默认 half-Kelly） |
| `RiskParitySizer` | 风险平价 |
| `EqualWeightSizer` | 等权分配 |

### 2.10 可视化
| 文件 | 功能 |
|------|------|
| `plot/dashboard.py` | `plot_dashboard` — 权益/回撤/月度收益面板 + rangeselector + updatemenus |
| `plot/comparison.py` | `plot_comparison` — 多策略对比面板（权益叠加/回撤/指标表） |
| `plot/report.py` | `plot_report` — HTML 报告入口（门面） |
| `plot/_svg_assets.py` | SVG / HTML 常量 |
| `plot/_chart_builder.py` | 图表 HTML 生成（权益曲线、回撤、热力图） |
| `plot/_table_builder.py` | 指标表格、基准对比、交易分析表格 |
| `plot/analysis.py` | 分析图表 |
| `plot/strategy.py` | 策略可视化 |
| `plot/utils.py` | check_plotly, get_color, make_subplots |

### 2.11 实盘/模拟
| 文件 | 说明 |
|------|------|
| `live.py` | `LiveRunner` — 实盘/模拟交易入口 |
| `live_helpers.py` | `_StrategyCallbackFanout`、工具函数 |
| `gateway/factory.py` | Gateway 工厂（broker metadata → asset_class → 市场模型选择） |
| `gateway/models.py` | UnifiedOrderRequest（含 broker_options） |
| `gateway/base.py` | Gateway 抽象基类 |
| `gateway/miniqmt.py` | MiniQMT 交易网关（bridge 插口） |
| `gateway/miniqmt_xtquant.py` | QMTXtQuantBridge（过渡方案，FutureWarning） |
| `gateway/ctp_adapter.py` | CTP 适配器 |
| `gateway/ctp_native.py` | CTP 原生接口 |
| `gateway/ptrade.py` | PTrade 网关（placeholder） |
| `gateway/registry.py` | 网关注册 |
| `gateway/mapper.py` | 标的映射 |

### 2.12 优化
| 文件 | 说明 |
|------|------|
| `optimize/__init__.py` | 门面 re-export（`run_grid_search`, `run_walk_forward`） |
| `optimize/_data.py` | 数据准备、OptimizationResult |
| `optimize/_worker.py` | 单次回测执行、多进程支持 |
| `optimize/_grid_search.py` | 网格搜索算法 |
| `optimize/_walk_forward.py` | 滚动前进算法 |

### 2.13 风控 (Python)
| 文件 | 说明 |
|------|------|
| `risk.py` | Python 侧风控辅助，含 Greek 限额配置桥接 |
| `config.py` | RiskConfig 含 `max_portfolio_delta/gamma/vega`、`slot_max_delta/gamma/vega`、`option_default_volatility` 等字段 |

### 2.14 其他
| 文件 | 说明 |
|------|------|
| `checkpoint.py` | 检查点保存/恢复 |
| `sizer.py` | 仓位管理器集合 |
| `params.py` | 参数定义 |
| `params_adapter.py` | 参数适配 |
| `analyzer_plugin.py` | 分析器插件 |
| `log.py` | 日志配置 |
| `utils/inspector.py` | 代码检查工具 |
| `utils/__init__.py` | 通用工具函数 |

---

## 3. 测试覆盖

### 引擎与策略
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_engine.py` | Rust Engine 绑定（订单生命周期、多资产、多策略、流式、热启动、保证金） |
| `test_strategy_extras.py` | 策略子类（事件回调、订单组、定时器、ML 集成、持仓管理） |
| `test_strategy_timers_indicators.py` | 定时器与指标集成 |
| `test_stop_orders.py` | 止损单生命周期（触发、成交、撤销） |
| `test_partial_filled_status.py` | 部分成交状态转换 |
| `test_fill_policy.py` | PriceBasis 填充策略 |
| `test_t_plus_one.py` | T+1 结算规则 |
| `test_portfolio.py` | 组合计算 |
| `test_orders_df.py` | 订单 DataFrame 导出 |
| `test_trades_df.py` | 成交 DataFrame 导出 |
| `test_quickstart_stream_consistency.py` | 流式 vs 非流式一致性 |
| `test_multisymbol_cross_section_consistency.py` | 多标的截面一致性（持仓追踪、PnL 精度） |

### 风控
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_account_risk_rules.py` | 组合级/策略级风控规则、强制平仓 |

### 技术指标
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_talib_backend.py` | 后端精度验证 |
| `test_talib_compat.py` | API 兼容性检查 |
| `test_talib_cdl.py` | K 线形态识别 |

### 网关与实盘
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_live_runner_broker_bridge.py` | LiveRunner broker 桥接 |
| `test_gateway_factory.py` | Gateway 工厂 |
| `test_gateway_miniqmt_xtquant.py` | MiniQMT Bridge |
| `test_gateway_ctp_adapter.py` | CTP 适配器 |
| `test_gateway_callbacks.py` | 网关回调注册与分发 |
| `test_gateway_mapper.py` | 券商状态/错误映射 |
| `test_gateway_registry.py` | 券商注册表 |
| `test_custom_matcher.py` | 自定义 Python Matcher |

### 资产模块
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_futures_module.py` | 期货模块 |
| `test_stock_module.py` | 股票模块 |
| `test_option_module.py` | 期权模块 |
| `test_fund_module.py` | 基金模块 |

### 因子与 ML
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_factor_engine.py` | 因子引擎（表达式解析、计划生成、多步执行） |
| `test_factor_ops.py` | 因子算子 |

### 可视化
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_plot_comparison.py` | 策略对比面板 |
| `test_report_plot_extensions.py` | 图表/报告生成 |
| `test_report_helpers.py` | 报告辅助函数 |
| `test_result_analysis_extensions.py` | 结果分析（指标计算） |

### 数据与配置
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_feed_adapter.py` | DataFeed 适配器（CSV、Parquet、回放、重采样） |
| `test_params_adapter.py` | 参数适配 |
| `test_inspector.py` | 策略检查器 |
| `test_p2_extensions.py` | Phase 2 扩展 |
| `test_examples_regression.py` | 示例回归测试 |

### 文档与版本
| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_docs_api_examples.py` | API 示例验证 |
| `test_docs_links.py` | 文档链接检查 |
| `test_version.py` | 版本号检查 |

### 回归测试
| 目录 | 说明 |
|------|------|
| `tests/golden/` | Golden（回归）测试，检测算法变更 |

---

## 4. 构建与发布

| 命令 | 说明 |
|------|------|
| `uv run maturin develop` | 编译 Rust 扩展 |
| `uv run pytest` | 全量测试 |
| `uv run ruff check` | Lint |
| `./scripts/cargo-test.sh -q` | Rust 单元测试 |
| `./scripts/dev-check.sh` | 快速验证（build + lint + smoke） |

发布：tag-push → maturin-action → 多平台 wheel → PyPI
