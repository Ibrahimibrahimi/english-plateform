import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const card = (item) => `
  <div class="panel panel-pad flex flex-col gap-3">
    <div class="flex items-start justify-between gap-3">
      <h3 class="font-display text-lg font-bold">${escapeHtml(item.name)}</h3>
      <span class="badge badge-accent badge-sm">${escapeHtml(item.status)}</span>
    </div>
    <p class="text-sm opacity-70">${escapeHtml(item.description || "No description")}</p>
    <div class="stat-tile"><span>Players</span><strong>${item.players} / ${item.max_players}</strong></div>
    <p class="font-mono text-xs tracking-widest opacity-70">${escapeHtml(item.allowed_letters)}</p>
    <a class="btn btn-primary btn-sm mt-auto gap-2" href="/tournament/${item.id}">View / Join</a>
  </div>`;

async function loadTournaments(search = "") {
  const container = document.getElementById("tournament-list");
  if (!container) return;
  try {
    const tournaments = await request(`/api/tournaments?search=${encodeURIComponent(search)}`);
    container.innerHTML = tournaments.length ? tournaments.map(card).join("") : "<div class='empty-state'><strong>No tournaments found</strong><span class='text-sm'>Try another name or check back later.</span></div>";
    reveal(container.children);
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  }
}

async function watchTournament(id) {
  let me;
  try {
    me = await request("/api/auth/me");
  } catch (error) {
    return;
  }
  let attempts = 0;
  const timer = setInterval(async () => {
    attempts += 1;
    if (attempts > 60) {
      clearInterval(timer);
      return;
    }
    try {
      const details = await request(`/api/tournaments/${id}`);
      const participant = details.participants.find((item) => item.id === me.id);
      if (participant?.status === "matched" && details.matches.length) {
        clearInterval(timer);
        location.href = `/playing/${details.matches[details.matches.length - 1].id}`;
      }
    } catch (error) {
      clearInterval(timer);
    }
  }, 2000);
}

const searchForm = document.getElementById("tournament-search-form");
if (searchForm) {
  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadTournaments(document.getElementById("tournament-search").value.trim());
  });
}

const meta = document.getElementById("tournament-meta");
if (meta) {
  const id = meta.dataset.id;
  try {
    const details = await request(`/api/tournaments/${id}`);
    document.getElementById("tournament-name").textContent = details.name;
    const skills = details.skills.map((skill) => `<span class="badge badge-ghost">${escapeHtml(skill.icon || "Skill")} ${escapeHtml(skill.label)}</span>`).join("") || "<span class='opacity-60'>None</span>";
    const participants = details.participants.map((player) => `<span class="badge badge-outline">${escapeHtml(player.username)}</span>`).join("") || "<span class='opacity-60'>None yet</span>";
    document.getElementById("tournament-details").innerHTML = `
      <p class="text-sm opacity-70">${escapeHtml(details.description || "No description")}</p>
      <div class="mt-4 grid gap-2 sm:grid-cols-3">
        <div class="stat-tile"><span>Status</span><strong>${escapeHtml(details.status)}</strong></div>
        <div class="stat-tile"><span>Players</span><strong>${details.participants.length} / ${details.max_players}</strong></div>
        <div class="stat-tile"><span>Letters</span><strong class="font-mono text-sm">${escapeHtml(details.allowed_letters)}</strong></div>
      </div>
      <div class="mt-4"><span class="text-xs uppercase tracking-wider opacity-60">Skills</span><div class="mt-2 flex flex-wrap gap-2">${skills}</div></div>
      <div class="mt-4"><span class="text-xs uppercase tracking-wider opacity-60">Participants</span><div class="mt-2 flex flex-wrap gap-2">${participants}</div></div>`;
    document.getElementById("tournament-join-form").classList.remove("hidden");
    reveal(document.getElementById("tournament-details"));
  } catch (error) {
    const details = document.getElementById("tournament-details");
    details.className = "alert alert-error";
    details.textContent = error.message;
  }
}

const joinForm = document.getElementById("tournament-join-form");
if (joinForm) {
  joinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = joinForm.querySelector("button[type=submit]");
    const errorEl = document.getElementById("key-error");
    const key = document.getElementById("tournament-key").value.trim().toUpperCase();
    const id = meta?.dataset.id;
    const path = id ? `/api/tournaments/${id}/join` : "/api/tournaments/join";
    button.disabled = true;
    errorEl.classList.add("hidden");
    try {
      const result = await request(path, {
        method: "POST",
        body: JSON.stringify({ key }),
      });
      const resultEl = document.getElementById("join-result");
      if (result.match) {
        location.href = `/playing/${result.match.id}`;
        return;
      }
      if (resultEl) {
        resultEl.className = "alert alert-success mt-4";
        resultEl.textContent = "Joined. Waiting for an opponent.";
        reveal(resultEl);
      }
      toast("Joined. Waiting for an opponent.", "success");
      watchTournament(result.tournament_id);
    } catch (error) {
      if (errorEl) {
        errorEl.textContent = error.message;
        errorEl.classList.remove("hidden");
        reveal(errorEl);
      } else {
        toast(error.message, "error");
      }
    } finally {
      button.disabled = false;
    }
  });
}

loadTournaments();
