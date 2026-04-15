"""Auto-scaling service for ingestion workers.

Monitors queue depth and automatically scales workers up/down based on
configured thresholds. Designed for production safety with cooldowns,
rate limiting, and manual override capabilities.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ingestion_job import IngestionJob
from .config import get_settings
from .database import get_session_factory

logger = logging.getLogger(__name__)


@dataclass
class QueueMetrics:
    """Current state of the ingestion queue."""

    queue_depth: int = 0
    oldest_job_age_seconds: float | None = None
    active_jobs: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScalingDecision:
    """Result of a scaling evaluation."""

    action: str  # "scale_up", "scale_down", "emergency_scale", "none"
    reason: str
    from_workers: int
    to_workers: int
    metrics: QueueMetrics
    cooldown_active: bool = False


class Autoscaler:
    """Production-safe autoscaler for ingestion workers.

    Uses queue depth as the primary signal with conservative thresholds
    and cooldowns to prevent thrashing.
    """

    def __init__(self) -> None:
        """Initialize the autoscaler with configuration."""
        settings = get_settings()

        # Core configuration
        self.enabled = settings.autoscaler_enabled
        self.min_workers = settings.autoscaler_min_workers
        self.max_workers = settings.autoscaler_max_workers
        self.check_interval = settings.autoscaler_check_interval_seconds

        # Scale up configuration
        self.scale_up_threshold = settings.autoscaler_scale_up_queue_threshold
        self.scale_up_duration = settings.autoscaler_scale_up_duration_seconds
        self.scale_up_cooldown = settings.autoscaler_scale_up_cooldown_seconds

        # Scale down configuration
        self.scale_down_threshold = settings.autoscaler_scale_down_queue_threshold
        self.scale_down_duration = settings.autoscaler_scale_down_duration_seconds
        self.scale_down_cooldown = settings.autoscaler_scale_down_cooldown_seconds

        # Emergency scaling
        self.emergency_threshold = settings.autoscaler_emergency_queue_threshold

        # State tracking
        self.current_workers = self.min_workers
        self.last_scale_up: datetime | None = None
        self.last_scale_down: datetime | None = None
        self.sustained_high_queue_start: datetime | None = None
        self.sustained_low_queue_start: datetime | None = None

        # Rate limiting
        self.scale_events_this_hour: list[datetime] = []
        self.max_scale_events_per_hour = 6

        if self.enabled:
            logger.info(
                "autoscaler_initialized",
                min_workers=self.min_workers,
                max_workers=self.max_workers,
                scale_up_threshold=self.scale_up_threshold,
                scale_down_threshold=self.scale_down_threshold,
            )

    async def get_metrics(self, session: AsyncSession) -> QueueMetrics:
        """Fetch current queue metrics from database."""
        # Count queued and active jobs
        active_statuses = ["queued", "parsing", "chunking", "embedding", "indexing"]
        queue_stmt = select(func.count()).where(IngestionJob.status.in_(active_statuses))
        queue_result = await session.execute(queue_stmt)
        queue_depth = queue_result.scalar() or 0

        # Count only queued jobs
        queued_stmt = select(func.count()).where(IngestionJob.status == "queued")
        queued_result = await session.execute(queued_stmt)
        queued_count = queued_result.scalar() or 0

        # Find oldest queued job
        oldest_stmt = (
            select(IngestionJob.created_at)
            .where(IngestionJob.status == "queued")
            .order_by(IngestionJob.created_at.asc())
            .limit(1)
        )
        oldest_result = await session.execute(oldest_stmt)
        oldest_job_time = oldest_result.scalar()

        oldest_job_age = None
        if oldest_job_time:
            oldest_job_age = (
                datetime.now(timezone.utc) - oldest_job_time
            ).total_seconds()

        return QueueMetrics(
            queue_depth=queue_depth,
            oldest_job_age_seconds=oldest_job_age,
            active_jobs=queue_depth,
        )

    def _is_in_cooldown(self, last_scale: datetime | None, cooldown: int) -> bool:
        """Check if we're still in cooldown period."""
        if last_scale is None:
            return False
        elapsed = (datetime.now(timezone.utc) - last_scale).total_seconds()
        return elapsed < cooldown

    def _cleanup_old_scale_events(self) -> None:
        """Remove scale events older than 1 hour from tracking."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        self.scale_events_this_hour = [
            t for t in self.scale_events_this_hour if t > cutoff
        ]

    def _can_scale(self) -> bool:
        """Check if we're within rate limits."""
        self._cleanup_old_scale_events()
        return len(self.scale_events_this_hour) < self.max_scale_events_per_hour

    def _update_sustained_tracking(self, metrics: QueueMetrics) -> None:
        """Track how long queue has been high/low."""
        now = datetime.now(timezone.utc)

        # Track high queue
        if metrics.queue_depth >= self.scale_up_threshold:
            if self.sustained_high_queue_start is None:
                self.sustained_high_queue_start = now
        else:
            self.sustained_high_queue_start = None

        # Track low queue
        if metrics.queue_depth <= self.scale_down_threshold:
            if self.sustained_low_queue_start is None:
                self.sustained_low_queue_start = now
        else:
            self.sustained_low_queue_start = None

    def _check_sustained_duration(
        self, start: datetime | None, required: int
    ) -> bool:
        """Check if a condition has been sustained for required duration."""
        if start is None:
            return False
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        return elapsed >= required

    def evaluate_scaling(self, metrics: QueueMetrics) -> ScalingDecision:
        """Evaluate whether to scale based on current metrics.

        Returns a ScalingDecision with the recommended action and reason.
        """
        if not self.enabled:
            return ScalingDecision(
                action="none",
                reason="autoscaler_disabled",
                from_workers=self.current_workers,
                to_workers=self.current_workers,
                metrics=metrics,
            )

        self._update_sustained_tracking(metrics)

        # Emergency scaling: immediate response to critical backlog
        if metrics.queue_depth >= self.emergency_threshold:
            if self.current_workers < self.max_workers:
                return ScalingDecision(
                    action="emergency_scale",
                    reason=f"emergency_queue_depth_{metrics.queue_depth}",
                    from_workers=self.current_workers,
                    to_workers=self.max_workers,
                    metrics=metrics,
                )

        # Scale up check
        if self.current_workers < self.max_workers:
            queue_sustained = self._check_sustained_duration(
                self.sustained_high_queue_start, self.scale_up_duration
            )

            if queue_sustained:
                in_cooldown = self._is_in_cooldown(
                    self.last_scale_up, self.scale_up_cooldown
                )
                can_scale = self._can_scale()

                if not in_cooldown and can_scale:
                    return ScalingDecision(
                        action="scale_up",
                        reason=f"queue_depth_sustained_{metrics.queue_depth}",
                        from_workers=self.current_workers,
                        to_workers=self.current_workers + 1,
                        metrics=metrics,
                    )
                elif in_cooldown:
                    return ScalingDecision(
                        action="none",
                        reason="scale_up_cooldown_active",
                        from_workers=self.current_workers,
                        to_workers=self.current_workers,
                        metrics=metrics,
                        cooldown_active=True,
                    )
                else:
                    return ScalingDecision(
                        action="none",
                        reason="rate_limit_reached",
                        from_workers=self.current_workers,
                        to_workers=self.current_workers,
                        metrics=metrics,
                    )

        # Scale down check
        if self.current_workers > self.min_workers:
            low_queue_sustained = self._check_sustained_duration(
                self.sustained_low_queue_start, self.scale_down_duration
            )

            if low_queue_sustained:
                in_cooldown = self._is_in_cooldown(
                    self.last_scale_down, self.scale_down_cooldown
                )

                if not in_cooldown:
                    return ScalingDecision(
                        action="scale_down",
                        reason=f"queue_low_sustained_{metrics.queue_depth}",
                        from_workers=self.current_workers,
                        to_workers=self.current_workers - 1,
                        metrics=metrics,
                    )
                else:
                    return ScalingDecision(
                        action="none",
                        reason="scale_down_cooldown_active",
                        from_workers=self.current_workers,
                        to_workers=self.current_workers,
                        metrics=metrics,
                        cooldown_active=True,
                    )

        return ScalingDecision(
            action="none",
            reason="no_scaling_needed",
            from_workers=self.current_workers,
            to_workers=self.current_workers,
            metrics=metrics,
        )

    async def execute_scaling(self, decision: ScalingDecision) -> bool:
        """Execute a scaling decision.

        This is a placeholder - actual implementation would interface with
        Docker API, Kubernetes, or orchestrator to adjust worker count.

        Returns True if scaling was successful, False otherwise.
        """
        if decision.action == "none":
            return True

        # Log the scaling action
        logger.info(
            "scaling_action",
            action=decision.action,
            reason=decision.reason,
            from_workers=decision.from_workers,
            to_workers=decision.to_workers,
            queue_depth=decision.metrics.queue_depth,
            oldest_job_age=decision.metrics.oldest_job_age_seconds,
        )

        # Update state
        self.current_workers = decision.to_workers
        now = datetime.now(timezone.utc)

        if decision.action in ("scale_up", "emergency_scale"):
            self.last_scale_up = now
        elif decision.action == "scale_down":
            self.last_scale_down = now

        self.scale_events_this_hour.append(now)

        # TODO: Integrate with actual orchestrator
        # Examples:
        # - Docker: docker compose up -d --scale worker={count}
        # - Kubernetes: kubectl scale deployment worker --replicas={count}
        # - ECS: aws ecs update-service --service worker --desired-count {count}

        logger.warning(
            "scaling_execution_placeholder: "
            "Scaling decision made but no orchestrator integration yet. "
            "Current count: %d",
            self.current_workers,
        )

        return True

    async def check_and_scale(self, session: AsyncSession) -> ScalingDecision:
        """Main entry point: check metrics and execute scaling if needed."""
        metrics = await self.get_metrics(session)
        decision = self.evaluate_scaling(metrics)

        if decision.action != "none":
            await self.execute_scaling(decision)

        return decision

    async def run_loop(self) -> None:
        """Run the autoscaler check loop continuously.

        This should be run as a background task alongside the worker.
        """
        if not self.enabled:
            logger.info("autoscaler_disabled_skipping_loop")
            return

        factory = get_session_factory()
        logger.info(
            "autoscaler_loop_started",
            check_interval=self.check_interval,
        )

        while True:
            try:
                async with factory() as session:
                    decision = await self.check_and_scale(session)

                    # Log decision details
                    if decision.action != "none":
                        logger.info(
                            "autoscaler_decision",
                            action=decision.action,
                            reason=decision.reason,
                            workers=decision.to_workers,
                            queue_depth=decision.metrics.queue_depth,
                        )
                    else:
                        logger.debug(
                            "autoscaler_no_action",
                            reason=decision.reason,
                            queue_depth=decision.metrics.queue_depth,
                            current_workers=self.current_workers,
                        )

            except Exception as e:
                logger.error("autoscaler_loop_error", error=str(e), exc_info=True)

            await asyncio.sleep(self.check_interval)


# Global autoscaler instance
_autoscaler: Autoscaler | None = None


def get_autoscaler() -> Autoscaler:
    """Get or create the global autoscaler instance."""
    global _autoscaler
    if _autoscaler is None:
        _autoscaler = Autoscaler()
    return _autoscaler


def reset_autoscaler() -> None:
    """Reset the global autoscaler (useful for testing)."""
    global _autoscaler
    _autoscaler = None
