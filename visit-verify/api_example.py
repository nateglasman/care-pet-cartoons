"""Example of mounting the verifier in the Replit FastAPI app.

Copy the route into app/server.py (or include this router), then POST a photo:

    curl -F photo=@visit.jpg https://<your-app>/api/pets/CAIL-A-50367/verify-visit

Response: the VerifyResult as JSON. `decision` is what the game should act on:
    match      -> award the visit points
    uncertain  -> no points yet; ask for a clearer photo (face + body, include kennel card)
    no_match   -> different animal; no points
    rejected   -> screen/print/copied photo (or stale/out-of-area EXIF when enabled); no points
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile

from verify import verify_visit

router = APIRouter()
_lock = asyncio.Semaphore(2)  # a few checks at a time is plenty on a small box


@router.post("/api/pets/{pet_id}/verify-visit")
async def verify_visit_route(pet_id: str, photo: UploadFile = File(...)):
    data = await photo.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "photo too large")
    async with _lock:
        try:
            result = await asyncio.to_thread(
                verify_visit, pet_id, data,
                expect_new_photo=True,        # reject copies of the shelter's own photos
                require_recent_hours=None,    # e.g. 6 to reject old camera-roll photos when EXIF survives
                require_geofence=False,       # True to reject EXIF GPS outside the shelter radius
            )
        except KeyError:
            raise HTTPException(404, f"unknown pet {pet_id}")
        except Exception as e:
            raise HTTPException(502, str(e))
    return result.to_dict()
