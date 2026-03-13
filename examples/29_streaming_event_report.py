import importlib
from pathlib import Path
from typing import cast

import pandas as pd


def load_events(csv_path: Path) -> pd.DataFrame:
    """Load persisted stream events and normalize key columns."""
    if not csv_path.exists():
        hint = "Run examples/28_streaming_alerts_and_persist.py first."
        raise FileNotFoundError(f"CSV not found: {csv_path}. {hint}")
    df = pd.read_csv(csv_path)
    if df.empty:
        raise ValueError(f"CSV is empty: {csv_path}")
    if "seq" not in df.columns or "event_type" not in df.columns:
        raise ValueError("CSV must contain seq and event_type columns")
    df["seq"] = pd.to_numeric(df["seq"], errors="coerce").fillna(0).astype(int)
    df["event_type"] = df["event_type"].astype(str)
    return cast(pd.DataFrame, df.sort_values("seq").reset_index(drop=True))


def build_html_report(df: pd.DataFrame, out_file: Path) -> None:
    """Build a compact interactive HTML report for stream events."""
    counts = df["event_type"].value_counts().sort_values(ascending=False)
    pivot = (
        df.assign(_n=1)
        .pivot_table(index="seq", columns="event_type", values="_n", aggfunc="sum")
        .fillna(0)
        .cumsum()
    )

    try:
        go = importlib.import_module("plotly.graph_objects")
        make_subplots = importlib.import_module("plotly.subplots").make_subplots
    except Exception:
        summary_html = counts.to_frame("count").to_html()
        out_file.write_text(
            "<html><body><h1>Streaming Event Summary</h1>"
            f"{summary_html}"
            "<p>Install plotly to get interactive charts.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        return

    fig = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.12,
        subplot_titles=("Cumulative Event Counts by Seq", "Event Distribution"),
    )

    for col in pivot.columns:
        fig.add_trace(
            go.Scatter(
                x=pivot.index,
                y=pivot[col],
                mode="lines",
                name=f"cum_{col}",
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Bar(
            x=list(counts.index),
            y=list(counts.values),
            name="event_count",
        ),
        row=2,
        col=1,
    )

    alert_rows = df[df["event_type"] == "alert_drawdown"]
    if not alert_rows.empty:
        hover_values = alert_rows.get("value", pd.Series(dtype="object")).astype(str)
        fig.add_trace(
            go.Scatter(
                x=alert_rows["seq"],
                y=[0] * len(alert_rows),
                mode="markers",
                marker=dict(size=10, symbol="diamond", color="red"),
                name="drawdown_alert",
                hovertext=hover_values,
            ),
            row=1,
            col=1,
        )

    fig.update_layout(
        title="AKQuant Streaming Event Report",
        height=820,
        template="plotly_white",
        showlegend=True,
    )
    fig.write_html(str(out_file), include_plotlyjs="cdn")


def main() -> None:
    """Generate stream event report HTML from persisted CSV."""
    out_dir = Path(__file__).resolve().parent / "output"
    csv_path = out_dir / "stream_alert_events.csv"
    html_path = out_dir / "stream_event_report.html"
    df = load_events(csv_path)
    build_html_report(df, html_path)
    print(f"event_rows={len(df)}")
    print(f"event_types={sorted(df['event_type'].unique().tolist())}")
    print(f"report_html={html_path}")
    print("done_streaming_event_report")


if __name__ == "__main__":
    main()
