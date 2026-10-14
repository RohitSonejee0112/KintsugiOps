"""Production Microsoft Graph API client for SharePoint Online integration."""
import os
import logging
from typing import Dict, Any, List, Optional
import httpx
from .base import DocumentationProvider
from ..process_mining.proposal_generator import StructuralImprovementProposal

logger = logging.getLogger("sharepoint.graph_client")

try:
    import msal
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False


class SharePointGraphProvider(DocumentationProvider):
    """Microsoft Graph API adapter syncing reports and lists with SharePoint Online."""

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        site_id: Optional[str] = None,
        list_name: str = "ITSM Operational Improvement Tracker",
        doc_library: str = "Process Mining Reports",
    ):
        self.tenant_id = tenant_id or os.getenv("SHAREPOINT_TENANT_ID")
        self.client_id = client_id or os.getenv("SHAREPOINT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SHAREPOINT_CLIENT_SECRET")
        self.site_id = site_id or os.getenv("SHAREPOINT_SITE_ID")
        self.list_name = list_name
        self.doc_library = doc_library

    def _get_access_token(self) -> str:
        """Acquire OAuth2 bearer token from Azure AD via MSAL."""
        if not MSAL_AVAILABLE:
            raise RuntimeError("msal library is not installed")
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise ValueError("Microsoft 365 credentials (tenant_id, client_id, client_secret) are not configured.")

        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        raise RuntimeError(f"MSAL authentication failed: {result.get('error_description')}")

    def create_improvement_item(self, proposal: StructuralImprovementProposal) -> Dict[str, Any]:
        """Create item in SharePoint List via Graph API."""
        token = self._get_access_token()
        url = f"{self.GRAPH_BASE_URL}/sites/{self.site_id}/lists/{self.list_name}/items"
        payload = {
            "fields": {
                "Title": proposal.title,
                "ProposalID": proposal.proposal_id,
                "ProblemStatement": proposal.problem_statement,
                "EmpiricalEvidence": proposal.empirical_evidence,
                "ProposedChange": proposal.proposed_structural_change,
                "ExpectedImpact": proposal.expected_impact,
                "Effort": proposal.implementation_effort,
                "Priority": proposal.priority,
                "TargetTeam": proposal.target_team,
                "Status": proposal.status,
            }
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def update_improvement_item(self, item_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        token = self._get_access_token()
        url = f"{self.GRAPH_BASE_URL}/sites/{self.site_id}/lists/{self.list_name}/items/{item_id}/fields"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(url, json=updates, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def list_improvement_items(self) -> List[Dict[str, Any]]:
        token = self._get_access_token()
        url = f"{self.GRAPH_BASE_URL}/sites/{self.site_id}/lists/{self.list_name}/items?expand=fields"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return [i.get("fields", {}) for i in resp.json().get("value", [])]

    def upload_report(
        self,
        filename: str,
        content: str,
        folder: str = "Process Mining Reports"
    ) -> Dict[str, Any]:
        token = self._get_access_token()
        url = f"{self.GRAPH_BASE_URL}/sites/{self.site_id}/drives/root:/{folder}/{filename}:/content"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "text/markdown"}
        with httpx.Client(timeout=15.0) as client:
            resp = client.put(url, content=content.encode("utf-8"), headers=headers)
            resp.raise_for_status()
            return resp.json()

    def list_reports(self) -> List[Dict[str, Any]]:
        token = self._get_access_token()
        url = f"{self.GRAPH_BASE_URL}/sites/{self.site_id}/drives/root:/{self.doc_library}:/children"
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json().get("value", [])
