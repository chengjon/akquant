import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import akquant as aq
import pandas as pd


def _load_example_module(module_name: str, relative_path: str) -> ModuleType:
    """Load an example module from the repository by relative path."""
    root = Path(__file__).resolve().parents[1]
    module_path = root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load example module: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_option_example_import_has_no_run_backtest_side_effect(
    monkeypatch: Any,
) -> None:
    """Importing the option example should not execute the backtest."""

    def _unexpected_run_backtest(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("run_backtest should not execute during import")

    monkeypatch.setattr(aq, "run_backtest", _unexpected_run_backtest)
    module = _load_example_module(
        "example_option_test_import",
        "examples/07_option_test.py",
    )
    assert hasattr(module, "build_data")
    assert hasattr(module, "build_config")
    assert hasattr(module, "main")


def test_option_example_builders_match_current_run_backtest_api() -> None:
    """Option example helpers should remain executable with the current API."""
    module = _load_example_module(
        "example_option_test_runtime",
        "examples/07_option_test.py",
    )
    data = module.build_data()
    config = module.build_config()
    assert set(data) == {"CALL_OPT", "UL"}
    assert all(isinstance(frame, pd.DataFrame) for frame in data.values())
    result = aq.run_backtest(
        data=data,
        strategy=module.OptionExpiryStrategy,
        config=config,
        commission_rate=0.0,
        show_progress=False,
    )
    assert result.metrics.end_market_value == 99900.0


def test_option_example_main_uses_keyword_arguments(monkeypatch: Any) -> None:
    """Option example main should call run_backtest with supported keywords."""
    module = _load_example_module(
        "example_option_test_main",
        "examples/07_option_test.py",
    )
    captured: dict[str, Any] = {}

    def _fake_run_backtest(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(
            orders=[],
            metrics=SimpleNamespace(end_market_value=99900.0),
            trades_df=pd.DataFrame(),
        )

    monkeypatch.setattr(module, "run_backtest", _fake_run_backtest)
    module.main()

    assert captured["strategy"] is module.OptionExpiryStrategy
    assert captured["commission_rate"] == 0.0
    assert captured["show_progress"] is False
    assert set(captured["data"]) == {"CALL_OPT", "UL"}
