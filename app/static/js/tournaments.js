import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const card = (item) => `
  <div class="card bg-base-100 border border-base-300">
    <div class="card-body">
      <h3 class="card-title">${escapeHtml(item.name)}</h3>
      <p class="text-sm opacity-70">${escapeHtml(item.description || "No description")}</p>
      <p class="text-xs">Players: ${item.players} / ${item.max_players} · ${escapeHtml(item.status)} · Letters: ${escapeHtml(item.allowed_letters)}</p>
      <div class="card-actions mt-2">
        <a class="btn btn-sm btn-warning" href="/tournament/${item.id}">View / Join</a>
      </div>
    </div>
  </div>`;

async function loadTournaments(search = "") {
  const container = document.getElementById("tournament-list");
  if (!container) return;
  try {
    const tournaments = await request(`/api/tournaments?search=${encodeURIComponent(search)}`);
    container.innerHTML = tournaments.length ? tournaments.map(card).join("") : "<p class='opacity-70'>No tournaments found.</p>";
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
    document.getElementById("tournament-details").innerHTML = `
      <p>${escapeHtml(details.description || "No description")}</p>
      <p><b>Status:</b> ${escapeHtml(details.status)} · <b>Players:</b> ${details.participants.length} / ${details.max_players}</p>
      <p><b>Letters:</b> ${escapeHtml(details.allowed_letters)}</p>
      <p><b>Skills:</b> ${details.skills.map((skill) => `${escapeHtml(skill.icon || "✨")} ${escapeHtml(skill.label)}`).join(", ") || "None"}</p>
      <p><b>Participants:</b> ${details.participants.map((player) => escapeHtml(player.username)).join(", ") || "None"}</p>`;
    document.getElementById("tournament-join-form").classList.remove("hidden");
  } catch (error) {
    document.getElementById("tournament-details").textContent = error.message;
  }
}

const joinForm = document.getElementById("tournament-join-form");
if (joinForm) {
  joinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const key = document.getElementById("tournament-key").value.trim().toUpperCase();
    const id = meta?.dataset.id;
    const path = id ? `/api/tournaments/${id}/join` : "/api/tournaments/join";
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
      if (resultEl) resultEl.textContent = "Joined. Waiting for an opponent.";
      toast("Joined. Waiting for an opponent.", "success");
      watchTournament(result.tournament_id);
    } catch (error) {
      const errorEl = document.getElementById("key-error");
      if (errorEl) {
        errorEl.textContent = error.message;
        errorEl.classList.remove("hidden");
      } else {
        toast(error.message, "error");
      }
    }
  });
}

loadTournaments();
