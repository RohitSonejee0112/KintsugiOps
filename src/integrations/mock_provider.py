"""Mock ITSM Provider implementation adapting ServiceNow-style REST and models to UnifiedTicket."""
from typing import Dict, Any, List, Optional
from .base import TicketingProvider, UnifiedTicket
from .resilient_client import ResilientHttpClient
from ..mock_itsm.models import Ticket, calculate_itil_priority, utcnow
from ..mock_itsm.database import SessionLocal


class MockITSMProvider(TicketingProvider):
    """Adapter for Mock ITSM platform (ServiceNow-style schema)."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        self.client = ResilientHttpClient(max_retries=3)

    def _model_to_unified(self, t: Ticket) -> UnifiedTicket:
        return UnifiedTicket(
            id=t.id,
            provider="mock_itsm",
            title=t.title,
            description=t.description,
            category=t.category,
            priority=t.priority,
            state=t.state,
            assignment_group=t.assignment_group,
            assigned_to=t.assigned_to,
            caller_email=t.caller_email,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
            resolved_at=t.resolved_at.isoformat() if t.resolved_at else None,
            resolution_notes=t.resolution_notes,
            auto_resolved=t.auto_resolved,
            raw_data={
                "impact": t.impact,
                "urgency": t.urgency,
                "ticket_type": t.ticket_type,
                "tags": t.get_tags(),
            },
        )

    def create_ticket(self, data: Dict[str, Any], idempotency_key: Optional[str] = None) -> UnifiedTicket:
        """Create ticket either via HTTP or direct DB session."""
        if self.base_url:
            resp = self.client.execute_with_retry(
                "POST",
                f"{self.base_url}/api/v1/tickets",
                json_data=data,
                idempotency_key=idempotency_key,
            )
            raw = resp.json()
            return UnifiedTicket(
                id=raw["id"],
                provider="mock_itsm",
                title=raw["title"],
                description=raw["description"],
                category=raw["category"],
                priority=raw["priority"],
                state=raw["state"],
                assignment_group=raw.get("assignment_group"),
                assigned_to=raw.get("assigned_to"),
                caller_email=raw["caller_email"],
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                raw_data=raw,
            )

        # In-process direct DB fallback
        with SessionLocal() as db:
            impact = data.get("impact", 2)
            urgency = data.get("urgency", 2)
            priority = calculate_itil_priority(impact, urgency)
            t_id = data.get("id") or f"INC{int(utcnow().timestamp() * 1000) % 1000000:06d}"

            ticket = Ticket(
                id=t_id,
                ticket_type=data.get("ticket_type", "incident"),
                title=data["title"],
                description=data["description"],
                category=data["category"],
                subcategory=data.get("subcategory"),
                impact=impact,
                urgency=urgency,
                priority=priority,
                state="new",
                assignment_group=data.get("assignment_group"),
                assigned_to=data.get("assigned_to"),
                caller_email=data["caller_email"],
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            if data.get("tags"):
                ticket.set_tags(data["tags"])
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            return self._model_to_unified(ticket)

    def get_ticket(self, ticket_id: str) -> UnifiedTicket:
        if self.base_url:
            resp = self.client.execute_with_retry("GET", f"{self.base_url}/api/v1/tickets/{ticket_id}")
            raw = resp.json()
            return UnifiedTicket(
                id=raw["id"],
                provider="mock_itsm",
                title=raw["title"],
                description=raw["description"],
                category=raw["category"],
                priority=raw["priority"],
                state=raw["state"],
                assignment_group=raw.get("assignment_group"),
                assigned_to=raw.get("assigned_to"),
                caller_email=raw["caller_email"],
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                resolved_at=raw.get("resolved_at"),
                resolution_notes=raw.get("resolution_notes"),
                auto_resolved=raw.get("auto_resolved", False),
                raw_data=raw,
            )

        with SessionLocal() as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                raise KeyError(f"Ticket {ticket_id} not found")
            return self._model_to_unified(ticket)

    def update_ticket(self, ticket_id: str, updates: Dict[str, Any], actor: str = "automation-engine") -> UnifiedTicket:
        if self.base_url:
            payload = dict(updates)
            payload["actor"] = actor
            resp = self.client.execute_with_retry("PATCH", f"{self.base_url}/api/v1/tickets/{ticket_id}", json_data=payload)
            raw = resp.json()
            return UnifiedTicket(
                id=raw["id"],
                provider="mock_itsm",
                title=raw["title"],
                description=raw["description"],
                category=raw["category"],
                priority=raw["priority"],
                state=raw["state"],
                assignment_group=raw.get("assignment_group"),
                assigned_to=raw.get("assigned_to"),
                caller_email=raw["caller_email"],
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                resolved_at=raw.get("resolved_at"),
                resolution_notes=raw.get("resolution_notes"),
                auto_resolved=raw.get("auto_resolved", False),
                raw_data=raw,
            )

        with SessionLocal() as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                raise KeyError(f"Ticket {ticket_id} not found")
            for k, v in updates.items():
                if hasattr(ticket, k) and v is not None:
                    setattr(ticket, k, v)
            ticket.updated_at = utcnow()
            db.commit()
            db.refresh(ticket)
            return self._model_to_unified(ticket)

    def resolve_ticket(self, ticket_id: str, resolution_notes: str, actor: str = "automation-engine") -> UnifiedTicket:
        return self.update_ticket(
            ticket_id,
            {"state": "resolved", "resolution_notes": resolution_notes, "auto_resolved": True},
            actor=actor
        )

    def list_tickets(self, filters: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[UnifiedTicket]:
        with SessionLocal() as db:
            query = db.query(Ticket)
            if filters:
                if "state" in filters:
                    query = query.filter(Ticket.state == filters["state"])
                if "category" in filters:
                    query = query.filter(Ticket.category == filters["category"])
            tickets = query.limit(limit).all()
            return [self._model_to_unified(t) for t in tickets]
