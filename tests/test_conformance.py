"""Unit tests for Process Mining Conformance Checking (Token-Based Replay) and Handover of Work."""
import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta

from src.process_mining.analyzer import ProcessMiningAnalyzer


@pytest.fixture
def sample_event_log_df():
    """Build synthetic event log DataFrame with compliant traces, unauthorized bypasses, and ping-pongs."""
    t0 = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    records = []

    # Case 1: Standard ITIL Compliant trace
    records.extend([
        {"case:concept:name": "INC101", "concept:name": "Created", "time:timestamp": t0, "org:group": "ServiceDesk-L1", "org:resource": "caller@corp.com"},
        {"case:concept:name": "INC101", "concept:name": "Assigned", "time:timestamp": t0 + timedelta(minutes=15), "org:group": "Desktop-Support-L2", "org:resource": "dispatcher"},
        {"case:concept:name": "INC101", "concept:name": "State_Changed", "time:timestamp": t0 + timedelta(hours=1), "org:group": "Desktop-Support-L2", "org:resource": "tech-alice"},
        {"case:concept:name": "INC101", "concept:name": "Resolved", "time:timestamp": t0 + timedelta(hours=3), "org:group": "Desktop-Support-L2", "org:resource": "tech-alice"},
    ])

    # Case 2: Authorized Runbook Auto-Resolution
    records.extend([
        {"case:concept:name": "INC102", "concept:name": "Created", "time:timestamp": t0 + timedelta(minutes=10), "org:group": "IAM-Identity-Operations", "org:resource": "caller2@corp.com"},
        {"case:concept:name": "INC102", "concept:name": "Resolved", "time:timestamp": t0 + timedelta(minutes=11), "org:group": "IAM-Identity-Operations", "org:resource": "RunbookEngine"},
    ])

    # Case 3: Unauthorized Direct Resolution Bypass (Human resolves immediately without assignment)
    records.extend([
        {"case:concept:name": "INC103", "concept:name": "Created", "time:timestamp": t0 + timedelta(minutes=20), "org:group": "ServiceDesk-L1", "org:resource": "caller3@corp.com"},
        {"case:concept:name": "INC103", "concept:name": "Resolved", "time:timestamp": t0 + timedelta(minutes=25), "org:group": "ServiceDesk-L1", "org:resource": "rogue-agent"},
    ])

    # Case 4: Escalation Ping-Pong Deviation (Bouncing across groups)
    records.extend([
        {"case:concept:name": "INC104", "concept:name": "Created", "time:timestamp": t0 + timedelta(minutes=30), "org:group": "ServiceDesk-L1", "org:resource": "caller4@corp.com"},
        {"case:concept:name": "INC104", "concept:name": "Assigned", "time:timestamp": t0 + timedelta(minutes=40), "org:group": "ServiceDesk-L1", "org:resource": "dispatcher"},
        {"case:concept:name": "INC104", "concept:name": "Reassigned", "time:timestamp": t0 + timedelta(hours=2), "org:group": "Network-Infrastructure-Ops", "org:resource": "tech-l1"},
        {"case:concept:name": "INC104", "concept:name": "Reassigned", "time:timestamp": t0 + timedelta(hours=5), "org:group": "ServiceDesk-L1", "org:resource": "net-specialist"},
        {"case:concept:name": "INC104", "concept:name": "Reassigned", "time:timestamp": t0 + timedelta(hours=8), "org:group": "Network-Infrastructure-Ops", "org:resource": "tech-l1"},
        {"case:concept:name": "INC104", "concept:name": "Resolved", "time:timestamp": t0 + timedelta(hours=12), "org:group": "Network-Infrastructure-Ops", "org:resource": "net-specialist"},
    ])

    return pd.DataFrame(records)


def test_conformance_checking_token_replay(sample_event_log_df):
    """Test Petri net discovery and Token-Based Replay Conformance Checking."""
    analyzer = ProcessMiningAnalyzer(sample_event_log_df)
    results = analyzer.run_conformance_checking()

    assert "fitness" in results
    assert "average_trace_fitness" in results["fitness"]
    assert results["fitness"]["average_trace_fitness"] > 0.0
    assert "precision" in results
    assert results["precision"] > 0.0
    assert "f1_process_score" in results
    assert results["total_cases"] == 4

    # Verify that violations were identified
    violations = results["violations"]
    assert len(violations) > 0

    violation_types = [v["violation_type"] for v in violations]
    # Check that unauthorized bypass was caught
    assert "Unauthorized Direct Resolution Bypass" in violation_types
    # Check that ping-pong escalation was caught
    assert "Escalation Ping-Pong Deviation" in violation_types

    # Find the bypass case INC103
    bypass_violation = next(v for v in violations if v["case_id"] == "INC103")
    assert bypass_violation["severity"] == "High"
    assert "rogue-agent" in bypass_violation["details"]


def test_handover_of_work_network(sample_event_log_df):
    """Test Handover of Work organizational mining."""
    analyzer = ProcessMiningAnalyzer(sample_event_log_df)
    handovers = analyzer.compute_handover_network(resource_key="org:group")

    assert isinstance(handovers, list)
    assert len(handovers) > 0

    # There should be handovers between ServiceDesk-L1 and Network-Infrastructure-Ops
    pairs = [(h["from_node"], h["to_node"]) for h in handovers]
    assert ("ServiceDesk-L1", "Network-Infrastructure-Ops") in pairs or ("Network-Infrastructure-Ops", "ServiceDesk-L1") in pairs


def test_conformance_empty_dataframe():
    """Verify graceful handling of empty event logs."""
    empty_df = pd.DataFrame(columns=["case:concept:name", "concept:name", "time:timestamp"])
    analyzer = ProcessMiningAnalyzer(empty_df)
    results = analyzer.run_conformance_checking()
    assert results["total_cases"] == 0
    assert results["fitness"]["average_trace_fitness"] == 1.0
    assert results["violations"] == []
