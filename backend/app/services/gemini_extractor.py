import json
import google.generativeai as genai
from app.services.prompts import PHARMACIST_EXTRACTION


def run_extraction(image_bytes: bytes, api_key: str) -> dict:
    """Sends compressed image to Gemini and calculates token usage metrics."""
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-2.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )

        full_prompt = PHARMACIST_EXTRACTION + """
        Return EXACTLY this JSON — no other text:
        {"patient_name": "string", "age": 0, "gender": "string", "medicines": [{"name": "string", "suggested_qty": 1}]}
        """
        picture = {"mime_type": "image/jpeg", "data": image_bytes}
        resp = model.generate_content([picture, full_prompt])

        metadata = resp.usage_metadata
        input_tokens = metadata.prompt_token_count
        output_tokens = metadata.candidates_token_count
        total_tokens = metadata.total_token_count

        INPUT_PRICE_PER_1M = 0.075
        OUTPUT_PRICE_PER_1M = 0.30
        INR_CONVERSION_RATE = 83.5

        input_cost = (input_tokens / 1_000_000) * INPUT_PRICE_PER_1M
        output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_1M
        total_usd = input_cost + output_cost
        total_inr = total_usd * INR_CONVERSION_RATE

        return {
            "extracted_data": json.loads(resp.text),
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