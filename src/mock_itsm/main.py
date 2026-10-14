"""FastAPI application implementing the Mock ITSM Platform API."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import get_db, init_db, reset_db
from .models import Ticket, EventLog, WebhookSubscription, calculate_itil_priority, utcnow
from .schemas import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    EventLogResponse,
    WebhookSubscriptionCreate,
    WebhookSubscriptionResponse,
    PriorityCalculationRequest,
    PriorityCalculationResponse,
)
from .webhooks import dispatch_webhook_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_itsm.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Mock ITSM Platform API",
    description="ServiceNow/Jira-style Mock ITSM Platform with ITIL Priority Matrix, Audit Event Logs, and Webhooks.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _generate_ticket_id(db: Session, ticket_type: str) -> str:
    """Generate sequential ticket identifier like INC0001001 or RITM0001001."""
    prefix = "INC" if ticket_type == "incident" else ("RITM" if ticket_type == "service_request" else "CHG")
    last_ticket = db.query(Ticket).filter(Ticket.id.like(f"{prefix}%")).order_by(desc(Ticket.id)).first()
    if last_ticket and last_ticket.id[len(prefix):].isdigit():
        next_num = int(last_ticket.id[len(prefix):]) + 1
    else:
        next_num = 100001
    return f"{prefix}{next_num:06d}"


def _ticket_to_response(ticket: Ticket) -> TicketResponse:
    """Map SQLAlchemy Ticket to TicketResponse schema."""
    return TicketResponse(
        id=ticket.id,
        ticket_type=ticket.ticket_type,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        subcategory=ticket.subcategory,
        impact=ticket.impact,
        urgency=ticket.urgency,
        priority=ticket.priority,
        state=ticket.state,
        assignment_group=ticket.assignment_group,
        assigned_to=ticket.assigned_to,
        caller_email=ticket.caller_email,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
        resolution_notes=ticket.resolution_notes,
        sla_due_at=ticket.sla_due_at,
        sla_breached=ticket.sla_breached,
        auto_resolved=ticket.auto_resolved,
        tags=ticket.get_tags(),
    )


# ==========================================================
# Health & Priority
# ==========================================================

@app.get("/health", tags=["System"])
def health_check():
    """Service health probe."""
    return {
        "status": "healthy",
        "service": "Mock ITSM Platform",
        "timestamp": utcnow().isoformat()
    }


@app.post("/api/v1/priority/calculate", response_model=PriorityCalculationResponse, tags=["ITIL"])
def calculate_priority_endpoint(req: PriorityCalculationRequest):
    """Compute ITIL Priority based on Impact and Urgency."""
    priority = calculate_itil_priority(req.impact, req.urgency)
    labels = {1: "1 - Critical", 2: "2 - High", 3: "3 - Moderate", 4: "4 - Low"}
    return PriorityCalculationResponse(
        impact=req.impact,
        urgency=req.urgency,
        priority=priority,
        priority_label=labels.get(priority, "3 - Moderate"),
    )


# ==========================================================
# Ticket Endpoints
# ==========================================================

@app.post("/api/v1/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, tags=["Tickets"])
def create_ticket(
    ticket_in: TicketCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new ITSM ticket, compute priority, write audit log, and fire webhook."""
    ticket_id = ticket_in.id or _generate_ticket_id(db, ticket_in.ticket_type)

    if db.query(Ticket).filter(Ticket.id == ticket_id).first():
        raise HTTPException(status_code=400, detail=f"Ticket {ticket_id} already exists")

    priority = calculate_itil_priority(ticket_in.impact, ticket_in.urgency)

    ticket = Ticket(
        id=ticket_id,
        ticket_type=ticket_in.ticket_type,
        title=ticket_in.title,
        description=ticket_in.description,
        category=ticket_in.category,
        subcategory=ticket_in.subcategory,
        impact=ticket_in.impact,
        urgency=ticket_in.urgency,
        priority=priority,
        state="new",
        assignment_group=ticket_in.assignment_group,
        assigned_to=ticket_in.assigned_to,
        caller_email=ticket_in.caller_email,
        created_at=utcnow(),
        updated_at=utcnow(),
        sla_breached=False,
        auto_resolved=False,
    )
    if ticket_in.tags:
        ticket.set_tags(ticket_in.tags)

    db.add(ticket)

    # Initial audit log
    event = EventLog(
        ticket_id=ticket.id,
        activity="Created",
        timestamp=ticket.created_at,
        actor=ticket_in.caller_email,
        to_state="new",
        to_group=ticket_in.assignment_group,
        details=f"Ticket created with priority P{priority}",
    )
    db.add(event)
    db.commit()
    db.refresh(ticket)

    response_data = _ticket_to_response(ticket)

    # Dispatch webhook in background
    background_tasks.add_task(
        dispatch_webhook_event,
        db=db,
        event_type="ticket.created",
        ticket_id=ticket.id,
        ticket_data=response_data.model_dump(mode="json"),
        actor=ticket_in.caller_email,
    )

    return response_data


@app.get("/api/v1/tickets", response_model=TicketListResponse, tags=["Tickets"])
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    state: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[int] = None,
    assignment_group: Optional[str] = None,
    ticket_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List tickets with pagination and filtering."""
    query = db.query(Ticket)

    if state:
        query = query.filter(Ticket.state == state)
    if category:
        query = query.filter(Ticket.category == category)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if assignment_group:
        query = query.filter(Ticket.assignment_group == assignment_group)
    if ticket_type:
        query = query.filter(Ticket.ticket_type == ticket_type)

    total = query.count()
    items = query.order_by(desc(Ticket.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return TicketListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_ticket_to_response(t) for t in items],
    )


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse, tags=["Tickets"])
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Retrieve ticket by ID."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return _ticket_to_response(ticket)


@app.patch("/api/v1/tickets/{ticket_id}", response_model=TicketResponse, tags=["Tickets"])
def update_ticket(
    ticket_id: str,
    update_in: TicketUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Update ticket fields, record state/assignment transitions in event log, fire webhooks."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    events_to_record = []
    actor = update_in.actor or "system"
    now = utcnow()

    old_state = ticket.state
    old_group = ticket.assignment_group
    old_priority = ticket.priority

    # Apply updates
    if update_in.title is not None:
        ticket.title = update_in.title
    if update_in.description is not None:
        ticket.description = update_in.description
    if update_in.category is not None:
        ticket.category = update_in.category
    if update_in.subcategory is not None:
        ticket.subcategory = update_in.subcategory
    if update_in.assigned_to is not None:
        ticket.assigned_to = update_in.assigned_to
    if update_in.resolution_notes is not None:
        ticket.resolution_notes = update_in.resolution_notes
    if update_in.sla_breached is not None:
        ticket.sla_breached = update_in.sla_breached
    if update_in.auto_resolved is not None:
        ticket.auto_resolved = update_in.auto_resolved
    if update_in.tags is not None:
        ticket.set_tags(update_in.tags)

    # Recalculate priority if impact or urgency changed
    impact_changed = update_in.impact is not None and update_in.impact != ticket.impact
    urgency_changed = update_in.urgency is not None and update_in.urgency != ticket.urgency
    if impact_changed or urgency_changed:
        if update_in.impact is not None:
            ticket.impact = update_in.impact
        if update_in.urgency is not None:
            ticket.urgency = update_in.urgency
        ticket.priority = calculate_itil_priority(ticket.impact, ticket.urgency)
        if ticket.priority != old_priority:
            events_to_record.append(
                EventLog(
                    ticket_id=ticket.id,
                    activity="Priority_Changed",
                    timestamp=now,
                    actor=actor,
                    details=f"Priority updated from P{old_priority} to P{ticket.priority}",
                )
            )

    # Reassignment check
    if update_in.assignment_group is not None and update_in.assignment_group != old_group:
        ticket.assignment_group = update_in.assignment_group
        events_to_record.append(
            EventLog(
                ticket_id=ticket.id,
                activity="Reassigned",
                timestamp=now,
                actor=actor,
                from_group=old_group,
                to_group=ticket.assignment_group,
                details=f"Reassigned from '{old_group}' to '{ticket.assignment_group}'",
            )
        )

    # State transition check
    webhook_event = "ticket.updated"
    if update_in.state is not None and update_in.state != old_state:
        ticket.state = update_in.state
        if ticket.state in ("resolved", "closed") and not ticket.resolved_at:
            ticket.resolved_at = now
            webhook_event = "ticket.resolved"

        activity_name = "Resolved" if ticket.state == "resolved" else "State_Changed"
        events_to_record.append(
            EventLog(
                ticket_id=ticket.id,
                activity=activity_name,
                timestamp=now,
                actor=actor,
                from_state=old_state,
                to_state=ticket.state,
                from_group=ticket.assignment_group,
                to_group=ticket.assignment_group,
                details=f"State transitioned from '{old_state}' to '{ticket.state}'",
            )
        )

    ticket.updated_at = now
    for ev in events_to_record:
        db.add(ev)

    db.commit()
    db.refresh(ticket)

    response_data = _ticket_to_response(ticket)

    background_tasks.add_task(
        dispatch_webhook_event,
        db=db,
        event_type=webhook_event,
        ticket_id=ticket.id,
        ticket_data=response_data.model_dump(mode="json"),
        actor=actor,
    )

    return response_data


@app.delete("/api/v1/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tickets"])
def delete_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """Delete a ticket and cascading events."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    db.delete(ticket)
    db.commit()
    return None


# ==========================================================
# Event Log / Audit Trail (Crucial for Process Mining)
# ==========================================================

@app.get("/api/v1/tickets/{ticket_id}/events", response_model=List[EventLogResponse], tags=["Process Mining"])
def get_ticket_events(ticket_id: str, db: Session = Depends(get_db)):
    """Get chronological audit log for a single ticket."""
    events = (
        db.query(EventLog)
        .filter(EventLog.ticket_id == ticket_id)
        .order_by(EventLog.timestamp)
        .all()
    )
    return events


@app.get("/api/v1/events", response_model=List[EventLogResponse], tags=["Process Mining"])
def get_all_events(
    limit: int = Query(5000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    activity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Fetch global event log for pm4py Process Mining analysis."""
    query = db.query(EventLog)
    if activity:
        query = query.filter(EventLog.activity == activity)
    events = query.order_by(EventLog.timestamp).offset(offset).limit(limit).all()
    return events


# ==========================================================
# Webhook Subscriptions
# ==========================================================

@app.post("/api/v1/webhooks/subscriptions", response_model=WebhookSubscriptionResponse, status_code=status.HTTP_201_CREATED, tags=["Webhooks"])
def register_webhook(
    sub_in: WebhookSubscriptionCreate,
    db: Session = Depends(get_db),
):
    """Register a webhook endpoint to receive ticket events."""
    sub = WebhookSubscription(
        target_url=sub_in.target_url,
        secret=sub_in.secret,
        events=sub_in.events,
        is_active=True,
        created_at=utcnow(),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@app.get("/api/v1/webhooks/subscriptions", response_model=List[WebhookSubscriptionResponse], tags=["Webhooks"])
def list_webhooks(db: Session = Depends(get_db)):
    """List all registered webhook subscriptions."""
    return db.query(WebhookSubscription).all()


@app.delete("/api/v1/webhooks/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Webhooks"])
def delete_webhook(sub_id: int, db: Session = Depends(get_db)):
    """Remove a webhook subscription."""
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.id == sub_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail=f"Webhook subscription {sub_id} not found")
    db.delete(sub)
    db.commit()
    return None


# ==========================================================
# Admin / Testing Helpers
# ==========================================================

@app.post("/api/v1/admin/reset", tags=["Admin"])
def reset_database_endpoint():
    """Reset the database tables (wipes all tickets and logs). Useful for test runs and fresh benchmarks."""
    reset_db()
    return {"status": "success", "message": "Database reset completed"}
