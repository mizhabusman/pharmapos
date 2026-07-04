"""
extraction.py — Prescription image -> structured data via Gemini OCR.
"""

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.config import GEMINI_API_KEY
from app.services.gemini_extractor import run_extraction
from app.services.image_processor import optimize_for_upload

router = APIRouter(tags=["extraction"])


@router.post("/extract")
async def extract_prescription(file: UploadFile):
    raw_bytes = await file.read()
    compressed_bytes = optimize_for_upload(raw_bytes)

    try:
        result = run_extraction(compressed_bytes, GEMINI_API_KEY)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Prescription extraction failed",
                "error": str(exc),
            },
        ) from exc
