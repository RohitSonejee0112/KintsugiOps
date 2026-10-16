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

