"""Pydantic schemas for AI triage, embeddings, and evaluation."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """Structured AI triage classification output."""
    category: str = Field(..., description="E.g., Access / Identity, Hardware, Network, ERP / SAP, Cloud & DevOps")
    subcategory: str
    urgency: int = Field(..., ge=1, le=3, description="1=High, 2=Medium, 3=Low")
    impact: int = Field(..., ge=1, le=3, description="1=High, 2=Medium, 3=Low")
    priority: int = Field(..., ge=1, le=4, description="Calculated ITIL Priority (1-4)")
    assignment_group: str = Field(..., description="Target operational team")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model classification confidence")
    reasoning_summary: str = Field(..., description="Concise justification for routing and priority")
    requires_human_review: bool = Field(False, description="Flagged if confidence is below threshold (e.g. 0.80)")
    pii_redacted_count: int = Field(0, description="Total PII tokens redacted prior to inference")
    duplicate_ticket_id: Optional[str] = Field(None, description="ID of existing similar/duplicate ticket if detected")
    suggested_kb_articles: List[str] = Field(default_factory=list, description="Relevant KB articles for resolution")


class EvaluationMetrics(BaseModel):
    """Quantitative comparison metrics between baseline rules and AI model."""
    total_samples: int
    rule_accuracy: float
    ai_accuracy: float
    accuracy_improvement_pct: float
    rule_avg_latency_ms: float
    ai_avg_latency_ms: float
    high_confidence_rate: float
    human_escalation_rate: float
    category_metrics: Dict[str, Dict[str, float]]
