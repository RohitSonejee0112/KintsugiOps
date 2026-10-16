"""Unit tests for Vector Semantic Caching and Outage Storm Clustering."""
import pytest
from datetime import datetime, timezone, timedelta
from src.ai.semantic_cache import SemanticCache
from src.ai.schemas import TriageResult
from src.ai.classifier import AITriageClassifier


@pytest.fixture
def sample_triage_result():
    return TriageResult(
        category="Network",
        subcategory="VPN Outage",
        urgency=1,
        impact=1,
        priority=1,
        assignment_group="Network-Infrastructure-Ops",
        confidence_score=0.95,
        reasoning_summary="GlobalProtect VPN gateway down.",
        requires_human_review=False,
        pii_redacted_count=0,
    )


def test_semantic_cache_store_and_lookup(sample_triage_result):
    """Test storing an incident and retrieving it via cosine similarity match."""
    cache = SemanticCache(similarity_threshold=0.60, storm_threshold=3)
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Store master ticket
    entry = cache.store(
        ticket_id="INC1001",
        title="GlobalProtect VPN client authentication failing",
        description="Users in Frankfurt office unable to connect to internal VPN gateway",
        triage_result=sample_triage_result,
        now=t0
    )
    assert entry.master_ticket_id == "INC1001"

    # Query with semantic variation
    hit = cache.lookup(
        title="GlobalProtect VPN connection error",
        description="Frankfurt remote users cannot reach VPN gateway server",
        incoming_ticket_id="INC1002",
        now=t0 + timedelta(minutes=5)
    )

    assert hit is not None
    cached_res, cached_entry = hit
    assert cached_res.cache_hit is True
    assert cached_res.master_incident_id == "INC1001"
    assert cached_res.category == "Network"
    assert "INC1002" in cached_entry.child_ticket_ids
    assert cache.cache_hits == 1


def test_incident_storm_elevation(sample_triage_result):
    """Test that multiple near-duplicates within sliding window elevate to an active Incident Storm."""
    cache = SemanticCache(similarity_threshold=0.60, storm_threshold=3)
    t0 = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Master ticket
    cache.store(
        ticket_id="INC2001",
        title="Floor 3 West WiFi access points down",
        description="Access points dropping 802.1x connections across marketing wing",
        triage_result=sample_triage_result,
        now=t0
    )

    # 2. Second ticket (Child 1)
    h1 = cache.lookup(
        title="Floor 3 WiFi dropping connection",
        description="Wireless network disconnected in west wing marketing",
        incoming_ticket_id="INC2002",
        now=t0 + timedelta(minutes=2)
    )
    assert h1 is not None
    assert h1[1].is_storm is False  # Only 2 total tickets so far

    # 3. Third ticket (Child 2 -> triggers storm threshold >= 3)
    h2 = cache.lookup(
        title="WiFi access points not working floor 3",
        description="Marketing wing cannot connect to 802.1x wireless AP",
        incoming_ticket_id="INC2003",
        now=t0 + timedelta(minutes=4)
    )
    assert h2 is not None
    assert h2[1].is_storm is True  # Storm triggered!
    assert h2[0].is_storm_incident is True

    # Check active storms reporting
    active_storms = cache.get_active_storms()
    assert len(active_storms) == 1
    assert active_storms[0]["master_incident_id"] == "INC2001"
    assert active_storms[0]["total_storm_tickets"] == 3
    assert set(active_storms[0]["child_ticket_ids"]) == {"INC2002", "INC2003"}


def test_sliding_window_expiration(sample_triage_result):
    """Verify that tickets arriving after the sliding window expire and do not hit cache."""
    cache = SemanticCache(similarity_threshold=0.60, sliding_window_seconds=1800)  # 30 min window
    t0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

    cache.store(
        ticket_id="INC3001",
        title="Temporary network latency in Dublin DC",
        description="Dublin switch reporting packet loss",
        triage_result=sample_triage_result,
        now=t0
    )

    # Arriving 45 minutes later (outside 30 min window)
    hit = cache.lookup(
        title="Network latency Dublin DC",
        description="Dublin switch packet loss",
        incoming_ticket_id="INC3002",
        now=t0 + timedelta(minutes=45)
    )
    assert hit is None
    assert cache.cache_misses == 1


def test_classifier_end_to_end_with_semantic_cache():
    """Verify AITriageClassifier end-to-end integration with SemanticCache."""
    cache = SemanticCache(similarity_threshold=0.60)
    classifier = AITriageClassifier(semantic_cache=cache)

    # Call 1: First ticket (miss, processed & stored in cache)
    res1 = classifier.triage_ticket(
        title="VPN authentication failed for remote employee",
        description="GlobalProtect client gives error User certificate invalid",
        caller_email="alice@corp.com",
        ticket_id="INC4001"
    )
    assert res1.cache_hit is False
    assert res1.category == "Network"

    # Call 2: Near duplicate within minutes
    res2 = classifier.triage_ticket(
        title="VPN authentication error for remote worker",
        description="GlobalProtect client certificate invalid error",
        caller_email="bob@corp.com",
        ticket_id="INC4002"
    )
    assert res2.cache_hit is True
    assert res2.master_incident_id == "INC4001"
    assert "Semantic Cache Hit" in res2.reasoning_summary
