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

*   **[第 4 章：事件驱动回测原理](04_backtest_engine.md)**
    *   向量化 vs 事件驱动 ([examples/textbook/ch04_comparison.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch04_comparison.py))
    *   核心组件解析：Engine, Strategy, DataFeed
*   **[第 5 章：构建第一个策略](05_strategy.md)**
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
    *   案例：Alpha101 因子实战 ([examples/19_factor_expression.py](https://github.com/akfamily/akquant/blob/main/examples/19_factor_expression.py))

### 第五部分：从回测到实盘 (Live Trading)

*   **[第 15 章：实盘交易系统与运维](15_live_trading.md)**
    *   实盘与回测的差异处理
    *   CTP 接口配置与实盘部署 ([examples/textbook/ch14_live.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch14_live.py))
    *   风控与熔断机制

---

**配套代码**：请参考项目根目录下的 `examples/textbook/` 文件夹。
