# 开发审核文档：TWAP Fill Strategy + TensorFlowAdapter

## 一、TensorFlowAdapter（P2，纯 Python）

### 新增文件/类

**`python/akquant/ml/model.py` — `TensorFlowAdapter` 类（约 120 行，第 308 行起）**

遵循已有的 `PyTorchAdapter` 模式，实现 `QuantModel` 抽象接口：

| 方法 | 功能 |
|------|------|
| `__init__(model, optimizer, loss_fn, epochs, batch_size, device)` | 延迟导入 tensorflow，保存初始权重用于非增量训练重置 |
| `fit(X, y)` | 支持 incremental/non-incremental 模式，使用 `tf.GradientTape` 手动训练循环 |
| `predict(X)` | `model(X, training=False)` 返回 numpy 数组 |
| `save(path)` | `model.save(path)` SavedModel 格式 |
| `load(path)` | `tf.keras.models.load_model(path)` |

**审核要点：**
- [ ] 延迟导入：所有 `import tensorflow` 在方法内部，未安装时不会影响模块加载
- [ ] 非增量训练：通过 `initial_weights` 重置网络权重
- [ ] 输出处理：处理了 list/tuple 输出和 squeeze 维度

### 配套修改

| 文件 | 修改 |
|------|------|
| `python/akquant/ml/__init__.py` | 导出 `TensorFlowAdapter` |
| `pyproject.toml` `[project.optional-dependencies] ml` | 添加 `"tensorflow>=2.12.0"` |
| `pyproject.toml` `[project.optional-dependencies] full` | 添加 `"tensorflow>=2.12.0"` |
| `pyproject.toml` `[[tool.mypy.overrides]] module` | 添加 `"tensorflow.*"` |

---

## 二、TWAP Fill Strategy（P1，Rust + Python）

### 架构设计

TWAP 订单**留在正常撮合队列**中，每个 bar 通过 `TwapScheduler` 限制成交量，订单以 `PartiallyFilled` 状态跨 bar 存活。

```
Bar 1: Order(qty=1000, twap_bars=5) → fill 200 → PartiallyFilled
Bar 2: remaining=800 → fill 200 → PartiallyFilled
...
Bar 5: remaining=200 → fill 200 → Filled
```

**均匀分配公式：** `slice = remaining / (num_bars - bars_elapsed + 1)`
- 避免最后 bar 因浮点截断导致剩余量不为零

### Rust 层修改

#### 1. `src/model/types.rs` — 类型扩展

- `PriceBasis` 枚举新增 `TwapWindow` 变体
- `ExecutionPolicyCore` 结构体新增 `twap_bars: u32` 字段（默认 0）
- 所有构造 `ExecutionPolicyCore` 的位置已更新（6 处）

**审核：** 全部 `ExecutionPolicyCore { ... }` 构造点是否都添加了 `twap_bars: 0`

#### 2. `src/execution/twap.rs` — **新文件**（约 120 行）

| 结构/方法 | 功能 |
|-----------|------|
| `TwapState` | 每个订单的 TWAP 状态（num_bars, bars_elapsed） |
| `TwapScheduler::register()` | 注册 TWAP 订单追踪 |
| `TwapScheduler::on_bar()` | 递增所有活跃订单的 bar 计数 |
| `TwapScheduler::slice_quantity()` | 计算当前 bar 的最大成交量 |
| `TwapScheduler::cancel()` | 取消追踪 |
| `TwapScheduler::remove()` | 清理已完成订单 |

**审核要点：**
- [ ] `slice_quantity` 的均匀分配公式是否正确
- [ ] `bars_remaining` 为 0 时返回 `Decimal::ZERO`

#### 3. `src/execution/simulated.rs` — 核心集成

修改点（3 处）：

**a) `on_event()` 开头 — 递增 TWAP bar 计数：**
```rust
if matches!(event, Event::Bar(_)) {
    self.twap_scheduler.on_bar();
}
```

**b) 匹配循环中 — TWAP 成交量截断（第 236-265 行）：**
- 匹配器返回成交后，检查订单是否为 TWAP
- 首次遇到时注册到 scheduler
- 调用 `slice_quantity()` 截断 `trade.quantity`

**审核要点：**
- [ ] 截断逻辑在保证金检查之前执行，确保不会超量成交
- [ ] TWAP 订单用 IOC 而非 GTC 时行为是否正确（当前用引擎级 policy，非 IOC）

**c) 清理段 — 移除已完成 TWAP 追踪：**
```rust
for id in &finished_ids {
    self.twap_scheduler.remove(id);
}
```

#### 4. `src/execution/common.rs` — 价格计算回退

`PriceBasis::TwapWindow` 回退到 OHLC4 均价计算（TWAP 子切片的实际成交价由引擎级 policy 决定）。

#### 5. `src/engine/python.rs` — Python 绑定

- `set_fill_policy()` 新增 `twap_bars` 参数，默认值 0
- `get_fill_policy()` 返回 4 元组（新增 `twap_bars`）
- `twap_window` 的 bar_offset 验证已加入

**审核：** `#[pyo3(signature = (..., twap_bars=0))]` 确保向后兼容

### Python 层修改

| 文件 | 修改 |
|------|------|
| `python/akquant/backtest/_types.py` | `twap_window` 从 `_RESERVED` 移到 `_SUPPORTED`；添加默认 bar_offset |
| `python/akquant/backtest/_execution.py` | `_resolve_execution_policy()` 处理 `twap_window` basis，校验 `twap_bars > 0` |
| `python/akquant/backtest/engine.py` | 两处 `set_fill_policy()` 调用传递 `twap_bars` |
| `python/akquant/akquant.pyi` | 类型存根更新 |

### 使用方式

```python
from akquant.backtest import run_backtest

result = run_backtest(
    strategy,
    data=data,
    fill_policy={
        "price_basis": "twap_window",
        "twap_bars": 5,
        "temporal": "same_cycle",
    },
)
```

### 测试覆盖

| 测试文件 | 测试数 | 覆盖内容 |
|----------|--------|----------|
| `tests/test_fill_policy.py` | 10 | twap_window set/get、twap_bars 校验、bar_offset 校验、各种 bar count |
| `tests/test_engine.py` | 161 | 全量回归测试，包含 set_fill_policy roundtrip |

全部 171 测试通过。

---

## 三、已知限制 / 后续增强

1. **TWAP 仅支持 Market 订单** — 限价 TWAP 未实现
2. **无 bid/ask 模型** — TWAP 切片使用 OHLC4 均价
3. **手续费按每 bar 切片计算** — 可能有微小累积误差
4. **VWAP 多 bar 累积** — 仍在 `_RESERVED` 中，未实现
5. **TensorFlowAdapter 无单元测试** — 需要 TF 运行环境，已添加到 optional deps
