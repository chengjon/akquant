"""单个回测执行、多进程支持和序列化工具."""

import inspect
import json
import pickle
import threading
import time
from logging.handlers import QueueHandler
from typing import Any, Dict, List, Mapping, Optional, Sequence, Type, cast

from ..backtest import run_backtest
from ..log import get_logger
from ..strategy import Strategy
from ._data import JSONEncoder, OptimizationResult, _normalize_backtest_symbol_kwargs

_WORKER_LOG_QUEUE: Any = None


def _run_backtest_safe(
    strategy_cls: Type[Strategy],
    kwargs: Dict[str, Any],
    result_container: Dict[str, Any],
) -> None:
    """Run backtest in a thread and store result/exception."""
    try:
        kwargs = _normalize_backtest_symbol_kwargs(kwargs)
        # 运行回测
        # 注意：show_progress 在并行时最好关掉
        kwargs["show_progress"] = False
        result = run_backtest(strategy=strategy_cls, **kwargs)
        metrics_df = result.metrics_df

        if "Backtest" in metrics_df.columns:
            metrics = cast(Dict[str, Any], metrics_df["Backtest"].to_dict())
        else:
            metrics = cast(Dict[str, Any], metrics_df.iloc[:, 0].to_dict())

        result_container["metrics"] = metrics
    except Exception as e:
        result_container["error"] = str(e)


def _run_single_backtest(args: Dict[str, Any]) -> OptimizationResult:
    """
    运行单个回测任务 (Internal).

    args 包含:
    - strategy_cls: 策略类
    - params: 当前参数组合
    - backtest_kwargs: run_backtest 的其他参数 (data, cash, etc.)
    - warmup_calc: 动态预热期计算函数 (可选)
    - timeout: 超时时间 (秒, 可选)

    :param args: 任务参数字典
    :return: 优化结果
    """
    strategy_cls = args["strategy_cls"]
    params = args["params"]
    backtest_kwargs = args["backtest_kwargs"]
    warmup_calc = args.get("warmup_calc")
    timeout = args.get("timeout")

    # 将参数合并到 kwargs 中传给 strategy
    kwargs = backtest_kwargs.copy()
    kwargs.update(params)

    # 动态计算 warmup_period
    if warmup_calc:
        try:
            dynamic_warmup = warmup_calc(params)
            base_warmup = kwargs.get("warmup_period", 0)
            kwargs["warmup_period"] = max(base_warmup, dynamic_warmup)
        except Exception as e:
            print(f"Warning: Failed to calculate dynamic warmup period: {e}")

    start_time = time.time()
    metrics: Dict[str, Any] = {}
    error_msg: Optional[str] = None

    if timeout:
        # 使用线程运行回测，支持超时
        result_container: Dict[str, Any] = {}
        t = threading.Thread(
            target=_run_backtest_safe,
            args=(strategy_cls, kwargs, result_container),
            daemon=True,
        )
        t.start()
        t.join(timeout)

        if t.is_alive():
            # 超时
            error_msg = f"Timeout after {timeout} seconds"
            metrics = {"error": error_msg}
            # 设置默认 bad metrics 以便后续排序不报错
            metrics["sharpe_ratio"] = -999.0
            metrics["total_return"] = -999.0
            # 注意：无法强制杀死线程，但如果使用了 maxtasksperchild=1，
            # 当前进程会在任务结束后退出，从而清理线程。
        else:
            # 正常结束
            if "error" in result_container:
                error_msg = result_container["error"]
                metrics = {"error": error_msg}
                metrics["sharpe_ratio"] = -999.0
                metrics["total_return"] = -999.0
            else:
                metrics = result_container.get("metrics", {})

    else:
        # 直接运行
        try:
            kwargs["show_progress"] = False
            result = run_backtest(strategy=strategy_cls, **kwargs)
            metrics_df = result.metrics_df
            if "Backtest" in metrics_df.columns:
                metrics = cast(Dict[str, Any], metrics_df["Backtest"].to_dict())
            else:
                metrics = cast(Dict[str, Any], metrics_df.iloc[:, 0].to_dict())
        except Exception as e:
            error_msg = str(e)
            metrics = {"error": error_msg}
            metrics["sharpe_ratio"] = -999.0
            metrics["total_return"] = -999.0

    duration = time.time() - start_time

    return OptimizationResult(
        params=params, metrics=metrics, duration=duration, error=error_msg
    )


def _init_worker_logging(log_queue: Any) -> None:
    """Initialize worker logger with queue handler."""
    global _WORKER_LOG_QUEUE
    _WORKER_LOG_QUEUE = log_queue
    if log_queue is None:
        return
    logger = get_logger()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.addHandler(QueueHandler(log_queue))


def _assert_parallel_pickleable(
    strategy: Type[Strategy],
    backtest_kwargs: Mapping[str, Any],
    warmup_calc: Optional[Any],
) -> None:
    """
    Validate critical multiprocessing inputs are pickle-serializable.

    :param strategy: 策略类
    :param backtest_kwargs: run_backtest kwargs (不包含 data)
    :param warmup_calc: 动态预热函数
    :raises TypeError: 当关键输入无法序列化时抛出
    """
    strategy_module = getattr(strategy, "__module__", "")
    if strategy_module == "__main__":
        raise TypeError(
            "Parallel optimization requires strategy class importable from module, "
            "but got strategy defined in __main__. "
            "Please move strategy class to a module file."
        )

    checks: List[tuple[str, Any]] = [("strategy", strategy)]
    if warmup_calc is not None:
        checks.append(("warmup_calc", warmup_calc))

    sensitive_keys = (
        "fill_policy",
        "on_event",
        "initialize",
        "on_start",
        "on_stop",
        "on_tick",
        "on_order",
        "on_trade",
        "on_timer",
    )
    for key in sensitive_keys:
        if key in backtest_kwargs:
            checks.append((f"kwargs['{key}']", backtest_kwargs[key]))

    for label, obj in checks:
        try:
            pickle.dumps(obj)
        except Exception as e:
            raise TypeError(
                "run_grid_search with max_workers>1 requires pickle-serializable "
                f"arguments, but {label} failed: {e}. "
                "Tips: use fill_policy dict and avoid lambda/local callbacks, "
                "and ensure strategy class is defined in importable module."
            ) from e


def _validate_strategy_param_grid_keys(
    strategy: Type[Strategy], param_grid: Mapping[str, Sequence[Any]]
) -> None:
    """Validate that param_grid keys can be passed to strategy constructor."""
    try:
        signature = inspect.signature(strategy.__init__)
    except (TypeError, ValueError):
        return

    supports_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if supports_var_kwargs:
        return

    accepted_names = {
        parameter_name
        for parameter_name, parameter in signature.parameters.items()
        if parameter_name != "self"
        and parameter.kind
        in {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    }
    unknown_keys = sorted(
        key for key in param_grid.keys() if str(key) not in accepted_names
    )
    if unknown_keys:
        unknown_keys_text = ", ".join(str(key) for key in unknown_keys)
        raise TypeError(
            "Unknown strategy constructor parameter(s) in param_grid: "
            f"{unknown_keys_text}. Strategy={strategy.__module__}.{strategy.__name__}"
        )


def _save_result_to_db(
    db_path: str, strategy_name: str, result: OptimizationResult
) -> None:
    """Save a single result to SQLite."""
    try:
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Serialize
            params_json = json.dumps(result.params, sort_keys=True, cls=JSONEncoder)
            metrics_json = json.dumps(result.metrics, cls=JSONEncoder)

            cursor.execute(
                """
                INSERT OR IGNORE INTO optimization_results
                (strategy_name, params_json, metrics_json, duration, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    strategy_name,
                    params_json,
                    metrics_json,
                    result.duration,
                    result.error,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"Failed to save result to DB: {e}")
