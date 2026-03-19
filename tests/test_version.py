"""Version sanity check tests."""

from typing import Any

import akquant as aq


def test_version_present() -> None:
    """
    Ensure package exposes a non-empty __version__ string.

    :return: None
    """
    v: Any = aq.__version__
    assert isinstance(v, str)
    assert len(v) > 0


def test_top_level_exposes_metric_formatter() -> None:
    """
    Ensure top-level package exports format_metric_value helper.

    :return: None
    """
    assert hasattr(aq, "format_metric_value")
    assert aq.format_metric_value("annualized_return", 0.021184) == "2.12%"
