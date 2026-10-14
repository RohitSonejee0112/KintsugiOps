"""Synthetic ITSM ticket generator with realistic distributions and domain scenarios."""
import random
from datetime import timedelta
from typing import List, Dict, Any, Optional
from faker import Faker
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..mock_itsm.models import Ticket, EventLog, calculate_itil_priority, utcnow
from ..mock_itsm.database import SessionLocal

fake = Faker()

# Defined Enterprise Scenarios
SCENARIOS = {
    "Access / Identity": {
        "assignment_group": "IAM-Identity-Operations",
        "templates": [
            {
                "title": "Password reset required for account {username}",
                "description": "User {name} ({email}) has forgotten their domain password after returning from leave. Account is currently locked out after 3 failed attempts.",
                "subcategory": "Password Reset",
                "impact_urgency": [(3, 2), (3, 3), (2, 2)],
                "auto_resolvable": True,
                "runbook": "PasswordResetRunbook",
            },
            {
                "title": "MFA token desynchronized on mobile device",
                "description": "User replaced mobile device over the weekend. Microsoft Authenticator prompt fails with error 'Invalid Session'. Requesting temporary bypass code.",
                "subcategory": "MFA Reset",
                "impact_urgency": [(3, 1), (2, 2)],
                "auto_resolvable": True,
                "runbook": "PasswordResetRunbook",
            },
            {
                "title": "Request read access to SharePoint folder {project_code}",
                "description": "New joiner {name} requires read/write access to confidential finance documents in folder 'Project_{project_code}'. Manager approval attached.",
                "subcategory": "Access Request",
                "impact_urgency": [(3, 3), (2, 3)],
                "auto_resolvable": True,
                "runbook": "SoftwareAccessRunbook",
            },
            {
                "title": "VPN access profile expired for remote worker",
                "description": "GlobalProtect VPN client displays 'Authentication Failed: User certificate invalid'. Remote worker cannot reach internal intranet portals.",
                "subcategory": "VPN Access",
                "impact_urgency": [(2, 1), (2, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
        ],
    },
    "Hardware": {
        "assignment_group": "Desktop-Support-L2",
        "templates": [
            {
                "title": "Laptop battery swollen - enclosure separating",
                "description": "User reports Dell XPS 15 trackpad is bulging upward and chassis bottom plate has separated. Immediate safety hazard; battery replacement required.",
                "subcategory": "Laptop Battery",
                "impact_urgency": [(1, 1), (2, 1)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "External dual monitor flickering intermittently via USB-C dock",
                "description": "Dell DisplayLink dock loses HDMI video sync every 5 minutes when running high resolution. Cables tested, driver update required.",
                "subcategory": "Peripherals",
                "impact_urgency": [(3, 3), (3, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "Company laptop keyboard key 'E' and 'Space' not responding",
                "description": "Mechanical key switch failure on Lenovo ThinkPad keyboard. User currently using external USB keyboard as temporary workaround.",
                "subcategory": "Keyboard/Input",
                "impact_urgency": [(3, 3), (3, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
        ],
    },
    "Network": {
        "assignment_group": "Network-Infrastructure-Ops",
        "templates": [
            {
                "title": "Floor 3 West WiFi access points dropping connections",
                "description": "Multiple employees in marketing wing experiencing 802.1x authentication drops. AP controller shows 98% channel saturation on 5GHz band.",
                "subcategory": "Wireless",
                "impact_urgency": [(1, 2), (2, 1), (2, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "Internal portal DNS resolution failing for staging domain",
                "description": "Developers receiving NXDOMAIN when resolving staging.internal.corp. Local DNS cache flushed, suspect authoritative bind zone desync.",
                "subcategory": "DNS",
                "impact_urgency": [(2, 2), (2, 1)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "High latency and 15% packet loss on Frankfurt MPLS line",
                "description": "Ping times between London HQ and Frankfurt office increased from 18ms to 240ms with intermittent packet loss. Core switch interface errors detected.",
                "subcategory": "WAN/MPLS",
                "impact_urgency": [(1, 1), (1, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
        ],
    },
    "ERP / SAP": {
        "assignment_group": "Enterprise-ERP-Support",
        "templates": [
            {
                "title": "SAP GUI transaction VA01 crashing with dump 'SYSTEM_NO_MORE_PAGING'",
                "description": "Order processing team unable to enter sales orders for European region. SAP ABAP short dump in program SAPMV45A. Urgent end-of-month impact.",
                "subcategory": "SAP SD/MM",
                "impact_urgency": [(1, 1), (1, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "Authorization missing for SAP transaction code ME21N (Purchase Order)",
                "description": "Procurement officer {name} receives error 'You are not authorized to use transaction ME21N' after departmental transfer. Role Z_MM_PURCHASER needed.",
                "subcategory": "SAP Authorization",
                "impact_urgency": [(2, 2), (3, 2)],
                "auto_resolvable": True,
                "runbook": "SoftwareAccessRunbook",
            },
            {
                "title": "Overnight invoice posting batch job failed with error code 104",
                "description": "Scheduled background job Z_FIN_POST_INV failed at 02:15 AM due to locked table BSID. 4,200 supplier invoices remain unposted.",
                "subcategory": "SAP Financials",
                "impact_urgency": [(1, 2), (2, 1)],
                "auto_resolvable": False,
                "runbook": None,
            },
        ],
    },
    "Cloud & DevOps": {
        "assignment_group": "Cloud-Platform-Engineering",
        "templates": [
            {
                "title": "Production Kubernetes pod in CrashLoopBackOff on cluster {cluster}",
                "description": "Payment microservice pods exiting with code 137 (OOMKilled). Memory limit 512Mi reached during flash sale traffic surge.",
                "subcategory": "Kubernetes",
                "impact_urgency": [(1, 1), (1, 2)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "AWS S3 403 Access Denied when reading analytics export bucket",
                "description": "Data science pipeline receiving 'Access Denied' on s3://corp-analytics-export-prod/. IAM role policy seems to have been modified in recent deployment.",
                "subcategory": "AWS IAM/S3",
                "impact_urgency": [(2, 2), (2, 3)],
                "auto_resolvable": False,
                "runbook": None,
            },
            {
                "title": "GitHub Actions self-hosted runner offline in VPC subnet",
                "description": "CI builds queued for more than 45 minutes. Runner instance i-0a8b9c2d unresponsive on port 22 and SSM agent status is inactive.",
                "subcategory": "CI/CD",
                "impact_urgency": [(2, 2), (2, 1)],
                "auto_resolvable": False,
                "runbook": None,
            },
        ],
    },
}


def generate_synthetic_ticket(
    ticket_id: Optional[str] = None,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """Generate a single realistic ITSM ticket dictionary."""
    if seed is not None:
        random.seed(seed)
        Faker.seed(seed)

    category = random.choice(list(SCENARIOS.keys()))
    cat_data = SCENARIOS[category]
    template = random.choice(cat_data["templates"])

    name = fake.name()
    email = fake.company_email()
    username = email.split("@")[0]
    project_code = f"PRJ-{random.randint(100, 999)}"
    cluster = random.choice(["prod-eu-west-1", "prod-us-east-1", "core-k8s-01"])

    title = template["title"].format(
        name=name, email=email, username=username, project_code=project_code, cluster=cluster
    )
    description = template["description"].format(
        name=name, email=email, username=username, project_code=project_code, cluster=cluster
    )

    impact, urgency = random.choice(template["impact_urgency"])
    priority = calculate_itil_priority(impact, urgency)

    ticket_type = "service_request" if "Request" in title or "access" in title.lower() else "incident"

    tags = [category.lower().replace(" ", "-")]
    if template["auto_resolvable"]:
        tags.append("auto-resolvable-candidate")
    if template.get("runbook"):
        tags.append(f"runbook:{template['runbook']}")

    return {
        "id": ticket_id or f"INC{random.randint(100000, 999999)}",
        "ticket_type": ticket_type,
        "title": title,
        "description": description,
        "category": category,
        "subcategory": template["subcategory"],
        "impact": impact,
        "urgency": urgency,
        "priority": priority,
        "assignment_group": cat_data["assignment_group"],
        "caller_email": email,
        "auto_resolvable": template["auto_resolvable"],
        "runbook": template.get("runbook"),
        "tags": tags,
    }


def seed_synthetic_tickets(
    count: int = 1000,
    db: Optional[Session] = None,
    seed: int = 42
) -> List[Ticket]:
    """Generate and commit synthetic tickets directly to database.

    Returns the list of created Ticket records.
    """
    random.seed(seed)
    Faker.seed(seed)

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    created_tickets = []
    prefix = "INC"

    # Fetch all existing IDs to guarantee zero collision
    existing_ids = {t[0] for t in db.query(Ticket.id).all()}
    max_num = 100000
    for tid in existing_ids:
        if tid.startswith(prefix) and tid[len(prefix):].isdigit():
            max_num = max(max_num, int(tid[len(prefix):]))
    start_num = max_num + 1

    try:
        now = utcnow()
        for i in range(count):
            t_id = f"{prefix}{start_num:06d}"
            while t_id in existing_ids:
                start_num += 1
                t_id = f"{prefix}{start_num:06d}"
            existing_ids.add(t_id)
            start_num += 1

            raw = generate_synthetic_ticket(ticket_id=t_id)

            # Assign a realistic creation date over the last 30 days
            created_time = now - timedelta(
                days=random.uniform(1, 30),
                hours=random.uniform(0, 23),
                minutes=random.uniform(0, 59)
            )

            is_auto = raw.get("auto_resolvable", False) and random.random() < 0.70
            is_ping_pong = (not is_auto) and (random.random() < 0.22)  # ~22% bounce rate for process mining

            ticket = Ticket(
                id=t_id,
                ticket_type=raw["ticket_type"],
                title=raw["title"],
                description=raw["description"],
                category=raw["category"],
                subcategory=raw["subcategory"],
                impact=raw["impact"],
                urgency=raw["urgency"],
                priority=raw["priority"],
                state="resolved",
                assignment_group=raw["assignment_group"],
                caller_email=raw["caller_email"],
                created_at=created_time,
                updated_at=created_time,
                sla_breached=False,
                auto_resolved=is_auto,
            )
            ticket.set_tags(raw["tags"])
            db.add(ticket)

            # Event 1: Created
            ev_created = EventLog(
                ticket_id=t_id,
                activity="Created",
                timestamp=created_time,
                actor=raw["caller_email"],
                to_state="new",
                to_group=raw["assignment_group"],
                details=f"Ticket created with priority P{raw['priority']}",
            )
            db.add(ev_created)

            if is_auto:
                # Resolved by runbook in seconds
                resolved_time = created_time + timedelta(seconds=random.uniform(20, 90))
                ticket.resolved_at = resolved_time
                ticket.updated_at = resolved_time
                ticket.resolution_notes = "Resolved automatically via self-service remediation runbook."
                ev_resolved = EventLog(
                    ticket_id=t_id,
                    activity="Resolved",
                    timestamp=resolved_time,
                    actor="RunbookEngine",
                    from_state="new",
                    to_state="resolved",
                    from_group=raw["assignment_group"],
                    to_group=raw["assignment_group"],
                    details="Automated self-service resolution completed.",
                )
                db.add(ev_resolved)

            elif is_ping_pong:
                # Ticket bounces between ServiceDesk-L1 and specialist group
                t_assign = created_time + timedelta(hours=random.uniform(1.0, 3.5))
                ev_assign = EventLog(
                    ticket_id=t_id,
                    activity="Assigned",
                    timestamp=t_assign,
                    actor="dispatcher-system",
                    from_state="new",
                    to_state="assigned",
                    from_group="ServiceDesk-L1",
                    to_group="ServiceDesk-L1",
                    details="Initial intake assignment",
                )
                db.add(ev_assign)

                # Hop 1: ServiceDesk-L1 -> Specialist group
                t_bounce1 = t_assign + timedelta(hours=random.uniform(2.0, 6.0))
                ev_b1 = EventLog(
                    ticket_id=t_id,
                    activity="Reassigned",
                    timestamp=t_bounce1,
                    actor="tech-l1",
                    from_group="ServiceDesk-L1",
                    to_group=raw["assignment_group"],
                    details=f"Escalated to {raw['assignment_group']}",
                )
                db.add(ev_b1)

                # Hop 2: Specialist group -> ServiceDesk-L1
                t_bounce2 = t_bounce1 + timedelta(hours=random.uniform(3.0, 10.0))
                ev_b2 = EventLog(
                    ticket_id=t_id,
                    activity="Reassigned",
                    timestamp=t_bounce2,
                    actor="specialist-l2",
                    from_group=raw["assignment_group"],
                    to_group="ServiceDesk-L1",
                    details="Incomplete diagnostics; returned to L1",
                )
                db.add(ev_b2)

                # Hop 3: ServiceDesk-L1 -> Specialist group
                t_bounce3 = t_bounce2 + timedelta(hours=random.uniform(2.0, 6.0))
                ev_b3 = EventLog(
                    ticket_id=t_id,
                    activity="Reassigned",
                    timestamp=t_bounce3,
                    actor="tech-l1",
                    from_group="ServiceDesk-L1",
                    to_group=raw["assignment_group"],
                    details="Diagnostic logs attached; re-routed to specialist",
                )
                db.add(ev_b3)

                # Resolved
                resolved_time = t_bounce3 + timedelta(hours=random.uniform(4.0, 18.0))
                ticket.resolved_at = resolved_time
                ticket.updated_at = resolved_time
                ticket.resolution_notes = "Issue resolved following multi-team investigation."
                ev_res = EventLog(
                    ticket_id=t_id,
                    activity="Resolved",
                    timestamp=resolved_time,
                    actor="specialist-l2",
                    from_state="in_progress",
                    to_state="resolved",
                    from_group=raw["assignment_group"],
                    to_group=raw["assignment_group"],
                    details="Resolved by senior specialist",
                )
                db.add(ev_res)

            else:
                # Standard linear resolution flow
                t_assign = created_time + timedelta(hours=random.uniform(0.5, 3.0))
                ev_assign = EventLog(
                    ticket_id=t_id,
                    activity="Assigned",
                    timestamp=t_assign,
                    actor="dispatcher",
                    from_state="new",
                    to_state="assigned",
                    to_group=raw["assignment_group"],
                    details="Routed to operational group",
                )
                db.add(ev_assign)

                t_work = t_assign + timedelta(hours=random.uniform(1.0, 5.0))
                ev_work = EventLog(
                    ticket_id=t_id,
                    activity="State_Changed",
                    timestamp=t_work,
                    actor="support-engineer",
                    from_state="assigned",
                    to_state="in_progress",
                    from_group=raw["assignment_group"],
                    to_group=raw["assignment_group"],
                    details="Investigation in progress",
                )
                db.add(ev_work)

                resolved_time = t_work + timedelta(hours=random.uniform(2.0, 16.0))
                ticket.resolved_at = resolved_time
                ticket.updated_at = resolved_time
                ticket.resolution_notes = "Issue diagnosed and resolved successfully."
                ev_res = EventLog(
                    ticket_id=t_id,
                    activity="Resolved",
                    timestamp=resolved_time,
                    actor="support-engineer",
                    from_state="in_progress",
                    to_state="resolved",
                    from_group=raw["assignment_group"],
                    to_group=raw["assignment_group"],
                    details="Remediation verified",
                )
                db.add(ev_res)

            created_tickets.append(ticket)

            if (i + 1) % 100 == 0:
                db.commit()

        db.commit()
    finally:
        if close_session:
            db.close()

    return created_tickets


def seed_events_for_existing_tickets(db: Optional[Session] = None) -> int:
    """Generate realistic Process Mining EventLog records for any existing tickets lacking events."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        tickets = db.query(Ticket).all()
        if not tickets:
            return 0

        now = utcnow()
        added_events = 0

        for ticket in tickets:
            existing_count = db.query(EventLog).filter(EventLog.ticket_id == ticket.id).count()
            if existing_count > 0:
                continue

            created_time = ticket.created_at or (now - timedelta(days=random.uniform(1, 20)))
            group = ticket.assignment_group or "ServiceDesk-L1"

            # Event 1: Created
            ev1 = EventLog(
                ticket_id=ticket.id,
                activity="Created",
                timestamp=created_time,
                actor=ticket.caller_email,
                to_state="new",
                to_group=group,
                details=f"Ticket created with priority P{ticket.priority}",
            )
            db.add(ev1)
            added_events += 1

            is_ping_pong = random.random() < 0.25

            if is_ping_pong:
                t_assign = created_time + timedelta(hours=random.uniform(1.0, 3.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Assigned",
                    timestamp=t_assign,
                    actor="dispatcher",
                    to_state="assigned",
                    from_group="ServiceDesk-L1",
                    to_group="ServiceDesk-L1",
                ))
                t_b1 = t_assign + timedelta(hours=random.uniform(2.0, 5.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Reassigned",
                    timestamp=t_b1,
                    actor="tech-l1",
                    from_group="ServiceDesk-L1",
                    to_group=group,
                ))
                t_b2 = t_b1 + timedelta(hours=random.uniform(3.0, 8.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Reassigned",
                    timestamp=t_b2,
                    actor="tech-l2",
                    from_group=group,
                    to_group="ServiceDesk-L1",
                ))
                t_b3 = t_b2 + timedelta(hours=random.uniform(2.0, 6.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Reassigned",
                    timestamp=t_b3,
                    actor="tech-l1",
                    from_group="ServiceDesk-L1",
                    to_group=group,
                ))
                t_res = t_b3 + timedelta(hours=random.uniform(3.0, 10.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Resolved",
                    timestamp=t_res,
                    actor="tech-l2",
                    from_state="in_progress",
                    to_state="resolved",
                    to_group=group,
                ))
                ticket.state = "resolved"
                ticket.resolved_at = t_res
                added_events += 5
            else:
                t_assign = created_time + timedelta(hours=random.uniform(0.5, 2.5))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Assigned",
                    timestamp=t_assign,
                    actor="dispatcher",
                    to_state="assigned",
                    to_group=group,
                ))
                t_res = t_assign + timedelta(hours=random.uniform(1.0, 8.0))
                db.add(EventLog(
                    ticket_id=ticket.id,
                    activity="Resolved",
                    timestamp=t_res,
                    actor="engineer",
                    from_state="assigned",
                    to_state="resolved",
                    to_group=group,
                ))
                ticket.state = "resolved"
                ticket.resolved_at = t_res
                added_events += 2

        db.commit()
        return added_events
    finally:
        if close_db:
            db.close()
