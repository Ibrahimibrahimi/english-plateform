import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const meta = document.getElementById("player-meta");
if (meta) {
  const container = meta.firstElementChild;
  try {
    const player = await request(`/api/players/${meta.dataset.id}`);
    const avatar = player.avatar;
    const friendAction = () => {
      if (player.friend_status === "self") return "<a class='btn btn-outline btn-sm mt-4' href='/profile'>Edit your profile</a>";
      if (player.friend_status === "friends") return "<span class='badge badge-success badge-sm mt-4'>Friends</span>";
      if (player.friend_status === "incoming") return "<a class='btn btn-primary btn-sm mt-4' href='/friends'>Accept friend request</a>";
      if (player.friend_status === "outgoing") return "<span class='badge badge-outline badge-sm mt-4'>Friend request sent</span>";
      return "<button class='btn btn-outline btn-sm mt-4 add-friend'>Add friend</button>";
    };
    meta.innerHTML = `
      <section class="panel panel-pad flex flex-col items-center gap-4 text-center">
        ${avatarHtml(avatar, player.username, "w-28 text-5xl ring-4 ring-primary/40")}
        <div>
          <h2 class="font-display text-3xl font-bold">${escapeHtml(player.username)}</h2>
          <p class="text-sm opacity-70">${escapeHtml(avatar.label)} avatar</p>
        </div>
        <div class="grid w-full gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div class="stat-tile"><span>Learning points</span><strong class="text-accent">${player.lifetime_learning_points}</strong></div>
          <div class="stat-tile"><span>Wins</span><strong class="text-success">${player.wins}</strong></div>
          <div class="stat-tile"><span>Losses</span><strong class="text-error">${player.losses}</strong></div>
          <div class="stat-tile"><span>Tournaments</span><strong>${player.tournaments_played}</strong></div>
        </div>
        <div class="flex flex-wrap justify-center gap-2">
          ${friendAction()}
          <a href="/players" class="btn btn-ghost btn-sm">Back to players</a>
        </div>
      </section>`;
    reveal(meta.children);
    meta.querySelector(".add-friend")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await request("/api/friends/requests", {
          method: "POST",
          body: JSON.stringify({ user_id: player.id }),
        });
        toast("Friend request sent", "success");
        button.outerHTML = "<span class='badge badge-outline badge-sm mt-4'>Friend request sent</span>";
      } catch (error) {
        toast(error.message, "error");
        button.disabled = false;
      }
    });
  } catch (error) {
    container.className = "alert alert-error";
    container.textContent = error.message;
  }
}
