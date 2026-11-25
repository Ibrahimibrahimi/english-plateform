import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

function friendAction(player) {
  if (player.friend_status === "self") return "";
  if (player.friend_status === "friends") return "<span class='badge badge-success badge-sm'>Friends</span>";
  if (player.friend_status === "incoming") return "<a class='btn btn-warning btn-sm' href='/friends'>Accept request</a>";
  if (player.friend_status === "outgoing") return "<span class='badge badge-outline badge-sm'>Request sent</span>";
  return `<button class="btn btn-outline btn-sm add-friend" data-id="${player.id}">Add friend</button>`;
}

const container = document.getElementById("online-players");
if (container) {
  try {
    const players = await request("/api/players/online");
    container.innerHTML = players.length ? players.map((player) => `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              ${avatarHtml(player.avatar, player.username)}
              <h3 class="font-bold">${escapeHtml(player.username)}</h3>
            </div>
            <span class="badge badge-success badge-sm">Online</span>
          </div>
          <p class="text-sm opacity-70">Learning points: ${player.lifetime_learning_points} · Wins: ${player.wins}</p>
          <div class="flex flex-wrap gap-2 mt-2">
            <button class="btn btn-warning btn-sm challenge-player" data-id="${player.id}">Challenge</button>
            ${friendAction(player)}
            <a class="btn btn-ghost btn-sm" href="${escapeHtml(player.profile_url)}">Profile</a>
          </div>
        </div>
      </div>`).join("") : "<p class='opacity-70'>No other players online. Open another browser window to test 1v1.</p>";
    container.querySelectorAll(".add-friend").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await request("/api/friends/requests", {
            method: "POST",
            body: JSON.stringify({ user_id: Number(button.dataset.id) }),
          });
          toast("Friend request sent", "success");
          button.outerHTML = "<span class='badge badge-outline badge-sm'>Request sent</span>";
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
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
