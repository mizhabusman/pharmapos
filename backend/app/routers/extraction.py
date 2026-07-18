"""
extraction.py — Prescription image -> structured data via Gemini OCR.
"""

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.config import GEMINI_API_KEY, MAX_UPLOAD_BYTES
from app.services.gemini_extractor import run_extraction
from app.services.image_processor import optimize_for_upload

router = APIRouter(tags=["extraction"])

_MAX_MB = MAX_UPLOAD_BYTES // (1024 * 1024)


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

    # Reject oversized uploads early (defence-in-depth; a global body-size
    # middleware also runs) so a huge image can't exhaust memory.
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"message": f"Image is too large (max {_MAX_MB} MB)."},
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=400,
            detail={"message": "The uploaded file is empty"},
        )
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"message": f"Image is too large (max {_MAX_MB} MB)."},
        )

    # Decode/compress in a worker thread — Pillow is CPU-bound and would freeze
    # the event loop (starving every other request) if run inline. A corrupt or
    # unreadable image is a client error (400).
    try:
        compressed_bytes = await run_in_threadpool(optimize_for_upload, raw_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Could not read the image", "error": str(exc)},
        ) from exc

    # The Gemini call is a blocking network request — offload it too so the
    # event loop stays responsive. An upstream/Gemini failure is a 502.
    try:
        return await run_in_threadpool(run_extraction, compressed_bytes, GEMINI_API_KEY)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Prescription extraction failed",
                "error": str(exc),
            },
        ) from exc
