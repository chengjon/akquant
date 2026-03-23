# Chapter 11: Parameter Optimization and Robustness Validation

This chapter is currently maintained in Chinese first.

- Chinese chapter: [第 11 章：参数优化与稳健性检验](../../zh/textbook/11_optimization.md)
- Textbook home: [Chinese textbook index](../../zh/textbook/index.md)
- Practice links:
  - Primary example: [examples/textbook/ch11_optimization.py](https://github.com/akfamily/akquant/blob/main/examples/textbook/ch11_optimization.py)
  - Extended example: [examples/02_parameter_optimization.py](https://github.com/akfamily/akquant/blob/main/examples/02_parameter_optimization.py)
  - Guide: [Optimization Guide](../guide/optimization.md)

Windows note for parallel optimization (`max_workers > 1`):

- Define strategy classes in an importable module, not in `__main__`.
- Guard script entry with `if __name__ == "__main__":`.
- This is caused by Windows multiprocessing `spawn`, not by `execution_mode` semantics.
