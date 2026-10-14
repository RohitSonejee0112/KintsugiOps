"""Unit tests for Phase 5 (Process Mining & Proposals) and Phase 6 (SharePoint Integration)."""
from datetime import datetime, timezone, timedelta
import pytest
import pandas as pd
from src.process_mining.event_logger import EventLogExtractor
from src.process_mining.analyzer import ProcessMiningAnalyzer
from src.process_mining.proposal_generator import StructuralProposalGenerator
from src.sharepoint.local_provider import LocalDocumentProvider
from src.sharepoint.report_builder import ReportBuilder
from src.mock_itsm.models import EventLog, Ticket
from src.mock_itsm.database import Base, engine, SessionLocal


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_process_mining_analyzer():
    now = datetime.now(timezone.utc)
    # Construct synthetic event logs with known ping-pong and dwell times
    records = [
        # Case 1: Simple flow
        {"case:concept:name": "INC101", "concept:name": "Created", "time:timestamp": now, "org:group": "ServiceDesk-L1", "org:resource": "caller", "from_state": None, "to_state": "new", "details": ""},
        {"case:concept:name": "INC101", "concept:name": "Assigned", "time:timestamp": now + timedelta(hours=1), "org:group": "ServiceDesk-L1", "org:resource": "agent", "from_state": "new", "to_state": "assigned", "details": ""},
        {"case:concept:name": "INC101", "concept:name": "Resolved", "time:timestamp": now + timedelta(hours=3), "org:group": "ServiceDesk-L1", "org:resource": "agent", "from_state": "assigned", "to_state": "resolved", "details": ""},

        # Case 2: Ping-Pong bounce
        {"case:concept:name": "INC102", "concept:name": "Created", "time:timestamp": now, "org:group": "ServiceDesk-L1", "org:resource": "caller", "from_state": None, "to_state": "new", "details": ""},
        {"case:concept:name": "INC102", "concept:name": "Reassigned", "time:timestamp": now + timedelta(hours=2), "org:group": "Enterprise-ERP-Support", "org:resource": "agent1", "from_state": "new", "to_state": "assigned", "details": ""},
        {"case:concept:name": "INC102", "concept:name": "Reassigned", "time:timestamp": now + timedelta(hours=5), "org:group": "ServiceDesk-L1", "org:resource": "agent2", "from_state": "assigned", "to_state": "assigned", "details": ""},
        {"case:concept:name": "INC102", "concept:name": "Resolved", "time:timestamp": now + timedelta(hours=8), "org:group": "Enterprise-ERP-Support", "org:resource": "agent3", "from_state": "assigned", "to_state": "resolved", "details": ""},
    ]

    df = pd.DataFrame(records)
    analyzer = ProcessMiningAnalyzer(df)

    summary = analyzer.get_summary_statistics()
    assert summary["total_cases"] == 2
    assert summary["total_events"] == 7

    bottlenecks = analyzer.detect_bottlenecks()
    assert len(bottlenecks) >= 1
    # Check that durations are computed
    assert bottlenecks[0]["mean_duration_hours"] > 0

    ping_pong = analyzer.detect_ping_pong_loops()
    assert ping_pong["ping_pong_cases_count"] == 1
    assert ping_pong["ping_pong_rate_pct"] == 50.0  # 1 out of 2 cases

    dfg = analyzer.compute_dfg()
    assert len(dfg["dfg"]) >= 1


def test_structural_proposal_generator():
    generator = StructuralProposalGenerator()
    bottlenecks = [
        {
            "from_activity": "Created",
            "to_activity": "Assigned",
            "transition_count": 450,
            "mean_duration_hours": 3.8,
            "median_duration_hours": 2.5,
            "max_duration_hours": 18.0,
        }
    ]
    ping_pong = {
        "ping_pong_cases_count": 48,
        "total_cases_evaluated": 250,
        "ping_pong_rate_pct": 19.2,
        "top_bouncing_pairs": [
            {"from_group": "ServiceDesk-L1", "to_group": "Enterprise-ERP-Support", "bounce_count": 35}
        ],
    }

    proposals = generator.generate_proposals(bottlenecks, ping_pong)
    assert len(proposals) >= 2

    # Verify proposals are grounded in data
    titles = [p.title for p in proposals]
    assert any("Ping-Pong" in t for t in titles)
    assert any("Dwell Time" in t for t in titles)
    assert "19.2%" in proposals[0].empirical_evidence or "35" in proposals[0].empirical_evidence


def test_sharepoint_local_provider_and_report_builder(tmp_path):
    local_provider = LocalDocumentProvider(base_dir=str(tmp_path / "sharepoint"))
    generator = StructuralProposalGenerator()

    proposals = generator.generate_proposals(
        bottlenecks=[{"from_activity": "Created", "to_activity": "Assigned", "transition_count": 10, "mean_duration_hours": 2.5, "median_duration_hours": 2.0, "max_duration_hours": 5.0}],
        ping_pong={"ping_pong_cases_count": 1, "ping_pong_rate_pct": 10.0, "top_bouncing_pairs": [{"from_group": "L1", "to_group": "L2", "bounce_count": 4}]}
    )

    # 1. Sync proposal to Tracker List
    for p in proposals:
        item = local_provider.create_improvement_item(p)
        assert item["id"] == p.proposal_id

    items = local_provider.list_improvement_items()
    assert len(items) == len(proposals)

    # 2. Update status
    updated = local_provider.update_improvement_item(items[0]["id"], {"status": "In Progress"})
    assert updated["status"] == "In Progress"

    # 3. Build and upload report
    report_content = ReportBuilder.build_markdown_report(
        summary={"total_cases": 100, "total_events": 350, "events_per_case_avg": 3.5},
        bottlenecks=[{"from_activity": "Created", "to_activity": "Assigned", "transition_count": 100, "mean_duration_hours": 3.2, "median_duration_hours": 2.1, "max_duration_hours": 12.0}],
        ping_pong={"ping_pong_cases_count": 12, "ping_pong_rate_pct": 12.0, "top_bouncing_pairs": []},
        proposals=proposals,
    )
    assert "# Executive Operational Audit" in report_content

    uploaded = local_provider.upload_report("audit_report_q1.md", report_content)
    assert uploaded["name"] == "audit_report_q1.md"
    assert uploaded["size_bytes"] > 0

    reports = local_provider.list_reports()
    assert len(reports) == 1
    assert reports[0]["name"] == "audit_report_q1.md"
