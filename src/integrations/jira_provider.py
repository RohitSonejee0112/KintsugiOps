"""Jira Service Management provider adapter demonstrating multi-platform interoperability."""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from .base import TicketingProvider, UnifiedTicket
from .resilient_client import ResilientHttpClient

logger = logging.getLogger("integrations.jira")

# Mapping between Jira priority names and normalized ITIL numeric priority
JIRA_PRIORITY_TO_NUMERIC = {
    "Highest": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4,
    "Lowest": 4,
}
NUMERIC_TO_JIRA_PRIORITY = {
    1: "Highest",
    2: "High",
    3: "Medium",
    4: "Low",
}


class JiraProvider(TicketingProvider):
    """Adapter for Jira Service Management (JSM) REST API with local mock mode."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        project_key: str = "ITSM",
    ):
        self.base_url = base_url
        self.email = email
        self.api_token = api_token
        self.project_key = project_key
        self.client = ResilientHttpClient(max_retries=3)
        # In-memory mock store for offline/demo operation without live Jira account
        self._mock_issues: Dict[str, Dict[str, Any]] = {}
        self._issue_seq = 100

    def _normalize_jira_issue(self, issue: Dict[str, Any]) -> UnifiedTicket:
        fields = issue.get("fields", {})
        priority_name = fields.get("priority", {}).get("name", "Medium")
        norm_priority = JIRA_PRIORITY_TO_NUMERIC.get(priority_name, 3)

        status_name = fields.get("status", {}).get("name", "Open").lower()
        if "done" in status_name or "resolved" in status_name or "closed" in status_name:
            norm_state = "resolved"
        elif "in progress" in status_name:
            norm_state = "in_progress"
        else:
            norm_state = "new"

        return UnifiedTicket(
            id=issue.get("key", "JSM-0"),
            provider="jira",
            title=fields.get("summary", ""),
            description=str(fields.get("description", "")),
            category=fields.get("components", [{}])[0].get("name", "General") if fields.get("components") else "General",
            priority=norm_priority,
            state=norm_state,
            assignment_group=fields.get("customfield_team", "ServiceDesk-L1"),
            assigned_to=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
            caller_email=fields.get("reporter", {}).get("emailAddress", "unknown@company.com"),
            created_at=fields.get("created", datetime.now(timezone.utc).isoformat()),
            updated_at=fields.get("updated", datetime.now(timezone.utc).isoformat()),
            resolved_at=fields.get("resolutiondate"),
            resolution_notes=fields.get("resolution", {}).get("name") if fields.get("resolution") else None,
            auto_resolved=issue.get("auto_resolved", fields.get("auto_resolved", False)),
            raw_data=issue,
        )

    def create_ticket(self, data: Dict[str, Any], idempotency_key: Optional[str] = None) -> UnifiedTicket:
        """Create Jira Service Request / Incident."""
        if self.base_url and self.api_token and self.email:
            jira_payload = {
                "fields": {
                    "project": {"key": self.project_key},
                    "summary": data["title"],
                    "description": data["description"],
                    "issuetype": {"name": "Service Request"},
                    "priority": {"name": NUMERIC_TO_JIRA_PRIORITY.get(data.get("priority", 3), "Medium")},
                    "components": [{"name": data.get("category", "General")}],
                }
            }
            auth_header = httpx.BasicAuth(self.email, self.api_token)
            resp = self.client.execute_with_retry(
                "POST",
                f"{self.base_url}/rest/api/3/issue",
                json_data=jira_payload,
                idempotency_key=idempotency_key,
            )
            raw = resp.json()
            return self.get_ticket(raw["key"])

        # Offline Mock JSM Mode
        self._issue_seq += 1
        key = f"{self.project_key}-{self._issue_seq}"
        now_str = datetime.now(timezone.utc).isoformat()
        jira_issue = {
            "key": key,
            "fields": {
                "summary": data["title"],
                "description": data["description"],
                "components": [{"name": data.get("category", "General")}],
                "priority": {"name": NUMERIC_TO_JIRA_PRIORITY.get(data.get("priority", 3), "Medium")},
                "status": {"name": "Open"},
                "customfield_team": data.get("assignment_group", "ServiceDesk-L1"),
                "reporter": {"emailAddress": data.get("caller_email", "user@company.com")},
                "created": now_str,
                "updated": now_str,
            },
            "auto_resolved": False,
        }
        self._mock_issues[key] = jira_issue
        return self._normalize_jira_issue(jira_issue)

    def get_ticket(self, ticket_id: str) -> UnifiedTicket:
        if self.base_url and self.api_token and self.email:
            resp = self.client.execute_with_retry("GET", f"{self.base_url}/rest/api/3/issue/{ticket_id}")
            return self._normalize_jira_issue(resp.json())

        issue = self._mock_issues.get(ticket_id)
        if not issue:
            raise KeyError(f"Jira issue {ticket_id} not found")
        return self._normalize_jira_issue(issue)

    def update_ticket(self, ticket_id: str, updates: Dict[str, Any], actor: str = "automation-engine") -> UnifiedTicket:
        if self.base_url and self.api_token:
            # Jira transition or fields update
            pass

        issue = self._mock_issues.get(ticket_id)
        if not issue:
            raise KeyError(f"Jira issue {ticket_id} not found")

        fields = issue["fields"]
        if "state" in updates:
            state_val = updates["state"]
            fields["status"] = {"name": "Resolved" if state_val == "resolved" else ("In Progress" if state_val == "in_progress" else "Open")}
        if "assignment_group" in updates:
            fields["customfield_team"] = updates["assignment_group"]
        if "resolution_notes" in updates:
            fields["resolution"] = {"name": updates["resolution_notes"]}
        if "auto_resolved" in updates:
            issue["auto_resolved"] = updates["auto_resolved"]

        fields["updated"] = datetime.now(timezone.utc).isoformat()
        return self._normalize_jira_issue(issue)

    def resolve_ticket(self, ticket_id: str, resolution_notes: str, actor: str = "automation-engine") -> UnifiedTicket:
        return self.update_ticket(
            ticket_id,
            {"state": "resolved", "resolution_notes": resolution_notes, "auto_resolved": True},
            actor=actor
        )

    def list_tickets(self, filters: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[UnifiedTicket]:
        return [self._normalize_jira_issue(issue) for issue in list(self._mock_issues.values())[:limit]]
