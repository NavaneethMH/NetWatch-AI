"""Network Health Score Schemas (Phase 8)"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ScoreDeduction(BaseModel):
    category: str
    reason: str
    points: int
    observed_value: Optional[str] = None

class HealthScoreResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    status: str  # HEALTHY, DEGRADED, POOR, CRITICAL
    timestamp: float
    timestamp_utc: str
    deductions: List[ScoreDeduction]
    telemetry_freshness: Dict[str, Any]
