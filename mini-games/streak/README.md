# Streaks, XP and token tiers

The retention loop for the "take care of a shelter pet" app. Finish all four
care tasks for a pet in one day and that pet is **cared for today**. Do it on
consecutive days and the pet's **token changes finish**: the gold coin gets
shinier, then turns platinum, then holographic, then legendary. Miss a day and
it drops back to gold. Every task and every completed day pays XP, which is
what the leaderboard ranks.

Everything here is plain CSS + JS with no dependencies, and the folder is
self-contained: `demo.html` shows all five tiers side by side and lets you
simulate any streak length on Vera's token (serve this folder with any static
server, e.g. `python3 -m http.server`, and open `demo.html`). `cartoons/`
holds six sample stickers for the demo only; the app uses its own
`/cartoons/{pet_id}.webp`. When the folder sits next to `bath/ walk/ fetch/
feed/` the demo also wires the four games in.

**Use the cartoon from the token.** The tiers are a finish *on the token*, not
new artwork: the same transparent sticker at `/cartoons/{pet_id}.webp` sits on
every tier.

## The tiers

| Tier | Needs | Look | XP multiplier |
|---|---|---|---|
| 🪙 **Gold** | no streak | the token exactly as it is today | ×1 |
| ✨ **Shiny Gold** | 1+ day streak | brighter gold, soft glow, a gloss sweep that passes over the face every ~3 s | ×1.1 |
| 🥈 **Platinum** | 10+ days | white-silver metal, cool glow, faster gloss sweep | ×1.25 |
| 🌈 **Holo** | 30+ days | silver base with a slowly rotating rainbow foil, like a holographic trading card | ×1.5 |
| 👑 **Legendary** | 50+ days | deep gold, rotating rainbow rim ring behind the coin, aurora + twinkling sparkles, pulsing glow | ×2 |

Tier is decided by the pet's **current** streak, so the finish is something
you keep by showing up, not a badge you earn once. `bestTier` is also stored
so the profile can show "reached Holo" after a streak breaks.

## The rules

- **Care day**: bath + walk + fetch + feed for the same pet on the same local
  calendar day (local midnight is the boundary, so no timezone games).
- **Streak**: consecutive care days for that pet. Each pet has its own streak,
  so a user can have a Platinum Vera and a Gold Bruno.
- **Breaking**: if yesterday was not a care day, the streak is 0 and the token
  is Gold again, unless a freeze covers it (next bullet).
- **Freezes**: every 7 consecutive days banks one streak freeze (max 2 in the
  bank). A freeze automatically covers a single missed day: care for the pet
  the day after the miss and the streak continues, minus one freeze. Two
  missed days in a row always break the streak.
- **At risk**: a streak is "at risk" from midnight until the day's care is
  done; the chip says "care today to keep it" so the user knows.

## XP

| Event | XP | Notes |
|---|---|---|
| Feed | 10 | |
| Bath | 15 | |
| Fetch | 15 + best throw in metres | from the game's `bestThrowMeters` |
| Walk | 20 + 1 per 100 m walked | from the game's `meters` |
| Care day complete (all four) | 50 | |
| Reach a 10 / 30 / 50-day streak | 100 / 300 / 500 | milestone, paid once per streak |

Every line is multiplied by the **tier multiplier in effect when it is
earned**, rounded. A task repeated on the same day pays nothing. Example day
on a 12-day (Platinum) streak with a 600 m walk and a 20 m throw:
feed 13 + bath 19 + fetch 44 + walk 33 + day 63 = **172 XP**.

The leaderboard ranks users by total XP. Reasonable extras: a "longest active
streak" board, and a per-pet board ("who has cared for Bruno the most days").
Milestone XP makes the 10 / 30 / 50 marks feel like events; the multiplier
makes a long streak worth protecting without making new users hopeless.

## Files

| File | What |
|---|---|
| `streak.css` | the five tier finishes (`streak-gold`, `streak-shiny`, `streak-platinum`, `streak-holo`, `streak-legendary`), the streak chip, the toast, the level-up flash |
| `streak.js` | the rules above: streak/freeze/XP bookkeeping, tier lookup, DOM helpers, leaderboard summary, QA helpers |
| `demo.html` | gallery of the five tiers + an interactive Vera with a streak slider (and the four games when they sit next to this folder) |
| `cartoons/` | six sample stickers for the demo |

## Integration

1. Include once per page, **after** the four game scripts (it listens for
   their completion events):

   ```html
   <link rel="stylesheet" href="/static/streak.css">
   <script src="/static/streak.js"></script>
   ```

2. Mark each token with the pet id. The styles target a nested `.face` (the
   Pages coin: `.coin > .face.front / .face.back`). For a single-element token
   add `streak-self` too:

   ```html
   <!-- coin with faces -->
   <div class="coin" data-streak-id="CAIL-A-50367"> <div class="face front"><img …></div> … </div>
   <!-- single element token -->
   <div class="token streak-self" data-streak-id="CAIL-A-50367"><img …></div>
   <!-- the chip under it -->
   <span data-streak-chip="CAIL-A-50367"></span>
   <!-- total XP anywhere -->
   ⭐ <b data-streak-xp>0</b> XP
   ```

   `streak.js` finds `[data-streak-id]` elements on load and keeps their
   `streak-*` class, `data-streak` and `data-tier` attributes current. For
   other selectors call `Streak.bindAll('.coin[data-id]')`.

3. Task completion arrives automatically: each game dispatches
   `petcare:done` (`{ game: 'bath'|'walk'|'fetch'|'feed', id, stats }`) on
   `document` when it is finished, and `streak.js` records it. If you have
   your own task source (e.g. the in-person visit from `visit-verify`), call
   `Streak.complete(petId, task, stats)` yourself.

4. Persist on the server. The module keeps its state in `localStorage`
   (`pet-streaks`), which is fine for the demo but not for a leaderboard.
   On the Replit app, mirror every change to the user's record:

   ```js
   document.addEventListener('streak:change', (e) => {
     const { state, events } = e.detail;           // state: one pet; events: what just happened
     fetch('/api/streak', { method: 'POST', body: JSON.stringify({ state, summary: Streak.summary() }) });
   });
   ```

   `events` entries are `{type:'task'|'day'|'freeze'|'milestone'|'tier', …}`
   so the server can validate and award the same XP (don't trust the client's
   `xp` number for the public leaderboard; recompute from the events with the
   same table).

5. Daily reset of the games. The four games remember "done" per pet forever
   in `localStorage`; a streak needs them playable again each day, so
   `streak.js` calls each game's `reset()` the first time it runs on a new
   calendar day. If you store completions server-side you can drop this.

## API

| Call | Returns |
|---|---|
| `Streak.complete(id, task, stats?)` | records the task for today, awards XP, extends the streak when all four are done; returns `state(id)` |
| `Streak.state(id)` | `{ streak, best, tier, bestTier, careToday, today:{bath,walk,fetch,feed}, remaining, atRisk, frozen, broken, freezes, xp, lastCare, nextTier }` |
| `Streak.tierFor(n)` | `{ key, name, min, mult, emoji }` |
| `Streak.apply(el, id?)` | sets the tier class on an element (id defaults to `data-streak-id` / `data-id`) |
| `Streak.bindAll(selector)` | apply now and after every change |
| `Streak.chip(id)` | HTML for the "🔥 12 days · 🥈 Platinum" chip |
| `Streak.summary()` | `{ xp, careDays, bestStreak, activeStreaks, pets:[{ id, streak, best, tier, bestTier, xp }] }` |
| `Streak.simulate(id, days)` / `Streak.rewind(id, days)` / `Streak.reset()` | QA only |
| `Streak.toast(text)` | the toast used for "day 3 streak! +55 XP" and tier-ups |

Events on `document`: `streak:change` (after every change) and, consumed,
`petcare:done` (from the games).

## Tuning knobs (top of `streak.js`)

`TIERS` (thresholds, multipliers, names), `TASK_XP`, `DAILY_BONUS`,
`MILESTONE_XP`, `FREEZE_EVERY`, `MAX_FREEZES`. Colours and animation speeds
are the `--sk-*` variables at the top of each tier block in `streak.css`.

## Things the real app should decide

- **Per-pet or per-user streak?** This module is per pet, because the finish
  lives on the pet's token. If you also want a user-level "days in a row you
  cared for *any* pet", derive it server-side from the care-day events.
- **What if the pet gets adopted?** Best outcome there is. Suggest freezing
  that pet's tier on the user's profile as a trophy ("you helped Vera get
  home") and letting them pick a new pet without losing XP.
- **Timezone** is the device's. If users travel, a day may be 23 or 25 hours;
  nobody will mind.
