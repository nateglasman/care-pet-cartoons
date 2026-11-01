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
ASSETS_DIR = config.ROOT / "bath-game"  # standalone mini-game package, also used by the Replit app


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
    for asset in ASSETS_DIR.iterdir():
        if asset.suffix in (".css", ".js"):
            shutil.copy(asset, out_dir / asset.name)
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
        coin = (
            f'<div class="coin-wrap"><div class="coin" data-id="{pid}" tabindex="0" role="button" aria-label="Spin {e(p["name"])}\'s coin">'
            f'<div class="face front"><img src="cartoons/{pid}.webp" alt="Cartoon of {e(p["name"])}" loading="lazy" draggable="false"></div>'
            f'<div class="face back"><img src="img/{pid}.jpg" alt="Photo of {e(p["name"])}" loading="lazy" draggable="false"></div>'
            f'</div><div class="caught-badge">caught ✓</div><div class="hint">flick to spin</div></div>'
        )
        mixed = ('<span class="pill">mix</span>' if b["is_mixed"] else "") + '<span class="pill bathed" hidden>🫧 bathed</span>'
        body = (
            f'{guesses}<p class="fact">{e(b["fun_fact"])}</p>'
            f'<button class="bath-btn" data-id="{pid}" data-name="{e(p["name"])}" data-src="cartoons/{pid}.webp">🛁 Give a bath</button>'
        )
    else:
        coin = (
            f'<div class="coin-wrap"><div class="coin pending-coin" aria-hidden="true">'
            f'<div class="face front"><img src="{e(p["cover_photo_url"])}" alt="Photo of {e(p["name"])}" loading="lazy" draggable="false"></div>'
            f'</div><div class="hint">cartoon coming on the next update</div></div>'
        )
        mixed, body = "", ""
    link = f'<a href="{e(p["public_url"])}" target="_blank" rel="noopener">adopt {e(p["name"])} ↗</a>' if p.get("public_url") else ""
    return f"""
<article class="card">
  {coin}
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
<link rel="stylesheet" href="bath.css">
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
  .counter {{ margin:10px 0 0; font-size:15px; }}
  .counter a {{ color:var(--muted); }}
  .coin-wrap {{ position:relative; display:grid; place-items:center; padding:18px 0 6px; perspective:900px; background:radial-gradient(ellipse at 50% 30%, rgba(228,87,46,.10), transparent 70%); }}
  .coin {{ width:210px; height:210px; position:relative; transform-style:preserve-3d; cursor:grab; touch-action:pan-y; user-select:none; -webkit-user-select:none; outline:none; will-change:transform; }}
  .coin:focus-visible {{ filter:drop-shadow(0 0 0 3px var(--accent)); }}
  .coin.dragging {{ cursor:grabbing; }}
  .face {{ position:absolute; inset:0; border-radius:50%; overflow:hidden; backface-visibility:hidden; -webkit-backface-visibility:hidden;
           background:radial-gradient(circle at 35% 30%, #fff1c2 0%, #f3c64f 45%, #c99324 100%);
           box-shadow: inset 0 0 0 7px #d9a93a, inset 0 0 0 9px #fff0b5, inset 0 0 0 12px #b8831c, 0 10px 22px rgba(0,0,0,.28); }}
  .face img {{ width:100%; height:100%; object-fit:contain; padding:16px; display:block; pointer-events:none; }}
  .face.back {{ transform:rotateY(180deg); }}
  .face.back img {{ object-fit:cover; padding:12px; border-radius:50%; }}
  .pending-coin {{ opacity:.55; filter:grayscale(.6); cursor:default; }}
  .pending-coin .face img {{ object-fit:cover; padding:12px; border-radius:50%; }}
  .hint {{ font-size:11px; color:var(--muted); margin-top:6px; }}
  .caught-badge {{ position:absolute; top:10px; right:12px; font-size:11px; font-weight:700; padding:3px 9px; border-radius:999px; background:var(--ok); color:#fff; opacity:0; transform:scale(.6); transition:all .35s cubic-bezier(.2,1.4,.4,1); }}
  .coin-wrap.caught .caught-badge {{ opacity:1; transform:scale(1); }}
  .coin-wrap.caught .coin .face {{ box-shadow: inset 0 0 0 7px #d9a93a, inset 0 0 0 9px #fff0b5, inset 0 0 0 12px #b8831c, 0 0 0 4px rgba(42,157,143,.35), 0 10px 22px rgba(0,0,0,.28); }}
  @media (prefers-reduced-motion: reduce) {{ .caught-badge {{ transition:none; }} }}
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
  <p class="counter">🏅 Caught <strong id="caught-n">0</strong> / {meta["analyzed"]} <span class="meta">· flick or tap a coin to spin it and catch the pet · <a href="#" id="reset">reset</a></span></p>
</header>
{banner}
<nav><a href="#dogs">Dogs ({len(dogs)})</a><a href="#cats">Cats ({len(cats)})</a></nav>
<section id="dogs"><h2>Dogs</h2><div class="grid">{"".join(_card(p) for p in dogs)}</div></section>
<section id="cats"><h2>Cats</h2><div class="grid">{"".join(_card(p) for p in cats)}</div></section>
<footer>Breed guesses are a model's best visual estimate, not a DNA test. Listing data and photos belong to C.A.R.E. North Shore via Shelterluv.</footer>
<script>
(function () {{
  // --- "caught" state lives only in this browser; the page itself never changes ---
  const KEY = 'caught-pets';
  const load = () => {{ try {{ return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); }} catch (e) {{ return new Set(); }} }};
  const save = (set) => {{ try {{ localStorage.setItem(KEY, JSON.stringify([...set])); }} catch (e) {{}} }};
  let caught = load();
  const counter = document.getElementById('caught-n');
  const ids = [...document.querySelectorAll('.coin[data-id]')].map(c => c.dataset.id);
  caught = new Set([...caught].filter(id => ids.includes(id)));  // drop pets no longer listed
  const paint = () => {{
    counter.textContent = caught.size;
    document.querySelectorAll('.coin[data-id]').forEach(c => c.parentElement.classList.toggle('caught', caught.has(c.dataset.id)));
  }};
  paint();
  document.getElementById('reset').addEventListener('click', (e) => {{ e.preventDefault(); caught = new Set(); save(caught); paint(); }});

  // --- coin physics: drag to spin, flick for momentum, tap for a quick spin, settles on a face ---
  const SNAP_V = 90, FRICTION = 1.6, TAP_V = 1500, CATCH_DEG = 360;
  document.querySelectorAll('.coin[data-id]').forEach(coin => {{
    let angle = 0, v = 0, raf = null, last = 0, dragging = false, startX = 0, lastX = 0, lastT = 0, spun = 0;
    const render = () => coin.style.transform = `rotateY(${{angle}}deg)`;
    const catchIt = () => {{
      if (caught.has(coin.dataset.id)) return;
      caught.add(coin.dataset.id); save(caught); paint();
      if (navigator.vibrate) navigator.vibrate(30);
    }};
    const step = (t) => {{
      const dt = Math.min(0.05, (t - last) / 1000 || 0.016); last = t;
      if (Math.abs(v) > SNAP_V) {{
        angle += v * dt; spun += Math.abs(v * dt);
        v *= Math.exp(-FRICTION * dt);
      }} else {{
        const target = Math.round(angle / 180) * 180;
        const d = target - angle;
        if (Math.abs(d) < 0.3) {{ angle = target; v = 0; render(); raf = null; if (spun >= CATCH_DEG) catchIt(); spun = 0; return; }}
        angle += d * Math.min(1, 10 * dt); v = 0;
      }}
      render(); raf = requestAnimationFrame(step);
    }};
    const go = () => {{ if (!raf) {{ last = performance.now(); raf = requestAnimationFrame(step); }} }};
    const spin = (speed) => {{ v = speed; go(); }};

    coin.addEventListener('pointerdown', (e) => {{
      dragging = true; coin.classList.add('dragging'); coin.setPointerCapture(e.pointerId);
      startX = lastX = e.clientX; lastT = performance.now(); v = 0;
      if (raf) {{ cancelAnimationFrame(raf); raf = null; }}
    }});
    coin.addEventListener('pointermove', (e) => {{
      if (!dragging) return;
      const now = performance.now(), dx = e.clientX - lastX, dt = Math.max(1, now - lastT) / 1000;
      angle += dx * 0.8; spun += Math.abs(dx * 0.8); v = (dx * 0.8) / dt; lastX = e.clientX; lastT = now; render();
    }});
    const release = (e) => {{
      if (!dragging) return;
      dragging = false; coin.classList.remove('dragging');
      if (Math.abs(e.clientX - startX) < 6) v = TAP_V * (Math.random() < 0.5 ? -1 : 1);  // a tap = flick
      if (performance.now() - lastT > 80) v = 0;  // held still before letting go
      go();
    }};
    coin.addEventListener('pointerup', release);
    coin.addEventListener('pointercancel', release);
    coin.addEventListener('keydown', (e) => {{ if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); spin(TAP_V); }} }});
  }});
}})();
</script>
<script src="bath.js"></script>
</body>
</html>
"""


if __name__ == "__main__":
    meta = build()
    print(f"site built: {meta['count']} pets, {meta['analyzed']} analyzed, mock={meta['mock']} -> {SITE_DIR}", file=sys.stderr)
