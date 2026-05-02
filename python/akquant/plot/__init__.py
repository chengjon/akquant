"""
AKQuant Visualization Module.

Provides professional-grade plotting capabilities for backtest results.
"""

from .analysis import plot_pnl_vs_duration, plot_trades_distribution
from .comparison import plot_comparison
from .dashboard import plot_dashboard
from .report import plot_report
from .strategy import plot_strategy

# Alias for backward compatibility
plot_result = plot_dashboard

__all__ = [
    "plot_comparison",
    "plot_dashboard",
    "plot_report",
    "plot_result",
    "plot_strategy",
    "plot_trades_distribution",
    "plot_pnl_vs_duration",
]
