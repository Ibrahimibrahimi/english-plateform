import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const settings = await request("/api/config");
const skillText = (raw) => {
  const codes = (raw || "").split(",").filter(Boolean);
  if (!codes.length) return "All";
  return codes.map((code) => {
    const skill = settings.skills.find((item) => item.code === code);
    return skill ? `${skill.icon || "Skill"} ${skill.label}` : code;
  }).join(", ");
};

const timingText = (challenge) => {
  const delay = Number(challenge.start_delay_seconds || 0);
  const start = delay ? `${delay}s delay` : "Instant start";
  const length = challenge.end_mode === "infinite" ? "Until KO" : `${settings.rounds_per_match} rounds`;
  return `${start} · ${length}`;
};

const skillOptions = document.getElementById("skill-options");
if (skillOptions) {
  skillOptions.innerHTML = settings.skills.map(({ code, label, icon }) => `
    <label class="label cursor-pointer gap-2 rounded-lg border border-base-300 bg-base-200/40 px-3">
      <input type="checkbox" class="checkbox checkbox-warning checkbox-sm" name="skills" value="${escapeHtml(code)}" checked />
      <span class="label-text text-xs">${escapeHtml(icon || "Skill")} ${escapeHtml(label)}</span>
    </label>`).join("");
}

const createForm = document.getElementById("challenge-form");
if (createForm) {
  createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = createForm.querySelector("button[type=submit]");
    const form = new FormData(createForm);
    button.disabled = true;
    try {
      const challenge = await request("/api/challenges", {
        method: "POST",
        body: JSON.stringify({
          allowed_letters: form.get("letters"),
          skills: form.getAll("skills").join(","),
          start_delay_seconds: Number(form.get("start_delay_seconds") || 0),
          end_mode: form.get("end_mode") || "rounds",
        }),
      });
      const result = document.getElementById("challenge-result");
      result.classList.remove("hidden");
      result.innerHTML = `
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <strong class="font-display text-lg">Challenge ready</strong>
            <p class="text-sm opacity-70">Key: <code class="font-mono">${escapeHtml(challenge.key)}</code></p>
            <p class="text-sm opacity-70">${escapeHtml(timingText(challenge))}</p>
            <a class="link link-primary text-sm" href="${escapeHtml(challenge.url)}">${escapeHtml(location.origin + challenge.url)}</a>
          </div>
          <a class="btn btn-primary btn-sm gap-2" href="/playing/${challenge.match.id}">Open lobby</a>
        </div>`;
      reveal(result);
      toast("Challenge created", "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      button.disabled = false;
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
    const button = joinForm.querySelector("button[type=submit]");
    const errorEl = document.getElementById("key-error");
    const key = joinKeyInput.value.trim().toUpperCase();
    button.disabled = true;
    errorEl.classList.add("hidden");
    try {
      const match = await request(`/api/challenges/${key}/join`, { method: "POST", body: JSON.stringify({}) });
      location.href = `/playing/${match.id}`;
    } catch (error) {
      errorEl.textContent = error.message;
      errorEl.classList.remove("hidden");
      reveal(errorEl);
    } finally {
      button.disabled = false;
    }
  });
}

const searchForm = document.getElementById("search-form");
if (searchForm) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = searchForm.querySelector("button[type=submit]");
    const container = document.getElementById("challenge-details");
    const key = document.getElementById("search-key").value.trim().toUpperCase();
    button.disabled = true;
    try {
      const challenge = await request(`/api/challenges/${key}`);
      container.innerHTML = `
        <div class="panel panel-pad">
          <span class="badge badge-accent badge-outline mb-4">${escapeHtml(challenge.status)}</span>
          <div class="grid gap-3 sm:grid-cols-2">
            <div><span class="text-xs uppercase tracking-wider opacity-60">Letters</span><strong class="mt-1 block font-mono">${escapeHtml(challenge.allowed_letters)}</strong></div>
            <div><span class="text-xs uppercase tracking-wider opacity-60">Skills</span><strong class="mt-1 block text-sm">${escapeHtml(skillText(challenge.skills))}</strong></div>
            <div><span class="text-xs uppercase tracking-wider opacity-60">Start</span><strong class="mt-1 block text-sm">${escapeHtml(Number(challenge.start_delay_seconds) ? `${challenge.start_delay_seconds}s delay` : "Instant")}</strong></div>
            <div><span class="text-xs uppercase tracking-wider opacity-60">Length</span><strong class="mt-1 block text-sm">${escapeHtml(challenge.end_mode === "infinite" ? "Until KO" : `${settings.rounds_per_match} rounds`)}</strong></div>
          </div>
          <a class="btn btn-primary btn-sm mt-5 gap-2" href="/challenge/join?key=${encodeURIComponent(challenge.key)}">Join challenge</a>
        </div>`;
      reveal(container.children);
    } catch (error) {
      container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
    }
  });
}
