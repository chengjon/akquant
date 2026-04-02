# Chapter 4: Event-Driven Backtesting Principles

This chapter is currently maintained in Chinese first.

- Chinese chapter: [第 4 章：事件驱动回测原理 (Event-Driven Architecture)](../../zh/textbook/04_backtest_engine.md)
- New three-axis note: `fill_policy={"price_basis": "...", "bar_offset": 0_or_1, "temporal": "..."}` is now the recommended public style.
- Configuration layering note (highest to lowest): order-level > strategy-map level (`strategy_*`) > run-level > market defaults.
- T+1 scope note: `t_plus_one` currently remains a run/market-level switch, not a per-strategy layered setting.
- Textbook home: [Chinese textbook index](../../zh/textbook/index.md)
- Practice links:
  - Primary example: [examples/textbook/ch04_comparison.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch04_comparison.py)
  - Extended example: [examples/25_streaming_backtest_demo.py](https://github.com/akfamily/akquant/blob/main/examples/25_streaming_backtest_demo.py)
  - Guide: [Stream Observability Guide](../advanced/stream_observability.md)
