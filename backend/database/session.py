"""SQLite Database Connection and Session Engine"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.core.config import settings
import os

# Ensure the database directory exists with restrictive permissions
db_dir = os.path.dirname(settings.SQLITE_URL.replace("sqlite:///", ""))
if db_dir:
    os.makedirs(db_dir, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(db_dir, 0o700)
        except OSError:
            pass


# SQLite Engine with multi-threading safety and timeout
engine = create_engine(
    settings.SQLITE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 10.0  # 10s busy timeout
    },
    echo=False
)

# Apply SQLite WAL mode, synchronous=NORMAL, and busy_timeout on every connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")  # 10,000 ms
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for providing a fresh scoped session per API request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
