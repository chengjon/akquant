# 第 1 章：量化投资概述与环境搭建

## 1.1 量化投资的定义与特征

**量化投资 (Quantitative Investment)** 是指借助现代统计学和数学方法，利用计算机技术从海量历史数据中寻找能够带来超额收益的多种“大概率”策略，并纪律严明地按照这些策略进行投资决策的过程。

与定性投资（Fundamental Investing）相比，量化投资具有以下显著特征：

1.  **纪律性 (Discipline)**：严格执行模型给出的信号，克服人性的贪婪与恐惧。
2.  **系统性 (Systematic)**：多层次（资产配置、行业选择、个股选择）、多角度（宏观、估值、成长、技术）地观察市场。
3.  **套利思想 (Arbitrage)**：寻找市场定价偏差，通过买入低估资产、卖出高估资产获利。
4.  **概率取胜 (Probability)**：不追求单笔交易的暴利，而是追求在大概率获利的策略下，通过长期重复交易积累财富。

### 1.1.1 核心流程 (Workflow)

一个标准的量化投资系统通常包含以下四个核心模块：

1.  **数据 (Data)**：
    *   **采集**：从交易所、数据商获取行情、财务、舆情等数据。
    *   **清洗**：处理缺失值、异常值，统一数据格式（ETL）。
2.  **策略 (Strategy)**：
    *   **建模**：基于金融逻辑或机器学习算法，构建交易信号。
    *   **回测**：在历史数据上验证策略的有效性。
3.  **交易 (Execution)**：
    *   **撮合**：模拟交易所的撮合机制（回测阶段）。
    *   **报单**：将策略信号转化为具体的买卖指令发送至柜台（实盘阶段）。
4.  **风控 (Risk Control)**：
    *   **事前**：限制单笔最大下单量、持仓集中度。
    *   **事中**：实时监控敞口风险、流动性风险。
    *   **事后**：归因分析，评估策略表现。

### 1.1.2 理论基础：从 CAPM 到多因子

量化投资的理论基石是 **现代投资组合理论 (MPT)** 和 **资本资产定价模型 (CAPM)**。

根据 CAPM，投资组合的预期收益率 $E(R_p)$ 可以分解为：

$$ E(R_p) = R_f + \beta_p (E(R_m) - R_f) + \alpha_p $$

其中：
*   $R_f$：无风险收益率（Risk-Free Rate），通常以国债收益率为锚。
*   $\beta_p (E(R_m) - R_f)$：**市场收益 (Beta)**。$\beta$ 衡量了组合对市场波动的敏感度。这是被动承担市场风险所获得的补偿。
*   $\alpha_p$：**超额收益 (Alpha)**。这是剔除市场因素后，由投资经理的主动管理能力带来的收益。

**量化投资的核心目标，通常是在控制 Beta 风险（甚至将 Beta 对冲至 0）的前提下，追求稳定且可持续的 Alpha 收益。**

### 1.1.3 有效市场假说 (EMH)

尤金·法玛 (Eugene Fama) 提出的 **有效市场假说 (Efficient Market Hypothesis)** 认为，如果在一个证券市场中，价格完全反映了所有可以获得的信息，那么就称这样的市场为有效市场。

*   **弱式有效**：价格已反映所有历史信息（技术分析无效）。
*   **半强式有效**：价格已反映所有公开信息（基本面分析无效）。
*   **强式有效**：价格已反映所有信息，包括内幕信息（所有分析均无效）。

**量化投资的前提是市场并非“强式有效”**。我们通过挖掘市场微观结构中的**非理性行为**或**信息不对称**，寻找定价偏差（Mispricing）并从中获利。

## 1.3 行为金融学 (Behavioral Finance)

传统金融学假设投资者是理性的 (Rational)，但现实中，人是情感驱动的。行为金融学揭示了导致市场无效的心理学根源。

1.  **前景理论 (Prospect Theory)**：
    *   由 Kahneman 和 Tversky 提出。人对损失的厌恶程度是对收益喜好程度的 2-2.5 倍。
    *   **现象**：投资者倾向于过早止盈（落袋为安），但死扛亏损（不愿意承认错误）。这解释了为什么动量策略（追涨杀跌）长期有效。

2.  **过度自信 (Overconfidence)**：
    *   投资者往往高估自己的信息优势和预测能力。
    *   **现象**：导致过度交易 (Over-trading)，推高了成交量和波动率，却降低了净收益。

3.  **羊群效应 (Herd Behavior)**：
    *   投资者倾向于模仿他人的行为，通过随大流来获得安全感。
    *   **现象**：导致资产价格泡沫的形成和破裂。

## 1.4 市场微观结构基础 (Market Microstructure)

宏观分析关注 GDP 和利率，微观结构关注**价格是如何形成的**。

### 1.4.1 限价订单簿 (Limit Order Book, LOB)

在指令驱动市场（如 A 股），所有未成交的限价单按照价格优先、时间优先的原则排列，形成 LOB。

*   **买一 (Bid 1)**：当前最高的买入价。
*   **卖一 (Ask 1)**：当前最低的卖出价。
*   **买卖价差 (Bid-Ask Spread)**：$Ask 1 - Bid 1$。衡量流动性的核心指标。价差越小，流动性越好，交易成本越低。

### 1.4.2 市场深度 (Market Depth)

指在特定价格水平上可交易的数量。深度越好，大单交易对价格的冲击 (Market Impact) 越小。

### 1.4.3 价格发现 (Price Discovery)

价格不是连续的曲线，而是通过买卖力量的博弈（吃单）瞬间跳变的。量化高频策略正是通过分析 LOB 的微观失衡（如大单压顶、撤单率）来预测短时间内的价格方向。

## 1.5 量化与主观的融合 (Quantamental)

**Quantamental = Quant + Fundamental**。

*   **量化 (Quant)**：擅长广度。能同时扫描 5000 只股票，处理海量数据，纪律性强，但对突发事件（如战争、政策突变）反应迟钝。
*   **主观 (Fundamental)**：擅长深度。能深入调研一家公司，理解商业模式和管理层，但覆盖面窄，易受情绪影响。

未来的趋势是二者的融合：
1.  **量化赋能主观**：用量化模型筛选出初选池，再由研究员深入调研。
2.  **主观赋能量化**：将研究员的逻辑（如供应链关系、行业景气度）转化为量化因子，增强模型的可解释性和适应性。

## 1.6 开发环境搭建

为了进行量化研究，我们需要搭建一套高效的开发环境。本教材推荐使用 **Python + Rust** 的混合架构。

### 1.6.1 Python 环境 (Miniconda)

Python 是量化领域最主流的语言，拥有丰富的生态库（Pandas, NumPy, Scikit-learn）。我们推荐使用 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 来管理 Python 环境。

> **国内镜像加速**：
> 1. **下载加速**：推荐从清华大学开源软件镜像站下载安装包：[https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/](https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda/)
> 2. **配置 Conda 源**：安装完成后，在终端执行以下命令以加速包的下载：
> ```bash
> conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
> conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge
> conda config --set show_channel_urls yes
> ```

安装完成后，打开终端（Windows 用户请打开 **Anaconda Powershell Prompt**，macOS/Linux 用户请打开 **Terminal**），创建一个新的环境：

```bash
conda create -n ak_env python=3.14
conda activate ak_env
```

### 1.6.2 安装 AKQuant

`akquant` 是一个基于 Rust 核心的高性能事件驱动量化回测框架。它结合了 Rust 的极致速度与 Python 的生态易用性，专为追求高性能回测与实盘一体化的量化开发者设计。

**核心特性**：

1.  **Rust 驱动的高性能**：底层撮合引擎、订单管理系统 (OMS) 和风控模块 (RMS) 均由 Rust 编写，彻底告别 Python 的 GIL 锁限制，回测速度比纯 Python 框架快 10-100 倍。
2.  **事件驱动架构 (Event-Driven)**：不同于简单的向量化回测，`akquant` 采用严格的时间序列事件驱动模型，能够精确模拟限价单 (Limit Order)、止损单 (Stop Order) 以及复杂的成交撮合逻辑，杜绝“未来函数”。
3.  **全资产覆盖**：原生支持 **股票 (Stock)**、**期货 (Futures)**、**期权 (Options)** 及 **基金 (Fund)** 等多种金融资产，并针对 A 股的 T+1 制度和涨跌停机制做了深度适配。
4.  **回测实盘一体化**：坚持 "Code Once, Run Anywhere" 理念。同一套策略代码，既可以在历史数据上回测，也可以直接切换到 CTP/XTP 等实盘接口进行交易。

在激活的 conda 环境中，运行以下命令安装（建议使用清华源加速）：

```bash
pip install akquant akshare pandas matplotlib -i https://pypi.tuna.tsinghua.edu.cn/simple
```

*   `akquant`: **高性能事件驱动量化框架**。作为本课程的核心，它提供了回测引擎、订单管理、风控模块等全套基础设施，让用户只需专注于编写策略逻辑 (`Strategy`)。
*   `akshare`: **强大的开源财经数据接口库**。它专为 Python 量化交易员设计，提供了从股票、期货、期权、基金到宏观经济、另类数据等全方位的金融数据获取能力。其完全开源、免费且持续更新的特性，使其成为国内量化社区的首选数据源。
*   `pandas`: **Python 数据分析标准库**。在量化中，它几乎无处不在：我们用 `DataFrame` 存储历史行情，用 `Series` 计算技术指标，用 `Timestamp` 处理时间序列。掌握 Pandas 是成为量化开发者的第一道门槛。
*   `matplotlib`: **基础绘图库**。量化不仅是数字的游戏，更是图形的艺术。我们使用 Matplotlib 绘制资金曲线、K 线图和技术指标，直观地评估策略表现。此外，`akquant` 内置的绘图功能也是基于它构建的。

### 1.6.3 IDE 选择 (Trae / VS Code / PyCharm)

#### 1. Trae (AI Native IDE) - 强烈推荐

**Trae** 是字节跳动推出的一款 AI 原生 IDE，内置了强大的 **AI 编程助手**。
*   **Context7 深度集成**：能够理解你的整个项目上下文，准确回答关于 `akquant` 架构的问题。
*   **智能代码补全**：根据你的策略逻辑，自动补全 `on_bar` 中的代码。
*   **一键重构**：帮你把复杂的 Python 循环重构为高效的 Pandas 向量化操作。

#### 2. Visual Studio Code (VS Code)

微软出品的轻量级编辑器，插件生态极其丰富。
*   **推荐插件**：Python, Pylance, Jupyter, Markdown All in One。
*   **优点**：启动快，资源占用低，远程开发 (Remote-SSH) 体验极佳。

#### 3. PyCharm

JetBrains 出品的专业 Python IDE。
*   **优点**：代码分析能力最强，重构功能极其强大，调试体验好。
*   **版本选择**：初学者可以使用免费的 **Community 版**；**Professional 版** 额外支持 Jupyter Notebook、科学绘图和远程开发功能，适合进阶用户。

## 1.7 第一个量化策略 (Hello World)

让我们通过一个简单的例子来体验 `akquant` 的工作流程。我们将编写一个简单的策略：**买入并持有**。

### 代码示例

创建一个名为 `quickstart.py` 的文件，输入以下代码：

```python
--8<-- "examples/textbook/ch01_quickstart.py"
```

### 代码解析

1.  **数据准备**：
    我们使用 `akshare` 获取了 `sh600000` (浦发银行) 等几只股票的历史数据。`akquant` 支持直接传入 Pandas DataFrame。

2.  **策略定义 (`MyStrategy`)**：
    *   继承自 `akquant.Strategy`。
    *   `on_bar(self, bar)`：这是策略的核心。回测引擎会按时间顺序，每产生一根 K 线（Bar），就调用一次该函数。
    *   `self.order_target_percent(target_percent=0.33, symbol=symbol)`：下单函数，将仓位调整到目标比例（这里是 33%）。

3.  **回测配置与运行**：
    *   `BacktestConfig`：配置回测参数（如手续费、初始资金）。
    *   `aq.run_backtest`：启动回测引擎。

### 运行结果

在终端运行该脚本：

```bash
python quickstart.py
```

你将看到类似以下的输出日志：

```text
正在获取数据...
开始回测...
2026-02-24 20:29:07 | INFO | Running backtest via run_backtest()...
[2020-01-02 00:00:00] 首次买入 600000，目标仓位 95%
  [00:00:00] [########################################] 970/970 (0s)
==============================
回测结果摘要
==============================
BacktestResult:
                                            Value
start_time              2020-01-02 00:00:00+08:00
end_time                2023-12-29 00:00:00+08:00
duration                       1457 days, 0:00:00
total_bars                                    970
trade_count                                   0.0
initial_market_value                     100000.0
end_market_value                       66014.3989
total_pnl                                     0.0
unrealized_pnl                           -33957.0
total_return_pct                       -33.985601
annualized_return                       -0.098809
volatility                               0.168118
total_profit                                  0.0
total_loss                                    0.0
total_commission                          28.6011
max_drawdown                              36630.0
max_drawdown_pct                        36.568054
win_rate                                      0.0
sharpe_ratio                            -0.587735
calmar_ratio                            -0.270206
```

> *注：由于浦发银行 (600000) 在 2020-2023 年表现不佳，简单的买入持有策略并未盈利。但这正是回测的意义——验证策略在历史上的表现。*

### 结果解析

下表详细解释了回测结果中的各项核心指标。这些指标的计算逻辑均基于 `akquant` 源码实现。

| 指标 (Metric) | 含义 (Meaning) | 计算公式 / 逻辑 | 评价标准 |
| :--- | :--- | :--- | :--- |
| **Total Return Pct** <br> (累计收益率) | 策略从开始到结束的总收益百分比。 | $\frac{\text{Final Value} - \text{Initial Cash}}{\text{Initial Cash}} \times 100\%$ | 越高越好。正值代表盈利，负值代表亏损。 |
| **Annualized Return** <br> (年化收益率) | 策略的复合年均增长率 (CAGR)。 | $(1 + R_{total})^{\frac{1}{Years}} - 1$ <br> *注：将累计收益平摊到每一年，便于与其他理财产品比较。* | > 10% 优秀 <br> > 20% 卓越 |
| **Max Drawdown Pct** <br> (最大回撤率) | 策略在任一时间点，从历史最高点 (Peak) 到当前点的最大跌幅。 | $\max_{t} \frac{\text{Peak}_t - \text{Value}_t}{\text{Peak}_t} \times 100\%$ <br> *注：这是衡量风险最直观的指标。* | < 10% 优秀 <br> < 20% 良好 <br> > 30% 风险较高 |
| **Sharpe Ratio** <br> (夏普比率) | 衡量每承担一单位总风险（波动率），能获得多少超额收益。 | $\frac{R_{annual} - R_{free}}{\sigma_{annual}}$ <br> *注：$R_{free}$ 默认为 0，$\sigma_{annual}$ 为年化波动率。* | > 1.0 良好 <br> > 2.0 优秀 <br> < 0 不如空仓 |
| **Calmar Ratio** <br> (卡玛比率) | 衡量收益与最大回撤的比值，即“性价比”。 | $\frac{R_{annual}}{|\text{Max Drawdown}|}$ <br> *注：每承担 1% 的回撤风险，能换来多少年化收益。* | > 1.0 良好 <br> > 2.0 优秀 <br> < 0.5 性价比低 |
| **Volatility** <br> (年化波动率) | 收益率标准差的年化值，反映策略的稳定性。 | $\sigma_{daily} \times \sqrt{252}$ | 越低越稳定。 |
| **Win Rate** <br> (胜率) | 盈利交易次数占总交易次数的比例。 | $\frac{\text{Winning Trades}}{\text{Total Trades}}$ | 取决于策略类型。趋势策略通常胜率低但盈亏比高。 |

通过这个简单的 "Hello World"，我们跑通了量化回测的全流程：数据 -> 策略 -> 回测 -> 结果。

---

**恭喜！** 你已经完成了量化投资的第一步。在下一章中，我们将深入探讨数据的获取与处理，这是量化大厦的基石。
