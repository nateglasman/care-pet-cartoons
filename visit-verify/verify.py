"""Verify that a visitor's photo shows a specific shelter pet, in person.

Standalone: this folder only needs `anthropic` and `pillow`. It reads the pet
list from data/pets.json (the format produced by app/shelter.py in the main
repo) or, if that file is missing, fetches it live from Shelterluv.

    from verify import verify_visit
    result = verify_visit("CAIL-A-50367", photo_bytes)
    result.decision        # "match" | "uncertain" | "no_match" | "rejected"
    result.confidence      # 0..1 that it's the same individual
    result.reason          # one line for the UI
    result.to_dict()       # everything, for logging

CLI:  python verify.py --pet CAIL-A-50367 --photo my_visit.jpg

Credentials, in priority order (same rule as the main app):
  ANTHROPIC_API_KEY, else Replit AI Integrations' AI_INTEGRATIONS_ANTHROPIC_API_KEY/_BASE_URL.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import re
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ---------------------------------------------------------------- config
MODEL = os.environ.get("VERIFY_MODEL") or "claude-opus-5-5"
PETS_JSON = Path(os.environ.get("PETS_JSON") or ROOT / "data" / "pets.json")
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR") or ROOT / "data" / "results")   # optional appearance text
CACHE_DIR = Path(os.environ.get("REF_CACHE_DIR") or HERE / ".cache")
SHELTERLUV_SHELTER_ID = os.environ.get("SHELTERLUV_SHELTER_ID") or "3204"

MAX_REFERENCES = 4      # reference photos of the target sent to the model
MAX_DECOYS = 3          # same-species lookalikes sent so the model must pick the target, not "a similar dog"
IMAGE_MAX_PX = 1024

# Leniency knobs. Lenient by design, but with a real "no". Set from calibrate.py on real
# shelter photos: true positives scored 0.50-0.95, true negatives 0.01-0.03, so 0.5 sits in the gap.
MATCH_AT = 0.50         # confidence >= this -> match
UNCERTAIN_AT = 0.25     # between -> uncertain (ask for another photo); below -> no_match
HIGH_LOOKALIKE_MATCH_AT = 0.50   # raise (e.g. 0.65) to demand more when the model flags lookalike risk

# Optional real-world signals read from the photo's EXIF (phones usually strip
# GPS on upload, so these are bonuses, never requirements, unless you set them).
SHELTER = {
    "name": "C.A.R.E. North Shore",
    "address": "4927 Main St, Skokie, IL 60077",
    "lat": 42.0334,   # approximate; refine from Google Maps if you enable the geofence
    "lon": -87.7246,
    "radius_m": 400,
}

PROMPT_RULES = (HERE / "PROMPT.md").read_text()

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "animal_present", "species_seen", "authenticity", "visible_text", "best_match",
        "same_animal_confidence", "matching_features", "conflicting_features", "lookalike_risk", "reasoning",
    ],
    "properties": {
        "animal_present": {"type": "boolean"},
        "species_seen": {"type": "string", "enum": ["Dog", "Cat", "Other", "None"]},
        "authenticity": {
            "type": "object",
            "additionalProperties": False,
            "required": ["is_photo_of_screen_or_print", "is_illustration", "is_duplicate_of_reference", "notes"],
            "properties": {
                "is_photo_of_screen_or_print": {"type": "boolean"},
                "is_illustration": {"type": "boolean"},
                "is_duplicate_of_reference": {"type": "boolean"},
                "notes": {"type": "string"},
            },
        },
        "visible_text": {"type": "string", "description": "Any kennel card / tag text readable in the candidate photo, else empty"},
        "best_match": {"type": "string", "description": "'target', 'decoy_N', or 'none'"},
        "same_animal_confidence": {"type": "number", "description": "Probability 0-1 that the candidate is the TARGET individual"},
        "matching_features": {"type": "array", "items": {"type": "string"}},
        "conflicting_features": {"type": "array", "items": {"type": "string"}},
        "lookalike_risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "reasoning": {"type": "string"},
    },
}


# ---------------------------------------------------------------- data
def _credentials() -> tuple[str, str | None]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key, os.environ.get("ANTHROPIC_BASE_URL") or None
    key = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
    if key:
        return key, os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL") or None
    raise RuntimeError("No Anthropic credentials: set ANTHROPIC_API_KEY or enable Replit AI Integrations (Anthropic)")


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (visit-verify)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_pets() -> list[dict]:
    """pets.json from the main repo, or a live pull from Shelterluv in the same shape."""
    if PETS_JSON.exists():
        return json.loads(PETS_JSON.read_text())["pets"]
    raw = _fetch_json(f"https://new.shelterluv.com/api/v3/available-animals/{SHELTERLUV_SHELTER_ID}")
    pets = []
    for a in raw.get("animals", []):
        photos = a.get("photos") or []
        photos = list(photos.values()) if isinstance(photos, dict) else list(photos)
        photos = [p for p in photos if isinstance(p, dict) and p.get("url")]
        photos.sort(key=lambda p: (not p.get("isCover", False), p.get("order_column", 0)))
        if not photos:
            continue
        pets.append({
            "id": a["uniqueId"], "name": (a.get("name") or "").strip(), "species": a.get("species"),
            "shelter_breed": a.get("breed"), "color": a.get("primary_color"),
            "cover_photo_id": photos[0].get("id"), "cover_photo_url": photos[0]["url"],
            "photo_urls": [p["url"] for p in photos], "public_url": a.get("public_url"),
        })
    return pets


def find_pet(pets: list[dict], pet_id: str) -> dict:
    for p in pets:
        if p["id"] == pet_id:
            return p
    raise KeyError(f"unknown pet {pet_id}")


def appearance_text(pet_id: str) -> str | None:
    p = RESULTS_DIR / f"{pet_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())["breed"]["appearance"]
        except (KeyError, ValueError):
            return None
    return None


def _prep_image(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((IMAGE_MAX_PX, IMAGE_MAX_PX))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def reference_image(url: str) -> bytes:
    """Download + resize a shelter photo once; cached on disk by URL hash."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9]", "", url)[-40:] + ".jpg"
    path = CACHE_DIR / name
    if path.exists():
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (visit-verify)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = _prep_image(r.read())
    path.write_bytes(data)
    return data


def pick_decoys(pets: list[dict], target: dict, n: int = MAX_DECOYS) -> list[dict]:
    """Same species; prefer same color / breed label so the decoys are real lookalikes."""
    others = [p for p in pets if p["species"] == target["species"] and p["id"] != target["id"]]
    def score(p):
        s = 0
        if (p.get("color") or "").lower() == (target.get("color") or "").lower():
            s -= 2
        if (p.get("shelter_breed") or "") == (target.get("shelter_breed") or ""):
            s -= 1
        return s
    others.sort(key=score)
    return others[:n]


# ---------------------------------------------------------------- EXIF side-signals
def exif_signals(data: bytes) -> dict:
    """Capture time and GPS distance to the shelter, when the photo still carries EXIF."""
    out = {"taken_at": None, "age_hours": None, "gps": None, "distance_m": None, "within_geofence": None}
    try:
        img = Image.open(io.BytesIO(data))
        exif = img.getexif()
    except Exception:
        return out
    dt = exif.get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
    if dt:
        try:
            taken = datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S")
            out["taken_at"] = taken.isoformat()
            out["age_hours"] = round((datetime.now() - taken).total_seconds() / 3600, 1)
        except ValueError:
            pass
    gps = exif.get_ifd(34853) if hasattr(exif, "get_ifd") else None
    if gps and 2 in gps and 4 in gps:
        def to_deg(v, ref):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if ref in ("S", "W") else d
        try:
            lat, lon = to_deg(gps[2], gps.get(1, "N")), to_deg(gps[4], gps.get(3, "E"))
            out["gps"] = {"lat": round(lat, 5), "lon": round(lon, 5)}
            r = 6371000
            p1, p2 = math.radians(lat), math.radians(SHELTER["lat"])
            dphi, dl = math.radians(SHELTER["lat"] - lat), math.radians(SHELTER["lon"] - lon)
            a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            out["distance_m"] = round(2 * r * math.asin(math.sqrt(a)))
            out["within_geofence"] = out["distance_m"] <= SHELTER["radius_m"]
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- result
@dataclass
class VerifyResult:
    pet_id: str
    pet_name: str
    decision: str            # match | uncertain | no_match | rejected
    confidence: float        # model's probability it's the target
    reason: str              # one line for the UI
    model_output: dict = field(default_factory=dict)
    exif: dict = field(default_factory=dict)
    references_used: int = 0
    decoys_used: list[str] = field(default_factory=list)
    model: str = MODEL
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- core
def verify_visit(
    pet_id: str,
    candidate: bytes,
    *,
    pets: list[dict] | None = None,
    expect_new_photo: bool = True,
    require_recent_hours: float | None = None,
    require_geofence: bool = False,
    exclude_reference_urls: set[str] | None = None,
) -> VerifyResult:
    """Decide whether `candidate` (image bytes) is a fresh in-person photo of pet `pet_id`.

    expect_new_photo      reject candidates that look copied from the shelter's own photos
    require_recent_hours  reject if EXIF says the photo is older than this (ignored when no EXIF)
    require_geofence      reject if EXIF GPS exists and is outside SHELTER radius (ignored when no GPS)
    exclude_reference_urls  used by calibrate.py to hold a photo out of the reference set
    """
    t0 = time.time()
    pets = pets or load_pets()
    target = find_pet(pets, pet_id)
    decoys = pick_decoys(pets, target)
    ex = exif_signals(candidate)
    cand = _prep_image(candidate)

    ref_urls = [u for u in target["photo_urls"] if u not in (exclude_reference_urls or set())][:MAX_REFERENCES]
    if not ref_urls:
        raise RuntimeError(f"{pet_id} has no reference photos")

    content: list[dict] = []
    def add_text(t): content.append({"type": "text", "text": t})
    def add_image(b): content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(b).decode()}})

    add_text(f"TARGET: {target['name']} ({target['species']}, shelter label '{target.get('shelter_breed')}', color '{target.get('color')}', id {target['id']}).")
    desc = appearance_text(pet_id)
    if desc:
        add_text(f"Staff description of the target: {desc}")
    for i, u in enumerate(ref_urls, 1):
        add_text(f"Reference photo {i} of {len(ref_urls)} of the TARGET:")
        add_image(reference_image(u))
    for i, d in enumerate(decoys, 1):
        add_text(f"Decoy {i} (a different {d['species'].lower()} at the same shelter, '{d.get('shelter_breed')}', color '{d.get('color')}'):")
        add_image(reference_image(d["cover_photo_url"]))
    add_text("CANDIDATE photo taken by the visitor:")
    add_image(cand)
    add_text("Apply the rubric and answer in the JSON format.")

    import anthropic

    key, base_url = _credentials()
    client = anthropic.Anthropic(api_key=key, base_url=base_url)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=PROMPT_RULES,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    conf = min(1.0, max(0.0, float(out["same_animal_confidence"])))

    # ---- policy ----
    auth = out["authenticity"]
    decision, reason = None, ""
    if not out["animal_present"] or out["species_seen"] == "None":
        decision, reason = "no_match", f"No animal visible in the photo."
    elif out["species_seen"] not in (target["species"], "Other") and out["species_seen"] != target["species"]:
        decision, reason = "no_match", f"That looks like a {out['species_seen'].lower()}, and {target['name']} is a {target['species'].lower()}."
    elif auth["is_photo_of_screen_or_print"]:
        decision, reason = "rejected", "That looks like a photo of a screen or printout. Take a photo of the pet in person."
    elif auth["is_illustration"]:
        decision, reason = "rejected", "That looks like a drawing or cartoon, not a photo."
    elif expect_new_photo and auth["is_duplicate_of_reference"]:
        decision, reason = "rejected", "That looks like one of the shelter's own photos. Take a new one at the shelter."
    elif require_recent_hours and ex["age_hours"] is not None and ex["age_hours"] > require_recent_hours:
        decision, reason = "rejected", f"This photo was taken {ex['age_hours']:.0f} hours ago. Take a fresh one."
    elif require_geofence and ex["within_geofence"] is False:
        decision, reason = "rejected", f"This photo was taken {ex['distance_m']} m from the shelter."
    else:
        name_seen = target["name"].split("(")[0].strip().lower()
        name_on_card = bool(name_seen) and name_seen in (out.get("visible_text") or "").lower()
        threshold = HIGH_LOOKALIKE_MATCH_AT if out["lookalike_risk"] == "high" else MATCH_AT
        if name_on_card and not out["conflicting_features"] and conf >= UNCERTAIN_AT:
            decision, reason = "match", f"It's {target['name']}, and the kennel card confirms it."
        elif conf >= threshold:
            decision, reason = "match", f"That's {target['name']}! " + (", ".join(out["matching_features"][:3]) or "")
        elif conf >= UNCERTAIN_AT:
            decision, reason = "uncertain", f"Could be {target['name']}, but it's hard to tell. Try a clearer photo of the face and body" + (" or include the kennel card." if out["lookalike_risk"] != "low" else ".")
        else:
            which = out.get("best_match", "none")
            decision, reason = "no_match", (f"That looks like a different {target['species'].lower()}." if which != "none" else f"That doesn't look like {target['name']}.")

    return VerifyResult(
        pet_id=pet_id, pet_name=target["name"], decision=decision, confidence=round(conf, 3), reason=reason.strip(),
        model_output=out, exif=ex, references_used=len(ref_urls), decoys_used=[d["id"] for d in decoys],
        seconds=round(time.time() - t0, 1),
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Is this photo the given shelter pet, taken in person?")
    ap.add_argument("--pet", required=True, help="pet id, e.g. CAIL-A-50367")
    ap.add_argument("--photo", required=True, help="path to the visitor's photo")
    ap.add_argument("--recent-hours", type=float, default=None, help="reject if EXIF says older than this")
    ap.add_argument("--geofence", action="store_true", help="reject if EXIF GPS is outside the shelter radius")
    ap.add_argument("--allow-known-photo", action="store_true", help="don't reject copies of shelter photos (testing)")
    args = ap.parse_args()
    r = verify_visit(args.pet, Path(args.photo).read_bytes(), expect_new_photo=not args.allow_known_photo,
                     require_recent_hours=args.recent_hours, require_geofence=args.geofence)
    print(json.dumps(r.to_dict(), indent=2))
    print(f"\n{r.decision.upper()} ({r.confidence:.0%}): {r.reason}", file=sys.stderr)
