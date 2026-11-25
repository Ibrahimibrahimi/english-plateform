import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const container = document.getElementById("online-players");
if (container) {
  try {
    const players = await request("/api/players/online");
    container.innerHTML = players.length ? players.map((player) => `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="avatar avatar-placeholder">
                <div class="w-10 rounded-full text-xl flex items-center justify-center" style="background:${escapeHtml(player.avatar.color)}">${player.avatar.emoji}</div>
              </div>
              <h3 class="font-bold">${escapeHtml(player.username)}</h3>
            </div>
            <span class="badge badge-success badge-sm">Online</span>
          </div>
          <p class="text-sm opacity-70">Learning points: ${player.lifetime_learning_points} · Wins: ${player.wins}</p>
          <div class="flex gap-2 mt-2">
            <button class="btn btn-warning btn-sm challenge-player" data-id="${player.id}">Challenge</button>
            <a class="btn btn-ghost btn-sm" href="${escapeHtml(player.profile_url)}">Profile</a>
          </div>
        </div>
      </div>`).join("") : "<p class='opacity-70'>No other players online. Open another browser window to test 1v1.</p>";
    container.querySelectorAll(".challenge-player").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const challenge = await request("/api/challenges", {
            method: "POST",
            body: JSON.stringify({ opponent_id: Number(button.dataset.id) }),
          });
          await navigator.clipboard?.writeText(`${location.origin}${challenge.url}`);
          toast("Challenge created. Share link copied if available.", "success");
          location.href = `/playing/${challenge.match.id}`;
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">Log in to see online players: ${escapeHtml(error.message)}</div>`;
  }
}
