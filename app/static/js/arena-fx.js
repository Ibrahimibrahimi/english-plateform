// Visual layer for the battle page. It never decides anything: it only animates
// what the server already sent (state / word / event / match_end).
const REDUCED = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const $ = (id) => document.getElementById(id);
const other = (side) => (side === "p1" ? "p2" : "p1");
const NOOP = { sync() {}, attack() {}, event() {}, banner() {}, end() {} };

export function createArenaFx() {
  const stage = $("arena-stage");
  if (!stage) return NOOP;

  const layer = $("arena-units");
  const lane = $("arena-lane");
  const tank = { p1: $("tank-p1"), p2: $("tank-p2") };
  const latest = { p1: null, p2: null }; // newest numbers from the server
  const shown = { p1: null, p2: null }; // numbers currently drawn on the bars
  const incoming = { p1: 0, p2: 0 }; // soldiers still marching toward this tank
  let flying = 0;
  let finished = false;

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

  // Draw bars from the newest server numbers; show damage if something was lost.
  function paint(side) {
    const now = latest[side];
    if (!now) return;
    const before = shown[side];
    if (before) {
      const lost = before.health + before.armor - (now.health + now.armor);
      if (lost > 0) {
        float(side, `-${lost}`, "fx-dmg");
        retrigger(tank[side], "is-hit", 350);
      }
    }
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

  // Sends one unit across the arena, then calls onArrive(targetSide).
  function march(from, label, kind, onArrive) {
    const to = other(from);
    const unitW = 34;
    const x0 = from === "p1" ? tank.p1.offsetLeft + tank.p1.offsetWidth - 20 : tank.p2.offsetLeft - 6;
    const x1 = from === "p1" ? tank.p2.offsetLeft - unitW + 6 : tank.p1.offsetLeft + tank.p1.offsetWidth - 18;

    const el = document.createElement("div");
    el.className = `fx-unit fx-${from} ${kind}`;
    el.innerHTML = '<span class="fx-word"></span><span class="fx-man"><i></i><i></i></span>';
    el.firstChild.textContent = label;
    layer.appendChild(el);

    flying += 1;
    lane.classList.add("on");
    retrigger(tank[from], "is-fire", 220);

    const ms = REDUCED ? 120 : Math.max(650, Math.abs(x1 - x0) / 0.42);
    const anim = el.animate(
      [{ transform: `translateX(${x0}px)` }, { transform: `translateX(${x1}px)` }],
      { duration: ms, easing: "linear", fill: "forwards" },
    );
    const arrive = () => {
      el.remove();
      flying -= 1;
      if (flying <= 0) lane.classList.remove("on");
      onArrive(to);
    };
    anim.finished.then(arrive, arrive);
  }

  // A validated word: the soldier carries the word to the opponent's tank.
  function attack(from, word) {
    if (finished || !tank[from]) return;
    const to = other(from);
    incoming[to] += 1;
    march(from, word, "fx-soldier", () => {
      spark(to);
      incoming[to] = Math.max(0, incoming[to] - 1);
      if (incoming[to] === 0) paint(to);
    });
  }

  // Server events that carry a human message (skills and regeneration).
  function event(name, side, message) {
    if (!side || !message || finished) return;
    if (name === "skill.activated") {
      march(side, "SKILL", "fx-orb", (to) => {
        spark(to, "fx-spark-skill");
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

  // winnerSide: "p1" | "p2" | null (draw)
  function end(winnerSide) {
    if (finished) return;
    finished = true;
    incoming.p1 = incoming.p2 = 0;
    paint("p1");
    paint("p2");
    if (!winnerSide) return banner("Draw");
    tank[winnerSide].classList.add("is-winner");
    tank[other(winnerSide)].classList.add("is-ko");
    banner(winnerSide === "p1" ? "Victory!" : "Defeat");
  }

  return { sync, attack, event, banner, end };
}
