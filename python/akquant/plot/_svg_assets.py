"""Embedded SVG icons, logos, and HTML template for report generation."""

# Embedded SVG Icon
AKQUANT_ICON_SVG = """<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <g transform="translate(17, 25)">
    <rect x="0" y="40" width="15" height="30" rx="4" fill="#CE412B" />
    <rect x="25" y="20" width="15" height="50" rx="4" fill="#BE5C60" />
    <rect x="50" y="0" width="15" height="70" rx="4" fill="#3776AB" />
    <circle cx="7" cy="30" r="2" fill="#CE412B" />
    <circle cx="32" cy="10" r="2" fill="#BE5C60" />
    <circle cx="57" cy="-10" r="2" fill="#3776AB" />
  </g>
</svg>"""

# Embedded SVG Logo
AKQUANT_LOGO_SVG = """<svg width="400" height="120" viewBox="0 0 400 120" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="textGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#CE412B;stop-opacity:1" />
      <!-- Rust Orange -->
      <stop offset="100%" style="stop-color:#3776AB;stop-opacity:1" />
      <!-- Python Blue -->
    </linearGradient>
  </defs>

  <!-- Graphic: Quant Signal Bars (Ascending Data Spectrum) -->
  <g transform="translate(30, 25)">
    <!-- Bar 1: Low (Foundation/Data - Rust Color) -->
    <rect x="0" y="40" width="15" height="30" rx="4" fill="#CE412B" />

    <!-- Bar 2: Mid (Processing/Strategy - Blend) -->
    <rect x="25" y="20" width="15" height="50" rx="4" fill="#BE5C60" />

    <!-- Bar 3: High (Alpha/Profit - Python Color) -->
    <rect x="50" y="0" width="15" height="70" rx="4" fill="#3776AB" />

    <!-- Abstract Data Dots -->
    <circle cx="7" cy="30" r="2" fill="#CE412B" />
    <circle cx="32" cy="10" r="2" fill="#BE5C60" />
    <circle cx="57" cy="-10" r="2" fill="#3776AB" />
  </g>

  <!-- Text -->
  <text x="110" y="75"
        font-family="'Segoe UI', Helvetica, Arial, sans-serif"
        font-size="60"
        font-weight="bold"
        fill="url(#textGradient)">AKQuant</text>

  <!-- Subtitle -->
  <text x="115" y="100"
        font-family="'Segoe UI', Helvetica, Arial, sans-serif"
        font-size="14"
        fill="#666">High-Performance Quant Framework</text>
</svg>"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link rel="icon" href="{favicon_uri}">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {{
            --primary-color: #2c3e50;
            --accent-color: #3498db;
            --bg-color: #f5f7fa;
            --card-bg: #ffffff;
            --text-color: #333333;
            --text-secondary: #7f8c8d;
            --border-color: #e1e4e8;
            --success-color: #27ae60;
            --danger-color: #c0392b;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB",
                "Microsoft YaHei", sans-serif;
            margin: 0;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: var(--card-bg);
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border-radius: 12px;
        }}

        header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
        }}

        .header-logo {{
            margin-bottom: 10px;
        }}

        .header-logo svg {{
            height: 80px;
            width: auto;
        }}

        header h1 {{
            margin: 0;
            color: var(--primary-color);
            font-size: 28px;
            font-weight: 700;
        }}

        header p {{
            color: var(--text-secondary);
            margin: 10px 0 0;
            font-size: 14px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--primary-color);
            margin: 40px 0 20px;
            padding-left: 12px;
            border-left: 4px solid var(--accent-color);
            display: flex;
            align-items: center;
        }}

        /* Summary Box */
        .summary-box {{
            display: flex;
            justify-content: space-between;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 20px;
        }}

        .summary-item {{
            flex: 1;
            min-width: 200px;
        }}

        .summary-label {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }}

        .summary-value {{
            font-size: 18px;
            font-weight: 600;
            color: var(--primary-color);
        }}

        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: #ffffff;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid var(--border-color);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }}

        .metric-value.positive {{
            color: var(--success-color);
        }}

        .metric-value.negative {{
            color: var(--danger-color);
        }}

        .metric-label {{
            font-size: 14px;
            color: var(--text-secondary);
        }}

        /* Charts Grid Layout */
        .row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
        }}

        .col {{
            background: white;
            border-radius: 8px;
            min-width: 0; /* Prevent grid blowout */
        }}

        /* Ensure chart containers fill the column and handle overflow */
        .chart-container {{
            width: 100%;
            height: 100%;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 5px; /* Reduced padding to give more space to chart */
            box-sizing: border-box;
            background: white;
            overflow-x: auto;
            overflow-y: hidden;
        }}

        .table-scroll {{
            width: 100%;
            overflow-x: auto;
            overflow-y: hidden;
        }}

        .table {{
            width: max-content;
            min-width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 14px;
        }}

        .table th, .table td {{
            white-space: nowrap;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-color);
            text-align: left;
        }}

        .table th {{
            position: sticky;
            top: 0;
            background: #f8f9fa;
            color: var(--primary-color);
            font-weight: 600;
            z-index: 1;
        }}

        .analysis-overview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }}

        .analysis-card {{
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px 14px;
        }}

        .analysis-card-label {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 6px;
            line-height: 1.35;
        }}

        .analysis-card-value {{
            font-size: 18px;
            font-weight: 700;
            color: var(--primary-color);
            line-height: 1.2;
        }}

        .details-block {{
            border: 1px solid var(--border-color);
            border-radius: 8px;
            background: #ffffff;
            margin-top: 14px;
        }}

        .details-block > summary {{
            list-style: none;
            cursor: pointer;
            padding: 12px 14px;
            font-size: 15px;
            font-weight: 600;
            color: var(--primary-color);
            border-bottom: 1px solid transparent;
            user-select: none;
        }}

        .details-block[open] > summary {{
            border-bottom-color: var(--border-color);
            background: #f8f9fa;
        }}

        .details-content {{
            padding: 10px 12px 12px 12px;
        }}

        .empty-panel {{
            border: 1px dashed var(--border-color);
            border-radius: 8px;
            background: #fafbfc;
            padding: 14px 16px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}

        footer {{
            text-align: center;
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            color: var(--text-secondary);
            font-size: 12px;
        }}

        @media (max-width: 768px) {{
            .container {{ padding: 20px; }}
            .row {{ grid-template-columns: 1fr; }} /* Stack on mobile */
            .summary-box {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-logo">{icon_svg}</div>
            <h1>{title}</h1>
            <p>生成时间: {date}</p>
        </header>

        <!-- Summary Section -->
        <div class="summary-box">
            <div class="summary-item">
                <div class="summary-label">回测区间</div>
                <div class="summary-value">{start_date} ~ {end_date}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">回测时长</div>
                <div class="summary-value">{duration_str}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">初始资金</div>
                <div class="summary-value">{initial_cash}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">最终权益</div>
                <div class="summary-value">{final_equity}</div>
            </div>
        </div>

        <div class="section-title">核心指标 (Key Metrics)</div>
        <div class="metrics-grid">
            {metrics_html}
        </div>

        {comparison_section_html}

        <div class="section-title">权益与回撤 (Equity & Drawdown)</div>
        <div class="chart-container">
            {dashboard_html}
        </div>

        <div class="section-title">收益分析 (Return Analysis)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {yearly_returns_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {returns_dist_html}
                </div>
            </div>
        </div>
        <div class="chart-container" style="margin-top: 20px;">
            {rolling_metrics_html}
        </div>

        <div class="section-title">基准对比 (Benchmark Comparison)</div>
        <div class="metrics-grid">
            {benchmark_metrics_html}
        </div>
        <div class="chart-container">
            {benchmark_chart_html}
        </div>

        <div class="section-title">交易分析 (Trade Analysis)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {trades_dist_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {pnl_duration_html}
                </div>
            </div>
        </div>
        <div class="section-title">交易复盘 (K线买卖点)</div>
        <div class="chart-container">
            {strategy_kline_html}
        </div>

        <div class="section-title">组合归因与容量分析 (Attribution & Capacity)</div>
        <div class="analysis-overview-grid">
            {analysis_overview_html}
        </div>
        <details class="details-block">
            <summary>暴露摘要明细 (Exposure Summary)</summary>
            <div class="details-content">{exposure_summary_html}</div>
        </details>
        <details class="details-block">
            <summary>容量摘要明细 (Capacity Summary)</summary>
            <div class="details-content">{capacity_summary_html}</div>
        </details>
        <details class="details-block" open>
            <summary>归因明细 (Attribution Details)</summary>
            <div class="details-content">{attribution_summary_html}</div>
        </details>
        <div class="section-title">策略归属聚合 (Strategy Ownership Aggregation)</div>
        <div class="row">
            <div class="col">
                <div class="chart-container">
                    {orders_by_strategy_html}
                </div>
            </div>
            <div class="col">
                <div class="chart-container">
                    {executions_by_strategy_html}
                </div>
            </div>
        </div>
        <details class="details-block" style="margin-top: 20px;">
            <summary>策略风控拒单明细 (Risk Rejections by Strategy)</summary>
            <div class="details-content">{risk_by_strategy_html}</div>
        </details>
        <details class="details-block">
            <summary>强平审计明细 (Forced Liquidation Audit)</summary>
            <div class="details-content">{liquidation_audit_html}</div>
        </details>
        {risk_charts_html}

        <footer>
            AKQuant Report | Powered by Plotly & AKQuant
        </footer>
    </div>
    <script>
        // Force Plotly resize on page load to ensure correct dimensions
        // in Grid/Flex layout
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                var plots = document.getElementsByClassName('js-plotly-plot');
                for (var i = 0; i < plots.length; i++) {{
                    Plotly.Plots.resize(plots[i]);
                }}
            }}, 100); // Small delay to allow CSS layout to stabilize
        }});

        // Also trigger on resize to be safe
        // (though responsive: true handles most cases)
        window.addEventListener('resize', function() {{
            var plots = document.getElementsByClassName('js-plotly-plot');
            for (var i = 0; i < plots.length; i++) {{
                Plotly.Plots.resize(plots[i]);
            }}
        }});
    </script>
</body>
</html>
"""
