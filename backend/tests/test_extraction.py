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
