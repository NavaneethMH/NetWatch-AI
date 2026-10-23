"""Alert Repository (Phase 8)
Data access layer for Alert persistence, deduplication, acknowledgement, and querying.
"""
from typing import Optional, List
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from backend.database.models import AlertModel
from backend.schemas.alert import AlertSummary

class AlertRepository:
    @staticmethod
    def get_active_alert(db: Session, alert_type: str, source: str) -> Optional[AlertModel]:
        """Finds an existing OPEN or ACKNOWLEDGED alert for the given type and source."""
        return db.query(AlertModel).filter(
            AlertModel.type == alert_type,
            AlertModel.source == source,
            AlertModel.status.in_(["OPEN", "ACKNOWLEDGED"])
        ).first()

    @staticmethod
    def create_alert(
        db: Session,
        alert_type: str,
        severity: str,
        source: str,
        message: str,
        metric_name: str,
        observed_value: Optional[float],
        threshold_value: Optional[float],
        timestamp: float,
        timestamp_utc: str
    ) -> AlertModel:
        """Inserts a new OPEN alert."""
        alert = AlertModel(
            alert_id=str(uuid.uuid4()),
            type=alert_type,
            severity=severity,
            status="OPEN",
            source=source,
            message=message,
            metric_name=metric_name,
            observed_value=observed_value,
            threshold_value=threshold_value,
            opened_at=timestamp,
            opened_at_utc=timestamp_utc,
            last_seen_at=timestamp,
            last_seen_at_utc=timestamp_utc,
            occurrence_count=1
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def update_active_alert(
        db: Session,
        alert: AlertModel,
        observed_value: Optional[float],
        severity: str,
        message: str,
        timestamp: float,
        timestamp_utc: str
    ) -> AlertModel:
        """Updates an existing active alert: increments occurrence_count, updates last_seen_at and observed_value,
        and escalates severity if higher.
        """
        alert.occurrence_count += 1
        alert.last_seen_at = timestamp
        alert.last_seen_at_utc = timestamp_utc
        alert.observed_value = observed_value
        alert.message = message
        # Escalate severity to CRITICAL if violation intensified
        if severity == "CRITICAL" and alert.severity != "CRITICAL":
            alert.severity = "CRITICAL"
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def resolve_alert(
        db: Session,
        alert: AlertModel,
        timestamp: float,
        timestamp_utc: str
    ) -> AlertModel:
        """Marks an alert as RESOLVED."""
        alert.status = "RESOLVED"
        alert.resolved_at = timestamp
        alert.resolved_at_utc = timestamp_utc
        alert.last_seen_at = timestamp
        alert.last_seen_at_utc = timestamp_utc
        db.commit()
        db.refresh(alert)
        return alert

    @staticmethod
    def acknowledge_alert(db: Session, identifier: str, timestamp: float, timestamp_utc: str) -> Optional[AlertModel]:
        """Marks an alert as ACKNOWLEDGED. Acknowledgement indicates user awareness; does NOT resolve the underlying condition."""
        query = db.query(AlertModel)
        if identifier.isdigit():
            alert = query.filter(AlertModel.id == int(identifier)).first()
        else:
            alert = query.filter(AlertModel.alert_id == identifier).first()

        if not alert:
            return None

        # Only transition if currently OPEN
        if alert.status == "OPEN":
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = timestamp
            alert.acknowledged_at_utc = timestamp_utc
            db.commit()
            db.refresh(alert)
        return alert

    @staticmethod
    def get_alert_by_id(db: Session, identifier: str) -> Optional[AlertModel]:
        """Fetches an alert by numeric id or UUID alert_id."""
        query = db.query(AlertModel)
        if identifier.isdigit():
            return query.filter(AlertModel.id == int(identifier)).first()
        return query.filter(AlertModel.alert_id == identifier).first()

    @staticmethod
    def list_alerts(
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AlertModel]:
        """Lists alerts with optional filters ordered by opened_at descending."""
        query = db.query(AlertModel)
        if status:
            query = query.filter(AlertModel.status == status.upper())
        if severity:
            query = query.filter(AlertModel.severity == severity.upper())
        if alert_type:
            query = query.filter(AlertModel.type == alert_type.upper())

        bounded_limit = min(1000, max(1, limit))
        return query.order_by(desc(AlertModel.opened_at)).limit(bounded_limit).all()

    @staticmethod
    def get_active_summary(db: Session) -> AlertSummary:
        """Returns counts of active (OPEN + ACKNOWLEDGED) alerts."""
        active_alerts = db.query(AlertModel).filter(AlertModel.status.in_(["OPEN", "ACKNOWLEDGED"])).all()
        open_count = sum(1 for a in active_alerts if a.status == "OPEN")
        ack_count = sum(1 for a in active_alerts if a.status == "ACKNOWLEDGED")
        crit_count = sum(1 for a in active_alerts if a.severity == "CRITICAL")
        warn_count = sum(1 for a in active_alerts if a.severity == "WARNING")
        info_count = sum(1 for a in active_alerts if a.severity == "INFO")

        return AlertSummary(
            total_active=len(active_alerts),
            open_count=open_count,
            acknowledged_count=ack_count,
            critical_count=crit_count,
            warning_count=warn_count,
            info_count=info_count
        )

alert_repo = AlertRepository()
