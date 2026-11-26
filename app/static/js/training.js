import { request } from "./api.js";
import { toast } from "./ui.js";
import { pop } from "./motion.js";
import { createArenaFx } from "./arena-fx.js";

const meta = document.getElementById("training-meta");
if (meta) {
  const config = {
    letters: meta.dataset.letters || "AEIOURSTLND",
    dummyHealth: Number(meta.dataset.dummyHealth || 300),
    attackBase: Number(meta.dataset.attackBase || 6),
    attackPerPoint: Number(meta.dataset.attackPerPoint || 1),
    attackCap: Number(meta.dataset.attackCap || 30),
  };
  const fx = createArenaFx();
  const form = document.getElementById("training-form");
  const lettersInput = document.getElementById("training-letters");
  const wordInput = document.getElementById("training-word");
  const scoreEl = document.getElementById("training-score");
  const wordsCountEl = document.getElementById("training-words-count");
  const damageEl = document.getElementById("training-damage");
  const dummyHealthEl = document.getElementById("dummy-health");
  const dummyArmorEl = document.getElementById("dummy-armor");
  const acceptedEl = document.getElementById("training-accepted");
  const feedback = document.getElementById("training-feedback");
  const submitButton = form.querySelector("button[type=submit]");
  const resetButton = document.getElementById("training-reset");
  const dummyTank = document.getElementById("tank-p2");
  let player;
  let dummy;
  let used = new Set();
  let busy = false;
  let finished = false;

  const renderStats = () => {
    scoreEl.textContent = player.points;
    wordsCountEl.textContent = used.size;
    damageEl.textContent = player.attack;
    dummyHealthEl.textContent = `${dummy.health}/${dummy.max_health}`;
    dummyArmorEl.textContent = `${dummy.armor}/${dummy.max_armor}`;
    fx.sync("p1", player);
    fx.sync("p2", dummy);
  };

  const reset = () => {
    player = {
      username: "You",
      points: 0,
      health: 100,
      max_health: 100,
      armor: 0,
      max_armor: 0,
      attack: config.attackBase,
    };
    dummy = {
      username: "Training dummy",
      points: 0,
      health: config.dummyHealth,
      max_health: config.dummyHealth,
      armor: 0,
      max_armor: 0,
      attack: 0,
    };
    used = new Set();
    busy = false;
    finished = false;
    acceptedEl.innerHTML = "";
    feedback.className = "min-h-5 flex-1 text-sm";
    feedback.textContent = "";
    wordInput.disabled = false;
    submitButton.disabled = false;
    resetButton.classList.add("hidden");
    dummyTank.classList.remove("is-ko", "is-low");
    document.getElementById("arena-banner").textContent = "";
    renderStats();
    wordInput.focus();
  };

  lettersInput.value = config.letters.toUpperCase();
  reset();

  lettersInput.addEventListener("change", () => {
    used = new Set();
    acceptedEl.innerHTML = "";
    feedback.className = "min-h-5 flex-1 text-sm";
    feedback.textContent = "New letter set ready. Previous words are cleared.";
  });

  resetButton.addEventListener("click", reset);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || finished) return;
    const word = wordInput.value.trim().toLowerCase();
    if (!word) return;
    if (used.has(word)) {
      feedback.className = "min-h-5 flex-1 text-sm font-semibold text-warning";
      feedback.textContent = "That word was already used.";
      pop(wordInput);
      return;
    }
    busy = true;
    submitButton.disabled = true;
    try {
      const result = await request("/api/words/validate", {
        method: "POST",
        body: JSON.stringify({ word, letters: lettersInput.value }),
      });
      if (!result.valid) {
        feedback.className = "min-h-5 flex-1 text-sm font-semibold text-error";
        feedback.textContent = "Not a valid word for these letters.";
        pop(wordInput);
        return;
      }
      used.add(word);
      const points = result.points;
      player.points += points;
      player.attack = Math.min(config.attackCap, config.attackBase + player.points * config.attackPerPoint);
      const damage = player.attack;
      fx.sync("p1", player);
      fx.attack("p1", word);
      fx.whenIdle(() => {
        const absorbed = Math.min(dummy.armor, damage);
        dummy.armor -= absorbed;
        dummy.health = Math.max(0, dummy.health - (damage - absorbed));
        renderStats();
        const badge = document.createElement("span");
        badge.className = "badge badge-success badge-outline";
        badge.textContent = `${word} +${points}`;
        acceptedEl.appendChild(badge);
        pop(badge);
        wordInput.value = "";
        feedback.className = "min-h-5 flex-1 text-sm font-semibold text-success";
        feedback.textContent = `Accepted ${word} for ${points} points. ${damage} damage.`;
        if (dummy.health <= 0) {
          finished = true;
          wordInput.disabled = true;
          submitButton.disabled = true;
          resetButton.classList.remove("hidden");
          dummyTank.classList.add("is-ko");
          fx.banner("Dummy destroyed");
          toast("Training dummy destroyed", "success");
        }
      });
    } catch (error) {
      feedback.className = "min-h-5 flex-1 text-sm font-semibold text-error";
      feedback.textContent = error.message;
      pop(wordInput);
    } finally {
      busy = false;
      if (!finished) submitButton.disabled = false;
      wordInput.focus();
    }
  });
}
