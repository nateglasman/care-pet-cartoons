"""Download + resize a pet's cover photo once; every model call reuses the file."""
from __future__ import annotations

import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

from . import config
from .shelter import USER_AGENT


def local_photo_path(pet: dict) -> Path:
    return config.PHOTOS_DIR / f"{pet['id']}.jpg"


def ensure_photo(pet: dict) -> Path:
    """Return a local, EXIF-rotated, max-1024px JPEG of the cover photo."""
    path = local_photo_path(pet)
    if path.exists():
        return path
    req = urllib.request.Request(pet["cover_photo_url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((config.PHOTO_MAX_PX, config.PHOTO_MAX_PX))
    img.save(path, "JPEG", quality=90)
    return path
