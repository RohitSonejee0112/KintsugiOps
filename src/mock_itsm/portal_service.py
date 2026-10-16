"""Portal Service: RBAC persona management, ticket delegation, and audit logging."""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import Ticket, EventLog, utcnow
from .database import SessionLocal

# Predefined Enterprise Personas for 1-Click Role Switching
DEMO_PERSONAS: Dict[str, Dict[str, str]] = {
    "dispatcher": {
        "name": "Sarah Connor",
        "email": "dispatcher@corp.com",
        "role": "Dispatcher / Triage Lead",
        "department": "Service Desk Operations",
        "avatar": "🧭",
        "description": "Can triage, categorize, and delegate incoming tickets to operational groups and engineers.",
    },
    "engineer_l2": {
        "name": "Alice Cooper",
        "email": "tech-alice@corp.com",
        "role": "Support Engineer (L2)",
        "department": "Desktop-Support-L2",
        "avatar": "👩‍💻",
        "description": "Receives delegated tickets in personal inbox, works on remediation, and resolves cases.",
    },
    "engineer_iam": {
        "name": "Bob Martinez",
        "email": "tech-bob@corp.com",
        "role": "Identity Specialist (IAM)",
        "department": "IAM-Identity-Operations",
        "avatar": "🔐",
        "description": "Handles sensitive access requests, MFA desyncs, and security identity lifecycles.",
    },
    "end_user": {
        "name": "Allison Hill",
        "email": "allison.hill@corp.com",
        "role": "End-User (Employee)",
        "department": "Finance & Operations",
        "avatar": "👤",
        "description": "Submits IT support requests and tracks resolution progress in real time.",
    },
    "executive_auditor": {
        "name": "Elena Vance",
        "email": "elena.auditor@corp.com",
        "role": "Service Delivery Lead (Auditor)",
        "department": "ITIL Service Management Office",
        "avatar": "📊",
        "description": "Monitors SLA conformance, process mining bottlenecks, and SharePoint improvement initiatives.",
    },
}

SUPPORT_ENGINEERS = [
    {"name": "Alice Cooper", "email": "tech-alice@corp.com", "group": "Desktop-Support-L2"},
    {"name": "Bob Martinez", "email": "tech-bob@corp.com", "group": "IAM-Identity-Operations"},
    {"name": "Carol Danvers", "email": "specialist-carol@corp.com", "group": "Network-Infrastructure-Ops"},
    {"name": "David Miller", "email": "specialist-david@corp.com", "group": "Enterprise-ERP-Support"},
]


class PortalService:
    """Handles ticket delegation, state transitions, and activity audit trails."""

    @staticmethod
    def delegate_ticket(
        db: Session,
        ticket_id: str,
        assigned_to: str,
        assigned_by: str,
        target_group: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[Ticket]:
        """Assign/delegate a ticket to a specific support engineer and log event."""
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return None

        prev_assignee = ticket.assigned_to
        prev_group = ticket.assignment_group
        prev_state = ticket.state

        ticket.assigned_to = assigned_to
        setattr(ticket, "assigned_by", assigned_by)
        if target_group:
            ticket.assignment_group = target_group
        ticket.state = "assigned"
        ticket.updated_at = utcnow()

        # Log delegation event in EventLog for Process Mining & audit
        ev = EventLog(
            ticket_id=ticket.id,
            activity="Assigned",
            timestamp=utcnow(),
            actor=assigned_by,
            from_state=prev_state,
            to_state="assigned",
            from_group=prev_group,
            to_group=ticket.assignment_group,
            details=f"Ticket delegated by {assigned_by} to {assigned_to}. {notes or ''}".strip(),
        )
        db.add(ev)
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def update_ticket_state(
        db: Session,
        ticket_id: str,
        new_state: str,
        actor: str,
        resolution_notes: Optional[str] = None,
        reassign_to: Optional[str] = None,
        reassign_group: Optional[str] = None
    ) -> Optional[Ticket]:
        """Update ticket state (in_progress, resolved, reassigned) and notify assigner."""
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return None

        from_state = ticket.state
        now = utcnow()
        ticket.state = new_state
        ticket.updated_at = now

        activity = "State_Changed"

        if new_state == "resolved":
            activity = "Resolved"
            ticket.resolved_at = now
            ticket.resolution_notes = resolution_notes or "Resolved by engineer."
        elif new_state == "in_progress":
            activity = "State_Changed"
        elif reassign_to or reassign_group:
            activity = "Reassigned"
            from_grp = ticket.assignment_group
            if reassign_group:
                ticket.assignment_group = reassign_group
            if reassign_to:
                ticket.assigned_to = reassign_to

        details = f"State updated from '{from_state}' to '{new_state}' by {actor}."
        if resolution_notes:
            details += f" Resolution: {resolution_notes}"
        if reassign_to:
            details += f" Reassigned to {reassign_to} ({ticket.assignment_group})."

        ev = EventLog(
            ticket_id=ticket.id,
            activity=activity,
            timestamp=now,
            actor=actor,
            from_state=from_state,
            to_state=new_state,
            from_group=ticket.assignment_group,
            to_group=ticket.assignment_group,
            details=details,
        )
        db.add(ev)
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def get_assigned_tickets(db: Session, engineer_email: str) -> List[Ticket]:
        """Return tickets assigned to a specific engineer."""
        return db.query(Ticket).filter(Ticket.assigned_to == engineer_email).order_by(desc(Ticket.updated_at)).all()

    @staticmethod
    def get_delegated_tickets(db: Session, dispatcher_email: str) -> List[Ticket]:
        """Return tickets that were delegated by this dispatcher/user."""
        if hasattr(Ticket, "assigned_by"):
            return db.query(Ticket).filter(Ticket.assigned_by == dispatcher_email).order_by(desc(Ticket.updated_at)).all()
        return []

    @staticmethod
    def get_submitted_tickets(db: Session, caller_email: str) -> List[Ticket]:
        """Return tickets submitted by this end-user."""
        return db.query(Ticket).filter(Ticket.caller_email == caller_email).order_by(desc(Ticket.created_at)).all()

    @staticmethod
    def get_delegation_audit_feed(db: Session, user_email: str, limit: int = 12) -> List[Dict[str, Any]]:
        """Return real-time audit feed of events on tickets assigned by or to this user."""
        filter_cond = (Ticket.assigned_to == user_email) | (Ticket.caller_email == user_email)
        if hasattr(Ticket, "assigned_by"):
            filter_cond = filter_cond | (Ticket.assigned_by == user_email)

        relevant_ticket_ids = [t[0] for t in db.query(Ticket.id).filter(filter_cond).all()]

        if not relevant_ticket_ids:
            return []

        events = db.query(EventLog).filter(
            EventLog.ticket_id.in_(relevant_ticket_ids)
        ).order_by(desc(EventLog.timestamp)).limit(limit).all()

        feed = []
        for ev in events:
            feed.append({
                "ticket_id": ev.ticket_id,
                "activity": ev.activity,
                "actor": ev.actor,
                "from_state": ev.from_state,
                "to_state": ev.to_state,
                "details": ev.details,
                "timestamp": ev.timestamp.strftime("%Y-%m-%d %H:%M:%S") if ev.timestamp else "",
            })
        return feed

    @staticmethod
    def generate_ticket_dossier_json(ticket: Ticket, triage_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate structured JSON audit dossier for downloading."""
        dossier = {
            "dossier_type": "ITSM_AI_TRIAGE_AUDIT_DOSSIER",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ticket": {
                "id": ticket.id,
                "title": ticket.title,
                "description": ticket.description,
                "caller_email": ticket.caller_email,
                "category": ticket.category,
                "priority": f"P{ticket.priority}",
                "impact": ticket.impact,
                "urgency": ticket.urgency,
                "state": ticket.state,
                "assignment_group": ticket.assignment_group,
                "assigned_to": ticket.assigned_to,
                "assigned_by": getattr(ticket, "assigned_by", None),
                "auto_resolved": ticket.auto_resolved,
                "resolution_notes": ticket.resolution_notes,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            },
            "ai_and_governance_metadata": triage_metadata or {},
        }
        return json.dumps(dossier, indent=2, default=str)

    @staticmethod
    def generate_ticket_dossier_markdown(ticket: Ticket, triage_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate formatted Markdown audit dossier for downloading."""
        meta = triage_metadata or {}
        lines = [
            f"# 📋 ITSM Incident Audit Dossier: {ticket.id}",
            f"**Exported At:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`",
            "",
            "## 1. Ticket Overview",
            f"- **Title:** {ticket.title}",
            f"- **Caller Email:** `{ticket.caller_email}`",
            f"- **Category / Group:** `{ticket.category}` ➔ `{ticket.assignment_group}`",
            f"- **ITIL Priority:** `P{ticket.priority}` (Impact: {ticket.impact}, Urgency: {ticket.urgency})",
            f"- **Current State:** `{ticket.state.upper()}`",
            f"- **Assigned To:** `{ticket.assigned_to or 'Unassigned'}` (Delegated by: `{getattr(ticket, 'assigned_by', None) or 'System'}`)",

            "",
            "## 2. Description",
            "> " + ticket.description.replace("\n", "\n> "),
            "",
            "## 3. AI Triage & Conformal Prediction Evidence",
            f"- **Confidence Score:** `{meta.get('confidence_score', 'N/A')}`",
            f"- **Conformal Prediction Set $\\Gamma^{{\\alpha=0.05}}$:** `{meta.get('conformal_set', [ticket.category])}`",
            f"- **Statistically Guaranteed Safe:** `{meta.get('conformal_guaranteed', False)}`",
            f"- **PII Tokens Redacted:** `{meta.get('pii_redacted_count', 0)}`",
            f"- **Semantic Cache Hit:** `{meta.get('cache_hit', False)}`",
            f"- **Reasoning Summary:** _{meta.get('reasoning_summary', 'Automated intake classification')}_",
            "",
            "## 4. Remediation & Runbook Status",
            f"- **Auto-Resolved:** `{ticket.auto_resolved}`",
            f"- **Resolution Notes:** {ticket.resolution_notes or 'Pending resolution'}",
            f"- **Resolved At:** `{ticket.resolved_at or 'N/A'}`",
        ]
        return "\n".join(lines)
