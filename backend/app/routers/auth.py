"""
auth.py — Login endpoint and current-identity lookup.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import create_access_token, get_current_user, verify_credentials
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    subject = verify_credentials(payload.username, payload.password)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token, expires_in = create_access_token(subject)
    return TokenResponse(access_token=token, expires_in=expires_in, user=subject)


@router.get("/me")
def me(current_user: str = Depends(get_current_user)):
    """Cheap endpoint for the frontend to check whether its token is still valid."""
    return {"user": current_user}
