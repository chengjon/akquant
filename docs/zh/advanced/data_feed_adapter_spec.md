# DataFeedAdapter 规范草案

## 目标

- 统一外部数据源接入方式，降低“先 ETL 再回测”的门槛。
- 明确 schema、时区、企业行为字段，减少数据漂移。
- 为缓存目录和重建流程提供统一协议。

## 接口抽象

```python
class DataFeedAdapter(Protocol):
    name: str
    def load(self, request: FeedSlice) -> pd.DataFrame: ...
```

`FeedSlice` 字段：
- `symbol`
- `start_time`
- `end_time`
- `timezone`

## 最小 schema

- 索引：`DatetimeIndex`
- 必需列：`open high low close volume`
- 推荐列：`symbol`
- 可选列：`adj_factor dividend split`

## 官方最小适配器（第一批）

- `CSVFeedAdapter`
  - 输入：`path_template=".../{symbol}.csv"`
  - 输出：标准 schema DataFrame
- `ParquetFeedAdapter`
  - 输入：`path_template=".../{symbol}.parquet"`
  - 输出：标准 schema DataFrame

实现位置：
- [feed_adapter.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/feed_adapter.py)

## 缓存规范 v0

- 根目录：`~/.akquant/feed_cache/`
- 目录层级：`{adapter}/{symbol}/{freq}/`
- 元数据文件：`meta.json`
  - `adapter`
  - `symbol`
  - `timezone`
  - `schema_hash`
  - `generated_at`

## 校验规则

- 校验索引是否单调递增。
- 校验 OHLCV 必需列是否完整。
- 校验重复时间戳与空值比例。
- 校验时区一致性。

## 迁移建议

- 现有 `DataFrame/Dict/List[Bar]` 入口保持不变。
- `run_backtest` 后续增加 `feed_adapter=` 可选参数。
- 适配器失败必须抛出结构化错误，包含 `symbol/path/hint`。
