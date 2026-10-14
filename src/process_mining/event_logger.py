"""Event log extraction and standardization for pm4py Process Mining."""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.orm import Session
from ..mock_itsm.models import EventLog, Ticket
from ..mock_itsm.database import SessionLocal


class EventLogExtractor:
    """Extracts, formats, and enriches event logs for process mining analysis."""

    @staticmethod
    def events_to_dataframe(events: List[EventLog]) -> pd.DataFrame:
        """Convert list of EventLog entities to a pm4py-standard DataFrame."""
        if not events:
            return pd.DataFrame(columns=[
                "case:concept:name",
                "concept:name",
                "time:timestamp",
                "org:group",
                "org:resource",
                "from_state",
                "to_state",
            ])

        records = []
        for e in events:
            ts = e.timestamp
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            records.append({
                "case:concept:name": str(e.ticket_id),
                "concept:name": str(e.activity),
                "time:timestamp": ts,
                "org:group": e.to_group or e.from_group or "Unassigned",
                "org:resource": e.actor or "system",
                "from_state": e.from_state,
                "to_state": e.to_state,
                "details": e.details or "",
            })

        df = pd.DataFrame(records)
        df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
        df = df.sort_values(by=["case:concept:name", "time:timestamp"]).reset_index(drop=True)
        return df

    @classmethod
    def extract_from_database(cls, db: Optional[Session] = None, limit: int = 50000) -> pd.DataFrame:
        """Query event logs directly from Mock ITSM database into pm4py format."""
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True
        try:
            events = db.query(EventLog).order_by(EventLog.timestamp).limit(limit).all()
            return cls.events_to_dataframe(events)
        finally:
            if close_db:
                db.close()

    @staticmethod
    def export_csv(df: pd.DataFrame, file_path: str) -> str:
        """Export DataFrame to CSV format."""
        df.to_csv(file_path, index=False)
        return file_path
