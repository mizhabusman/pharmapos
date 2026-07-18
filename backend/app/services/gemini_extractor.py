import json
import google.generativeai as genai
from app.services.prompts import PHARMACIST_EXTRACTION
from app.core.config import (
    GEMINI_MODEL,
    GEMINI_INPUT_PRICE_PER_1M,
    GEMINI_OUTPUT_PRICE_PER_1M,
    INR_CONVERSION_RATE,
    GEMINI_TIMEOUT_SECONDS,
)


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalise_extracted(raw) -> dict:
    """
    Coerce whatever Gemini returned into the exact shape the frontend expects,
    so a non-prescription photo (e.g. {"error": ...} or medicines: null) or a
    non-integer suggested_qty can never crash the UI or the /billing call.
    Guarantees: patient_name/gender are strings, age is an int, medicines is a
    list of {name: non-empty str, suggested_qty: int >= 1}.
    """
    if not isinstance(raw, dict):
        raw = {}

    medicines = []
    for med in raw.get("medicines") or []:
        if not isinstance(med, dict):
            continue
        name = str(med.get("name", "") or "").strip()
        if not name:
            continue
        medicines.append({
            "name": name,
            "suggested_qty": max(1, _coerce_int(med.get("suggested_qty", 1), 1)),
        })

    return {
        "patient_name": str(raw.get("patient_name", "") or ""),
        "age": max(0, _coerce_int(raw.get("age", 0), 0)),
        "gender": str(raw.get("gender", "") or ""),
        "medicines": medicines,
    }


def run_extraction(image_bytes: bytes, api_key: str) -> dict:
    """Sends compressed image to Gemini and calculates token usage metrics."""
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={"response_mime_type": "application/json"}
        )

        full_prompt = PHARMACIST_EXTRACTION + """
        Return EXACTLY this JSON — no other text:
        {"patient_name": "string", "age": 0, "gender": "string", "medicines": [{"name": "string", "suggested_qty": 1}]}
        """
        picture = {"mime_type": "image/jpeg", "data": image_bytes}
        resp = model.generate_content(
            [picture, full_prompt],
            request_options={"timeout": GEMINI_TIMEOUT_SECONDS},
        )

        metadata = resp.usage_metadata
        input_tokens = metadata.prompt_token_count
        output_tokens = metadata.candidates_token_count
        total_tokens = metadata.total_token_count

        input_cost = (input_tokens / 1_000_000) * GEMINI_INPUT_PRICE_PER_1M
        output_cost = (output_tokens / 1_000_000) * GEMINI_OUTPUT_PRICE_PER_1M
        total_usd = input_cost + output_cost
        total_inr = total_usd * INR_CONVERSION_RATE

        return {
            "extracted_data": _normalise_extracted(json.loads(resp.text)),
            "metrics": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": total_usd,
                "cost_inr": total_inr
            }
        }
    except Exception as exc:
        raise RuntimeError(f"Gemini extraction failed: {exc}") from exc