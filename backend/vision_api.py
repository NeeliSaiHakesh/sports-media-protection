"""
vision_api.py — Google Cloud Vision API integration for web detection.
Finds where images appear across the internet — visually similar images,
pages containing the image, and best-guess labels.

Requires:
  pip install google-cloud-vision
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_vision_available = None
_client = None


def _try_load():
    """Lazily initialise the Vision API client."""
    global _vision_available, _client
    if _vision_available is not None:
        return _vision_available
    try:
        from google.cloud import vision
        # Check if credentials exist
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            logger.info("GOOGLE_APPLICATION_CREDENTIALS not set — Vision API disabled")
            _vision_available = False
            return False
        _client = vision.ImageAnnotatorClient()
        _vision_available = True
        logger.info("✅ Google Cloud Vision API loaded")
    except Exception as exc:
        logger.warning(f"⚠️  Vision API unavailable: {exc}")
        _vision_available = False
    return _vision_available


def is_available() -> bool:
    return _try_load()


def web_detect(image_path: str) -> Optional[dict]:
    """
    Run Google Vision web detection on a local image file.
    Returns a dict with:
      - pages_with_matching_images: [{url, page_title}, ...]
      - visually_similar_images: [{url}, ...]
      - full_matching_images: [{url}, ...]
      - best_guess_labels: [str, ...]
    """
    if not _try_load():
        return None

    from google.cloud import vision

    path = Path(image_path)
    if not path.exists():
        return None

    image = vision.Image(content=path.read_bytes())
    response = _client.web_detection(image=image)
    web = response.web_detection

    result = {
        "pages_with_matching_images": [],
        "visually_similar_images": [],
        "full_matching_images": [],
        "partial_matching_images": [],
        "best_guess_labels": [],
    }

    if web.pages_with_matching_images:
        for page in web.pages_with_matching_images:
            result["pages_with_matching_images"].append({
                "url": page.url,
                "page_title": page.page_title or "",
            })

    if web.visually_similar_images:
        for img in web.visually_similar_images:
            result["visually_similar_images"].append({"url": img.url})

    if web.full_matching_images:
        for img in web.full_matching_images:
            result["full_matching_images"].append({"url": img.url})

    if web.partial_matching_images:
        for img in web.partial_matching_images:
            result["partial_matching_images"].append({"url": img.url})

    if web.best_guess_labels:
        result["best_guess_labels"] = [lbl.label for lbl in web.best_guess_labels]

    return result


def label_detect(image_path: str, max_results: int = 10) -> Optional[list]:
    """Run label detection — returns [{"label": str, "score": float}, ...]."""
    if not _try_load():
        return None

    from google.cloud import vision

    path = Path(image_path)
    if not path.exists():
        return None

    image = vision.Image(content=path.read_bytes())
    response = _client.label_detection(image=image, max_results=max_results)

    return [
        {"label": label.description, "score": round(label.score * 100, 1)}
        for label in response.label_annotations
    ]


def safe_search(image_path: str) -> Optional[dict]:
    """Run safe search detection on an image."""
    if not _try_load():
        return None

    from google.cloud import vision

    path = Path(image_path)
    if not path.exists():
        return None

    image = vision.Image(content=path.read_bytes())
    response = _client.safe_search_detection(image=image)
    safe = response.safe_search_annotation

    likelihood_name = (
        "UNKNOWN", "VERY_UNLIKELY", "UNLIKELY", "POSSIBLE", "LIKELY", "VERY_LIKELY"
    )

    return {
        "adult": likelihood_name[safe.adult],
        "violence": likelihood_name[safe.violence],
        "racy": likelihood_name[safe.racy],
        "medical": likelihood_name[safe.medical],
        "spoof": likelihood_name[safe.spoof],
    }
