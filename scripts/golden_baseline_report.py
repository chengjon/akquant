from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, cast

import pandas as pd


@dataclass(frozen=True)
class ScenarioSnapshot:
    """Snapshot of one golden scenario for baseline vs current comparison."""

    name: str
    baseline_metrics: Dict[str, Any]
    current_metrics: Dict[str, Any] | None
    baseline_orders_count: int
    current_orders_count: int | None
    baseline_trades_count: int
    current_trades_count: int | None
    baseline_equity_points: int
    current_equity_points: int | None


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fp:
        return cast(Dict[str, Any], json.load(fp))


def _load_parquet_count(path: Path) -> int:
    if not path.exists():
        return 0
    return int(len(pd.read_parquet(path)))


def _load_snapshot(
    scenario: str, baseline_dir: Path, current_dir: Path
) -> ScenarioSnapshot:
    baseline_path = baseline_dir / scenario
    current_path = current_dir / scenario
    baseline_metrics = _load_json(baseline_path / "metrics.json")
    current_metrics_path = current_path / "metrics.json"
    current_metrics = (
        _load_json(current_metrics_path) if current_metrics_path.exists() else None
    )
    return ScenarioSnapshot(
        name=scenario,
        baseline_metrics=baseline_metrics,
        current_metrics=current_metrics,
        baseline_orders_count=_load_parquet_count(baseline_path / "orders.parquet"),
        current_orders_count=(
            _load_parquet_count(current_path / "orders.parquet")
            if current_path.exists()
            else None
        ),
        baseline_trades_count=_load_parquet_count(baseline_path / "trades.parquet"),
        current_trades_count=(
            _load_parquet_count(current_path / "trades.parquet")
            if current_path.exists()
            else None
        ),
        baseline_equity_points=_load_parquet_count(
            baseline_path / "equity_curve.parquet"
        ),
        current_equity_points=(
            _load_parquet_count(current_path / "equity_curve.parquet")
            if current_path.exists()
            else None
        ),
    )


def _metric_diff(
    current: Dict[str, Any] | None, baseline: Dict[str, Any], key: str
) -> str:
    if current is None or key not in current or key not in baseline:
        return "n/a"
    current_value = float(current[key])
    baseline_value = float(baseline[key])
    return f"{current_value - baseline_value:.10f}"


def _iter_scenarios(baseline_dir: Path) -> Iterable[str]:
    for item in sorted(baseline_dir.iterdir()):
        if item.is_dir():
            yield item.name


def build_report(baseline_dir: Path, current_dir: Path) -> str:
    """Build markdown report from baseline and current golden outputs."""
    scenarios = list(_iter_scenarios(baseline_dir))
    lines: list[str] = [
        "# Golden Baseline Regression Report",
        "",
        f"- Baseline directory: `{baseline_dir}`",
        f"- Current directory: `{current_dir}`",
        "",
        (
            "| Scenario | Metrics Ready | Δtotal_return_pct | Δsharpe_ratio | "
            "Δmax_drawdown_pct | Orders (base/curr) | Trades (base/curr) | "
            "Equity points (base/curr) |"
        ),
        "| :--- | :---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scenario in scenarios:
        snapshot = _load_snapshot(scenario, baseline_dir, current_dir)
        has_current = snapshot.current_metrics is not None
        ready = "yes" if has_current else "no"
        current_orders = (
            snapshot.current_orders_count
            if snapshot.current_orders_count is not None
            else "n/a"
        )
        current_trades = (
            snapshot.current_trades_count
            if snapshot.current_trades_count is not None
            else "n/a"
        )
        current_equity_points = (
            snapshot.current_equity_points
            if snapshot.current_equity_points is not None
            else "n/a"
        )
        order_pair = f"{snapshot.baseline_orders_count}/{current_orders}"
        trade_pair = f"{snapshot.baseline_trades_count}/{current_trades}"
        equity_pair = f"{snapshot.baseline_equity_points}/{current_equity_points}"
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario,
                    ready,
                    _metric_diff(
                        snapshot.current_metrics,
                        snapshot.baseline_metrics,
                        "total_return_pct",
                    ),
                    _metric_diff(
                        snapshot.current_metrics,
                        snapshot.baseline_metrics,
                        "sharpe_ratio",
                    ),
                    _metric_diff(
                        snapshot.current_metrics,
                        snapshot.baseline_metrics,
                        "max_drawdown_pct",
                    ),
                    order_pair,
                    trade_pair,
                    equity_pair,
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint for golden baseline report generation."""
    parser = argparse.ArgumentParser(
        description="Generate golden baseline regression report."
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("tests/golden/baselines"),
        help="Baseline directory path.",
    )
    parser.add_argument(
        "--current-dir",
        type=Path,
        default=Path("tests/golden/current"),
        help="Current results directory path.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tests/golden/BASELINE_REPORT.md"),
        help="Output markdown report path.",
    )
    args = parser.parse_args()
    report = build_report(args.baseline_dir, args.current_dir)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
