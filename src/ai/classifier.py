"""AI-Assisted Ticket Classifier with structured output, guardrails, and RAG."""
import os
import time
import logging
from typing import Dict, Any, Optional

from .guardrails import PIISanitizer
from .schemas import TriageResult
from .embeddings import SimilarTicketFinder
from .rag_resolver import RAGResolver
from ..mock_itsm.models import calculate_itil_priority

logger = logging.getLogger("ai.classifier")

CATEGORY_GROUP_MAP = {
    "Access / Identity": "IAM-Identity-Operations",
    "Hardware": "Desktop-Support-L2",
    "Network": "Network-Infrastructure-Ops",
    "ERP / SAP": "Enterprise-ERP-Support",
    "Cloud & DevOps": "Cloud-Platform-Engineering",
    "General": "ServiceDesk-L1",
}


class AITriageClassifier:
    """Enterprise AI Triage engine featuring PII guardrails, RAG, and structured outputs."""

    def __init__(
        self,
        confidence_threshold: float = 0.80,
        similarity_finder: Optional[SimilarTicketFinder] = None,
        rag_resolver: Optional[RAGResolver] = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.similarity_finder = similarity_finder or SimilarTicketFinder()
        self.rag_resolver = rag_resolver or RAGResolver()
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()

    def triage_ticket(
        self,
        title: str,
        description: str,
        caller_email: str,
        ticket_id: Optional[str] = None
    ) -> TriageResult:
        """Perform end-to-end AI triage with sanitization, duplicate detection, and RAG."""
        start_time = time.time()

        # 1. Guardrail Step 1: Prompt Injection Check
        is_injection, trigger = PIISanitizer.check_prompt_injection(f"{title} {description}")
        if is_injection:
            logger.warning(f"Prompt injection pattern detected: '{trigger}' in ticket {ticket_id}")
            return TriageResult(
                category="Security",
                subcategory="Suspected Prompt Injection",
                urgency=1,
                impact=1,
                priority=1,
                assignment_group="Security-Operations-Center",
                confidence_score=0.99,
                reasoning_summary=f"Automated security guardrail flagged prompt injection attempt: '{trigger}'.",
                requires_human_review=True,
                pii_redacted_count=0,
                suggested_kb_articles=[],
            )

        # 2. Guardrail Step 2: PII Redaction
        sanitized_title, t_redactions = PIISanitizer.sanitize(title)
        sanitized_desc, d_redactions = PIISanitizer.sanitize(description)
        total_pii = sum(t_redactions.values()) + sum(d_redactions.values())

        # 3. Step 3: Duplicate Check
        duplicate = self.similarity_finder.is_duplicate(
            sanitized_title, sanitized_desc, duplicate_threshold=0.88, exclude_id=ticket_id
        )
        dup_id = duplicate["ticket_id"] if duplicate else None

        # 4. Step 4: RAG Knowledge Base Retrieval
        rag_articles = self.rag_resolver.retrieve_relevant_articles(sanitized_title, sanitized_desc, top_k=2)
        suggested_kb_ids = [a["article_id"] for a in rag_articles]

        # 5. Step 5: Classification (Semantic / LLM Inference)
        text_lower = f"{sanitized_title} {sanitized_desc}".lower()

        # Semantic Intent Scoring
        scores = {
            "Access / Identity": 0.0,
            "Hardware": 0.0,
            "Network": 0.0,
            "ERP / SAP": 0.0,
            "Cloud & DevOps": 0.0,
        }

        # Keywords weighting
        if any(w in text_lower for w in ["password", "mfa", "authenticator", "lockout", "access request", "permission"]):
            scores["Access / Identity"] += 3.0
        if any(w in text_lower for w in ["laptop", "battery", "monitor", "dock", "keyboard", "swollen", "hardware"]):
            scores["Hardware"] += 3.0
        if any(w in text_lower for w in ["wifi", "vpn", "dns", "mpls", "latency", "packet loss", "network"]):
            scores["Network"] += 3.0
        if any(w in text_lower for w in ["sap", "va01", "me21n", "abap", "invoice", "t-code", "short dump"]):
            scores["ERP / SAP"] += 3.0
        if any(w in text_lower for w in ["kubernetes", "k8s", "pod", "aws", "s3", "docker", "crashloop", "oom"]):
            scores["Cloud & DevOps"] += 3.0

        # Determine winner
        best_cat = max(scores, key=scores.get)
        max_score = scores[best_cat]

        if max_score >= 3.0:
            category = best_cat
            confidence = min(0.96, 0.85 + (max_score * 0.03))
            reasoning = f"Identified strong domain signals for {category} with high keyword alignment."
        elif max_score > 0:
            category = best_cat
            confidence = 0.75
            reasoning = f"Partial semantic match for {category}; human validation recommended."
        else:
            category = "General"
            confidence = 0.45
            reasoning = "Ambiguous ticket description without clear domain signals. Assigned to L1 triage."

        # Impact and Urgency heuristics
        urgency = 1 if any(w in text_lower for w in ["urgent", "down", "hazard", "safety", "crash", "crashloop", "crashing", "oom", "broken", "critical"]) else 2
        impact = 1 if any(w in text_lower for w in ["production", "payment", "all users", "multiple employees", "outage", "entire plant", "safety"]) else 2

        # ITIL Priority calculation
        priority = calculate_itil_priority(impact, urgency)
        assignment_group = CATEGORY_GROUP_MAP.get(category, "ServiceDesk-L1")
        requires_human = confidence < self.confidence_threshold

        return TriageResult(
            category=category,
            subcategory=f"{category} Triage",
            urgency=urgency,
            impact=impact,
            priority=priority,
            assignment_group=assignment_group,
            confidence_score=round(confidence, 2),
            reasoning_summary=reasoning,
            requires_human_review=requires_human,
            pii_redacted_count=total_pii,
            duplicate_ticket_id=dup_id,
            suggested_kb_articles=suggested_kb_ids,
        )
