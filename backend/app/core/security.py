"""
security.py — Authentication core (isolated, swappable).

This module owns everything about *proving who you are*:
  - verifying credentials         -> verify_credentials()
  - minting a signed token        -> create_access_token()
  - guarding routes with a token  -> get_current_user() (FastAPI dependency)

CURRENT MODE: a single shared password (AUTH_PASSWORD). The token itself
carries a ``sub`` (subject) claim, so upgrading to per-user logins later is a
localized change: swap the body of ``verify_credentials`` to look the user up
in a table and check a hashed password, and return their username as the
subject. The token layer, the route guard, and every protected router stay
exactly as they are.
"""

import hmac
import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import (
    AUTH_ALGORITHM,
    AUTH_PASSWORD,
    AUTH_SECRET_KEY,
    AUTH_TOKEN_EXPIRE_MINUTES,
    INSECURE_SECRET_DEFAULT,
)

logger = logging.getLogger(__name__)


def check_startup_security() -> list[str]:
    """
    Return a list of security misconfigurations found at startup (empty means
    all good). The app factory decides what to do with them: fatal in
    production, logged warnings in development (see app.main.create_app).

    Reads the module-level config values so tests that monkeypatch them (see
    tests/conftest.py) are reflected here.
    """
    problems: list[str] = []
    if not AUTH_PASSWORD:
        problems.append("AUTH_PASSWORD is not set — logins cannot succeed.")
    if not AUTH_SECRET_KEY or AUTH_SECRET_KEY == INSECURE_SECRET_DEFAULT:
        problems.append(
            "AUTH_SECRET_KEY is missing or still the insecure default — "
            "set a strong random value."
        )
    return problems

# auto_error=False so we can return a consistent JSON 401 instead of the
# default terse error when the Authorization header is missing.
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_credentials(username: str, password: str) -> str | None:
    """
    Validate a login attempt.

    Returns the authenticated *subject* (identity string) on success, or
    ``None`` on failure.

    Shared-password mode: ``username`` is accepted but not required; only the
    password is checked (constant-time). To move to per-user accounts, replace
    the body below with a users-table lookup + hashed-password verification and
    return the real username.
    """
    if not AUTH_PASSWORD:
        logger.warning("Login attempt but AUTH_PASSWORD is not configured.")
        return None
    if hmac.compare_digest(password or "", AUTH_PASSWORD):
        return username or "pharmacist"
    return None


def create_access_token(subject: str) -> tuple[str, int]:
    """Mint a signed JWT for ``subject``. Returns (token, expires_in_seconds)."""
    expires_in = AUTH_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=AUTH_TOKEN_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, AUTH_SECRET_KEY, algorithm=AUTH_ALGORITHM)
    return token, expires_in


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency that rejects unauthenticated requests.

    Attach it to any route/router to require a valid bearer token; it returns
    the token subject (the current identity) for handlers that want it.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            AUTH_SECRET_KEY,
            algorithms=[AUTH_ALGORITHM],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if not subject:
        raise unauthorized
    return subject
