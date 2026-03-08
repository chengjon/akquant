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
| CTP | Tick/Bar | Market/Limit/Stop(经映射) | Yes | Yes | Yes | 交易所相关 | 已有本地适配 |
| MiniQMT | Tick/Bar | Market/Limit | Yes | Yes | Yes | DAY/GTC | 已有本地适配 |
| PTrade | Bar(占位) | Market/Limit(占位) | Yes | 部分 | 部分 | DAY | 需增强 |

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

## 关联代码入口

- [factory.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/gateway/factory.py)
- [registry.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/gateway/registry.py)
- [base.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/gateway/base.py)
