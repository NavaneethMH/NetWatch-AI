"""Database schema migrations for NetWatch AI.
Safe, idempotent SQLite migrations to upgrade schemas across phases without data loss.
"""
import sqlite3
import logging
import os
from typing import Optional
from backend.core.config import settings

logger = logging.getLogger("netwatch.database.migrations")

def run_migrations(db_path: Optional[str] = None) -> None:
    """Runs all pending schema migrations idempotently on the specified or configured SQLite database."""
    if db_path is None:
        db_path = settings.SQLITE_URL.replace("sqlite:///", "")

    if not os.path.exists(db_path):
        logger.info(f"Database at {db_path} does not exist yet; skipping migration until initialized.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        # 1. Check if protocol_metrics table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protocol_metrics'")
        if not cur.fetchone():
            logger.info("protocol_metrics table does not exist yet; nothing to migrate.")
            return

        # 2. Inspect columns in protocol_metrics
        cur.execute("PRAGMA table_info(protocol_metrics)")
        cols = [row[1] for row in cur.fetchall()]

        # Migration: Add non_ip_packets column if missing
        if "non_ip_packets" not in cols:
            logger.info("Migrating protocol_metrics: adding non_ip_packets column...")
            cur.execute("ALTER TABLE protocol_metrics ADD COLUMN non_ip_packets INTEGER NOT NULL DEFAULT 0")
            # Existing records are strictly IP frames (from SIO_RCVALL raw socket), so backfill 0 is exact.
            cur.execute("UPDATE protocol_metrics SET non_ip_packets = 0 WHERE non_ip_packets IS NULL")
            conn.commit()
            logger.info("Successfully added non_ip_packets column to protocol_metrics.")
        else:
            logger.debug("protocol_metrics already has non_ip_packets column.")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed on {db_path}: {e}", exc_info=True)
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
