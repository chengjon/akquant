"""
策略参数适配层.

用于连接策略参数模型、前端 schema 与回测入口。
"""

import inspect
from typing import Any, Mapping, Sequence, cast

from .params import ParamModel, model_to_schema, to_runtime_kwargs, validate_payload
from .strategy import Strategy


def resolve_param_model(strategy_cls: type[Strategy]) -> type[ParamModel] | None:
    """
    解析策略的参数模型.

    :param strategy_cls: 策略类
    :return: ParamModel 子类；若未声明则返回 None
    :raises TypeError: PARAM_MODEL 类型不合法
    """
    model_cls = getattr(strategy_cls, "PARAM_MODEL", None)
    if model_cls is None:
        return None
    if not isinstance(model_cls, type) or not issubclass(model_cls, ParamModel):
        raise TypeError("PARAM_MODEL must be a subclass of ParamModel")
    return cast(type[ParamModel], model_cls)


def get_strategy_param_schema(strategy_cls: type[Strategy]) -> dict[str, Any]:
    """
    获取策略参数 schema.

    :param strategy_cls: 策略类
    :return: 参数 schema
    """
    model_cls = resolve_param_model(strategy_cls)
    if model_cls is not None:
        return model_to_schema(model_cls)
    return _build_signature_schema(strategy_cls)


def validate_strategy_params(
    strategy_cls: type[Strategy],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """
    校验策略参数.

    :param strategy_cls: 策略类
    :param payload: 待校验参数
    :return: 可直接注入 strategy_params 的参数字典
    """
    model_cls = resolve_param_model(strategy_cls)
    if model_cls is not None:
        model = validate_payload(model_cls, payload)
        return cast(dict[str, Any], model.model_dump())
    return _validate_with_signature(strategy_cls, payload)


def extract_runtime_kwargs(
    strategy_cls: type[Strategy],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """
    提取运行时参数.

    :param strategy_cls: 策略类
    :param payload: 待校验参数
    :return: 可透传 run_backtest 的 runtime kwargs
    """
    model_cls = resolve_param_model(strategy_cls)
    if model_cls is None:
        return {}
    model = validate_payload(model_cls, payload)
    return to_runtime_kwargs(model)


def build_param_grid_from_search_space(
    search_space: Mapping[str, Sequence[Any]],
) -> dict[str, list[Any]]:
    """
    将上层 search space 归一化为 param_grid.

    :param search_space: 搜索空间
    :return: param_grid
    :raises TypeError: 值不是序列
    :raises ValueError: 候选为空
    """
    grid: dict[str, list[Any]] = {}
    for key, values in search_space.items():
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise TypeError(f"search_space[{key}] must be a sequence")
        candidate_values = list(values)
        if not candidate_values:
            raise ValueError(f"search_space[{key}] cannot be empty")
        grid[str(key)] = candidate_values
    return grid


def _build_signature_schema(strategy_cls: type[Strategy]) -> dict[str, Any]:
    signature = inspect.signature(strategy_cls.__init__)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = param.annotation
        json_type = _annotation_to_json_type(annotation)
        field_schema: dict[str, Any] = {"type": json_type, "title": name}
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            field_schema["default"] = param.default
        properties[name] = field_schema
    return {
        "title": f"{strategy_cls.__name__}Params",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_with_signature(
    strategy_cls: type[Strategy],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    signature = inspect.signature(strategy_cls.__init__)
    allowed_params: dict[str, inspect.Parameter] = {}
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        allowed_params[name] = param

    unknown = sorted(set(payload.keys()).difference(set(allowed_params.keys())))
    if unknown:
        raise ValueError(f"Unknown strategy params: {unknown}")

    validated: dict[str, Any] = {}
    for name, param in allowed_params.items():
        if name in payload:
            validated[name] = _coerce_value(payload[name], param.annotation)
        elif param.default is not inspect.Parameter.empty:
            validated[name] = param.default
        else:
            raise ValueError(f"Missing required strategy param: {name}")
    return validated


def _annotation_to_json_type(annotation: Any) -> str:
    normalized = _normalize_annotation(annotation)
    if normalized is int:
        return "integer"
    if normalized is float:
        return "number"
    if normalized is bool:
        return "boolean"
    return "string"


def _coerce_value(value: Any, annotation: Any) -> Any:
    normalized = _normalize_annotation(annotation)
    if normalized is int:
        return int(value)
    if normalized is float:
        return float(value)
    if normalized is bool:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "no", "n", "off"}:
                return False
        return bool(value)
    if normalized is str:
        return str(value)
    return value


def _normalize_annotation(annotation: Any) -> Any:
    if annotation is int:
        return int
    if annotation is float:
        return float
    if annotation is bool:
        return bool
    if annotation is str:
        return str
    if isinstance(annotation, str):
        mapping = {"int": int, "float": float, "bool": bool, "str": str}
        return mapping.get(annotation, annotation)
    return annotation


__all__ = [
    "resolve_param_model",
    "get_strategy_param_schema",
    "validate_strategy_params",
    "extract_runtime_kwargs",
    "build_param_grid_from_search_space",
]
