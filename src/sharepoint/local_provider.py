"""Local file and JSON store implementation replicating SharePoint Lists & Document Libraries."""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from .base import DocumentationProvider
from ..process_mining.proposal_generator import StructuralImprovementProposal


class LocalDocumentProvider(DocumentationProvider):
    """Zero-tenant local documentation store replicating SharePoint functionality."""

    def __init__(self, base_dir: str = "./local_sharepoint"):
        self.base_dir = Path(base_dir)
        self.reports_dir = self.base_dir / "reports"
        self.lists_dir = self.base_dir / "lists"
        self.tracker_file = self.lists_dir / "improvement_tracker.json"

        # Ensure directory structure exists
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.lists_dir.mkdir(parents=True, exist_ok=True)

        if not self.tracker_file.exists():
            self._save_tracker([])

    def _load_tracker(self) -> List[Dict[str, Any]]:
        try:
            with open(self.tracker_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_tracker(self, items: List[Dict[str, Any]]) -> None:
        with open(self.tracker_file, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, default=str)

    def create_improvement_item(self, proposal: StructuralImprovementProposal) -> Dict[str, Any]:
        """Create a new item in the local Improvement Tracker List."""
        items = self._load_tracker()
        record = {
            "id": proposal.proposal_id,
            "title": proposal.title,
            "problem_statement": proposal.problem_statement,
            "empirical_evidence": proposal.empirical_evidence,
            "proposed_structural_change": proposal.proposed_structural_change,
            "expected_impact": proposal.expected_impact,
            "effort": proposal.implementation_effort,
            "priority": proposal.priority,
            "target_team": proposal.target_team,
            "status": proposal.status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Update if exists, or append
        existing_idx = next((i for i, item in enumerate(items) if item["id"] == record["id"]), None)
        if existing_idx is not None:
            items[existing_idx] = record
        else:
            items.append(record)

        self._save_tracker(items)
        return record

    def update_improvement_item(self, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update fields on an improvement item."""
        items = self._load_tracker()
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            raise KeyError(f"Improvement item {item_id} not found")

        for k, v in updates.items():
            item[k] = v
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_tracker(items)
        return item

    def list_improvement_items(self) -> List[Dict[str, Any]]:
        """Return all items in tracker list."""
        return self._load_tracker()

    def upload_report(
        self,
        filename: str,
        content: str,
        folder: str = "Process Mining Reports"
    ) -> Dict[str, Any]:
        """Save report document to local document library."""
        file_path = self.reports_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "name": filename,
            "path": str(file_path),
            "size_bytes": os.path.getsize(file_path),
            "folder": folder,
            "web_url": f"file:///{file_path.as_posix()}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_reports(self) -> List[Dict[str, Any]]:
        """List all documents stored in the local document library."""
        reports = []
        for p in self.reports_dir.glob("*"):
            if p.is_file():
                reports.append({
                    "name": p.name,
                    "path": str(p),
                    "size_bytes": os.path.getsize(p),
                    "modified_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "web_url": f"file:///{p.as_posix()}",
                })
        return reports
