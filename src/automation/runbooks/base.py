"""Abstract base class and schemas for automated ITSM runbooks."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class RunbookResult(BaseModel):
    """Execution output from an automated runbook."""
    success: bool
    runbook_name: str
    action_taken: str
    resolution_notes: str
    audit_details: Dict[str, Any] = Field(default_factory=dict)


class BaseRunbook(ABC):
    """Abstract interface for repeatable auto-resolution runbooks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the runbook."""
        pass

    @abstractmethod
    def can_handle(self, ticket_data: Dict[str, Any]) -> bool:
        """Evaluate if this runbook applies to the ticket."""
        pass

    @abstractmethod
    def execute(self, ticket_data: Dict[str, Any]) -> RunbookResult:
        """Execute automated remediation and return result."""
        pass
