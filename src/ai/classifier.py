"""AI-Assisted Ticket Classifier with structured output, guardrails, and RAG."""
import os
import time
import logging
from typing import Dict, Any, Optional

from .guardrails import PIISanitizer
from .schemas import TriageResult
from .embeddings import SimilarTicketFinder, VectorEmbeddingEngine
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

CATEGORY_SIGNALS = {
    "Access / Identity": {
        "primary": ["password", "mfa", "authenticator", "lockout", "account locked", "active directory", "permission", "access request", "user grant"],
        "secondary": ["token", "login", "reset", "unlock", "domain", "credentials", "okta", "azuread", "sso"],
        "prototype": "user password reset forgot credentials account locked active directory mfa authenticator mobile token permission access request",
    },
    "Hardware": {
        "primary": ["laptop", "battery", "monitor", "dock", "displaylink", "keyboard", "chassis", "swollen", "trackpad", "screen", "headset"],
        "secondary": ["hardware", "broken", "flickering", "unresponsive", "replacement", "dell", "lenovo", "cable", "port", "usb-c"],
        "prototype": "laptop battery swollen trackpad keyboard broken key monitor flickering dock displaylink hardware replacement dell lenovo",
    },
    "Network": {
        "primary": ["wifi", "vpn", "dns", "mpls", "latency", "packet loss", "globalprotect", "firewall", "switch", "router", "bandwidth"],
        "secondary": ["network", "timeout", "disconnected", "gateway", "unreachable", "ping", "subnet", "ap", "5ghz", "802.1x"],
        "prototype": "wifi wireless connection drop vpn globalprotect dns resolution latency packet loss mpls network portal switch router firewall",
    },
    "ERP / SAP": {
        "primary": ["sap", "va01", "me21n", "abap", "short dump", "t-code", "purchase order", "sales order", "invoice", "system_no_more_paging"],
        "secondary": ["erp", "posting", "procurement", "authorization", "role", "batch job", "transaction", "mm", "sd", "fi"],
        "prototype": "sap gui transaction va01 me21n short dump abap purchase order invoice batch job role authorization erp financial",
    },
    "Cloud & DevOps": {
        "primary": ["kubernetes", "k8s", "pod", "aws", "s3", "docker", "crashloopbackoff", "crashloop", "oomkilled", "github actions", "pipeline", "ci/cd"],
        "secondary": ["cloud", "container", "runner", "iam role", "access denied", "403", "cluster", "helm", "devops", "vpc", "subnet"],
        "prototype": "kubernetes k8s pod crashloopbackoff oomkilled aws s3 access denied docker container ci cd github actions runner cloud pipeline",
    },
}


class AITriageClassifier:
    """Enterprise AI Triage engine featuring PII guardrails, RAG, and structured outputs."""

    def __init__(
        self,
        confidence_threshold: float = 0.80,
        similarity_finder: Optional[SimilarTicketFinder] = None,
        rag_resolver: Optional[RAGResolver] = None,
        embedding_engine: Optional[VectorEmbeddingEngine] = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.similarity_finder = similarity_finder or SimilarTicketFinder()
        self.rag_resolver = rag_resolver or RAGResolver()
        self.embedding_engine = embedding_engine or VectorEmbeddingEngine()
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()

        # Precompute category prototype embeddings
        self.category_prototypes = {
            cat: self.embedding_engine.get_embedding(cfg["prototype"])
            for cat, cfg in CATEGORY_SIGNALS.items()
        }

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

        # 5. Step 5: Multi-Signal Semantic & Prototype Vector Scoring
        text_lower = f"{sanitized_title} {sanitized_desc}".lower()
        ticket_vec = self.embedding_engine.get_embedding(f"{sanitized_title} {sanitized_desc}")

        category_scores: Dict[str, float] = {}
        matched_details: Dict[str, Dict[str, Any]] = {}

        for cat, cfg in CATEGORY_SIGNALS.items():
            primary_hits = sum(1 for w in cfg["primary"] if w in text_lower)
            secondary_hits = sum(1 for w in cfg["secondary"] if w in text_lower)
            proto_sim = self.embedding_engine.cosine_similarity(ticket_vec, self.category_prototypes[cat])

            # Composite evidence: weighted keywords + cosine prototype similarity
            score = (primary_hits * 1.8) + (secondary_hits * 0.7) + (proto_sim * 2.8)
            category_scores[cat] = score
            matched_details[cat] = {
                "primary": primary_hits,
                "secondary": secondary_hits,
                "sim": proto_sim,
            }

        sorted_cats = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        top_cat, top_score = sorted_cats[0]
        runner_up_cat, runner_up_score = sorted_cats[1]
        margin = max(0.0, top_score - runner_up_score)

        if top_score < 1.2:
            category = "General"
            confidence = round(0.40 + min(0.18, top_score * 0.1), 2)
            reasoning = "Ambiguous ticket description without clear domain signals. Assigned to L1 triage."
        else:
            category = top_cat
            # Continuous baseline confidence derived from evidence strength
            base_conf = 0.66 + min(0.20, (top_score / 6.5) * 0.20)
            # Margin bonus: distinct winner over second place boosts confidence up to +0.08
            margin_bonus = min(0.08, (margin / 3.5) * 0.08)
            # RAG bonus: if relevant KB article category confirms classification, +0.03
            rag_bonus = 0.03 if (rag_articles and rag_articles[0].get("article", {}).get("category") == category) else 0.0

            raw_conf = min(0.97, base_conf + margin_bonus + rag_bonus)
            confidence = round(raw_conf, 2)
            reasoning = (
                f"Classified into '{category}' (evidence score: {top_score:.1f}, "
                f"semantic match: {int(matched_details[top_cat]['sim'] * 100)}%, "
                f"margin: +{margin:.1f})."
            )

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
