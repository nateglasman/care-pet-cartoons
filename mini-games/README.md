# Pet care mini-games

Four drop-in games for the "take care of a shelter pet" app. They share one
look (overlay card, meter, message line, sparkles on completion) and one API
pattern, so wiring one wires them all. Plain CSS + JS, no dependencies, no
build step. Each game uses the **cartoon from the pet's token**.

| Folder | Game | Goal | Finish stats passed to `onDone` |
|---|---|---|---|
| `bath/` | 🛁 Give a bath | scrub the pet with your finger for 25 s of real scrubbing | – |
| `walk/` | 🦮 Walk the dog | lead the token around a stylized map of Skokie from C.A.R.E., visit 3 spots, come home | `{ meters, spots }` |
| `fetch/` | 🎾 Play fetch | flick the tennis ball, the token brings it back, 5 times | `{ fetches, bestThrowMeters }` |
| `feed/` | 🥣 Feed | scoop the right portion for the pet's size, serve, pet it while it eats | `{ portion }` |

Each folder has `<game>.css`, `<game>.js`, a `demo.html` you can open in a
browser, and its own README with tuning knobs. `demo.html` in this folder runs
all four on one token.

## Use the cartoon from the token

Every game takes an `image` URL. Pass the token's cartoon, the transparent
sticker the pipeline generates: on the Replit app it is served at
**`/cartoons/{pet_id}.webp`** (`data/cartoons/` on disk). Do not generate new
art for the games; the transparent background is what lets the token sit in
the tub, on the map, in the park and at the bowl.

## Integrate (all four)

1. Serve the eight files as static assets and include them once per page:

   ```html
   <link rel="stylesheet" href="/static/bath.css">
   <link rel="stylesheet" href="/static/walk.css">
   <link rel="stylesheet" href="/static/fetch.css">
   <link rel="stylesheet" href="/static/feed.css">
   <script src="/static/bath.js"></script>
   <script src="/static/walk.js"></script>
   <script src="/static/fetch.js"></script>
   <script src="/static/feed.js"></script>
   ```

2. Open a game from your own UI (the token, a menu, a quest card):

   ```js
   const pet = { id: 'CAIL-A-50367', name: 'Vera', species: 'Dog', shelter_breed: 'Mixed Breed (Large)' };
   const image = `/cartoons/${pet.id}.webp`;

   BathGame.open({ id: pet.id, name: pet.name, image, onDone: (id) => award(id, 'bath') });
   WalkGame.open({ id: pet.id, name: pet.name, image, onDone: (id, s) => award(id, 'walk', s.meters) });
   FetchGame.open({ id: pet.id, name: pet.name, image, onDone: (id, s) => award(id, 'fetch', s.bestThrowMeters) });
   FeedGame.open({ id: pet.id, name: pet.name, image, species: pet.species, sizeLabel: pet.shelter_breed,
                   onDone: (id, s) => award(id, 'feed') });
   ```

   …or render buttons and they wire themselves:

   ```html
   <button class="bath-btn"  data-id="CAIL-A-50367" data-name="Vera" data-src="/cartoons/CAIL-A-50367.webp">🛁 Bath</button>
   <button class="walk-btn"  data-id="CAIL-A-50367" data-name="Vera" data-src="/cartoons/CAIL-A-50367.webp">🦮 Walk</button>
   <button class="fetch-btn" data-id="CAIL-A-50367" data-name="Vera" data-src="/cartoons/CAIL-A-50367.webp">🎾 Fetch</button>
   <button class="feed-btn"  data-id="CAIL-A-50367" data-name="Vera" data-src="/cartoons/CAIL-A-50367.webp"
           data-species="Dog" data-size-label="Mixed Breed (Large)">🥣 Feed</button>
   ```

3. Completion state is remembered per browser in `localStorage`
   (`bathed-pets`, `walked-pets`, `played-pets`, `fed-pets`). Every game exposes
   `isDone(id)` and `reset()`. For real scoring, persist in `onDone` on the
   server instead of trusting the browser.

## API, identical across games

| Call | Does |
|---|---|
| `XGame.open({ id, name, image, onDone, ... })` | open the game for one pet |
| `XGame.close()` | close it |
| `XGame.isDone(id)` | this browser has completed it for that pet |
| `XGame.reset()` | forget completions in this browser |

Deep links open a game on page load when a matching button exists:
`#bath-<id>`, `#walk-<id>`, `#fetch-<id>`, `#feed-<id>`.

## Suggested points (the game's call)

| Action | Points | Notes |
|---|---|---|
| Feed | 10 | once per pet per day |
| Bath | 15 | once per pet per day |
| Fetch | 15 | + 1 per meter of best throw |
| Walk | 20 | + 1 per 100 m |
| Visit in person (see `visit-verify/`) | 200 | once per pet per day; the big one |

## Behaviour notes

- Pointer Events throughout; touch and mouse behave the same, scenes set `touch-action: none` so play never scrolls the page.
- Escape, ✕, the Done button, or tapping the dark backdrop closes any game. Opening sets `body.<game>-open` to stop background scrolling.
- Each game creates its own overlay element on load; the page needs no markup.
- Reduced-motion users get the games without the idle animations.
- Styles only use `--line`, `--card`, `--ink` CSS variables for the card buttons, with fallbacks, so they look fine on any page.
