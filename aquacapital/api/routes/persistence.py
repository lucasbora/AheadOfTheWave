"""
JSON file-based persistence for saved locations and leaderboard.
Replaces MongoDB for local development — no extra service needed.
Data is stored in data/db.json and survives server restarts.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["persistence"])

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "db.json")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _load() -> dict:
    if not os.path.exists(DB_PATH):
        return {"locations": [], "leaderboard": []}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"locations": [], "leaderboard": []}


def _save(db: dict) -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LocationBody(BaseModel):
    name: str
    lat: float
    lon: float
    user_type: str = "data_center"
    grade: str | None = None
    score: float | None = None
    label: str | None = None
    payload: dict[str, Any] | None = None


class LeaderboardBody(BaseModel):
    name: str
    lat: float
    lon: float
    user_type: str = "data_center"
    grade: str | None = None
    score: float | None = None
    label: str | None = None


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@router.get("/locations")
def list_locations() -> list[dict]:
    return _load().get("locations", [])


@router.post("/locations")
def save_location(body: LocationBody) -> dict:
    db = _load()
    entry = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        **body.model_dump(),
    }
    db["locations"].insert(0, entry)
    _save(db)
    return entry


@router.delete("/locations/{entry_id}")
def delete_location(entry_id: str) -> dict:
    db = _load()
    before = len(db["locations"])
    db["locations"] = [l for l in db["locations"] if l.get("id") != entry_id]
    if len(db["locations"]) == before:
        raise HTTPException(status_code=404, detail="Location not found")
    _save(db)
    return {"deleted": entry_id}


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@router.get("/leaderboard")
def list_leaderboard() -> list[dict]:
    entries = _load().get("leaderboard", [])
    return sorted(entries, key=lambda x: x.get("score", 0), reverse=True)


@router.post("/leaderboard")
def add_leaderboard(body: LeaderboardBody) -> dict:
    db = _load()
    entry = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        **body.model_dump(),
    }
    db["leaderboard"].append(entry)
    _save(db)
    return entry


@router.delete("/leaderboard/{entry_id}")
def delete_leaderboard_entry(entry_id: str) -> dict:
    db = _load()
    before = len(db["leaderboard"])
    db["leaderboard"] = [l for l in db["leaderboard"] if l.get("id") != entry_id]
    if len(db["leaderboard"]) == before:
        raise HTTPException(status_code=404, detail="Leaderboard entry not found")
    _save(db)
    return {"deleted": entry_id}


@router.delete("/leaderboard")
def clear_leaderboard() -> dict:
    db = _load()
    db["leaderboard"] = []
    _save(db)
    return {"cleared": True}
