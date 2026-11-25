import { request } from "./api.js";
import { toast } from "./ui.js";
import { pop } from "./motion.js";

const form = document.getElementById("practice-form");
if (form) {
  const lettersInput = document.getElementById("practice-letters");
  const wordInput = document.getElementById("practice-word");
  const scoreEl = document.getElementById("practice-score");
  const wordsEl = document.getElementById("practice-words");
  const progress = document.getElementById("practice-timer");
  const timeEl = document.getElementById("practice-time");
  const feedback = document.getElementById("practice-feedback");
  const button = form.querySelector("button[type=submit]");
  const used = new Set();
  let score = 0;
  let remaining = 60;

  const timer = setInterval(() => {
    remaining -= 1;
    progress.value = Math.max(0, remaining);
    timeEl.textContent = `${Math.max(0, remaining)}s`;
    if (remaining <= 0) {
      clearInterval(timer);
      wordInput.disabled = true;
      button.disabled = true;
      feedback.className = "min-h-5 text-sm font-semibold text-accent";
      feedback.textContent = `Practice finished with ${score} points`;
      toast(`Practice finished with ${score} points`, "info");
    }
  }, 1000);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const word = wordInput.value.trim().toLowerCase();
    if (!word || used.has(word)) return;
    button.disabled = true;
    try {
      const result = await request("/api/words/validate", {
        method: "POST",
        body: JSON.stringify({ word, letters: lettersInput.value }),
      });
      if (!result.valid) {
        feedback.className = "min-h-5 text-sm font-semibold text-error";
        feedback.textContent = "Not a valid word for these letters.";
        pop(wordInput);
        return;
      }
      used.add(word);
      score += result.points;
      scoreEl.textContent = score;
      pop(scoreEl);
      const badge = document.createElement("span");
      badge.className = "badge badge-success badge-outline";
      badge.textContent = `${word} +${result.points}`;
      wordsEl.appendChild(badge);
      pop(badge);
      wordInput.value = "";
      feedback.className = "min-h-5 text-sm font-semibold text-success";
      feedback.textContent = `Accepted ${word} for ${result.points} points.`;
    } catch (error) {
      feedback.className = "min-h-5 text-sm font-semibold text-error";
      feedback.textContent = error.message;
    } finally {
      if (remaining > 0) button.disabled = false;
      wordInput.focus();
    }
  });
}
