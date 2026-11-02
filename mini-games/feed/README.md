# Feed the pet

Two short phases, same look as the bath:

1. **Scoop the right portion.** Press on the kibble bag to pick up the scoop,
   carry it over the bowl and hold to pour. A gauge on the right shows the
   **green zone for this pet's size** (½ cup small, 1 cup medium, 2 cups large;
   cats are small). Overfill turns it red; tap the bowl to tip some back.
   When the level is in the zone a **Serve** button pops up.
2. **Dinner.** The token slides down to the bowl and crunches through it
   ("crunch", "nom" particles). Tapping the pet while it eats throws hearts
   and adds happiness. The game finishes when the bowl is empty.

Files: `feed.css`, `feed.js` (game + `window.FeedGame` API), `demo.html`. No dependencies, no build step.

## Use the cartoon from the token

Pass the token's image: on Replit it is `/cartoons/{pet_id}.webp`.

## Integrate

```html
<link rel="stylesheet" href="/static/feed.css">
<script src="/static/feed.js"></script>
```
```js
FeedGame.open({ id: pet.id, name: pet.name, image: `/cartoons/${pet.id}.webp`,
                species: pet.species,            // "Dog" | "Cat"
                size: "large",                   // "small" | "medium" | "large"; or pass sizeLabel: pet.shelter_breed
                onDone: (id, { portion }) => { /* award points */ } });
```
…or render `<button class="feed-btn" data-id data-name data-src data-species data-size-label="Mixed Breed (Large)">`; the size is inferred from the shelter's breed label ("Small"/"Medium"/"Large", cats small). A `<span class="pill fed" hidden>` inside the same `.card` is shown once fed. Deep link: `#feed-<pet_id>`.

API: `open(opts)`, `close()`, `isDone(id)`, `reset()`.

## Tuning

- `PORTION` zones and labels at the top of `feed.js`.
- Pour rate 0.22 bowl/s, eat rate 0.09 bowl/s, happiness +5%/s while eating, +4% per pet tap.
- `sizeFromLabel()` maps shelter labels to a size; extend it for breeds you want treated as large/small.
