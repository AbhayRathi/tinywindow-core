"""Report generation for backtest results."""

import logging
from datetime import datetime
from typing import Any, Optional

from .engine import BacktestResult

logger = logging.getLogger(__name__)


class BacktestReporter:
    """Generates reports from backtest results."""

    def __init__(self, result: BacktestResult):
        """Initialize reporter.

        Args:
            result: Backtest result to report on
        """
        self.result = result

    def generate_summary(self) -> str:
        """Generate text summary of backtest.

        Returns:
            Summary string
        """
        m = self.result.metrics
        lines = [
            "=" * 60,
            "BACKTEST SUMMARY",
            "=" * 60,
            f"Symbol: {self.result.data.symbol}",
            f"Period: {self.result.start_date.strftime('%Y-%m-%d')} to {self.result.end_date.strftime('%Y-%m-%d')}",
            f"Initial Capital: ${m.initial_capital:,.2f}",
            f"Final Capital: ${m.final_capital:,.2f}",
            "",
            "RETURNS",
            "-" * 40,
            f"Total Return: {m.total_return:.2f}%",
            f"Annualized Return: {m.annualized_return:.2f}%",
            "",
            "RISK METRICS",
            "-" * 40,
            f"Sharpe Ratio: {m.sharpe_ratio:.2f}",
            f"Sortino Ratio: {m.sortino_ratio:.2f}",
            f"Max Drawdown: {m.max_drawdown:.2f}%",
            f"Calmar Ratio: {m.calmar_ratio:.2f}",
            "",
            "TRADE STATISTICS",
            "-" * 40,
            f"Total Trades: {m.total_trades}",
            f"Win Rate: {m.win_rate:.1f}%",
            f"Profit Factor: {m.profit_factor:.2f}",
            f"Winning Trades: {m.winning_trades}",
            f"Losing Trades: {m.losing_trades}",
            f"Avg Trade P&L: ${m.avg_trade_pnl:.2f}",
            f"Avg Win: ${m.avg_win:.2f}",
            f"Avg Loss: ${m.avg_loss:.2f}",
            f"Largest Win: ${m.largest_win:.2f}",
            f"Largest Loss: ${m.largest_loss:.2f}",
            "=" * 60,
        ]
        return "\n".join(lines)

    def generate_html_report(self) -> str:
        """Generate HTML report with charts.

        Returns:
            HTML string
        """
        m = self.result.metrics

        # Create equity curve data for chart
        equity_data = [float(e) for e in self.result.equity_curve]
        indices = list(range(len(equity_data)))

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report - {self.result.data.symbol}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }}
        .metric-label {{
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }}
        .positive {{ color: #28a745 !important; }}
        .negative {{ color: #dc3545 !important; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .chart-container {{
            width: 100%;
            height: 400px;
            margin: 20px 0;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>Backtest Report: {self.result.data.symbol}</h1>
        <p><strong>Period:</strong> {self.result.start_date.strftime('%Y-%m-%d')} to {self.result.end_date.strftime('%Y-%m-%d')}</p>

        <h2>Performance Summary</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value {'positive' if m.total_return >= 0 else 'negative'}">{m.total_return:.2f}%</div>
                <div class="metric-label">Total Return</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{m.sharpe_ratio:.2f}</div>
                <div class="metric-label">Sharpe Ratio</div>
            </div>
            <div class="metric-card">
                <div class="metric-value negative">{m.max_drawdown:.2f}%</div>
                <div class="metric-label">Max Drawdown</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{m.win_rate:.1f}%</div>
                <div class="metric-label">Win Rate</div>
            </div>
        </div>

        <h2>Equity Curve</h2>
        <div class="chart-container">
            <canvas id="equityChart"></canvas>
        </div>

        <h2>Trade Statistics</h2>
        <table>
            <tr>
                <td>Total Trades</td>
                <td>{m.total_trades}</td>
            </tr>
            <tr>
                <td>Winning Trades</td>
                <td>{m.winning_trades}</td>
            </tr>
            <tr>
                <td>Losing Trades</td>
                <td>{m.losing_trades}</td>
            </tr>
            <tr>
                <td>Profit Factor</td>
                <td>{m.profit_factor:.2f}</td>
            </tr>
            <tr>
                <td>Average Trade P&L</td>
                <td>${m.avg_trade_pnl:.2f}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td>${m.avg_win:.2f}</td>
            </tr>
            <tr>
                <td>Average Loss</td>
                <td>${m.avg_loss:.2f}</td>
            </tr>
            <tr>
                <td>Largest Win</td>
                <td>${m.largest_win:.2f}</td>
            </tr>
            <tr>
                <td>Largest Loss</td>
                <td>${m.largest_loss:.2f}</td>
            </tr>
        </table>

        <h2>Risk Metrics</h2>
        <table>
            <tr>
                <td>Sortino Ratio</td>
                <td>{m.sortino_ratio:.2f}</td>
            </tr>
            <tr>
                <td>Calmar Ratio</td>
                <td>{m.calmar_ratio:.2f}</td>
            </tr>
            <tr>
                <td>Initial Capital</td>
                <td>${m.initial_capital:,.2f}</td>
            </tr>
            <tr>
                <td>Final Capital</td>
                <td>${m.final_capital:,.2f}</td>
            </tr>
        </table>
    </div>

    <script>
        const ctx = document.getElementById('equityChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {indices},
                datasets: [{{
                    label: 'Portfolio Value ($)',
                    data: {equity_data},
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: false,
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toLocaleString();
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        return html

    def save_html_report(self, filepath: str) -> None:
        """Save HTML report to file.

        Args:
            filepath: Output file path
        """
        html = self.generate_html_report()
        with open(filepath, "w") as f:
            f.write(html)
        logger.info(f"Report saved to {filepath}")

    def print_summary(self) -> None:
        """Print summary to console."""
        print(self.generate_summary())
