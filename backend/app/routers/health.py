"""
health.py — Liveness/health check route.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
def read_root():
    return {"message": "PharmaPOS backend is alive"}
