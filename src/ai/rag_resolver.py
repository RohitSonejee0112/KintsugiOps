"""RAG-based Knowledge Base retrieval for automated resolution suggestions."""
from typing import List, Dict, Any, Optional
from .embeddings import VectorEmbeddingEngine, SimilarTicketFinder

DEFAULT_KNOWLEDGE_BASE = [
    {
        "id": "KB00101",
        "title": "Resolving SAP GUI short dump SYSTEM_NO_MORE_PAGING",
        "category": "ERP / SAP",
        "summary": "Occurs when SAP background job or dialog session exceeds roll area / swap memory.",
        "steps": "1. Check SM21 system log. 2. Verify instance profile parameter 'rdisp/ROLL_MAX'. 3. Clean stale session locks in SM12.",
    },
    {
        "id": "KB00102",
        "title": "Remediating GlobalProtect VPN Split-Tunneling and Certificate Failures",
        "category": "Network",
        "summary": "Fixes connection drops and 'Certificate Invalid' errors for remote workers.",
        "steps": "1. Open Certificate Manager (certmgr.msc). 2. Renew root corporate CA. 3. Re-install gateway profile in GlobalProtect settings.",
    },
    {
        "id": "KB00103",
        "title": "Standard Active Directory Account Unlock & Self-Service Reset",
        "category": "Access / Identity",
        "summary": "Handles user lockouts resulting from expired cached credentials on mobile devices.",
        "steps": "1. Verify caller identity via Duo/SMS. 2. In AD Users & Computers, check 'Unlock Account'. 3. Remind user to update Wi-Fi saved password.",
    },
    {
        "id": "KB00104",
        "title": "Resolving Kubernetes OOMKilled Pods (Exit Code 137)",
        "category": "Cloud & DevOps",
        "summary": "Container terminated because it exceeded memory limit specified in pod spec.",
        "steps": "1. Run kubectl describe pod to inspect termination message. 2. Check Prometheus memory usage trends. 3. Increase resources.limits.memory in Helm values.",
    },
    {
        "id": "KB00105",
        "title": "Dell USB-C DisplayLink Dock Video Sync & Flickering",
        "category": "Hardware",
        "summary": "Intermittent HDMI/DisplayPort blackout caused by outdated DisplayLink firmware.",
        "steps": "1. Unplug dock power for 30 seconds. 2. Update Dell Dock WD19/WD22 firmware via SupportAssist. 3. Update Intel Graphics driver.",
    },
]


class RAGResolver:
    """Retrieval-Augmented Generation resolver searching knowledge base articles."""

    def __init__(self, kb_data: Optional[List[Dict[str, Any]]] = None):
        self.kb_articles = kb_data or DEFAULT_KNOWLEDGE_BASE
        self.finder = SimilarTicketFinder()
        self._index_kb()

    def _index_kb(self) -> None:
        for doc in self.kb_articles:
            content = f"{doc['title']} {doc['summary']} {doc['steps']}"
            self.finder.index_ticket(
                ticket_id=doc["id"],
                title=doc["title"],
                description=content,
                metadata=doc
            )

    def retrieve_relevant_articles(self, title: str, description: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Retrieve the most relevant knowledge base articles for a ticket."""
        matches = self.finder.find_similar(title, description, top_k=top_k, threshold=0.15)
        results = []
        for m in matches:
            results.append({
                "article_id": m["ticket_id"],
                "relevance_score": m["similarity_score"],
                "article": m["metadata"],
            })
        return results
