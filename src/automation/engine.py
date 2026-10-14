"""Main automation engine orchestrating routing, runbooks, SLAs, and notifications."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..integrations.base import TicketingProvider, UnifiedTicket
from ..integrations.slack_notifier import NotificationDispatcher
from .rules_engine import RulesEngine
from .sla_monitor import SLAMonitor
from .runbooks.base import BaseRunbook
from .runbooks.password_reset import PasswordResetRunbook
from .runbooks.software_access import SoftwareAccessRunbook

logger = logging.getLogger("automation.engine")


class AutomationEngine:
    """Orchestrates incoming ticket triage, runbook execution, routing, and notifications."""

    def __init__(
        self,
        provider: TicketingProvider,
        rules_engine: Optional[RulesEngine] = None,
        sla_monitor: Optional[SLAMonitor] = None,
        notifier: Optional[NotificationDispatcher] = None,
        runbooks: Optional[List[BaseRunbook]] = None,
    ):
        self.provider = provider
        self.rules_engine = rules_engine or RulesEngine()
        self.sla_monitor = sla_monitor or SLAMonitor()
        self.notifier = notifier or NotificationDispatcher()
        self.runbooks = runbooks or [PasswordResetRunbook(), SoftwareAccessRunbook()]

    def process_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming ticket through automated triage and execution pipeline.

        Returns:
            Dict detailing the actions executed (auto-resolution, routing, SLA target).
        """
        ticket_id = ticket_data.get("id", "UNKNOWN")
        priority = ticket_data.get("priority", 3)

        # 1. Step 1: Check Auto-Resolution Runbooks
        for runbook in self.runbooks:
            if runbook.can_handle(ticket_data):
                logger.info(f"Triggering auto-resolution runbook '{runbook.name}' for ticket {ticket_id}")
                runbook_result = runbook.execute(ticket_data)
                if runbook_result.success:
                    # Update ticket in provider
                    updated_ticket = self.provider.resolve_ticket(
                        ticket_id=ticket_id,
                        resolution_notes=runbook_result.resolution_notes,
                        actor="Automated-Runbook-Engine",
                    )
                    # Send notification
                    self.notifier.notify_auto_resolution(
                        ticket_id=ticket_id,
                        runbook_name=runbook.name,
                        notes=runbook_result.resolution_notes,
                    )
                    return {
                        "ticket_id": ticket_id,
                        "status": "auto_resolved",
                        "runbook": runbook.name,
                        "action_taken": runbook_result.action_taken,
                        "ticket": updated_ticket,
                    }

        # 2. Step 2: Routing & Assignment Evaluation (Rules baseline)
        routing_info = self.rules_engine.evaluate_routing(ticket_data)
        target_group = routing_info["assignment_group"]

        # 3. Step 3: SLA Deadline Calculation
        created_at = datetime.now(timezone.utc)
        sla_deadline = self.sla_monitor.calculate_deadline(created_at, priority)

        # 4. Step 4: Apply Updates via Provider
        updates = {
            "assignment_group": target_group,
            "state": "assigned",
        }
        updated_ticket = self.provider.update_ticket(ticket_id, updates, actor="Automation-Triage-Engine")

        # 5. Step 5: Critical Incident Notification
        if priority in (1, 2):
            self.notifier.notify_critical_ticket(ticket_data)

        return {
            "ticket_id": ticket_id,
            "status": "routed",
            "assignment_group": target_group,
            "routing_confidence": routing_info["confidence"],
            "sla_deadline": sla_deadline.isoformat(),
            "ticket": updated_ticket,
        }
