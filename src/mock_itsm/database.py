"""Database connection and session handling for Mock ITSM."""
import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Default to local SQLite database in data directory
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/itsm.db")

# Ensure target directory exists for SQLite
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables and ensure schema migrations."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE tickets ADD COLUMN assigned_by VARCHAR(100)"))
            conn.commit()
        except Exception:
            # Column already exists or table was freshly created with it
            pass


def reset_db() -> None:
    """Drop and recreate all database tables (useful for tests/simulations)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
