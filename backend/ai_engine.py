"""
ai_engine.py — Multi-model AI engine: CLIP ViT-B/32 + DINOv2-small + GradCAM
Final score = 50% CLIP + 30% DINOv2 + 20% hash

Models:
  - openai/clip-vit-base-patch32  (~350MB, 512-dim, semantic understanding)
  - facebook/dinov2-small          (~85MB,  384-dim, visual structure)
"""
import base64
import io
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Model config ──────────────────────────────────────────────────────────────
CLIP_MODEL_ID = "openai/clip-vit-base-patch32"
DINO_MODEL_ID = "facebook/dinov2-small"
CLIP_DIM      = 512
DINO_DIM      = 384

# Blend weights (must sum to 1.0)
CLIP_WEIGHT = 0.50
DINO_WEIGHT = 0.30
HASH_WEIGHT = 0.20

# ── Lazy singletons ─────────────────────────────────────────────────────────
_clip_model     = None
_clip_processor = None
_dino_model     = None
_dino_processor = None
_device         = "cpu"
_clip_available = None
_dino_available = None


def _try_load_clip() -> bool:
    global _clip_model, _clip_processor, _device, _clip_available
    if _clip_available is not None:
        return _clip_available
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading CLIP {CLIP_MODEL_ID} on {_device}…")
        _clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
        _clip_model     = CLIPModel.from_pretrained(CLIP_MODEL_ID).to(_device)
        _clip_model.eval()
        _clip_available = True
        logger.info("✅ CLIP loaded")
    except Exception as exc:
        logger.warning(f"⚠️  CLIP unavailable: {exc}")
        _clip_available = False
    return _clip_available


def _try_load_dino() -> bool:
    global _dino_model, _dino_processor, _dino_available
    if _dino_available is not None:
        return _dino_available
    try:
        import torch
        logger.info(f"Loading DINOv2 {DINO_MODEL_ID}…")
        # Try multiple processor classes for compatibility across transformers versions
        try:
            from transformers import AutoImageProcessor
            _dino_processor = AutoImageProcessor.from_pretrained(DINO_MODEL_ID)
        except (ImportError, AttributeError):
            try:
                from transformers import ViTImageProcessor
                _dino_processor = ViTImageProcessor.from_pretrained(DINO_MODEL_ID)
            except Exception:
                from transformers import BitImageProcessor
                _dino_processor = BitImageProcessor.from_pretrained(DINO_MODEL_ID)
        from transformers import AutoModel
        _dino_model     = AutoModel.from_pretrained(DINO_MODEL_ID).to(_device)
        _dino_model.eval()
        _dino_available = True
        logger.info("✅ DINOv2 loaded")
    except Exception as exc:
        logger.warning(f"⚠️  DINOv2 unavailable: {exc}")
        _dino_available = False
    return _dino_available


def get_status() -> dict:
    clip_ok = _try_load_clip()
    dino_ok = _try_load_dino()
    active_models = []
    weights_desc  = ""
    if clip_ok: active_models.append("CLIP ViT-B/32")
    if dino_ok: active_models.append("DINOv2-small")
    if clip_ok and dino_ok:
        weights_desc = f"CLIP {int(CLIP_WEIGHT*100)}% + DINO {int(DINO_WEIGHT*100)}% + Hash {int(HASH_WEIGHT*100)}%"
    elif clip_ok:
        weights_desc = "CLIP 70% + Hash 30%"
    else:
        weights_desc = "Hash-only fallback"
    return {
        "available":    clip_ok,
        "dino_available": dino_ok,
        "model":        CLIP_MODEL_ID if clip_ok else None,
        "dino_model":   DINO_MODEL_ID if dino_ok else None,
        "device":       _device       if clip_ok else None,
        "mode":         weights_desc,
        "models":       active_models,
    }


# ── CLIP embedding ────────────────────────────────────────────────────────────

def generate_embedding(image_path: str) -> Optional[List[float]]:
    """512-dim L2-normalized CLIP embedding."""
    if not _try_load_clip():
        return None
    try:
        import torch
        img     = Image.open(image_path).convert("RGB")
        inputs  = _clip_processor(images=img, return_tensors="pt").to(_device)
        with torch.no_grad():
            feat = _clip_model.get_image_features(**inputs)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        return feat[0].cpu().tolist()
    except Exception as exc:
        logger.warning(f"CLIP embedding failed: {exc}")
        return None


# ── DINOv2 embedding ──────────────────────────────────────────────────────────

def generate_dino_embedding(image_path: str) -> Optional[List[float]]:
    """384-dim L2-normalized DINOv2 embedding (CLS token)."""
    if not _try_load_dino():
        return None
    try:
        import torch
        img    = Image.open(image_path).convert("RGB")
        inputs = _dino_processor(images=img, return_tensors="pt").to(_device)
        with torch.no_grad():
            out  = _dino_model(**inputs)
            feat = out.last_hidden_state[:, 0, :]  # CLS token
            feat = feat / feat.norm(dim=-1, keepdim=True)
        return feat[0].cpu().tolist()
    except Exception as exc:
        logger.warning(f"DINOv2 embedding failed: {exc}")
        return None


# ── Similarity ────────────────────────────────────────────────────────────────

def cosine_similarity(emb1: List[float], emb2: List[float]) -> float:
    v1  = np.array(emb1, dtype=np.float32)
    v2  = np.array(emb2, dtype=np.float32)
    dot = float(np.dot(v1, v2))
    return round(max(0.0, dot) * 100, 2)


def hybrid_similarity(clip_sim: float, hash_sim: float,
                       dino_sim: float = 0.0) -> float:
    """
    Blend: 50% CLIP + 30% DINO + 20% hash  (when DINO available)
           70% CLIP + 30% hash              (CLIP only)
    """
    if _dino_available and dino_sim > 0:
        return round(clip_sim * CLIP_WEIGHT + dino_sim * DINO_WEIGHT + hash_sim * HASH_WEIGHT, 2)
    # Fallback to 70/30 CLIP+hash
    return round(clip_sim * 0.70 + hash_sim * 0.30, 2)


# ── GradCAM heatmap ───────────────────────────────────────────────────────────

def generate_gradcam_heatmap(image_path: str) -> Optional[str]:
    """
    Generate a GradCAM-style attention heatmap using CLIP's vision transformer.
    Returns a base64-encoded PNG of the original image with heatmap overlay,
    or None if CLIP is unavailable.
    """
    if not _try_load_clip():
        return None
    try:
        import torch
        import torch.nn.functional as F

        img_pil = Image.open(image_path).convert("RGB")
        orig_w, orig_h = img_pil.size

        inputs = _clip_processor(images=img_pil, return_tensors="pt").to(_device)
        pixel_values = inputs["pixel_values"].requires_grad_(True)

        # Forward pass through CLIP vision encoder
        vision_outputs = _clip_model.vision_model(pixel_values=pixel_values)
        # Use CLS token output norm as the "score"
        cls_output = vision_outputs.last_hidden_state[:, 0, :]
        score = cls_output.norm()
        score.backward()

        # Gradients of CLS w.r.t. patch tokens
        grads  = pixel_values.grad[0]                  # [3, H, W]
        cam    = grads.abs().mean(dim=0)               # [H, W]
        cam    = cam.detach().cpu().numpy()
        cam    = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

        # Resize cam to original image size
        cam_img = Image.fromarray((cam * 255).astype("uint8")).resize(
            (orig_w, orig_h), Image.BILINEAR
        )
        cam_arr = np.array(cam_img, dtype=np.float32) / 255.0

        # Colorize: blue→yellow→red  (matplotlib 'hot' style)
        r = np.clip(cam_arr * 2.0,       0, 1)
        g = np.clip(cam_arr * 2.0 - 0.5, 0, 1)
        b = np.clip(1.0 - cam_arr * 2.0, 0, 1)
        colormap = np.stack([r, g, b], axis=-1)
        colormap_pil = Image.fromarray((colormap * 255).astype("uint8"))

        # Blend with original
        orig_arr = np.array(img_pil.resize((orig_w, orig_h)), dtype=np.float32) / 255.0
        heat_arr = np.array(colormap_pil.resize((orig_w, orig_h)), dtype=np.float32) / 255.0
        alpha    = (cam_arr[..., None] * 0.55)           # 0–55% overlay strength
        blended  = orig_arr * (1 - alpha) + heat_arr * alpha
        blended  = np.clip(blended * 255, 0, 255).astype("uint8")
        result   = Image.fromarray(blended)

        buf = io.BytesIO()
        result.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{b64}"

    except Exception as exc:
        logger.warning(f"GradCAM failed: {exc}")
        return None


# ── Serialization helpers ─────────────────────────────────────────────────────

def embedding_to_json(embedding: List[float]) -> str:
    return json.dumps(embedding, separators=(",", ":"))


def json_to_embedding(json_str: str) -> Optional[List[float]]:
    try:
        return json.loads(json_str)
    except Exception:
        return None
