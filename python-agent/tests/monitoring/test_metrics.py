"""Tests for Prometheus metrics."""

import pytest
from tinywindow.monitoring.metrics import (
    Counter,
    Gauge,
    Histogram,
    trades_total,
    trade_pnl_usd,
    win_rate,
    portfolio_value_usd,
    drawdown_pct,
    api_latency_seconds,
    api_errors_total,
    agent_decisions_total,
    circuit_breaker_trips,
    MetricsServer,
    generate_metrics,
)


class TestCounter:
    """Test Counter metric."""

    def test_counter_increment(self):
        """Test counter increment."""
        counter = Counter("test_counter", "Test counter")
        counter.inc()
        counter.inc(2)
        values = counter.get_all()
        assert values[()] == 3

    def test_counter_with_labels(self):
        """Test counter with labels."""
        counter = Counter("test_counter", "Test counter", labels=["status"])
        counter.labels(status="success").inc()
        counter.labels(status="error").inc(2)
        values = counter.get_all()
        assert values[("success",)] == 1
        assert values[("error",)] == 2

    def test_counter_prometheus_format(self):
        """Test Prometheus text format output."""
        counter = Counter("test_counter", "Test counter")
        counter.inc(5)
        output = counter.to_prometheus()
        assert "# HELP test_counter Test counter" in output
        assert "# TYPE test_counter counter" in output
        assert "test_counter 5" in output


class TestGauge:
    """Test Gauge metric."""

    def test_gauge_set(self):
        """Test gauge set."""
        gauge = Gauge("test_gauge", "Test gauge")
        gauge.set(42)
        values = gauge.get_all()
        assert values[()] == 42

    def test_gauge_inc_dec(self):
        """Test gauge increment and decrement."""
        gauge = Gauge("test_gauge", "Test gauge")
        gauge.set(10)
        gauge.inc(5)
        gauge.dec(3)
        values = gauge.get_all()
        assert values[()] == 12

    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauge = Gauge("test_gauge", "Test gauge", labels=["symbol"])
        gauge.labels(symbol="BTC").set(50000)
        gauge.labels(symbol="ETH").set(3000)
        values = gauge.get_all()
        assert values[("BTC",)] == 50000
        assert values[("ETH",)] == 3000


class TestHistogram:
    """Test Histogram metric."""

    def test_histogram_observe(self):
        """Test histogram observe."""
        histogram = Histogram("test_histogram", "Test histogram")
        histogram.observe(0.5)
        histogram.observe(1.5)
        histogram.observe(2.5)
        observations = histogram.get_all()
        assert len(observations[()]) == 3

    def test_histogram_with_labels(self):
        """Test histogram with labels."""
        histogram = Histogram("test_histogram", "Test histogram", labels=["service"])
        histogram.labels(service="api").observe(0.1)
        histogram.labels(service="db").observe(0.05)
        observations = histogram.get_all()
        assert ("api",) in observations
        assert ("db",) in observations

    def test_histogram_prometheus_format(self):
        """Test Prometheus text format output."""
        histogram = Histogram("test_histogram", "Test histogram")
        histogram.observe(0.5)
        output = histogram.to_prometheus()
        assert "# HELP test_histogram Test histogram" in output
        assert "# TYPE test_histogram histogram" in output
        assert "_bucket" in output
        assert "_sum" in output
        assert "_count" in output


class TestPredefinedMetrics:
    """Test predefined metrics."""

    def test_trades_total(self):
        """Test trades_total counter."""
        trades_total.labels(status="filled", symbol="BTC/USDT").inc()
        values = trades_total.get_all()
        assert ("filled", "BTC/USDT") in values

    def test_win_rate_gauge(self):
        """Test win_rate gauge."""
        win_rate.set(65.5)
        values = win_rate.get_all()
        assert values[()] == 65.5

    def test_portfolio_value(self):
        """Test portfolio_value_usd gauge."""
        portfolio_value_usd.set(100000)
        values = portfolio_value_usd.get_all()
        assert values[()] == 100000

    def test_drawdown(self):
        """Test drawdown_pct gauge."""
        drawdown_pct.set(-5.5)
        values = drawdown_pct.get_all()
        assert values[()] == -5.5

    def test_api_latency(self):
        """Test api_latency_seconds histogram."""
        api_latency_seconds.labels(service="claude").observe(0.5)
        observations = api_latency_seconds.get_all()
        assert ("claude",) in observations

    def test_api_errors(self):
        """Test api_errors_total counter."""
        api_errors_total.labels(service="binance", error_type="timeout").inc()
        values = api_errors_total.get_all()
        assert ("binance", "timeout") in values

    def test_agent_decisions(self):
        """Test agent_decisions_total counter."""
        agent_decisions_total.labels(action="BUY", agent="agent-1").inc()
        values = agent_decisions_total.get_all()
        assert ("BUY", "agent-1") in values

    def test_circuit_breaker_trips(self):
        """Test circuit_breaker_trips counter."""
        circuit_breaker_trips.labels(reason="daily_loss").inc()
        values = circuit_breaker_trips.get_all()
        assert ("daily_loss",) in values


class TestGenerateMetrics:
    """Test metrics generation."""

    def test_generate_metrics_format(self):
        """Test generate_metrics returns valid format."""
        # Set some metrics first
        portfolio_value_usd.set(50000)

        output = generate_metrics()
        assert isinstance(output, str)
        # Should have HELP and TYPE comments
        assert "# HELP" in output
        assert "# TYPE" in output


class TestMetricsServer:
    """Test MetricsServer."""

    def test_server_initialization(self):
        """Test server initialization."""
        server = MetricsServer(host="127.0.0.1", port=8001)
        assert server.host == "127.0.0.1"
        assert server.port == 8001
        assert not server.is_running

    def test_server_start_stop(self):
        """Test server start and stop."""
        server = MetricsServer(host="127.0.0.1", port=8002)
        server.start()
        assert server.is_running

        server.stop()
        assert not server.is_running

    def test_server_double_start(self):
        """Test starting server twice doesn't crash."""
        server = MetricsServer(host="127.0.0.1", port=8003)
        server.start()
        server.start()  # Should be no-op
        assert server.is_running
        server.stop()
