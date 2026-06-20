"""
image_processor.py — Image preprocessing for PharmaPOS.

Handles resizing and compression of prescription images before they are
sent to the Gemini API, reducing both upload bandwidth and token usage.
"""

from PIL import Image
import io


def optimize_for_upload(
    image_bytes: bytes,
    max_dimension: int = 1500,
    jpeg_quality: int = 80,
) -> bytes:
    """
    Resize and re-encode an image for efficient API upload.

    Args:
        image_bytes:   Raw image bytes (any Pillow-supported format).
        max_dimension:  Longest side, in pixels, after resizing.
                        Keeps aspect ratio. Prescription handwriting stays
                        legible at 1500px; lower for faster/cheaper uploads,
                        raise if OCR misreads increase.
        jpeg_quality:  JPEG quality (0-100). 80 is a good legibility/size
                        balance for text-heavy images.

    Returns:
        Re-encoded JPEG bytes.

    Raises:
        ValueError: if image_bytes cannot be decoded as an image.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()   # force decode now, so corrupt files fail here, not later
    except Exception as e:
        raise ValueError(f"optimize_for_upload: could not decode image — {e}") from e

    if img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail(
        (max_dimension, max_dimension),
        Image.Resampling.LANCZOS
    )

    buffer = io.BytesIO()
    img.save(
        buffer,
        format="JPEG",
        quality=jpeg_quality,
        optimize=True
    )

    return buffer.getvalue()