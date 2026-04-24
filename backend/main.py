"""
main.py — FastAPI application entrypoint for Digital Asset Protection Platform
"""
import csv
import io
import json
import os
import random
import shutil
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import aiosqlite
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

from database import DB_PATH, init_db
from fingerprint import (
    classify,
    compute_confidence,
    compute_risk_score,
    generate_hash,
    hash_distance,
    similarity_percentage,
)
from ai_engine import (
    get_status as ai_get_status,
    _try_load_clip,
    _try_load_dino,
    generate_gradcam_heatmap,
)
from legal import generate_dmca
from scanner import scan_asset
from watermark import extract_exif, visible_watermark, tiled_watermark

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
REFERENCE_DIR = UPLOAD_DIR / "reference"
UPLOAD_DIR.mkdir(exist_ok=True)
REFERENCE_DIR.mkdir(exist_ok=True)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Digital Asset Protection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    await seed_reference_db()
    # Pre-warm CLIP model in a thread so it doesn't block the first request
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _try_load_clip)
    loop.run_in_executor(None, _try_load_dino)



async def seed_reference_db():
    """
    Seed reference database with synthetic sports images using PIL.
    These serve as the 'known assets' that uploads are compared against.
    """
    from PIL import Image, ImageDraw, ImageFont
    import imagehash

    SPORTS = [
        ("Champions League Final 2024", "UEFA", "YouTube", "https://youtube.com/watch?v=cl2024", (30, 80, 180)),
        ("NBA Finals Game 7 Highlights", "NBA Media", "YouTube", "https://youtube.com/watch?v=nba7", (200, 40, 40)),
        ("FIFA World Cup Trophy Lift", "FIFA", "Instagram", "https://instagram.com/p/fifawc", (30, 150, 80)),
        ("Wimbledon Men's Final 2024", "Wimbledon", "Instagram", "https://instagram.com/p/wimb24", (0, 120, 200)),
        ("Super Bowl LVIII Halftime Show", "NFL Media", "YouTube", "https://youtube.com/watch?v=sb58", (150, 0, 200)),
        ("Tour de France Stage 21", "ASO", "Unknown", "https://letour.fr/stage21", (200, 130, 0)),
        ("Olympics 100m Sprint Final", "IOC", "YouTube", "https://youtube.com/watch?v=olym100", (180, 60, 0)),
        ("Premier League Goal of Season", "PL Media", "Instagram", "https://instagram.com/p/plgoal", (120, 0, 80)),
        ("Formula 1 Monaco Grand Prix", "F1 Media", "YouTube", "https://youtube.com/watch?v=f1monaco", (20, 180, 180)),
        ("Cricket World Cup Final 2024", "ICC", "Unknown", "https://icc-cricket.com/wc2024", (80, 160, 40)),
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) as cnt FROM assets WHERE is_reference = 1")
        row = await cur.fetchone()
        if row["cnt"] > 0:
            return  # Already seeded

    for idx, (name, owner, platform, url, color) in enumerate(SPORTS):
        img_path = REFERENCE_DIR / f"ref_{idx:02d}.jpg"
        # Create a synthetic but visually unique image
        img = Image.new("RGB", (640, 480), color=color)
        draw = ImageDraw.Draw(img)
        # Add some visual variety
        for i in range(0, 640, 40):
            draw.rectangle([i, 0, i + 20, 480], fill=tuple(max(0, c - 40) for c in color))
        # Draw text area
        draw.rectangle([40, 180, 600, 300], fill=(20, 20, 20, 180))
        draw.text((60, 200), name[:30], fill=(255, 255, 255))
        draw.text((60, 240), f"{owner} | {platform}", fill=(200, 200, 200))
        img.save(str(img_path), "JPEG", quality=85)

        img_hash = generate_hash(str(img_path))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO assets (filename, file_path, hash, source_url, platform, is_reference)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (f"{name}.jpg", str(img_path), img_hash, url, platform),
            )
            await db.commit()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Digital Asset Protection API"}


@app.get("/ai/status")
async def ai_status_endpoint():
    """Return current AI engine status — CLIP + DINOv2, model names, device."""
    return ai_get_status()


@app.get("/assets/{asset_id}/explain")
async def explain_asset(asset_id: int):
    """
    Generate a GradCAM heatmap for the given asset.
    Returns a base64 JPEG showing which regions triggered the AI match.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT file_path, filename FROM assets WHERE id = ?", (asset_id,)
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Asset not found")

    file_path = row["file_path"]
    if not Path(file_path).exists():
        raise HTTPException(404, "Asset file not found on disk")

    import asyncio
    loop  = asyncio.get_event_loop()
    heatmap = await loop.run_in_executor(None, generate_gradcam_heatmap, file_path)

    if not heatmap:
        raise HTTPException(503, "CLIP model not available for GradCAM")

    return {
        "asset_id": asset_id,
        "filename": row["filename"],
        "heatmap": heatmap,
        "explanation": (
            "Highlighted (red/orange) regions show where the CLIP neural network "
            "focused attention when comparing this image to the reference database. "
            "High-intensity areas contributed most to the similarity score."
        ),
    }


@app.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    source_url: str = Form(""),
    platform: str = Form("Unknown"),
    algorithm: str = Form("average"),
):
    """Upload a media file, fingerprint it, run scan, return full result."""
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, WebP, and GIF images are supported.")

    safe_name = Path(file.filename).name
    dest = UPLOAD_DIR / f"{random.randbytes(6).hex()}_{safe_name}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        img_hash = generate_hash(str(dest), algorithm=algorithm)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Could not process image: {e}")

    exif_data = extract_exif(str(dest))

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO assets (filename, file_path, hash, source_url, platform)
               VALUES (?, ?, ?, ?, ?)""",
            (safe_name, str(dest), img_hash, source_url, platform),
        )
        await db.commit()
        asset_id = cur.lastrowid

    result = await scan_asset(asset_id)

    return {
        "asset_id": result.asset_id,
        "filename": safe_name,
        "status": result.status,
        "similarity_percentage": result.similarity_percentage,
        "ai_similarity": result.ai_similarity,
        "hash_similarity": result.hash_similarity,
        "ai_available": result.ai_available,
        "ai_model": "CLIP ViT-B/32" if result.ai_available else None,
        "confidence_score": result.confidence_score,
        "number_of_matches": result.number_of_matches,
        "top_match_source": result.top_match_source,
        "risk_score": result.risk_score,
        "top_matches": [asdict(m) for m in result.top_matches],
        "algorithm": "CLIP + " + algorithm if result.ai_available else algorithm,
        "exif": exif_data,
    }



@app.post("/match")
async def direct_match(
    file: UploadFile = File(...),
    platform: str = Form("Unknown"),
):
    """Quick match check without persisting the asset."""
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Unsupported file type.")

    tmp_path = UPLOAD_DIR / f"tmp_{random.randbytes(6).hex()}.jpg"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        query_hash = generate_hash(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    # Compare against all assets
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, filename, hash, source_url, platform FROM assets")
        rows = await cur.fetchall()

    matches = []
    for row in rows:
        dist = hash_distance(query_hash, row["hash"])
        sim = similarity_percentage(dist)
        if sim > 0:
            matches.append({
                "asset_id": row["id"],
                "filename": row["filename"],
                "similarity": sim,
                "source_url": row["source_url"],
                "platform": row["platform"],
            })

    matches.sort(key=lambda m: m["similarity"], reverse=True)
    top3 = matches[:3]
    best_sim = top3[0]["similarity"] if top3 else 0.0

    return {
        "status": classify(best_sim),
        "similarity_percentage": best_sim,
        "confidence_score": compute_confidence(best_sim, len(top3)),
        "number_of_matches": len(top3),
        "top_match_source": top3[0]["source_url"] if top3 else "",
        "risk_score": compute_risk_score(best_sim, platform),
        "top_matches": top3,
    }


@app.get("/violations")
async def get_violations():
    """Return all scans classified as Copied (excluding false positives), sorted by risk_score DESC."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.*, a.filename, a.source_url, a.platform, a.created_at as asset_created
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied'
                 AND a.is_reference = 0
                 AND (s.is_false_positive IS NULL OR s.is_false_positive = 0)
               ORDER BY s.risk_score DESC""",
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.post("/scans/{scan_id}/false-positive")
async def mark_false_positive(scan_id: int, reason: str = Form("")):
    """Mark a scan as a false positive — removes it from violations."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scans SET is_false_positive = 1, false_positive_reason = ? WHERE id = ?",
            (reason, scan_id),
        )
        await db.commit()
    return {"success": True, "scan_id": scan_id}


@app.post("/upload-url")
async def upload_from_url(
    image_url: str = Form(...),
    platform: str  = Form("Unknown"),
    algorithm: str = Form("average"),
):
    """Download an image from a URL and run a full AI scan on it."""
    import httpx, mimetypes
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"Could not fetch URL: {e}")

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if content_type not in allowed:
        # Try to guess from URL
        guessed, _ = mimetypes.guess_type(image_url.split("?")[0])
        if guessed not in allowed:
            raise HTTPException(400, f"URL does not point to a supported image (got {content_type})")
        content_type = guessed

    ext = {"image/jpeg": ".jpg", "image/png": ".png",
           "image/webp": ".webp", "image/gif": ".gif"}.get(content_type, ".jpg")
    safe_name = f"url_import_{random.randbytes(4).hex()}{ext}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(resp.content)

    try:
        img_hash = generate_hash(str(dest), algorithm=algorithm)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Could not process image: {e}")

    from watermark import extract_exif
    exif_data = extract_exif(str(dest))

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO assets (filename, file_path, hash, source_url, platform)
               VALUES (?, ?, ?, ?, ?)""",
            (safe_name, str(dest), img_hash, image_url, platform),
        )
        await db.commit()
        asset_id = cur.lastrowid

    result = await scan_asset(asset_id)
    return {
        "asset_id": result.asset_id,
        "filename": safe_name,
        "source_url": image_url,
        "status": result.status,
        "similarity_percentage": result.similarity_percentage,
        "ai_similarity": result.ai_similarity,
        "hash_similarity": result.hash_similarity,
        "ai_available": result.ai_available,
        "ai_model": "CLIP ViT-B/32" if result.ai_available else None,
        "confidence_score": result.confidence_score,
        "number_of_matches": result.number_of_matches,
        "top_match_source": result.top_match_source,
        "risk_score": result.risk_score,
        "top_matches": [asdict(m) for m in result.top_matches],
        "algorithm": "CLIP + " + algorithm if result.ai_available else algorithm,
        "exif": exif_data,
    }


@app.get("/scans")
async def get_scans(limit: int = 50):
    """Return all scans with asset info."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.*, a.filename, a.source_url, a.platform
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
               ORDER BY s.timestamp DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/assets")
async def get_assets():
    """Return all uploaded (non-reference) assets."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM assets WHERE is_reference = 0 ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/assets/reference")
async def get_reference_assets():
    """Return all reference (seeded) assets — used by the demo mode."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM assets WHERE is_reference = 1 ORDER BY id ASC"
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/dashboard/stats")
async def dashboard_stats(days: int = 30):
    """Aggregate KPI statistics for the dashboard. Filter by days."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM assets WHERE is_reference = 0"
        )
        total_assets = (await cur.fetchone())["cnt"]

        cur = await db.execute(
            """SELECT COUNT(*) as cnt FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied' AND a.is_reference = 0
                 AND (s.is_false_positive IS NULL OR s.is_false_positive = 0)
                 AND s.timestamp >= datetime('now', '-' || ? || ' days')""",
            (days,),
        )
        total_violations = (await cur.fetchone())["cnt"]

        cur = await db.execute(
            """SELECT AVG(s.risk_score) as avg_risk FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
                 AND s.timestamp >= datetime('now', '-' || ? || ' days')""",
            (days,),
        )
        row = await cur.fetchone()
        avg_risk = round(row["avg_risk"] or 0.0, 1)

        cur = await db.execute(
            """SELECT s.id, s.status, a.filename, s.risk_score, s.similarity, s.timestamp
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
               ORDER BY s.timestamp DESC LIMIT 10"""
        )
        recent = await cur.fetchall()

        cur = await db.execute(
            """SELECT COUNT(*) as cnt FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0"""
        )
        total_scans = (await cur.fetchone())["cnt"]

    return {
        "total_assets": total_assets,
        "total_violations": total_violations,
        "total_scans": total_scans,
        "avg_risk_score": avg_risk,
        "recent_activity": [dict(r) for r in recent],
        "days_filter": days,
    }


@app.get("/dashboard/trend")
async def dashboard_trend(days: int = 7):
    """Return daily scan counts grouped by status for trend chart."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT
                 date(s.timestamp) as day,
                 SUM(CASE WHEN s.status='Original'   THEN 1 ELSE 0 END) as original,
                 SUM(CASE WHEN s.status='Suspicious' THEN 1 ELSE 0 END) as suspicious,
                 SUM(CASE WHEN s.status='Copied'     THEN 1 ELSE 0 END) as copied,
                 AVG(s.similarity) as avg_similarity
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
                 AND s.timestamp >= datetime('now', '-' || ? || ' days')
               GROUP BY day ORDER BY day ASC""",
            (days,),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/export/violations.csv")
async def export_violations_csv():
    """Download violations as CSV file."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.id, a.filename, a.platform, s.risk_score,
                      s.similarity, s.ai_similarity, s.hash_similarity,
                      s.status, s.confidence, s.timestamp, a.source_url
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied' AND a.is_reference = 0
                 AND (s.is_false_positive IS NULL OR s.is_false_positive = 0)
               ORDER BY s.risk_score DESC"""
        )
        rows = await cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Filename", "Platform", "Risk Score",
                     "Similarity %", "AI Similarity %", "Hash Similarity %",
                     "Status", "Confidence", "Timestamp", "Source URL"])
    for r in rows:
        writer.writerow([
            r["id"], r["filename"], r["platform"], r["risk_score"],
            r["similarity"], r["ai_similarity"] or 0, r["hash_similarity"] or 0,
            r["status"], r["confidence"], r["timestamp"], r["source_url"] or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=guardsport_violations.csv"},
    )


@app.post("/generate-legal")
async def generate_legal(
    owner_name: str = Form(...),
    infringing_url: str = Form(...),
    asset_id: Optional[int] = Form(None),
):
    """Generate a DMCA takedown notice."""
    asset_filename = "sports media content"
    similarity = 0.0
    status = "Copied"
    risk_score = 0.0

    if asset_id:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT s.similarity, s.status, s.risk_score, a.filename
                   FROM scans s
                   JOIN assets a ON s.asset_id = a.id
                   WHERE s.asset_id = ?
                   ORDER BY s.timestamp DESC LIMIT 1""",
                (asset_id,),
            )
            row = await cur.fetchone()
            if row:
                asset_filename = row["filename"]
                similarity = row["similarity"]
                status = row["status"]
                risk_score = row["risk_score"]

    notice = generate_dmca(
        owner_name=owner_name,
        infringing_url=infringing_url,
        asset_filename=asset_filename,
        similarity=similarity,
        status=status,
        risk_score=risk_score,
    )

    return {"notice": notice, "owner_name": owner_name, "infringing_url": infringing_url}


@app.get("/scan/{asset_id}")
async def get_scan(asset_id: int):
    """Get the latest scan result for an asset."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.*, a.filename, a.source_url, a.platform, a.file_path
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.asset_id = ?
               ORDER BY s.timestamp DESC LIMIT 1""",
            (asset_id,),
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Scan not found")

    data = dict(row)
    try:
        data["top_matches"] = json.loads(data.get("matches_json", "[]"))
    except Exception:
        data["top_matches"] = []
    return data


@app.post("/bulk-legal")
async def bulk_legal(owner_name: str = Form(...)):
    """Generate DMCA notices for ALL current violations (Copied scans)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT s.similarity, s.status, s.risk_score, a.filename, a.source_url, s.asset_id
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied' AND a.is_reference = 0
               ORDER BY s.risk_score DESC""",
        )
        rows = await cur.fetchall()

    if not rows:
        raise HTTPException(404, "No violations found to export.")

    notices = []
    for row in rows:
        notice = generate_dmca(
            owner_name=owner_name,
            infringing_url=row["source_url"] or "Unknown URL",
            asset_filename=row["filename"],
            similarity=row["similarity"],
            status=row["status"],
            risk_score=row["risk_score"],
        )
        notices.append(notice)

    combined = "\n\n" + ("=" * 60) + "\n\n".join(notices)
    return {"notices": notices, "combined": combined, "count": len(notices)}


@app.get("/scan-trend")
async def scan_trend():
    """Return daily scan counts grouped by status for the last 30 days."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT DATE(s.timestamp) as day, s.status, COUNT(*) as count
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
                 AND s.timestamp >= DATE('now', '-30 days')
               GROUP BY day, s.status
               ORDER BY day""",
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/asset-image/{asset_id}")
async def serve_asset_image(asset_id: int):
    """Serve the actual image file for an asset (for comparison view)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT file_path, filename FROM assets WHERE id = ?", (asset_id,))
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Asset not found")

    file_path = Path(row["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "Image file not found on disk")

    suffix = file_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
    }.get(suffix, "image/jpeg")

    return Response(content=file_path.read_bytes(), media_type=media_type)


@app.post("/scan-url")
async def scan_from_url(
    image_url: str = Form(...),
    source_url: str = Form(""),
    platform: str = Form("Unknown"),
    algorithm: str = Form("average"),
):
    """Fetch a public image URL and run it through the scan pipeline."""
    # Fetch image from URL
    try:
        req = urllib.request.Request(
            image_url,
            headers={"User-Agent": "GuardSport-AI/1.0 (image scanner)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            image_bytes = resp.read(20 * 1024 * 1024)  # 20MB limit
    except Exception as e:
        raise HTTPException(400, f"Could not fetch image from URL: {e}")

    allowed_ct = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    ct_clean = content_type.split(";")[0].strip()
    if ct_clean not in allowed_ct:
        raise HTTPException(400, f"URL does not point to a supported image type ({ct_clean})")

    # Save to disk
    ext_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    ext = ext_map.get(ct_clean, ".jpg")
    filename = f"url_scan_{random.randbytes(6).hex()}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(image_bytes)

    try:
        img_hash = generate_hash(str(dest), algorithm=algorithm)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Could not fingerprint image: {e}")

    exif_data = extract_exif(str(dest))

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO assets (filename, file_path, hash, source_url, platform)
               VALUES (?, ?, ?, ?, ?)""",
            (filename, str(dest), img_hash, source_url or image_url, platform),
        )
        await db.commit()
        asset_id = cur.lastrowid

    result = await scan_asset(asset_id)

    return {
        "asset_id": result.asset_id,
        "filename": filename,
        "status": result.status,
        "similarity_percentage": result.similarity_percentage,
        "confidence_score": result.confidence_score,
        "number_of_matches": result.number_of_matches,
        "top_match_source": result.top_match_source,
        "risk_score": result.risk_score,
        "top_matches": [asdict(m) for m in result.top_matches],
        "algorithm": algorithm,
        "exif": exif_data,
        "scanned_url": image_url,
    }


@app.delete("/assets/{asset_id}")
async def delete_asset(asset_id: int):
    """Delete an uploaded asset and its scan records."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT file_path, is_reference FROM assets WHERE id = ?", (asset_id,)
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Asset not found")
    if row["is_reference"]:
        raise HTTPException(403, "Cannot delete reference assets")

    # Delete file
    try:
        Path(row["file_path"]).unlink(missing_ok=True)
    except Exception:
        pass

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM scans WHERE asset_id = ?", (asset_id,))
        await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        await db.commit()

    return {"deleted": True, "asset_id": asset_id}


@app.get("/export/violations.csv")
async def export_violations_csv():
    """Download all violations as a CSV file."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT a.filename, s.status, s.similarity, s.risk_score,
                      s.confidence, s.num_matches, s.top_match_source,
                      a.platform, a.source_url, s.timestamp
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied' AND a.is_reference = 0
               ORDER BY s.risk_score DESC"""
        )
        rows = await cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Filename", "Status", "Similarity %", "Risk Score",
        "Confidence %", "Matches", "Top Match Source",
        "Platform", "Source URL", "Scanned At"
    ])
    for r in rows:
        writer.writerow([
            r["filename"], r["status"],
            round(r["similarity"] or 0, 2),
            round(r["risk_score"] or 0, 2),
            round(r["confidence"] or 0, 2),
            r["num_matches"] or 0,
            r["top_match_source"] or "",
            r["platform"] or "",
            r["source_url"] or "",
            r["timestamp"] or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=guardsport_violations.csv"},
    )


@app.get("/export/scans.csv")
async def export_scans_csv():
    """Download all scan history as a CSV file."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT a.filename, s.status, s.similarity, s.risk_score,
                      s.confidence, s.num_matches, a.platform,
                      a.source_url, s.timestamp
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE a.is_reference = 0
               ORDER BY s.timestamp DESC
               LIMIT 1000"""
        )
        rows = await cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Filename", "Status", "Similarity %", "Risk Score",
        "Confidence %", "Matches", "Platform", "Source URL", "Scanned At"
    ])
    for r in rows:
        writer.writerow([
            r["filename"], r["status"],
            round(r["similarity"] or 0, 2),
            round(r["risk_score"] or 0, 2),
            round(r["confidence"] or 0, 2),
            r["num_matches"] or 0,
            r["platform"] or "",
            r["source_url"] or "",
            r["timestamp"] or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=guardsport_scan_history.csv"},
    )


@app.post("/watermark")
async def watermark_image(
    file: UploadFile = File(...),
    owner_name: str = Form("GuardSport AI"),
    style: str = Form("visible"),
    position: str = Form("bottom-right"),
):
    """Embed a watermark into an uploaded image and return the result."""
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only JPEG, PNG, and WebP images are supported.")

    tmp_path = UPLOAD_DIR / f"wm_tmp_{random.randbytes(6).hex()}.jpg"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        if style == "tiled":
            image_bytes = tiled_watermark(str(tmp_path), owner_name=owner_name)
        else:
            image_bytes = visible_watermark(str(tmp_path), owner_name=owner_name, position=position)
    except Exception as e:
        raise HTTPException(500, f"Watermark failed: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)

    safe_name = Path(file.filename).stem
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"attachment; filename={safe_name}_watermarked.jpg",
            "X-Owner": owner_name,
        },
    )


@app.get("/dashboard/platform-breakdown")
async def platform_breakdown():
    """Return violation counts grouped by platform for pie chart."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT a.platform, COUNT(*) as count
               FROM scans s
               JOIN assets a ON s.asset_id = a.id
               WHERE s.status = 'Copied' AND a.is_reference = 0
               GROUP BY a.platform
               ORDER BY count DESC"""
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]

