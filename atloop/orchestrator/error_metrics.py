"""Error metrics collection for monitoring and debugging."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorMetric:
    """Single error metric entry."""

    error_type: str
    error_message: str
    phase: str
    step: int
    timestamp: str
    category: str  # "recoverable" or "fatal"
    context: Optional[str] = None


class ErrorMetricsCollector:
    """Collects error metrics for monitoring and debugging."""

    def __init__(self):
        """Initialize error metrics collector."""
        self.errors: List[ErrorMetric] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_by_phase: Dict[str, int] = defaultdict(int)
        self.error_by_type: Dict[str, int] = defaultdict(int)

    def record_error(
        self,
        error: Exception,
        phase: str,
        step: int,
        category: str,
        context: Optional[str] = None,
    ) -> None:
        """
        Record an error metric.

        Args:
            error: The exception that occurred
            phase: Current phase (DISCOVER, PLAN, ACT, VERIFY)
            step: Current step number
            category: Error category ("recoverable" or "fatal")
            context: Optional context about where error occurred
        """
        from datetime import datetime

        error_type = type(error).__name__
        error_msg = str(error)[:200]  # Truncate long messages

        metric = ErrorMetric(
            error_type=error_type,
            error_message=error_msg,
            phase=phase,
            step=step,
            timestamp=datetime.now().isoformat(),
            category=category,
            context=context,
        )

        self.errors.append(metric)
        self.error_counts[category] += 1
        self.error_by_phase[phase] += 1
        self.error_by_type[error_type] += 1

        logger.debug(
            f"[ErrorMetrics] Recorded {category} error: {error_type} in {phase} at step {step}"
        )

    def get_summary(self) -> Dict[str, any]:
        """
        Get error metrics summary.

        Returns:
            Dictionary with error statistics
        """
        total_errors = len(self.errors)
        recoverable_count = self.error_counts.get("recoverable", 0)
        fatal_count = self.error_counts.get("fatal", 0)

        return {
            "total_errors": total_errors,
            "recoverable_errors": recoverable_count,
            "fatal_errors": fatal_count,
            "errors_by_phase": dict(self.error_by_phase),
            "errors_by_type": dict(self.error_by_type),
            "recent_errors": [
                {
                    "type": e.error_type,
                    "message": e.error_message[:100],
                    "phase": e.phase,
                    "step": e.step,
                    "category": e.category,
                }
                for e in self.errors[-10:]  # Last 10 errors
            ],
        }

    def log_summary(self) -> None:
        """Log error metrics summary."""
        summary = self.get_summary()
        logger.info(f"[ErrorMetrics] Summary: {summary['total_errors']} total errors")
        logger.info(
            f"[ErrorMetrics] Recoverable: {summary['recoverable_errors']}, "
            f"Fatal: {summary['fatal_errors']}"
        )
        if summary["errors_by_phase"]:
            logger.info(f"[ErrorMetrics] By phase: {summary['errors_by_phase']}")
        if summary["errors_by_type"]:
            logger.info(f"[ErrorMetrics] By type: {summary['errors_by_type']}")

    def reset(self) -> None:
        """Reset all collected metrics."""
        self.errors.clear()
        self.error_counts.clear()
        self.error_by_phase.clear()
        self.error_by_type.clear()
