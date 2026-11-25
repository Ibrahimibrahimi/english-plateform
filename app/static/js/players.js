import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const container = document.getElementById("online-players");
if (container) {
  try {
    const players = await request("/api/players/online");
    container.innerHTML = players.length ? players.map((player) => `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body p-4">
          <div class="flex items-center justify-between"><h3 class="font-bold">${escapeHtml(player.username)}</h3><span class="badge badge-success badge-sm">Online</span></div>
          <p class="text-sm opacity-70">Learning points: ${player.lifetime_learning_points} · Wins: ${player.wins}</p>
          <button class="btn btn-warning btn-sm mt-2 challenge-player" data-id="${player.id}">Challenge</button>
        </div>
      </div>`).join("") : "<p class='opacity-70'>No other players online. Open another browser window to test 1v1.</p>";
    container.querySelectorAll(".challenge-player").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const challenge = await request("/api/challenges", {
            method: "POST",
            body: JSON.stringify({ opponent_id: Number(button.dataset.id), allowed_letters: "AEIOURSTLND" }),
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
