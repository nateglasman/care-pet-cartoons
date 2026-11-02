# Walk the dog

Nintendogs-style stroll. The pet's **token** (the same cartoon as the coin) trots
after your finger around a stylized map of Skokie, IL, starting at
**C.A.R.E. (4927 Main St)**. Visit 3 of the 4 spots, then bring the pet back
home to finish. Distance is shown in approximate meters, paw prints trail
behind, the leash pulls tight when you get ahead, and standing still by a
hydrant earns a sniff.

Files: `walk.css`, `walk.js` (game + `window.WalkGame` API), `demo.html`. No dependencies, no build step.

## Use the cartoon from the token

Pass the token's image: on Replit it is `/cartoons/{pet_id}.webp`, the transparent sticker from the pipeline.

## Integrate

```html
<link rel="stylesheet" href="/static/walk.css">
<script src="/static/walk.js"></script>
```
```js
WalkGame.open({ id: pet.id, name: pet.name, image: `/cartoons/${pet.id}.webp`,
                onDone: (id, { meters, spots }) => { /* award points */ } });
```
…or render `<button class="walk-btn" data-id data-name data-src>` and it wires itself. A `<span class="pill walked" hidden>` inside the same `.card` is shown once walked. Deep link: `#walk-<pet_id>`.

API: `open(opts)`, `close()`, `isDone(id)`, `reset()`.

## The map

Streets and landmarks are real (Dempster, Main, Oakton, Skokie Blvd, Laramie,
Lincoln, Niles Center Rd, the Skokie Swift and its Dempster/Oakton stations,
the North Shore Channel and Sculpture Park, Laramie Park, Oakton Park, the
library, downtown Skokie) but placement is **stylized**, not to scale. It's
inline SVG at the top of `walk.js` in a 400 × 360 unit space; `SPOTS`, `HOME`
and `HYDRANTS` use the same coordinates, so moving a landmark is a number edit.

## Tuning

- `SPOTS_NEEDED` (3), `SPEED` (110 units/s), `METERS_PER_UNIT` (5).
- Waypoint radius is 20 units, home radius 22; leash goes "tight" (faster trot) beyond 90 units.
- Everything visual is in `walk.css`; the token reuses the coin look.
