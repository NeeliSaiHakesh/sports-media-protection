"""
scanner.py — Full scan pipeline: hash comparison → classification → risk scoring
"""
import json
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


@dataclass
class MatchInfo:
    asset_id: int
    filename: str
    similarity: float
    source_url: str
    platform: str


@dataclass
class ScanResult:
    asset_id: int
    status: str
    similarity_percentage: float
    confidence_score: float
    number_of_matches: int
    top_match_source: str
    risk_score: float
    top_matches: List[MatchInfo] = field(default_factory=list)


async def scan_asset(asset_id: int) -> ScanResult:
    """
    Full scan pipeline for an uploaded asset:
    1. Load asset hash from DB
    2. Compare against all reference+existing assets
    3. Classify & score
    4. Persist scan record
    5. Return ScanResult
    """
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

        target_hash = target["hash"]
        target_platform = target["platform"] or "Unknown"

        # Load all OTHER assets as reference pool
        cur = await db.execute(
            "SELECT id, filename, hash, source_url, platform FROM assets WHERE id != ?",
            (asset_id,),
        )
        candidates = await cur.fetchall()

    matches: List[MatchInfo] = []

    for row in candidates:
        dist = hash_distance(target_hash, row["hash"])
        sim = similarity_percentage(dist)
        if sim > 0:  # only record non-zero similarity
            matches.append(
                MatchInfo(
                    asset_id=row["id"],
                    filename=row["filename"],
                    similarity=sim,
                    source_url=row["source_url"] or "",
                    platform=row["platform"] or "Unknown",
                )
            )

    # Sort by similarity descending
    matches.sort(key=lambda m: m.similarity, reverse=True)
    top3 = matches[:3]

    # Use the best match for classification
    best_sim = top3[0].similarity if top3 else 0.0
    best_source = top3[0].source_url or top3[0].filename if top3 else ""

    status = classify(best_sim)
    risk = compute_risk_score(best_sim, target_platform)
    confidence = compute_confidence(best_sim, len(top3))

    # Persist scan
    async with aiosqlite.connect(DB_PATH) as db:
        matches_json = json.dumps([asdict(m) for m in top3])
        await db.execute(
            """INSERT INTO scans
               (asset_id, similarity, status, risk_score, confidence, matches_json, top_match_source, num_matches)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (asset_id, best_sim, status, risk, confidence, matches_json, best_source, len(top3)),
        )
        await db.commit()

    return ScanResult(
        asset_id=asset_id,
        status=status,
        similarity_percentage=best_sim,
        confidence_score=confidence,
        number_of_matches=len(top3),
        top_match_source=best_source,
        risk_score=risk,
        top_matches=top3,
    )
