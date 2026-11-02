# Play fetch

Pull the tennis ball toward you and let go (slingshot), or flick it up the
field. The ball flies with height, gravity, bounces and perspective; the pet's
**token** gallops after it, grabs it, trots back and drops it at your hand.
Five fetches finish the game. Best throw distance is tracked.

Files: `fetch.css`, `fetch.js` (game + `window.FetchGame` API), `demo.html`. No dependencies, no build step.

## Use the cartoon from the token

Pass the token's image: on Replit it is `/cartoons/{pet_id}.webp`.

## Integrate

```html
<link rel="stylesheet" href="/static/fetch.css">
<script src="/static/fetch.js"></script>
```
```js
FetchGame.open({ id: pet.id, name: pet.name, image: `/cartoons/${pet.id}.webp`,
                 onDone: (id, { fetches, bestThrowMeters }) => { /* award points */ } });
```
…or render `<button class="fetch-btn" data-id data-name data-src>`. A `<span class="pill played" hidden>` inside the same `.card` is shown once played. Deep link: `#fetch-<pet_id>`.

API: `open(opts)`, `close()`, `isDone(id)`, `reset()`.

## How the throw works

- Press on the scene while the ball is in your hand, drag **down/back**, release: slingshot with power from the pull distance.
- A fast upward flick instead throws in the flick direction.
- Too weak a pull (or pulling the wrong way) just puts the ball back with a hint.
- Horizontal and far bounds bounce the ball; the dog waits for it to come down before grabbing.

## Tuning

- `FETCHES_NEEDED` (5), gravity `G` (1400), velocity clamps in `release()`, dog speeds (260 chasing, 230 returning px/s).
- `metersOf()` is the playful distance scale shown in the HUD.
- Visuals in `fetch.css`: park gradient, fence line, trees, hand, ball.
