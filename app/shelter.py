"""Pull the current adoptable list from Shelterluv.

carenorthshore.org/dogs and /cats are just an <iframe> of Shelterluv's embed
(shelter GID 3204). The embed is driven by a public JSON endpoint that needs no
API key, so we read that directly instead of scraping HTML:

    https://new.shelterluv.com/api/v3/available-animals/3204

Run `python -m app.shelter` any time the shelter updates its list. The output
(data/pets.json) is normalized and stable, so results cached per pet survive a
re-sync and only *new* pets (or pets whose cover photo changed) get re-analyzed.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from . import config

USER_AGENT = "Mozilla/5.0 (pet-breed-cartoon hackathon; +https://github.com/)"


def fetch_raw(url: str = config.SHELTERLUV_URL, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _photo_list(photos) -> list[dict]:
    """Shelterluv returns photos as a list OR a dict keyed by index. Normalize."""
    if not photos:
        return []
    items = list(photos.values()) if isinstance(photos, dict) else list(photos)
    items = [p for p in items if isinstance(p, dict) and p.get("url")]
    items.sort(key=lambda p: (not p.get("isCover", False), p.get("order_column", 0)))
    return items


def normalize(raw: dict) -> list[dict]:
    animals = raw.get("animals") if isinstance(raw, dict) else raw
    pets = []
    for a in animals or []:
        photos = _photo_list(a.get("photos"))
        if not photos:
            continue  # nothing to look at
        cover = photos[0]
        age_group = a.get("age_group") or {}
        pets.append(
            {
                "id": a["uniqueId"],
                "name": (a.get("name") or "").strip(),
                "species": a.get("species"),  # "Dog" | "Cat"
                "sex": a.get("sex"),
                "age_group": age_group.get("name"),
                "shelter_breed": a.get("breed"),
                "shelter_secondary_breed": a.get("secondary_breed") or None,
                "color": a.get("primary_color"),
                "location": a.get("location"),
                "attributes": a.get("attributes") or [],
                "cover_photo_id": cover.get("id"),
                "cover_photo_url": cover["url"],
                "photo_urls": [p["url"] for p in photos],
                "public_url": a.get("public_url"),
            }
        )
    pets.sort(key=lambda p: (p["species"] or "", p["name"]))
    return pets


def sync(out_path: Path = config.PETS_JSON) -> list[dict]:
    raw = fetch_raw()
    pets = normalize(raw)
    payload = {
        "source": config.SHELTERLUV_URL,
        "synced_at": int(time.time()),
        "count": len(pets),
        "pets": pets,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return pets


def load_pets(path: Path = config.PETS_JSON) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("pets", [])


if __name__ == "__main__":
    pets = sync()
    dogs = sum(1 for p in pets if p["species"] == "Dog")
    cats = sum(1 for p in pets if p["species"] == "Cat")
    print(f"synced {len(pets)} pets ({dogs} dogs, {cats} cats) -> {config.PETS_JSON}", file=sys.stderr)
