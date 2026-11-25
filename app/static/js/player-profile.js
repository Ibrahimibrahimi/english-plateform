import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const meta = document.getElementById("player-meta");
if (meta) {
  const container = meta.firstElementChild;
  try {
    const player = await request(`/api/players/${meta.dataset.id}`);
    const avatar = player.avatar;
    const friendAction = () => {
      if (player.friend_status === "self") return "<a class='btn btn-outline btn-sm mt-4' href='/profile'>Edit your profile</a>";
      if (player.friend_status === "friends") return "<span class='badge badge-success badge-sm mt-4'>Friends</span>";
      if (player.friend_status === "incoming") return "<a class='btn btn-warning btn-sm mt-4' href='/friends'>Accept friend request</a>";
      if (player.friend_status === "outgoing") return "<span class='badge badge-outline badge-sm mt-4'>Friend request sent</span>";
      return `<button class="btn btn-outline btn-sm mt-4 add-friend">Add friend</button>`;
    };
    meta.innerHTML = `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body items-center text-center">
          ${avatarHtml(avatar, player.username, "w-28 text-5xl ring-4 ring-base-300")}
          <h1 class="card-title text-3xl mt-3">${escapeHtml(player.username)}</h1>
          <p class="opacity-70">${escapeHtml(avatar.label)} avatar</p>
          <div class="stats stats-vertical sm:stats-horizontal shadow mt-4 w-full">
            <div class="stat"><div class="stat-title">Learning points</div><div class="stat-value text-warning">${player.lifetime_learning_points}</div></div>
            <div class="stat"><div class="stat-title">Wins</div><div class="stat-value text-success">${player.wins}</div></div>
            <div class="stat"><div class="stat-title">Losses</div><div class="stat-value text-error">${player.losses}</div></div>
            <div class="stat"><div class="stat-title">Tournaments</div><div class="stat-value">${player.tournaments_played}</div></div>
          </div>
          <div class="flex flex-wrap justify-center gap-2 mt-4">
            ${friendAction()}
            <a href="/players" class="btn btn-outline btn-sm">Back to players</a>
          </div>
        </div>
      </div>`;
    meta.querySelector(".add-friend")?.addEventListener("click", async (event) => {
      try {
        await request("/api/friends/requests", {
          method: "POST",
          body: JSON.stringify({ user_id: player.id }),
        });
        toast("Friend request sent", "success");
        event.currentTarget.outerHTML = "<span class='badge badge-outline badge-sm mt-4'>Friend request sent</span>";
      } catch (error) {
        toast(error.message, "error");
      }
    });
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  }
}
