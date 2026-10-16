"""Unit tests for Queueing Theory Realism: Non-Homogeneous Poisson and Kingman Saturation."""
import pytest
from src.simulation.queueing_model import (
    NonHomogeneousPoissonProcess,
    KingmanSaturationAnalyzer,
    DiscreteEventQueueSimulator,
)


def test_non_homogeneous_poisson_bursts():
    """Verify that arrival process produces higher traffic during Monday morning peak."""
    process = NonHomogeneousPoissonProcess(base_lambda_per_hour=20.0, seed=123)

    # Monday 9:00 AM (hour 9) vs Sunday 3:00 AM (hour 147)
    mult_monday_peak = process.get_intensity_multiplier(9.0)
    mult_weekend_night = process.get_intensity_multiplier(147.0)

    assert mult_monday_peak > 2.0
    assert mult_weekend_night < 0.3
    assert mult_monday_peak > (mult_weekend_night * 5.0)

    # Generate 48 hours of arrivals
    arrivals = process.generate_arrivals(simulation_hours=48.0)
    assert len(arrivals) > 0
    # Arrivals must be sorted strictly ascending
    assert all(arrivals[i] <= arrivals[i+1] for i in range(len(arrivals) - 1))


def test_kingman_formula_hyper_saturation():
    """Verify that Kingman's formula models non-linear queue explosion as rho approaches 1.0."""
    mu = 2.5
    # Compare rho = 0.50 vs rho = 0.95
    w_q_50 = KingmanSaturationAnalyzer.calculate_waiting_time(rho=0.50, mu=mu)
    w_q_95 = KingmanSaturationAnalyzer.calculate_waiting_time(rho=0.95, mu=mu)

    # Kingman non-linearity: rho/(1-rho) is 1.0 for 0.50, but 19.0 for 0.95
    assert w_q_95 > (w_q_50 * 15.0)

    # Saturated boundary condition
    w_q_max = KingmanSaturationAnalyzer.calculate_waiting_time(rho=0.999, mu=mu)
    assert w_q_max >= 900.0


def test_kingman_human_vs_ai_comparison():
    """Verify comparative metrics proving non-linear MTTR reduction."""
    comp = KingmanSaturationAnalyzer.compare_human_vs_ai(
        base_arrival_rate=23.5,
        agent_count=10,
        agent_service_rate=2.5,
        ai_auto_resolution_rate=0.382
    )

    baseline = comp["baseline"]
    ai = comp["ai_augmented"]
    impact = comp["impact_metrics"]

    assert baseline["traffic_intensity_rho"] > 0.90
    assert ai["traffic_intensity_rho"] < 0.65
    # Shaving 38.2% of tickets must yield > 70% wait time reduction due to Kingman effect
    assert impact["queue_wait_reduction_pct"] > 70.0
    assert impact["queue_wait_speedup_factor"] > 3.0


def test_discrete_event_queue_simulation():
    """Verify paired discrete-event queue simulation runs and demonstrates AI backlog stabilization."""
    sim = DiscreteEventQueueSimulator(agent_count=8, mean_service_hours=0.35, ai_auto_resolution_rate=0.35, seed=42)
    res = sim.run_simulation(total_hours=72.0, base_lambda=18.0)

    assert "baseline" in res
    assert "ai_augmented" in res
    assert "comparative_roi" in res

    base_stats = res["baseline"]
    ai_stats = res["ai_augmented"]

    assert ai_stats["avg_wait_hours"] < base_stats["avg_wait_hours"]
    assert ai_stats["peak_queue_length"] <= base_stats["peak_queue_length"]
    assert res["comparative_roi"]["wait_reduction_pct"] > 40.0
