// Visual layer for the battle page. It never decides anything: it only animates
// what the server already sent (state / word / event / match_end).
const REDUCED = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const $ = (id) => document.getElementById(id);
const other = (side) => (side === "p1" ? "p2" : "p1");
const NOOP = { sync() {}, attack() {}, event() {}, banner() {}, end() {}, whenIdle: (cb) => cb() };

// Words longer than this send a skeleton soldier; shorter ones fire a bullet.
const SOLDIER_MIN_EXCLUSIVE = 5;
const PROFILE = {
  "fx-skel": { w: 42, speed: 0.26, min: 1000, ground: true }, // low, walking, heavy
  "fx-bullet": { w: 20, ballisticSpeed: 1100, ground: false }, // ballistic cannon shot
  "fx-orb": { w: 34, ballisticSpeed: 700, ground: false }, // ballistic skill orb
};
const GRAVITY = 1600;
const SKELETON = `<svg class="skel" viewBox="0 0 48 40" aria-hidden="true">
  <g class="sk-leg sk-l1"><path d="M22 22 L22 30"/><g class="sk-shin"><path d="M22 30 L22 38 L27 38"/></g></g>
  <g class="sk-leg sk-l2"><path d="M22 22 L22 30"/><g class="sk-shin"><path d="M22 30 L22 38 L27 38"/></g></g>
  <g class="sk-body">
    <g class="sk-arm sk-swing"><path d="M25 12 L25 18 L27 22"/></g>
    <path d="M22 22 L25 11"/><path d="M23.5 18 L27 17 M24.2 15 L27.5 14 M22.8 20.5 L26 20"/>
    <ellipse class="fill" cx="22" cy="22" rx="3.5" ry="2"/>
    <g class="sk-arm sk-hold"><path d="M25 12 L30 15 L36 13"/><path d="M30 17 L46 9"/></g>
    <g class="sk-skull"><circle class="fill" cx="28" cy="6" r="5"/><circle class="eye" cx="30.2" cy="5.2" r="1.4"/>
      <g class="sk-jaw"><path d="M25.5 10 H31"/></g></g>
  </g>
</svg>`;

export function createArenaFx() {
  const stage = $("arena-stage");
  if (!stage) return NOOP;

  const layer = $("arena-units");
  const lane = $("arena-lane");
  const tank = { p1: $("tank-p1"), p2: $("tank-p2") };
  const latest = { p1: null, p2: null }; // newest numbers from the server
  const shown = { p1: null, p2: null }; // numbers currently drawn on the bars
  const incoming = { p1: 0, p2: 0 }; // soldiers still marching toward this tank
  const slam = { p1: false, p2: false }; // next hit on this tank came from a soldier
  let flying = 0; // ground units in the air (drives the dashed lane)
  let airborne = 0; // every unit still travelling (bullets, soldiers, orbs)
  let finished = false;
  let endQueued = false;
  let idleQueue = [];

  const pct = (value, max) => `${Math.max(0, Math.min(100, (value / Math.max(1, max)) * 100))}%`;

  function retrigger(element, cls, ms = 450) {
    element.classList.remove(cls);
    void element.offsetWidth;
    element.classList.add(cls);
    setTimeout(() => element.classList.remove(cls), ms);
  }

  function centerX(side) {
    const t = tank[side];
    return t.offsetLeft + t.offsetWidth / 2;
  }

  function muzzle(side) {
    const t = tank[side];
    const m = t?.querySelector(".tank-muzzle");
    if (!m) return { x: t.offsetLeft + (side === "p1" ? t.offsetWidth : 0), y: t.offsetTop + t.offsetHeight * 0.3 };
    const stageRect = stage.getBoundingClientRect();
    const rect = m.getBoundingClientRect();
    return { x: rect.left - stageRect.left + rect.width / 2, y: rect.top - stageRect.top + rect.height / 2 };
  }

  function muzzleX(side) { return muzzle(side).x; }

  function targetCenter(side) {
    const t = tank[side];
    return { x: centerX(side), y: t.offsetTop + t.offsetHeight * 0.45 };
  }

  function float(side, text, cls) {
    const el = document.createElement("span");
    el.className = `fx-float ${cls}`;
    el.textContent = text;
    el.style.left = `${Math.min(Math.max(centerX(side), 90), layer.clientWidth - 90)}px`;
    layer.appendChild(el);
    setTimeout(() => el.remove(), 1200);
  }

  function spark(side, cls = "") {
    const el = document.createElement("span");
    el.className = `fx-spark ${cls}`;
    el.style.left = `${centerX(side)}px`;
    layer.appendChild(el);
    setTimeout(() => el.remove(), 450);
  }

  function impactFx(side, heavy = false) {
    const { x, y } = targetCenter(side);
    const flash = document.createElement("span");
    flash.className = `fx-impact-flash${heavy ? " fx-impact-big" : ""}`;
    flash.style.left = `${x}px`;
    flash.style.top = `${y}px`;
    layer.appendChild(flash);
    setTimeout(() => flash.remove(), 260);

    const smoke = document.createElement("span");
    smoke.className = `fx-impact-smoke${heavy ? " fx-impact-big" : ""}`;
    smoke.style.left = `${x}px`;
    smoke.style.top = `${y}px`;
    layer.appendChild(smoke);
    setTimeout(() => smoke.remove(), 850);

    const count = heavy ? 10 : 7;
    for (let i = 0; i < count; i += 1) {
      const bit = document.createElement("span");
      bit.className = "fx-impact-spark";
      bit.style.left = `${x}px`;
      bit.style.top = `${y}px`;
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
      const dist = (heavy ? 34 : 24) + Math.random() * (heavy ? 28 : 18);
      bit.style.setProperty("--dx", `${Math.cos(angle) * dist}px`);
      bit.style.setProperty("--dy", `${Math.sin(angle) * dist - 10}px`);
      layer.appendChild(bit);
      setTimeout(() => bit.remove(), 450);
    }
  }

  function bones(side) {
    for (let i = 0; i < 6; i += 1) {
      const bit = document.createElement("span");
      bit.className = "fx-bone";
      bit.style.left = `${centerX(side)}px`;
      bit.style.setProperty("--dx", `${(Math.random() - 0.5) * 90}px`);
      bit.style.setProperty("--dy", `${-20 - Math.random() * 55}px`);
      bit.style.setProperty("--r", `${(Math.random() - 0.5) * 540}deg`);
      layer.appendChild(bit);
      setTimeout(() => bit.remove(), 750);
    }
  }

  // Draw bars from the newest server numbers; show damage if something was lost.
  function paint(side) {
    const now = latest[side];
    if (!now) return;
    const before = shown[side];
    if (before) {
      const lost = before.health + before.armor - (now.health + now.armor);
      if (lost > 0) {
        float(side, `-${lost}`, slam[side] ? "fx-dmg fx-dmg-big" : "fx-dmg");
        retrigger(tank[side], "is-hit", 350);
      }
    }
    slam[side] = false;
    shown[side] = { health: now.health, armor: now.armor };
    $(`arena-hp-${side}`).style.width = pct(now.health, now.max_health);
    $(`arena-ar-${side}`).style.width = pct(now.armor, now.max_armor);
    tank[side].classList.toggle("is-low", now.health / Math.max(1, now.max_health) < 0.3);
  }

  function sync(side, player) {
    latest[side] = player;
    $(`arena-name-${side}`).textContent = player.username;
    const points = $(`arena-pts-${side}`);
    if (points.textContent !== String(player.points)) {
      points.textContent = player.points;
      retrigger(points, "score-pop", 350);
    }
    // While a soldier is still on its way, the bars wait for the impact.
    if (incoming[side] === 0) paint(side);
  }

  function flushIdle() {
    if (airborne > 0 || idleQueue.length === 0) return;
    const queued = idleQueue;
    idleQueue = [];
    queued.forEach((callback) => callback());
  }

  // Runs callback once every bullet/soldier has landed (immediately if none is flying).
  function whenIdle(callback) {
    idleQueue.push(callback);
    flushIdle();
    if (idleQueue.length) {
      // Safety net: a hidden tab may never finish its animations.
      setTimeout(() => {
        airborne = 0;
        flushIdle();
      }, 5000);
    }
  }

  // Sends one unit across the arena, then calls onArrive(targetSide).
  function march(from, label, kind, onArrive) {
    const to = other(from);
    const prof = PROFILE[kind];
    const start = muzzle(from);
    const target = targetCenter(to);

    const el = document.createElement("div");
    el.className = `fx-unit fx-${from} ${kind}`;
    el.innerHTML = {
      "fx-skel": `<span class="fx-word"></span><span class="fx-fig">${SKELETON}</span>`,
      "fx-bullet": '<span class="fx-fig"></span>',
      "fx-orb": '<span class="fx-word"></span><span class="fx-orb-glow"></span>',
    }[kind];
    const word = el.querySelector(".fx-word");
    if (word) word.textContent = label;
    layer.appendChild(el);

    airborne += 1;
    if (prof.ground) {
      flying += 1;
      lane.classList.add("on");
    }
    retrigger(tank[from], "is-fire", 220);

    let anim;
    if (prof.ground) {
      const x0 = start.x;
      const x1 = from === "p1" ? tank.p2.offsetLeft - prof.w + 6 : tank.p1.offsetLeft + tank.p1.offsetWidth - 18;
      const ms = REDUCED ? 120 : Math.max(prof.min, Math.abs(x1 - x0) / prof.speed);
      anim = el.animate(
        [{ transform: `translate(${x0}px, 0px)` }, { transform: `translate(${x1}px, 0px)` }],
        { duration: ms, easing: "linear", fill: "forwards" },
      );
      el.style.bottom = "2.2rem";
      el.style.left = "0";
      el.style.top = "auto";
    } else {
      const dx = target.x - start.x;
      const dy = target.y - start.y;
      const distance = Math.hypot(dx, dy);
      const ms = REDUCED ? 120 : Math.max(350, Math.min(900, (distance / prof.ballisticSpeed) * 1000));
      const T = ms / 1000;
      const vy0 = (dy - 0.5 * GRAVITY * T * T) / T;
      const vx = dx / T;
      const frames = [];
      const steps = 36;
      for (let i = 0; i <= steps; i += 1) {
        const t = (T * i) / steps;
        const x = start.x + vx * t;
        const y = start.y + vy0 * t + 0.5 * GRAVITY * t * t;
        const tan = Math.atan2(vy0 + GRAVITY * t, vx);
        const rot = tan + (from === "p2" ? Math.PI : 0);
        frames.push({ transform: `translate(${x}px, ${y}px) rotate(${rot}rad)`, offset: i / steps });
      }
      el.style.left = "0";
      el.style.top = "0";
      el.style.bottom = "auto";
      anim = el.animate(frames, { duration: ms, easing: "linear", fill: "forwards" });
    }

    const arrive = () => {
      el.remove();
      if (prof.ground) {
        flying -= 1;
        if (flying <= 0) lane.classList.remove("on");
      }
      onArrive(to);
      airborne -= 1;
      flushIdle();
    };
    anim.finished.then(arrive, arrive);
  }

  // A validated word. Short word: a fast bullet. Long word (more than 5 letters):
  // a skeleton soldier walking along the ground; it lands harder.
  function attack(from, word) {
    if (finished || !tank[from]) return;
    const to = other(from);
    const heavy = (word || "").length > SOLDIER_MIN_EXCLUSIVE;
    incoming[to] += 1;
    march(from, word, heavy ? "fx-skel" : "fx-bullet", () => {
      if (heavy) {
        slam[to] = true;
        impactFx(to, true);
        bones(to);
        retrigger(stage, "is-slam", 420);
      } else {
        impactFx(to, false);
      }
      incoming[to] = Math.max(0, incoming[to] - 1);
      if (incoming[to] === 0) paint(to);
    });
  }

  // Server events that carry a human message (skills and regeneration).
  function event(name, side, message) {
    if (!side || !message || finished) return;
    if (name === "skill.activated") {
      march(side, "SKILL", "fx-orb", (to) => {
        impactFx(to, false);
        float(to, message, "fx-skill");
      });
    } else if (name?.startsWith("health")) {
      retrigger(tank[side], "is-heal");
      float(side, message, "fx-heal");
    } else if (name?.startsWith("armor")) {
      retrigger(tank[side], "is-armor");
      float(side, message, "fx-armor");
    } else if (name?.startsWith("skill")) {
      float(side, message, "fx-skill");
    }
  }

  function banner(text) {
    const el = $("arena-banner");
    el.textContent = text;
    retrigger(el, "show", 1500);
  }

  // winnerSide: "p1" | "p2" | null (draw). The finale waits for the fatal hit to land.
  function end(winnerSide) {
    if (endQueued) return;
    endQueued = true;
    whenIdle(() => {
      finished = true;
      incoming.p1 = incoming.p2 = 0;
      paint("p1");
      paint("p2");
      if (!winnerSide) return banner("Draw");
      tank[winnerSide].classList.add("is-winner");
      tank[other(winnerSide)].classList.add("is-ko");
      banner(winnerSide === "p1" ? "Victory!" : "Defeat");
    });
  }

  return { sync, attack, event, banner, end, whenIdle };
}
