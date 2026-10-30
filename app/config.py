"""Environment / credential resolution.

Priority for every provider:
  1. Your own key (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY) -> billed to you.
  2. Replit AI Integrations (AI_INTEGRATIONS_<PROVIDER>_API_KEY + _BASE_URL)
     -> billed to the Replit account that owns the app at public API rates.
  3. Nothing -> the provider is "unavailable"; set MOCK_AI=1 to run without any model.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PHOTOS_DIR = DATA_DIR / "photos"
CARTOONS_DIR = DATA_DIR / "cartoons"
RESULTS_DIR = DATA_DIR / "results"
PETS_JSON = DATA_DIR / "pets.json"

for _d in (PHOTOS_DIR, CARTOONS_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SHELTERLUV_SHELTER_ID = os.environ.get("SHELTERLUV_SHELTER_ID", "3204")
SHELTERLUV_URL = f"https://new.shelterluv.com/api/v3/available-animals/{SHELTERLUV_SHELTER_ID}"

MOCK_AI = os.environ.get("MOCK_AI", "").strip().lower() in {"1", "true", "yes"}

BREED_MODEL = os.environ.get("BREED_MODEL", "claude-opus-5-5")
CARTOON_PROVIDER = os.environ.get("CARTOON_PROVIDER", "openai").strip().lower()
CARTOON_MODEL = os.environ.get("CARTOON_MODEL") or {
    "openai": "gpt-image-2",
    "gemini": "gemini-2.5-flash-image",
}.get(CARTOON_PROVIDER, "gpt-image-2")
CARTOON_STYLE = os.environ.get(
    "CARTOON_STYLE",
    "friendly flat-color cartoon with bold clean outlines and soft shading, "
    "like a character from a modern animated series",
)

# Longest side the shelter photo is resized to before it's sent to any model.
PHOTO_MAX_PX = int(os.environ.get("PHOTO_MAX_PX", "1024"))


@dataclass(frozen=True)
class Credentials:
    api_key: str | None
    base_url: str | None
    source: str  # "own-key" | "replit" | "none"

    @property
    def available(self) -> bool:
        return bool(self.api_key)


def _resolve(own_key: str, own_base: str, replit_prefix: str) -> Credentials:
    key = os.environ.get(own_key)
    if key:
        return Credentials(key, os.environ.get(own_base) or None, "own-key")
    key = os.environ.get(f"AI_INTEGRATIONS_{replit_prefix}_API_KEY")
    if key:
        return Credentials(key, os.environ.get(f"AI_INTEGRATIONS_{replit_prefix}_BASE_URL") or None, "replit")
    return Credentials(None, None, "none")


def anthropic_credentials() -> Credentials:
    return _resolve("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC")


def openai_credentials() -> Credentials:
    return _resolve("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI")


def gemini_credentials() -> Credentials:
    return _resolve("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI")


def status() -> dict:
    """Small summary the UI shows so you can tell what's wired up."""
    a, o, g = anthropic_credentials(), openai_credentials(), gemini_credentials()
    return {
        "mock_ai": MOCK_AI,
        "breed_model": BREED_MODEL,
        "breed_credentials": a.source,
        "cartoon_provider": CARTOON_PROVIDER,
        "cartoon_model": CARTOON_MODEL,
        "cartoon_credentials": (o if CARTOON_PROVIDER == "openai" else g).source,
        "cartoon_style": CARTOON_STYLE,
        "shelterluv_shelter_id": SHELTERLUV_SHELTER_ID,
    }
