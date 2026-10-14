"""SQLAlchemy ORM models for Mock ITSM Platform."""
from datetime import datetime, timezone
import json
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from .database import Base


def utcnow() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def calculate_itil_priority(impact: int, urgency: int) -> int:
    """Calculate ITIL Priority (1=Critical, 2=High, 3=Moderate, 4=Low)

    Standard ITIL Priority Matrix:
        Urgency 1  Urgency 2  Urgency 3
    Imp 1:   P1         P2         P3
    Imp 2:   P2         P3         P4
    Imp 3:   P3         P4         P4
    """
    matrix = {
        (1, 1): 1,
        (1, 2): 2,
        (1, 3): 3,
        (2, 1): 2,
        (2, 2): 3,
        (2, 3): 4,
        (3, 1): 3,
        (3, 2): 4,
        (3, 3): 4,
    }
    return matrix.get((impact, urgency), 3)


class Ticket(Base):
    """ITSM Ticket Entity (Incidents, Service Requests, Change Requests)."""
    __tablename__ = "tickets"

    id = Column(String(50), primary_key=True, index=True)
    ticket_type = Column(String(30), default="incident", index=True)  # incident, service_request, change
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(100), nullable=True)
    impact = Column(Integer, default=2)    # 1=High, 2=Medium, 3=Low
    urgency = Column(Integer, default=2)   # 1=High, 2=Medium, 3=Low
    priority = Column(Integer, default=3, index=True)  # 1=Critical, 2=High, 3=Moderate, 4=Low
    state = Column(String(50), default="new", index=True)
    assignment_group = Column(String(100), nullable=True, index=True)
    assigned_to = Column(String(100), nullable=True)
    caller_email = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    sla_due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sla_breached = Column(Boolean, default=False, index=True)
    auto_resolved = Column(Boolean, default=False)
    tags = Column(Text, default="[]")  # JSON-encoded array

    # Relationship to audit event logs
    events = relationship(
        "EventLog",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="EventLog.timestamp"
    )

    def get_tags(self) -> List[str]:
        try:
            return json.loads(self.tags or "[]")
        except Exception:
            return []

    def set_tags(self, tags_list: List[str]) -> None:
        self.tags = json.dumps(tags_list)


class EventLog(Base):
    """Discrete state transition and operational event log for Process Mining."""
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(50), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    activity = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    actor = Column(String(100), nullable=False)
    from_state = Column(String(50), nullable=True)
    to_state = Column(String(50), nullable=True)
    from_group = Column(String(100), nullable=True)
    to_group = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)

    ticket = relationship("Ticket", back_populates="events")


class WebhookSubscription(Base):
    """Registered webhook subscribers for event-driven automation."""
    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)
    events = Column(String(255), default="*")  # Comma-separated or '*' for all
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
