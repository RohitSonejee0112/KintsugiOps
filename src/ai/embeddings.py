"""Vector embeddings and cosine similarity for duplicate and similar ticket detection."""
import re
import math
from typing import List, Tuple, Dict, Optional, Any
from collections import Counter


class VectorEmbeddingEngine:
    """Lightweight, deterministic vector embedding engine using normalized subword n-grams.

    Generates dense L2-normalized embedding vectors for fast, zero-dependency cosine similarity.
    """

    def __init__(self, vector_dim: int = 256):
        self.vector_dim = vector_dim

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
        tokens = list(words)
        # Add character tri-grams for typo resilience
        for word in words:
            if len(word) >= 4:
                for i in range(len(word) - 2):
                    tokens.append(word[i:i+3])
        return tokens

    def get_embedding(self, text: str) -> List[float]:
        """Compute normalized dense embedding vector for text."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.vector_dim

        counts = Counter(tokens)
        vec = [0.0] * self.vector_dim

        for token, count in counts.items():
            # Hash token into vector index deterministically
            idx = hash(token) % self.vector_dim
            weight = math.log1p(count)
            vec[idx] += weight

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two normalized vectors (dot product)."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        return max(0.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))


class SimilarTicketFinder:
    """Indexes tickets and queries for duplicates and similar resolved cases."""

    def __init__(self, engine: Optional[VectorEmbeddingEngine] = None):
        self.engine = engine or VectorEmbeddingEngine()
        self.index: Dict[str, Tuple[List[float], Dict[str, str]]] = {}

    def index_ticket(self, ticket_id: str, title: str, description: str, metadata: Optional[Dict[str, str]] = None) -> None:
        """Add a ticket to the similarity vector index."""
        text = f"{title} {description}"
        vector = self.engine.get_embedding(text)
        self.index[ticket_id] = (vector, metadata or {"title": title})

    def find_similar(
        self,
        title: str,
        description: str,
        top_k: int = 3,
        threshold: float = 0.50,
        exclude_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find top-k most similar tickets above threshold."""
        query_text = f"{title} {description}"
        query_vec = self.engine.get_embedding(query_text)

        scored: List[Tuple[float, str, Dict[str, str]]] = []
        for t_id, (v, meta) in self.index.items():
            if exclude_id and t_id == exclude_id:
                continue
            sim = self.engine.cosine_similarity(query_vec, v)
            if sim >= threshold:
                scored.append((sim, t_id, meta))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for sim, t_id, meta in scored[:top_k]:
            results.append({
                "ticket_id": t_id,
                "similarity_score": round(sim, 3),
                "metadata": meta,
            })
        return results

    def is_duplicate(
        self,
        title: str,
        description: str,
        duplicate_threshold: float = 0.85,
        exclude_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Check if ticket is an exact or near duplicate of an existing ticket."""
        similar = self.find_similar(title, description, top_k=1, threshold=duplicate_threshold, exclude_id=exclude_id)
        return similar[0] if similar else None
