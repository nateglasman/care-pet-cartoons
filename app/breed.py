"""Breed identification from a photo.

Why a vision LLM instead of a classic fine-tuned classifier?
  * Shelter labels are nearly useless ("Mixed Breed (Medium)", "Domestic
    Shorthair" for 42 of 43 cats). The task is really "what does this animal
    look *closest* to", which needs mixed-breed reasoning, not a 120-way
    Stanford-Dogs softmax (the best public ViT there is ~84% top-1 and has no
    cat classes at all).
  * One model handles dogs and cats, gives a ranked list with confidence,
    and describes the markings we need for the cartoon prompt anyway.
  * Nothing to host: no PyTorch on a Replit box.

Swap `identify()` for a CLIP / ViT call if you want a non-LLM baseline; the
rest of the pipeline only depends on the BreedResult shape.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from pydantic import BaseModel, Field

from . import config

SPECIES = ("Dog", "Cat")


class BreedGuess(BaseModel):
    breed: str = Field(description="Breed name, e.g. 'Labrador Retriever' or 'Domestic Shorthair (tabby)'")
    confidence: float = Field(ge=0, le=1, description="0-1 confidence that this breed dominates the animal's appearance")
    reason: str = Field(description="One sentence on the visual cues (ears, coat, muzzle, build, markings) behind this guess")


class BreedResult(BaseModel):
    species: str = Field(description="'Dog' or 'Cat'")
    is_mixed: bool = Field(description="True if the animal looks like a mix rather than a single purebred")
    guesses: list[BreedGuess] = Field(description="Closest breeds, most likely first; 1 to 3 entries")
    appearance: str = Field(
        description=(
            "2-3 sentences describing coat color/pattern, ear shape, eye color, size/build, "
            "and any distinctive markings, written so an illustrator could draw this exact animal"
        )
    )
    fun_fact: str = Field(description="One short, upbeat sentence about the top breed that a shelter could put on an adoption card")


_SCHEMA = BreedResult.model_json_schema()


def _strict(schema: dict) -> dict:
    """Structured outputs want additionalProperties=false everywhere."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema.setdefault("additionalProperties", False)
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
        for v in schema.values():
            _strict(v)
    elif isinstance(schema, list):
        for v in schema:
            _strict(v)
    return schema


_strict(_SCHEMA)


def _prompt(pet: dict) -> str:
    return (
        f"This is an adoptable {pet['species'].lower()} named {pet['name']} at an animal shelter. "
        f"The shelter listed it as '{pet.get('shelter_breed') or 'unknown'}'"
        + (f" / '{pet['shelter_secondary_breed']}'" if pet.get("shelter_secondary_breed") else "")
        + ", which is usually a placeholder. "
        "Based only on what you can see in the photo, identify the closest breed(s). "
        "If it looks mixed, say so and rank the likely contributing breeds. "
        "For cats, use common breed/coat types (Domestic Shorthair tabby, tuxedo, Siamese mix, Maine Coon mix, etc.). "
        "Then describe the animal's appearance precisely enough for an illustrator."
    )


def identify(pet: dict, photo_path: Path) -> BreedResult:
    if config.MOCK_AI:
        return _mock(pet)

    import anthropic

    creds = config.anthropic_credentials()
    if not creds.available:
        raise RuntimeError(
            "No Anthropic credentials: set ANTHROPIC_API_KEY, enable Replit AI Integrations, or set MOCK_AI=1"
        )
    client = anthropic.Anthropic(api_key=creds.api_key, base_url=creds.base_url)

    image_b64 = base64.standard_b64encode(photo_path.read_bytes()).decode("utf-8")
    response = client.messages.create(
        model=config.BREED_MODEL,
        max_tokens=2048,
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": _SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
                    {"type": "text", "text": _prompt(pet)},
                ],
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model declined: {getattr(response.stop_details, 'explanation', '')}")
    text = next(b.text for b in response.content if b.type == "text")
    result = BreedResult.model_validate(json.loads(text))
    result.guesses = result.guesses[:3]
    return result


def _mock(pet: dict) -> BreedResult:
    dog = pet["species"] == "Dog"
    return BreedResult(
        species=pet["species"],
        is_mixed=True,
        guesses=[
            BreedGuess(breed="Labrador Retriever" if dog else "Domestic Shorthair (tabby)", confidence=0.55, reason="(mock) placeholder guess"),
            BreedGuess(breed="Border Collie" if dog else "Maine Coon mix", confidence=0.25, reason="(mock) placeholder guess"),
        ],
        appearance=f"(mock) A {pet.get('color') or 'brown'} {pet['species'].lower()} with bright eyes and a friendly expression.",
        fun_fact="(mock) Set real API keys or enable Replit AI Integrations to get a real answer.",
    )
