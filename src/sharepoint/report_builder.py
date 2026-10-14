"""Executive Markdown and HTML report generator for Process Mining & Structural Proposals."""
from datetime import datetime, timezone
from typing import List, Dict, Any
from ..process_mining.proposal_generator import StructuralImprovementProposal


class ReportBuilder:
    """Builds formatted executive audit reports documenting operational gaps and structural proposals."""

    @staticmethod
    def build_markdown_report(
        summary: Dict[str, Any],
        bottlenecks: List[Dict[str, Any]],
        ping_pong: Dict[str, Any],
        proposals: List[StructuralImprovementProposal],
    ) -> str:
        """Generate comprehensive executive Markdown report."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        md = []
        md.append("# Executive Operational Audit: ITSM Process Mining & Structural Improvement Report\n")
        md.append(f"**Generated:** {now_str} | **Scope:** Service Management Lifecycle Optimization\n")
        md.append("---\n")

        # 1. Executive Summary
        md.append("## 1. Executive Summary\n")
        md.append(
            f"An end-to-end process mining audit was conducted across **{summary.get('total_cases', 0):,} unique ticket lifecycles** "
            f"comprising **{summary.get('total_events', 0):,} discrete state transitions**. The analysis uncovered critical operational "
            f"friction points, most notably a **{ping_pong.get('ping_pong_rate_pct', 0)}% reassignment bounce rate** and "
            f"significant dwell times during initial triage and approval stages.\n"
        )

        # 2. Key Process Metrics
        md.append("## 2. Key Process Mining Performance Indicators\n")
        md.append("| Metric | Observed Value | Industry ITIL Target | Status |")
        md.append("| :--- | :--- | :--- | :--- |")
        md.append(f"| Total Cases Analyzed | {summary.get('total_cases', 0):,} | N/A | Completed |")
        md.append(f"| Events per Case (Avg) | {summary.get('events_per_case_avg', 0)} hops | < 2.5 hops | {'⚠️ Elevating Dwell' if summary.get('events_per_case_avg', 0) > 2.5 else '✅ Optimal'} |")
        md.append(f"| Reassignment Bounce Rate | {ping_pong.get('ping_pong_rate_pct', 0)}% | < 5.0% | {'❌ Friction Detected' if ping_pong.get('ping_pong_rate_pct', 0) > 5.0 else '✅ Optimal'} |")
        md.append(f"| Ping-Pong Case Volume | {ping_pong.get('ping_pong_cases_count', 0)} cases | 0 cases | Action Required |\n")

        # 3. Transition Bottlenecks
        md.append("## 3. Transition Bottlenecks & Waiting Dwell Times\n")
        if bottlenecks:
            md.append("| Transition (Stage ➔ Stage) | Event Count | Mean Dwell (Hours) | Median (Hours) | Max Dwell (Hours) |")
            md.append("| :--- | :--- | :--- | :--- | :--- |")
            for bn in bottlenecks[:5]:
                md.append(
                    f"| `{bn['from_activity']}` ➔ `{bn['to_activity']}` | {bn['transition_count']:,} | "
                    f"**{bn['mean_duration_hours']:.1f}h** | {bn['median_duration_hours']:.1f}h | {bn['max_duration_hours']:.1f}h |"
                )
            md.append("\n")
        else:
            md.append("_No bottleneck stages detected._\n")

        # 4. Reassignment Ping-Pong Analysis
        md.append("## 4. Reassignment Ping-Pong Patterns\n")
        top_pairs = ping_pong.get("top_bouncing_pairs", [])
        if top_pairs:
            md.append("| Origin Team | Destination Team | Bounce Volume | Primary Root Cause |")
            md.append("| :--- | :--- | :--- | :--- |")
            for p in top_pairs:
                md.append(f"| **{p.get('from_group')}** | **{p.get('to_group')}** | {p.get('bounce_count')} bounces | Ambiguous Intake & Misrouting |")
            md.append("\n")

        # 5. Structural Improvement Proposals
        md.append("## 5. Structural Improvement Proposals (Synced to SharePoint Tracker)\n")
        for idx, prop in enumerate(proposals, 1):
            md.append(f"### Proposal {idx}: {prop.title} (`{prop.proposal_id}`)")
            md.append(f"- **Target Team:** `{prop.target_team}` | **Priority:** **{prop.priority}** | **Effort:** {prop.implementation_effort}")
            md.append(f"- **Problem Identified:** {prop.problem_statement}")
            md.append(f"- **Empirical Evidence:** _{prop.empirical_evidence}_")
            md.append(f"- **Proposed Structural Change:** {prop.proposed_structural_change}")
            md.append(f"- **Expected ROI / Impact:** **{prop.expected_impact}**")
            md.append(f"- **Governance Status:** `{prop.status}`\n")

        md.append("---\n")
        md.append("*Document automatically published to SharePoint Document Library via Microsoft Graph API integration.*\n")
        return "\n".join(md)
