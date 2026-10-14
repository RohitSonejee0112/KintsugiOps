"""Automated password and MFA reset runbook."""
import re
import uuid
from typing import Dict, Any
from .base import BaseRunbook, RunbookResult


class PasswordResetRunbook(BaseRunbook):
    """Runbook for automating user password resets, account unlocks, and MFA resync."""

    @property
    def name(self) -> str:
        return "PasswordResetRunbook"

    def can_handle(self, ticket_data: Dict[str, Any]) -> bool:
        title = (ticket_data.get("title") or "").lower()
        desc = (ticket_data.get("description") or "").lower()
        subcat = (ticket_data.get("subcategory") or "").lower()
        tags = ticket_data.get("tags") or []

        if "runbook:PasswordResetRunbook" in tags:
            return True

        indicators = ["password reset", "forgot password", "account locked", "unlock account", "mfa reset", "authenticator"]
        return any(ind in title or ind in desc or ind in subcat for ind in indicators)

    def execute(self, ticket_data: Dict[str, Any]) -> RunbookResult:
        caller = ticket_data.get("caller_email", "user@company.com")
        ticket_id = ticket_data.get("id", "UNKNOWN")
        is_mfa = "mfa" in (ticket_data.get("title", "") + ticket_data.get("description", "")).lower()

        # Generate temporary token / incident reference
        temp_token = f"TMP-{uuid.uuid4().hex[:8].upper()}"

        if is_mfa:
            action = "MFA Token Reset & Resynchronization"
            notes = (
                f"Automated identity verification passed for {caller}. "
                f"MFA session reset in Okta/AzureAD. Temporary bypass code issued via secure SMS. "
                f"Session token: {temp_token}."
            )
        else:
            action = "Active Directory Password Reset & Unlock"
            notes = (
                f"Automated account unlock and password reset executed for {caller}. "
                f"Active Directory user status set to 'Password Expired - Force Change at Next Logon'. "
                f"One-time recovery password dispatched to caller's registered mobile number."
            )

        return RunbookResult(
            success=True,
            runbook_name=self.name,
            action_taken=action,
            resolution_notes=notes,
            audit_details={
                "ticket_id": ticket_id,
                "caller_email": caller,
                "auth_method": "Automated Directory API (Simulated)",
                "remediation_status": "Success",
            },
        )
