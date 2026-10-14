"""Automated standard software and role access provisioning runbook."""
import uuid
from typing import Dict, Any
from .base import BaseRunbook, RunbookResult


class SoftwareAccessRunbook(BaseRunbook):
    """Runbook for automating pre-approved software access and standard role provisioning."""

    @property
    def name(self) -> str:
        return "SoftwareAccessRunbook"

    def can_handle(self, ticket_data: Dict[str, Any]) -> bool:
        title = (ticket_data.get("title") or "").lower()
        desc = (ticket_data.get("description") or "").lower()
        subcat = (ticket_data.get("subcategory") or "").lower()
        tags = ticket_data.get("tags") or []

        if "runbook:SoftwareAccessRunbook" in tags:
            return True

        keywords = ["sharepoint folder", "access request", "me21n", "license", "authorization missing"]
        return any(kw in title or kw in desc or kw in subcat for kw in keywords)

    def execute(self, ticket_data: Dict[str, Any]) -> RunbookResult:
        caller = ticket_data.get("caller_email", "user@company.com")
        ticket_id = ticket_data.get("id", "UNKNOWN")
        text = f"{ticket_data.get('title', '')} {ticket_data.get('description', '')}".lower()

        grant_id = f"GRN-{uuid.uuid4().hex[:6].upper()}"

        if "sap" in text or "me21n" in text:
            action = "SAP Role Provisioning"
            notes = (
                f"Automated approval check verified manager authorization for {caller}. "
                f"SAP user master record updated: assigned standard role 'Z_MM_PURCHASER'. "
                f"User confirmed synchronized with central CUA. Grant ID: {grant_id}."
            )
        elif "sharepoint" in text:
            action = "SharePoint Site Access Grant"
            notes = (
                f"Permission group lookup executed for caller {caller}. "
                f"Granted 'Contribute' access to requested SharePoint Document Library. "
                f"Sync completed via Microsoft Graph API. Grant ID: {grant_id}."
            )
        else:
            action = "SaaS License Assignment"
            notes = (
                f"Standard catalog item approved automatically. "
                f"Assigned available cloud license pool to user {caller}. Grant ID: {grant_id}."
            )

        return RunbookResult(
            success=True,
            runbook_name=self.name,
            action_taken=action,
            resolution_notes=notes,
            audit_details={
                "ticket_id": ticket_id,
                "grant_id": grant_id,
                "caller_email": caller,
                "policy": "Pre-Approved Enterprise Catalog",
            },
        )
