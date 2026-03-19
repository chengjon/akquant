# 第 15 章：实盘交易系统与运维

量化投资的终极目标是实盘获利。从回测到实盘，不仅是代码环境的切换，更是对**系统稳定性**、**执行效率**和**风险控制**的全面考验。本章将介绍 `AKQuant` 的实盘架构，并深入探讨订单管理系统 (OMS)、风控系统 (RMS) 以及高可用部署方案。

## 本章实践入口

- 主示例：[examples/textbook/ch15_live_trading.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_live_trading.py)
- 进阶示例：[examples/textbook/ch15_strategy_loader.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch15_strategy_loader.py)
- 对应指南：[实盘函数式指南](../advanced/live_functional_quickstart.md)

## 快速运行与验收

```bash
python examples/textbook/ch15_live_trading.py
python examples/textbook/ch15_strategy_loader.py
```

验收要点：

1. 示例可启动并完成最小实盘流程演示。
2. 日志中可观察到订单状态、网关事件或风控检查信息。
3. 调整风控参数后，策略行为变化符合预期。

## 15.1 实盘架构与接口

### 15.1.1 回测与实盘的差异

| 维度 | 回测 (Backtest) | 实盘 (Live Trading) |
| :--- | :--- | :--- |
| **时间流** | 历史数据重放 (Replay) | 实时数据流 (Stream) |
| **成交机制** | 假设成交 (Perfect Fill) | 真实撮合 (Partial/Reject) |
| **延迟** | 零延迟 (Zero Latency) | 网络延迟 + 内部处理延迟 |
| **状态管理** | 内存状态 (Transient) | 持久化状态 (Persistent) |

### 15.1.2 交易接口 (Gateway)

`AKQuant` 通过适配器模式支持多种柜台接口：

*   **CTP (China Trading Platform)**：期货市场标准接口，支持行情与交易链路。
*   **MiniQMT**：面向本地 A 股交易生态的适配接口。
*   **PTrade**：可接入券商量化终端的适配接口。

在实盘模式下，`DataFeed` 切换为实时行情源，交易执行由对应 broker gateway 负责。

当内置网关不满足需求时，可以通过注册机制扩展自定义 broker，且注册 broker 会被工厂优先解析，再回退到内置 `ctp/miniqmt/ptrade`。

```python
from akquant import DataFeed
from akquant.gateway import create_gateway_bundle, register_broker

register_broker("demo", demo_builder)
bundle = create_gateway_bundle(
    broker="demo",
    feed=DataFeed(),
    symbols=["000001.SZ"],
)
```

建议结合以下文档落地：

*   [自定义 Broker 注册](../advanced/custom_broker_registry.md)
*   [自定义 Broker 生产接入清单](../advanced/custom_broker_production_checklist.md)

## 15.2 订单管理系统 (Order Management System, OMS)

OMS 是实盘交易的核心，负责维护订单的全生命周期状态。

### 15.2.1 订单状态机

实盘中的订单状态远比回测复杂，常见状态包括：

1.  **New**：策略已创建订单。
2.  **Submitted**：订单已提交到交易通道。
3.  **Accepted**：柜台/交易所确认接收。
4.  **PartiallyFilled**：部分成交。
5.  **Filled**：全部成交。
6.  **Cancelled**：已撤单。
7.  **Rejected**：废单（如资金不足、不在交易时间、风控拒绝）。

### 15.2.2 状态同步 (Synchronization)

策略持仓 (`Strategy Position`) 与柜台持仓 (`Broker Position`) 可能因网络丢包或人工干预而不一致。

*   **定时同步**：每隔 N 秒查询柜台持仓，强制覆盖本地状态。
*   **事件驱动**：通过 `on_order`、`on_trade`（以及可选 `on_broker_event`）实时更新状态并做审计落盘。

## 15.3 风险管理系统 (Risk Management System, RMS)

在实盘中，**风控前置 (Pre-trade Risk Check)** 是防止“乌龙指”的最后一道防线。

### 15.3.1 核心风控规则

1.  **单笔最大委托量 (Max Order Size)**：防止代码错误导致的天量下单。
2.  **资金使用率限制 (Margin Usage Limit)**：防止满仓操作，预留安全垫。
3.  **日内撤单次数限制**：交易所对频繁撤单有惩罚措施（如上期所 500 次）。
4.  **策略级止损**：当策略当日亏损超过 N% 时，强制平仓并停止运行。

## 15.4 算法交易 (Algorithmic Execution)

对于大资金，直接下单会产生巨大的**冲击成本 (Market Impact)**。算法交易旨在拆解大单，降低成本。

### 15.4.1 TWAP (Time Weighted Average Price)

时间加权平均价格算法。将大单均匀拆分到一段时间内执行。

*   **逻辑**：每隔 $t$ 秒，下单 $q$ 手。
*   **适用**：流动性均匀的市场。

### 15.4.2 VWAP (Volume Weighted Average Price)

成交量加权平均价格算法。根据历史成交量分布，在流动性好的时候多下单，流动性差的时候少下单。

*   **目标**：成交均价接近市场 VWAP。

## 15.5 实盘部署与运维

### 15.5.1 部署环境

*   **云服务器 (ECS)**：推荐使用靠近交易所机房的节点（如上海、深圳）以降低延迟。
*   **Docker 容器化**：确保实盘环境与测试环境完全一致，避免 "It works on my machine" 问题。

### 15.5.2 监控与报警

*   **心跳监测 (Heartbeat)**：确保程序存活。
*   **日志 (Logging)**：详细记录每一笔 Tick、Signal 和 Order。
*   **消息推送**：集成钉钉/飞书/邮件机器人，实时推送成交和异常信息。

### 15.5.3 代码示例：启动实盘

```python
--8<-- "examples/textbook/ch15_live_trading.py"
```

推荐进一步查看以下实盘脚本：

*   `examples/38_live_functional_strategy_demo.py`：函数式策略入口（paper / broker_live）。
*   `examples/39_live_broker_submit_order_demo.py`：`broker_live` 下最小下单闭环。
*   `examples/42_live_broker_event_audit_demo.py`：统一 broker 事件审计与策略归属追踪。
*   `examples/35_custom_broker_registry_demo.py`：自定义 broker 注册与工厂接入。

### 15.5.4 热启动与状态持久化 (Warm Start)

在准实盘/长会话回放场景中，系统可能会因网络波动或维护重启。为了保证策略状态（如指标缓存、持仓记录）不丢失，`AKQuant` 提供了**热启动**机制。

**1. 保存状态 (Checkpoint)**

在每日收盘后或定期调用 `save_snapshot`：

```python
import akquant as aq
# 保存当前引擎状态和策略变量
aq.save_snapshot(engine, strategy, "strategy_checkpoint.pkl")
```

**2. 恢复运行 (Restore)**

系统重启后，使用 `run_warm_start` 加载快照并注入新的数据源：

```python
# 加载最新的数据源 (包含历史数据 + 今日新数据)
data_feed = aq.CSVFeedAdapter(path_template="latest_data_{symbol}.csv")

engine_result = aq.run_warm_start(
    checkpoint_path="strategy_checkpoint.pkl",
    data=data_feed,
    symbols="rb2310",
)

# 获取恢复后的引擎和策略
engine = engine_result.engine
strategy = engine_result.strategy
```

`run_warm_start` 会恢复 checkpoint 中的策略实例，不会通过 `strategy_source/strategy_loader` 重新加载策略实现。

### 15.5.5 动态策略加载 (Strategy Loader)

在实盘与准实盘场景中，策略实现有时需要按运行时配置动态加载，而不是在脚本中静态 `import`。`AKQuant` 支持通过 `strategy_source + strategy_loader` 机制完成策略注入。

下面示例演示了两种加载方式：

1.  `python_plain`：从源码文件按类名加载策略。
2.  `encrypted_external`：由外部回调解密并返回策略类。

```python
--8<-- "examples/textbook/ch15_strategy_loader.py"
```

当你需要将“策略参数 + 策略代码来源 + 运行模式”统一交给调度平台管理时，这条路径比手工改脚本更稳健。完整参数说明可结合《运行时配置指南》一起使用。

你也可以使用通用示例 `examples/44_strategy_source_loader_demo.py` 作为最小验证入口，先在回测中验证策略装载链路，再切换到实盘调度。

## 15.6 高可用架构 (High Availability)

实盘系统最怕的不是亏损，而是**宕机**。一旦系统崩溃，持仓状态丢失，正在进行的订单无法撤销，后果不堪设想。

### 15.6.1 主备切换 (Primary-Backup)

构建两套完全相同的系统：

1.  **主机 (Master)**：负责接收行情、计算信号、发送订单。
2.  **备机 (Slave)**：实时接收行情和主机状态，但不发单。
3.  **心跳 (Heartbeat)**：主机每秒向备机发送心跳包。
4.  **切换 (Failover)**：当备机连续 N 秒未收到心跳，判定主机宕机，自动接管交易权限，并报警通知人工介入。

### 15.6.2 状态持久化 (Persistence)

内存中的状态（持仓、订单、信号）必须实时落地到数据库（如 Redis AOF 或 SQLite）。

*   **Crash Recovery**：程序重启后，首先读取数据库恢复现场，确保“断点续传”。

## 15.7 低延迟优化 (Low Latency)

对于高频交易 (HFT)，速度就是利润。

1.  **共置 (Co-location)**：将服务器托管在交易所机房（如上交所金桥数据中心），光纤直连，物理距离缩短至米级。延迟可从毫秒级 (ms) 降至微秒级 ($\mu s$)。
2.  **内核旁路 (Kernel Bypass)**：使用 Solarflare 网卡和 OpenOnload 技术，绕过操作系统内核，直接在用户态处理网络包，减少上下文切换。
3.  **CPU 亲和性 (CPU Affinity)**：将交易进程绑定到特定的 CPU 核心，独占 L1/L2 缓存，避免缓存失效 (Cache Miss)。
4.  **无锁编程 (Lock-free)**：在 C++ 或 Rust 中使用原子操作 (Atomic) 和无锁队列 (Ring Buffer) 替代互斥锁，避免线程阻塞。

## 15.8 监控体系 (Monitoring Stack)

仅仅有日志是不够的，我们需要可视化的仪表盘。

1.  **Prometheus**：时序数据库，采集系统指标。
    *   `strategy_latency`: 策略计算耗时。
    *   `order_latency`: 订单往返延时 (RTT)。
    *   `position_exposure`: 当前持仓敞口。
    *   `pnl_realtime`: 实时盈亏。
2.  **Grafana**：可视化展示。配置大屏，实时显示资金曲线、持仓分布、系统负载。
3.  **AlertManager**：报警中心。
    *   **P0 级报警**：程序崩溃、网络断开、资金不足。电话通知。
    *   **P1 级报警**：策略亏损超限、未成交订单过多。短信通知。
    *   **P2 级报警**：延迟抖动、CPU 高负载。邮件通知。

## 15.9 实盘事故复盘 (Post-Mortem)

前车之鉴，后事之师。

1.  **光大乌龙指 (2013)**：策略系统错误生成巨量市价单，且缺乏**资金校验**风控，导致瞬间买入 234 亿元股票，拉升上证指数 5%。
    *   **教训**：风控系统必须独立于交易系统，且拥有最高权限（“熔断机制”）。
2.  **骑士资本 (2012)**：由于部署失误，旧代码被错误激活，在 45 分钟内疯狂买卖，亏损 4.4 亿美元，导致公司破产。
    *   **教训**：**灰度发布**和**自动化部署**是生命线。新代码上线前必须在模拟盘 (Paper Trading) 充分验证。

## 15.10 硬件加速 (Hardware Acceleration)

当通用 CPU 的性能达到瓶颈时，我们需要借助专用硬件。

### 15.10.1 FPGA (Field-Programmable Gate Array)

FPGA 允许直接在硬件电路层面编程，将网络包处理、行情解析、订单构建等逻辑烧录到芯片中。

*   **延迟**：亚微秒级 (Sub-microsecond)。从接收行情到发出订单仅需 500ns。
*   **应用**：做市商 (Market Making)、高频套利。
*   **开发成本**：极高。需要使用 Verilog/VHDL 语言，调试困难。

### 15.10.2 GPU (Graphics Processing Unit)

GPU 擅长大规模并行计算。

*   **应用**：深度学习训练 (Training)、大规模期权定价 (Monte Carlo)。
*   **限制**：由于 PCIe 总线的延迟，GPU 不适合处理对延迟极度敏感的即时交易逻辑，更适合盘中实时计算复杂的因子或风险指标。

## 15.11 量化团队协作 (Team Collaboration)

量化交易不再是单打独斗的时代，而是一个工业化的流水线。

1.  **基金经理 (PM)**：制定顶层投资逻辑，管理投资组合风险，对最终盈亏负责。
2.  **量化研究员 (Quant Researcher)**：挖掘因子，构建模型，撰写研究报告 (Jupyter Notebook)。
3.  **量化开发 (Quant Developer)**：
    *   **平台开发**：维护回测引擎 (`AKQuant`)、数据清洗管线。
    *   **策略开发**：将研究员的 Python 代码重构为高性能的 C++/Rust 实盘代码。
4.  **数据工程师 (Data Engineer)**：负责大数据的采集、存储和清洗。
5.  **运维 (SRE)**：负责服务器维护、网络监控、故障排查。

## 本章小结

1. 实盘系统的核心挑战是稳定性、延迟与风险控制的平衡。
2. OMS、RMS 与网关适配是策略可上线运行的三大基础模块。
3. 工程化部署与监控体系决定了策略长期可运维性。

## 课后练习

1. 在示例中增加一条订单风控规则并验证触发日志。
2. 模拟一次网络中断，设计并验证恢复流程。
3. 记录一次完整订单生命周期并输出关键状态时间点。

## 常见错误与排查

1. 订单状态不同步：检查本地状态与柜台回报对账流程。
2. 异常延迟增大：排查网络链路、消息积压和策略阻塞代码。
3. 实盘风险失控：核对仓位限制、熔断阈值和报警通道是否生效。

---

**全书结语**：
恭喜你完成了《量化投资：从理论到实战》的全部课程！
我们从 Python/Rust 基础出发，构建了高性能回测引擎，探讨了股票、期货、期权等全资产类别的策略，最后落地到实盘交易系统。
量化投资是一场没有终点的马拉松。市场在变，对手在变，唯一不变的是我们要保持**对数据的敬畏**和**对逻辑的执着**。

**愿 Alpha 与你同在！**
