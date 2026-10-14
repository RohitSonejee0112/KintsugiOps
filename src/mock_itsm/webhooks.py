"""Webhook delivery dispatcher and HMAC signature verification."""
import hmac
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
import httpx
from sqlalchemy.orm import Session
from .models import WebhookSubscription

logger = logging.getLogger("mock_itsm.webhooks")


def generate_hmac_signature(payload_bytes: bytes, secret: str) -> str:
    """Generate SHA256 HMAC signature formatted as 'sha256=<hex>'."""
    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """Verify incoming HMAC signature against secret."""
    if not signature_header or not secret:
        return False
    expected = generate_hmac_signature(payload_bytes, secret)
    return hmac.compare_digest(expected, signature_header)


async def dispatch_webhook_event(
    db: Session,
    event_type: str,
    ticket_id: str,
    ticket_data: Dict[str, Any],
    actor: str = "system"
) -> int:
    """Find active webhook subscriptions matching event_type and dispatch async HTTP POST.

    Returns the number of subscribers notified.
    """
    subs: List[WebhookSubscription] = db.query(WebhookSubscription).filter(
        WebhookSubscription.is_active.is_(True)
    ).all()

    if not subs:
        return 0

    event_payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "data": ticket_data,
        "actor": actor,
    }
    payload_bytes = json.dumps(event_payload, default=str).encode("utf-8")

    sent_count = 0
    async with httpx.AsyncClient(timeout=4.0) as client:
        for sub in subs:
            # Check if subscribed to '*' or this specific event_type
            subscribed_events = [e.strip() for e in sub.events.split(",")]
            if "*" not in subscribed_events and event_type not in subscribed_events:
                continue

            sig = generate_hmac_signature(payload_bytes, sub.secret)
            headers = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
                "X-Event-Type": event_type,
                "X-Event-ID": event_payload["event_id"],
                "User-Agent": "MockITSM-Webhook-Dispatcher/1.0",
            }
            try:
                resp = await client.post(sub.target_url, content=payload_bytes, headers=headers)
                logger.info(
                    f"Dispatched {event_type} for ticket {ticket_id} to {sub.target_url} -> Status {resp.status_code}"
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    f"Failed dispatching {event_type} to {sub.target_url}: {exc}"
                )

    return sent_count
