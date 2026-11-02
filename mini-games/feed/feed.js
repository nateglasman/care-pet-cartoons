/* Feed: drag the scoop from the kibble bag to the bowl and hold to pour. Fill the bowl into
 * the green zone for this pet's size (too much turns the gauge red; tap the bowl to tip some
 * back). Press Serve: the token comes down, crunches through the bowl, and you can tap it
 * while it eats for hearts. Finishes when the bowl is empty.
 *
 * Public API (window.FeedGame):
 *   FeedGame.open({ id, name, image, size, species, onDone })
 *     size: "small" | "medium" | "large"  (defaults from the shelter breed label when wired via .feed-btn)
 *   FeedGame.close(), FeedGame.isDone(id), FeedGame.reset()
 * Elements with class "feed-btn" and data-id / data-name / data-src (+ optional data-size, data-species) are wired automatically.
 */
(function () {
  const KEY = 'fed-pets';
  const PORTION = { small: [.30, .42, '½ cup'], medium: [.48, .62, '1 cup'], large: [.68, .84, '2 cups'] };   // [zone low, zone high, label] as a fraction of the bowl
  const load = () => { try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { return new Set(); } };
  const save = (s) => { try { localStorage.setItem(KEY, JSON.stringify([...s])); } catch (e) {} };
  let done = load();

  const el = document.createElement('div');
  el.id = 'feed'; el.hidden = true;
  el.innerHTML = `
    <div class="feed-stage" role="dialog" aria-modal="true" aria-labelledby="feed-title">
      <button class="feed-close" aria-label="Close">✕</button>
      <h2 class="feed-title" id="feed-title">Dinner time for <span></span></h2>
      <div class="feed-scene">
        <div class="feed-dog waiting"><img alt="" draggable="false"><div class="bubble"></div></div>
        <div class="feed-mat"></div>
        <div class="bowl"><div class="bowl-back"></div><div class="bowl-fill"><i></i></div><div class="bowl-heap"></div><div class="bowl-front"></div><div class="bowl-name"></div></div>
        <div class="bag"></div>
        <div class="gauge"><div class="zone"></div><div class="level"></div><div class="tag"></div></div>
        <div class="scoop empty"><div class="cup"></div><div class="handle"></div></div>
        <button class="serve">Serve 🍽️</button>
      </div>
      <div class="feed-hud"><span>🥣 bowl <strong class="feed-fill">0%</strong></span><span>😊 happy <strong class="feed-happy">0%</strong></span></div>
      <div class="feed-meter"><i></i></div>
      <p class="feed-msg">Drag the scoop from the bag to the bowl and hold to pour.</p>
      <button class="feed-done">Yum! 🐾</button>
    </div>`;
  document.body.appendChild(el);

  const stage = el.querySelector('.feed-stage'), scene = el.querySelector('.feed-scene');
  const dog = el.querySelector('.feed-dog'), dogImg = dog.querySelector('img'), bubble = dog.querySelector('.bubble');
  const bowl = el.querySelector('.bowl'), fillEl = el.querySelector('.bowl-fill i'), heap = el.querySelector('.bowl-heap'), bowlName = el.querySelector('.bowl-name');
  const bag = el.querySelector('.bag'), scoop = el.querySelector('.scoop'), gauge = el.querySelector('.gauge'), zone = gauge.querySelector('.zone'), level = gauge.querySelector('.level'), tag = gauge.querySelector('.tag');
  const serve = el.querySelector('.serve'), fillHud = el.querySelector('.feed-fill'), happyHud = el.querySelector('.feed-happy'), meter = el.querySelector('.feed-meter i'), msg = el.querySelector('.feed-msg');
  const nameEl = el.querySelector('.feed-title span');

  let current = null, onDone = null, zoneLo = .48, zoneHi = .62, fill = 0, happy = 0, phase = 'scoop';   // scoop | eating | finished
  let holding = false, scoopHasFood = false, overBowl = false, raf = null, lastT = 0, kibAcc = 0, bubbleTimer = null, eatTimer = 0;
  const say = (t, ms = 1200) => { bubble.textContent = t; bubble.classList.add('show'); clearTimeout(bubbleTimer); bubbleTimer = setTimeout(() => bubble.classList.remove('show'), ms); };

  function sizeFromLabel(label = '', species = 'Dog') {
    const l = label.toLowerCase();
    if (species === 'Cat') return 'small';
    if (l.includes('small') || l.includes('chihuahua') || l.includes('terrier')) return 'small';
    if (l.includes('large') || l.includes('husky') || l.includes('shepherd') || l.includes('retriever')) return 'large';
    return 'medium';
  }
  function setFill(v) {
    fill = Math.max(0, Math.min(1, v));
    fillEl.style.height = (Math.min(fill, .7) / .7 * 100) + '%';
    heap.style.transform = `scaleY(${Math.max(0, (fill - .6) / .4)})`;
    level.style.height = (fill * 190) + 'px';
    const over = fill > zoneHi + .02; gauge.classList.toggle('over', over);
    const inZone = fill >= zoneLo && fill <= zoneHi + .02;
    scene.classList.toggle('ready', phase === 'scoop' && inZone);
    fillHud.textContent = Math.round(fill * 100) + '%';
    meter.style.width = (phase === 'scoop' ? Math.min(1, fill / zoneLo) * 40 : 40 + happy * 60) + '%';
    if (phase === 'scoop') msg.textContent = over ? `Too much for a ${sizeName}! Tap the bowl to tip some back.` : inZone ? 'Perfect portion. Serve it up!' : fill > 0 ? 'Keep pouring to the green zone.' : 'Drag the scoop from the bag to the bowl and hold to pour.';
  }
  let sizeName = 'medium';

  function open(opts) {
    current = opts.id; onDone = opts.onDone || null; nameEl.textContent = opts.name; dogImg.src = opts.image; bowlName.textContent = opts.name.split('(')[0].trim().toUpperCase();
    sizeName = opts.size || sizeFromLabel(opts.sizeLabel, opts.species);
    [zoneLo, zoneHi] = PORTION[sizeName] || PORTION.medium;
    bag.classList.toggle('cat', opts.species === 'Cat');
    zone.style.bottom = (5 + zoneLo * 190) + 'px'; zone.style.height = ((zoneHi - zoneLo) * 190) + 'px';
    tag.textContent = `${PORTION[sizeName][2]} for a ${sizeName} ${opts.species === 'Cat' ? 'cat' : 'dog'}`; tag.style.bottom = (5 + (zoneLo + zoneHi) / 2 * 190) + 'px'; tag.style.transform = 'translateY(50%)';
    phase = 'scoop'; happy = 0; holding = false; scoopHasFood = false; overBowl = false; eatTimer = 0;
    dog.className = 'feed-dog waiting'; stage.classList.remove('finished'); scene.classList.remove('scooping', 'ready'); scoop.classList.add('empty'); scoop.classList.remove('pouring');
    happyHud.textContent = '0%'; setFill(0);
    el.hidden = false; document.body.classList.add('feed-open');
    if (!raf) { lastT = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function close() { el.hidden = true; document.body.classList.remove('feed-open'); if (raf) { cancelAnimationFrame(raf); raf = null; } }

  const local = (e) => { const r = scene.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const inside = (node, e) => { const r = node.getBoundingClientRect(); return e.clientX >= r.left - 10 && e.clientX <= r.right + 10 && e.clientY >= r.top - 20 && e.clientY <= r.bottom + 10; };
  function kibble(x, y) { const k = document.createElement('span'); k.className = 'kib'; k.style.left = x + (Math.random() - .5) * 16 + 'px'; k.style.top = y + 'px'; k.style.setProperty('--dx', ((Math.random() - .5) * 24) + 'px'); k.style.setProperty('--dy', (60 + Math.random() * 30) + 'px'); scene.appendChild(k); k.addEventListener('animationend', () => k.remove()); }
  function crumb(text) { const r = bowl.getBoundingClientRect(), s = scene.getBoundingClientRect(); const c = document.createElement('span'); c.className = 'crumb'; c.textContent = text; c.style.left = (r.left - s.left + 20 + Math.random() * (r.width - 40)) + 'px'; c.style.top = (r.top - s.top - 10) + 'px'; c.style.setProperty('--dx', ((Math.random() - .5) * 50) + 'px'); scene.appendChild(c); c.addEventListener('animationend', () => c.remove()); }
  function heart(x, y) { const h = document.createElement('span'); h.className = 'heart'; h.textContent = ['💛', '❤️', '🧡'][Math.floor(Math.random() * 3)]; h.style.left = x + 'px'; h.style.top = y + 'px'; h.style.setProperty('--dx', ((Math.random() - .5) * 60) + 'px'); scene.appendChild(h); h.addEventListener('animationend', () => h.remove()); }

  function tick(t) {
    const dt = Math.min(.05, (t - lastT) / 1000 || 0); lastT = t;
    if (phase === 'scoop' && holding && scoopHasFood && overBowl) {
      scoop.classList.add('pouring');
      setFill(fill + .22 * dt);
      kibAcc += dt; if (kibAcc > .06) { kibAcc = 0; const r = scoop.getBoundingClientRect(), s = scene.getBoundingClientRect(); kibble(r.left - s.left + 6, r.top - s.top + 26); }
      if (fill > .25 && Math.random() < .01) say(['is it ready yet?', 'drool…', 'hurry hurry'][Math.floor(Math.random() * 3)]);
    } else scoop.classList.remove('pouring');
    if (phase === 'eating') {
      eatTimer += dt;
      setFill(fill - .09 * dt);
      if (eatTimer > .35) { eatTimer = 0; crumb(['crunch', 'nom', 'munch', 'crunch'][Math.floor(Math.random() * 4)]); }
      happy = Math.min(1, happy + .05 * dt); happyHud.textContent = Math.round(happy * 100) + '%';
      meter.style.width = (40 + happy * 60) + '%';
      if (fill <= 0.001) finish();
    }
    raf = requestAnimationFrame(tick);
  }
  function finish() {
    phase = 'finished'; happy = 1; happyHud.textContent = '100%'; meter.style.width = '100%';
    dog.className = 'feed-dog full'; stage.classList.add('finished');
    msg.textContent = `${nameEl.textContent} licked the bowl clean. Full belly, happy ${bag.classList.contains('cat') ? 'cat' : 'dog'}. 😊`;
    say('burp. thank you!', 2500);
    const r = scene.getBoundingClientRect();
    for (let i = 0; i < 14; i++) { const s = document.createElement('span'); s.className = 'feed-sparkle'; s.textContent = ['✨', '🦴', '💛'][i % 3]; s.style.left = (20 + Math.random() * (r.width - 40)) + 'px'; s.style.top = (20 + Math.random() * (r.height - 60)) + 'px'; s.style.animationDelay = (Math.random() * .8) + 's'; scene.appendChild(s); s.addEventListener('animationend', () => s.remove()); }
    if (navigator.vibrate) navigator.vibrate([40, 60, 40]);
    done.add(current); save(done); paint();
    const stats = { portion: sizeName };
    if (onDone) { try { onDone(current, stats); } catch (e) { console.error(e); } }
    document.dispatchEvent(new CustomEvent('petcare:done', { detail: { game: 'feed', id: current, stats } }));
  }

  // ---------- input ----------
  scene.addEventListener('pointerdown', (e) => {
    if (phase === 'eating') { const p = local(e); if (inside(dog, e)) { heart(p.x, p.y); happy = Math.min(1, happy + .04); say(['more pets!', 'mmm', '♥'][Math.floor(Math.random() * 3)], 700); } return; }
    if (phase !== 'scoop') return;
    if (inside(bag, e)) { holding = true; scoopHasFood = true; scoop.classList.remove('empty'); scene.classList.add('scooping'); bag.classList.add('active'); scene.setPointerCapture(e.pointerId); const p = local(e); scoop.style.left = p.x + 'px'; scoop.style.top = p.y + 'px'; msg.textContent = 'Now carry it over the bowl and hold to pour.'; }
    else if (inside(bowl, e) && fill > zoneHi + .02) { setFill(fill - .08); crumb('tip'); }
  });
  scene.addEventListener('pointermove', (e) => {
    if (!holding) return;
    const p = local(e); scoop.style.left = p.x + 'px'; scoop.style.top = p.y + 'px';
    overBowl = inside(bowl, e) || (p.y > scene.clientHeight * .45 && Math.abs(p.x - scene.clientWidth / 2) < 90);
  });
  const release = () => { holding = false; overBowl = false; scoopHasFood = false; scoop.classList.add('empty'); scene.classList.remove('scooping'); bag.classList.remove('active'); };
  scene.addEventListener('pointerup', release); scene.addEventListener('pointercancel', release);
  serve.addEventListener('click', () => { if (phase !== 'scoop') return; phase = 'eating'; scene.classList.remove('ready', 'scooping'); dog.className = 'feed-dog eating'; msg.textContent = `Crunch crunch. Tap ${nameEl.textContent} while it eats for extra happiness.`; say('FOOD!', 1500); });
  el.querySelector('.feed-close').addEventListener('click', close);
  el.querySelector('.feed-done').addEventListener('click', close);
  el.addEventListener('click', (e) => { if (e.target === el) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.hidden) close(); });

  function paint() {
    document.querySelectorAll('.feed-btn').forEach(bt => {
      const was = done.has(bt.dataset.id);
      bt.textContent = was ? '🍖 Feed again' : '🥣 Feed';
      const pill = bt.closest('.card')?.querySelector('.pill.fed'); if (pill) pill.hidden = !was;
    });
  }
  document.querySelectorAll('.feed-btn').forEach(bt => bt.addEventListener('click', () => open({ id: bt.dataset.id, name: bt.dataset.name, image: bt.dataset.src, size: bt.dataset.size || undefined, sizeLabel: bt.dataset.sizeLabel, species: bt.dataset.species })));
  paint();
  const m = location.hash.match(/^#feed-(.+)$/);
  if (m) { const bt = document.querySelector(`.feed-btn[data-id="${CSS.escape(m[1])}"]`); if (bt) bt.click(); }

  window.FeedGame = { open, close, isDone: (id) => done.has(id), reset: () => { done = new Set(); save(done); paint(); } };
})();
