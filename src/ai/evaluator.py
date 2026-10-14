"""Comparative evaluation framework benchmarking Rules baseline against AI triage."""
import time
from typing import List, Dict, Any, Tuple, Optional
from .classifier import AITriageClassifier
from .schemas import EvaluationMetrics
from ..automation.rules_engine import RulesEngine
from ..simulation.generator import generate_synthetic_ticket


class EvaluationRunner:
    """Runs automated benchmark evaluation comparing Rule-based vs AI-based triage."""

    def __init__(
        self,
        classifier: Optional[AITriageClassifier] = None,
        rules_engine: Optional[RulesEngine] = None,
    ):
        self.classifier = classifier or AITriageClassifier()
        self.rules_engine = rules_engine or RulesEngine()

    def run_benchmark(self, sample_size: int = 100, seed: int = 42) -> EvaluationMetrics:
        """Run comparative evaluation on synthetic tickets with known ground truth."""
        test_samples: List[Dict[str, Any]] = [
            generate_synthetic_ticket(seed=seed + i) for i in range(sample_size)
        ]

        rule_correct = 0
        ai_correct = 0
        rule_latencies = []
        ai_latencies = []
        high_confidence_count = 0
        human_review_count = 0

        cat_counts: Dict[str, Dict[str, int]] = {}

        for sample in test_samples:
            ground_truth_group = sample["assignment_group"]
            ground_truth_cat = sample["category"]

            if ground_truth_cat not in cat_counts:
                cat_counts[ground_truth_cat] = {"total": 0, "rule_correct": 0, "ai_correct": 0}
            cat_counts[ground_truth_cat]["total"] += 1

            # 1. Evaluate Rule Engine
            t0 = time.time()
            rule_out = self.rules_engine.evaluate_routing(sample)
            rule_latencies.append((time.time() - t0) * 1000)

            if rule_out["assignment_group"] == ground_truth_group:
                rule_correct += 1
                cat_counts[ground_truth_cat]["rule_correct"] += 1

            # 2. Evaluate AI Classifier
            t1 = time.time()
            ai_out = self.classifier.triage_ticket(
                title=sample["title"],
                description=sample["description"],
                caller_email=sample["caller_email"],
                ticket_id=sample["id"],
            )
            ai_latencies.append((time.time() - t1) * 1000)

            if ai_out.assignment_group == ground_truth_group:
                ai_correct += 1
                cat_counts[ground_truth_cat]["ai_correct"] += 1

            if ai_out.confidence_score >= 0.80:
                high_confidence_count += 1
            if ai_out.requires_human_review:
                human_review_count += 1

        rule_acc = round(rule_correct / sample_size, 4)
        ai_acc = round(ai_correct / sample_size, 4)
        imp_pct = round(((ai_acc - rule_acc) / max(0.01, rule_acc)) * 100, 2)

        cat_metrics: Dict[str, Dict[str, float]] = {}
        for cat, data in cat_counts.items():
            tot = max(1, data["total"])
            cat_metrics[cat] = {
                "rule_acc": round(data["rule_correct"] / tot, 3),
                "ai_acc": round(data["ai_correct"] / tot, 3),
            }

        return EvaluationMetrics(
            total_samples=sample_size,
            rule_accuracy=rule_acc,
            ai_accuracy=ai_acc,
            accuracy_improvement_pct=imp_pct,
            rule_avg_latency_ms=round(sum(rule_latencies) / len(rule_latencies), 2),
            ai_avg_latency_ms=round(sum(ai_latencies) / len(ai_latencies), 2),
            high_confidence_rate=round(high_confidence_count / sample_size, 3),
            human_escalation_rate=round(human_review_count / sample_size, 3),
            category_metrics=cat_metrics,
        )
