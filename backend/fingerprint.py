"""
fingerprint.py — Perceptual hashing engine (kept for hybrid AI+hash scoring)
Uses average_hash (pure-PIL, no scipy dependency) for robust visual similarity.
CLIP AI embeddings are handled by ai_engine.py — this module provides the
hash component of the 70% CLIP / 30% hash hybrid score.
"""
from PIL import Image
import imagehash


# ── Classification thresholds (tightened for CLIP hybrid accuracy) ────────────
ORIGINAL_MAX   = 55   # 0–55  → Original  (was 60)
SUSPICIOUS_MAX = 82   # 55–82 → Suspicious (was 85)
                       # 82+   → Copied

# ── Platform risk weights ─────────────────────────────────────────────────────
PLATFORM_WEIGHTS = {
    "YouTube":   1.5,
    "Instagram": 1.2,
    "Twitter":   1.1,
    "Facebook":  1.1,
    "Unknown":   1.0,
}

MAX_HASH_DISTANCE = 64  # pHash produces 64-bit hashes


def generate_hash(image_path: str, algorithm: str = "average") -> str:
    """Generate a perceptual hash string for an image file.

    algorithm: 'average' (default), 'difference', or 'color'
    All three work without scipy / numpy dependencies.
    """
    img = Image.open(image_path).convert("RGB")
    algo = (algorithm or "average").lower()
    if algo == "difference":
        h = imagehash.dhash(img)
    elif algo == "color":
        h = imagehash.colorhash(img)
    else:
        h = imagehash.average_hash(img)
    return str(h)


def hash_distance(hash1_str: str, hash2_str: str) -> int:
    """Compute the Hamming distance between two hash strings."""
    h1 = imagehash.hex_to_hash(hash1_str)
    h2 = imagehash.hex_to_hash(hash2_str)
    return h1 - h2


def similarity_percentage(distance: int) -> float:
    """Convert Hamming distance → similarity % (0–100)."""
    sim = max(0.0, (1.0 - distance / MAX_HASH_DISTANCE)) * 100
    return round(sim, 2)


def classify(similarity: float) -> str:
    """Classify similarity into: Original / Suspicious / Copied."""
    if similarity >= SUSPICIOUS_MAX:
        return "Copied"
    elif similarity >= ORIGINAL_MAX:
        return "Suspicious"
    else:
        return "Original"


def compute_risk_score(similarity: float, platform: str = "Unknown") -> float:
    """
    risk_score = similarity × platform_weight, capped at 100.
    """
    weight = PLATFORM_WEIGHTS.get(platform, PLATFORM_WEIGHTS["Unknown"])
    score = similarity * weight
    return round(min(score, 100.0), 2)


def compute_confidence(similarity: float, num_matches: int,
                       ai_available: bool = False) -> float:
    """
    Confidence derived from similarity strength and match count.
    Higher similarity + more matches → higher confidence.
    AI mode gets a +5% confidence bonus for accuracy.
    """
    base = similarity / 100.0
    match_factor = min(num_matches / 5.0, 1.0)  # saturates at 5 matches
    # Blend: 70% similarity, 30% match volume
    confidence = (base * 0.7 + match_factor * 0.3) * 100
    if ai_available:
        confidence = min(confidence + 5.0, 100.0)
    return round(min(confidence, 100.0), 2)
