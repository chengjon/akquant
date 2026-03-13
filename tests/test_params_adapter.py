from typing import Any

import pytest
from akquant.params import DateRange, DateRangeParam, IntParam, ParamModel
from akquant.params_adapter import (
    extract_runtime_kwargs,
    get_strategy_param_schema,
    validate_strategy_params,
)
from akquant.strategy import Strategy


class DemoParams(ParamModel):
    """用于测试的参数模型."""

    fast_period: int = IntParam(5, ge=2, le=100)
    slow_period: int = IntParam(20, ge=3, le=300)
    date_range: DateRange = DateRangeParam()


class DemoStrategy(Strategy):
    """用于测试的带 PARAM_MODEL 策略."""

    PARAM_MODEL = DemoParams

    def __init__(self, fast_period: int = 5, slow_period: int = 20) -> None:
        """初始化测试策略."""
        self.fast_period = fast_period
        self.slow_period = slow_period

    def on_bar(self, bar: Any) -> None:
        """处理 bar 事件."""
        return


class LegacyStrategy(Strategy):
    """用于测试签名推断的旧风格策略."""

    def __init__(self, period: int, use_exit: bool = True) -> None:
        """初始化旧风格测试策略."""
        self.period = period
        self.use_exit = use_exit

    def on_bar(self, bar: Any) -> None:
        """处理 bar 事件."""
        return


def test_get_strategy_param_schema_uses_param_model() -> None:
    """PARAM_MODEL 策略应返回模型 schema."""
    schema = get_strategy_param_schema(DemoStrategy)
    properties = schema.get("properties", {})
    assert "fast_period" in properties
    assert "date_range" in properties


def test_validate_strategy_params_with_model_and_runtime_kwargs() -> None:
    """参数模型应完成校验并导出运行时 kwargs."""
    payload = {
        "fast_period": 8,
        "slow_period": 26,
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    }
    validated = validate_strategy_params(DemoStrategy, payload)
    assert validated["fast_period"] == 8
    kwargs = extract_runtime_kwargs(DemoStrategy, payload)
    assert kwargs["start_time"] == "2024-01-01"
    assert kwargs["end_time"] == "2024-12-31"


def test_validate_strategy_params_rejects_unknown_fields() -> None:
    """未知字段应被拒绝."""
    payload = {"fast_period": 8, "slow_period": 20, "unknown": 1}
    with pytest.raises(Exception):
        validate_strategy_params(DemoStrategy, payload)


def test_validate_strategy_params_signature_fallback() -> None:
    """无参数模型时应回退到 __init__ 签名推断."""
    validated = validate_strategy_params(LegacyStrategy, {"period": "10"})
    assert validated["period"] == 10
    assert validated["use_exit"] is True
