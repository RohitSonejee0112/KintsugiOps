"""SLA monitoring, countdown calculation, and breach escalation engine."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Default ITIL SLA policy: (response_minutes, resolution_minutes, warning_threshold)
DEFAULT_SLA_POLICY = {
    1: {"response_min": 15, "resolution_min": 120, "warning_pct": 0.75},    # P1: 2 hrs
    2: {"response_min": 30, "resolution_min": 240, "warning_pct": 0.75},    # P2: 4 hrs
    3: {"response_min": 120, "resolution_min": 1440, "warning_pct": 0.80},  # P3: 24 hrs
    4: {"response_min": 240, "resolution_min": 4320, "warning_pct": 0.85},  # P4: 72 hrs
}


class SLAMonitor:
    """Evaluates ticket SLA timers, calculates deadlines, and flags breaches and warnings."""

    def __init__(self, policy: Optional[Dict[int, Dict[str, Any]]] = None):
        self.policy = policy or DEFAULT_SLA_POLICY

    def calculate_deadline(self, created_at: datetime, priority: int) -> datetime:
        """Calculate the target resolution deadline datetime."""
        p_cfg = self.policy.get(priority, self.policy[3])
        return created_at + timedelta(minutes=p_cfg["resolution_min"])

    def evaluate_ticket(
        self,
        created_at: datetime,
        priority: int,
        current_time: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Evaluate current SLA health for a ticket.

        Returns:
            dict with:
                - target_deadline: datetime
                - minutes_allowed: int
                - minutes_elapsed: float
                - minutes_remaining: float
                - pct_elapsed: float (0.0 to 1.0+)
                - is_breached: bool
                - is_warning: bool (breach imminent)
        """
        now = current_time or datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        p_cfg = self.policy.get(priority, self.policy[3])
        total_allowed_min = p_cfg["resolution_min"]
        deadline = created_at + timedelta(minutes=total_allowed_min)

        end_time = resolved_at or now
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        elapsed_seconds = (end_time - created_at).total_seconds()
        elapsed_min = max(0.0, elapsed_seconds / 60.0)
        remaining_min = (deadline - now).total_seconds() / 60.0
        pct_elapsed = elapsed_min / total_allowed_min if total_allowed_min > 0 else 1.0

        is_breached = elapsed_min > total_allowed_min
        # Warning if not breached, not resolved, and elapsed >= warning threshold
        is_warning = (not is_breached) and (resolved_at is None) and (pct_elapsed >= p_cfg["warning_pct"])

        return {
            "target_deadline": deadline,
            "minutes_allowed": total_allowed_min,
            "minutes_elapsed": round(elapsed_min, 1),
            "minutes_remaining": round(remaining_min, 1),
            "pct_elapsed": round(pct_elapsed, 3),
            "is_breached": is_breached,
            "is_warning": is_warning,
        }
