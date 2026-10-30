# Closest breed + cartoon for C.A.R.E. North Shore adoptables

Hackathon prototype. For every dog and cat currently listed on
[carenorthshore.org/dogs](https://www.carenorthshore.org/dogs) and
[/cats](https://www.carenorthshore.org/cats) it:

1. pulls the live listing (name, photos, shelter's breed label),
2. asks a vision model for the **closest breed(s)** with confidence + a precise description of the animal,
3. generates a **cartoon portrait** from the real photo so the markings match,
4. caches everything per pet so a re-sync only spends API calls on *new* animals.

```
Shelterluv JSON ──► data/pets.json ──► photo (resized) ──► Claude vision ──► breed JSON
                                                    └────────────────────► image model ──► cartoon PNG
```

## Where the pet list comes from

The shelter's site doesn't host the list itself. Both pages embed Shelterluv
(shelter GID `3204`), and that embed is fed by a **public JSON endpoint that
needs no API key**:

```
https://new.shelterluv.com/api/v3/available-animals/3204
```

`python -m app.shelter` reads it and writes `data/pets.json`. No HTML scraping,
no Petfinder/Shelterluv API credentials, and it is the same data the website
shows, so it stays in sync whenever the shelter updates its list. (If the
shelter ever gives you a real Shelterluv API key, `app/shelter.py` is the only
file to change.)

## Models (and why)

| Step | Default | Why |
|---|---|---|
| Breed ID | Claude Opus 5.5 vision, structured JSON output | The shelter's own labels are placeholders ("Mixed Breed (Medium)", "Domestic Shorthair" for 42 of 43 cats). The useful question is *what does it look closest to*, which needs mixed-breed reasoning across dogs **and** cats. Purpose-built classifiers (e.g. ViT fine-tuned on Stanford Dogs) top out around 84% top-1 on purebreds only and have no cat classes. A vision LLM also writes the appearance description the cartoon prompt needs. Nothing to host on Replit. |
| Cartoon | OpenAI `gpt-image-1.5` via `images.edit` (photo as reference, transparent background, high input fidelity) | Image-to-image keeps the actual animal's face and markings. Alternative: Gemini image models (`CARTOON_PROVIDER=gemini`). Both are offered through Replit AI Integrations. |

Swap either by env var (see `.env.example`). `app/breed.py` is the only place
that knows about Claude; drop in CLIP/ViT there if you want a classic-CV baseline.

## GitHub Pages demo (zero-maintenance)

`.github/workflows/update.yml` keeps a static demo page alive with no one
touching the code:

1. every 6 hours (and on every push) it pulls the current list from Shelterluv,
2. analyzes only pets that are **new or have a new cover photo** (everything else is
   cached in `data/`, which the workflow commits back to the repo),
3. deletes cached files for pets that left the list,
4. rebuilds `site/` with `python -m app.site` and deploys it to GitHub Pages.

The page shows each pet as a spinnable coin: cartoon on the front, shelter
photo on the back. Flick it to spin; the first spin "catches" the pet and the
counter in the header remembers it in that browser. Bump `CARTOON_VERSION` in
`app/cartoon.py` whenever you change the cartoon prompt or format and every
cartoon is regenerated on the next run.

Setup once: **Settings → Secrets and variables → Actions** and add
`ANTHROPIC_API_KEY` and `OPENAI_API_KEY` (billed to whoever owns those keys).
Optional repository *variables*: `CARTOON_PROVIDER`, `CARTOON_MODEL`,
`CARTOON_STYLE`. Without the Anthropic secret the page still builds, in a
clearly labelled preview mode with placeholder breeds and posterized photos.

To move the cost to the shelter later, fork/transfer the repo to their GitHub
org and set their keys as secrets; nothing else changes.

## Run on Replit (the target)

1. Push this repo to GitHub, then in Replit: **Create App → Import from GitHub**.
2. In the workspace open **Integrations → AI Integrations** and enable
   **Anthropic** and **OpenAI** (or Google if you set `CARTOON_PROVIDER=gemini`).
   Replit then injects `AI_INTEGRATIONS_ANTHROPIC_API_KEY`,
   `AI_INTEGRATIONS_ANTHROPIC_BASE_URL` (and the OpenAI/Gemini equivalents)
   into the environment and the app picks them up automatically. Confirm with
   `printenv | grep AI_INTEGRATIONS` in the Replit shell.
3. Hit **Run**. `.replit` runs `python main.py`, which serves on port 8000 → 80.
4. Click **Analyze all unprocessed** (or run `python -m app.pipeline --sync` in the shell).
5. **Publish** (Autoscale) when you want a shareable URL.

### Who pays

With AI Integrations, Replit holds the provider keys and bills model usage to
the **Replit account/org that owns the app** at the providers' public API
rates, deducted from that account's credits. There is no per-provider sign-up.
That means:

- While the app lives in your (or the hackathon's) Replit account, you pay.
- To hand it to the shelter, transfer the Replit app to their account/org (or
  have them import the GitHub repo). It keeps working as long as *their*
  Replit plan has AI Integrations enabled (Core or above; Teams/Enterprise
  admins must switch it on) and has credits.
- If they would rather pay providers directly, add `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY` as Replit Secrets. Own keys always win over the Replit-managed ones.

Rough cost per pet: one vision call (~$0.01–0.03) + one 1024px image
(~$0.03–0.07). The whole current list (57 pets) is a few dollars, and only new
pets cost anything after that.

## Run locally

```bash
uv venv --python 3.12 .venv && uv pip install -r requirements.txt   # or: pip install -r requirements.txt
cp .env.example .env                                                  # fill in keys, or set MOCK_AI=1
export $(grep -v '^#' .env | xargs)
python -m app.shelter          # fetch the current list -> data/pets.json
python main.py                 # http://localhost:8000
```

`MOCK_AI=1` runs the entire pipeline with no API calls (placeholder breed,
posterized photo as the "cartoon") so you can demo the UI and the caching with
zero spend.

Batch mode: `python -m app.pipeline --sync [--prune] [--species Dog|Cat] [--limit N] [--force]`, then `python -m app.site` for the static page.

## Project layout

```
main.py             uvicorn entry (Replit runs this)
app/config.py       env + credential resolution (own key > Replit AI Integrations > mock)
app/shelter.py      Shelterluv sync -> data/pets.json
app/photos.py       download + resize cover photo once
app/breed.py        Claude vision -> BreedResult (pydantic, strict JSON schema)
app/cartoon.py      OpenAI images.edit / Gemini generate_content -> PNG
app/pipeline.py     orchestration + per-pet cache (data/results/<id>.json)
app/server.py       FastAPI: /api/pets, /api/pets/{id}/analyze, /api/sync, /api/status
static/index.html   gallery UI
tests/              sync normalizer test with a real Shelterluv fixture
app/site.py         static GitHub Pages builder -> site/
data/               cache (pets.json, photos, cartoons, results); committed by the Action
.github/workflows   scheduled sync + Pages deploy
```

### Cache / reproducibility rules

- Results are keyed by Shelterluv `uniqueId` and the cover photo id. New photo ⇒ re-analyzed. Same photo ⇒ reused forever.
- `data/` is committed, so a fresh clone (Replit import included) already has
  every cartoon generated so far. On a Replit Autoscale deployment the filesystem
  is ephemeral, so new pets analyzed there are lost on redeploy; for production,
  keep the GitHub Action as the system of record (it commits results) and have
  Replit pull from GitHub, or move the cache to Replit Object Storage / a DB.
- The UI serializes model calls (2 at a time) so a small box or a rate limit doesn't fall over.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/status` | which models / credential source are active |
| GET | `/api/pets?species=Dog` | list with cached results attached |
| POST | `/api/sync` | re-pull from Shelterluv |
| POST | `/api/pets/{id}/analyze?force=&style=` | run (or re-run) one pet; `style` overrides `CARTOON_STYLE` |
| GET | `/photos/{id}.jpg`, `/cartoons/{id}.webp` | files |
