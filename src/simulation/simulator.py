"""Discrete-Event Monte Carlo simulation engine comparing Manual Baseline vs AI Treatment."""
import random
import math
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from .generator import generate_synthetic_ticket


class SimulationKPIs(BaseModel):
    """Comparative operational metrics for Manual Baseline vs AI Treatment."""
    ticket_count: int
    mtta_baseline_hours: float
    mtta_treatment_hours: float
    mtta_reduction_pct: float
    mttr_baseline_hours: float
    mttr_treatment_hours: float
    mttr_reduction_pct: float
    sla_compliance_baseline_pct: float
    sla_compliance_treatment_pct: float
    auto_resolved_pct: float
    misrouting_baseline_pct: float
    misrouting_treatment_pct: float
    technician_hours_saved: float


class SimulationRunner:
    """Simulates ticket lifecycles under manual and automated conditions."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def run_simulation(
        self,
        ticket_count: int = 1000,
        manual_triage_mean_hours: float = 3.5,
        ai_triage_seconds: float = 2.0,
        runbook_coverage_pct: float = 0.35,
    ) -> SimulationKPIs:
        """Execute discrete-event simulation comparing manual vs AI-assisted operations."""
        random.seed(self.seed)

        baseline_mtta_list = []
        treatment_mtta_list = []
        baseline_mttr_list = []
        treatment_mttr_list = []
        baseline_sla_breaches = 0
        treatment_sla_breaches = 0
        auto_resolved_count = 0
        baseline_misroutes = 0
        treatment_misroutes = 0

        # ITIL Resolution SLA targets in hours: P1=2h, P2=4h, P3=24h, P4=72h
        sla_targets = {1: 2.0, 2: 4.0, 3: 24.0, 4: 72.0}

        for i in range(ticket_count):
            ticket = generate_synthetic_ticket(seed=self.seed + i)
            priority = ticket["priority"]
            is_auto_candidate = ticket.get("auto_resolvable", False)
            sla_limit = sla_targets.get(priority, 24.0)

            # ------------------------------------------------------------------
            # 1. MANUAL BASELINE SIMULATION
            # ------------------------------------------------------------------
            # MTTA: Human triage delay follows lognormal distribution
            m_triage = max(0.2, random.lognormvariate(math.log(manual_triage_mean_hours), 0.4))
            baseline_mtta_list.append(m_triage)

            # Manual misrouting rate: ~18%
            is_misrouted_manual = random.random() < 0.18
            hops = 1
            bounce_delay = 0.0
            if is_misrouted_manual:
                baseline_misroutes += 1
                hops = random.choice([2, 3])
                bounce_delay = sum(random.uniform(3.0, 8.0) for _ in range(hops - 1))

            # Base manual work time based on priority
            work_time_manual = {
                1: random.uniform(1.0, 2.5),
                2: random.uniform(2.5, 6.0),
                3: random.uniform(8.0, 28.0),
                4: random.uniform(16.0, 60.0),
            }[priority]

            manual_total_mttr = m_triage + bounce_delay + work_time_manual
            baseline_mttr_list.append(manual_total_mttr)
            if manual_total_mttr > sla_limit:
                baseline_sla_breaches += 1

            # ------------------------------------------------------------------
            # 2. AI-AUTOMATED TREATMENT SIMULATION
            # ------------------------------------------------------------------
            # AI MTTA: instant (seconds converted to hours)
            ai_triage_hours = ai_triage_seconds / 3600.0
            treatment_mtta_list.append(ai_triage_hours)

            # If ticket matches auto-resolution runbook
            if is_auto_candidate and (random.random() < (runbook_coverage_pct / 0.35)):
                auto_resolved_count += 1
                # Auto-runbook executes in seconds (0.01 - 0.03 hours)
                auto_mttr = ai_triage_hours + random.uniform(0.01, 0.03)
                treatment_mttr_list.append(auto_mttr)
                # Auto resolution virtually never breaches SLA
            else:
                # Routed ticket
                is_misrouted_ai = random.random() < 0.04  # AI accuracy is 96%
                ai_bounce_delay = 0.0
                if is_misrouted_ai:
                    treatment_misroutes += 1
                    ai_bounce_delay = random.uniform(2.0, 4.0)

                # Queue dwell time is reduced because ticket arrives in right group immediately
                work_time_ai = {
                    1: random.uniform(0.8, 1.8),
                    2: random.uniform(1.8, 3.5),
                    3: random.uniform(4.0, 16.0),
                    4: random.uniform(10.0, 36.0),
                }[priority]

                ai_total_mttr = ai_triage_hours + ai_bounce_delay + work_time_ai
                treatment_mttr_list.append(ai_total_mttr)
                if ai_total_mttr > sla_limit:
                    treatment_sla_breaches += 1

        # Summary Metrics
        base_mtta = sum(baseline_mtta_list) / ticket_count
        treat_mtta = sum(treatment_mtta_list) / ticket_count
        mtta_red = ((base_mtta - treat_mtta) / base_mtta) * 100.0

        base_mttr = sum(baseline_mttr_list) / ticket_count
        treat_mttr = sum(treatment_mttr_list) / ticket_count
        mttr_red = ((base_mttr - treat_mttr) / base_mttr) * 100.0

        base_sla_comp = (1.0 - (baseline_sla_breaches / ticket_count)) * 100.0
        treat_sla_comp = (1.0 - (treatment_sla_breaches / ticket_count)) * 100.0

        auto_res_pct = (auto_resolved_count / ticket_count) * 100.0
        base_misroute_pct = (baseline_misroutes / ticket_count) * 100.0
        treat_misroute_pct = (treatment_misroutes / ticket_count) * 100.0

        # Technician hours saved = manual labor saved on auto-resolved tickets + triage overhead saved
        hours_saved = sum(
            baseline_mttr_list[i] - treatment_mttr_list[i] for i in range(ticket_count)
        )

        return SimulationKPIs(
            ticket_count=ticket_count,
            mtta_baseline_hours=round(base_mtta, 2),
            mtta_treatment_hours=round(treat_mtta, 4),
            mtta_reduction_pct=round(mtta_red, 1),
            mttr_baseline_hours=round(base_mttr, 2),
            mttr_treatment_hours=round(treat_mttr, 2),
            mttr_reduction_pct=round(mttr_red, 1),
            sla_compliance_baseline_pct=round(base_sla_comp, 1),
            sla_compliance_treatment_pct=round(treat_sla_comp, 1),
            auto_resolved_pct=round(auto_res_pct, 1),
            misrouting_baseline_pct=round(base_misroute_pct, 1),
            misrouting_treatment_pct=round(treat_misroute_pct, 1),
            technician_hours_saved=round(hours_saved, 1),
        )
