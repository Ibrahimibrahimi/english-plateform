import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const accessBadge = (requiresKey) => requiresKey
  ? '<span class="badge badge-outline badge-sm">Key required</span>'
  : '<span class="badge badge-success badge-outline badge-sm">Open access</span>';

const card = (item) => `
  <div class="panel panel-pad flex flex-col gap-3">
    <div class="flex items-start justify-between gap-3">
      <h3 class="font-display text-lg font-bold">${escapeHtml(item.name)}</h3>
      <div class="flex flex-wrap gap-2 justify-end">
        ${accessBadge(item.requires_key !== false)}
        <span class="badge badge-accent badge-sm">${escapeHtml(item.status)}</span>
      </div>
    </div>
    <p class="text-sm opacity-70">${escapeHtml(item.description || "No description")}</p>
    <div class="stat-tile"><span>Players</span><strong>${item.players} / ${item.max_players}</strong></div>
    <p class="font-mono text-xs tracking-widest opacity-70">${escapeHtml(item.allowed_letters)}</p>
    <a class="btn btn-primary btn-sm mt-auto gap-2" href="/tournament/${item.id}">${item.requires_key === false ? "View / Join" : "View / Join"}</a>
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

function setJoinAccess(requiresKey, status, viewerParticipant) {
  const form = document.getElementById("tournament-join-form");
  if (!form) return;
  const keyField = document.getElementById("tournament-key-field");
  const keyInput = document.getElementById("tournament-key");
  const note = document.getElementById("tournament-access-note");
  const label = document.getElementById("tournament-join-btn-label");
  const canJoin = status === "open" && !viewerParticipant;

  if (keyField) keyField.classList.toggle("hidden", !requiresKey);
  if (keyInput) {
    keyInput.required = Boolean(requiresKey);
    if (!requiresKey) keyInput.value = "";
  }
  if (label) label.textContent = requiresKey ? "Join" : "Join now";
  if (note) {
    note.textContent = requiresKey
      ? "Enter the tournament key to join."
      : "This tournament is open to all logged-in players.";
    note.classList.toggle("hidden", !canJoin);
  }
  form.classList.toggle("hidden", !canJoin);
}

function renderViewer(details) {
  const panel = document.getElementById("tournament-viewer");
  if (!panel) return;
  const participant = details.viewer_participant;
  const match = details.viewer_match;
  if (!participant) {
    panel.classList.add("hidden");
    panel.innerHTML = "";
    return;
  }
  let title = "You're entered";
  let message = "You're in this tournament.";
  let href = "";
  let cta = "";
  if (match?.status === "waiting") {
    title = "Waiting for an opponent";
    message = "Your tournament lobby is ready. We’ll start automatically when another player joins.";
    href = `/playing/${match.id}`;
    cta = "Return to lobby";
  } else if (match?.status === "active") {
    title = "Match in progress";
    message = "Your tournament match has already started.";
    href = `/playing/${match.id}`;
    cta = "Return to match";
  } else if (match?.status === "finished") {
    title = "Match finished";
    message = "Your latest tournament match is complete.";
    href = `/playing/${match.id}`;
    cta = "View result";
  } else {
    title = "Resume tournament entry";
    message = "You’re registered, but there is no active lobby right now. Join again to reopen a waiting lobby.";
  }
  panel.className = "mt-6 alert alert-info";
  panel.innerHTML = `
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between w-full">
      <div>
        <strong class="font-display text-lg">${escapeHtml(title)}</strong>
        <p class="text-sm opacity-80">${escapeHtml(message)}</p>
      </div>
      ${href ? `<a class="btn btn-primary btn-sm" href="${href}">${escapeHtml(cta)}</a>` : ""}
    </div>`;
  panel.classList.remove("hidden");
}

const searchForm = document.getElementById("tournament-search-form");
if (searchForm) {
  searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadTournaments(document.getElementById("tournament-search").value.trim());
  });
}

const meta = document.getElementById("tournament-meta");
let tournamentDetails = null;
if (meta) {
  const id = meta.dataset.id;
  try {
    const details = await request(`/api/tournaments/${id}`);
    tournamentDetails = details;
    document.getElementById("tournament-name").textContent = details.name;
    const skills = details.skills.map((skill) => `<span class="badge badge-ghost">${escapeHtml(skill.icon || "Skill")} ${escapeHtml(skill.label)}</span>`).join("") || "<span class='opacity-60'>None</span>";
    const participants = details.participants.map((player) => `<span class="badge badge-outline">${escapeHtml(player.username)}</span>`).join("") || "<span class='opacity-60'>None yet</span>";
    const access = details.requires_key === false ? "Open to everyone" : "Key required";
    document.getElementById("tournament-details").innerHTML = `
      <p class="text-sm opacity-70">${escapeHtml(details.description || "No description")}</p>
      <div class="mt-4 grid gap-2 sm:grid-cols-4">
        <div class="stat-tile"><span>Status</span><strong>${escapeHtml(details.status)}</strong></div>
        <div class="stat-tile"><span>Access</span><strong>${escapeHtml(access)}</strong></div>
        <div class="stat-tile"><span>Players</span><strong>${details.participants.length} / ${details.max_players}</strong></div>
        <div class="stat-tile"><span>Letters</span><strong class="font-mono text-sm">${escapeHtml(details.allowed_letters)}</strong></div>
      </div>
      <div class="mt-4"><span class="text-xs uppercase tracking-wider opacity-60">Skills</span><div class="mt-2 flex flex-wrap gap-2">${skills}</div></div>
      <div class="mt-4"><span class="text-xs uppercase tracking-wider opacity-60">Participants</span><div class="mt-2 flex flex-wrap gap-2">${participants}</div></div>`;
    renderViewer(details);
    setJoinAccess(details.requires_key !== false, details.status, details.viewer_participant);
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
    const requiresKey = id ? tournamentDetails?.requires_key !== false : true;
    button.disabled = true;
    if (errorEl) errorEl.classList.add("hidden");
    try {
      const result = await request(path, {
        method: "POST",
        body: JSON.stringify(requiresKey ? { key } : {}),
      });
      if (result.match?.id) {
        location.href = `/playing/${result.match.id}`;
        return;
      }
      const resultEl = document.getElementById("join-result");
      if (resultEl) {
        resultEl.className = "alert alert-success mt-4";
        resultEl.textContent = "Joined. Open your waiting lobby to continue.";
        reveal(resultEl);
      }
      toast("Joined tournament", "success");
      if (id) location.reload();
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
