"""Vector-based Semantic Caching and Outage Incident Storm Clustering.

Recognizes near-duplicate incoming tickets within a sliding time window (e.g. 30 min),
bypasses redundant LLM inference calls, and automatically clusters child tickets under
a single master outage incident.
"""
import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone, timedelta

from .schemas import TriageResult
from .embeddings import VectorEmbeddingEngine

logger = logging.getLogger("ai.semantic_cache")


class CachedIncidentEntry:
    """Represents a cached triage decision and incident storm cluster."""

    def __init__(
        self,
        entry_id: str,
        master_ticket_id: str,
        title: str,
        description: str,
        embedding: List[float],
        triage_result: TriageResult,
        created_at: Optional[datetime] = None,
    ):
        self.entry_id = entry_id
        self.master_ticket_id = master_ticket_id
        self.title = title
        self.description = description
        self.embedding = embedding
        self.triage_result = triage_result
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_hit_at = self.created_at
        self.child_ticket_ids: List[str] = []
        self.hit_count = 0
        self.is_storm = False

    def register_hit(self, child_id: Optional[str] = None, hit_time: Optional[datetime] = None) -> None:
        """Register a cache hit, link child ticket, and update storm status."""
        self.hit_count += 1
        self.last_hit_at = hit_time or datetime.now(timezone.utc)
        if child_id and child_id not in self.child_ticket_ids and child_id != self.master_ticket_id:
            self.child_ticket_ids.append(child_id)


class SemanticCache:
    """Sliding-window semantic cache and incident storm cluster engine."""

    def __init__(
        self,
        similarity_threshold: float = 0.62,
        sliding_window_seconds: int = 1800,  # 30-minute outage storm window
        storm_threshold: int = 3,            # 3 near-duplicates triggers Incident Storm
        cost_per_inference_usd: float = 0.003,
        embedding_engine: Optional[VectorEmbeddingEngine] = None,
    ):
        self.similarity_threshold = similarity_threshold
        self.sliding_window_seconds = sliding_window_seconds
        self.storm_threshold = storm_threshold
        self.cost_per_inference_usd = cost_per_inference_usd
        self.embedding_engine = embedding_engine or VectorEmbeddingEngine()

        self.entries: Dict[str, CachedIncidentEntry] = {}
        self.total_lookups = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _normalize_text(self, title: str, description: str) -> str:
        return f"{title} {description}".strip()

    def lookup(
        self,
        title: str,
        description: str,
        incoming_ticket_id: Optional[str] = None,
        now: Optional[datetime] = None
    ) -> Optional[Tuple[TriageResult, CachedIncidentEntry]]:
        """Query semantic cache for near-duplicate tickets within the sliding time window.

        Returns (cached_triage_result, cached_entry) on hit, or None on miss.
        """
        self.total_lookups += 1
        current_time = now or datetime.now(timezone.utc)
        query_text = self._normalize_text(title, description)
        query_vec = self.embedding_engine.get_embedding(query_text)

        best_entry: Optional[CachedIncidentEntry] = None
        best_similarity = 0.0

        # Purge or skip expired entries outside sliding window
        window_delta = timedelta(seconds=self.sliding_window_seconds)

        for entry_id, entry in list(self.entries.items()):
            # Check if entry is within active sliding window
            if current_time - entry.last_hit_at > window_delta:
                continue

            sim = self.embedding_engine.cosine_similarity(query_vec, entry.embedding)
            if sim >= self.similarity_threshold and sim > best_similarity:
                best_similarity = sim
                best_entry = entry

        if best_entry is not None:
            self.cache_hits += 1
            best_entry.register_hit(child_id=incoming_ticket_id, hit_time=current_time)

            # Elevate to storm if hit count reaches threshold
            if (best_entry.hit_count + 1) >= self.storm_threshold:
                best_entry.is_storm = True

            # Clone triage result with cache and storm metadata
            result_dict = best_entry.triage_result.model_dump()
            result_dict.update({
                "cache_hit": True,
                "is_storm_incident": best_entry.is_storm,
                "master_incident_id": best_entry.master_ticket_id,
                "duplicate_ticket_id": best_entry.master_ticket_id,
                "reasoning_summary": (
                    f"⚡ [Semantic Cache Hit - Cosine Match: {int(best_similarity * 100)}%] "
                    f"Resolved via cached Master Incident #{best_entry.master_ticket_id}. "
                    f"{'⚠️ ACTIVE OUTAGE INCIDENT STORM DETECTED.' if best_entry.is_storm else ''}"
                ),
            })
            cloned_result = TriageResult(**result_dict)
            return cloned_result, best_entry

        self.cache_misses += 1
        return None

    def store(
        self,
        ticket_id: str,
        title: str,
        description: str,
        triage_result: TriageResult,
        now: Optional[datetime] = None
    ) -> CachedIncidentEntry:
        """Store fresh triage result in cache as a potential Master Incident."""
        current_time = now or datetime.now(timezone.utc)
        text = self._normalize_text(title, description)
        vec = self.embedding_engine.get_embedding(text)

        entry = CachedIncidentEntry(
            entry_id=f"cache_{ticket_id}",
            master_ticket_id=ticket_id,
            title=title,
            description=description,
            embedding=vec,
            triage_result=triage_result,
            created_at=current_time,
        )
        self.entries[entry.entry_id] = entry
        return entry

    def get_active_storms(self) -> List[Dict[str, Any]]:
        """Retrieve all active outage incident storms with child ticket clusters."""
        storms = []
        for entry in self.entries.values():
            if entry.is_storm:
                storms.append({
                    "master_incident_id": entry.master_ticket_id,
                    "title": entry.title,
                    "category": entry.triage_result.category,
                    "total_storm_tickets": entry.hit_count + 1,
                    "child_ticket_ids": list(entry.child_ticket_ids),
                    "created_at": entry.created_at.isoformat(),
                    "last_hit_at": entry.last_hit_at.isoformat(),
                })
        storms.sort(key=lambda s: s["total_storm_tickets"], reverse=True)
        return storms

    def get_metrics(self) -> Dict[str, Any]:
        """Compute operational metrics: hit rate, active storms, and token cost savings."""
        hit_rate = round((self.cache_hits / max(1, self.total_lookups)) * 100, 1)
        cost_saved = round(self.cache_hits * self.cost_per_inference_usd, 4)
        active_storms = sum(1 for e in self.entries.values() if e.is_storm)

        return {
            "total_lookups": self.total_lookups,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate_pct": hit_rate,
            "active_storms_count": active_storms,
            "cost_saved_usd": cost_saved,
            "inference_calls_saved": self.cache_hits,
        }

    def clear(self) -> None:
        """Clear all cache entries and reset counters."""
        self.entries.clear()
        self.total_lookups = 0
        self.cache_hits = 0
        self.cache_misses = 0
