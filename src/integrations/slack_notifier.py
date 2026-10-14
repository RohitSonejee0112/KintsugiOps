"""Outbound notification handler for Slack (Block Kit) and Microsoft Teams webhooks."""
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("integrations.notifications")


class NotificationDispatcher:
    """Dispatches formatted message cards to Slack or MS Teams channels."""

    def __init__(self, slack_webhook_url: Optional[str] = None, teams_webhook_url: Optional[str] = None):
        self.slack_url = slack_webhook_url
        self.teams_url = teams_webhook_url
        self.sent_notifications: List[Dict[str, Any]] = []

    def notify_critical_ticket(self, ticket: Dict[str, Any]) -> bool:
        """Send urgent alert when a P1 or P2 incident is logged."""
        priority_str = f"P{ticket.get('priority', 1)} - CRITICAL" if ticket.get("priority") == 1 else f"P{ticket.get('priority', 2)} - HIGH"
        color = "#D32F2F" if ticket.get("priority") == 1 else "#F57C00"

        slack_payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": f"🚨 {priority_str} Incident Detected"}
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Ticket ID:*\n{ticket.get('id')}"},
                                {"type": "mrkdwn", "text": f"*Category:*\n{ticket.get('category')}"},
                                {"type": "mrkdwn", "text": f"*Assignment Group:*\n{ticket.get('assignment_group', 'Unassigned')}"},
                                {"type": "mrkdwn", "text": f"*Caller:*\n{ticket.get('caller_email')}"},
                            ]
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Summary:*\n{ticket.get('title')}\n>{ticket.get('description')[:200]}..."}
                        }
                    ]
                }
            ]
        }
        return self._dispatch(slack_payload, event="critical_incident", ticket_id=ticket.get("id"))

    def notify_auto_resolution(self, ticket_id: str, runbook_name: str, notes: str) -> bool:
        """Send notification when an automated runbook resolves a ticket."""
        slack_payload = {
            "attachments": [
                {
                    "color": "#388E3C",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "✅ Automated Self-Service Resolution Completed"}
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Ticket ID:*\n{ticket_id}"},
                                {"type": "mrkdwn", "text": f"*Runbook Executed:*\n`{runbook_name}`"},
                            ]
                        },
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": f"*Resolution Notes:*\n{notes}"}
                        }
                    ]
                }
            ]
        }
        return self._dispatch(slack_payload, event="auto_resolution", ticket_id=ticket_id)

    def notify_sla_breach_warning(self, ticket_id: str, minutes_remaining: int, group: str) -> bool:
        """Send warning when a ticket is within 15-30m of breaching SLA."""
        slack_payload = {
            "attachments": [
                {
                    "color": "#FFA000",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "⚠️ SLA Breach Imminent"}
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"Ticket *{ticket_id}* assigned to *{group}* will breach SLA in *{minutes_remaining} minutes* unless acknowledged or resolved."
                            }
                        }
                    ]
                }
            ]
        }
        return self._dispatch(slack_payload, event="sla_warning", ticket_id=ticket_id)

    def _dispatch(self, payload: Dict[str, Any], event: str, ticket_id: Optional[str]) -> bool:
        record = {
            "event": event,
            "ticket_id": ticket_id,
            "payload": payload,
        }
        self.sent_notifications.append(record)

        if self.slack_url:
            try:
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(self.slack_url, json=payload)
                    return resp.status_code == 200
            except Exception as e:
                logger.error(f"Failed to post to Slack: {e}")
                return False

        logger.info(f"[Notification Emulated] Event: {event} for ticket: {ticket_id}")
        return True
