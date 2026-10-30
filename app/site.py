"""Build the read-only GitHub Pages site from data/.

`python -m app.site` writes site/index.html + site/pets.json and copies the
photos/cartoons in. The page is rebuilt from data/pets.json every run, so pets
that leave the shelter's list disappear and new ones appear without anyone
editing anything.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
import time
from pathlib import Path

from . import config
from .cartoon import cartoon_path
from .photos import local_photo_path
from .pipeline import load_result
from .shelter import load_pets

SITE_DIR = config.ROOT / "site"


def build(out_dir: Path = SITE_DIR) -> dict:
    pets = load_pets()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "img").mkdir(parents=True)
    (out_dir / "cartoons").mkdir()

    rows, mock = [], False
    for pet in pets:
        r = load_result(pet)
        photo, cartoon = local_photo_path(pet), cartoon_path(pet)
        if r and photo.exists() and cartoon.exists():
            shutil.copy(photo, out_dir / "img" / photo.name)
            shutil.copy(cartoon, out_dir / "cartoons" / cartoon.name)
            mock = mock or r["models"]["breed"] == "mock"
        rows.append({**pet, "result": r})

    synced_at = json.loads(config.PETS_JSON.read_text()).get("synced_at") if config.PETS_JSON.exists() else None
    meta = {
        "built_at": int(time.time()),
        "synced_at": synced_at,
        "count": len(rows),
        "analyzed": sum(1 for r in rows if r["result"]),
        "mock": mock,
        "shelter_url": "https://www.carenorthshore.org",
    }
    (out_dir / "pets.json").write_text(json.dumps({"meta": meta, "pets": rows}, indent=1))
    (out_dir / "index.html").write_text(render(rows, meta))
    (out_dir / ".nojekyll").write_text("")
    return meta


def _card(p: dict) -> str:
    e = html.escape
    r = p["result"]
    pid = e(p["id"])
    shelter_label = e(p.get("shelter_breed") or "—") + (f" / {e(p['shelter_secondary_breed'])}" if p.get("shelter_secondary_breed") else "")
    if r:
        b = r["breed"]
        guesses = "".join(
            f'<div class="guess"><span>{e(g["breed"])}</span><span class="pct">{round(g["confidence"] * 100)}%</span></div>'
            f'<div class="bar"><i style="width:{round(g["confidence"] * 100)}%"></i></div>'
            for g in b["guesses"]
        )
        imgs = (
            f'<figure><img src="img/{pid}.jpg" alt="Photo of {e(p["name"])}" loading="lazy"><figcaption>shelter photo</figcaption></figure>'
            f'<figure><img src="cartoons/{pid}.jpg" alt="Cartoon of {e(p["name"])}" loading="lazy"><figcaption>cartoon</figcaption></figure>'
        )
        mixed = '<span class="pill">mix</span>' if b["is_mixed"] else ""
        body = f'{guesses}<p class="fact">{e(b["fun_fact"])}</p>'
    else:
        imgs = (
            f'<figure><img src="{e(p["cover_photo_url"])}" alt="Photo of {e(p["name"])}" loading="lazy"><figcaption>shelter photo</figcaption></figure>'
            f'<figure><div class="pending">cartoon coming on the next update</div><figcaption>cartoon</figcaption></figure>'
        )
        mixed, body = "", ""
    link = f'<a href="{e(p["public_url"])}" target="_blank" rel="noopener">adopt {e(p["name"])} ↗</a>' if p.get("public_url") else ""
    return f"""
<article class="card">
  <div class="imgs">{imgs}</div>
  <div class="body">
    <h2>{e(p["name"])} <span class="pill">{e(p["species"])}</span> {mixed}</h2>
    <p class="meta">Shelter label: {shelter_label} · {e(p.get("age_group") or "")} · {e(p.get("sex") or "")}</p>
    {body}
    <p class="meta">{link}</p>
  </div>
</article>"""


def render(rows: list[dict], meta: dict) -> str:
    dogs = [p for p in rows if p["species"] == "Dog"]
    cats = [p for p in rows if p["species"] == "Cat"]
    updated = time.strftime("%b %d, %Y %H:%M UTC", time.gmtime(meta["built_at"]))
    banner = (
        '<div class="banner">Preview mode: no AI keys were set when this was built, so breeds are placeholders '
        'and "cartoons" are posterized photos. Add ANTHROPIC_API_KEY and OPENAI_API_KEY as repository secrets to get real results.</div>'
        if meta["mock"] else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Breed Cartoons</title>
<meta name="description" content="Closest breed guess and a cartoon portrait for every adoptable dog and cat at C.A.R.E. North Shore.">
<style>
  :root {{ --bg:#f6f4ef; --card:#fff; --ink:#1f1d1a; --muted:#6b665e; --accent:#e4572e; --ok:#2a9d8f; --line:#e6e1d8; --warn:#fff3cd; --warn-ink:#664d03; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#17161a; --card:#232227; --ink:#f1efe9; --muted:#a39d93; --line:#34323a; --warn:#4a3b00; --warn-ink:#ffe69c; }} }}
  :root[data-theme="dark"] {{ --bg:#17161a; --card:#232227; --ink:#f1efe9; --muted:#a39d93; --line:#34323a; --warn:#4a3b00; --warn-ink:#ffe69c; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  header {{ padding:28px 16px 8px; max-width:1200px; margin:0 auto; }}
  h1 {{ margin:0 0 6px; font-size:26px; }}
  .sub {{ color:var(--muted); margin:0; }}
  .banner {{ max-width:1200px; margin:12px auto 0; padding:10px 16px; background:var(--warn); color:var(--warn-ink); border-radius:10px; font-size:14px; }}
  nav {{ max-width:1200px; margin:12px auto 0; padding:0 16px; display:flex; gap:8px; }}
  nav a {{ color:var(--ink); text-decoration:none; border:1px solid var(--line); padding:6px 12px; border-radius:999px; background:var(--card); }}
  section {{ max-width:1200px; margin:0 auto; padding:16px 16px 8px; }}
  section > h2 {{ margin:8px 0 12px; font-size:20px; }}
  .grid {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; }}
  .imgs {{ display:grid; grid-template-columns:1fr 1fr; background:#111; }}
  figure {{ margin:0; position:relative; }}
  figure img, .pending {{ width:100%; aspect-ratio:1; object-fit:cover; display:block; }}
  .pending {{ display:grid; place-items:center; color:#aaa; font-size:12px; text-align:center; padding:12px; background:#2b2a2e; }}
  figcaption {{ position:absolute; left:6px; bottom:6px; font-size:11px; background:rgba(0,0,0,.55); color:#fff; padding:2px 7px; border-radius:999px; }}
  .body {{ padding:12px 14px 14px; }}
  .body h2 {{ margin:0 0 4px; font-size:17px; }}
  .meta {{ color:var(--muted); font-size:13px; margin:4px 0; }}
  .meta a {{ color:var(--accent); }}
  .pill {{ display:inline-block; font-size:11px; padding:2px 8px; border-radius:999px; background:var(--line); color:var(--muted); vertical-align:middle; }}
  .guess {{ display:flex; justify-content:space-between; margin-top:6px; }}
  .pct {{ color:var(--muted); }}
  .bar {{ height:6px; background:var(--line); border-radius:3px; overflow:hidden; }}
  .bar i {{ display:block; height:100%; background:var(--ok); }}
  .fact {{ font-size:13px; font-style:italic; margin:8px 0 0; }}
  footer {{ max-width:1200px; margin:0 auto; padding:24px 16px 40px; color:var(--muted); font-size:13px; }}
</style>
</head>
<body>
<header>
  <h1>🐾 Who do they look like?</h1>
  <p class="sub">Every adoptable dog and cat at <a href="{meta["shelter_url"]}">C.A.R.E. North Shore</a>: the shelter photo, the closest breed guess from a vision model, and a cartoon portrait drawn from the photo.</p>
  <p class="sub">{meta["count"]} pets · {meta["analyzed"]} with cartoons · updated {updated} · refreshes automatically from the shelter's list.</p>
</header>
{banner}
<nav><a href="#dogs">Dogs ({len(dogs)})</a><a href="#cats">Cats ({len(cats)})</a></nav>
<section id="dogs"><h2>Dogs</h2><div class="grid">{"".join(_card(p) for p in dogs)}</div></section>
<section id="cats"><h2>Cats</h2><div class="grid">{"".join(_card(p) for p in cats)}</div></section>
<footer>Breed guesses are a model's best visual estimate, not a DNA test. Listing data and photos belong to C.A.R.E. North Shore via Shelterluv.</footer>
</body>
</html>
"""


if __name__ == "__main__":
    meta = build()
    print(f"site built: {meta['count']} pets, {meta['analyzed']} analyzed, mock={meta['mock']} -> {SITE_DIR}", file=sys.stderr)
