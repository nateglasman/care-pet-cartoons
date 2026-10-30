import json
from pathlib import Path

from app.shelter import normalize

FIXTURE = Path(__file__).parent / "fixtures" / "shelterluv_sample.json"


def test_normalize_handles_dict_and_list_photos():
    raw = json.loads(FIXTURE.read_text())
    pets = normalize(raw)
    assert len(pets) == 2
    by_id = {p["id"]: p for p in pets}
    # dict-shaped photos: cover first even though it's not index 0
    gaia = by_id["CAIL-A-3215"]
    assert gaia["species"] == "Cat"
    assert gaia["cover_photo_id"] == 42524183
    assert gaia["cover_photo_url"].endswith("36768fa53f3c1c3df6df4c999bb8a75f.png")
    # list-shaped photos
    roger = by_id["CAIL-A-5131"]
    assert roger["species"] == "Dog"
    assert roger["cover_photo_id"] == raw["animals"][1]["photos"][3]["id"]  # cover was last in the list


def test_pets_without_photos_are_dropped():
    raw = {"animals": [{"uniqueId": "X-1", "name": "Ghost", "species": "Dog", "photos": []}]}
    assert normalize(raw) == []
