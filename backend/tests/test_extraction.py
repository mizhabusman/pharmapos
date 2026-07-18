"""
Integration tests for the /extract validation paths.

These exercise the guard rails *before* any real Gemini call, so they run
offline and never hit the network.
"""

import io


def _png_bytes():
    """A tiny valid 1x1 PNG so image decoding succeeds if reached."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_extract_rejects_non_image(client, monkeypatch):
    # Pretend the OCR key is present so we reach the content-type check.
    monkeypatch.setattr("app.routers.extraction.GEMINI_API_KEY", "test-key")
    r = client.post(
        "/extract",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
    assert "image" in r.json()["detail"]["message"].lower()


def test_extract_rejects_corrupt_image(client, monkeypatch):
    monkeypatch.setattr("app.routers.extraction.GEMINI_API_KEY", "test-key")
    # Correct content-type but the bytes are not a decodable image.
    r = client.post(
        "/extract",
        files={"file": ("x.png", b"not-a-real-image", "image/png")},
    )
    assert r.status_code == 400
    assert "could not read" in r.json()["detail"]["message"].lower()


def test_extract_returns_503_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr("app.routers.extraction.GEMINI_API_KEY", None)
    r = client.post(
        "/extract",
        files={"file": ("rx.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]["message"].lower()


def test_oversized_request_body_is_rejected_413(client):
    # The body-size middleware rejects a huge Content-Length before parsing.
    from app.core.config import MAX_UPLOAD_BYTES

    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post("/extract", files={"file": ("big.png", big, "image/png")})
    assert r.status_code == 413
    assert "too large" in r.json()["detail"]["message"].lower()


def test_normalise_extracted_coerces_gemini_output():
    # A non-prescription / malformed Gemini payload must never crash the UI:
    # medicines is always a list of {name:str, suggested_qty:int>=1}.
    from app.services.gemini_extractor import _normalise_extracted

    # medicines missing entirely
    assert _normalise_extracted({"error": "not a prescription"})["medicines"] == []
    # medicines null
    assert _normalise_extracted({"medicines": None})["medicines"] == []
    # non-integer qty, blank name filtered, floats coerced
    out = _normalise_extracted({
        "patient_name": "A", "age": "34", "gender": "Female",
        "medicines": [
            {"name": "Dolo 650", "suggested_qty": "2"},
            {"name": "  ", "suggested_qty": 5},       # blank -> dropped
            {"name": "Amox", "suggested_qty": 2.9},    # float -> int
            {"name": "Zero", "suggested_qty": 0},      # clamped to >= 1
        ],
    })
    assert out["age"] == 34
    assert out["medicines"] == [
        {"name": "Dolo 650", "suggested_qty": 2},
        {"name": "Amox", "suggested_qty": 2},
        {"name": "Zero", "suggested_qty": 1},
    ]
