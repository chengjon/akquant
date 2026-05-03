"""Walk-Forward Optimization (WFO) 算法."""

from typing import Any, List, Mapping, Optional, Sequence, Type, Union, cast

import pandas as pd

from ..backtest import run_backtest
from ..strategy import Strategy
from ._data import (
    OptimizationData,
    _build_optimization_timeline,
    _filter_optimization_data_by_symbols,
    _normalize_symbol_values,
    _prepare_optimization_data,
    _resolve_optimization_backtest_kwargs,
    _slice_optimization_data,
)
from ._grid_search import run_grid_search


def run_walk_forward(
    strategy: Type[Strategy],
    param_grid: Mapping[str, Sequence[Any]],
    data: OptimizationData,
    train_period: int,
    test_period: int,
    metric: Union[str, List[str]] = "sharpe_ratio",
    ascending: Union[bool, List[bool]] = False,
    initial_cash: float = 100_000.0,
    warmup_period: int = 0,
    warmup_calc: Optional[Any] = None,
    constraint: Optional[Any] = None,
    result_filter: Optional[Any] = None,
    compounding: bool = False,
    timeout: Optional[float] = None,
    max_tasks_per_child: Optional[int] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    执行 Walk-Forward Optimization (WFO).

    将数据切分为多个 "训练集+测试集" 片段，滚动优化参数并验证。

    :param strategy: 策略类
    :param param_grid: 参数网格
    :param data: 回测数据 (支持 DataFrame 或 Dict[str, DataFrame])
    :param train_period: 训练窗口长度 (Bar数量)
    :param test_period: 测试窗口长度 (Bar数量)
    :param metric: 优化目标指标 (默认: "sharpe_ratio")，支持多字段排序列表。
                   对应 run_grid_search 的 sort_by 参数。
    :param ascending: 排序方向 (默认: False, 即降序)，支持单值或多值列表。
                      对应 run_grid_search 的 ascending 参数。
    :param initial_cash: 初始资金 (默认: 100,000.0)
    :param warmup_period: 基础预热长度 (Bar数量)
    :param warmup_calc: 动态预热计算函数 (可选)
    :param constraint: 参数约束函数 (可选)
    :param result_filter: 结果筛选函数 (可选)
    :param compounding: 是否使用复利拼接结果 (True=复利, False=累加盈亏, 默认: False)
    :param timeout: 单次优化任务超时时间 (秒)
    :param max_tasks_per_child: Worker 重启频率
    :param kwargs: 透传给 run_grid_search 和 run_backtest 的其他参数
    :return: 包含拼接后资金曲线的 DataFrame
    """
    kwargs = _resolve_optimization_backtest_kwargs(data, kwargs)
    requested_symbols = _normalize_symbol_values(kwargs.get("symbols"))
    prepared_data = _prepare_optimization_data(data)
    prepared_data = _filter_optimization_data_by_symbols(
        prepared_data,
        requested_symbols,
    )
    timeline = _build_optimization_timeline(prepared_data)
    total_len = len(timeline)
    if total_len < train_period + test_period:
        raise ValueError(
            f"Data length ({total_len}) is too short for "
            f"train ({train_period}) + test ({test_period})."
        )

    print(
        f"Starting Walk-Forward Optimization: Train={train_period}, "
        f"Test={test_period}, Total Bars={total_len}"
    )

    oos_results = []
    current_capital = initial_cash

    # 滚动窗口循环
    # Step size is test_period
    for i in range(0, total_len - train_period - test_period + 1, test_period):
        train_start_idx = i
        train_end_idx = i + train_period
        oos_start_idx = train_end_idx
        oos_end_idx = min(oos_start_idx + test_period, total_len)

        train_start_time = timeline[train_start_idx]
        train_end_exclusive = (
            timeline[train_end_idx] if train_end_idx < total_len else None
        )
        train_end_time = timeline[train_end_idx - 1]
        oos_start_time = timeline[oos_start_idx]
        oos_end_exclusive = timeline[oos_end_idx] if oos_end_idx < total_len else None
        oos_end_time = timeline[oos_end_idx - 1]
        train_data = _slice_optimization_data(
            prepared_data,
            train_start_time,
            train_end_exclusive,
        )

        print(
            f"\n=== Window {i // test_period + 1}: "
            f"Train [{train_start_time} - {train_end_time}] ==="
        )

        # 2. 样本内优化 (Optimization)
        opt_results = run_grid_search(
            strategy=strategy,
            param_grid=param_grid,
            data=train_data,
            sort_by=metric,
            ascending=ascending,
            return_df=True,
            warmup_calc=warmup_calc,
            constraint=constraint,
            result_filter=result_filter,
            initial_cash=initial_cash,
            timeout=timeout,
            max_tasks_per_child=max_tasks_per_child,
            **kwargs,
        )

        if isinstance(opt_results, list) or opt_results.empty:
            print(
                "Warning: Optimization failed or returned no results. Skipping window."
            )
            continue

        # 获取最佳参数
        best_row = opt_results.iloc[0]
        best_params = {k: best_row[k] for k in param_grid.keys()}

        # 显示排序指标的值
        metric_str = ""
        if isinstance(metric, list):
            metric_str = ", ".join([f"{m}={best_row.get(m, 0):.4f}" for m in metric])
        else:
            metric_str = f"{metric}={best_row.get(metric, 0):.4f}"

        print(f"  Best Params: {best_params} ({metric_str})")

        # 计算实际需要的预热期
        current_warmup = warmup_period
        if warmup_calc:
            try:
                current_warmup = max(current_warmup, warmup_calc(best_params))
            except Exception:
                pass

        slice_start_idx = max(0, oos_start_idx - current_warmup)
        slice_start_time = timeline[slice_start_idx]
        test_data_with_warmup = _slice_optimization_data(
            prepared_data,
            slice_start_time,
            oos_end_exclusive,
        )

        # 4. 样本外验证 (Backtest)
        # 使用最佳参数运行回测
        # 注意：这里我们使用一个新的 initial_cash 进行回测，后续再拼接
        backtest_kwargs = kwargs.copy()
        backtest_kwargs.update(best_params)
        backtest_kwargs["initial_cash"] = initial_cash
        backtest_kwargs["warmup_period"] = current_warmup

        print(f"  Test [{oos_start_time} - {oos_end_time}] (Warmup: {current_warmup})")

        bt_result = run_backtest(
            strategy=strategy, data=test_data_with_warmup, **backtest_kwargs
        )

        # 5. 提取并拼接结果
        equity_curve = bt_result.equity_curve

        if equity_curve.empty:
            print("  Warning: Empty equity curve in OOS.")
            continue

        # 处理时区不匹配问题
        idx = equity_curve.index
        # Cast to DatetimeIndex to access .tz
        dt_idx = (
            cast(pd.DatetimeIndex, idx) if isinstance(idx, pd.DatetimeIndex) else None
        )

        if (
            dt_idx is not None
            and dt_idx.tz is not None
            and oos_start_time.tzinfo is None
        ):
            # 如果结果有时区但原始数据没有，假设原始数据是本地时间并本地化
            try:
                oos_start_time = oos_start_time.tz_localize(dt_idx.tz)
            except Exception:
                # 如果失败 (例如可能是 UTC)，尝试转为 naive 进行比较
                equity_curve = equity_curve.tz_localize(None)
        elif (
            dt_idx is None or dt_idx.tz is None
        ) and oos_start_time.tzinfo is not None:
            equity_curve = equity_curve.tz_localize(oos_start_time.tzinfo)

        # 过滤时间段
        valid_equity = equity_curve[equity_curve.index >= oos_start_time]
        if valid_equity.empty:
            print("  Warning: No equity data in valid OOS period.")
            continue

        # 拼接逻辑
        if compounding:
            # 复利模式：计算收益率并累乘
            returns = valid_equity.pct_change().fillna(0)
            # 第一个点的收益率需要相对于"入场资金"计算
            first_ret = (valid_equity.iloc[0] - initial_cash) / initial_cash
            returns.iloc[0] = first_ret

            segment_df = pd.DataFrame({"return": returns})
            segment_df["equity"] = (
                current_capital * (1 + segment_df["return"]).cumprod()
            )
            current_capital = segment_df["equity"].iloc[-1]

        else:
            # 累加模式 (默认)：计算 PnL 并累加
            pnl = valid_equity - initial_cash

            # 调整后的净值 = 上一段结束资金 + 当前段PnL
            adjusted_equity = current_capital + pnl
            segment_df = pd.DataFrame({"equity": adjusted_equity})
            current_capital = adjusted_equity.iloc[-1]

        # 添加元数据
        segment_df["train_start"] = train_start_time
        segment_df["train_end"] = train_end_time
        for k, v in best_params.items():
            segment_df[k] = v

        oos_results.append(segment_df)

    if not oos_results:
        print("Walk-Forward Optimization produced no results.")
        return pd.DataFrame()

    # 6. 合并所有片段
    final_df = pd.concat(oos_results)

    # 填补空缺 (如果时间不连续) ? WFO 通常是连续的
    return final_df
