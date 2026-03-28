# 量化投资：从理论到实战——基于 AKQuant 框架

## 教材简介

本教材专为中国高校本科生及研究生（金融工程、计算机、统计学背景）设计，旨在填补理论与工程实践之间的鸿沟。

### 核心特色

*   **现代技术栈**：深入解析 Rust + Python 混合架构，掌握高性能量化系统的设计原理。
*   **中国本土化**：专注于 A 股（T+1、涨跌停）、国内期货（CTP接口）与期权市场。
*   **实战导向**：从数据清洗、策略回测到实盘交易的全链路覆盖，配套完整代码示例。

## 目录大纲

### 第一部分：量化基础与数据准备 (Foundations)

*   **[第 1 章：量化投资概述与环境搭建](01_foundations.md)**
    *   量化投资发展史与 Alpha/Beta 理论
    *   AKQuant 架构简介 (Rust Core + Python Wrapper)
    *   环境配置与 Hello World ([examples/textbook/ch01_quickstart.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch01_quickstart.py))
*   **[第 2 章：编程生存指南](02_programming.md)**
    *   Python for Quant: Pandas, NumPy, Matplotlib
    *   Rust 概念入门：类型系统与内存安全
    *   案例：数据处理实战 ([examples/textbook/ch02_programming.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch02_programming.py))
*   **[第 3 章：金融数据获取与处理](03_data.md)**
    *   时间序列分析基础
    *   AkShare 数据接口详解
    *   数据清洗与本地存储 ([examples/textbook/ch03_data.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch03_data.py))

### 第二部分：回测引擎架构 (The Engine)

*   **[第 4 章：事件驱动回测原理 (Event-Driven Architecture)](04_backtest_engine.md)**
    *   向量化 vs 事件驱动 ([examples/textbook/ch04_comparison.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch04_comparison.py))
    *   核心组件解析：Engine, Strategy, DataFeed
*   **[第 5 章：策略开发实战 (Strategy Implementation)](05_strategy.md)**
    *   策略生命周期与下单接口
    *   历史数据获取与防未来函数
    *   案例：双均线策略实现 ([examples/textbook/ch05_strategy.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch05_strategy.py))

### 第三部分：多资产策略开发 (Strategies)

*   **[第 6 章：A 股市场微观结构与策略实战](06_stock_a.md)**
    *   T+1 交易制度的工程实现
    *   涨跌停与滑点模拟
    *   案例：A 股交易规则演示 ([examples/textbook/ch06_stock_a.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch06_stock_a.py))
*   **[第 7 章：期货市场与衍生品策略](07_futures.md)**
    *   保证金与杠杆
    *   期权基础与 Greeks 风控
    *   案例：期货动量策略 ([examples/textbook/ch07_futures.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch07_futures.py))
*   **[第 8 章：期权定价与波动率策略](08_options.md)**
    *   核心要素与 Greeks
    *   案例：备兑看涨 (Covered Call) ([examples/textbook/ch08_options.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch08_options.py))
*   **[第 9 章：基金投资与资产配置理论](09_funds.md)**
    *   ETF/LOF 交易规则与免税优势
    *   可转债 T+0 与双低轮动
    *   现代投资组合理论 (MPT) 与 60/40 策略
    *   案例：ETF 网格交易 ([examples/textbook/ch09_funds.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch09_funds.py))
    *   案例：股债平衡策略 ([examples/textbook/ch09_portfolio.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch09_portfolio.py))

### 第四部分：评价、优化与高阶话题 (Advanced)

*   **[第 10 章：策略评价体系与风险指标](10_analysis.md)**
    *   夏普比率、最大回撤与归因分析
    *   案例：回测结果深入分析 ([examples/textbook/ch10_analysis.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch10_analysis.py))
*   **[第 11 章：参数优化与稳健性检验](11_optimization.md)**
    *   网格搜索与滚动回测 (WFO)
    *   案例：多进程参数优化 ([examples/textbook/ch11_optimization.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch11_optimization.py))
*   **[第 12 章：机器学习在量化中的应用](12_ml.md)**
    *   特征工程与模型预测
    *   基于 Scikit-learn 的择时策略 ([examples/textbook/ch12_ml.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch12_ml.py))
*   **[第 13 章：策略可视化与报表分析](13_visualization.md)**
    *   权益曲线与回撤图绘制
    *   案例：生成回测图表 ([examples/textbook/ch13_visualization.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch13_visualization.py))
*   **[第 14 章：高性能因子挖掘与表达式引擎](14_factor.md)**
    *   因子表达式的原理与优势
    *   Polars 高性能计算架构
    *   案例：Alpha101 因子实战 ([examples/textbook/ch14_factor.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch14_factor.py))
### 第五部分：从回测到实盘 (Live Trading)

*   **[第 15 章：实盘交易系统与运维](15_live_trading.md)**
    *   实盘与回测的差异处理
    *   主示例：实盘启动与网关接入 ([examples/textbook/ch15_live_trading.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_live_trading.py))
    *   进阶示例：动态策略加载与运行时注入 ([examples/textbook/ch15_strategy_loader.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_strategy_loader.py))
    *   风控与熔断机制

### 第六部分：指标工程与工具链 (Indicator Engineering)

*   **[第 16 章：AKQuant 指标全景与工程化使用](16_rust_indicators.md)**
    *   AKQuant 支持的 103 个指标分类、解释与 warmup 口径
    *   指标词典与教学脚手架联动（见 [AKQuant 指标全量说明](../guide/rust_indicator_reference.md)）

## 章节示例映射（主示例 / 进阶示例 / 对应指南）

| 章节 | 主示例 | 进阶示例 | 对应指南 |
| :--- | :--- | :--- | :--- |
| 第 1 章 | [ch01_quickstart.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch01_quickstart.py) | [01_quickstart.py](https://github.com/akfamily/akquant/blob/main/examples/01_quickstart.py) | [快速开始](../start/quickstart.md) |
| 第 2 章 | [ch02_programming.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch02_programming.py) | [17_readme_demo.py](https://github.com/akfamily/akquant/blob/main/examples/17_readme_demo.py) | [Python 基础](../guide/python_basics.md) |
| 第 3 章 | [ch03_data.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch03_data.py) | [37_feed_replay_alignment_demo.py](https://github.com/akfamily/akquant/blob/main/examples/37_feed_replay_alignment_demo.py) | [数据指南](../guide/data.md) |
| 第 4 章 | [ch04_comparison.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch04_comparison.py) | [25_streaming_backtest_demo.py](https://github.com/akfamily/akquant/blob/main/examples/25_streaming_backtest_demo.py) | [可观测性指南](../advanced/stream_observability.md) |
| 第 5 章 | [ch05_strategy.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch05_strategy.py) | [23_functional_callbacks_demo.py](https://github.com/akfamily/akquant/blob/main/examples/23_functional_callbacks_demo.py) | [策略指南](../guide/strategy.md) |
| 第 6 章 | [ch06_stock_a.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch06_stock_a.py) | [20_risk_management_demo.py](https://github.com/akfamily/akquant/blob/main/examples/20_risk_management_demo.py) | [量化基础](../guide/quant_basics.md) |
| 第 7 章 | [ch07_futures.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch07_futures.py) | [04_mixed_assets.py](https://github.com/akfamily/akquant/blob/main/examples/04_mixed_assets.py) | [策略指南](../guide/strategy.md) |
| 第 8 章 | [ch08_options.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch08_options.py) | [07_option_test.py](https://github.com/akfamily/akquant/blob/main/examples/07_option_test.py) | [量化基础](../guide/quant_basics.md) |
| 第 9 章 | [ch09_funds.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch09_funds.py) | [ch09_portfolio.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch09_portfolio.py) | [策略指南](../guide/strategy.md) |
| 第 10 章 | [ch10_analysis.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch10_analysis.py) | [33_report_and_analysis_outputs.py](https://github.com/akfamily/akquant/blob/main/examples/33_report_and_analysis_outputs.py) | [分析指南](../guide/analysis.md) |
| 第 11 章 | [ch11_optimization.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch11_optimization.py) | [02_parameter_optimization.py](https://github.com/akfamily/akquant/blob/main/examples/02_parameter_optimization.py) | [优化指南](../guide/optimization.md) |
| 第 12 章 | [ch12_ml.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch12_ml.py) | [10_ml_walk_forward.py](https://github.com/akfamily/akquant/blob/main/examples/10_ml_walk_forward.py) | [机器学习指南](../advanced/ml.md) |
| 第 13 章 | [ch13_visualization.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch13_visualization.py) | [11_plot_visualization.py](https://github.com/akfamily/akquant/blob/main/examples/11_plot_visualization.py) | [可视化指南](../guide/visualization.md) |
| 第 14 章 | [ch14_factor.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch14_factor.py) | [16_adj_returns_signal.py](https://github.com/akfamily/akquant/blob/main/examples/16_adj_returns_signal.py) | [因子指南](../guide/factor.md) |
| 第 15 章 | [ch15_live_trading.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_live_trading.py) | [ch15_strategy_loader.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_strategy_loader.py) | [实盘函数式指南](../advanced/live_functional_quickstart.md) |
| 第 16 章 | 暂无独立脚本（以指标词典驱动） | [45_talib_indicator_playbook_demo.py](https://github.com/akfamily/akquant/blob/main/examples/45_talib_indicator_playbook_demo.py) | [AKQuant 指标全量说明](../guide/rust_indicator_reference.md) |

---

**配套代码**：请参考项目根目录下的 `examples/textbook/` 文件夹。
