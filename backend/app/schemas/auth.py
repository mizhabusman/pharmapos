"""
auth.py — Request/response models for the login flow.
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    # username is optional today (shared-password mode) but already part of the
    # contract so per-user login needs no client change later.
    username: str = ""
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds until the token expires
    user: str                # the authenticated subject
