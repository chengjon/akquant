# Analyzer 插件接口草案

## 目标

- 让第三方分析器无需修改内核即可接入回测流程。
- 将固定分析输出扩展为“内置 + 插件”双轨体系。

## 最小生命周期

```python
class AnalyzerPlugin(Protocol):
    name: str
    def on_start(self, context: dict[str, Any]) -> None: ...
    def on_bar(self, context: dict[str, Any]) -> None: ...
    def on_trade(self, context: dict[str, Any]) -> None: ...
    def on_finish(self, context: dict[str, Any]) -> dict[str, Any]: ...
```

实现草案：
- [analyzer_plugin.py](file:///Users/albert/Documents/trae_projects/akquant/python/akquant/analyzer_plugin.py)

## 插件管理

- `AnalyzerManager.register(plugin)`
- `AnalyzerManager.on_start/on_bar/on_trade/on_finish`
- 输出结构：`{plugin_name: plugin_result}`

## 上下文约定（v0）

- `engine`
- `strategy`
- `bar`（在 `on_bar` 时存在）
- `trade`（在 `on_trade` 时存在）
- `result`（在 `on_finish` 时存在）

## 模板插件

- `AnalyzerTemplate`
- 示例输出：`seen_trades`

## 分发建议

- 包发现机制采用 `entry_points`。
- 每个插件包声明：
  - 支持 AKQuant 版本范围
  - 插件名称
  - 入口类

## 验收

- 插件异常隔离策略可配置（继续/中断）。
- 报告输出可附加插件 section。
- 提供至少 2 个官方示例插件。
