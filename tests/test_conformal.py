"""Unit tests for Split Conformal Prediction and Temperature Scaling."""
import pytest
from src.ai.conformal import (
    SplitConformalClassifier,
    TemperatureScaler,
    CALIBRATION_BENCHMARK,
)
from src.ai.classifier import AITriageClassifier


def test_temperature_scaling():
    """Verify TemperatureScaler smooths overconfident logits."""
    scaler = TemperatureScaler(temperature=1.5)
    raw_scores = {"Access / Identity": 6.0, "Hardware": 2.0, "Network": 1.0}

    scaled_probs = scaler.scale_probabilities(raw_scores)

    # Probabilities must sum to ~1.0
    assert abs(sum(scaled_probs.values()) - 1.0) < 0.01
    assert scaled_probs["Access / Identity"] > scaled_probs["Hardware"]
    # With T=1.5, top category shouldn't be 0.9999 overconfident
    assert scaled_probs["Access / Identity"] < 0.98


def test_conformal_classifier_calibration():
    """Verify SplitConformalClassifier calibrates quantile q_hat on benchmark."""
    clf = SplitConformalClassifier(alpha=0.05)
    assert clf.is_calibrated is True
    assert 0.0 < clf.q_hat < 1.0
    assert len(clf.calibration_scores) == len(CALIBRATION_BENCHMARK)


def test_conformal_prediction_singleton_runbook_safe():
    """Verify that clear domain tickets yield a singleton conformal set guaranteeing <=1% error."""
    clf = SplitConformalClassifier(alpha=0.05)
    # Clear password reset signals
    scores = {
        "Access / Identity": 8.5,
        "Hardware": 0.5,
        "Network": 0.2,
        "ERP / SAP": 0.1,
        "Cloud & DevOps": 0.1,
    }

    res = clf.predict_conformal_set(scores)

    assert res.set_size == 1
    assert res.prediction_set == ["Access / Identity"]
    assert res.guaranteed_safe_execution is True
    assert res.recommended_action == "auto_resolve_runbook"
    assert "Singleton Conformal Set" in res.explanation


def test_conformal_prediction_ambiguity_hitl_fallback():
    """Verify that ambiguous tickets between multiple categories produce multi-class set and route to HITL."""
    clf = SplitConformalClassifier(alpha=0.05)
    # Ambiguous ticket with close scores between Hardware and Network
    scores = {
        "Hardware": 3.8,
        "Network": 3.6,
        "Access / Identity": 0.5,
        "ERP / SAP": 0.2,
        "Cloud & DevOps": 0.1,
    }

    res = clf.predict_conformal_set(scores)

    assert res.set_size >= 2
    assert "Hardware" in res.prediction_set
    assert "Network" in res.prediction_set
    assert res.guaranteed_safe_execution is False
    assert res.recommended_action == "human_triage"
    assert "Multi-Class Conformal Set" in res.explanation


def test_classifier_end_to_end_conformal():
    """Verify AITriageClassifier attaches conformal prediction set and guarantee status."""
    classifier = AITriageClassifier()

    # Clear ticket
    res = classifier.triage_ticket(
        title="Domain password reset required for user",
        description="Account locked out after multiple failed Active Directory login attempts",
        caller_email="test@corp.com",
        ticket_id="INC5001"
    )

    assert res.category == "Access / Identity"
    assert "Access / Identity" in res.conformal_set
    assert res.conformal_guaranteed is True
    assert res.conformal_p_value is not None
