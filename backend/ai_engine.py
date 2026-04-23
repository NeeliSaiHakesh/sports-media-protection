"""
ai_engine.py — CLIP-based AI image embedding engine
Uses OpenAI CLIP (ViT-B/32) via Hugging Face transformers for semantic
image similarity. Works fully offline after first model download (~350MB).
"""
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Model config ──────────────────────────────────────────────────────────────
CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
EMBEDDING_DIM  = 512  # ViT-B/32 embedding dimension

# ── Lazy-loaded singletons ─────────────────────────────────────────────────────
_model     = None
_processor = None
_device    = "cpu"
_available = None   # None = not yet checked, True/False = result


def _try_load_clip() -> bool:
    """Attempt to load the CLIP model. Returns True on success."""
    global _model, _processor, _device, _available
    if _available is not None:
        return _available
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading CLIP model {CLIP_MODEL_ID} on {_device}…")

        _processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
        _model     = CLIPModel.from_pretrained(CLIP_MODEL_ID).to(_device)
        _model.eval()

        _available = True
        logger.info("✅ CLIP model loaded successfully")
    except Exception as exc:
        logger.warning(f"⚠️  CLIP unavailable — falling back to hash-only: {exc}")
        _available = False
    return _available


def get_status() -> dict:
    """Return AI engine status dict (called by /ai/status endpoint)."""
    loaded = _try_load_clip()
    return {
        "available": loaded,
        "model":     CLIP_MODEL_ID if loaded else None,
        "device":    _device       if loaded else None,
        "mode":      "CLIP + Hash hybrid (70/30)" if loaded else "Hash-only fallback",
    }


# ── Core functions ─────────────────────────────────────────────────────────────

def generate_embedding(image_path: str) -> Optional[List[float]]:
    """
    Generate a 512-dim CLIP embedding for an image file.
    Returns a normalized float list, or None if CLIP is unavailable.
    """
    if not _try_load_clip():
        return None
    try:
        import torch
        img = Image.open(image_path).convert("RGB")
        inputs = _processor(images=img, return_tensors="pt").to(_device)
        with torch.no_grad():
            features = _model.get_image_features(**inputs)
            # L2-normalize so cosine sim == dot product
            features = features / features.norm(dim=-1, keepdim=True)
        return features[0].cpu().tolist()
    except Exception as exc:
        logger.warning(f"Embedding generation failed for {image_path}: {exc}")
        return None


def cosine_similarity(emb1: List[float], emb2: List[float]) -> float:
    """
    Cosine similarity between two normalized embeddings → 0–100%.
    Both vectors must already be L2-normalized (generate_embedding returns them that way).
    """
    v1 = np.array(emb1, dtype=np.float32)
    v2 = np.array(emb2, dtype=np.float32)
    # Dot product of unit vectors == cosine similarity; clamp to [0, 1]
    dot = float(np.dot(v1, v2))
    sim = max(0.0, dot)          # CLIP similarities are always positive in practice
    return round(sim * 100, 2)   # → percentage


def hybrid_similarity(clip_sim: float, hash_sim: float,
                       clip_weight: float = 0.70) -> float:
    """
    Blend CLIP similarity and hash-based similarity.
    Default: 70% CLIP + 30% hash.
    """
    hash_weight = 1.0 - clip_weight
    blended = clip_sim * clip_weight + hash_sim * hash_weight
    return round(blended, 2)


def embedding_to_json(embedding: List[float]) -> str:
    """Serialise embedding list to compact JSON string for DB storage."""
    return json.dumps(embedding, separators=(",", ":"))


def json_to_embedding(json_str: str) -> Optional[List[float]]:
    """Deserialise embedding from DB JSON string."""
    try:
        return json.loads(json_str)
    except Exception:
        return None
