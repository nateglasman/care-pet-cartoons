# Bath mini-game

A drop-in "give the pet a bath" game. The pet's **cartoon from its token/coin**
sits in an animated bathtub; the player scrubs it with their finger (or mouse,
which turns into a scrub brush), bubbles pop out, dirt spots fade, and after
**25 seconds of real scrubbing** the pet is squeaky clean and gets a "bathed"
badge that the browser remembers.

Two files, no dependencies, no build step:

| File | What |
|---|---|
| `bath.css` | all styling: overlay, tub, water, steam, bubbles, brush, meter |
| `bath.js` | the game + a tiny public API (`window.BathGame`) |
| `demo.html` | standalone example, open it in a browser to see it work |

It is already used by the GitHub Pages site (`app/site.py` copies these two
files into the build). The Replit app should use the **same files** so the
game stays identical in both places.

## Use the cartoon from the token

The image passed to the game must be the same cartoon the token/coin shows,
the transparent sticker the pipeline generates for each pet:

- on the Replit app it is served at **`/cartoons/{pet_id}.webp`**
  (`app/server.py`, file in `data/cartoons/`)
- on the GitHub Pages site it is `cartoons/{pet_id}.webp`

Do not generate a new image for the bath; the sticker has a transparent
background, which is what lets it sit "inside" the tub.

## Integrate in 3 steps

1. Serve `bath.css` and `bath.js` as static files and include them once per page:

   ```html
   <link rel="stylesheet" href="/static/bath.css">
   <script src="/static/bath.js"></script>
   ```

2. Open the game from the token. Either call the API from your own click
   handler (for example when the player taps the coin or a "Bath" button):

   ```js
   BathGame.open({
     id: pet.id,                        // e.g. "CAIL-A-50367"
     name: pet.name,                    // shown in the title
     image: `/cartoons/${pet.id}.webp`, // the token's cartoon
     onDone: (id) => { /* optional: award points, update the card, etc. */ },
   });
   ```

   …or just render a button and the script wires it up automatically:

   ```html
   <button class="bath-btn" data-id="CAIL-A-50367" data-name="Vera" data-src="/cartoons/CAIL-A-50367.webp">🛁 Give a bath</button>
   ```

3. Optional: show the badge. Any `<span class="pill bathed" hidden>` inside
   the same `.card` as a `.bath-btn` is un-hidden when the pet has been bathed.
   Or ask directly: `BathGame.isBathed(pet.id)`.

## API

| Call | Does |
|---|---|
| `BathGame.open({ id, name, image, onDone })` | open the tub |
| `BathGame.close()` | close it |
| `BathGame.isBathed(id)` | `true` if this browser has bathed the pet |
| `BathGame.reset()` | forget all baths in this browser |
| `BathGame.NEED` | seconds of scrubbing required |

Deep link: `#bath-<pet_id>` in the URL opens the game for that pet on load
(only when a matching `.bath-btn` exists on the page).

## Tuning

- **Duration:** `<script src="bath.js" data-seconds="10">` overrides the 25 s default (handy while testing).
- **Scrubbing rule:** the meter fills only while the pointer is held down, moving, and over the pet (plus a 24 px margin). Holding still or scrubbing the water does nothing.
- **Bubbles:** spawn every ~45 ms of movement over the pet, 1 to 2 per spawn; sizes 8 to 30 px. See `spawnBubble` in `bath.js`.
- **Dirt:** 7 random spots, opacity = 1 − progress. Count is in `open()`.
- **Colors / size:** everything is plain CSS in `bath.css`. The scene is 320 px tall and the stage is `min(440px, 100%)` wide.
- **Reduced motion:** steam, waves and wiggles are disabled when the OS asks for reduced motion.

## Behaviour notes

- Pointer Events are used, so touch and mouse behave the same. The scene sets `touch-action: none` so scrubbing never scrolls the page.
- "Bathed" state is stored in `localStorage` under `bathed-pets`; nothing is sent to a server. Wire `onDone` if you want to persist it elsewhere.
- Escape, the ✕ button, the "Done" button, or tapping the dark backdrop closes the overlay. The overlay sets `body.bath-open` to stop background scrolling.
- The game creates its own `<div id="bath">` on load, so the page needs no markup for it.
