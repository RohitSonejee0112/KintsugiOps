"""Abstract DocumentationProvider interface for SharePoint and local fallbacks."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..process_mining.proposal_generator import StructuralImprovementProposal


class DocumentationProvider(ABC):
    """Abstract provider for publishing reports and maintaining an Improvement Tracker."""

    @abstractmethod
    def create_improvement_item(self, proposal: StructuralImprovementProposal) -> Dict[str, Any]:
        """Create a new item in the SharePoint Improvement Tracker List."""
        pass

    @abstractmethod
    def update_improvement_item(self, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update status, owner, or impact of an improvement tracker item."""
        pass

    @abstractmethod
    def list_improvement_items(self) -> List[Dict[str, Any]]:
        """Fetch all items from the Improvement Tracker List."""
        pass

    @abstractmethod
    def upload_report(
        self,
        filename: str,
        content: str,
        folder: str = "Process Mining Reports"
    ) -> Dict[str, Any]:
        """Upload generated process mining report to the SharePoint Document Library."""
        pass

    @abstractmethod
    def list_reports(self) -> List[Dict[str, Any]]:
        """List uploaded documents in the library."""
        pass
