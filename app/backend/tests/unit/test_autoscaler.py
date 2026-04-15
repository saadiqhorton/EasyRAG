"""Unit tests for the autoscaler module."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.backend.services.autoscaler import (
    Autoscaler,
    QueueMetrics,
    ScalingDecision,
    get_autoscaler,
    reset_autoscaler,
)


@pytest.fixture(autouse=True)
def setup_env_vars(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("ANSWER_LLM_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("ANSWER_LLM_MODEL", "test-model")
    yield


class TestAutoscalerConfiguration:
    """Test autoscaler configuration loading."""

    def test_autoscaler_disabled_by_default(self, monkeypatch):
        """Autoscaler should be disabled by default."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "false")
        from app.backend.services.config import _settings
        import app.backend.services.config as config_module
        config_module._settings = None  # Clear settings cache

        autoscaler = get_autoscaler()
        assert autoscaler.enabled is False

    def test_autoscaler_enabled_via_env(self, monkeypatch):
        """Autoscaler can be enabled via environment variable."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None  # Clear settings cache

        autoscaler = get_autoscaler()
        assert autoscaler.enabled is True

    def test_default_worker_bounds(self, monkeypatch):
        """Default worker bounds are 3-6."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None

        autoscaler = get_autoscaler()
        assert autoscaler.min_workers == 3
        assert autoscaler.max_workers == 6

    def test_custom_worker_bounds(self, monkeypatch):
        """Worker bounds can be customized."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        monkeypatch.setenv("AUTOSCALER_MIN_WORKERS", "2")
        monkeypatch.setenv("AUTOSCALER_MAX_WORKERS", "8")
        import app.backend.services.config as config_module
        config_module._settings = None

        autoscaler = get_autoscaler()
        assert autoscaler.min_workers == 2
        assert autoscaler.max_workers == 8


class TestQueueMetrics:
    """Test queue metrics dataclass."""

    def test_queue_metrics_defaults(self):
        """QueueMetrics has sensible defaults."""
        metrics = QueueMetrics()
        assert metrics.queue_depth == 0
        assert metrics.oldest_job_age_seconds is None
        assert metrics.active_jobs == 0
        assert isinstance(metrics.timestamp, datetime)


class TestEvaluateScaling:
    """Test the scaling decision logic."""

    @pytest.fixture
    def enabled_autoscaler(self, monkeypatch):
        """Create an enabled autoscaler for testing."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        monkeypatch.setenv("AUTOSCALER_MIN_WORKERS", "3")
        monkeypatch.setenv("AUTOSCALER_MAX_WORKERS", "6")
        import app.backend.services.config as config_module
        config_module._settings = None
        return get_autoscaler()

    def test_disabled_autoscaler_returns_none(self):
        """Disabled autoscaler always returns no action."""
        reset_autoscaler()
        autoscaler = Autoscaler()
        autoscaler.enabled = False

        metrics = QueueMetrics(queue_depth=10)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "none"
        assert decision.reason == "autoscaler_disabled"

    def test_no_scaling_when_queue_normal(self, enabled_autoscaler):
        """No scaling when queue depth is within normal range."""
        autoscaler = enabled_autoscaler

        metrics = QueueMetrics(queue_depth=2)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "none"
        assert decision.reason == "no_scaling_needed"

    def test_no_scale_up_immediately(self, enabled_autoscaler):
        """Scale up requires sustained high queue."""
        autoscaler = enabled_autoscaler

        # Queue depth = 6 (above threshold of 5), but not sustained
        metrics = QueueMetrics(queue_depth=6)
        decision = autoscaler.evaluate_scaling(metrics)

        # Should not scale immediately - needs 10 minutes
        assert decision.action == "none"

    def test_scale_up_after_sustained_high_queue(self, enabled_autoscaler):
        """Scale up after queue has been high for required duration."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 3

        # Simulate sustained high queue for 10+ minutes
        autoscaler.sustained_high_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_up_duration + 60
        )

        metrics = QueueMetrics(queue_depth=6)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "scale_up"
        assert decision.from_workers == 3
        assert decision.to_workers == 4

    def test_no_scale_up_at_max_workers(self, enabled_autoscaler):
        """Cannot scale up beyond max_workers."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 6  # At max workers
        autoscaler.sustained_high_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_up_duration + 60
        )

        metrics = QueueMetrics(queue_depth=10)
        decision = autoscaler.evaluate_scaling(metrics)

        # Already at max workers, so no action possible
        assert decision.action == "none"

    def test_scale_down_after_sustained_low_queue(self, enabled_autoscaler):
        """Scale down after queue has been low for required duration."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 4

        # Simulate sustained low queue for 30+ minutes
        autoscaler.sustained_low_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_down_duration + 60
        )

        metrics = QueueMetrics(queue_depth=1)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "scale_down"
        assert decision.from_workers == 4
        assert decision.to_workers == 3

    def test_no_scale_down_at_min_workers(self, enabled_autoscaler):
        """Cannot scale down below min_workers."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 3  # At minimum

        autoscaler.sustained_low_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_down_duration + 60
        )

        metrics = QueueMetrics(queue_depth=0)
        decision = autoscaler.evaluate_scaling(metrics)

        # Should not scale down
        assert decision.action == "none"

    def test_emergency_scale_for_critical_backlog(self, enabled_autoscaler):
        """Emergency scale triggers immediately for critical queue depth."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 3

        # Queue depth = 10 (emergency threshold), no sustainment needed
        metrics = QueueMetrics(queue_depth=10)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "emergency_scale"
        assert decision.to_workers == 6  # Max workers


class TestCooldown:
    """Test cooldown mechanisms."""

    @pytest.fixture
    def enabled_autoscaler(self, monkeypatch):
        """Create an enabled autoscaler for testing."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None
        autoscaler = get_autoscaler()
        autoscaler.current_workers = 3
        return autoscaler

    def test_scale_up_cooldown_blocks_scaling(self, enabled_autoscaler):
        """Recent scale up blocks new scale up during cooldown."""
        autoscaler = enabled_autoscaler

        # Recent scale up
        autoscaler.last_scale_up = datetime.now(timezone.utc) - timedelta(seconds=30)

        # Sustained high queue
        autoscaler.sustained_high_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_up_duration + 60
        )

        metrics = QueueMetrics(queue_depth=6)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "none"
        assert decision.reason == "scale_up_cooldown_active"
        assert decision.cooldown_active is True

    def test_cooldown_expires_after_duration(self, enabled_autoscaler):
        """Cooldown expires after configured duration."""
        autoscaler = enabled_autoscaler

        # Scale up long ago (cooldown expired)
        autoscaler.last_scale_up = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_up_cooldown + 60
        )

        # Sustained high queue
        autoscaler.sustained_high_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_up_duration + 60
        )

        metrics = QueueMetrics(queue_depth=6)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "scale_up"

    def test_scale_down_cooldown_blocks_scaling(self, enabled_autoscaler):
        """Recent scale down blocks new scale down during cooldown."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 4

        # Recent scale down
        autoscaler.last_scale_down = datetime.now(timezone.utc) - timedelta(seconds=30)

        # Sustained low queue
        autoscaler.sustained_low_queue_start = datetime.now(timezone.utc) - timedelta(
            seconds=autoscaler.scale_down_duration + 60
        )

        metrics = QueueMetrics(queue_depth=1)
        decision = autoscaler.evaluate_scaling(metrics)

        assert decision.action == "none"
        assert decision.reason == "scale_down_cooldown_active"


class TestSustainedTracking:
    """Test sustained condition tracking."""

    @pytest.fixture
    def enabled_autoscaler(self, monkeypatch):
        """Create an enabled autoscaler for testing."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None
        autoscaler = get_autoscaler()
        return autoscaler

    def test_high_queue_tracking_starts(self, enabled_autoscaler):
        """High queue tracking starts when threshold exceeded."""
        autoscaler = enabled_autoscaler
        assert autoscaler.sustained_high_queue_start is None

        metrics = QueueMetrics(queue_depth=6)
        autoscaler._update_sustained_tracking(metrics)

        assert autoscaler.sustained_high_queue_start is not None

    def test_high_queue_tracking_resets(self, enabled_autoscaler):
        """High queue tracking resets when queue drops."""
        autoscaler = enabled_autoscaler

        # First set high queue
        autoscaler._update_sustained_tracking(QueueMetrics(queue_depth=6))
        assert autoscaler.sustained_high_queue_start is not None

        # Then drop queue
        autoscaler._update_sustained_tracking(QueueMetrics(queue_depth=2))
        assert autoscaler.sustained_high_queue_start is None

    def test_low_queue_tracking_starts(self, enabled_autoscaler):
        """Low queue tracking starts when below threshold."""
        autoscaler = enabled_autoscaler
        assert autoscaler.sustained_low_queue_start is None

        metrics = QueueMetrics(queue_depth=1)
        autoscaler._update_sustained_tracking(metrics)

        assert autoscaler.sustained_low_queue_start is not None

    def test_sustained_duration_check(self, enabled_autoscaler):
        """Correctly checks if duration has been sustained."""
        autoscaler = enabled_autoscaler

        # Not sustained yet
        start = datetime.now(timezone.utc) - timedelta(seconds=30)
        assert autoscaler._check_sustained_duration(start, 600) is False

        # Sustained long enough
        start = datetime.now(timezone.utc) - timedelta(seconds=700)
        assert autoscaler._check_sustained_duration(start, 600) is True


class TestRateLimiting:
    """Test rate limiting for scale events."""

    @pytest.fixture
    def enabled_autoscaler(self, monkeypatch):
        """Create an enabled autoscaler for testing."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None
        autoscaler = get_autoscaler()
        autoscaler.current_workers = 3
        return autoscaler

    def test_rate_limit_blocks_after_max_events(self, enabled_autoscaler):
        """Rate limit blocks scaling after max events per hour."""
        autoscaler = enabled_autoscaler
        autoscaler.max_scale_events_per_hour = 2

        # Add events at max
        now = datetime.now(timezone.utc)
        autoscaler.scale_events_this_hour = [now, now]

        assert autoscaler._can_scale() is False

    def test_rate_limit_allows_below_max(self, enabled_autoscaler):
        """Rate limit allows scaling below max events."""
        autoscaler = enabled_autoscaler
        autoscaler.max_scale_events_per_hour = 6

        # Add some events but below max
        now = datetime.now(timezone.utc)
        autoscaler.scale_events_this_hour = [now, now]

        assert autoscaler._can_scale() is True

    def test_old_events_cleaned(self, enabled_autoscaler):
        """Old scale events are cleaned from tracking."""
        autoscaler = enabled_autoscaler

        # Add old events (more than 1 hour)
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        autoscaler.scale_events_this_hour = [old, old, old]

        # Cleanup should remove them
        autoscaler._cleanup_old_scale_events()
        assert len(autoscaler.scale_events_this_hour) == 0


class TestExecuteScaling:
    """Test the scaling execution."""

    @pytest.fixture
    def enabled_autoscaler(self, monkeypatch):
        """Create an enabled autoscaler for testing."""
        reset_autoscaler()
        monkeypatch.setenv("AUTOSCALER_ENABLED", "true")
        import app.backend.services.config as config_module
        config_module._settings = None
        return get_autoscaler()

    async def test_execute_scaling_updates_state(self, enabled_autoscaler):
        """Execute scaling updates autoscaler state."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 3

        decision = ScalingDecision(
            action="scale_up",
            reason="test",
            from_workers=3,
            to_workers=4,
            metrics=QueueMetrics(queue_depth=6),
        )

        result = await autoscaler.execute_scaling(decision)
        assert result is True
        assert autoscaler.current_workers == 4
        assert autoscaler.last_scale_up is not None

    async def test_execute_none_does_nothing(self, enabled_autoscaler):
        """Execute with no action doesn't change state."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 3

        decision = ScalingDecision(
            action="none",
            reason="test",
            from_workers=3,
            to_workers=3,
            metrics=QueueMetrics(queue_depth=2),
        )

        result = await autoscaler.execute_scaling(decision)
        assert result is True
        assert autoscaler.current_workers == 3

    async def test_scale_down_updates_state(self, enabled_autoscaler):
        """Scale down updates autoscaler state."""
        autoscaler = enabled_autoscaler
        autoscaler.current_workers = 4

        decision = ScalingDecision(
            action="scale_down",
            reason="test",
            from_workers=4,
            to_workers=3,
            metrics=QueueMetrics(queue_depth=1),
        )

        result = await autoscaler.execute_scaling(decision)
        assert result is True
        assert autoscaler.current_workers == 3
        assert autoscaler.last_scale_down is not None
