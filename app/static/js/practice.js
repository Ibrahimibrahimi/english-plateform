import { request } from "./api.js";
import { toast } from "./ui.js";

const form = document.getElementById("practice-form");
if (form) {
  const lettersInput = document.getElementById("practice-letters");
  const wordInput = document.getElementById("practice-word");
  const scoreEl = document.getElementById("practice-score");
  const wordsEl = document.getElementById("practice-words");
  const progress = document.getElementById("practice-timer");
  const timeEl = document.getElementById("practice-time");
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
      form.querySelector("button").disabled = true;
      toast(`Practice finished with ${score} points`, "info");
    }
  }, 1000);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const word = wordInput.value.trim().toLowerCase();
    if (!word || used.has(word)) return;
    try {
      const result = await request("/api/words/validate", {
        method: "POST",
        body: JSON.stringify({ word, letters: lettersInput.value }),
      });
      if (!result.valid) {
        toast("Invalid word", "error");
        return;
      }
      used.add(word);
      score += result.points;
      scoreEl.textContent = score;
      const badge = document.createElement("span");
      badge.className = "badge badge-success";
      badge.textContent = `${word} +${result.points}`;
      wordsEl.appendChild(badge);
      wordInput.value = "";
    } catch (error) {
      toast(error.message, "error");
    }
    wordInput.focus();
  });
}
