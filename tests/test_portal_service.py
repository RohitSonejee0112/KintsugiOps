"""Unit tests for PortalService: delegation, state updates, and dossier exports."""
import pytest
from src.mock_itsm.database import SessionLocal, init_db
from src.mock_itsm.models import Ticket, EventLog
from src.mock_itsm.portal_service import PortalService, DEMO_PERSONAS


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_portal_delegate_ticket(db_session):
    """Test assigning a ticket to an engineer and checking EventLog creation."""
    # Create test ticket
    t = Ticket(
        id="INC99901",
        title="Laptop keyboard failing",
        description="Keys spacebar and enter unresponsive",
        category="Hardware",
        caller_email="employee@corp.com",
        state="new",
        priority=3,
    )
    db_session.merge(t)
    db_session.commit()

    # Delegate ticket
    updated = PortalService.delegate_ticket(
        db=db_session,
        ticket_id="INC99901",
        assigned_to="tech-alice@corp.com",
        assigned_by="dispatcher@corp.com",
        target_group="Desktop-Support-L2",
        notes="High priority user",
    )

    assert updated is not None
    assert updated.assigned_to == "tech-alice@corp.com"
    assert updated.assigned_by == "dispatcher@corp.com"
    assert updated.state == "assigned"

    # Verify event log was written
    events = db_session.query(EventLog).filter(EventLog.ticket_id == "INC99901").all()
    assert len(events) >= 1
    assert any(e.activity == "Assigned" and e.actor == "dispatcher@corp.com" for e in events)


def test_portal_update_ticket_state_and_feed(db_session):
    """Test engineer resolving ticket and dispatcher receiving activity feed update."""
    t = Ticket(
        id="INC99902",
        title="VPN access issue",
        description="Certificate invalid",
        category="Network",
        caller_email="remote@corp.com",
        assigned_to="tech-alice@corp.com",
        assigned_by="dispatcher@corp.com",
        state="assigned",
        priority=2,
    )
    db_session.merge(t)
    db_session.commit()

    # Alice resolves the ticket
    resolved = PortalService.update_ticket_state(
        db=db_session,
        ticket_id="INC99902",
        new_state="resolved",
        actor="tech-alice@corp.com",
        resolution_notes="Re-issued client certificate and flushed DNS."
    )

    assert resolved.state == "resolved"
    assert resolved.resolution_notes == "Re-issued client certificate and flushed DNS."
    assert resolved.resolved_at is not None

    # Check dispatcher feed contains the resolution update
    feed = PortalService.get_delegation_audit_feed(db=db_session, user_email="dispatcher@corp.com")
    assert len(feed) > 0
    resolved_event = next((e for e in feed if e["ticket_id"] == "INC99902"), None)
    assert resolved_event is not None
    assert resolved_event["activity"] == "Resolved"
    assert "tech-alice@corp.com" in resolved_event["actor"]


def test_portal_dossier_generation(db_session):
    """Test generating JSON and Markdown dossiers."""
    t = Ticket(
        id="INC99903",
        title="SharePoint access needed",
        description="Requesting read permissions to folder",
        category="Access / Identity",
        caller_email="user@corp.com",
        state="resolved",
        priority=3,
        auto_resolved=True,
        resolution_notes="Granted via automated runbook.",
    )
    db_session.merge(t)
    db_session.commit()

    json_doc = PortalService.generate_ticket_dossier_json(t, {"confidence_score": 0.94})
    assert "INC99903" in json_doc
    assert "0.94" in json_doc

    md_doc = PortalService.generate_ticket_dossier_markdown(t, {"confidence_score": 0.94})
    assert "# 📋 ITSM Incident Audit Dossier: INC99903" in md_doc
    assert "Granted via automated runbook." in md_doc


def test_support_engineers_roster_composition():
    """Verify that exactly 20 engineers exist across 4 categories with 1 lead, 2 seniors, and 2 juniors."""
    from src.mock_itsm.portal_service import SUPPORT_ENGINEERS

    assert len(SUPPORT_ENGINEERS) == 20

    categories = ["ERP / SAP", "Hardware", "Network", "Access / Identity"]
    for cat in categories:
        members = [e for e in SUPPORT_ENGINEERS if e["category"] == cat]
        assert len(members) == 5, f"Category {cat} must have exactly 5 members"

        leads = [e for e in members if e["seniority"] == "lead"]
        seniors = [e for e in members if e["seniority"] == "senior"]
        juniors = [e for e in members if e["seniority"] == "junior"]

        assert len(leads) == 1, f"Category {cat} must have exactly 1 lead"
        assert len(seniors) == 2, f"Category {cat} must have exactly 2 seniors"
        assert len(juniors) == 2, f"Category {cat} must have exactly 2 juniors"

        # Preferred lead verification
        preferred = [e for e in members if e.get("is_preferred")]
        assert len(preferred) == 1
        assert preferred[0]["seniority"] == "lead"


def test_erp_delegation_tiered_filtering_and_defaults():
    """Verify ERP tickets: P1 -> 1 lead (David Miller), P2 -> 3 members, P3 -> 5 members, David Miller default."""
    # Priority 1: Manager / Lead only (1 person)
    p1_engineers, p1_idx = PortalService.get_eligible_engineers("ERP / SAP", priority=1)
    assert len(p1_engineers) == 1
    assert p1_engineers[0]["name"] == "David Miller"
    assert p1_engineers[0]["seniority"] == "lead"
    assert p1_idx == 0

    # Priority 2: Lead + Seniors (3 persons: 1 Lead + 2 Seniors)
    p2_engineers, p2_idx = PortalService.get_eligible_engineers("ERP / SAP", priority=2)
    assert len(p2_engineers) == 3
    seniorities = {e["seniority"] for e in p2_engineers}
    assert seniorities == {"lead", "senior"}
    assert "junior" not in seniorities
    assert p2_engineers[p2_idx]["name"] == "David Miller"
    assert p2_engineers[p2_idx]["is_preferred"] is True

    # Priority 3: All 5 members (1 Lead + 2 Seniors + 2 Juniors)
    p3_engineers, p3_idx = PortalService.get_eligible_engineers("ERP / SAP", priority=3)
    assert len(p3_engineers) == 5
    p3_seniorities = {e["seniority"] for e in p3_engineers}
    assert p3_seniorities == {"lead", "senior", "junior"}
    assert p3_engineers[p3_idx]["name"] == "David Miller"
    assert p3_engineers[p3_idx]["is_preferred"] is True


def test_category_scoping_isolation():
    """Verify that only engineers belonging to the specific category are shown."""
    # Hardware P2: exactly 3 Hardware members, Alice Cooper preferred
    hw_engineers, hw_idx = PortalService.get_eligible_engineers("Hardware", priority=2)
    assert len(hw_engineers) == 3
    assert all(e["category"] == "Hardware" for e in hw_engineers)
    assert hw_engineers[hw_idx]["name"] == "Alice Cooper"

    # Network P1: exactly 1 member, Carol Danvers
    net_engineers, net_idx = PortalService.get_eligible_engineers("Network", priority=1)
    assert len(net_engineers) == 1
    assert net_engineers[0]["name"] == "Carol Danvers"
    assert net_engineers[0]["category"] == "Network"

    # Access / Identity P3: exactly 5 members, Bob Martinez preferred
    iam_engineers, iam_idx = PortalService.get_eligible_engineers("Access / Identity", priority=3)
    assert len(iam_engineers) == 5
    assert all(e["category"] == "Access / Identity" for e in iam_engineers)
    assert iam_engineers[iam_idx]["name"] == "Bob Martinez"


def test_23_personas_and_cascading_departments_roster():
    """Verify that exactly 23 personas exist across 5 departments with valid ITIL tags and attributes."""
    from src.mock_itsm.portal_service import ALL_PERSONAS, DEPARTMENT_TEAMS, DEMO_PERSONAS, PERSONA_ALIAS_MAP

    assert len(ALL_PERSONAS) == 23
    assert len(DEPARTMENT_TEAMS) == 5

    # Check 5 departments
    dept_names = [d["name"] for d in DEPARTMENT_TEAMS]
    assert "Admin & Operations Governance" in dept_names
    assert "Enterprise ERP & SAP" in dept_names
    assert "Hardware & Desktop Support" in dept_names
    assert "Network Infrastructure" in dept_names
    assert "Access & Identity / Security" in dept_names

    # Check Admin & Operations Governance has Sarah, Elena, Allison
    admin_dept = next(d for d in DEPARTMENT_TEAMS if d["name"] == "Admin & Operations Governance")
    assert admin_dept["members"] == ["sarah_connor", "elena_vance", "allison_hill"]
    assert ALL_PERSONAS["sarah_connor"]["itil_tag"] == "[DISPATCHER]"
    assert ALL_PERSONAS["elena_vance"]["itil_tag"] == "[AUDITOR]"
    assert ALL_PERSONAS["allison_hill"]["itil_tag"] == "[END-USER]"

    # Check each technical team has exactly 5 members (1 Lead, 2 Seniors, 2 Juniors)
    for dept in DEPARTMENT_TEAMS:
        if dept["name"] == "Admin & Operations Governance":
            continue
        members = [ALL_PERSONAS[m_key] for m_key in dept["members"]]
        assert len(members) == 5
        leads = [m for m in members if m["seniority"] == "lead"]
        seniors = [m for m in members if m["seniority"] == "senior"]
        juniors = [m for m in members if m["seniority"] == "junior"]
        assert len(leads) == 1 and leads[0]["itil_tag"] == "[LEAD]"
        assert len(seniors) == 2 and all(s["itil_tag"] == "[SENIOR]" for s in seniors)
        assert len(juniors) == 2 and all(j["itil_tag"] == "[JUNIOR]" for j in juniors)

    # Verify all 23 members have mandatory fields
    required_fields = {"name", "email", "role", "department", "seniority", "itil_tag", "avatar", "description"}
    for key, p in ALL_PERSONAS.items():
        assert required_fields.issubset(set(p.keys())), f"Persona {key} missing required attributes"

    # Verify backwards compatibility in DEMO_PERSONAS and aliases
    for legacy_key, canonical_key in PERSONA_ALIAS_MAP.items():
        assert legacy_key in DEMO_PERSONAS
        assert DEMO_PERSONAS[legacy_key]["email"] == ALL_PERSONAS[canonical_key]["email"]
        resolved = PortalService.get_persona(legacy_key)
        assert resolved["name"] == ALL_PERSONAS[canonical_key]["name"]


def test_rbac_dynamic_visibility_all_tiers(db_session):
    """
    Test SAP-grade dynamic RBAC visibility across all 5 tiers:
    1. End-User (Allison Hill): only caller tickets, hidden from P1 outages.
    2. Junior Engineer: only P3 & P4 of own team.
    3. Senior Engineer: all P1-P4 of own team, no other teams.
    4. Team Lead: all tickets of own team PLUS company-wide P1 outages.
    5. Dispatcher & Auditor: global visibility.
    """
    from src.mock_itsm.portal_service import ALL_PERSONAS

    # Clear and seed test tickets across groups and priorities
    db_session.query(Ticket).delete()
    db_session.commit()

    test_tickets = [
        # ERP Team tickets
        Ticket(id="T-ERP-P1", title="SAP Prod Outage", description="SAP production database unresponsive", category="ERP / SAP", priority=1, assignment_group="Enterprise-ERP-Support", caller_email="user1@corp.com", state="new"),
        Ticket(id="T-ERP-P2", title="ABAP RFC Error", description="RFC connection timeout", category="ERP / SAP", priority=2, assignment_group="Enterprise-ERP-Support", caller_email="user2@corp.com", state="new"),
        Ticket(id="T-ERP-P3", title="SAP GUI Lock", description="User session locked in GUI", category="ERP / SAP", priority=3, assignment_group="Enterprise-ERP-Support", caller_email="user3@corp.com", state="new"),
        Ticket(id="T-ERP-P4", title="SAP Cost Center Query", description="Help with cost center assignment", category="ERP / SAP", priority=4, assignment_group="Enterprise-ERP-Support", caller_email="user4@corp.com", state="new"),

        # Network Team tickets (including a P1 Major Outage)
        Ticket(id="T-NET-P1", title="Core Switch Down", description="Core datacenter switch failure", category="Network", priority=1, assignment_group="Network-Infrastructure-Ops", caller_email="user5@corp.com", state="new"),
        Ticket(id="T-NET-P2", title="VPN Gateway Latency", description="High packet drop on VPN gateway", category="Network", priority=2, assignment_group="Network-Infrastructure-Ops", caller_email="user6@corp.com", state="new"),
        Ticket(id="T-NET-P3", title="Wi-Fi AP Offline", description="Floor 3 access point offline", category="Network", priority=3, assignment_group="Network-Infrastructure-Ops", caller_email="user7@corp.com", state="new"),

        # End-User Allison Hill personal ticket
        Ticket(id="T-USER-ALLISON", title="Password Reset Request", description="Allison locked out of account", category="Hardware", priority=3, assignment_group="Desktop-Support-L2", caller_email="allison.hill@corp.com", state="new"),
    ]
    for t in test_tickets:
        db_session.merge(t)
    db_session.commit()

    # 1. End-User: Allison Hill
    allison = ALL_PERSONAS["allison_hill"]
    allison_tickets, allison_badge = PortalService.get_rbac_tickets(db_session, allison)
    allison_ids = {t.id for t in allison_tickets}
    assert allison_ids == {"T-USER-ALLISON"}, "End-user must only view self-submitted tickets"
    assert "T-ERP-P1" not in allison_ids, "End-user must be hidden from enterprise P1 outages"
    assert "T-NET-P1" not in allison_ids
    assert "RBAC-TIER-0" in allison_badge["tier_code"]

    # 2. Junior Engineer: Siddharth Rao (Enterprise-ERP-Support)
    siddharth = ALL_PERSONAS["siddharth_rao"]
    siddharth_tickets, siddharth_badge = PortalService.get_rbac_tickets(db_session, siddharth)
    siddharth_ids = {t.id for t in siddharth_tickets}
    assert siddharth_ids == {"T-ERP-P3", "T-ERP-P4"}, "Junior must strictly see P3 and P4 tickets of own team"
    assert "T-ERP-P1" not in siddharth_ids, "Junior cannot see P1"
    assert "T-ERP-P2" not in siddharth_ids, "Junior cannot see P2"
    assert "T-NET-P1" not in siddharth_ids, "Junior cannot see other teams"
    assert "RBAC-TIER-1" in siddharth_badge["tier_code"]

    # 3. Senior Engineer: Kavita Patel (Enterprise-ERP-Support)
    kavita = ALL_PERSONAS["kavita_patel"]
    kavita_tickets, kavita_badge = PortalService.get_rbac_tickets(db_session, kavita)
    kavita_ids = {t.id for t in kavita_tickets}
    assert kavita_ids == {"T-ERP-P1", "T-ERP-P2", "T-ERP-P3", "T-ERP-P4"}, "Senior sees all P1-P4 of own team"
    assert "T-NET-P1" not in kavita_ids, "Senior cannot see cross-domain P1 outages"
    assert "T-NET-P2" not in kavita_ids
    assert "RBAC-TIER-2" in kavita_badge["tier_code"]

    # 4. Team Lead: David Miller (Enterprise-ERP-Support Lead)
    david = ALL_PERSONAS["david_miller"]
    david_tickets, david_badge = PortalService.get_rbac_tickets(db_session, david)
    david_ids = {t.id for t in david_tickets}
    assert david_ids == {"T-ERP-P1", "T-ERP-P2", "T-ERP-P3", "T-ERP-P4", "T-NET-P1"}, "Lead sees own team + all cross-domain P1 War Room outages"
    assert "T-NET-P2" not in david_ids, "Lead cannot see non-P1 tickets of other teams"
    assert "T-NET-P3" not in david_ids
    assert "RBAC-TIER-3" in david_badge["tier_code"]

    # 5. Dispatcher: Sarah Connor & Auditor: Elena Vance
    sarah = ALL_PERSONAS["sarah_connor"]
    sarah_tickets, sarah_badge = PortalService.get_rbac_tickets(db_session, sarah)
    assert len(sarah_tickets) == len(test_tickets), "Dispatcher has global unrestricted visibility"
    assert "RBAC-TIER-4" in sarah_badge["tier_code"]

    elena = ALL_PERSONAS["elena_vance"]
    elena_tickets, elena_badge = PortalService.get_rbac_tickets(db_session, elena)
    assert len(elena_tickets) == len(test_tickets), "Auditor has global unrestricted visibility"
    assert "RBAC-TIER-4" in elena_badge["tier_code"]


def test_portal_can_dispatch_tickets():
    """Verify that intake ticket dispatch is strictly limited to Dispatchers and Leads."""
    from src.mock_itsm.portal_service import ALL_PERSONAS

    # Dispatcher and Team Leads HAVE dispatch authority
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["sarah_connor"]) is True
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["david_miller"]) is True
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["alice_cooper"]) is True
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["carol_danvers"]) is True
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["bob_martinez"]) is True

    # Senior Engineers CANNOT dispatch (operational resolvers)
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["kavita_patel"]) is False
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["marcus_vance"]) is False
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["fatima_zahra"]) is False

    # Junior Engineers CANNOT dispatch
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["siddharth_rao"]) is False
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["chloe_bennett"]) is False

    # Auditor & End-User CANNOT dispatch
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["elena_vance"]) is False
    assert PortalService.can_dispatch_tickets(ALL_PERSONAS["allison_hill"]) is False



