"""Abstract TicketingProvider protocol and unified ticket data model."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class UnifiedTicket(BaseModel):
    """Normalized ticket model bridging ServiceNow and Jira Service Management schemas."""
    id: str = Field(..., description="Canonical ID (e.g., INC000123 or JSM-456)")
    provider: str = Field(..., description="Origin provider: 'mock_itsm' or 'jira'")
    title: str
    description: str
    category: str
    priority: int = Field(..., ge=1, le=4, description="Normalized 1 (Critical) to 4 (Low)")
    state: str = Field(..., description="Normalized: 'new', 'in_progress', 'resolved', 'closed'")
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    caller_email: str
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None
    auto_resolved: bool = False
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class TicketingProvider(ABC):
    """Abstract interface defining required provider operations."""

    @abstractmethod
    def create_ticket(self, data: Dict[str, Any], idempotency_key: Optional[str] = None) -> UnifiedTicket:
        """Create ticket in target ITSM platform."""
        pass

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> UnifiedTicket:
        """Fetch ticket by ID."""
        pass

    @abstractmethod
    def update_ticket(self, ticket_id: str, updates: Dict[str, Any], actor: str = "automation-engine") -> UnifiedTicket:
        """Apply partial updates to ticket."""
        pass

    @abstractmethod
    def resolve_ticket(self, ticket_id: str, resolution_notes: str, actor: str = "automation-engine") -> UnifiedTicket:
        """Mark ticket as resolved."""
        pass

    @abstractmethod
    def list_tickets(self, filters: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[UnifiedTicket]:
        """Query list of tickets matching filters."""
        pass
