"""Prometheus metrics for TinyWindow trading system.

Exports metrics on port 8000 for Prometheus scraping:
- Trade metrics: trades_total, trade_pnl_usd, win_rate
- Position metrics: active_positions, portfolio_value_usd, unrealized_pnl_usd
- Risk metrics: drawdown_pct, daily_pnl_pct, leverage_ratio, portfolio_var_95
- API metrics: api_latency_seconds, api_errors_total
- Agent metrics: agent_decisions_total, agent_confidence
- Safety metrics: circuit_breaker_trips, kill_switch_activations
"""

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Metric Classes (Lightweight implementation without prometheus_client dependency)
# =============================================================================


class Counter:
    """A counter metric that can only increase."""

    def __init__(self, name: str, description: str, labels: Optional[list[str]] = None):
        self.name = name
        self.description = description
        self._label_names = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "CounterWithLabels":
        """Return a counter with specific labels."""
        label_values = tuple(kwargs.get(l, "") for l in self._label_names)
        return CounterWithLabels(self, label_values)

    def inc(self, value: float = 1.0) -> None:
        """Increment the counter."""
        with self._lock:
            key = ()
            self._values[key] = self._values.get(key, 0) + value

    def _inc_labels(self, label_values: tuple, value: float = 1.0) -> None:
        """Increment with specific labels."""
        with self._lock:
            self._values[label_values] = self._values.get(label_values, 0) + value

    def get_all(self) -> dict[tuple, float]:
        """Get all values."""
        with self._lock:
            return self._values.copy()

    def to_prometheus(self) -> str:
        """Format as Prometheus text."""
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} counter"]
        with self._lock:
            for label_values, value in self._values.items():
                if label_values:
                    labels_str = ",".join(
                        f'{l}="{v}"' for l, v in zip(self._label_names, label_values)
                    )
                    lines.append(f"{self.name}{{{labels_str}}} {value}")
                else:
                    lines.append(f"{self.name} {value}")
        return "\n".join(lines)


class CounterWithLabels:
    """Counter with specific label values."""

    def __init__(self, parent: Counter, label_values: tuple):
        self._parent = parent
        self._label_values = label_values

    def inc(self, value: float = 1.0) -> None:
        """Increment the counter."""
        self._parent._inc_labels(self._label_values, value)


class Gauge:
    """A gauge metric that can increase or decrease."""

    def __init__(self, name: str, description: str, labels: Optional[list[str]] = None):
        self.name = name
        self.description = description
        self._label_names = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "GaugeWithLabels":
        """Return a gauge with specific labels."""
        label_values = tuple(kwargs.get(l, "") for l in self._label_names)
        return GaugeWithLabels(self, label_values)

    def set(self, value: float) -> None:
        """Set the gauge value."""
        with self._lock:
            self._values[()] = value

    def inc(self, value: float = 1.0) -> None:
        """Increment the gauge."""
        with self._lock:
            key = ()
            self._values[key] = self._values.get(key, 0) + value

    def dec(self, value: float = 1.0) -> None:
        """Decrement the gauge."""
        with self._lock:
            key = ()
            self._values[key] = self._values.get(key, 0) - value

    def _set_labels(self, label_values: tuple, value: float) -> None:
        """Set with specific labels."""
        with self._lock:
            self._values[label_values] = value

    def get_all(self) -> dict[tuple, float]:
        """Get all values."""
        with self._lock:
            return self._values.copy()

    def to_prometheus(self) -> str:
        """Format as Prometheus text."""
        lines = [f"# HELP {self.name} {self.description}", f"# TYPE {self.name} gauge"]
        with self._lock:
            for label_values, value in self._values.items():
                if label_values:
                    labels_str = ",".join(
                        f'{l}="{v}"' for l, v in zip(self._label_names, label_values)
                    )
                    lines.append(f"{self.name}{{{labels_str}}} {value}")
                else:
                    lines.append(f"{self.name} {value}")
        return "\n".join(lines)


class GaugeWithLabels:
    """Gauge with specific label values."""

    def __init__(self, parent: Gauge, label_values: tuple):
        self._parent = parent
        self._label_values = label_values

    def set(self, value: float) -> None:
        """Set the gauge value."""
        self._parent._set_labels(self._label_values, value)

    def inc(self, value: float = 1.0) -> None:
        """Increment the gauge."""
        with self._parent._lock:
            current = self._parent._values.get(self._label_values, 0)
            self._parent._values[self._label_values] = current + value

    def dec(self, value: float = 1.0) -> None:
        """Decrement the gauge."""
        with self._parent._lock:
            current = self._parent._values.get(self._label_values, 0)
            self._parent._values[self._label_values] = current - value


class Histogram:
    """A histogram metric for tracking distributions."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(
        self,
        name: str,
        description: str,
        labels: Optional[list[str]] = None,
        buckets: Optional[tuple] = None,
    ):
        self.name = name
        self.description = description
        self._label_names = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._observations: dict[tuple, list[float]] = {}
        self._lock = threading.Lock()

    def labels(self, **kwargs) -> "HistogramWithLabels":
        """Return a histogram with specific labels."""
        label_values = tuple(kwargs.get(l, "") for l in self._label_names)
        return HistogramWithLabels(self, label_values)

    def observe(self, value: float) -> None:
        """Record an observation."""
        with self._lock:
            key = ()
            if key not in self._observations:
                self._observations[key] = []
            self._observations[key].append(value)

    def _observe_labels(self, label_values: tuple, value: float) -> None:
        """Record observation with labels."""
        with self._lock:
            if label_values not in self._observations:
                self._observations[label_values] = []
            self._observations[label_values].append(value)

    def get_all(self) -> dict[tuple, list[float]]:
        """Get all observations."""
        with self._lock:
            return {k: v.copy() for k, v in self._observations.items()}

    def to_prometheus(self) -> str:
        """Format as Prometheus text."""
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            for label_values, observations in self._observations.items():
                total = sum(observations)
                count = len(observations)

                labels_prefix = ""
                if label_values:
                    labels_prefix = ",".join(
                        f'{l}="{v}"' for l, v in zip(self._label_names, label_values)
                    )

                # Bucket counts
                for bucket in self.buckets:
                    bucket_count = sum(1 for o in observations if o <= bucket)
                    if labels_prefix:
                        lines.append(
                            f'{self.name}_bucket{{{labels_prefix},le="{bucket}"}} {bucket_count}'
                        )
                    else:
                        lines.append(f'{self.name}_bucket{{le="{bucket}"}} {bucket_count}')

                # +Inf bucket
                if labels_prefix:
                    lines.append(f'{self.name}_bucket{{{labels_prefix},le="+Inf"}} {count}')
                    lines.append(f"{self.name}_sum{{{labels_prefix}}} {total}")
                    lines.append(f"{self.name}_count{{{labels_prefix}}} {count}")
                else:
                    lines.append(f'{self.name}_bucket{{le="+Inf"}} {count}')
                    lines.append(f"{self.name}_sum {total}")
                    lines.append(f"{self.name}_count {count}")

        return "\n".join(lines)


class HistogramWithLabels:
    """Histogram with specific label values."""

    def __init__(self, parent: Histogram, label_values: tuple):
        self._parent = parent
        self._label_values = label_values

    def observe(self, value: float) -> None:
        """Record an observation."""
        self._parent._observe_labels(self._label_values, value)


# =============================================================================
# Trade Metrics
# =============================================================================

trades_total = Counter(
    name="tinywindow_trades_total",
    description="Total number of trades executed",
    labels=["status", "symbol"],
)

trade_pnl_usd = Histogram(
    name="tinywindow_trade_pnl_usd",
    description="Trade profit/loss in USD",
    buckets=(-1000, -500, -100, -50, -10, 0, 10, 50, 100, 500, 1000),
)

trade_amount_usd = Histogram(
    name="tinywindow_trade_amount_usd",
    description="Trade amount in USD",
    buckets=(100, 500, 1000, 2500, 5000, 10000, 25000, 50000),
)

win_rate = Gauge(
    name="tinywindow_win_rate",
    description="Current win rate percentage",
)


# =============================================================================
# Position Metrics
# =============================================================================

active_positions = Gauge(
    name="tinywindow_active_positions",
    description="Number of active positions",
    labels=["symbol"],
)

portfolio_value_usd = Gauge(
    name="tinywindow_portfolio_value_usd",
    description="Total portfolio value in USD",
)

unrealized_pnl_usd = Gauge(
    name="tinywindow_unrealized_pnl_usd",
    description="Unrealized profit/loss in USD",
)


# =============================================================================
# Risk Metrics
# =============================================================================

drawdown_pct = Gauge(
    name="tinywindow_drawdown_pct",
    description="Current drawdown percentage",
)

daily_pnl_pct = Gauge(
    name="tinywindow_daily_pnl_pct",
    description="Daily profit/loss percentage",
)

leverage_ratio = Gauge(
    name="tinywindow_leverage_ratio",
    description="Current leverage ratio",
)

portfolio_var_95 = Gauge(
    name="tinywindow_portfolio_var_95",
    description="95% Value at Risk in USD",
)


# =============================================================================
# API Metrics
# =============================================================================

api_latency_seconds = Histogram(
    name="tinywindow_api_latency_seconds",
    description="API call latency in seconds",
    labels=["service"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

api_errors_total = Counter(
    name="tinywindow_api_errors_total",
    description="Total number of API errors",
    labels=["service", "error_type"],
)

api_requests_total = Counter(
    name="tinywindow_api_requests_total",
    description="Total number of API requests",
    labels=["service"],
)


# =============================================================================
# Agent Metrics
# =============================================================================

agent_decisions_total = Counter(
    name="tinywindow_agent_decisions_total",
    description="Total number of agent decisions",
    labels=["action", "agent"],
)

agent_confidence = Histogram(
    name="tinywindow_agent_confidence",
    description="Agent decision confidence scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)


# =============================================================================
# Safety Metrics
# =============================================================================

circuit_breaker_trips = Counter(
    name="tinywindow_circuit_breaker_trips",
    description="Number of circuit breaker trips",
    labels=["reason"],
)

kill_switch_activations = Counter(
    name="tinywindow_kill_switch_activations",
    description="Number of kill switch activations",
    labels=["mode"],
)


# =============================================================================
# Metrics Registry
# =============================================================================

_ALL_METRICS = [
    trades_total,
    trade_pnl_usd,
    trade_amount_usd,
    win_rate,
    active_positions,
    portfolio_value_usd,
    unrealized_pnl_usd,
    drawdown_pct,
    daily_pnl_pct,
    leverage_ratio,
    portfolio_var_95,
    api_latency_seconds,
    api_errors_total,
    api_requests_total,
    agent_decisions_total,
    agent_confidence,
    circuit_breaker_trips,
    kill_switch_activations,
]


def generate_metrics() -> str:
    """Generate all metrics in Prometheus text format."""
    output = []
    for metric in _ALL_METRICS:
        prometheus_text = metric.to_prometheus()
        if prometheus_text.strip():
            output.append(prometheus_text)
    return "\n\n".join(output)


# =============================================================================
# Metrics HTTP Server
# =============================================================================


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics endpoint."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/metrics":
            content = generate_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class MetricsServer:
    """HTTP server for Prometheus metrics."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        """Initialize metrics server.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the metrics server in a background thread."""
        if self._server is not None:
            logger.warning("Metrics server already running")
            return

        self._server = HTTPServer((self.host, self.port), MetricsHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Metrics server started on http://{self.host}:{self.port}/metrics")

    def stop(self) -> None:
        """Stop the metrics server."""
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("Metrics server stopped")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server is not None
