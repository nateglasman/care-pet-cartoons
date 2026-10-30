"""FastAPI app: a small gallery UI + JSON API over the pipeline."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .pipeline import analyze, load_result
from .shelter import load_pets, sync

app = FastAPI(title="Pet Breed + Cartoon")
ROOT = config.ROOT

# One model call at a time per process keeps Replit's small boxes (and rate limits) happy.
_lock = asyncio.Semaphore(2)


def _pets():
    pets = load_pets()
    if not pets:
        pets = sync()
    return pets


def _find(pet_id: str) -> dict:
    for p in _pets():
        if p["id"] == pet_id:
            return p
    raise HTTPException(404, f"unknown pet {pet_id}")


def _with_result(pet: dict) -> dict:
    r = load_result(pet)
    return {**pet, "result": r, "analyzed": r is not None}


@app.get("/api/status")
def status():
    return config.status()


@app.get("/api/pets")
def list_pets(species: str | None = Query(default=None)):
    pets = _pets()
    if species:
        pets = [p for p in pets if p["species"].lower() == species.lower()]
    return [_with_result(p) for p in pets]


@app.post("/api/sync")
def resync():
    pets = sync()
    return {"count": len(pets)}


@app.get("/api/pets/{pet_id}")
def get_pet(pet_id: str):
    return _with_result(_find(pet_id))


@app.post("/api/pets/{pet_id}/analyze")
async def analyze_pet(pet_id: str, force: bool = False, style: str | None = None):
    pet = _find(pet_id)
    async with _lock:
        try:
            result = await asyncio.to_thread(analyze, pet, force, style)
        except Exception as e:  # surface model/provider errors to the UI
            raise HTTPException(502, str(e)) from e
    return {**pet, "result": result, "analyzed": True}


@app.get("/photos/{pet_id}.jpg")
def photo(pet_id: str):
    p = config.PHOTOS_DIR / f"{pet_id}.jpg"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.get("/cartoons/{pet_id}.webp")
def cartoon(pet_id: str):
    p = config.CARTOONS_DIR / f"{pet_id}.webp"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/webp")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
