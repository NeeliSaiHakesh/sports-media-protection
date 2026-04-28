"""
watermark.py — PIL-based digital watermarking engine
Provides:
  - visible_watermark(): overlays copyright text + semi-transparent banner
  - extract_exif(): returns key EXIF metadata from an image
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ExifTags


# ── Visible Watermark ─────────────────────────────────────────────────────────

def visible_watermark(
    image_path: str,
    owner_name: str = "Media Guard AI",
    opacity: int = 180,
    position: str = "bottom-right",
) -> bytes:
    """
    Add a professional visible copyright watermark to an image.

    Returns the watermarked image as JPEG bytes.
    """
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size

    # ── Build transparent overlay ──────────────────────────
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Text content
    text = f"© {owner_name}"
    sub_text = "Protected by Media Guard AI"

    # Font size relative to image size
    font_size = max(16, int(min(W, H) * 0.035))
    sub_size  = max(11, int(font_size * 0.65))

    try:
        font     = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sub_size)
    except Exception:
        font     = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # Measure text bounding box
    bb  = draw.textbbox((0, 0), text,     font=font)
    bbs = draw.textbbox((0, 0), sub_text, font=sub_font)
    tw, th   = bb[2] - bb[0],   bb[3] - bb[1]
    stw, sth = bbs[2] - bbs[0], bbs[3] - bbs[1]

    pad_x, pad_y = 20, 14
    block_w = max(tw, stw) + pad_x * 2
    block_h = th + sth + pad_y * 2 + 6

    # Position
    margin = max(16, int(min(W, H) * 0.025))
    pos_dict = {
        "bottom-right": (W - block_w - margin, H - block_h - margin),
        "bottom-left":  (margin, H - block_h - margin),
        "top-right":    (W - block_w - margin, margin),
        "top-left":     (margin, margin),
        "center":       ((W - block_w) // 2, (H - block_h) // 2),
    }
    x, y = pos_dict.get(position, pos_dict["bottom-right"])

    # Background rectangle
    bg_color = (10, 10, 20, opacity)
    draw.rectangle([x, y, x + block_w, y + block_h], fill=bg_color, outline=(255,255,255,80), width=1)

    # Main copyright text
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=(255, 255, 255, 240))
    # Sub text
    draw.text((x + pad_x, y + pad_y + th + 6), sub_text, font=sub_font, fill=(180, 190, 210, 200))

    # Composite
    watermarked = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    watermarked.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ── Diagonal tiled watermark (subtle, covers whole image) ─────────────────────

def tiled_watermark(image_path: str, owner_name: str = "Media Guard AI") -> bytes:
    """Add a subtle diagonal tiled watermark across the entire image."""
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = f"© {owner_name} · Media Guard AI"
    font_size = max(12, int(min(W, H) * 0.022))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except Exception:
        font = ImageFont.load_default()

    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]

    step_x = max(tw + 60, int(W / 4))
    step_y = step_x

    import math
    angle = 35

    for row in range(-2, int(H / step_y) + 3):
        for col in range(-2, int(W / step_x) + 3):
            cx = col * step_x + (row % 2) * step_x // 2
            cy = row * step_y

            # Create tiny text tile
            tile = Image.new("RGBA", (tw + 20, font_size + 10), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(tile)
            tdraw.text((10, 5), text, font=font, fill=(200, 210, 230, 45))

            rotated = tile.rotate(angle, expand=True)
            rx, ry = rotated.size
            paste_x = cx - rx // 2
            paste_y = cy - ry // 2
            overlay.paste(rotated, (paste_x, paste_y), rotated)

    watermarked = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    watermarked.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


# ── EXIF Extractor ────────────────────────────────────────────────────────────

def extract_exif(image_path: str) -> dict:
    """
    Extract human-readable EXIF metadata from an image.
    Returns dict of tag_name → value. Empty dict if no EXIF.
    """
    try:
        img = Image.open(image_path)
        raw = img._getexif()
        if not raw:
            return {}

        WANTED = {
            "Make", "Model", "Software", "DateTime",
            "DateTimeOriginal", "ExposureTime", "FNumber",
            "ISOSpeedRatings", "FocalLength", "Orientation",
            "GPSInfo", "LensModel", "Artist", "Copyright",
            "ImageDescription",
        }

        result = {}
        tags = {v: k for k, v in ExifTags.TAGS.items()}

        for tag_name in WANTED:
            tag_id = tags.get(tag_name)
            if tag_id and tag_id in raw:
                val = raw[tag_id]
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", errors="ignore").strip()
                    except Exception:
                        continue
                if tag_name == "GPSInfo" and isinstance(val, dict):
                    val = _decode_gps(val)
                if val:
                    result[tag_name] = str(val)

        return result
    except Exception:
        return {}


def _decode_gps(gps_info: dict) -> Optional[str]:
    """Convert raw GPSInfo dict to lat/lon string."""
    try:
        def to_deg(val):
            d, m, s = val
            return float(d) + float(m) / 60 + float(s) / 3600

        lat  = to_deg(gps_info.get(2, ((0,1),(0,1),(0,1))))
        lon  = to_deg(gps_info.get(4, ((0,1),(0,1),(0,1))))
        lat_ref = gps_info.get(1, "N")
        lon_ref = gps_info.get(3, "E")
        if lat_ref == "S": lat = -lat
        if lon_ref == "W": lon = -lon
        return f"{lat:.6f}, {lon:.6f}"
    except Exception:
        return None
