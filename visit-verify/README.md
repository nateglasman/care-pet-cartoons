# Visit verification: "did you really go see this pet?"

A visitor photographs the pet they are caring for in the game, at the shelter.
This folder decides whether that photo shows **the same individual animal**,
taken **in person**, so the app can award the big visit bonus. It uses the same
Claude vision approach as the breed identifier, with no extra models to host.

```
visitor photo ─┐
               ├─► Claude (vision, strict JSON) ─► policy ─► match | uncertain | no_match | rejected
target pet ────┤      ▲ up to 4 shelter photos of the target
               │      ▲ up to 3 "decoy" lookalikes from the same shelter
               └──────▲ staff appearance description (from the breed step, if present)
```

## Files

| File | What |
|---|---|
| `verify.py` | the whole thing: `verify_visit(pet_id, photo_bytes) -> VerifyResult`, plus a CLI |
| `PROMPT.md` | the rubric the model follows; edit this to change what counts as a match |
| `api_example.py` | a FastAPI route (`POST /api/pets/{id}/verify-visit`) to paste into the Replit app |
| `calibrate.py` | measures leniency against the shelter's own photos; results in `calibration.json` |
| `requirements.txt` | `anthropic`, `pillow` |

## What it needs

- **Credentials:** `ANTHROPIC_API_KEY`, or Replit AI Integrations (Anthropic) which provides `AI_INTEGRATIONS_ANTHROPIC_API_KEY` / `_BASE_URL`. Same rule as the rest of the app.
- **The pet list:** `data/pets.json` from the main repo (set `PETS_JSON` if it lives elsewhere). If the file is missing it pulls the list live from Shelterluv, so the folder also works on its own.
- **Reference photos:** downloaded from Shelterluv on first use and cached in `.cache/` (set `REF_CACHE_DIR`). Every pet has between 1 and ~30 staff photos; the first 4 are used.
- Optional: `data/results/<id>.json` from the breed step, whose `appearance` text is added as context.

## How a decision is made

1. The model sees the target's reference photos, up to three decoys (other pets of the same species, preferring the same color and breed label), the staff description, and the visitor's photo last. It must say whether the candidate is the **target**, a **decoy**, or **none**, with a 0 to 1 confidence, the matching and conflicting features, a lookalike-risk rating, any readable kennel-card text, and authenticity flags.
2. Policy in `verify_visit` turns that into one of four decisions:

| Decision | When | Game should |
|---|---|---|
| `match` | confidence ≥ 0.50, or the kennel card shows the pet's name with no conflicting features | award visit points |
| `uncertain` | confidence 0.25 to 0.50 | no points; ask for a clearer face-and-body photo, or one with the kennel card |
| `no_match` | below 0.25, no animal, or wrong species | no points |
| `rejected` | photo of a screen/print, an illustration, or a copy of a shelter photo; optionally stale EXIF time or out-of-area GPS | no points, explain why |

The thresholds are the constants at the top of `verify.py`. They were set from the calibration below: lenient on angle, lighting and quality, but a genuine "no" when permanent features disagree.

## Anti-gaming

- **Copied shelter photos** are flagged by the model as duplicates of a reference and rejected (`expect_new_photo=True`).
- **Photos of screens or prints** and **drawings/cartoons/stickers** are flagged and rejected.
- **Decoys** force the model to pick *this* dog over similar dogs rather than answering "yes, that's a brown dog".
- **Kennel card** text, when readable, is treated as strong evidence. For hard-to-distinguish animals (most of the cats here are brown tabbies), the UI should actively ask visitors to include the kennel card in the frame.
- **EXIF bonuses** (`exif_signals`): capture time and GPS distance to 4927 Main St, Skokie. Phones strip these on most uploads, so they're off by default; turn on `require_recent_hours` / `require_geofence` only if your upload path preserves EXIF. A better location signal is the browser's geolocation at upload time, which the Replit app can check before calling the verifier.

## Honest limits

- Cats at this shelter are mostly domestic shorthair tabbies, so photo-only identity is inherently weaker for cats than dogs. Genuine tabby photos scored as low as 0.55 in calibration. `HIGH_LOOKALIKE_MATCH_AT` lets you demand more for those cases (it is 0.50 now, the same as `MATCH_AT`), and a visible kennel card is rewarded.
- Pets with a single reference photo (a couple of dogs) are verified from that one photo plus the description.
- One check costs roughly 5 cents (about 8 images in, small JSON out) and takes 15 to 40 seconds. Rate-limit per user in the app; the example route allows two concurrent checks.

## Calibration

`python calibrate.py --dogs 6 --cats 6` holds one photo of each pet out of the
reference set and submits it as a visitor photo (should match), then submits a
photo of the most similar *other* pet (should not). See `calibration.json` and
the results table below.

Run on 2026-11-01 with the thresholds above (24 checks, about $1.50):

| Species | Case | Correct | Confidence range |
|---|---|---|---|
| Dog | positive (same animal, new photo) | 6/6 | 0.85 to 0.95 |
| Dog | negative (closest lookalike) | 6/6 | 0.01 to 0.01 |
| Cat | positive (same animal, new photo) | 6/6 | 0.55 to 0.93 |
| Cat | negative (closest lookalike) | 6/6 | 0.01 to 0.03 |

| Pet | Case | Candidate | Decision | Confidence | Lookalike risk |
|---|---|---|---|---|---|
| Arty | positive | Arty | match | 0.93 | medium |
| Arty | negative | Fluffy | no_match | 0.01 | low |
| Bonchon | positive | Bonchon | match | 0.93 | low |
| Bonchon | negative | Dahlia | no_match | 0.01 | low |
| Bruno | positive | Bruno | match | 0.85 | medium |
| Bruno | negative | Jerry | no_match | 0.01 | low |
| Dahlia | positive | Dahlia | match | 0.93 | low |
| Dahlia | negative | Bonchon | no_match | 0.01 | low |
| Hutch | positive | Hutch | match | 0.85 | medium |
| Hutch | negative | Bonchon | no_match | 0.01 | low |
| Jack | positive | Jack | match | 0.95 | low |
| Jack | negative | Vera | no_match | 0.01 | low |
| Addison (k2026) | positive | Addison (k2026) | match | 0.60 | high |
| Addison (k2026) | negative | Angela (2026) | no_match | 0.01 | low |
| Angela (2026) | positive | Angela (2026) | match | 0.93 | low |
| Angela (2026) | negative | Addison (k2026) | no_match | 0.01 | low |
| Bella (2026) | positive | Bella (2026) | match | 0.55 | high |
| Bella (2026) | negative | Maria (aka Ahjumma) | no_match | 0.03 | high |
| Burt (c2026) | positive | Burt (c2026) | match | 0.88 | medium |
| Burt (c2026) | negative | Addison (k2026) | no_match | 0.01 | low |
| Damen | positive | Damen | match | 0.88 | high |
| Damen | negative | Gia | no_match | 0.02 | high |
| Eileen | positive | Eileen | match | 0.88 | medium |
| Eileen | negative | Addison (k2026) | no_match | 0.01 | low |

Reading it: every genuine photo matched and every lookalike was refused, with a
wide gap between them (genuine 0.55 to 0.95, lookalike 0.01 to 0.03). The two
closest calls were tabby kittens (Addison 0.60, Bella 0.55), exactly the
high-lookalike cats; a kennel card in frame is what makes those comfortable.
Re-run after editing `PROMPT.md` or the thresholds, and expand `--dogs/--cats`
as the list changes.

Anti-gaming spot checks (same day): submitting the shelter's own cover photo of
Vera was **rejected** as a duplicate of a reference, and submitting her cartoon
sticker was **rejected** as an illustration.

## Try it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...            # not needed on Replit with AI Integrations
python verify.py --pet CAIL-A-50367 --photo my_visit.jpg
python verify.py --pet CAIL-A-50367 --photo my_visit.jpg --allow-known-photo   # testing with a shelter photo
```

## Integrating in the Replit app

1. Copy this folder into the app (keep it as `visit-verify/`), add its two requirements.
2. Paste the route from `api_example.py` into the server, or `include_router` it.
3. From the client, `POST` the captured photo as multipart `photo` to `/api/pets/{id}/verify-visit` and branch on `decision`. `reason` is written to be shown to the player as-is.
4. Points are the game's call; a suggested shape: `match` = full visit bonus once per pet per day, `uncertain` = free retry with the hint shown, everything else = no points.
