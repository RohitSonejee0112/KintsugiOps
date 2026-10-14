"""Unit tests for Integration layer, provider adapters, resilient client, and notifications."""
import pytest
from unittest.mock import patch, MagicMock
import httpx
from src.integrations.base import UnifiedTicket
from src.integrations.mock_provider import MockITSMProvider
from src.integrations.jira_provider import JiraProvider
from src.integrations.resilient_client import ResilientHttpClient, TransientHttpError
from src.integrations.slack_notifier import NotificationDispatcher
from src.mock_itsm.database import Base, engine


@pytest.fixture(autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_mock_itsm_provider_lifecycle():
    provider = MockITSMProvider()
    data = {
        "title": "Database connection pool exhausted",
        "description": "Postgres returning 'FATAL: remaining connection slots reserved'",
        "category": "Cloud & DevOps",
        "impact": 1,
        "urgency": 1,
        "caller_email": "sre@company.com",
    }
    ticket = provider.create_ticket(data)
    assert ticket.provider == "mock_itsm"
    assert ticket.priority == 1
    assert ticket.state == "new"

    # Fetch
    fetched = provider.get_ticket(ticket.id)
    assert fetched.id == ticket.id

    # Resolve
    resolved = provider.resolve_ticket(ticket.id, "Scaled PgBouncer instances from 2 to 4")
    assert resolved.state == "resolved"
    assert resolved.auto_resolved is True


def test_jira_provider_adapter():
    jira = JiraProvider()
    data = {
        "title": "Need PyCharm Professional license",
        "description": "Data analyst needs IDE license for Python scripts",
        "category": "Software",
        "priority": 3,
        "caller_email": "analyst@company.com",
    }
    issue = jira.create_ticket(data)
    assert issue.provider == "jira"
    assert issue.id.startswith("ITSM-")
    assert issue.priority == 3
    assert issue.state == "new"

    # Update state & resolve
    resolved = jira.resolve_ticket(issue.id, "License assigned in JetBrains portal")
    assert resolved.state == "resolved"
    assert resolved.auto_resolved is True


def test_resilient_http_client_idempotency_and_dlq():
    client = ResilientHttpClient(max_retries=2, backoff_factor=0.01, timeout=1.0)
    key = "unique-event-id-999"

    assert not client.is_idempotency_key_seen(key)
    client.mark_idempotency_key(key)
    assert client.is_idempotency_key_seen(key)

    # Test DLQ on persistent failure
    with patch("httpx.Client.request") as mock_req:
        mock_req.side_effect = httpx.ConnectTimeout("Connection timed out")
        with pytest.raises(Exception):
            client.execute_with_retry("POST", "https://unreachable.local/webhook", json_data={"test": 1})

        # Verify entry landed in DLQ
        dlq = client.get_dlq_entries()
        assert len(dlq) == 1
        assert dlq[0]["url"] == "https://unreachable.local/webhook"
        assert dlq[0]["retry_count"] == 2


def test_slack_notification_dispatcher():
    dispatcher = NotificationDispatcher()

    # Test P1 alert
    ticket = {
        "id": "INC009988",
        "title": "Core ERP down for all European plants",
        "description": "SAP production database offline",
        "priority": 1,
        "category": "ERP / SAP",
        "assignment_group": "Enterprise-ERP-Support",
        "caller_email": "plant_manager@company.com",
    }
    sent = dispatcher.notify_critical_ticket(ticket)
    assert sent is True
    assert len(dispatcher.sent_notifications) == 1
    assert dispatcher.sent_notifications[0]["event"] == "critical_incident"

    # Test Auto-resolution alert
    sent_res = dispatcher.notify_auto_resolution("INC009988", "PasswordResetRunbook", "Domain password reset")
    assert sent_res is True
    assert len(dispatcher.sent_notifications) == 2
