"""Portal Service: RBAC persona management, ticket delegation, and audit logging."""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
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
    "engineer_erp": {
        "name": "David Miller",
        "email": "david.miller@corp.com",
        "role": "ERP Systems Lead / Manager",
        "department": "Enterprise-ERP-Support",
        "avatar": "👔",
        "description": "Oversees enterprise SAP & ERP operations, reviews financial exceptions, and resolves escalated issues.",
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
    "engineer_net": {
        "name": "Carol Danvers",
        "email": "specialist-carol@corp.com",
        "role": "Network Operations Lead",
        "department": "Network-Infrastructure-Ops",
        "avatar": "🌐",
        "description": "Oversees network topology, routing switches, VPN tunnels, and connectivity escalations.",
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

# 20 Enterprise Support Engineers across 4 Operational Domains (5 members per domain)
# Seniority Eligibility:
# - Lead (1 per team): Eligible for P1, P2, P3, P4 (The ONLY role eligible for P1)
# - Senior (2 per team): Eligible for P2, P3, P4
# - Junior (2 per team): Eligible for P3, P4 only
SUPPORT_ENGINEERS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # TYPE 1: ERP / SAP (Enterprise-ERP-Support)
    # -------------------------------------------------------------------------
    {
        "name": "David Miller",
        "email": "david.miller@corp.com",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "lead",
        "title": "ERP Systems Lead / Manager",
        "is_preferred": True,
    },
    {
        "name": "Kavita Patel",
        "email": "kavita.patel@corp.com",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "senior",
        "title": "Senior SAP Financials Specialist",
        "is_preferred": False,
    },
    {
        "name": "Marcus Vance",
        "email": "marcus.vance@corp.com",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "senior",
        "title": "Senior ABAP Integration Engineer",
        "is_preferred": False,
    },
    {
        "name": "Siddharth Rao",
        "email": "siddharth.rao@corp.com",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "junior",
        "title": "Junior ERP Support Analyst",
        "is_preferred": False,
    },
    {
        "name": "Chloe Bennett",
        "email": "chloe.bennett@corp.com",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "junior",
        "title": "Junior SAP Associate",
        "is_preferred": False,
    },

    # -------------------------------------------------------------------------
    # TYPE 2: Hardware (Desktop-Support-L2)
    # -------------------------------------------------------------------------
    {
        "name": "Alice Cooper",
        "email": "tech-alice@corp.com",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "lead",
        "title": "Desktop Support Operations Lead",
        "is_preferred": True,
    },
    {
        "name": "James Wilson",
        "email": "james.wilson@corp.com",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "senior",
        "title": "Senior Hardware Field Specialist",
        "is_preferred": False,
    },
    {
        "name": "Rachel Green",
        "email": "rachel.green@corp.com",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "senior",
        "title": "Senior Systems Fleet Engineer",
        "is_preferred": False,
    },
    {
        "name": "Lucas Scott",
        "email": "lucas.scott@corp.com",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "junior",
        "title": "Junior Hardware Support Technician",
        "is_preferred": False,
    },
    {
        "name": "Maya Lin",
        "email": "maya.lin@corp.com",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "junior",
        "title": "Junior Desktop Field Associate",
        "is_preferred": False,
    },

    # -------------------------------------------------------------------------
    # TYPE 3: Network (Network-Infrastructure-Ops)
    # -------------------------------------------------------------------------
    {
        "name": "Carol Danvers",
        "email": "specialist-carol@corp.com",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "lead",
        "title": "Network Infrastructure Operations Lead",
        "is_preferred": True,
    },
    {
        "name": "Vikram Malhotra",
        "email": "vikram.malhotra@corp.com",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "senior",
        "title": "Senior Network Security Engineer",
        "is_preferred": False,
    },
    {
        "name": "Samantha Cole",
        "email": "samantha.cole@corp.com",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "senior",
        "title": "Senior Routing & Firewall Specialist",
        "is_preferred": False,
    },
    {
        "name": "Ethan Hunt",
        "email": "ethan.hunt@corp.com",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "junior",
        "title": "Junior Network NOC Technician",
        "is_preferred": False,
    },
    {
        "name": "Priya Sharma",
        "email": "priya.sharma@corp.com",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "junior",
        "title": "Junior Infrastructure Operations Analyst",
        "is_preferred": False,
    },

    # -------------------------------------------------------------------------
    # TYPE 4: Access / Identity (IAM-Identity-Operations)
    # -------------------------------------------------------------------------
    {
        "name": "Bob Martinez",
        "email": "tech-bob@corp.com",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "lead",
        "title": "Identity Governance & IAM Lead",
        "is_preferred": True,
    },
    {
        "name": "Fatima Zahra",
        "email": "fatima.zahra@corp.com",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "senior",
        "title": "Senior Directory & Okta Specialist",
        "is_preferred": False,
    },
    {
        "name": "Liam O'Connor",
        "email": "liam.oconnor@corp.com",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "senior",
        "title": "Senior Privileged Access Security Engineer",
        "is_preferred": False,
    },
    {
        "name": "Noah Clark",
        "email": "noah.clark@corp.com",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "junior",
        "title": "Junior Access Provisioning Administrator",
        "is_preferred": False,
    },
    {
        "name": "Zara Ahmed",
        "email": "zara.ahmed@corp.com",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "junior",
        "title": "Junior Identity Support Associate",
        "is_preferred": False,
    },
]


class PortalService:
    """Handles ticket delegation, state transitions, and activity audit trails."""

    @staticmethod
    def normalize_category(category: Optional[str]) -> str:
        """Map incoming category name to standardized category key."""
        cat_lower = (category or "").lower()
        if "erp" in cat_lower or "sap" in cat_lower:
            return "ERP / SAP"
        if "hard" in cat_lower or "desktop" in cat_lower or "laptop" in cat_lower or "chassis" in cat_lower:
            return "Hardware"
        if "net" in cat_lower or "vpn" in cat_lower or "wifi" in cat_lower or "dns" in cat_lower:
            return "Network"
        if "access" in cat_lower or "identity" in cat_lower or "iam" in cat_lower or "auth" in cat_lower:
            return "Access / Identity"
        return "ERP / SAP"

    @staticmethod
    def get_eligible_engineers(
        category: str,
        priority: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Return eligible engineers for a ticket based on category and ITIL priority.
        
        Rules:
        - Scoped strictly to the ticket's category (Type 1: ERP, Type 2: Hardware,
          Type 3: Network, Type 4: Access/Identity).
        - P1 (Critical): Lead / Manager only (1 person shown).
        - P2 (High): Lead + Senior engineers (3 persons shown).
        - P3/P4 (Normal/Low): Lead + Senior + Junior engineers (all 5 persons shown).
        - Preferred engineer (e.g. David Miller for ERP) is pre-selected by default.
        
        Returns:
            Tuple of (eligible_engineers_list, default_selection_index)
        """
        norm_cat = PortalService.normalize_category(category)

        # Parse priority safely
        try:
            p_val = int(str(priority).replace("P", "").strip())
        except (ValueError, TypeError):
            p_val = 3

        # Determine eligible seniority levels
        if p_val == 1:
            allowed_seniorities = {"lead"}
        elif p_val == 2:
            allowed_seniorities = {"lead", "senior"}
        else:
            # P3, P4, P5
            allowed_seniorities = {"lead", "senior", "junior"}

        # Filter strictly by category and seniority
        team_members = [
            e for e in SUPPORT_ENGINEERS
            if e["category"] == norm_cat
        ]

        eligible = [
            e for e in team_members
            if e["seniority"] in allowed_seniorities
        ]

        # Defensive fallback: if empty for any reason, return team members
        if not eligible:
            eligible = team_members if team_members else SUPPORT_ENGINEERS[:1]

        # Find default index (preferred engineer)
        default_idx = 0
        for idx, eng in enumerate(eligible):
            if eng.get("is_preferred", False):
                default_idx = idx
                break

        return eligible, default_idx

    @staticmethod
    def get_engineer_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Look up engineer by email (supports aliases like specialist-david)."""
        # Alias mapping for backwards compatibility
        alias_map = {
            "specialist-david@corp.com": "david.miller@corp.com",
        }
        target_email = alias_map.get(email, email)
        for e in SUPPORT_ENGINEERS:
            if e["email"] == target_email:
                return e
        return None

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
