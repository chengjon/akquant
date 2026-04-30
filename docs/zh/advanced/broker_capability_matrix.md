# Broker Capability Matrix（模板 + 首批填充）

## 字段定义

- `market_data`: 行情接入能力（Tick/Bar）
- `order_entry`: 下单能力（Market/Limit/Stop/StopLimit）
- `cancel`: 撤单能力
- `execution_report`: 回报能力（订单状态、成交回报）
- `account`: 账户查询（资金、持仓）
- `tif`: 支持的 TimeInForce 集合
- `notes`: 语义差异或限制

## 能力矩阵（v0）

| Broker | market_data | order_entry | cancel | execution_report | account | tif | notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| IB | Tick/Bar | Market/Limit/Stop/StopLimit | Yes | Yes | Yes | DAY/GTC/IOC | 首批优先 |
| Oanda | Tick/Bar | Market/Limit/Stop | Yes | Yes | Yes | GTC/GTD/FOK/IOC | FX/CFD 语义 |
| CCXT | Tick/Bar(交易所相关) | Market/Limit(主) | Yes | Yes | Yes | 交易所相关 | 需按交易所分层 |
| CTP | Tick/Bar | Market/Limit(经映射) | Yes | Yes | 否 | GFD/IOC/FAK/FOK(经映射) | 行情 + 下单/撤单/回报已实现；账户、持仓、当日成交与柜台查询恢复待补 |
| MiniQMT | 否（占位） | Market/Limit(占位) | Yes(占位) | Yes(占位) | 部分（账户为构造参数，持仓为空） | DAY/GTC（占位） | 当前为纯内存占位实现，不连接真实 QMT |
| PTrade | 否（占位） | Market/Limit(占位) | Yes(占位) | Yes(占位) | 部分（账户为构造参数，持仓为空） | DAY/GTC（占位） | 当前为纯内存占位实现，不连接真实柜台 |

## 统一错误规范

- `UNSUPPORTED_ORDER_TYPE`
- `UNSUPPORTED_TIF`
- `BROKER_DISCONNECTED`
- `BROKER_RATE_LIMITED`
- `BROKER_REJECTED`

## 最小闭环验收

- 行情订阅成功并触发回调。
- 下单后能收到状态更新与成交回报。
- 撤单可追踪到最终状态。
- 账户与持仓查询返回非空结构。

> **注意**：以上是“生产接入的最小验收”，不是当前所有内置 broker 都已经满足的现状。以当前代码为准，CTP 还未满足“账户与持仓查询返回非空结构”，MiniQMT/PTrade 也还未满足“真实行情订阅成功并触发回调”。

## 关联代码入口

- [factory.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/factory.py)
- [registry.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/registry.py)
- [base.py](https://github.com/akfamily/akquant/blob/main/python/akquant/gateway/base.py)
