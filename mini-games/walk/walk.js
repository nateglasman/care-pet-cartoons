/* Walk the dog: drag the leash handle around a stylized map of Skokie, IL, starting at
 * C.A.R.E. (4927 Main St). The token trots after your finger. Visit 3 of the 4 spots,
 * then bring the pet home to finish. Distance is shown in approximate meters.
 *
 * Public API (window.WalkGame):
 *   WalkGame.open({ id, name, image, onDone })
 *   WalkGame.close()
 *   WalkGame.isDone(id)      true if this browser has walked the pet
 *   WalkGame.reset()
 * Elements with class "walk-btn" and data-id / data-name / data-src are wired automatically.
 */
(function () {
  const KEY = 'walked-pets';
  const SPOTS_NEEDED = 3;
  const METERS_PER_UNIT = 5;            // map is 400 x 360 units; ~2 km across
  const SPEED = 110;                    // units per second
  const load = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return new Set(); } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch (e) {} };
  let done = load();

  // ---------- the map (stylized; real streets and landmarks, approximate placement) ----------
  const W = 400, H = 360;
  const tree = (x, y, s = 1) => `<circle class="map-tree" cx="${x}" cy="${y}" r="${5 * s}"/><rect class="map-tree-trunk" x="${x - 1}" y="${y + 3 * s}" width="2" height="${4 * s}"/>`;
  const bld = (x, y, w, h) => `<rect class="map-bld" x="${x}" y="${y}" width="${w}" height="${h}" rx="1"/><rect class="map-bld roof" x="${x}" y="${y}" width="${w}" height="${Math.min(4, h / 3)}" rx="1"/>`;
  const MAP = `
<svg class="walk-map" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <rect width="${W}" height="${H}" fill="#cfe6b8"/>
  <!-- blocks -->
  ${[[0,0,W,H]].map(() => '').join('')}
  <rect class="map-block" x="0" y="0" width="${W}" height="${H}"/>
  <!-- parks and water -->
  <rect class="map-park" x="40" y="62" width="120" height="96" rx="10"/>
  <rect class="map-park" x="30" y="318" width="110" height="38" rx="10"/>
  <rect class="map-park" x="330" y="0" width="26" height="${H}"/>
  <rect class="map-water" x="356" y="0" width="16" height="${H}"/>
  <rect class="map-park" x="372" y="0" width="28" height="${H}"/>
  <!-- streets (edges then surface) -->
  <g class="map-road-edge"><line x1="0" y1="40" x2="${W}" y2="40"/><line x1="0" y1="180" x2="${W}" y2="180"/><line x1="0" y1="300" x2="${W}" y2="300"/><line x1="250" y1="0" x2="250" y2="${H}"/><line x1="110" y1="0" x2="110" y2="${H}"/><line x1="190" y1="180" x2="190" y2="${H}"/><line x1="222" y1="300" x2="150" y2="40"/></g>
  <g class="map-road"><line x1="0" y1="40" x2="${W}" y2="40"/><line x1="0" y1="180" x2="${W}" y2="180"/><line x1="0" y1="300" x2="${W}" y2="300"/><line x1="250" y1="0" x2="250" y2="${H}"/><line x1="110" y1="0" x2="110" y2="${H}"/><line x1="222" y1="300" x2="150" y2="40"/></g>
  <g class="map-road-minor"><line x1="190" y1="180" x2="190" y2="${H}"/><line x1="60" y1="180" x2="60" y2="300"/><line x1="300" y1="40" x2="300" y2="300"/><line x1="0" y1="240" x2="110" y2="240"/><line x1="250" y1="110" x2="330" y2="110"/><line x1="250" y1="240" x2="330" y2="240"/></g>
  <g class="map-dash"><line x1="0" y1="180" x2="${W}" y2="180"/><line x1="250" y1="0" x2="250" y2="${H}"/><line x1="0" y1="40" x2="${W}" y2="40"/><line x1="0" y1="300" x2="${W}" y2="300"/></g>
  <!-- Skokie Swift (CTA Yellow Line) -->
  <line class="map-rail" x1="268" y1="0" x2="268" y2="${H}"/>
  <rect x="262" y="34" width="12" height="12" rx="2" fill="#f6d33c" stroke="#7b7b8a" stroke-width=".8"/>
  <rect x="262" y="294" width="12" height="12" rx="2" fill="#f6d33c" stroke="#7b7b8a" stroke-width=".8"/>
  <!-- buildings -->
  ${bld(170, 282, 14, 12)}${bld(196, 282, 16, 12)}${bld(216, 284, 12, 10)}${bld(170, 306, 16, 12)}${bld(198, 306, 14, 12)}
  ${bld(280, 150, 14, 14)}${bld(300, 150, 16, 14)}${bld(280, 196, 18, 12)}${bld(300, 196, 12, 12)}
  ${bld(20, 196, 14, 12)}${bld(70, 196, 16, 12)}${bld(130, 196, 14, 12)}${bld(20, 150, 14, 12)}${bld(130, 150, 14, 12)}
  ${bld(20, 56, 14, 12)}${bld(176, 56, 14, 12)}${bld(206, 56, 14, 12)}${bld(300, 56, 16, 12)}
  ${bld(160, 310, 22, 14)}
  <!-- trees -->
  ${tree(60, 90)}${tree(90, 120, 1.2)}${tree(130, 80)}${tree(140, 130)}${tree(70, 140)}${tree(50, 335)}${tree(90, 340, 1.2)}${tree(130, 332)}
  ${tree(343, 60)}${tree(343, 150, 1.2)}${tree(343, 230)}${tree(343, 320)}${tree(386, 90)}${tree(386, 200, 1.2)}${tree(386, 300)}
  ${tree(30, 230)}${tree(80, 260)}${tree(215, 120)}${tree(330, 190)}
  <!-- the shelter: C.A.R.E., 4927 Main St -->
  <rect class="map-shelter" x="210" y="152" width="30" height="22" rx="3"/>
  <polygon points="208,153 225,142 242,153" fill="#e4572e"/>
  <text class="map-poi" x="225" y="166" text-anchor="middle" font-size="9">🐾</text>
  <!-- hydrants -->
  <rect class="map-hydrant" x="115" y="186" width="4" height="7" rx="1.5"/><rect class="map-hydrant" x="114" y="185" width="6" height="2" rx="1"/>
  <rect class="map-hydrant" x="296" y="306" width="4" height="7" rx="1.5"/><rect class="map-hydrant" x="295" y="305" width="6" height="2" rx="1"/>
  <!-- labels -->
  <text class="map-label big" x="8" y="34">DEMPSTER ST</text>
  <text class="map-label big" x="8" y="174">MAIN ST</text>
  <text class="map-label big" x="8" y="294">OAKTON ST</text>
  <text class="map-label" transform="translate(254,70) rotate(90)">SKOKIE BLVD</text>
  <text class="map-label" transform="translate(114,250) rotate(90)">LARAMIE AVE</text>
  <text class="map-label" transform="translate(194,215) rotate(90)">LINCOLN AVE</text>
  <text class="map-label" transform="translate(196,110) rotate(-68)">NILES CENTER RD</text>
  <text class="map-label" transform="translate(366,250) rotate(90)">N. SHORE CHANNEL</text>
  <text class="map-label" transform="translate(273,180) rotate(90)">SKOKIE SWIFT</text>
  <text class="map-poi" x="100" y="78" text-anchor="middle">Laramie Park</text>
  <text class="map-poi" x="85" y="332" text-anchor="middle">Oakton Park</text>
  <text class="map-poi" x="200" y="278" text-anchor="middle">Downtown Skokie</text>
  <text class="map-poi" x="268" y="30" text-anchor="middle">Dempster</text>
  <text class="map-poi" x="268" y="316" text-anchor="middle">Oakton</text>
  <text class="map-poi" x="225" y="139" text-anchor="middle">C.A.R.E.</text>
</svg>`;

  const HOME = { x: 225, y: 184 };
  const SPOTS = [
    { x: 100, y: 110, icon: '🌳', label: 'Laramie Park' },
    { x: 171, y: 318, icon: '📚', label: 'Skokie Library' },
    { x: 343, y: 110, icon: '🗿', label: 'Sculpture Park' },
    { x: 296, y: 320, icon: '🧯', label: 'Hydrant sniff' },
  ];
  const HYDRANTS = [{ x: 117, y: 190 }, { x: 298, y: 310 }];

  // ---------- overlay ----------
  const el = document.createElement('div');
  el.id = 'walk'; el.hidden = true;
  el.innerHTML = `
    <div class="walk-stage" role="dialog" aria-modal="true" aria-labelledby="walk-title">
      <button class="walk-close" aria-label="Close">✕</button>
      <h2 class="walk-title" id="walk-title">Walk <span></span> around Skokie</h2>
      <div class="walk-scene">
        ${MAP}
        <div class="walk-layer walk-markers"></div>
        <div class="walk-layer walk-paws"></div>
        <div class="walk-layer"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice"><path class="leash" d=""/></svg></div>
        <div class="walk-dog"><img alt="" draggable="false"><div class="bubble"></div></div>
        <div class="leash-handle"></div>
      </div>
      <div class="walk-hud"><span>🚶 <strong class="walk-dist">0 m</strong></span><span>📍 spots <strong class="walk-spots">0 / ${SPOTS_NEEDED}</strong></span></div>
      <div class="walk-meter"><i></i></div>
      <p class="walk-msg">Press and drag to hold the leash. Visit ${SPOTS_NEEDED} spots, then come back to C.A.R.E.</p>
      <button class="walk-done">Good walk! 🐾</button>
    </div>`;
  document.body.appendChild(el);

  const stage = el.querySelector('.walk-stage'), scene = el.querySelector('.walk-scene');
  const markers = el.querySelector('.walk-markers'), paws = el.querySelector('.walk-paws');
  const leash = el.querySelector('.leash'), dog = el.querySelector('.walk-dog'), dogImg = dog.querySelector('img'), bubble = dog.querySelector('.bubble');
  const handle = el.querySelector('.leash-handle');
  const distEl = el.querySelector('.walk-dist'), spotsEl = el.querySelector('.walk-spots'), meter = el.querySelector('.walk-meter i'), msg = el.querySelector('.walk-msg');
  const nameEl = el.querySelector('.walk-title span');

  // markers (percent positions so they scale with the scene)
  const pct = (p) => `left:${p.x / W * 100}%;top:${p.y / H * 100}%`;
  let spotEls = [], homeEl = null;
  function buildMarkers() {
    markers.innerHTML = '';
    spotEls = SPOTS.map(s => { const d = document.createElement('div'); d.className = 'wp'; d.style.cssText = pct(s); d.innerHTML = `<span>${s.icon}</span><div class="wp-label">${s.label}</div>`; markers.appendChild(d); return d; });
    homeEl = document.createElement('div'); homeEl.className = 'wp home'; homeEl.style.cssText = pct(HOME); homeEl.innerHTML = '<span>🏠</span><div class="wp-label">C.A.R.E.</div>'; markers.appendChild(homeEl);
  }

  // ---------- state ----------
  let current = null, onDone = null, pos = { ...HOME }, target = null, holding = false, dist = 0, visited = new Set(), finished = false;
  let raf = null, lastT = 0, pawAcc = 0, stillFor = 0, sniffed = new Set(), bubbleTimer = null;

  const toMap = (clientX, clientY) => {
    const r = scene.getBoundingClientRect();
    // slice-fit: scale is max of the two, centered
    const scale = Math.max(r.width / W, r.height / H);
    const ox = (r.width - W * scale) / 2, oy = (r.height - H * scale) / 2;
    return { x: Math.max(4, Math.min(W - 4, (clientX - r.left - ox) / scale)), y: Math.max(4, Math.min(H - 4, (clientY - r.top - oy) / scale)) };
  };
  const place = (node, p) => { node.style.left = (p.x / W * 100) + '%'; node.style.top = (p.y / H * 100) + '%'; };
  const say = (text, ms = 1400) => { bubble.textContent = text; bubble.classList.add('show'); clearTimeout(bubbleTimer); bubbleTimer = setTimeout(() => bubble.classList.remove('show'), ms); };

  function open(opts) {
    current = opts.id; onDone = opts.onDone || null;
    nameEl.textContent = opts.name; dogImg.src = opts.image;
    pos = { ...HOME }; target = null; holding = false; dist = 0; visited = new Set(); sniffed = new Set(); finished = false; pawAcc = 0; stillFor = 0;
    buildMarkers(); paws.innerHTML = ''; place(dog, pos); leash.setAttribute('d', '');
    stage.classList.remove('finished'); scene.classList.remove('walking'); dog.classList.remove('moving');
    distEl.textContent = '0 m'; spotsEl.textContent = `0 / ${SPOTS_NEEDED}`; meter.style.width = '0%';
    msg.textContent = `Press and drag to hold the leash. Visit ${SPOTS_NEEDED} spots, then come back to C.A.R.E.`;
    el.hidden = false; document.body.classList.add('walk-open');
    if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function close() { el.hidden = true; document.body.classList.remove('walk-open'); if (raf) { cancelAnimationFrame(raf); raf = null; } }

  function tick(t) {
    const dt = Math.min(.05, (t - lastT) / 1000 || 0); lastT = t;
    let moving = false;
    if (holding && target && !finished) {
      const dx = target.x - pos.x, dy = target.y - pos.y, d = Math.hypot(dx, dy);
      if (d > 14) {
        const step = Math.min(d - 12, SPEED * dt * (d > 90 ? 1.35 : 1));   // leash tight -> trot faster
        pos.x += dx / d * step; pos.y += dy / d * step; dist += step; pawAcc += step; moving = true;
        if (Math.abs(dx) > 2) dog.classList.toggle('flip', dx < 0);
        if (pawAcc > 16) { pawAcc = 0; const p = document.createElement('span'); p.className = 'paw'; p.textContent = '🐾'; p.style.cssText = pct(pos) + `;transform:rotate(${Math.atan2(dy, dx) * 180 / Math.PI + 90}deg)`; paws.appendChild(p); p.addEventListener('animationend', () => p.remove()); if (paws.childElementCount > 60) paws.firstElementChild.remove(); }
        checkSpots();
      }
      leash.setAttribute('d', `M${pos.x},${pos.y} Q${(pos.x + target.x) / 2},${(pos.y + target.y) / 2 + 10} ${target.x},${target.y}`);
      leash.classList.toggle('tight', d > 90);
    }
    dog.classList.toggle('moving', moving);
    place(dog, pos);
    // sniffing: stand still next to a hydrant
    stillFor = moving ? 0 : stillFor + dt;
    if (!finished && stillFor > .6) HYDRANTS.forEach((h, i) => { if (!sniffed.has(i) && Math.hypot(h.x - pos.x, h.y - pos.y) < 22) { sniffed.add(i); say('sniff sniff… 👃', 1600); } });
    distEl.textContent = Math.round(dist * METERS_PER_UNIT) + ' m';
    raf = requestAnimationFrame(tick);
  }
  function checkSpots() {
    SPOTS.forEach((s, i) => {
      if (!visited.has(i) && Math.hypot(s.x - pos.x, s.y - pos.y) < 20) {
        visited.add(i); spotEls[i].classList.add('visited');
        say(['woof!', 'yip!', 'this is the spot!', 'so many smells'][i % 4]);
        spotsEl.textContent = `${Math.min(visited.size, SPOTS_NEEDED)} / ${SPOTS_NEEDED}`;
        meter.style.width = (Math.min(visited.size, SPOTS_NEEDED) / (SPOTS_NEEDED + 1) * 100) + '%';
        if (visited.size >= SPOTS_NEEDED) { homeEl.classList.add('ready'); msg.textContent = `Great! Now bring ${nameEl.textContent} back home to C.A.R.E. 🏠`; }
        else msg.textContent = `${SPOTS_NEEDED - visited.size} more spot${SPOTS_NEEDED - visited.size === 1 ? '' : 's'} to go.`;
      }
    });
    if (visited.size >= SPOTS_NEEDED && Math.hypot(HOME.x - pos.x, HOME.y - pos.y) < 22) finish();
  }
  function finish() {
    finished = true; holding = false; scene.classList.remove('walking'); leash.setAttribute('d', '');
    stage.classList.add('finished'); meter.style.width = '100%';
    msg.textContent = `${nameEl.textContent} walked ${Math.round(dist * METERS_PER_UNIT)} m and is happily tired. 🐾`;
    say('best walk ever!', 2500);
    const r = scene.getBoundingClientRect();
    for (let i = 0; i < 14; i++) { const s = document.createElement('span'); s.className = 'walk-sparkle'; s.textContent = ['✨', '🐾', '💚'][i % 3]; s.style.left = (20 + Math.random() * (r.width - 40)) + 'px'; s.style.top = (20 + Math.random() * (r.height - 60)) + 'px'; s.style.animationDelay = (Math.random() * .8) + 's'; scene.appendChild(s); s.addEventListener('animationend', () => s.remove()); }
    if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
    done.add(current); save(done); paint();
    const stats = { meters: Math.round(dist * METERS_PER_UNIT), spots: visited.size };
    if (onDone) { try { onDone(current, stats); } catch (e) { console.error(e); } }
    document.dispatchEvent(new CustomEvent('petcare:done', { detail: { game: 'walk', id: current, stats } }));
  }

  // ---------- input ----------
  scene.addEventListener('pointerdown', (e) => { if (finished) return; holding = true; scene.setPointerCapture(e.pointerId); target = toMap(e.clientX, e.clientY); place(handle, target); scene.classList.add('walking'); });
  scene.addEventListener('pointermove', (e) => { if (!holding) return; target = toMap(e.clientX, e.clientY); place(handle, target); });
  const release = () => { holding = false; scene.classList.remove('walking'); leash.setAttribute('d', ''); };
  scene.addEventListener('pointerup', release); scene.addEventListener('pointercancel', release);
  el.querySelector('.walk-close').addEventListener('click', close);
  el.querySelector('.walk-done').addEventListener('click', close);
  el.addEventListener('click', (e) => { if (e.target === el) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.hidden) close(); });

  // ---------- cards ----------
  function paint() {
    document.querySelectorAll('.walk-btn').forEach(b => {
      const was = done.has(b.dataset.id);
      b.textContent = was ? '🐾 Walk again' : '🦮 Walk';
      const pill = b.closest('.card')?.querySelector('.pill.walked'); if (pill) pill.hidden = !was;
    });
  }
  document.querySelectorAll('.walk-btn').forEach(b => b.addEventListener('click', () => open({ id: b.dataset.id, name: b.dataset.name, image: b.dataset.src })));
  paint();
  const m = location.hash.match(/^#walk-(.+)$/);
  if (m) { const b = document.querySelector(`.walk-btn[data-id="${CSS.escape(m[1])}"]`); if (b) b.click(); }

  window.WalkGame = { open, close, isDone: (id) => done.has(id), reset: () => { done = new Set(); save(done); paint(); } };
})();
