"""网格搜索参数优化算法."""

import itertools
import json
import logging
import multiprocessing
from logging.handlers import QueueListener
from typing import Any, List, Mapping, Optional, Sequence, Type, Union

import pandas as pd
from tqdm import tqdm  # type: ignore

from ..log import get_logger
from ..strategy import Strategy
from ._data import (
    JSONEncoder,
    OptimizationResult,
    _resolve_optimization_backtest_kwargs,
)
from ._worker import (
    _assert_parallel_pickleable,
    _init_worker_logging,
    _run_single_backtest,
    _save_result_to_db,
    _validate_strategy_param_grid_keys,
)


def run_grid_search(
    strategy: Type[Strategy],
    param_grid: Mapping[str, Sequence[Any]],
    data: Any = None,
    max_workers: Optional[int] = None,
    sort_by: Union[str, List[str]] = "sharpe_ratio",
    ascending: Union[bool, List[bool]] = False,
    return_df: bool = True,
    warmup_calc: Optional[Any] = None,
    constraint: Optional[Any] = None,
    result_filter: Optional[Any] = None,
    timeout: Optional[float] = None,
    max_tasks_per_child: Optional[int] = None,
    db_path: Optional[str] = None,
    forward_worker_logs: bool = False,
    **kwargs: Any,
) -> Union[pd.DataFrame, List[OptimizationResult]]:
    """
    运行参数优化 (Grid Search).

    :param strategy: 策略类
    :param param_grid: 参数网格，例如 {'period': [10, 20], 'factor': [0.5, 1.0]}
    :param data: 回测数据 (DataFrame, Dict[str, DataFrame], or List[Bar])
    :param max_workers: 并行进程数，默认 CPU 核心数
    :param sort_by: 结果排序指标 (默认: "sharpe_ratio")，支持单字段或多字段列表
    :param ascending: 排序方向 (默认: False, 即降序)，支持单值或多值列表
    :param return_df: 是否返回 DataFrame 格式 (默认: True)
    :param warmup_calc: 动态计算预热期的函数，接收 params 字典，返回 int (默认: None)
    :param constraint: 参数约束函数，接收 params 字典，返回 bool。True 表示保留，
                       False 表示过滤 (默认: None)
    :param result_filter: 结果筛选函数，接收 metrics 字典，返回 bool。True 表示保留，
                          False 表示过滤 (默认: None)
    :param timeout: 单次任务超时时间 (秒, 默认: None)。如果设置，
                    建议也设置 max_tasks_per_child=1 以清理超时线程。
    :param max_tasks_per_child: Worker 进程执行多少个任务后重启 (默认: None)。
                                设置 1 可以避免内存泄漏或超时线程残留。
    :param db_path: SQLite 数据库路径 (可选)。如果提供，将支持断点续传和增量保存。
    :param forward_worker_logs: 并行时是否将子进程策略日志回传主进程 (默认: False)
    :param kwargs: 传递给 run_backtest 的其他参数 (symbol, cash, etc.)
    :return: 优化结果 (DataFrame 或 List[OptimizationResult])
    """
    backtest_kwargs = _resolve_optimization_backtest_kwargs(data, dict(kwargs))
    backtest_kwargs.setdefault("strict_strategy_params", True)
    if (
        "execution_mode" in backtest_kwargs
        or "timer_execution_policy" in backtest_kwargs
    ):
        raise ValueError(
            "run_grid_search no longer accepts execution_mode/timer_execution_policy; "
            "please use fill_policy"
        )
    strict_strategy_params = bool(backtest_kwargs.get("strict_strategy_params", False))
    if strict_strategy_params:
        _validate_strategy_param_grid_keys(strategy, param_grid)

    # 1. 生成参数组合
    keys = param_grid.keys()
    values = param_grid.values()
    param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    # 1.5 应用约束过滤
    if constraint:
        original_count = len(param_combinations)
        param_combinations = [p for p in param_combinations if constraint(p)]
        filtered_count = len(param_combinations)
        if original_count != filtered_count:
            print(
                f"Constraint filtered {original_count - filtered_count} combinations "
                f"({original_count} -> {filtered_count})"
            )

    # 1.6 断点续传 (如果有 db_path)
    existing_results: list[OptimizationResult] = []
    if db_path:
        try:
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                # 检查表是否存在
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS optimization_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy_name TEXT,
                        params_json TEXT UNIQUE,
                        metrics_json TEXT,
                        duration REAL,
                        error TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()

                # 读取已有的结果
                cursor.execute(
                    "SELECT params_json, metrics_json, duration, error "
                    "FROM optimization_results WHERE strategy_name = ?",
                    (strategy.__name__,),
                )
                rows = cursor.fetchall()

                existing_params_set: set[str] = set()
                for row in rows:
                    p_json, m_json, dur, err = row
                    try:
                        # 尝试解析 JSON
                        p = json.loads(p_json)
                        existing_params_set.add(p_json)

                        m = json.loads(m_json)
                        existing_results.append(
                            OptimizationResult(
                                params=p, metrics=m, duration=dur, error=err
                            )
                        )
                    except Exception:
                        continue

                if existing_results:
                    print(
                        f"Found {len(existing_results)} existing results in DB. "
                        "Resuming..."
                    )

                    # 过滤已完成的任务
                    new_combinations = []
                    skipped_count = 0
                    for p in param_combinations:
                        # 使用 sort_keys=True 确保顺序一致
                        p_str = json.dumps(p, sort_keys=True, cls=JSONEncoder)
                        if p_str in existing_params_set:
                            skipped_count += 1
                        else:
                            new_combinations.append(p)

                    param_combinations = new_combinations
                    print(
                        f"Skipped {skipped_count} completed tasks. "
                        f"Remaining: {len(param_combinations)}"
                    )

        except Exception as e:
            print(f"Warning: Failed to access SQLite DB at {db_path}: {e}")

    total_combinations = len(param_combinations)

    # 3. 并行执行 (如果有剩余任务)
    new_results: list[OptimizationResult] = []
    if total_combinations > 0:
        print(
            f"Running optimization for {total_combinations} parameter combinations..."
        )

        # 2. 准备任务
        tasks = []
        for params in param_combinations:
            tasks.append(
                {
                    "strategy_cls": strategy,
                    "params": params,
                    "backtest_kwargs": {"data": data, **backtest_kwargs},
                    "warmup_calc": warmup_calc,
                    "timeout": timeout,
                }
            )

        # 如果 max_workers 为 None，默认使用 os.cpu_count()
        if max_workers is None:
            max_workers = multiprocessing.cpu_count() or 1

        # 如果只有一个任务或 worker=1，直接运行
        # (除非设置了 timeout，需要线程支持，仍走单线程逻辑)
        if max_workers == 1 or total_combinations == 1:
            for task in tqdm(tasks, desc="Optimizing"):
                result = _run_single_backtest(task)
                new_results.append(result)
                # 单线程模式下也可以实时写入 DB
                if db_path:
                    _save_result_to_db(db_path, strategy.__name__, result)
        else:
            # 使用 multiprocessing.Pool
            if timeout is not None and max_tasks_per_child is None:
                max_tasks_per_child = 1
            _assert_parallel_pickleable(strategy, backtest_kwargs, warmup_calc)
            listener: Optional[Any] = None
            log_queue: Any = None
            pool_initializer: Optional[Any] = None
            pool_init_args: tuple[Any, ...] = ()
            worker_log_forwarding_active = False
            if forward_worker_logs:
                logger = get_logger()
                active_handlers = [
                    handler
                    for handler in logger.handlers
                    if not isinstance(handler, logging.NullHandler)
                ]
                if active_handlers:
                    log_queue = multiprocessing.Queue()
                    listener = QueueListener(
                        log_queue, *active_handlers, respect_handler_level=True
                    )
                    listener.start()
                    pool_initializer = _init_worker_logging
                    pool_init_args = (log_queue,)
                    worker_log_forwarding_active = True
                else:
                    print(
                        "Warning: forward_worker_logs=True but no active logger "
                        "handler found in main process."
                    )
            if not worker_log_forwarding_active and not forward_worker_logs:
                print(
                    "Warning: max_workers>1 uses subprocess workers. "
                    "Strategy self.log() output may not be visible in the main "
                    "process console."
                )
            try:
                with multiprocessing.Pool(
                    processes=max_workers,
                    maxtasksperchild=max_tasks_per_child,
                    initializer=pool_initializer,
                    initargs=pool_init_args,
                ) as pool:
                    iterator = pool.imap(_run_single_backtest, tasks)
                    try:
                        for result in tqdm(
                            iterator, total=total_combinations, desc="Optimizing"
                        ):
                            new_results.append(result)
                            if db_path:
                                _save_result_to_db(
                                    db_path, strategy.__name__, result
                                )
                    except Exception as e:
                        print(f"Error during optimization (Worker Crash/OOM?): {e}")
                        pass
            finally:
                if listener is not None:
                    listener.stop()
                if log_queue is not None:
                    log_queue.close()
                    log_queue.join_thread()
    else:
        print("All tasks completed. Returning existing results.")

    # 合并结果
    results = existing_results + new_results

    # 4. 结果筛选
    if result_filter:
        original_count = len(results)
        results = [r for r in results if result_filter(r.metrics)]
        filtered_count = len(results)
        if original_count != filtered_count:
            print(
                f"Result filter removed {original_count - filtered_count} combinations "
                f"({original_count} -> {filtered_count})"
            )

    # 5. 排序结果
    if isinstance(sort_by, list):
        # 多字段排序
        if isinstance(ascending, bool):
            asc_list = [ascending] * len(sort_by)
        else:
            asc_list = ascending
            if len(asc_list) != len(sort_by):
                raise ValueError("Length of ascending list must match sort_by list")

        for key, asc in zip(reversed(sort_by), reversed(asc_list)):
            results.sort(
                key=lambda x: x.metrics.get(key, -float("inf")), reverse=not asc
            )
    else:
        # 单字段排序
        results.sort(
            key=lambda x: x.metrics.get(sort_by, -float("inf")),
            reverse=not ascending,
        )

    if return_df:
        data_list = []
        for r in results:
            row = r.params.copy()
            row.update(r.metrics)
            row["_duration"] = r.duration
            data_list.append(row)
        return pd.DataFrame(data_list)

    return results
