"""
scanner.py — Full scan pipeline: CLIP AI + hash comparison → classification → risk scoring
Hybrid engine: 70% CLIP semantic similarity + 30% perceptual hash
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import aiosqlite

from database import DB_PATH
from fingerprint import (
    generate_hash,
    hash_distance,
    similarity_percentage,
    classify,
    compute_risk_score,
    compute_confidence,
)
from ai_engine import (
    generate_embedding,
    generate_dino_embedding,
    cosine_similarity,
    hybrid_similarity,
    embedding_to_json,
    json_to_embedding,
    get_status as ai_status,
)

logger = logging.getLogger(__name__)


@dataclass
class MatchInfo:
    asset_id: int
    filename: str
    similarity: float
    ai_similarity: float
    hash_similarity: float
    source_url: str
    platform: str


@dataclass
class ScanResult:
    asset_id: int
    status: str
    similarity_percentage: float
    ai_similarity: float
    hash_similarity: float
    confidence_score: float
    number_of_matches: int
    top_match_source: str
    risk_score: float
    ai_available: bool
    top_matches: List[MatchInfo] = field(default_factory=list)


async def _get_or_generate_embedding(db: aiosqlite.Connection,
                                      asset_id: int,
                                      file_path: str) -> Optional[List[float]]:
    """
    Fetch cached embedding from DB, or generate + cache it on the fly.
    Returns None if AI is unavailable.
    """
    cur = await db.execute(
        "SELECT embedding FROM assets WHERE id = ?", (asset_id,)
    )
    row = await cur.fetchone()
    if row and row["embedding"]:
        return json_to_embedding(row["embedding"])

    # Generate fresh embedding
    emb = generate_embedding(file_path)
    if emb:
        await db.execute(
            "UPDATE assets SET embedding = ? WHERE id = ?",
            (embedding_to_json(emb), asset_id),
        )
        await db.commit()
    return emb


async def scan_asset(asset_id: int) -> ScanResult:
    """
    Full AI-powered scan pipeline:
    1. Load asset hash + file path from DB
    2. Generate CLIP embedding for target (or use cached)
    3. Compare against all reference+existing assets using CLIP + hash
    4. Hybrid score = 70% CLIP + 30% hash
    5. Classify & score
    6. Persist scan record with AI scores
    7. Return ScanResult
    """
    ai_info = ai_status()
    ai_on   = ai_info["available"]

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Load the target asset
        cur = await db.execute(
            "SELECT id, file_path, hash, platform FROM assets WHERE id = ?",
            (asset_id,),
        )
        target = await cur.fetchone()
        if not target:
            raise ValueError(f"Asset {asset_id} not found")

        target_hash     = target["hash"]
        target_platform = target["platform"] or "Unknown"
        target_path     = target["file_path"]

        # Generate / fetch CLIP + DINO embeddings for target
        target_emb      = None
        target_dino_emb = None
        if ai_on:
            target_emb      = await _get_or_generate_embedding(db, asset_id, target_path)
            target_dino_emb = generate_dino_embedding(target_path)

        # Load all OTHER assets as reference pool
        cur = await db.execute(
            "SELECT id, filename, hash, embedding, file_path, source_url, platform "
            "FROM assets WHERE id != ?",
            (asset_id,),
        )
        candidates = await cur.fetchall()

        matches: List[MatchInfo] = []

        for row in candidates:
            # ── Hash similarity ──────────────────────────────────────────────
            dist     = hash_distance(target_hash, row["hash"])
            hash_sim = similarity_percentage(dist)

            # ── CLIP similarity ──────────────────────────────────────────────
            clip_sim = 0.0
            if ai_on and target_emb:
                cand_emb = json_to_embedding(row["embedding"]) if row["embedding"] else None
                if cand_emb is None:
                    # Generate + cache for candidate too
                    cand_emb = generate_embedding(row["file_path"])
                    if cand_emb:
                        await db.execute(
                            "UPDATE assets SET embedding = ? WHERE id = ?",
                            (embedding_to_json(cand_emb), row["id"]),
                        )
                if cand_emb:
                    clip_sim = cosine_similarity(target_emb, cand_emb)

            # ── DINOv2 similarity ─────────────────────────────────────────────
            dino_sim = 0.0
            if ai_on and target_dino_emb:
                cand_dino = generate_dino_embedding(row["file_path"])
                if cand_dino:
                    dino_sim = cosine_similarity(target_dino_emb, cand_dino)

            # ── Hybrid score ─────────────────────────────────────────────────
            if ai_on and clip_sim > 0:
                final_sim = hybrid_similarity(clip_sim, hash_sim, dino_sim)
            else:
                final_sim = hash_sim

            if final_sim > 0:
                matches.append(
                    MatchInfo(
                        asset_id=row["id"],
                        filename=row["filename"],
                        similarity=final_sim,
                        ai_similarity=clip_sim,
                        hash_similarity=hash_sim,
                        source_url=row["source_url"] or "",
                        platform=row["platform"] or "Unknown",
                    )
                )

        await db.commit()

    # Sort by hybrid similarity descending
    matches.sort(key=lambda m: m.similarity, reverse=True)
    top3 = matches[:3]

    best_sim      = top3[0].similarity    if top3 else 0.0
    best_ai_sim   = top3[0].ai_similarity if top3 else 0.0
    best_hash_sim = top3[0].hash_similarity if top3 else 0.0
    best_source   = top3[0].source_url or top3[0].filename if top3 else ""

    status     = classify(best_sim)
    risk       = compute_risk_score(best_sim, target_platform)
    confidence = compute_confidence(best_sim, len(top3), ai_available=ai_on)

    # Persist scan with AI scores
    async with aiosqlite.connect(DB_PATH) as db:
        matches_json = json.dumps([asdict(m) for m in top3])
        await db.execute(
            """INSERT INTO scans
               (asset_id, similarity, ai_similarity, hash_similarity,
                status, risk_score, confidence, matches_json, top_match_source, num_matches)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, best_sim, best_ai_sim, best_hash_sim,
             status, risk, confidence, matches_json, best_source, len(top3)),
        )
        await db.commit()

    return ScanResult(
        asset_id=asset_id,
        status=status,
        similarity_percentage=best_sim,
        ai_similarity=best_ai_sim,
        hash_similarity=best_hash_sim,
        confidence_score=confidence,
        number_of_matches=len(top3),
        top_match_source=best_source,
        risk_score=risk,
        ai_available=ai_on,
        top_matches=top3,
    )
