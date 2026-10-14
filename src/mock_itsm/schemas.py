"""Pydantic v2 schemas for Mock ITSM API."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, EmailStr


class TicketBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Short summary of issue or request")
    description: str = Field(..., min_length=5, description="Full ticket description")
    category: str = Field(..., max_length=100, description="E.g., Hardware, Network, Access, ERP/SAP")
    subcategory: Optional[str] = Field(None, max_length=100)
    impact: int = Field(2, ge=1, le=3, description="1=High, 2=Medium, 3=Low")
    urgency: int = Field(2, ge=1, le=3, description="1=High, 2=Medium, 3=Low")
    caller_email: str = Field(..., description="Email of requester")
    ticket_type: str = Field("incident", description="incident, service_request, or change")


class TicketCreate(TicketBase):
    id: Optional[str] = Field(None, description="Optional custom ticket ID (e.g. INC0001001)")
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    impact: Optional[int] = Field(None, ge=1, le=3)
    urgency: Optional[int] = Field(None, ge=1, le=3)
    state: Optional[str] = None  # new, assigned, in_progress, awaiting_user, resolved, closed, cancelled
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    sla_breached: Optional[bool] = None
    auto_resolved: Optional[bool] = None
    tags: Optional[List[str]] = None
    actor: str = Field("system", description="Identity performing this update for audit logging")


class TicketResponse(TicketBase):
    id: str
    priority: int
    state: str
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    sla_breached: bool = False
    auto_resolved: bool = False
    tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TicketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TicketResponse]


class EventLogResponse(BaseModel):
    id: int
    ticket_id: str
    activity: str
    timestamp: datetime
    actor: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    from_group: Optional[str] = None
    to_group: Optional[str] = None
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WebhookSubscriptionCreate(BaseModel):
    target_url: str = Field(..., description="Destination endpoint URL to receive POST events")
    secret: str = Field(..., min_length=8, description="Secret used to sign HMAC-SHA256 headers")
    events: str = Field("*", description="Comma-separated event names or '*' for all")


class WebhookSubscriptionResponse(WebhookSubscriptionCreate):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookPayload(BaseModel):
    event_id: str
    event_type: str  # ticket.created, ticket.updated, ticket.resolved, ticket.reassigned
    timestamp: datetime
    ticket_id: str
    data: Dict[str, Any]
    actor: str


class PriorityCalculationRequest(BaseModel):
    impact: int = Field(..., ge=1, le=3)
    urgency: int = Field(..., ge=1, le=3)


class PriorityCalculationResponse(BaseModel):
    impact: int
    urgency: int
    priority: int
    priority_label: str
