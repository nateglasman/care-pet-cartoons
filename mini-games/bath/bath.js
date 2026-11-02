/* Bath mini-game: scrub the pet for NEED seconds of real scrubbing.
 *
 * Public API (window.BathGame):
 *   BathGame.open({ id, name, image, onDone })   open the tub with this pet's cartoon
 *   BathGame.close()
 *   BathGame.isBathed(id)                        true if this browser has bathed the pet
 *   BathGame.reset()                             forget all baths in this browser
 *   BathGame.NEED                                seconds of scrubbing required (default 25)
 *
 * Any element with class "bath-btn" and data-id / data-name / data-src is wired automatically.
 * "Bathed" state is remembered in localStorage only; nothing is sent anywhere.
 */
(function () {
  const NEED = Number(document.currentScript?.dataset?.seconds) || 25;   // <script src="bath.js" data-seconds="10"> to override
  const KEY = 'bathed-pets';
  const load = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return new Set(); } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch (e) {} };
  let bathed = load();

  const BRUSH_SVG = `<svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
    <rect x="10" y="30" width="44" height="18" rx="7" fill="#f2c14e" stroke="#b8862b" stroke-width="2"/>
    <rect x="22" y="12" width="14" height="22" rx="6" fill="#e4572e"/>
    <g fill="#fff8e1">${Array.from({ length: 8 }, (_, i) => `<rect x="${13 + i * 5}" y="46" width="3" height="10" rx="1.5"/>`).join('')}</g>
  </svg>`;

  // ---------- overlay (built once) ----------
  const el = document.createElement('div');
  el.id = 'bath'; el.hidden = true;
  el.innerHTML = `
    <div class="bath-stage" role="dialog" aria-modal="true" aria-labelledby="bath-title">
      <button class="bath-close" aria-label="Close">✕</button>
      <h2 class="bath-title" id="bath-title">Bath time for <span></span></h2>
      <div class="bath-scene">
        <div class="steam"><i></i><i></i><i></i></div>
        <div class="faucet"></div>
        <div class="tub">
          <div class="tub-back"></div>
          <img class="bath-pet" alt="" draggable="false">
          <div class="dirt"></div>
          <div class="water"><div class="wave"></div></div>
          <div class="tub-front"><div class="foam"></div></div>
          <div class="feet"></div>
        </div>
        <div class="bubbles"></div>
        <div class="brush">${BRUSH_SVG}</div>
      </div>
      <div class="bath-meter"><i></i></div>
      <p class="bath-msg"><span class="bath-hint">Press and scrub with your finger or mouse</span><strong class="bath-time">0 / ${NEED}s</strong></p>
      <button class="bath-done">Done, all clean! 🫧</button>
    </div>`;
  document.body.appendChild(el);

  const stage = el.querySelector('.bath-stage'), scene = el.querySelector('.bath-scene');
  const pet = el.querySelector('.bath-pet'), dirt = el.querySelector('.dirt'), foam = el.querySelector('.foam');
  const bubbles = el.querySelector('.bubbles'), brush = el.querySelector('.brush');
  const meter = el.querySelector('.bath-meter i'), hint = el.querySelector('.bath-hint'), time = el.querySelector('.bath-time');
  const nameEl = el.querySelector('.bath-title span');

  let current = null, onDone = null, progress = 0, down = false, lastMove = 0, lastBubble = 0, raf = null, lastT = 0, px = 0, py = 0, done = false;

  function open(opts) {
    const { id, name, image, onDone: cb } = opts;
    const src = image;
    current = id; onDone = cb || null; progress = 0; done = false; down = false;
    nameEl.textContent = name; pet.src = src;
    stage.classList.remove('clean'); scene.classList.remove('scrubbing', 'pointer-in');
    bubbles.innerHTML = ''; meter.style.width = '0%'; foam.style.opacity = 0;
    hint.textContent = 'Press and scrub with your finger or mouse'; time.textContent = `0 / ${NEED}s`;
    dirt.replaceChildren(...Array.from({ length: 7 }, () => {
      const i = document.createElement('i');
      i.style.left = (25 + Math.random() * 50) + '%'; i.style.top = (25 + Math.random() * 50) + '%';
      i.style.transform = `rotate(${Math.random() * 180}deg) scale(${.8 + Math.random() * .7})`;
      return i;
    }));
    dirt.style.opacity = 1;
    el.hidden = false; document.body.classList.add('bath-open');
    if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function close() {
    el.hidden = true; document.body.classList.remove('bath-open');
    if (raf) { cancelAnimationFrame(raf); raf = null; }
  }

  function overPet(x, y) {
    const r = pet.getBoundingClientRect(), pad = 24;
    return x > r.left - pad && x < r.right + pad && y > r.top - pad && y < r.bottom + pad;
  }
  function spawnBubble(x, y) {
    const r = scene.getBoundingClientRect(), b = document.createElement('div');
    const size = 8 + Math.random() * 22;
    b.className = 'bubble';
    b.style.left = (x - r.left - size / 2 + (Math.random() - .5) * 30) + 'px';
    b.style.top = (y - r.top - size / 2 + (Math.random() - .5) * 20) + 'px';
    b.style.width = b.style.height = size + 'px';
    b.style.setProperty('--dx', ((Math.random() - .5) * 80) + 'px');
    b.style.setProperty('--t', (1.2 + Math.random() * 1.2) + 's');
    bubbles.appendChild(b);
    b.addEventListener('animationend', () => b.remove());
  }
  function moveBrush(x, y) {
    const r = scene.getBoundingClientRect();
    brush.style.left = (x - r.left) + 'px'; brush.style.top = (y - r.top) + 'px';
  }
  function tick(t) {
    const dt = Math.min(.05, (t - lastT) / 1000 || 0); lastT = t;
    const active = !done && down && (t - lastMove) < 140 && overPet(px, py);
    scene.classList.toggle('scrubbing', active);
    if (active) {
      progress = Math.min(NEED, progress + dt);
      const f = progress / NEED;
      meter.style.width = (f * 100) + '%';
      time.textContent = `${Math.floor(progress)} / ${NEED}s`;
      dirt.style.opacity = 1 - f;
      foam.style.opacity = Math.min(1, f * 1.6);
      hint.textContent = f < .3 ? 'Scrub, scrub, scrub!' : f < .7 ? 'Getting there… lots of suds!' : 'Almost sparkling!';
      if (progress >= NEED) finish();
    }
    raf = requestAnimationFrame(tick);
  }
  function finish() {
    done = true; down = false;
    stage.classList.add('clean'); scene.classList.remove('scrubbing');
    hint.textContent = `${nameEl.textContent} is squeaky clean!`;
    foam.style.opacity = 0;
    const r = scene.getBoundingClientRect();
    for (let i = 0; i < 14; i++) {
      const s = document.createElement('span'); s.className = 'sparkle'; s.textContent = ['✨', '🫧', '💧'][i % 3];
      s.style.left = (20 + Math.random() * (r.width - 40)) + 'px'; s.style.top = (20 + Math.random() * (r.height - 120)) + 'px';
      s.style.animationDelay = (Math.random() * .8) + 's';
      scene.appendChild(s); s.addEventListener('animationend', () => s.remove());
    }
    if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
    bathed.add(current); save(bathed); paint();
    if (onDone) { try { onDone(current); } catch (e) { console.error(e); } }
    document.dispatchEvent(new CustomEvent('petcare:done', { detail: { game: 'bath', id: current, stats: {} } }));
  }

  // ---------- input ----------
  scene.addEventListener('pointerenter', () => scene.classList.add('pointer-in'));
  scene.addEventListener('pointerleave', () => { scene.classList.remove('pointer-in'); down = false; });
  scene.addEventListener('pointerdown', (e) => { if (done) return; down = true; px = e.clientX; py = e.clientY; lastMove = performance.now(); scene.setPointerCapture(e.pointerId); moveBrush(px, py); scene.classList.add('pointer-in'); });
  scene.addEventListener('pointermove', (e) => {
    px = e.clientX; py = e.clientY; moveBrush(px, py);
    if (!down || done) return;
    const now = performance.now();
    lastMove = now;
    if (overPet(px, py) && now - lastBubble > 45) { lastBubble = now; spawnBubble(px, py); if (Math.random() < .4) spawnBubble(px, py); }
  });
  const up = () => { down = false; };
  scene.addEventListener('pointerup', up); scene.addEventListener('pointercancel', up);
  el.querySelector('.bath-close').addEventListener('click', close);
  el.querySelector('.bath-done').addEventListener('click', close);
  el.addEventListener('click', (e) => { if (e.target === el) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.hidden) close(); });

  // ---------- cards ----------
  function paint() {
    document.querySelectorAll('.bath-btn').forEach(b => {
      const was = bathed.has(b.dataset.id);
      b.textContent = was ? '🫧 Bath again' : '🛁 Give a bath';
      const pill = b.closest('.card').querySelector('.pill.bathed');
      if (pill) pill.hidden = !was;
    });
  }
  document.querySelectorAll('.bath-btn').forEach(b => b.addEventListener('click', () => open({ id: b.dataset.id, name: b.dataset.name, image: b.dataset.src })));
  paint();

  window.BathGame = {
    open, close, NEED,
    isBathed: (id) => bathed.has(id),
    reset: () => { bathed = new Set(); save(bathed); paint(); },
  };
  // deep link for testing / sharing: index.html#bath-CAIL-A-50246
  const m = location.hash.match(/^#bath-(.+)$/);
  if (m) { const b = document.querySelector(`.bath-btn[data-id="${CSS.escape(m[1])}"]`); if (b) b.click(); }
})();
