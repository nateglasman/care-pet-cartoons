/* Fetch: drag the tennis ball back and flick it. It flies with a bit of physics (height,
 * gravity, bounces, perspective), the token gallops after it, grabs it, and trots back to
 * your hand. FETCHES_NEEDED good throws finish the game.
 *
 * Public API (window.FetchGame): open({ id, name, image, onDone }), close(), isDone(id), reset()
 * Elements with class "fetch-btn" and data-id / data-name / data-src are wired automatically.
 */
(function () {
  const KEY = 'played-pets';
  const FETCHES_NEEDED = 5;
  const load = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return new Set(); } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch (e) {} };
  let done = load();

  const el = document.createElement('div');
  el.id = 'fetch'; el.hidden = true;
  el.innerHTML = `
    <div class="fetch-stage" role="dialog" aria-modal="true" aria-labelledby="fetch-title">
      <button class="fetch-close" aria-label="Close">✕</button>
      <h2 class="fetch-title" id="fetch-title">Play fetch with <span></span></h2>
      <div class="fetch-scene">
        <div class="fetch-sun"></div>
        <span class="fetch-tree" style="left:6%">🌳</span><span class="fetch-tree" style="left:30%;font-size:28px">🌲</span><span class="fetch-tree" style="left:62%">🌳</span><span class="fetch-tree" style="left:84%;font-size:26px">🌳</span>
        <svg class="aim" width="100%" height="100%"><line x1="0" y1="0" x2="0" y2="0" style="display:none"/></svg>
        <div class="ball-shadow"></div>
        <div class="fetch-dog"><img alt="" draggable="false"><div class="mouth-ball"></div><div class="bubble"></div></div>
        <div class="ball"></div>
        <div class="fetch-hand"></div>
      </div>
      <div class="fetch-hud"><span>🎾 fetches <strong class="fetch-count">0 / ${FETCHES_NEEDED}</strong></span><span>🏆 best throw <strong class="fetch-best">0 m</strong></span></div>
      <div class="fetch-meter"><i></i></div>
      <p class="fetch-msg">Drag the ball back and let go to throw it.</p>
      <button class="fetch-done">Good game! 🎾</button>
    </div>`;
  document.body.appendChild(el);

  const stage = el.querySelector('.fetch-stage'), scene = el.querySelector('.fetch-scene');
  const ball = el.querySelector('.ball'), shadow = el.querySelector('.ball-shadow'), dog = el.querySelector('.fetch-dog'), dogImg = dog.querySelector('img'), bubble = dog.querySelector('.bubble');
  const aim = el.querySelector('.aim line');
  const countEl = el.querySelector('.fetch-count'), bestEl = el.querySelector('.fetch-best'), meter = el.querySelector('.fetch-meter i'), msg = el.querySelector('.fetch-msg');
  const nameEl = el.querySelector('.fetch-title span');

  // world: x across the scene, y = ground depth (0 far/top .. H near/bottom), h = height above ground
  const G = 1400, HORIZON = .18;
  let Wd = 400, Hd = 380;
  let current = null, onDone = null, raf = null, lastT = 0, finished = false;
  let b = { x: 0, y: 0, h: 0, vx: 0, vy: 0, vh: 0, state: 'hand' };   // hand | drag | flying | ground | carried
  let d = { x: 0, y: 0, state: 'idle', wait: 0 };                      // idle | chase | return
  let fetches = 0, best = 0, drag = null, bubbleTimer = null;

  const hand = () => ({ x: Wd / 2, y: Hd - 26 });
  const scaleAt = (y) => .45 + .55 * Math.max(0, Math.min(1, (y / Hd - HORIZON) / (1 - HORIZON)));
  const say = (t, ms = 1200) => { bubble.textContent = t; bubble.classList.add('show'); clearTimeout(bubbleTimer); bubbleTimer = setTimeout(() => bubble.classList.remove('show'), ms); };
  const metersOf = (dx, dy) => Math.round(Math.hypot(dx, dy * 2.2) / 14);   // playful scale

  function layout() { const r = scene.getBoundingClientRect(); Wd = r.width; Hd = r.height; }
  function open(opts) {
    current = opts.id; onDone = opts.onDone || null; nameEl.textContent = opts.name; dogImg.src = opts.image;
    el.hidden = false; document.body.classList.add('fetch-open'); layout();
    finished = false; fetches = 0; best = 0; drag = null;
    const hp = hand(); b = { x: hp.x, y: hp.y - 14, h: 0, vx: 0, vy: 0, vh: 0, state: 'hand' };
    d = { x: Wd * .25, y: Hd * .78, state: 'idle', wait: 0 };
    stage.classList.remove('finished'); dog.classList.remove('carrying', 'running'); dog.classList.add('wag');
    countEl.textContent = `0 / ${FETCHES_NEEDED}`; bestEl.textContent = '0 m'; meter.style.width = '0%';
    msg.textContent = 'Drag the ball back and let go to throw it.';
    render();
    if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function close() { el.hidden = true; document.body.classList.remove('fetch-open'); if (raf) { cancelAnimationFrame(raf); raf = null; } }

  function render() {
    const sb = scaleAt(b.y);
    ball.style.left = b.x + 'px'; ball.style.top = (b.y - b.h * sb) + 'px'; ball.style.transform = `scale(${sb})`;
    ball.style.zIndex = b.state === 'carried' ? 0 : 5; ball.style.opacity = b.state === 'carried' ? 0 : 1;
    shadow.style.left = b.x + 'px'; shadow.style.top = b.y + 'px'; shadow.style.transform = `scale(${sb * Math.max(.5, 1 - b.h / 260)})`; shadow.style.opacity = b.state === 'carried' ? 0 : .3;
    const sd = scaleAt(d.y);
    dog.style.left = d.x + 'px'; dog.style.top = d.y + 'px'; dog.style.transform = `scale(${sd})`; dog.style.zIndex = d.y > b.y ? 6 : 4;
  }
  function dust(x, y) { const s = document.createElement('span'); s.className = 'dust'; s.style.left = x + 'px'; s.style.top = y + 'px'; s.style.setProperty('--dx', ((Math.random() - .5) * 30) + 'px'); scene.appendChild(s); s.addEventListener('animationend', () => s.remove()); }

  function tick(t) {
    const dt = Math.min(.05, (t - lastT) / 1000 || 0); lastT = t;
    // --- ball ---
    if (b.state === 'flying') {
      b.x += b.vx * dt; b.y += b.vy * dt; b.vh -= G * dt; b.h += b.vh * dt;
      if (b.x < 14) { b.x = 14; b.vx = -b.vx * .6; } if (b.x > Wd - 14) { b.x = Wd - 14; b.vx = -b.vx * .6; }
      if (b.y < Hd * HORIZON + 10) { b.y = Hd * HORIZON + 10; b.vy = -b.vy * .4; }
      if (b.y > Hd - 16) { b.y = Hd - 16; b.vy = -b.vy * .4; }
      if (b.h < 0) { b.h = 0; b.vh = -b.vh * .45; b.vx *= .7; b.vy *= .7; dust(b.x, b.y); if (Math.abs(b.vh) < 60) { b.vh = 0; b.vx *= .5; b.vy *= .5; } }
      if (b.h === 0 && Math.hypot(b.vx, b.vy) < 12) { b.vx = b.vy = 0; b.state = 'ground'; }
    }
    // --- dog ---
    const run = (tx, ty, speed) => { const dx = tx - d.x, dy = ty - d.y, dist = Math.hypot(dx, dy); if (dist < 4) return true; const st = Math.min(dist, speed * dt); d.x += dx / dist * st; d.y += dy / dist * st; if (Math.abs(dx) > 1) dog.classList.toggle('flip', dx < 0); if (Math.random() < .25) dust(d.x, d.y + 20 * scaleAt(d.y)); return false; };
    if (d.state === 'idle') {
      dog.classList.remove('running'); dog.classList.add('wag');
      if (b.state === 'flying' || b.state === 'ground') { d.wait += dt; if (d.wait > .35) { d.state = 'chase'; d.wait = 0; say('mine!'); } }
    } else if (d.state === 'chase') {
      dog.classList.add('running'); dog.classList.remove('wag');
      if (run(b.x, b.y, 260) || (Math.hypot(b.x - d.x, b.y - d.y) < 22 && b.h < 40)) {
        if (b.state === 'flying' && b.h > 40) { /* still in the air above us: wait */ }
        else { b.state = 'carried'; dog.classList.add('carrying'); d.state = 'return'; say(['got it!', 'woof!', 'mine mine mine'][fetches % 3]); }
      }
    } else if (d.state === 'return') {
      const hp = hand(); b.x = d.x; b.y = d.y; b.h = 0;
      if (run(hp.x - 40, hp.y - 30, 230)) {
        d.state = 'idle'; dog.classList.remove('carrying'); b = { x: hp.x, y: hp.y - 14, h: 0, vx: 0, vy: 0, vh: 0, state: 'hand' };
        fetches++; countEl.textContent = `${Math.min(fetches, FETCHES_NEEDED)} / ${FETCHES_NEEDED}`; meter.style.width = (Math.min(fetches, FETCHES_NEEDED) / FETCHES_NEEDED * 100) + '%';
        msg.textContent = fetches >= FETCHES_NEEDED ? '' : ['Again! Again!', 'Nice one. Throw it farther?', 'That tail is going fast.', 'One more?'][fetches % 4];
        if (fetches >= FETCHES_NEEDED) finish();
      }
    }
    render();
    raf = requestAnimationFrame(tick);
  }
  function finish() {
    finished = true; stage.classList.add('finished'); meter.style.width = '100%';
    msg.textContent = `${nameEl.textContent} is happily worn out. Best throw: ${best} m 🎾`;
    say('best day ever!', 2500);
    const r = scene.getBoundingClientRect();
    for (let i = 0; i < 14; i++) { const s = document.createElement('span'); s.className = 'fetch-sparkle'; s.textContent = ['✨', '🎾', '💛'][i % 3]; s.style.left = (20 + Math.random() * (r.width - 40)) + 'px'; s.style.top = (20 + Math.random() * (r.height - 60)) + 'px'; s.style.animationDelay = (Math.random() * .8) + 's'; scene.appendChild(s); s.addEventListener('animationend', () => s.remove()); }
    if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
    done.add(current); save(done); paint();
    const stats = { fetches, bestThrowMeters: best };
    if (onDone) { try { onDone(current, stats); } catch (e) { console.error(e); } }
    document.dispatchEvent(new CustomEvent('petcare:done', { detail: { game: 'fetch', id: current, stats } }));
  }

  // ---------- throwing: drag back from the ball (slingshot) or just flick it ----------
  const local = (e) => { const r = scene.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top, t: performance.now() }; };
  scene.addEventListener('pointerdown', (e) => {
    if (finished || b.state !== 'hand') return;
    scene.setPointerCapture(e.pointerId);
    const p = local(e); drag = { start: p, last: p, hist: [p] }; b.state = 'drag'; ball.classList.add('flying');
    aim.style.display = ''; aim.setAttribute('x1', b.x); aim.setAttribute('y1', b.y);
  });
  scene.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const p = local(e); drag.hist.push(p); if (drag.hist.length > 6) drag.hist.shift(); drag.last = p;
    // slingshot preview: the ball follows the finger a little, the aim line shows the launch direction
    const pullx = p.x - drag.start.x, pully = p.y - drag.start.y;
    b.x = hand().x + pullx * .35; b.y = hand().y - 14 + Math.max(0, pully) * .35;
    aim.setAttribute('x1', b.x); aim.setAttribute('y1', b.y); aim.setAttribute('x2', b.x - pullx * 1.2); aim.setAttribute('y2', b.y - pully * 1.2);
  });
  const release = (e) => {
    if (!drag) return;
    const p = local(e), first = drag.hist[0];
    const dtm = Math.max(16, p.t - first.t) / 1000;
    const fx = (p.x - first.x) / dtm, fy = (p.y - first.y) / dtm;           // flick velocity
    const sx = drag.start.x - p.x, sy = drag.start.y - p.y;                   // slingshot pull
    let vx, vy;
    if (Math.hypot(fx, fy) > 350 && fy < 0) { vx = fx * .9; vy = fy * .6; }   // fast upward flick: throw in that direction
    else { vx = sx * 4.5; vy = sy * 3.2; }                                     // otherwise slingshot
    const power = Math.hypot(vx, vy);
    aim.style.display = 'none'; ball.classList.remove('flying'); drag = null;
    if (power < 90 || vy > -40) { const hp = hand(); b = { x: hp.x, y: hp.y - 14, h: 0, vx: 0, vy: 0, vh: 0, state: 'hand' }; msg.textContent = 'Pull the ball toward you, then let go to throw it up the field.'; return; }
    b.vx = Math.max(-900, Math.min(900, vx)); b.vy = Math.max(-620, Math.min(-40, vy)); b.vh = Math.min(620, 160 + power * .45); b.h = 2; b.state = 'flying';
    const est = metersOf(b.vx * .9, b.vy * .9); if (est > best) { best = est; bestEl.textContent = best + ' m'; }
    msg.textContent = est > 22 ? 'Huge throw!' : est > 12 ? 'Nice throw!' : 'Short toss. Pull farther for a bigger throw.';
  };
  scene.addEventListener('pointerup', release); scene.addEventListener('pointercancel', release);
  window.addEventListener('resize', () => { if (!el.hidden) layout(); });
  el.querySelector('.fetch-close').addEventListener('click', close);
  el.querySelector('.fetch-done').addEventListener('click', close);
  el.addEventListener('click', (e) => { if (e.target === el) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.hidden) close(); });

  function paint() {
    document.querySelectorAll('.fetch-btn').forEach(bt => {
      const was = done.has(bt.dataset.id);
      bt.textContent = was ? '🎾 Play again' : '🎾 Play fetch';
      const pill = bt.closest('.card')?.querySelector('.pill.played'); if (pill) pill.hidden = !was;
    });
  }
  document.querySelectorAll('.fetch-btn').forEach(bt => bt.addEventListener('click', () => open({ id: bt.dataset.id, name: bt.dataset.name, image: bt.dataset.src })));
  paint();
  const m = location.hash.match(/^#fetch-(.+)$/);
  if (m) { const bt = document.querySelector(`.fetch-btn[data-id="${CSS.escape(m[1])}"]`); if (bt) bt.click(); }

  window.FetchGame = { open, close, isDone: (id) => done.has(id), reset: () => { done = new Set(); save(done); paint(); } };
})();
