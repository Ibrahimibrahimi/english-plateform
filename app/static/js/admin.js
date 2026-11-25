import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const settings = await request("/api/config");

const options = document.getElementById("skill-options");
if (options) {
  options.innerHTML = settings.skills.map(({ code, label, icon }) => `<label class="label cursor-pointer gap-2 border border-base-300 rounded px-2"><input type="checkbox" class="checkbox checkbox-warning checkbox-sm" name="skills" value="${escapeHtml(code)}" checked /><span class="label-text text-xs">${escapeHtml(icon || "✨")} ${escapeHtml(label)}</span></label>`).join("");
}

async function loadLetters() {
  const list = document.getElementById("letterset-list");
  if (!list) return;
  try {
    const sets = await request("/admin/api/letter-sets");
    list.innerHTML = sets.length ? sets.map((set) => `<div class="flex justify-between border-b border-base-300 py-1"><span>${escapeHtml(set.name)}</span><button class="btn btn-xs btn-error delete-set" data-id="${set.id}">Delete</button></div>`).join("") : "<p class='opacity-70'>No letter sets.</p>";
    list.querySelectorAll(".delete-set").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await request(`/admin/api/letter-sets/${button.dataset.id}`, { method: "DELETE" });
          loadLetters();
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

async function loadTournaments() {
  const list = document.getElementById("admin-tournaments");
  if (!list) return;
  try {
    const tournaments = await request("/admin/api/tournaments");
    list.innerHTML = tournaments.length ? tournaments.map((item) => `<div class="card bg-base-100 border border-base-300"><div class="card-body p-4"><h3 class="font-bold">${escapeHtml(item.name)}</h3><p class="text-xs">Key: ${escapeHtml(item.key)} · ${item.max_players} players · letters: ${escapeHtml(item.allowed_letters)}</p><select class="select select-bordered select-sm" data-id="${item.id}">${settings.tournament_statuses.map((status) => `<option ${status === item.status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}</select><button class="btn btn-sm btn-warning update-status" data-id="${item.id}">Update</button></div></div>`).join("") : "<p class='opacity-70'>No tournaments.</p>";
    list.querySelectorAll(".update-status").forEach((button) => {
      button.addEventListener("click", async () => {
        const status = list.querySelector(`select[data-id="${button.dataset.id}"]`).value;
        try {
          await request(`/admin/api/tournaments/${button.dataset.id}/status`, { method: "POST", body: JSON.stringify({ status }) });
          toast("Tournament updated", "success");
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

async function loadActions() {
  const list = document.getElementById("admin-actions");
  if (!list) return;
  try {
    const rows = await request("/admin/api/actions");
    list.innerHTML = rows.length ? rows.map((row) => `<div class="border-b border-base-300 py-1">${escapeHtml(row.created_at)} · ${escapeHtml(row.action)} · ${escapeHtml(row.detail)}</div>`).join("") : "<p class='opacity-70'>No actions yet.</p>";
  } catch (error) {
    list.textContent = error.message;
  }
}

const letterForm = document.getElementById("letterset-form");
if (letterForm) {
  letterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(letterForm);
    try {
      await request("/admin/api/letter-sets", { method: "POST", body: JSON.stringify({ name: form.get("name"), letters: form.get("letters") }) });
      letterForm.reset();
      loadLetters();
      toast("Letter set added", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

const tournamentForm = document.getElementById("tournament-form");
if (tournamentForm) {
  tournamentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(tournamentForm);
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
      document.getElementById("tournament-create-result").textContent = `Created "${result.name}" with key ${result.key} (${result.max_players} players)`;
      loadTournaments();
      toast("Tournament created", "success");
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

loadLetters();
loadTournaments();
loadActions();
