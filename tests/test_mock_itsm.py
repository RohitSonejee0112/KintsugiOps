"""Unit and integration tests for Mock ITSM API, Models, and Webhooks."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.mock_itsm.database import Base, get_db
from src.mock_itsm.main import app
from src.mock_itsm.models import calculate_itil_priority
from src.mock_itsm.webhooks import generate_hmac_signature, verify_signature
from src.simulation.generator import generate_synthetic_ticket

from sqlalchemy.pool import StaticPool

# Setup in-memory SQLite database with StaticPool for isolated testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Mock ITSM" in data["service"]


def test_itil_priority_matrix():
    # Critical: Imp 1, Urg 1 -> P1
    assert calculate_itil_priority(1, 1) == 1
    # High: Imp 1, Urg 2 -> P2 / Imp 2, Urg 1 -> P2
    assert calculate_itil_priority(1, 2) == 2
    assert calculate_itil_priority(2, 1) == 2
    # Moderate: Imp 2, Urg 2 -> P3
    assert calculate_itil_priority(2, 2) == 3
    # Low: Imp 3, Urg 3 -> P4
    assert calculate_itil_priority(3, 3) == 4

    # Test via API endpoint
    res = client.post("/api/v1/priority/calculate", json={"impact": 1, "urgency": 1})
    assert res.status_code == 200
    assert res.json()["priority"] == 1


def test_create_ticket_and_audit_event():
    payload = {
        "title": "VPN connection drops every 10 minutes",
        "description": "User cannot stay connected to internal corporate network.",
        "category": "Network",
        "subcategory": "VPN Access",
        "impact": 2,
        "urgency": 1,
        "caller_email": "john.doe@company.com",
        "ticket_type": "incident",
        "tags": ["vpn", "network-drop"],
    }
    response = client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    ticket_id = data["id"]
    assert ticket_id.startswith("INC")
    assert data["priority"] == 2  # Imp 2, Urg 1 -> P2
    assert data["state"] == "new"
    assert "vpn" in data["tags"]

    # Verify event audit trail was recorded
    events_res = client.get(f"/api/v1/tickets/{ticket_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 1
    assert events[0]["activity"] == "Created"
    assert events[0]["actor"] == "john.doe@company.com"


def test_update_ticket_state_and_reassignment():
    # 1. Create ticket
    payload = {
        "title": "Need access to SAP T-Code VA01",
        "description": "Sales order creation authorization required.",
        "category": "ERP / SAP",
        "impact": 2,
        "urgency": 2,
        "caller_email": "alice@company.com",
        "ticket_type": "service_request",
    }
    res = client.post("/api/v1/tickets", json=payload)
    ticket_id = res.json()["id"]

    # 2. Update assignment group (reassignment) and state
    update_payload = {
        "assignment_group": "Enterprise-ERP-Support",
        "state": "in_progress",
        "actor": "dispatcher-ai",
    }
    patch_res = client.patch(f"/api/v1/tickets/{ticket_id}", json=update_payload)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["assignment_group"] == "Enterprise-ERP-Support"
    assert updated["state"] == "in_progress"

    # 3. Resolve ticket
    resolve_payload = {
        "state": "resolved",
        "resolution_notes": "Assigned role Z_VA01_SALES to user.",
        "auto_resolved": True,
        "actor": "runbook-engine",
    }
    res_final = client.patch(f"/api/v1/tickets/{ticket_id}", json=resolve_payload)
    assert res_final.status_code == 200
    assert res_final.json()["state"] == "resolved"
    assert res_final.json()["auto_resolved"] is True
    assert res_final.json()["resolved_at"] is not None

    # Check event history
    events = client.get(f"/api/v1/tickets/{ticket_id}/events").json()
    activities = [e["activity"] for e in events]
    assert "Created" in activities
    assert "Reassigned" in activities
    assert "State_Changed" in activities
    assert "Resolved" in activities


def test_webhook_signature_verification():
    secret = "super_secure_secret_123"
    payload = b'{"event":"ticket.created","ticket_id":"INC10001"}'

    signature = generate_hmac_signature(payload, secret)
    assert signature.startswith("sha256=")

    # Valid check
    assert verify_signature(payload, signature, secret) is True

    # Tampered payload check
    tampered = b'{"event":"ticket.created","ticket_id":"INC99999"}'
    assert verify_signature(tampered, signature, secret) is False

    # Wrong secret check
    assert verify_signature(payload, signature, "wrong_secret") is False


def test_synthetic_ticket_generator():
    ticket = generate_synthetic_ticket(seed=123)
    assert "id" in ticket
    assert "title" in ticket
    assert "description" in ticket
    assert ticket["category"] in [
        "Access / Identity", "Hardware", "Network", "ERP / SAP", "Cloud & DevOps"
    ]
    assert 1 <= ticket["priority"] <= 4
    assert 1 <= ticket["impact"] <= 3
    assert 1 <= ticket["urgency"] <= 3
    assert "@" in ticket["caller_email"]
