"""Metrics collection and reporting for operational visibility.

Provides Prometheus-compatible metrics for monitoring:
- API request counts and latencies
- Worker job processing rates
- Database connection status
- Qdrant collection metrics
- Failure and dead-letter counts
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Track API request metrics."""
    count: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    latency_histogram: dict[str, int] = field(default_factory=lambda: Counter())


@dataclass
class JobMetrics:
    """Track ingestion job metrics."""
    queued: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_letter: int = 0
    total_processing_time_ms: float = 0.0


class MetricsCollector:
    """Collect and report operational metrics.

    This is a lightweight in-memory metrics collector suitable for:
    - Health check endpoints
    - Prometheus metrics export
    - Log-based metrics aggregation

    For production at scale, consider replacing with Prometheus client library.
    """

    def __init__(self):
        self.request_metrics: dict[str, RequestMetrics] = {}
        self.job_metrics = JobMetrics()
        self.start_time = time.time()

    def record_request(self, endpoint: str, latency_ms: float, error: bool = False):
        """Record an API request."""
        if endpoint not in self.request_metrics:
            self.request_metrics[endpoint] = RequestMetrics()

        metric = self.request_metrics[endpoint]
        metric.count += 1
        metric.total_latency_ms += latency_ms

        if error:
            metric.errors += 1

        # Simple histogram buckets
        bucket = f"le_{int(latency_ms // 100 + 1) * 100}ms"
        metric.latency_histogram[bucket] += 1

    def record_job_status(self, status: str, processing_time_ms: float = 0):
        """Record a job status change."""
        if status == "queued":
            self.job_metrics.queued += 1
        elif status == "succeeded":
            self.job_metrics.succeeded += 1
        elif status == "failed":
            self.job_metrics.failed += 1
        elif status == "dead_letter":
            self.job_metrics.dead_letter += 1

        self.job_metrics.total_processing_time_ms += processing_time_ms

    def get_request_summary(self) -> dict[str, Any]:
        """Get summary of request metrics."""
        total_requests = sum(m.count for m in self.request_metrics.values())
        total_errors = sum(m.errors for m in self.request_metrics.values())
        total_latency = sum(m.total_latency_ms for m in self.request_metrics.values())

        avg_latency = total_latency / total_requests if total_requests > 0 else 0
        error_rate = total_errors / total_requests if total_requests > 0 else 0

        return {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": round(error_rate, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "by_endpoint": {
                endpoint: {
                    "count": metric.count,
                    "errors": metric.errors,
                    "avg_latency_ms": round(
                        metric.total_latency_ms / metric.count, 2
                    ) if metric.count > 0 else 0,
                }
                for endpoint, metric in self.request_metrics.items()
            },
        }

    def get_job_summary(self) -> dict[str, Any]:
        """Get summary of job metrics."""
        total = (
            self.job_metrics.succeeded
            + self.job_metrics.failed
            + self.job_metrics.dead_letter
        )

        return {
            "queued": self.job_metrics.queued,
            "succeeded": self.job_metrics.succeeded,
            "failed": self.job_metrics.failed,
            "dead_letter": self.job_metrics.dead_letter,
            "total_processed": total,
            "success_rate": round(
                self.job_metrics.succeeded / total, 4
            ) if total > 0 else 0,
            "dead_letter_rate": round(
                self.job_metrics.dead_letter / total, 4
            ) if total > 0 else 0,
        }

    def get_uptime_seconds(self) -> float:
        """Get service uptime in seconds."""
        return time.time() - self.start_time

    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-compatible metrics output."""
        lines = []

        # Request metrics
        lines.append("# HELP ragkb_requests_total Total API requests")
        lines.append("# TYPE ragkb_requests_total counter")
        for endpoint, metric in self.request_metrics.items():
            lines.append(
                f'ragkb_requests_total{{endpoint="{endpoint}"}} {metric.count}'
            )

        # Error metrics
        lines.append("# HELP ragkb_request_errors_total Total API request errors")
        lines.append("# TYPE ragkb_request_errors_total counter")
        for endpoint, metric in self.request_metrics.items():
            lines.append(
                f'ragkb_request_errors_total{{endpoint="{endpoint}"}} {metric.errors}'
            )

        # Job metrics
        lines.append("# HELP ragkb_jobs_total Total jobs processed")
        lines.append("# TYPE ragkb_jobs_total counter")
        lines.append(f'ragkb_jobs_total{{status="succeeded"}} {self.job_metrics.succeeded}')
        lines.append(f'ragkb_jobs_total{{status="failed"}} {self.job_metrics.failed}')
        lines.append(f'ragkb_jobs_total{{status="dead_letter"}} {self.job_metrics.dead_letter}')

        # Uptime
        lines.append("# HELP ragkb_uptime_seconds Service uptime")
        lines.append("# TYPE ragkb_uptime_seconds gauge")
        lines.append(f"ragkb_uptime_seconds {self.get_uptime_seconds()}")

        return "\n".join(lines)


# Global metrics collector
_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def record_request_metric(endpoint: str, latency_ms: float, error: bool = False):
    """Convenience function to record a request metric."""
    get_metrics().record_request(endpoint, latency_ms, error)


def record_job_metric(status: str, processing_time_ms: float = 0):
    """Convenience function to record a job metric."""
    get_metrics().record_job_status(status, processing_time_ms)
