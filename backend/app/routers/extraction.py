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
    # Fail clearly if the OCR service isn't configured (missing API key).
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "OCR service is not configured",
                "error": "GEMINI_API_KEY is not set on the server",
            },
        )

    # Only accept images — reject PDFs, docs, etc. with a helpful message.
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Please upload an image file (JPG, PNG, etc.)",
                "error": f"unsupported content type: {file.content_type}",
            },
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=400,
            detail={"message": "The uploaded file is empty"},
        )

    # Decode/compress — a corrupt or unreadable image is a client error (400).
    try:
        compressed_bytes = optimize_for_upload(raw_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Could not read the image", "error": str(exc)},
        ) from exc

    # Extraction itself — an upstream/Gemini failure is a gateway error (502).
    try:
        return run_extraction(compressed_bytes, GEMINI_API_KEY)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Prescription extraction failed",
                "error": str(exc),
            },
        ) from exc
