# ADR 001: FastAPI and Pydantic v2 for Mock ITSM Platform

## Status
Accepted

## Context
The project required a robust, high-performance mock ITSM platform providing ServiceNow and Jira-style ticket lifecycle management, ITIL priority matrix calculations, audit event logging, and HMAC-signed webhook dispatching.

## Decision
We selected **FastAPI** with **Pydantic v2** and **SQLAlchemy 2.0**:
1. **Asynchronous Throughput & Webhooks**: FastAPI's async execution model and background task support allow asynchronous delivery of signed webhook notifications (`X-Hub-Signature-256`) without blocking the main REST response.
2. **Pydantic v2 Performance & Validation**: Pydantic v2 provides compiled C/Rust-level JSON serialization speed and strict schema validation for ITIL priority matrices, ticket creation, and event logging.
3. **OpenAPI & Interactive Documentation**: FastAPI automatically produces OpenAPI 3.0 documentation (`/docs`), allowing engineers and enterprise evaluators to interact directly with the mock ITSM API.

## Consequences
- Requires Python 3.10+.
- Provides instantaneous response times and clean type hints throughout the integration layer.
