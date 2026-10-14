"""Synthetic ITSM ticket generator with realistic distributions and domain scenarios."""
import random
from typing import List, Dict, Any, Optional
from faker import Faker
from sqlalchemy.orm import Session

from ..mock_itsm.models import Ticket, calculate_itil_priority, utcnow
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

    try:
        for i in range(1, count + 1):
            t_id = f"{prefix}{100000 + i:06d}"
            raw = generate_synthetic_ticket(ticket_id=t_id)

            ticket = Ticket(
                id=raw["id"],
                ticket_type=raw["ticket_type"],
                title=raw["title"],
                description=raw["description"],
                category=raw["category"],
                subcategory=raw["subcategory"],
                impact=raw["impact"],
                urgency=raw["urgency"],
                priority=raw["priority"],
                state="new",
                assignment_group=raw["assignment_group"],
                caller_email=raw["caller_email"],
                created_at=utcnow(),
                updated_at=utcnow(),
                sla_breached=False,
                auto_resolved=False,
            )
            ticket.set_tags(raw["tags"])
            db.add(ticket)
            created_tickets.append(ticket)

            if i % 500 == 0:
                db.commit()

        db.commit()
    finally:
        if close_session:
            db.close()

    return created_tickets
