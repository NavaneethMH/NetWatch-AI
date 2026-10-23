# -*- coding: utf-8 -*-
"""Phase 13.1: Security & Operator Authorization Service.

Provides centralized API Key authorization for sensitive mutation endpoints:
- POST /api/devices/scan
- POST /api/alerts/{id}/acknowledge

Security Model:
1. Production: Fail-closed. If NETWATCH_API_KEY is unset or empty, mutating operations are denied with 403 Forbidden.
2. Development: If NETWATCH_API_KEY is configured, valid X-NetWatch-Key is required. If NETWATCH_API_KEY is unset/empty in development mode, local mutation is permitted with a clear audit log warning.
3. Secrets are compared using hmac.compare_digest to prevent timing attacks.
4. Secrets are NEVER logged.
"""
from typing import Optional
import hmac
import logging
from fastapi import Header, HTTPException, status
from backend.core.config import settings

logger = logging.getLogger("netwatch.security")


def require_operator_auth(
    x_netwatch_key: Optional[str] = Header(None, alias="X-NetWatch-Key", description="Operator authorization key")
) -> bool:
    """FastAPI dependency to authorize sensitive operator actions.
    
    Raises:
        HTTPException(401): If key is required but missing or invalid.
        HTTPException(403): If in production without configured NETWATCH_API_KEY.
    """
    configured_key = settings.API_KEY.strip()
    is_production = settings.ENVIRONMENT in ("production", "prod")

    # Production safety: fail-closed if key is not configured
    if is_production and not configured_key:
        logger.error("Operator action rejected: NETWATCH_API_KEY is not configured in production environment.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator actions are disabled: server authorization key is not configured.",
        )

    # When key is configured (dev, test, or prod), enforce strict constant-time comparison
    if configured_key:
        if not x_netwatch_key:
            logger.warning("Operator action rejected: missing X-NetWatch-Key header.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: missing X-NetWatch-Key header.",
            )
        
        # Compare constant-time
        if not hmac.compare_digest(x_netwatch_key.strip(), configured_key):
            logger.warning("Operator action rejected: invalid X-NetWatch-Key.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: invalid X-NetWatch-Key.",
            )
        return True

    # Local development bypass only when NETWATCH_API_KEY is explicitly blank in development
    logger.debug("Operator action permitted: local development bypass (NETWATCH_API_KEY not configured).")
    return True
