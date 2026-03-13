import logging
from typing import Any

from .log import get_logger
from .strategy_time import now as _now


def log(strategy: Any, msg: str, level: int = logging.INFO) -> None:
    """输出日志 (自动添加当前回测时间)."""
    timestamp_str = ""
    ts = _now(strategy)
    if ts:
        timestamp_str = ts.strftime("%Y-%m-%d %H:%M:%S")

    if timestamp_str:
        final_msg = f"[{timestamp_str}] {msg}"
    else:
        final_msg = msg

    get_logger().log(level, final_msg)
