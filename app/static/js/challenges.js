import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const settings = await request("/api/config");

const skillOptions = document.getElementById("skill-options");
if (skillOptions) {
  skillOptions.innerHTML = settings.skills.map(({ code, label }) => `
    <label class="label cursor-pointer gap-2 border border-base-300 rounded px-2">
      <input type="checkbox" class="checkbox checkbox-warning checkbox-sm" name="skills" value="${escapeHtml(code)}" checked />
      <span class="label-text text-xs">${escapeHtml(label)}</span>
    </label>`).join("");
}

const createForm = document.getElementById("challenge-form");
if (createForm) {
  createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(createForm);
    const skills = form.getAll("skills").join(",");
    try {
      const challenge = await request("/api/challenges", {
        method: "POST",
        body: JSON.stringify({ allowed_letters: form.get("letters"), skills }),
      });
      const result = document.getElementById("challenge-result");
      result.classList.remove("hidden");
      result.innerHTML = `Challenge key: <code class="font-mono">${escapeHtml(challenge.key)}</code><br />Share link: <a class="link" href="${escapeHtml(challenge.url)}">${escapeHtml(location.origin + challenge.url)}</a><br /><a class="btn btn-sm btn-warning mt-2" href="/playing/${challenge.match.id}">Go to match lobby</a>`;
      toast("Challenge created", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

const joinKeyInput = document.getElementById("challenge-key");
if (joinKeyInput && !joinKeyInput.value) {
  const shared = new URLSearchParams(location.search).get("key");
  if (shared) joinKeyInput.value = shared.toUpperCase();
}

const joinForm = document.getElementById("join-form");
if (joinForm) {
  joinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const key = document.getElementById("challenge-key").value.trim().toUpperCase();
    try {
      const match = await request(`/api/challenges/${key}/join`, { method: "POST", body: JSON.stringify({}) });
      location.href = `/playing/${match.id}`;
    } catch (error) {
      const errorEl = document.getElementById("key-error");
      errorEl.textContent = error.message;
      errorEl.classList.remove("hidden");
    }
  });
}

const searchForm = document.getElementById("search-form");
if (searchForm) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const key = document.getElementById("search-key").value.trim().toUpperCase();
    const container = document.getElementById("challenge-details");
    try {
      const challenge = await request(`/api/challenges/${key}`);
      container.innerHTML = `<div class="alert"><div><p><b>Status:</b> ${escapeHtml(challenge.status)}</p><p><b>Letters:</b> ${escapeHtml(challenge.allowed_letters)}</p><p><b>Skills:</b> ${escapeHtml(challenge.skills || "All")}</p><a class="btn btn-warning btn-sm mt-3" href="/challenge/join?key=${encodeURIComponent(challenge.key)}">Join</a></div></div>`;
    } catch (error) {
      container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
    }
  });
}
