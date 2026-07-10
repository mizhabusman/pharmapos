"""
auth.py — Login endpoint and current-identity lookup.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.security import create_access_token, get_current_user, verify_credentials
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request):
    # Throttle brute-force attempts per client IP (see core/rate_limit.py).
    limiter = request.app.state.login_limiter
    client_ip = request.client.host if request.client else "unknown"

    retry_after = limiter.seconds_until_unblocked(client_ip)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    subject = verify_credentials(payload.username, payload.password)
    if not subject:
        limiter.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    limiter.reset(client_ip)  # clear the counter on a clean login
    token, expires_in = create_access_token(subject)
    return TokenResponse(access_token=token, expires_in=expires_in, user=subject)


@router.get("/me")
def me(current_user: str = Depends(get_current_user)):
    """Cheap endpoint for the frontend to check whether its token is still valid."""
    return {"user": current_user}
