"""Orchestrates sync -> photo -> breed -> cartoon, with a per-pet disk cache.

data/results/<pet id>.json holds the breed result + cartoon path + the cover
photo id it was computed from. If the shelter swaps the cover photo, the pet
is re-analyzed on the next request; otherwise cached results are reused across
re-syncs and restarts, so re-running after the list updates only costs API
calls for new animals.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from . import breed as breed_mod
from . import cartoon as cartoon_mod
from . import config
from .photos import ensure_photo
from .shelter import load_pets, sync


def result_path(pet_id: str) -> Path:
    return config.RESULTS_DIR / f"{pet_id}.json"


def load_result(pet: dict) -> dict | None:
    p = result_path(pet["id"])
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    if data.get("cover_photo_id") != pet.get("cover_photo_id"):
        return None  # photo changed -> stale
    if not cartoon_mod.cartoon_path(pet).exists():
        return None
    if data.get("models", {}).get("breed") == "mock" and not config.MOCK_AI:
        return None  # placeholder from a keyless run; redo now that real models are available
    return data


def analyze(pet: dict, force: bool = False, style: str | None = None) -> dict:
    if not force:
        cached = load_result(pet)
        if cached:
            return cached
    t0 = time.time()
    photo = ensure_photo(pet)
    breed = breed_mod.identify(pet, photo)
    cartoon = cartoon_mod.generate(pet, breed, photo, style=style)
    data = {
        "pet_id": pet["id"],
        "cover_photo_id": pet.get("cover_photo_id"),
        "breed": breed.model_dump(),
        "cartoon_prompt": cartoon_mod.cartoon_prompt(pet, breed, style),
        "photo_file": photo.name,
        "cartoon_file": cartoon.name,
        "models": {
            "breed": "mock" if config.MOCK_AI else config.BREED_MODEL,
            "cartoon": "mock" if config.MOCK_AI else f"{config.CARTOON_PROVIDER}:{config.CARTOON_MODEL}",
        },
        "seconds": round(time.time() - t0, 1),
        "analyzed_at": int(time.time()),
    }
    result_path(pet["id"]).write_text(json.dumps(data, indent=2))
    return data


def prune(pets: list[dict]) -> int:
    """Delete cached files for animals no longer on the list (adopted, etc.)."""
    keep = {p["id"] for p in pets}
    removed = 0
    for d in (config.RESULTS_DIR, config.PHOTOS_DIR, config.CARTOONS_DIR):
        for f in d.iterdir():
            if f.is_file() and f.stem not in keep and not f.name.startswith("."):
                f.unlink()
                removed += 1
    return removed


def run_all(species: str | None = None, force: bool = False, limit: int | None = None) -> tuple[list[dict], int]:
    """Batch mode: `python -m app.pipeline [--sync] [--species Dog|Cat] [--force] [--limit N] [--prune]`.

    Returns (results, error_count). Pets already cached cost nothing.
    """
    pets = load_pets()
    if species:
        pets = [p for p in pets if p["species"].lower() == species.lower()]
    if limit:
        pets = pets[:limit]
    out, errors = [], 0
    for i, pet in enumerate(pets, 1):
        cached = None if force else load_result(pet)
        try:
            r = cached or analyze(pet, force=force)
            top = r["breed"]["guesses"][0]["breed"] if r["breed"]["guesses"] else "?"
            tag = "cached" if cached else f"{r['seconds']}s"
            print(f"[{i}/{len(pets)}] {pet['id']} {pet['name']:<22} {pet['species']}: {top} ({tag})", file=sys.stderr)
            out.append(r)
        except Exception as e:  # keep going; one bad photo shouldn't kill the batch
            errors += 1
            print(f"[{i}/{len(pets)}] {pet['id']} {pet['name']}: ERROR {e}", file=sys.stderr)
    return out, errors


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true", help="refresh data/pets.json from Shelterluv first")
    ap.add_argument("--species", choices=["Dog", "Cat"])
    ap.add_argument("--force", action="store_true", help="ignore cached results")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--prune", action="store_true", help="delete cached files for pets no longer listed")
    args = ap.parse_args()
    if args.sync or not config.PETS_JSON.exists():
        sync()
    if args.prune:
        n = prune(load_pets())
        print(f"pruned {n} stale files", file=sys.stderr)
    results, errors = run_all(args.species, args.force, args.limit)
    print(f"done: {len(results)} ok, {errors} errors", file=sys.stderr)
    if errors and not results:
        sys.exit(1)  # nothing worked (bad key?) -> fail loudly instead of publishing an empty page
