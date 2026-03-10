import importlib.util
import os
import uuid
from typing import Any, Callable, Dict, Optional, Union, cast

from .akquant import Bar
from .strategy import Strategy

StrategyLike = Union[type[Strategy], Strategy, Callable[[Any, Bar], None]]
StrategySource = Union[str, bytes, os.PathLike[str]]
StrategyLoader = Callable[[StrategySource, Dict[str, Any]], StrategyLike]

_LOADERS: Dict[str, StrategyLoader] = {}


def _is_strategy_like(value: Any) -> bool:
    if isinstance(value, type) and issubclass(value, Strategy):
        return True
    if isinstance(value, Strategy):
        return True
    if callable(value):
        return True
    return False


def register_strategy_loader(name: str, loader: StrategyLoader) -> None:
    """Register a strategy loader by name."""
    normalized = str(name).strip()
    if not normalized:
        raise ValueError("strategy loader name cannot be empty")
    if not callable(loader):
        raise TypeError("strategy loader must be callable")
    _LOADERS[normalized] = loader


def get_strategy_loader(name: str) -> StrategyLoader:
    """Resolve a registered strategy loader."""
    normalized = str(name).strip()
    if not normalized:
        raise ValueError("strategy loader name cannot be empty")
    if normalized not in _LOADERS:
        raise ValueError(f"unknown strategy_loader: {normalized}")
    return _LOADERS[normalized]


def _load_python_plain(source: StrategySource, options: Dict[str, Any]) -> StrategyLike:
    if isinstance(source, bytes):
        raise TypeError("python_plain loader does not accept bytes source")
    module_path = os.fspath(source)
    module_name = f"akquant_user_strategy_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"failed to create module spec from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    attr_name_raw = options.get("strategy_attr")
    attr_name = str(attr_name_raw).strip() if attr_name_raw is not None else ""
    if attr_name:
        picked = getattr(module, attr_name, None)
        if picked is not None:
            if _is_strategy_like(picked):
                return cast(StrategyLike, picked)
            raise TypeError(f"module attr '{attr_name}' is not a valid strategy input")

    candidates = [
        obj
        for obj in module.__dict__.values()
        if isinstance(obj, type) and issubclass(obj, Strategy) and obj is not Strategy
    ]
    if len(candidates) == 1:
        return cast(StrategyLike, candidates[0])
    if not candidates:
        raise ValueError(
            "no Strategy subclass found in module; "
            "provide strategy_attr in loader options"
        )
    raise ValueError(
        "multiple Strategy subclasses found; provide strategy_attr in loader options"
    )


def _load_encrypted_external(
    source: StrategySource, options: Dict[str, Any]
) -> StrategyLike:
    callback = options.get("decrypt_and_load")
    if not callable(callback):
        raise ValueError(
            "encrypted_external loader requires callable option: decrypt_and_load"
        )
    loaded = callback(source, dict(options))
    if not _is_strategy_like(loaded):
        raise TypeError("decrypt_and_load must return Strategy type/instance/callable")
    return cast(StrategyLike, loaded)


def resolve_strategy_input(
    strategy: Optional[StrategyLike] = None,
    strategy_source: Optional[StrategySource] = None,
    strategy_loader: Optional[str] = None,
    strategy_loader_options: Optional[Dict[str, Any]] = None,
) -> StrategyLike:
    """Resolve strategy-like input from direct strategy or source + loader."""
    if strategy is not None:
        return strategy
    if strategy_source is None:
        raise ValueError("Strategy must be provided.")
    if strategy_loader is not None and not isinstance(strategy_loader, str):
        raise TypeError("strategy_loader must be str when provided")
    if strategy_loader_options is not None and not isinstance(
        strategy_loader_options, dict
    ):
        raise TypeError("strategy_loader_options must be dict when provided")
    loader_name = strategy_loader.strip() if strategy_loader else "python_plain"
    options: Dict[str, Any] = dict(strategy_loader_options or {})
    loader = get_strategy_loader(loader_name)
    loaded = loader(strategy_source, options)
    if not _is_strategy_like(loaded):
        raise TypeError("resolved strategy must be Strategy type/instance/callable")
    return loaded


register_strategy_loader("python_plain", _load_python_plain)
register_strategy_loader("encrypted_external", _load_encrypted_external)


__all__ = [
    "StrategyLike",
    "StrategySource",
    "StrategyLoader",
    "register_strategy_loader",
    "get_strategy_loader",
    "resolve_strategy_input",
]
