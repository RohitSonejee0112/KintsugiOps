"""Unit tests for automation engine, baseline rules, SLAs, and runbooks."""
from datetime import datetime, timezone, timedelta
import pytest
from src.automation.rules_engine import RulesEngine
from src.automation.sla_monitor import SLAMonitor
from src.automation.runbooks.password_reset import PasswordResetRunbook
from src.automation.runbooks.software_access import SoftwareAccessRunbook
from src.automation.engine import AutomationEngine
from src.integrations.mock_provider import MockITSMProvider
from src.mock_itsm.database import Base, engine


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_rules_engine_routing():
    engine = RulesEngine()

    # Category match
    res1 = engine.evaluate_routing({"category": "Network", "title": "Slow browsing", "description": ""})
    assert res1["assignment_group"] == "Network-Infrastructure-Ops"
    assert res1["confidence"] >= 0.90

    # Keyword match
    res2 = engine.evaluate_routing({"category": "Unknown", "title": "SAP GUI crash", "description": "Error in va01"})
    assert res2["assignment_group"] == "Enterprise-ERP-Support"
    assert res2["confidence"] >= 0.80

    # Fallback
    res3 = engine.evaluate_routing({"category": "Unknown", "title": "Coffee machine broken", "description": ""})
    assert res3["assignment_group"] == "ServiceDesk-L1"
    assert res3["confidence"] <= 0.50


def test_sla_monitor():
    monitor = SLAMonitor()
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    # P1: 2 hours allowed. 1 hour elapsed -> 50% elapsed, not breached, no warning
    p1_eval = monitor.evaluate_ticket(created_at=one_hour_ago, priority=1, current_time=now)
    assert p1_eval["minutes_allowed"] == 120
    assert not p1_eval["is_breached"]
    assert not p1_eval["is_warning"]

    # P1: 1.8 hours (108 mins) elapsed -> 90% elapsed -> warning should trigger!
    almost_breached = now - timedelta(minutes=100)
    p1_warn = monitor.evaluate_ticket(created_at=almost_breached, priority=1, current_time=now)
    assert p1_warn["is_warning"] is True

    # P1: 3 hours elapsed -> breached
    three_hours_ago = now - timedelta(hours=3)
    p1_breach = monitor.evaluate_ticket(created_at=three_hours_ago, priority=1, current_time=now)
    assert p1_breach["is_breached"] is True


def test_password_reset_runbook():
    runbook = PasswordResetRunbook()
    ticket = {
        "id": "INC001234",
        "title": "Need password reset for active directory",
        "description": "User locked out after wrong attempts",
        "caller_email": "employee@company.com",
    }
    assert runbook.can_handle(ticket) is True
    result = runbook.execute(ticket)
    assert result.success is True
    assert "Active Directory user status" in result.resolution_notes


def test_automation_engine_auto_resolution():
    provider = MockITSMProvider()
    engine = AutomationEngine(provider=provider)

    # Create ticket in provider
    ticket_data = {
        "title": "Password reset needed",
        "description": "I cannot log in to Windows desktop",
        "category": "Access / Identity",
        "impact": 3,
        "urgency": 2,
        "caller_email": "bob@company.com",
    }
    ticket = provider.create_ticket(ticket_data)

    # Process through automation engine
    res = engine.process_ticket({"id": ticket.id, **ticket_data})
    assert res["status"] == "auto_resolved"
    assert res["runbook"] == "PasswordResetRunbook"

    # Verify ticket in provider is resolved
    updated = provider.get_ticket(ticket.id)
    assert updated.state == "resolved"
    assert updated.auto_resolved is True


def test_automation_engine_routing_and_sla():
    provider = MockITSMProvider()
    engine = AutomationEngine(provider=provider)

    ticket_data = {
        "title": "Switch port failing on core rack",
        "description": "Intermittent CRC errors detected on 10Gbps trunk",
        "category": "Network",
        "impact": 1,
        "urgency": 1,
        "caller_email": "network_admin@company.com",
    }
    ticket = provider.create_ticket(ticket_data)

    res = engine.process_ticket({"id": ticket.id, **ticket_data, "priority": 1})
    assert res["status"] == "routed"
    assert res["assignment_group"] == "Network-Infrastructure-Ops"
    assert "sla_deadline" in res

    updated = provider.get_ticket(ticket.id)
    assert updated.assignment_group == "Network-Infrastructure-Ops"
    assert updated.state == "assigned"
