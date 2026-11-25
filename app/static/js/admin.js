import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const settings = await request("/api/config");
const empty = (title, message) => `<div class="empty-state"><strong>${title}</strong><span class="text-sm">${message}</span></div>`;
const errorBox = (error) => `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;

const options = document.getElementById("skill-options");
if (options) {
  options.innerHTML = settings.skills.map(({ code, label, icon }) => `
    <label class="label cursor-pointer gap-2 rounded-lg border border-base-300 bg-base-200/40 px-3">
      <input type="checkbox" class="checkbox checkbox-warning checkbox-sm" name="skills" value="${escapeHtml(code)}" checked />
      <span class="label-text text-xs">${escapeHtml(icon || "Skill")} ${escapeHtml(label)}</span>
    </label>`).join("");
}

async function loadLetters() {
  const list = document.getElementById("letterset-list");
  if (!list) return;
  try {
    const sets = await request("/admin/api/letter-sets");
    list.innerHTML = sets.length ? sets.map((set) => `
      <div class="panel panel-pad flex items-center justify-between gap-3 py-3">
        <div class="min-w-0">
          <strong class="font-display">${escapeHtml(set.name)}</strong>
          <p class="font-mono text-xs tracking-widest opacity-70">${escapeHtml(set.letters)}</p>
        </div>
        <button class="btn btn-error btn-xs delete-set" data-id="${set.id}">Delete</button>
      </div>`).join("") : empty("No letter sets", "Add a curated set above.");
    reveal(list.children);
    list.querySelectorAll(".delete-set").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await request(`/admin/api/letter-sets/${button.dataset.id}`, { method: "DELETE" });
          loadLetters();
          toast("Letter set deleted", "success");
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    list.innerHTML = errorBox(error);
  }
}

async function loadTournaments() {
  const list = document.getElementById("admin-tournaments");
  if (!list) return;
  try {
    const tournaments = await request("/admin/api/tournaments");
    list.innerHTML = tournaments.length ? tournaments.map((item) => `
      <div class="panel panel-pad flex flex-col gap-3">
        <div class="flex items-start justify-between gap-3">
          <h3 class="font-display text-lg font-bold">${escapeHtml(item.name)}</h3>
          <span class="badge badge-warning badge-sm">${escapeHtml(item.status)}</span>
        </div>
        <p class="text-xs opacity-70">Key: <code class="font-mono">${escapeHtml(item.key)}</code></p>
        <div class="grid grid-cols-2 gap-2">
          <div class="stat-tile"><span>Players</span><strong>${item.max_players}</strong></div>
          <div class="stat-tile"><span>Letters</span><strong class="font-mono text-xs">${escapeHtml(item.allowed_letters)}</strong></div>
        </div>
        <div class="mt-auto flex flex-wrap gap-2 pt-2">
          <select class="select select-bordered select-sm" data-id="${item.id}">${settings.tournament_statuses.map((status) => `<option ${status === item.status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select>
          <button class="btn btn-warning btn-sm update-status" data-id="${item.id}">Update</button>
        </div>
      </div>`).join("") : empty("No tournaments", "Create one to get started.");
    reveal(list.children);
    list.querySelectorAll(".update-status").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        const status = list.querySelector(`select[data-id="${button.dataset.id}"]`).value;
        try {
          await request(`/admin/api/tournaments/${button.dataset.id}/status`, { method: "POST", body: JSON.stringify({ status }) });
          toast("Tournament updated", "success");
          loadTournaments();
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    list.innerHTML = errorBox(error);
  }
}

async function loadActions() {
  const list = document.getElementById("admin-actions");
  if (!list) return;
  try {
    const rows = await request("/admin/api/actions");
    list.innerHTML = rows.length ? `<div class="grid gap-2">${rows.map((row) => `
      <div class="rounded-lg border border-base-300 bg-base-200/40 px-3 py-2">
        <span class="font-mono text-xs opacity-70">${escapeHtml(row.created_at)}</span>
        <strong class="mx-2 text-warning">${escapeHtml(row.action)}</strong>
        <span class="text-sm">${escapeHtml(row.detail)}</span>
      </div>`).join("")}</div>` : empty("No actions yet", "Admin activity will appear here.");
    reveal(list.children);
  } catch (error) {
    list.innerHTML = errorBox(error);
  }
}

const letterForm = document.getElementById("letterset-form");
if (letterForm) {
  letterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = letterForm.querySelector("button[type=submit]");
    const form = new FormData(letterForm);
    button.disabled = true;
    try {
      await request("/admin/api/letter-sets", { method: "POST", body: JSON.stringify({ name: form.get("name"), letters: form.get("letters") }) });
      letterForm.reset();
      loadLetters();
      toast("Letter set added", "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
}

const tournamentForm = document.getElementById("tournament-form");
if (tournamentForm) {
  tournamentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = tournamentForm.querySelector("button[type=submit]");
    const form = new FormData(tournamentForm);
    button.disabled = true;
    try {
      const result = await request("/admin/api/tournaments", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          description: form.get("description"),
          max_players: Number(form.get("max_players")),
          allowed_letters: form.get("allowed_letters"),
          skills: form.getAll("skills").join(","),
        }),
      });
      const resultEl = document.getElementById("tournament-create-result");
      resultEl.className = "alert alert-success mt-5";
      resultEl.innerHTML = `Created <strong>${escapeHtml(result.name)}</strong> with key <code class="font-mono">${escapeHtml(result.key)}</code> for ${result.max_players} players.`;
      reveal(resultEl);
      loadTournaments();
      toast("Tournament created", "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
}

loadLetters();
loadTournaments();
loadActions();
