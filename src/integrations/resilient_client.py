"""Resilient HTTP client with exponential backoff, idempotency, and Dead-Letter Queue."""
import time
import uuid
import logging
from typing import Dict, Any, Optional, Set, List
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger("integrations.resilient_client")


class TransientHttpError(Exception):
    """Raised on recoverable HTTP 429, 500, 502, 503, 504 errors."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Transient HTTP {status_code}: {message}")


class ResilientHttpClient:
    """HTTP Client wrapping httpx with exponential backoff, idempotency, and DLQ."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        timeout: float = 5.0,
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.processed_idempotency_keys: Set[str] = set()
        self.dead_letter_queue: List[Dict[str, Any]] = []

    def is_idempotency_key_seen(self, key: Optional[str]) -> bool:
        """Check if an idempotency key was already processed."""
        if not key:
            return False
        return key in self.processed_idempotency_keys

    def mark_idempotency_key(self, key: Optional[str]) -> None:
        """Record an idempotency key as processed."""
        if key:
            self.processed_idempotency_keys.add(key)

    def execute_with_retry(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Execute HTTP request with retries, idempotency tracking, and DLQ fallback."""
        key = idempotency_key or str(uuid.uuid4())
        req_headers = dict(headers or {})
        req_headers["X-Idempotency-Key"] = key

        # Inner retry function configured with tenacity
        @retry(
            reraise=True,
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=self.backoff_factor, min=1, max=10),
            retry=retry_if_exception_type((TransientHttpError, httpx.RequestError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        def _attempt():
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(method, url, json=json_data, headers=req_headers)
                # Check for rate limiting or server error
                if resp.status_code in (429, 500, 502, 503, 504):
                    # Check Retry-After
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        time.sleep(float(retry_after))
                    raise TransientHttpError(resp.status_code, resp.text)
                return resp

        try:
            response = _attempt()
            self.mark_idempotency_key(key)
            return response
        except Exception as exc:
            # Exhausted retries -> save to Dead-Letter Queue
            logger.error(f"Request to {url} failed after {self.max_retries} retries. Routing to DLQ. Error: {exc}")
            dlq_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": time.time(),
                "method": method,
                "url": url,
                "payload": json_data,
                "headers": req_headers,
                "error": str(exc),
                "retry_count": self.max_retries,
            }
            self.dead_letter_queue.append(dlq_entry)
            raise exc

    def get_dlq_entries(self) -> List[Dict[str, Any]]:
        """Return all items currently stored in Dead-Letter Queue."""
        return list(self.dead_letter_queue)

    def clear_dlq(self) -> None:
        """Flush the Dead-Letter Queue."""
        self.dead_letter_queue.clear()
