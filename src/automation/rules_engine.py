"""Rule-based routing and priority calculation engine (Baseline)."""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml


class RulesEngine:
    """Deterministic, YAML-configurable rules engine for category routing and priority."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to config/routing_rules.yaml relative to this file
            config_path = str(Path(__file__).parent / "config" / "routing_rules.yaml")
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        # Fallback in-memory configuration
        return {
            "assignment_rules": [
                {
                    "name": "IAM_Identity_Operations",
                    "group": "IAM-Identity-Operations",
                    "categories": ["Access / Identity"],
                    "keywords": ["password", "mfa", "authenticator", "lockout", "access"],
                },
                {
                    "name": "Desktop_Support",
                    "group": "Desktop-Support-L2",
                    "categories": ["Hardware"],
                    "keywords": ["laptop", "battery", "monitor", "dock"],
                },
                {
                    "name": "Network_Operations",
                    "group": "Network-Infrastructure-Ops",
                    "categories": ["Network"],
                    "keywords": ["wifi", "vpn", "dns", "latency"],
                },
                {
                    "name": "Enterprise_ERP_Support",
                    "group": "Enterprise-ERP-Support",
                    "categories": ["ERP / SAP"],
                    "keywords": ["sap", "va01", "me21n", "invoice"],
                },
                {
                    "name": "Cloud_Platform_Engineering",
                    "group": "Cloud-Platform-Engineering",
                    "categories": ["Cloud & DevOps"],
                    "keywords": ["kubernetes", "aws", "s3", "docker"],
                },
                {
                    "name": "Default_Fallback",
                    "group": "ServiceDesk-L1",
                    "categories": [],
                    "keywords": [],
                },
            ]
        }

    def evaluate_routing(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate ticket and determine assignment group, matched rule, and confidence.

        Returns:
            dict with:
                - assignment_group: str
                - rule_matched: str
                - confidence: float (1.0 for direct match, 0.4 for fallback)
        """
        title = (ticket_data.get("title") or "").lower()
        desc = (ticket_data.get("description") or "").lower()
        category = ticket_data.get("category", "")
        combined_text = f"{title} {desc}"

        rules: List[Dict[str, Any]] = self.config.get("assignment_rules", [])

        # 1. First pass: exact category match
        for rule in rules:
            if category and category in rule.get("categories", []):
                return {
                    "assignment_group": rule["group"],
                    "rule_matched": rule["name"],
                    "confidence": 0.95,
                    "method": "category_match",
                }

        # 2. Second pass: keyword search in text
        for rule in rules:
            keywords = rule.get("keywords", [])
            for kw in keywords:
                if kw in combined_text:
                    return {
                        "assignment_group": rule["group"],
                        "rule_matched": rule["name"],
                        "confidence": 0.85,
                        "method": "keyword_match",
                    }

        # 3. Fallback to ServiceDesk-L1
        fallback_group = "ServiceDesk-L1"
        for rule in rules:
            if rule.get("name") == "Default_Fallback":
                fallback_group = rule.get("group", fallback_group)
                break

        return {
            "assignment_group": fallback_group,
            "rule_matched": "Default_Fallback",
            "confidence": 0.40,
            "method": "fallback",
        }
