"""Turn the shelter photo + breed description into a cartoon portrait.

Two providers, both available through Replit AI Integrations (no key needed
on Replit) or your own key:

  openai  -> images.edit with the photo as a reference (default: gpt-image-2)
  gemini  -> generate_content with the photo inline (default: gemini-2.5-flash-image)

Pick with CARTOON_PROVIDER / CARTOON_MODEL. Both take the real photo as input,
so the cartoon keeps the animal's actual markings instead of drawing a generic
breed.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

# Cartoons are committed to git by the GitHub Action, so keep them small.
CARTOON_MAX_PX = 768

from . import config
from .breed import BreedResult


def cartoon_prompt(pet: dict, breed: BreedResult, style: str | None = None) -> str:
    top = breed.guesses[0].breed if breed.guesses else pet["species"]
    return (
        f"Redraw the {pet['species'].lower()} in this photo as a {style or config.CARTOON_STYLE}. "
        f"It is a {top}{' mix' if breed.is_mixed else ''} named {pet['name']}. "
        f"Keep its real appearance: {breed.appearance} "
        "Keep the same face, ear shape, coat colors and markings so it is clearly the same animal. "
        "Happy, approachable expression, full head and shoulders centered in frame, "
        "simple warm single-color background, no text, no watermark, no collar tag text."
    )


def cartoon_path(pet: dict) -> Path:
    return config.CARTOONS_DIR / f"{pet['id']}.jpg"


def _save(image_bytes: bytes, out: Path) -> None:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((CARTOON_MAX_PX, CARTOON_MAX_PX))
    img.save(out, "JPEG", quality=88)


def generate(pet: dict, breed: BreedResult, photo_path: Path, style: str | None = None) -> Path:
    out = cartoon_path(pet)
    prompt = cartoon_prompt(pet, breed, style)
    if config.MOCK_AI:
        _mock(photo_path, out)
    elif config.CARTOON_PROVIDER == "gemini":
        _gemini(prompt, photo_path, out)
    else:
        _openai(prompt, photo_path, out)
    return out


def _openai(prompt: str, photo_path: Path, out: Path) -> None:
    from openai import OpenAI

    creds = config.openai_credentials()
    if not creds.available:
        raise RuntimeError("No OpenAI credentials: set OPENAI_API_KEY, enable Replit AI Integrations, or set MOCK_AI=1")
    client = OpenAI(api_key=creds.api_key, base_url=creds.base_url)
    with photo_path.open("rb") as f:
        result = client.images.edit(
            model=config.CARTOON_MODEL,
            image=[f],
            prompt=prompt,
            size="1024x1024",
            quality="medium",
            output_format="png",
        )
    data = result.data[0].b64_json
    if not data:
        raise RuntimeError("OpenAI returned no image data")
    _save(base64.b64decode(data), out)


def _gemini(prompt: str, photo_path: Path, out: Path) -> None:
    from google import genai
    from google.genai import types

    creds = config.gemini_credentials()
    if not creds.available:
        raise RuntimeError("No Gemini credentials: set GEMINI_API_KEY, enable Replit AI Integrations, or set MOCK_AI=1")
    http_options = types.HttpOptions(base_url=creds.base_url) if creds.base_url else None
    client = genai.Client(api_key=creds.api_key, http_options=http_options)
    response = client.models.generate_content(
        model=config.CARTOON_MODEL,
        contents=[
            types.Part.from_bytes(data=photo_path.read_bytes(), mime_type="image/jpeg"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="1:1"),
        ),
    )
    for part in response.parts or []:
        if part.inline_data and part.inline_data.data:
            _save(part.inline_data.data, out)
            return
    raise RuntimeError("Gemini returned no image part")


def _mock(photo_path: Path, out: Path) -> None:
    """No API: posterize the photo so the UI still has something cartoon-ish to show."""
    img = Image.open(photo_path).convert("RGB")
    img = ImageOps.posterize(ImageOps.autocontrast(img), 3)
    img = img.quantize(colors=12).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    _save(buf.getvalue(), out)
