"""Pydantic schemas for Health API"""
from pydantic import BaseModel
from typing import Dict, Any

class HealthResponse(BaseModel):
    status: str
    version: str
    telemetry_status: str
    details: Dict[str, Any]
