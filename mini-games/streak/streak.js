/* Streaks, XP and token tiers for the pet-care app.
 *
 * A pet is "cared for" on a day when all four tasks are done that day
 * (bath, walk, fetch, feed). Consecutive cared-for days build that pet's
 * streak; the streak decides which finish the token gets.
 *
 * Public API (window.Streak):
 *   Streak.complete(id, task, stats)   record a finished task for today; returns state(id)
 *   Streak.state(id)                   { streak, best, tier, careToday, today:{bath,walk,fetch,feed},
 *                                        atRisk, freezes, xp, lastCare }
 *   Streak.tierFor(streak)             tier object for a streak length
 *   Streak.apply(el, id)               put the right streak-* class on a token element
 *   Streak.bindAll(selector)           apply to every matching element now and whenever state changes
 *   Streak.chip(id)                    HTML for the little "🔥 12 days · Platinum" chip
 *   Streak.summary()                   { xp, careDays, bestStreak, pets:[...] } for a leaderboard
 *   Streak.simulate(id, days)          set a pet's streak (demos / QA)
 *   Streak.rewind(id, days)            pretend the last care day was `days` ago (demos / QA)
 *   Streak.reset()                     wipe all streak data in this browser
 *
 * Events: document fires "streak:change" (detail = state) after every change.
 * It also listens for "petcare:done" ({ game, id, stats }) which the four
 * games dispatch on completion, so nothing else is needed to feed it.
 *
 * Storage is localStorage ("pet-streaks"); on the real app persist per user
 * on the server and compute the leaderboard from Streak.summary() instead.
 */
(() => {
  const KEY = 'pet-streaks';
  const TASKS = ['bath', 'walk', 'fetch', 'feed'];

  // ---- tuning ----------------------------------------------------------
  const TIERS = [
    { key: 'gold',      name: 'Gold',        min: 0,  mult: 1.0,  emoji: '🪙' },
    { key: 'shiny',     name: 'Shiny Gold',  min: 1,  mult: 1.1,  emoji: '✨' },
    { key: 'platinum',  name: 'Platinum',    min: 10, mult: 1.25, emoji: '🥈' },
    { key: 'holo',      name: 'Holo',        min: 30, mult: 1.5,  emoji: '🌈' },
    { key: 'legendary', name: 'Legendary',   min: 50, mult: 2.0,  emoji: '👑' },
  ];
  const TASK_XP = { feed: 10, bath: 15, fetch: 15, walk: 20 };
  const DAILY_BONUS = 50;                                  // all four done in one day
  const MILESTONE_XP = { 10: 100, 30: 300, 50: 500 };      // paid once when the streak reaches that day
  const FREEZE_EVERY = 7;                                  // every 7 straight days earns a streak freeze…
  const MAX_FREEZES = 2;                                   // …which auto-covers one missed day (max banked)

  // ---- dates (local calendar days) --------------------------------------
  const dayKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const parse = (k) => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
  const daysBetween = (a, b) => Math.round((parse(b) - parse(a)) / 864e5);
  const shift = (k, n) => { const d = parse(k); d.setDate(d.getDate() + n); return dayKey(d); };

  // ---- storage ----------------------------------------------------------
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; } };
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch (e) {} };
  let db = load();
  const rec = (id) => (db[id] ||= { streak: 0, best: 0, lastCare: null, freezes: 0, xp: 0, days: {}, milestones: [], bestTier: 'gold' });

  // ---- core -------------------------------------------------------------
  const tierFor = (streak) => { let t = TIERS[0]; for (const x of TIERS) if (streak >= x.min) t = x; return t; };
  const tierIndex = (key) => TIERS.findIndex(t => t.key === key);

  // streak as it stands today: a missed day (beyond what a freeze covers) means it's over
  function effective(r, today = dayKey()) {
    if (!r.lastCare) return { streak: 0, atRisk: false, broken: false };
    const gap = daysBetween(r.lastCare, today);
    if (gap <= 1) return { streak: r.streak, atRisk: gap === 1, broken: false };
    if (gap === 2 && r.freezes > 0) return { streak: r.streak, atRisk: true, broken: false, frozen: true };
    return { streak: 0, atRisk: false, broken: true };
  }

  function state(id) {
    const r = rec(id), today = dayKey(), eff = effective(r, today);
    const done = r.days[today] || {};
    const t = {}; TASKS.forEach(k => t[k] = !!done[k]);
    return {
      id, streak: eff.streak, best: r.best, tier: tierFor(eff.streak), bestTier: r.bestTier,
      careToday: r.lastCare === today, today: t, remaining: TASKS.filter(k => !t[k]),
      atRisk: eff.atRisk && r.lastCare !== today, frozen: !!eff.frozen, broken: eff.broken,
      freezes: r.freezes, xp: r.xp, lastCare: r.lastCare,
      nextTier: TIERS.find(x => x.min > eff.streak) || null,
    };
  }

  function complete(id, task, stats = {}) {
    if (!TASKS.includes(task)) throw new Error('unknown task ' + task);
    const r = rec(id), today = dayKey();
    const before = state(id);
    const day = (r.days[today] ||= {});
    const events = [];
    if (!day[task]) {
      day[task] = true;
      let pts = TASK_XP[task] || 0;
      if (task === 'walk' && stats.meters) pts += Math.floor(stats.meters / 100);
      if (task === 'fetch' && stats.bestThrowMeters) pts += Math.floor(stats.bestThrowMeters);
      pts = Math.round(pts * before.tier.mult);
      r.xp += pts; events.push({ type: 'task', task, xp: pts });
    }
    if (TASKS.every(k => day[k]) && r.lastCare !== today) {
      // a full care day → extend (or restart) the streak
      const eff = effective(r, today);
      if (eff.broken) r.streak = 1;
      else { if (eff.frozen) r.freezes -= 1; r.streak += 1; }
      r.lastCare = today; r.best = Math.max(r.best, r.streak);
      const tier = tierFor(r.streak);
      const bonus = Math.round(DAILY_BONUS * tier.mult);
      r.xp += bonus; events.push({ type: 'day', streak: r.streak, xp: bonus, frozen: !!eff.frozen });
      if (r.streak % FREEZE_EVERY === 0 && r.freezes < MAX_FREEZES) { r.freezes += 1; events.push({ type: 'freeze', freezes: r.freezes }); }
      if (MILESTONE_XP[r.streak] && !r.milestones.includes(r.streak)) { r.milestones.push(r.streak); r.xp += MILESTONE_XP[r.streak]; events.push({ type: 'milestone', streak: r.streak, xp: MILESTONE_XP[r.streak] }); }
      if (tierIndex(tier.key) > tierIndex(r.bestTier)) r.bestTier = tier.key;
      if (tier.key !== before.tier.key) events.push({ type: 'tier', tier });
    }
    // keep only the last few days
    Object.keys(r.days).sort().slice(0, -7).forEach(k => delete r.days[k]);
    save();
    const after = state(id);
    announce(after, events);
    return after;
  }

  // ---- presentation -----------------------------------------------------
  const CLASSES = TIERS.map(t => 'streak-' + t.key);
  function apply(el, id) {
    const s = state(id || el.dataset.streakId || el.dataset.id);
    const cls = 'streak-' + s.tier.key;
    if (!el.classList.contains(cls)) {
      const had = CLASSES.some(c => el.classList.contains(c));
      el.classList.remove(...CLASSES); el.classList.add(cls);
      if (had && s.tier.key !== 'gold') { el.classList.remove('streak-levelup'); void el.offsetWidth; el.classList.add('streak-levelup'); }
    }
    el.dataset.streak = s.streak; el.dataset.tier = s.tier.key;
    return s;
  }
  function chip(id) {
    const s = state(id);
    if (!s.streak && !s.atRisk) return `<span class="streak-chip t-gold">${s.tier.emoji} no streak yet</span>`;
    const risk = s.atRisk ? ` <span class="at-risk">${s.frozen ? '· freeze used if you care today' : '· care today to keep it'}</span>` : '';
    return `<span class="streak-chip t-${s.tier.key}">🔥 ${s.streak} day${s.streak === 1 ? '' : 's'} · ${s.tier.emoji} ${s.tier.name}${risk}</span>`;
  }
  const bound = [];
  function paint() {
    bound.forEach(sel => document.querySelectorAll(sel).forEach(el => apply(el)));
    document.querySelectorAll('[data-streak-chip]').forEach(el => { el.innerHTML = chip(el.dataset.streakChip); });
    const xp = document.querySelector('[data-streak-xp]'); if (xp) xp.textContent = summary().xp;
  }
  function bindAll(selector) { if (!bound.includes(selector)) bound.push(selector); paint(); }

  let toastEl = null, toastT = null;
  function toast(msg, cls = '') {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'streak-toast'; document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.className = 'streak-toast show ' + cls;
    clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('show'), 2800);
  }
  function announce(s, events) {
    paint();
    const tierEv = events.find(e => e.type === 'tier'), dayEv = events.find(e => e.type === 'day'), ms = events.find(e => e.type === 'milestone');
    const name = nameOf(s.id);
    if (tierEv) setTimeout(() => toast(`${tierEv.tier.emoji} ${name}'s token is now ${tierEv.tier.name}!`, 'tier'), dayEv ? 1500 : 0);
    if (ms) toast(`🏆 ${s.streak}-day streak! +${ms.xp} XP`, 'tier');
    else if (dayEv) toast(`🔥 ${name} cared for · day ${s.streak} streak · +${dayEv.xp} XP`);
    document.dispatchEvent(new CustomEvent('streak:change', { detail: { state: s, events } }));
  }
  const names = {};
  const nameOf = (id) => names[id] || document.querySelector(`[data-id="${CSS.escape(id)}"][data-name]`)?.dataset.name || 'Your pet';

  function summary() {
    const pets = Object.keys(db).map(state);
    return {
      xp: pets.reduce((a, p) => a + p.xp, 0),
      careDays: Object.values(db).reduce((a, r) => a + r.best, 0),
      bestStreak: pets.reduce((a, p) => Math.max(a, p.best), 0),
      activeStreaks: pets.filter(p => p.streak > 0).length,
      pets: pets.map(p => ({ id: p.id, streak: p.streak, best: p.best, tier: p.tier.key, bestTier: p.bestTier, xp: p.xp })),
    };
  }

  // ---- QA helpers --------------------------------------------------------
  function simulate(id, days) {
    const r = rec(id); days = Math.max(0, days | 0);
    r.streak = days; r.best = Math.max(r.best, days); r.lastCare = days ? dayKey() : null;
    const day = (r.days[dayKey()] = {}); if (days) TASKS.forEach(k => day[k] = true);
    const t = tierFor(days); if (tierIndex(t.key) > tierIndex(r.bestTier)) r.bestTier = t.key;
    save(); paint(); document.dispatchEvent(new CustomEvent('streak:change', { detail: { state: state(id), events: [] } }));
    return state(id);
  }
  function rewind(id, days) {
    const r = rec(id); if (!r.lastCare) return state(id);
    r.lastCare = shift(r.lastCare, -days);
    Object.keys(r.days).forEach(k => { if (k === dayKey()) delete r.days[k]; });
    save(); paint(); return state(id);
  }
  function reset() { db = {}; save(); paint(); document.dispatchEvent(new CustomEvent('streak:change', { detail: { state: null, events: [] } })); }

  // ---- hook the games ---------------------------------------------------
  document.addEventListener('petcare:done', (e) => { const { game, id, stats } = e.detail || {}; if (TASKS.includes(game) && id) complete(id, game, stats || {}); });

  // Games remember "done" forever in this browser; a streak needs them redoable
  // every day, so forget yesterday's completions once the date rolls over.
  function dailyReset() {
    const DKEY = 'pet-streaks-day';
    let last = null; try { last = localStorage.getItem(DKEY); } catch (e) {}
    const today = dayKey();
    if (last !== today) {
      ['BathGame', 'WalkGame', 'FetchGame', 'FeedGame'].forEach(g => { try { window[g] && window[g].reset(); } catch (e) {} });
      try { localStorage.setItem(DKEY, today); } catch (e) {}
    }
  }

  const boot = () => { dailyReset(); bindAll('[data-streak-id]'); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();

  window.Streak = { TIERS, TASKS, TASK_XP, DAILY_BONUS, MILESTONE_XP, complete, state, tierFor, apply, bindAll, chip, summary, simulate, rewind, reset, toast, dayKey };
})();
