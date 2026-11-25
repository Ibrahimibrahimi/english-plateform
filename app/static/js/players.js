import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const empty = "<div class='empty-state'><strong>No players online</strong><span class='text-sm'>Open another browser window to test 1v1.</span></div>";

function friendAction(player) {
  if (player.friend_status === "self") return "<span class='badge badge-ghost badge-sm'>You</span>";
  if (player.friend_status === "friends") return "<span class='badge badge-success badge-sm'>Friends</span>";
  if (player.friend_status === "incoming") return "<a class='btn btn-primary btn-sm' href='/friends'>Accept request</a>";
  if (player.friend_status === "outgoing") return "<span class='badge badge-outline badge-sm'>Request sent</span>";
  return `<button class="btn btn-outline btn-sm add-friend" data-id="${player.id}">Add friend</button>`;
}

const container = document.getElementById("online-players");
if (container) {
  try {
    const players = await request("/api/players/online");
    container.innerHTML = players.length ? players.map((player) => `
      <div class="panel panel-pad flex flex-col gap-3">
        <div class="flex items-center justify-between gap-2">
          <div class="flex min-w-0 items-center gap-2">
            ${avatarHtml(player.avatar, player.username, "w-12 text-2xl")}
            <h3 class="truncate font-display text-lg font-bold">${escapeHtml(player.username)}</h3>
          </div>
          <span class="badge badge-success badge-sm">Online</span>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="stat-tile"><span>Points</span><strong>${player.lifetime_learning_points}</strong></div>
          <div class="stat-tile"><span>Wins</span><strong>${player.wins}</strong></div>
        </div>
        <div class="mt-auto flex flex-wrap gap-2 pt-2">
          <button class="btn btn-primary btn-sm challenge-player gap-2" data-id="${player.id}">Challenge</button>
          ${friendAction(player)}
          <a class="btn btn-ghost btn-sm" href="${escapeHtml(player.profile_url)}">Profile</a>
        </div>
      </div>`).join("") : empty;
    reveal(container.children);
    container.querySelectorAll(".add-friend").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await request("/api/friends/requests", {
            method: "POST",
            body: JSON.stringify({ user_id: Number(button.dataset.id) }),
          });
          toast("Friend request sent", "success");
          button.outerHTML = "<span class='badge badge-outline badge-sm'>Request sent</span>";
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });
    container.querySelectorAll(".challenge-player").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
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
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">Log in to see online players: ${escapeHtml(error.message)}</div>`;
  }
}
