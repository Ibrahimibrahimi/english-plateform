import { escapeHtml, request } from "./api.js";

const meta = document.getElementById("player-meta");
if (meta) {
  const container = meta.firstElementChild;
  try {
    const player = await request(`/api/players/${meta.dataset.id}`);
    const avatar = player.avatar;
    meta.innerHTML = `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body items-center text-center">
          <div class="avatar avatar-placeholder">
            <div class="w-28 rounded-full text-5xl flex items-center justify-center ring-4 ring-base-300" style="background:${escapeHtml(avatar.color)}">${avatar.emoji}</div>
          </div>
          <h1 class="card-title text-3xl mt-3">${escapeHtml(player.username)}</h1>
          <p class="opacity-70">${escapeHtml(avatar.label)} avatar</p>
          <div class="stats stats-vertical sm:stats-horizontal shadow mt-4 w-full">
            <div class="stat"><div class="stat-title">Learning points</div><div class="stat-value text-warning">${player.lifetime_learning_points}</div></div>
            <div class="stat"><div class="stat-title">Wins</div><div class="stat-value text-success">${player.wins}</div></div>
            <div class="stat"><div class="stat-title">Losses</div><div class="stat-value text-error">${player.losses}</div></div>
            <div class="stat"><div class="stat-title">Tournaments</div><div class="stat-value">${player.tournaments_played}</div></div>
          </div>
          <a href="/players" class="btn btn-outline btn-sm mt-4">Back to players</a>
        </div>
      </div>`;
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  }
}
