"""Portal Service: RBAC persona management, ticket delegation, and audit logging."""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import Ticket, EventLog, utcnow
from .database import SessionLocal

# -----------------------------------------------------------------------------
# Comprehensive 23-Member Enterprise RBAC Roster across 5 Operational Domains
# -----------------------------------------------------------------------------
ALL_PERSONAS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # 1. Admin & Operations Governance (3 members)
    # -------------------------------------------------------------------------
    "sarah_connor": {
        "key": "sarah_connor",
        "name": "Sarah Connor",
        "email": "dispatcher@corp.com",
        "role": "Dispatcher / Triage Lead",
        "department": "Admin & Operations Governance",
        "group": "Service Desk Operations",
        "seniority": "dispatcher",
        "itil_tag": "[DISPATCHER]",
        "avatar": "🧭",
        "description": "Global triage authority. Can triage, categorize, and delegate incoming tickets across all enterprise domains.",
    },
    "elena_vance": {
        "key": "elena_vance",
        "name": "Elena Vance",
        "email": "elena.auditor@corp.com",
        "role": "Service Delivery Lead (Auditor)",
        "department": "Admin & Operations Governance",
        "group": "ITIL Service Management Office",
        "seniority": "auditor",
        "itil_tag": "[AUDITOR]",
        "avatar": "📊",
        "description": "Service Delivery Auditor. Monitors SLA conformance, process mining bottlenecks, and SharePoint improvement initiatives.",
    },
    "allison_hill": {
        "key": "allison_hill",
        "name": "Allison Hill",
        "email": "allison.hill@corp.com",
        "role": "End-User (Employee)",
        "department": "Admin & Operations Governance",
        "group": "Finance & Operations",
        "seniority": "end_user",
        "itil_tag": "[END-USER]",
        "avatar": "👤",
        "description": "Submits IT support requests and tracks personal resolution progress in real time.",
    },

    # -------------------------------------------------------------------------
    # 2. Enterprise ERP & SAP (5 members)
    # -------------------------------------------------------------------------
    "david_miller": {
        "key": "david_miller",
        "name": "David Miller",
        "email": "david.miller@corp.com",
        "role": "ERP Systems Lead / Manager",
        "department": "Enterprise ERP & SAP",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "lead",
        "itil_tag": "[LEAD]",
        "avatar": "👔",
        "description": "Major Incident Manager for Enterprise ERP & SAP. Oversees enterprise SAP & ERP operations, reviews financial exceptions, and resolves escalated issues.",
    },
    "kavita_patel": {
        "key": "kavita_patel",
        "name": "Kavita Patel",
        "email": "kavita.patel@corp.com",
        "role": "Senior SAP Financials Specialist",
        "department": "Enterprise ERP & SAP",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "💼",
        "description": "L3 Development & RCA Specialist for SAP Finance & General Ledger operations.",
    },
    "marcus_vance": {
        "key": "marcus_vance",
        "name": "Marcus Vance",
        "email": "marcus.vance@corp.com",
        "role": "Senior ABAP Integration Engineer",
        "department": "Enterprise ERP & SAP",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "⚙️",
        "description": "L3 ABAP developer diagnosing integration bottlenecks and RFC connection exceptions.",
    },
    "siddharth_rao": {
        "key": "siddharth_rao",
        "name": "Siddharth Rao",
        "email": "siddharth.rao@corp.com",
        "role": "Junior ERP Support Analyst",
        "department": "Enterprise ERP & SAP",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "👨‍💻",
        "description": "L2 Primary Support handling P3/P4 user SAP GUI locks, transport validation, and basic accounting errors.",
    },
    "chloe_bennett": {
        "key": "chloe_bennett",
        "name": "Chloe Bennett",
        "email": "chloe.bennett@corp.com",
        "role": "Junior SAP Associate",
        "department": "Enterprise ERP & SAP",
        "group": "Enterprise-ERP-Support",
        "category": "ERP / SAP",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "👩‍💻",
        "description": "L2 Primary Support assisting with SAP table lookups, password unlocks, and standard routine tickets.",
    },

    # -------------------------------------------------------------------------
    # 3. Hardware & Desktop Support (5 members)
    # -------------------------------------------------------------------------
    "alice_cooper": {
        "key": "alice_cooper",
        "name": "Alice Cooper",
        "email": "tech-alice@corp.com",
        "role": "Desktop Support Operations Lead",
        "department": "Hardware & Desktop Support",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "lead",
        "itil_tag": "[LEAD]",
        "avatar": "👩‍💻",
        "description": "Major Incident Manager for Desktop & End-User Compute. Coordinates hardware outage triage and device deployments.",
    },
    "james_wilson": {
        "key": "james_wilson",
        "name": "James Wilson",
        "email": "james.wilson@corp.com",
        "role": "Senior Hardware Field Specialist",
        "department": "Hardware & Desktop Support",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "🖥️",
        "description": "L3 Field Specialist diagnosing workstation hardware failures, motherboard diagnostics, and field escalations.",
    },
    "rachel_green": {
        "key": "rachel_green",
        "name": "Rachel Green",
        "email": "rachel.green@corp.com",
        "role": "Senior Systems Fleet Engineer",
        "department": "Hardware & Desktop Support",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "💻",
        "description": "L3 Systems Engineer overseeing corporate laptop provisioning, MDM profiles, and hardware fleet RCA.",
    },
    "lucas_scott": {
        "key": "lucas_scott",
        "name": "Lucas Scott",
        "email": "lucas.scott@corp.com",
        "role": "Junior Hardware Support Technician",
        "department": "Hardware & Desktop Support",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "🔧",
        "description": "L2 Support Technician handling monitor replacements, docking station firmware, and peripherals.",
    },
    "maya_lin": {
        "key": "maya_lin",
        "name": "Maya Lin",
        "email": "maya.lin@corp.com",
        "role": "Junior Desktop Field Associate",
        "department": "Hardware & Desktop Support",
        "group": "Desktop-Support-L2",
        "category": "Hardware",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "🛠️",
        "description": "L2 Field Associate diagnosing local printer spoolers, keyboard replacements, and office workstation setup.",
    },

    # -------------------------------------------------------------------------
    # 4. Network Infrastructure (5 members)
    # -------------------------------------------------------------------------
    "carol_danvers": {
        "key": "carol_danvers",
        "name": "Carol Danvers",
        "email": "specialist-carol@corp.com",
        "role": "Network Operations Lead",
        "department": "Network Infrastructure",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "lead",
        "itil_tag": "[LEAD]",
        "avatar": "🌐",
        "description": "Major Incident Manager for Core Network & Edge Infrastructure. Oversees routing switches, SD-WAN, and site outages.",
    },
    "vikram_malhotra": {
        "key": "vikram_malhotra",
        "name": "Vikram Malhotra",
        "email": "vikram.malhotra@corp.com",
        "role": "Senior Network Security Engineer",
        "department": "Network Infrastructure",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "🛡️",
        "description": "L3 Network Security Engineer managing firewall rule drops, IPS/IDS signatures, and DMZ configurations.",
    },
    "samantha_cole": {
        "key": "samantha_cole",
        "name": "Samantha Cole",
        "email": "samantha.cole@corp.com",
        "role": "Senior Routing & Firewall Specialist",
        "department": "Network Infrastructure",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "📡",
        "description": "L3 Specialist diagnosing BGP/OSPF route flaps, redundant circuits, and IPsec site-to-site tunnels.",
    },
    "ethan_hunt": {
        "key": "ethan_hunt",
        "name": "Ethan Hunt",
        "email": "ethan.hunt@corp.com",
        "role": "Junior Network NOC Technician",
        "department": "Network Infrastructure",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "🔍",
        "description": "L2 NOC Technician monitoring ping latencies, switch port flaps, and routine Wi-Fi access point resets.",
    },
    "priya_sharma": {
        "key": "priya_sharma",
        "name": "Priya Sharma",
        "email": "priya.sharma@corp.com",
        "role": "Junior Infrastructure Operations Analyst",
        "department": "Network Infrastructure",
        "group": "Network-Infrastructure-Ops",
        "category": "Network",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "📶",
        "description": "L2 Analyst assisting with IP reservations, DNS record verification, and bandwidth utilization tickets.",
    },

    # -------------------------------------------------------------------------
    # 5. Access & Identity / Security (5 members)
    # -------------------------------------------------------------------------
    "bob_martinez": {
        "key": "bob_martinez",
        "name": "Bob Martinez",
        "email": "tech-bob@corp.com",
        "role": "Identity Governance & IAM Lead",
        "department": "Access & Identity / Security",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "lead",
        "itil_tag": "[LEAD]",
        "avatar": "🔐",
        "description": "Major Incident Manager for Identity & Access. Oversees SSO federation, PAM, and directory security incidents.",
    },
    "fatima_zahra": {
        "key": "fatima_zahra",
        "name": "Fatima Zahra",
        "email": "fatima.zahra@corp.com",
        "role": "Senior Directory & Okta Specialist",
        "department": "Access & Identity / Security",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "🔑",
        "description": "L3 Senior Specialist resolving SAML/OIDC federations, conditional access policies, and Azure AD sync.",
    },
    "liam_oconnor": {
        "key": "liam_oconnor",
        "name": "Liam O'Connor",
        "email": "liam.oconnor@corp.com",
        "role": "Senior Privileged Access Security Engineer",
        "department": "Access & Identity / Security",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "senior",
        "itil_tag": "[SENIOR]",
        "avatar": "🛡️",
        "description": "L3 PAM Engineer managing CyberArk vaults, privileged credentials, and administrative role escalations.",
    },
    "noah_clark": {
        "key": "noah_clark",
        "name": "Noah Clark",
        "email": "noah.clark@corp.com",
        "role": "Junior Access Provisioning Administrator",
        "department": "Access & Identity / Security",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "📋",
        "description": "L2 Administrator handling security group memberships, distribution list updates, and folder permissions.",
    },
    "zara_ahmed": {
        "key": "zara_ahmed",
        "name": "Zara Ahmed",
        "email": "zara.ahmed@corp.com",
        "role": "Junior Identity Support Associate",
        "department": "Access & Identity / Security",
        "group": "IAM-Identity-Operations",
        "category": "Access / Identity",
        "seniority": "junior",
        "itil_tag": "[JUNIOR]",
        "avatar": "🚪",
        "description": "L2 Associate handling MFA token resets, badge sync issues, and standard Active Directory account unlocks.",
    },
}

# 5 Operational Departments for Cascading Selection
DEPARTMENT_TEAMS: List[Dict[str, Any]] = [
    {
        "name": "Admin & Operations Governance",
        "display": "Admin & Operations Governance",
        "group": None,
        "members": ["sarah_connor", "elena_vance", "allison_hill"],
    },
    {
        "name": "Enterprise ERP & SAP",
        "display": "Enterprise ERP & SAP (Enterprise-ERP-Support)",
        "group": "Enterprise-ERP-Support",
        "members": ["david_miller", "kavita_patel", "marcus_vance", "siddharth_rao", "chloe_bennett"],
    },
    {
        "name": "Hardware & Desktop Support",
        "display": "Hardware & Desktop Support (Desktop-Support-L2)",
        "group": "Desktop-Support-L2",
        "members": ["alice_cooper", "james_wilson", "rachel_green", "lucas_scott", "maya_lin"],
    },
    {
        "name": "Network Infrastructure",
        "display": "Network Infrastructure (Network-Infrastructure-Ops)",
        "group": "Network-Infrastructure-Ops",
        "members": ["carol_danvers", "vikram_malhotra", "samantha_cole", "ethan_hunt", "priya_sharma"],
    },
    {
        "name": "Access & Identity / Security",
        "display": "Access & Identity / Security (IAM-Identity-Operations)",
        "group": "IAM-Identity-Operations",
        "members": ["bob_martinez", "fatima_zahra", "liam_oconnor", "noah_clark", "zara_ahmed"],
    },
]

# Legacy key alias mapping for backwards compatibility
PERSONA_ALIAS_MAP: Dict[str, str] = {
    "dispatcher": "sarah_connor",
    "engineer_erp": "david_miller",
    "engineer_l2": "alice_cooper",
    "engineer_iam": "bob_martinez",
    "engineer_net": "carol_danvers",
    "end_user": "allison_hill",
    "executive_auditor": "elena_vance",
}

# DEMO_PERSONAS dictionary preserves legacy keys while exposing all 23 members
DEMO_PERSONAS: Dict[str, Dict[str, Any]] = {
    "dispatcher": ALL_PERSONAS["sarah_connor"],
    "engineer_erp": ALL_PERSONAS["david_miller"],
    "engineer_l2": ALL_PERSONAS["alice_cooper"],
    "engineer_iam": ALL_PERSONAS["bob_martinez"],
    "engineer_net": ALL_PERSONAS["carol_danvers"],
    "end_user": ALL_PERSONAS["allison_hill"],
    "executive_auditor": ALL_PERSONAS["elena_vance"],
    **ALL_PERSONAS,
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
    def get_persona(key: str) -> Dict[str, Any]:
        """Resolve a persona dictionary by key or legacy alias."""
        canonical_key = PERSONA_ALIAS_MAP.get(key, key)
        return ALL_PERSONAS.get(canonical_key, ALL_PERSONAS.get("sarah_connor", list(ALL_PERSONAS.values())[0]))

    @staticmethod
    def get_persona_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Look up persona by email address."""
        # Alias mapping for backwards compatibility
        alias_map = {
            "specialist-david@corp.com": "david.miller@corp.com",
        }
        target_email = alias_map.get(email, email)
        for p in ALL_PERSONAS.values():
            if p["email"] == target_email:
                return p
        return None

    @staticmethod
    def can_dispatch_tickets(persona: Dict[str, Any]) -> bool:
        """
        Check if a persona has authority to dispatch incoming tickets.
        Only Service Desk Dispatchers ('dispatcher') and Team Leads ('lead')
        possess dispatch and routing authority in ITIL Service Desk operations.
        Operational engineers (Senior/Junior), Auditors, and End-Users are restricted.
        """
        if not persona:
            return False
        seniority = str(persona.get("seniority", "")).lower()
        return seniority in ["dispatcher", "lead"]

    @staticmethod
    def get_rbac_tickets(
        db: Session,
        persona: Dict[str, Any],
        limit: int = 100
    ) -> Tuple[List[Ticket], Dict[str, Any]]:
        """
        Dynamically filter tickets according to SAP-grade RBAC policies:
        1. End-User (Allison Hill):
           Strictly views only tickets she submitted (caller_email == persona['email']).
           Hidden from enterprise-wide P1 outages.
        2. Junior Engineers (L2 Primary Support):
           Strictly view P3 (Medium) & P4 (Low) tickets assigned to their operational team
           (assignment_group == persona['group']).
        3. Senior Engineers (L3 Development/RCA):
           View all tickets (P1, P2, P3, P4) assigned to their operational team.
        4. Team Leads (Major Incident Managers):
           View all tickets of their own team PLUS all company-wide P1 Critical Outages
           (War Room cross-domain visibility).
        5. Dispatcher & Auditor (Sarah Connor, Elena Vance):
           Global visibility across all teams and priorities.
           
        Returns:
            Tuple of (filtered_tickets_list, rbac_badge_metadata_dict)
        """
        from sqlalchemy import or_

        seniority = str(persona.get("seniority", "dispatcher")).lower()
        email = persona.get("email", "")
        group = persona.get("group")
        name = persona.get("name", "User")
        itil_tag = persona.get("itil_tag", "")

        query = db.query(Ticket)

        # 1. End-User (Allison Hill)
        if seniority == "end_user" or email == "allison.hill@corp.com":
            query = query.filter(Ticket.caller_email == email)
            badge_info = {
                "tier_title": "End-User Self-Service Scope",
                "tier_code": "RBAC-TIER-0 (END-USER)",
                "badge_color": "#10B981",
                "badge_bg": "rgba(16, 185, 129, 0.15)",
                "badge_border": "rgba(16, 185, 129, 0.4)",
                "icon": "👤",
                "description": (
                    f"Access restricted strictly to requests submitted by caller {name} ({email}). "
                    "Enterprise operational queues and cross-department P1 outage records are restricted."
                ),
                "scope_tag": "Self-Submitted Only",
            }

        # 2. Junior Engineers (L2 Primary Support)
        elif seniority == "junior":
            query = query.filter(
                Ticket.assignment_group == group,
                Ticket.priority.in_([3, 4])
            )
            badge_info = {
                "tier_title": f"L2 Primary Support Queue ({group})",
                "tier_code": "RBAC-TIER-1 (L2-PRIMARY)",
                "badge_color": "#38BDF8",
                "badge_bg": "rgba(56, 189, 248, 0.15)",
                "badge_border": "rgba(56, 189, 248, 0.4)",
                "icon": "🛡️",
                "description": (
                    f"Restricted strictly to P3 (Medium) & P4 (Low) tickets assigned to operational team '{group}'. "
                    "Major incidents (P1 Critical / P2 High) require L3 Senior Engineer or MIM Lead clearance."
                ),
                "scope_tag": f"{group} [P3-P4]",
            }

        # 3. Senior Engineers (L3 Development / RCA)
        elif seniority == "senior":
            query = query.filter(Ticket.assignment_group == group)
            badge_info = {
                "tier_title": f"L3 Development & RCA Specialist Queue ({group})",
                "tier_code": "RBAC-TIER-2 (L3-RCA)",
                "badge_color": "#818CF8",
                "badge_bg": "rgba(129, 140, 248, 0.15)",
                "badge_border": "rgba(129, 140, 248, 0.4)",
                "icon": "🔬",
                "description": (
                    f"Authorized for all priority levels (P1, P2, P3, P4) assigned to operational team '{group}'. "
                    "Cross-department operational queues remain restricted."
                ),
                "scope_tag": f"{group} [P1-P4]",
            }

        # 4. Team Leads (Major Incident Managers)
        elif seniority == "lead":
            query = query.filter(
                or_(
                    Ticket.assignment_group == group,
                    Ticket.priority == 1
                )
            )
            badge_info = {
                "tier_title": f"Major Incident Manager / War Room ({group} + Enterprise P1)",
                "tier_code": "RBAC-TIER-3 (MIM-WAR-ROOM)",
                "badge_color": "#F59E0B",
                "badge_bg": "rgba(245, 158, 11, 0.15)",
                "badge_border": "rgba(245, 158, 11, 0.4)",
                "icon": "🚨",
                "description": (
                    f"Dual Operational Scope: Full team queue for '{group}' (P1–P4) PLUS "
                    "All Company-Wide P1 Critical Outages (War Room Cross-Domain Visibility)."
                ),
                "scope_tag": f"{group} + Global P1 Outages",
            }

        # 5. Dispatcher & Auditor (Sarah Connor, Elena Vance)
        else:
            badge_info = {
                "tier_title": "Global Operations & Governance Clearance (Unrestricted)",
                "tier_code": "RBAC-TIER-4 (GLOBAL-GOVERNANCE)",
                "badge_color": "#A855F7",
                "badge_bg": "rgba(168, 85, 247, 0.15)",
                "badge_border": "rgba(168, 85, 247, 0.4)",
                "icon": "🌐",
                "description": (
                    f"Global unrestricted visibility across all operational groups, departments, and priority levels. "
                    f"Active Subject: {name} {itil_tag}."
                ),
                "scope_tag": "All Enterprise Domains [P1-P4]",
            }

        tickets = query.order_by(desc(Ticket.created_at)).limit(limit).all()
        badge_info["record_count"] = len(tickets)
        return tickets, badge_info

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
