"""Authentication and authorization for API access.

Provides API key-based bearer token authentication that:
- Fails closed: authentication required when API_KEY is configured
- Allows local dev without auth: optional in development
- Simple but extensible: easy to add RBAC later
"""

import logging
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

logger = logging.getLogger(__name__)

# Use HTTPBearer with auto_error=False to control our own error handling
security_scheme = HTTPBearer(auto_error=False)


class AuthenticationError(HTTPException):
    """Raised when authentication fails."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> Optional[str]:
    """Validate bearer token API key.

    Returns the API key if valid, None if no auth configured and no credentials provided.
    Raises AuthenticationError if authentication is required but invalid/missing.

    Behavior by environment:
    - No API_KEY configured: No authentication required (local dev)
    - API_KEY configured: Valid bearer token required (staging/production)
    """
    settings = get_settings()
    configured_key = getattr(settings, "api_key", None)

    # No API key configured = no authentication required (local dev mode)
    if not configured_key:
        logger.debug("auth_disabled_no_key_configured")
        return None

    # API key configured but no credentials provided
    if credentials is None:
        logger.warning("auth_required_no_credentials")
        raise AuthenticationError("Bearer token required")

    # Validate bearer token format
    token = credentials.credentials

    # Use secrets.compare_digest for timing attack resistance
    if not secrets.compare_digest(token, configured_key):
        logger.warning("auth_invalid_token")
        raise AuthenticationError("Invalid API key")

    logger.debug("auth_success")
    return token


# Require authentication for protected endpoints
require_auth = Depends(get_current_api_key)


# For endpoints that need auth but want to handle their own error messages
async def require_authenticated(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> str:
    """Strictly require authentication. Fails closed always."""
    settings = get_settings()
    configured_key = getattr(settings, "api_key", None)

    if not configured_key:
        # Even if no key configured, in strict mode we require one
        logger.error("auth_misconfigured_no_key_in_strict_mode")
        raise AuthenticationError("Authentication misconfigured")

    if credentials is None:
        raise AuthenticationError("Bearer token required")

    token = credentials.credentials
    if not secrets.compare_digest(token, configured_key):
        raise AuthenticationError("Invalid API key")

    return token


strict_auth = Depends(require_authenticated)
