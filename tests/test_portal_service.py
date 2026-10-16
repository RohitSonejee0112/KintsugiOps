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
