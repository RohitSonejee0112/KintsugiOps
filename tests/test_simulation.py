"""Unit tests for Discrete-Event Simulation Runner."""
import pytest
from src.simulation.simulator import SimulationRunner, SimulationKPIs


def test_simulation_runner_kpis():
    runner = SimulationRunner(seed=123)
    kpis = runner.run_simulation(ticket_count=200, manual_triage_mean_hours=4.0)

    assert isinstance(kpis, SimulationKPIs)
    assert kpis.ticket_count == 200

    # MTTA: Manual should be hours, AI should be seconds/near zero
    assert kpis.mtta_baseline_hours > 1.0
    assert kpis.mtta_treatment_hours < 0.1
    assert kpis.mtta_reduction_pct > 95.0

    # MTTR: Significant reduction due to instant triage + auto-resolution runbooks
    assert kpis.mttr_baseline_hours > kpis.mttr_treatment_hours
    assert kpis.mttr_reduction_pct > 50.0

    # SLA Compliance: Treatment should outperform baseline
    assert kpis.sla_compliance_treatment_pct >= kpis.sla_compliance_baseline_pct

    # Auto-resolution: Runbooks resolve ~30-40% of standard tickets
    assert 20.0 <= kpis.auto_resolved_pct <= 50.0

    # Misrouting: AI accuracy is higher than manual triage
    assert kpis.misrouting_treatment_pct < kpis.misrouting_baseline_pct

    # Labor Savings
    assert kpis.technician_hours_saved > 0
