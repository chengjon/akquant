# feed.resample / feed.replay API 草案

## API 提案

```python
resampled = feed.resample(
    freq="15min",
    agg={"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"},
    label="right",
    closed="right",
)

replayed = feed.replay(
    freq="1h",
    align="session",
    day_mode="trading",
    emit_partial=False,
    session_windows=[("09:30", "11:30"), ("13:00", "15:00")],
)
```

## 当前落地（最小可用）

- `BasePandasFeedAdapter` 已支持：
  - `resample(freq, agg=None, label="right", closed="right", emit_partial=True)`
  - `replay(freq, align="session", emit_partial=False, agg=None, label="right", closed="right")`
- 两者均返回可直接传入 `run_backtest(data=...)` 的适配器对象。
- 当前 `replay(align="session")` 已支持按交易日分区聚合，`emit_partial=False` 时按日丢弃尾部未闭合窗口。
- 可通过 `session_windows` 进一步按日内交易时段分区（例如午休前后分段），减少跨时段混合聚合。
- `align` 当前支持三种语义：
  - `session`：按交易日分区，可叠加 `session_windows`。
  - `day`：按日分区，不接收 `session_windows`，并支持 `day_mode`。
  - `global`：按全局时间轴聚合，不按交易日切段。
- `day_mode` 当前支持：
  - `trading`：按请求时区下的本地交易日切分。
  - `calendar`：按 UTC 自然日切分。

## 语义锁定

### resample

- 输入：原始 `Bar/Tick` 流。
- 输出：按目标频率聚合后的 Bar 流。
- 默认聚合：
  - `open=first`
  - `high=max`
  - `low=min`
  - `close=last`
  - `volume=sum`
- 边界：默认 `label=right, closed=right`。

### replay

- 输入：高频数据。
- 输出：按低频时钟重放的事件流。
- `align=session`：按交易时段边界对齐。
- `emit_partial=False`：未闭合窗口不发出。

## 事件对齐策略

- 时区统一：内部统一 UTC，展示层可转本地时区。
- 会话优先：跨日、午休等边界以 market session 为准。
- 缺口策略：
  - 价格列沿用“无成交不补值”。
  - volume 默认置 0。

## 一致性校验

- 与 pandas `resample` 在同参数下做结果比对。
- 对齐误差允许仅限浮点精度范围。
- 回测与实时流使用同一聚合实现。

## 与示例迁移

- 目标替代 [14_multi_frequency.py](file:///c:/Users/albert/Documents/trae_projects/akquant/examples/14_multi_frequency.py) 中手写 `pandas.resample` 流程。
- 新示例结构：
  - `feed_1m = ...`
  - `feed_15m = feed_1m.resample("15min")`
  - 策略内直接消费双时框 feed。
