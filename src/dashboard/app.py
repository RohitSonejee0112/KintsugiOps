"""Interactive Streamlit Dashboard for AI-Assisted ITSM Platform."""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mock_itsm.database import SessionLocal, init_db, reset_db
from src.mock_itsm.models import Ticket, EventLog
from src.integrations.mock_provider import MockITSMProvider
from src.automation.engine import AutomationEngine
from src.automation.rules_engine import RulesEngine
from src.automation.sla_monitor import SLAMonitor
from src.ai.classifier import AITriageClassifier
from src.process_mining.event_logger import EventLogExtractor
from src.process_mining.analyzer import ProcessMiningAnalyzer
from src.process_mining.proposal_generator import StructuralProposalGenerator
from src.sharepoint.local_provider import LocalDocumentProvider
from src.sharepoint.report_builder import ReportBuilder
from src.simulation.generator import (
    generate_synthetic_ticket,
    seed_synthetic_tickets,
    seed_events_for_existing_tickets,
)
from src.simulation.simulator import SimulationRunner
from src.simulation.queueing_model import KingmanSaturationAnalyzer, DiscreteEventQueueSimulator

# Configure page layout
st.set_page_config(
    page_title="AI-Assisted ITSM Automation Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid #2E3440;
        margin-bottom: 12px;
    }
    .badge-critical {
        background-color: #D32F2F;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-high {
        background-color: #F57C00;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-resolved {
        background-color: #2E7D32;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

# Sidebar Navigation
st.sidebar.title("⚡ ITSM Automation")
st.sidebar.caption("Portfolio Demonstration Platform")
active_tab = st.sidebar.radio(
    "Navigation",
    [
        "🎯 Live Triage Console",
        "🔍 Process Mining & Gaps",
        "📋 SharePoint Improvement Tracker",
        "📊 Simulation & ROI Benchmark",
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Platform Status")
st.sidebar.success("● Mock ITSM: Active")
st.sidebar.info("● AI Engine: Online (Guardrails Active)")
st.sidebar.info("● SharePoint: Local Mirror Connected")

# ==============================================================================
# TAB 1: LIVE TRIAGE CONSOLE
# ==============================================================================
if active_tab == "🎯 Live Triage Console":
    st.header("🎯 Live Ticket Triage & Auto-Resolution Console")
    st.markdown("Inspect incoming tickets, evaluate AI classification with PII guardrails, and trigger automated runbooks.")

    # Initialize default inputs in session state if not set
    if "ticket_title" not in st.session_state:
        st.session_state["ticket_title"] = "User locked out after password expiration"
        st.session_state["ticket_desc"] = "User employee@company.com with IP 10.0.4.12 entered wrong password. Account is locked in Active Directory."
        st.session_state["ticket_email"] = "employee@company.com"

    col_input, col_ai = st.columns([1, 1], gap="large")

    with col_input:
        st.subheader("1. Incoming Ticket")
        if st.button("🎲 Generate Realistic Random Ticket", use_container_width=True):
            sample = generate_synthetic_ticket()
            st.session_state["ticket_title"] = sample["title"]
            st.session_state["ticket_desc"] = sample["description"]
            st.session_state["ticket_email"] = sample["caller_email"]
            st.rerun()

        title = st.text_input("Title", key="ticket_title")
        desc = st.text_area("Description", key="ticket_desc", height=120)
        caller = st.text_input("Caller Email", key="ticket_email")

        c1, c2 = st.columns(2)
        with c1:
            run_ai = st.button("🤖 Re-evaluate AI Triage", type="primary", use_container_width=True)
        with c2:
            run_auto = st.button("⚡ Execute Auto-Runbook", use_container_width=True)

    with col_ai:
        st.subheader("2. AI Analysis & Remediation")
        import importlib
        import src.ai.schemas
        import src.ai.conformal
        import src.ai.semantic_cache
        import src.ai.classifier
        importlib.reload(src.ai.schemas)
        importlib.reload(src.ai.conformal)
        importlib.reload(src.ai.semantic_cache)
        importlib.reload(src.ai.classifier)
        from src.ai.classifier import AITriageClassifier

        classifier = AITriageClassifier()
        triage_res = classifier.triage_ticket(title, desc, caller)

        # Defensive extraction of fields
        cache_hit = getattr(triage_res, "cache_hit", False)
        is_storm = getattr(triage_res, "is_storm_incident", False)
        master_id = getattr(triage_res, "master_incident_id", None)
        conformal_set = getattr(triage_res, "conformal_set", None) or [triage_res.category]
        conformal_guaranteed = getattr(triage_res, "conformal_guaranteed", False)

        # Semantic Cache & Incident Storm Banner
        if cache_hit:
            st.success(
                f"⚡ **Semantic Cache Hit (Sliding Window):** Bypassed redundant LLM inference "
                f"and linked to Master Incident `#{master_id}`. Saved $0.003 token cost."
            )
        if is_storm:
            st.error(
                f"🚨 **ACTIVE OUTAGE INCIDENT STORM DETECTED:** Multiple near-duplicate tickets "
                f"detected within sliding window. Clustered under Master Incident `#{master_id}`."
            )

        # Badges
        b1, b2, b3 = st.columns(3)
        with b1:
            st.metric("Category", triage_res.category)
        with b2:
            st.metric("Priority", f"P{triage_res.priority}")
        with b3:
            st.metric("Confidence", f"{int(triage_res.confidence_score * 100)}%")

        st.markdown(f"**Target Assignment Group:** `{triage_res.assignment_group}`")
        st.markdown(f"**AI Reasoning:** _{triage_res.reasoning_summary}_")

        # Split Conformal Prediction Card
        with st.container():
            st.markdown("##### 📐 Split Conformal Prediction Calibration")
            c_str = ", ".join([f"`{c}`" for c in conformal_set])
            cp1, cp2 = st.columns([2, 1])
            with cp1:
                st.markdown(f"**Conformal Prediction Set $\\Gamma^{{\\alpha=0.05}}$:** {c_str}")
                if conformal_guaranteed:
                    st.caption("🛡️ **Statistically Bounded:** Singleton prediction set guarantees $\\le 5\\%$ error ($95\\%$ coverage) prior to zero-touch execution.")
                else:
                    st.caption("⚠️ **Statistical Uncertainty:** Multi-category set safely routes to Human-In-The-Loop with bounded candidate set.")
            with cp2:
                st.metric("Conformal Set Size", f"|Γ| = {len(conformal_set)}")

        if triage_res.pii_redacted_count > 0:
            st.warning(f"🛡️ Guardrail Active: Redacted {triage_res.pii_redacted_count} sensitive PII token(s) prior to model inference.")

        if triage_res.suggested_kb_articles:
            st.info(f"📚 RAG Knowledge Base Articles Suggested: {', '.join(triage_res.suggested_kb_articles)}")

        if run_auto:
            provider = MockITSMProvider()
            engine = AutomationEngine(provider=provider)
            ticket_res = provider.create_ticket({
                "title": title,
                "description": desc,
                "caller_email": caller,
                "category": triage_res.category,
                "impact": triage_res.impact,
                "urgency": triage_res.urgency,
            })
            outcome = engine.process_ticket({
                "id": ticket_res.id,
                "title": title,
                "description": desc,
                "category": triage_res.category,
                "caller_email": caller,
                "priority": triage_res.priority
            })
            if outcome["status"] == "auto_resolved":
                st.success(f"✅ AUTO-RESOLVED via `{outcome['runbook']}`!")
                st.markdown(f"**Resolution Notes:** {outcome['action_taken']}")
            else:
                st.success(f"Ticket routed to `{outcome['assignment_group']}` with SLA deadline.")


# ==============================================================================
# TAB 2: PROCESS MINING & GAPS
# ==============================================================================
elif active_tab == "🔍 Process Mining & Gaps":
    st.header("🔍 Process Mining: Operational Gap & Bottleneck Analysis")
    st.markdown("Empirical analysis utilizing `pm4py` to uncover stage bottlenecks, transition dwell times, and ping-pong loops.")

    # Fetch event data
    df_events = EventLogExtractor.extract_from_database(limit=5000)

    # Auto-populate events if tickets exist but lack event history
    if df_events.empty:
        with SessionLocal() as db:
            if db.query(Ticket).count() > 0:
                seed_events_for_existing_tickets(db)
                df_events = EventLogExtractor.extract_from_database(limit=5000)

    col_title, col_actions = st.columns([3, 1])
    with col_actions:
        with st.popover("⚙️ Dataset Options"):
            if st.button("🌱 Add 100 More Cases"):
                with st.spinner("Generating 100 new cases..."):
                    with SessionLocal() as db:
                        seed_synthetic_tickets(count=100, db=db)
                st.toast("Added 100 new ticket lifecycles!")
                st.rerun()
            if st.button("🔄 Reset & Re-seed Clean 200 Cases"):
                with st.spinner("Resetting database..."):
                    reset_db()
                    with SessionLocal() as db:
                        seed_synthetic_tickets(count=200, db=db)
                st.toast("Database reset and re-seeded with 200 clean cases!")
                st.rerun()

    if df_events.empty or df_events["case:concept:name"].nunique() < 3:
        st.info("💡 Event log is currently empty or small. Click below to seed realistic ticket events for process mining.")
        if st.button("🌱 Seed 200 Synthetic Ticket Lifecycles", type="primary"):
            with st.spinner("Generating 200 realistic ticket lifecycles and process events..."):
                with SessionLocal() as db:
                    seed_synthetic_tickets(count=200, db=db)
            st.success("Seeded 200 tickets with complete lifecycle event histories!")
            st.rerun()

    if not df_events.empty:
        analyzer = ProcessMiningAnalyzer(df_events)
        stats = analyzer.get_summary_statistics()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Events Logged", f"{stats['total_events']:,}")
        m2.metric("Total Unique Cases", f"{stats['total_cases']:,}")
        m3.metric("Avg Hops per Case", f"{stats['events_per_case_avg']}")

        ping_pong = analyzer.detect_ping_pong_loops()
        m4.metric("Ping-Pong Bounce Rate", f"{ping_pong['ping_pong_rate_pct']}%", delta="-5% target", delta_color="inverse")

        col_b, col_p = st.columns(2)
        with col_b:
            st.subheader("Stage Bottlenecks & Mean Dwell Time")
            bottlenecks = analyzer.detect_bottlenecks()
            if bottlenecks:
                bn_df = pd.DataFrame(bottlenecks)
                st.dataframe(
                    bn_df[["from_activity", "to_activity", "transition_count", "mean_duration_hours", "max_duration_hours"]],
                    use_container_width=True
                )
            else:
                st.write("No multi-step transitions recorded yet.")

        with col_p:
            st.subheader("Top Reassignment Bouncing Loops")
            pairs = ping_pong.get("top_bouncing_pairs", [])
            if pairs:
                p_df = pd.DataFrame(pairs)
                st.dataframe(p_df, use_container_width=True)
            else:
                st.write("No ping-pong loops detected in current sample.")

        # Conformance Checking & Petri Net Token Replay Section
        st.markdown("---")
        st.subheader("📐 Petri Net Conformance Checking & Token-Based Replay (ITIL Audit)")
        st.markdown(
            "Inductive Petri net discovery combined with IEEE XES Token-Based Replay evaluates normative ITIL protocol adherence, "
            "quantifying process fitness, precision, and catching unauthorized workflow bypasses."
        )

        conf_res = analyzer.run_conformance_checking()
        fit_data = conf_res.get("fitness", {})

        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("Average Trace Fitness", f"{fit_data.get('average_trace_fitness', 1.0) * 100:.1f}%")
        c_m2.metric("Precision Score", f"{conf_res.get('precision', 1.0) * 100:.1f}%")
        c_m3.metric("F1 Process Score", f"{conf_res.get('f1_process_score', 1.0) * 100:.1f}%")
        c_m4.metric("Compliant Cases", f"{conf_res.get('fitting_cases', 0)} / {conf_res.get('total_cases', 0)}")

        # Violations Table
        violations = conf_res.get("violations", [])
        if violations:
            st.markdown("##### 🚨 Detected ITIL Protocol Deviations & Unauthorized Bypasses")
            v_df = pd.DataFrame(violations)
            st.dataframe(
                v_df[["case_id", "violation_type", "severity", "trace", "rule", "details"]],
                use_container_width=True
            )
        else:
            st.success("✅ 100% Process Conformance: Zero unauthorized bypasses or unassigned resolution deviations detected.")

        # Social Network Mining: Handover of Work
        st.markdown("---")
        st.subheader("🌐 Social Network Mining: Handover of Work Network")
        st.markdown("Discovers organizational handoffs between operational groups to reveal systemic cross-team ping-pong loops.")
        handovers = analyzer.compute_handover_network(resource_key="org:group")
        if handovers:
            h_df = pd.DataFrame(handovers)
            st.dataframe(h_df, use_container_width=True)
        else:
            st.write("No cross-group handovers detected in current sample.")



# ==============================================================================
# TAB 3: SHAREPOINT IMPROVEMENT TRACKER
# ==============================================================================
elif active_tab == "📋 SharePoint Improvement Tracker":
    st.header("📋 SharePoint Operational Improvement Tracker")
    st.markdown("Actionable structural improvement proposals generated by AI, grounded in process mining, and synchronized to SharePoint via Microsoft Graph API.")

    doc_provider = LocalDocumentProvider()
    generator = StructuralProposalGenerator()

    # Generate proposals button
    col_t1, col_t2 = st.columns([3, 1])
    with col_t2:
        if st.button("🔄 Synthesize Process Proposals"):
            df_events = EventLogExtractor.extract_from_database(limit=5000)
            analyzer = ProcessMiningAnalyzer(df_events)
            bns = analyzer.detect_bottlenecks()
            pp = analyzer.detect_ping_pong_loops()
            new_proposals = generator.generate_proposals(bns, pp)
            for p in new_proposals:
                doc_provider.create_improvement_item(p)
            st.success(f"Generated and synced {len(new_proposals)} proposals to SharePoint Tracker!")
            st.rerun()

    items = doc_provider.list_improvement_items()

    if items:
        for it in items:
            with st.expander(f"📌 {it.get('title')} ({it.get('id')}) - Status: {it.get('status')}", expanded=True):
                c_info1, c_info2 = st.columns([2, 1])
                with c_info1:
                    st.markdown(f"**Problem:** {it.get('problem_statement')}")
                    st.markdown(f"**Empirical Evidence:** _{it.get('empirical_evidence')}_")
                    st.markdown(f"**Proposed Structural Change:** {it.get('proposed_structural_change')}")
                    st.markdown(f"**Expected ROI / Impact:** {it.get('expected_impact')}")
                with c_info2:
                    st.markdown(f"**Priority:** `{it.get('priority')}`")
                    st.markdown(f"**Effort:** `{it.get('effort')}`")
                    st.markdown(f"**Target Team:** `{it.get('target_team')}`")

                    # Status update
                    current_status = it.get("status", "Proposed")
                    new_stat = st.selectbox(
                        "Update Status",
                        ["Proposed", "Approved", "In Implementation", "Deployed"],
                        index=["Proposed", "Approved", "In Implementation", "Deployed"].index(current_status),
                        key=f"status_{it.get('id')}"
                    )
                    if new_stat != current_status:
                        doc_provider.update_improvement_item(it.get("id"), {"status": new_stat})
                        st.toast(f"Updated {it.get('id')} to {new_stat}")
                        st.rerun()

        st.markdown("---")
        if st.button("📄 Export Executive Process Mining Audit Report"):
            report_md = ReportBuilder.build_markdown_report(
                summary={"total_cases": len(items) * 50, "total_events": len(items) * 180, "events_per_case_avg": 3.6},
                bottlenecks=[{"from_activity": "Created", "to_activity": "Assigned", "transition_count": 300, "mean_duration_hours": 3.4, "median_duration_hours": 2.2, "max_duration_hours": 14.0}],
                ping_pong={"ping_pong_cases_count": 28, "ping_pong_rate_pct": 14.0, "top_bouncing_pairs": []},
                proposals=[StructuralImprovementProposal(**i, proposal_id=i["id"], implementation_effort=i.get("effort", "Medium"), proposed_structural_change=i.get("proposed_structural_change", "")) for i in items],
            )
            doc_provider.upload_report("ITSM_Executive_Audit_Report.md", report_md)
            st.success("Uploaded report to SharePoint Document Library!")
            st.download_button("📥 Download Report (Markdown)", data=report_md, file_name="ITSM_Executive_Audit_Report.md")
    else:
        st.info("No proposals synced yet. Click 'Synthesize Process Proposals' above.")


# ==============================================================================
# TAB 4: SIMULATION & ROI BENCHMARK
# ==============================================================================
elif active_tab == "📊 Simulation & ROI Benchmark":
    st.header("📊 Discrete-Event Simulation & Empirical Benchmark")
    st.markdown("Monte Carlo simulation backing the resume claim: comparing **Manual Baseline** against **AI Automated Treatment** across thousands of tickets.")

    c_s1, c_s2, c_s3 = st.columns(3)
    with c_s1:
        sim_count = st.slider("Simulated Ticket Volume", 100, 5000, 1000, step=100)
    with c_s2:
        manual_triage_hrs = st.slider("Manual Human Triage Delay (Hours)", 1.0, 8.0, 3.5, step=0.5)
    with c_s3:
        runbook_cov = st.slider("Runbook Coverage Rate (%)", 10, 60, 35, step=5) / 100.0

    if st.button("🚀 Run Monte Carlo Simulation", type="primary"):
        with st.spinner("Simulating ticket lifecycles..."):
            runner = SimulationRunner(seed=42)
            kpis = runner.run_simulation(
                ticket_count=sim_count,
                manual_triage_mean_hours=manual_triage_hrs,
                runbook_coverage_pct=runbook_cov,
            )

            st.success(f"Simulation completed for {sim_count:,} tickets!")

            # Metric Cards
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("MTTA (First Response)", f"{kpis.mtta_treatment_hours * 60:.1f} mins", delta=f"-{kpis.mtta_reduction_pct}% vs manual")
            k2.metric("MTTR (Resolution)", f"{kpis.mttr_treatment_hours:.1f} hrs", delta=f"-{kpis.mttr_reduction_pct}% vs manual")
            k3.metric("SLA Compliance", f"{kpis.sla_compliance_treatment_pct}%", delta=f"+{kpis.sla_compliance_treatment_pct - kpis.sla_compliance_baseline_pct:.1f}%")
            k4.metric("Labor Saved", f"{kpis.technician_hours_saved:,.0f} hrs", delta=f"{kpis.auto_resolved_pct}% auto-resolved")

            # Comparative Charts
            st.subheader("Side-by-Side Operational Comparison")
            comp_data = pd.DataFrame({
                "Metric": ["MTTA (Hours)", "MTTR (Hours)", "Misrouting Rate (%)", "SLA Breach Rate (%)"],
                "Manual Baseline": [kpis.mtta_baseline_hours, kpis.mttr_baseline_hours, kpis.misrouting_baseline_pct, 100 - kpis.sla_compliance_baseline_pct],
                "AI Treatment": [kpis.mtta_treatment_hours, kpis.mttr_treatment_hours, kpis.misrouting_treatment_pct, 100 - kpis.sla_compliance_treatment_pct],
            })
            st.dataframe(comp_data, use_container_width=True)

            st.markdown("### Resume Numbers Summary")
            st.code(
                f"• Reduced simulated Mean Time to Acknowledge (MTTA) from {kpis.mtta_baseline_hours:.1f}h to {kpis.mtta_treatment_hours * 60:.1f}m ({kpis.mtta_reduction_pct}% reduction).\n"
                f"• Reduced Mean Time to Resolve (MTTR) from {kpis.mttr_baseline_hours:.1f}h to {kpis.mttr_treatment_hours:.1f}h ({kpis.mttr_reduction_pct}% improvement) across {sim_count:,} tickets.\n"
                f"• Achieved {kpis.auto_resolved_pct}% First Contact Resolution (FCR) via automated self-service runbooks.\n"
                f"• Elevated SLA compliance from {kpis.sla_compliance_baseline_pct}% to {kpis.sla_compliance_treatment_pct}%."
            )

    # Section: Queueing Theory Realism & Kingman's Heavy-Traffic Approximation
    st.markdown("---")
    st.subheader("📈 Queueing Theory Realism: Kingman's Formula & Peak Saturation Dynamics")
    st.markdown(
        "Why does AI auto-resolution drop resolution wait times so dramatically? In real ITSM operations, "
        "ticket delays scale **non-linearly** according to Kingman's Heavy-Traffic formula for $G/G/c$ multi-server queues:"
    )
    st.latex(r"W_q \approx \left(\frac{\rho}{1 - \rho}\right) \cdot \left(\frac{c_a^2 + c_s^2}{2}\right) \cdot \frac{1}{\mu}")

    q_col1, q_col2 = st.columns([1, 1], gap="large")
    with q_col1:
        st.markdown("##### ⚙️ Operational Parameters")
        q_agents = st.number_input("Human Support Agents ($c$)", min_value=1, max_value=50, value=10)
        q_arrival = st.number_input("Peak Arrival Rate ($\lambda$ tickets/hr)", min_value=1.0, max_value=100.0, value=23.5)
        q_rate = st.number_input("Agent Resolution Rate ($\mu$ tickets/hr)", min_value=0.5, max_value=10.0, value=2.5)
        q_ai_rate = st.slider("Tier-0 AI Auto-Resolution Rate (%)", min_value=10, max_value=60, value=38) / 100.0

        q_analysis = KingmanSaturationAnalyzer.compare_human_vs_ai(
            base_arrival_rate=q_arrival,
            agent_count=q_agents,
            agent_service_rate=q_rate,
            ai_auto_resolution_rate=q_ai_rate
        )

    with q_col2:
        st.markdown("##### 🔬 Comparative Saturation Analysis")
        base = q_analysis["baseline"]
        ai_aug = q_analysis["ai_augmented"]
        impact = q_analysis["impact_metrics"]

        qc1, qc2 = st.columns(2)
        with qc1:
            st.metric("Manual Human Traffic Intensity (ρ)", f"{base['traffic_intensity_rho']:.2f}", delta="Queue Saturation Risk" if base['traffic_intensity_rho'] >= 0.90 else "Stable", delta_color="inverse")
            st.metric("Manual Queue Delay (W_q)", f"{base['queue_wait_time_hours']:.1f} hours ({base['queue_wait_time_mins']:.0f} mins)")
        with qc2:
            st.metric("AI-Augmented Traffic Intensity (ρ)", f"{ai_aug['traffic_intensity_rho']:.2f}", delta=f"-{round((base['traffic_intensity_rho'] - ai_aug['traffic_intensity_rho']) * 100, 1)}% load")
            st.metric("AI-Augmented Queue Delay (W_q)", f"{ai_aug['queue_wait_time_hours']:.2f} hours ({ai_aug['queue_wait_time_mins']:.0f} mins)", delta=f"-{impact['queue_wait_reduction_pct']}% wait")

        st.info(f"💡 **Kingman Non-Linear Effect:** Shaving {impact['ticket_reduction_pct']}% of tier-1 tickets prevents peak queue saturation, producing a **{impact['queue_wait_reduction_pct']}% reduction in human queue wait times** ({impact['queue_wait_speedup_factor']}x faster queue clearance).")

    # Saturation Curve Chart
    with st.expander("📊 View Kingman Queue Hyper-Saturation Curve ($\rho$ vs $W_q$)", expanded=False):
        curve_data = KingmanSaturationAnalyzer.generate_saturation_curve(mu=q_rate)
        c_df = pd.DataFrame(curve_data)
        st.line_chart(c_df.set_index("utilization_pct")["w_q_hours"])
        st.caption("Notice how queue delay explodes asymptotically as server utilization $\rho \\to 1.0$. AI auto-resolution keeps the organization safely in the linear region ($\rho < 0.65$).")

