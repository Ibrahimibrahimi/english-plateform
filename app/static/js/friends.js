import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

function card(user, actions, extra = "") {
  return `
    <div class="card bg-base-100 border border-base-300">
      <div class="card-body p-4">
        <div class="flex items-center gap-3">
          ${avatarHtml(user.avatar, user.username)}
          <div>
            <h3 class="font-bold">${escapeHtml(user.username)}</h3>
            <p class="text-sm opacity-70">${extra}</p>
          </div>
        </div>
        <div class="flex flex-wrap gap-2 mt-2">${actions}<a class="btn btn-ghost btn-sm" href="${escapeHtml(user.profile_url)}">Profile</a></div>
      </div>
    </div>`;
}

const incoming = document.getElementById("incoming-requests");
const outgoing = document.getElementById("outgoing-requests");
const friends = document.getElementById("friends-list");
if (incoming && outgoing && friends) {
  try {
    const data = await request("/api/friends");
    const count = document.getElementById("incoming-count");
    if (count) count.textContent = data.incoming.length;

    incoming.innerHTML = data.incoming.length
      ? data.incoming.map((row) => card(
          row.user,
          `<button class="btn btn-warning btn-sm friend-accept" data-id="${row.id}">Accept</button>
           <button class="btn btn-ghost btn-sm friend-decline" data-id="${row.id}">Decline</button>`,
          "Wants to be friends",
        )).join("")
      : "<p class='opacity-70'>No incoming requests.</p>";

    outgoing.innerHTML = data.outgoing.length
      ? data.outgoing.map((row) => card(row.user, "", "Request sent")).join("")
      : "<p class='opacity-70'>No sent requests.</p>";

    friends.innerHTML = data.friends.length
      ? data.friends.map((user) => card(
          user,
          `<button class="btn btn-ghost btn-sm friend-remove" data-id="${user.id}">Remove</button>`,
          `${user.wins} wins · ${user.lifetime_learning_points} pts`,
        )).join("")
      : "<p class='opacity-70'>You have no friends yet. Visit the players list to add some.</p>";

    const act = async (selector, path, success) => {
      document.querySelectorAll(selector).forEach((button) => {
        button.addEventListener("click", async () => {
          try {
            await request(path(button.dataset.id), { method: "POST", body: JSON.stringify({}) });
            toast(success, "success");
            location.reload();
          } catch (error) {
            toast(error.message, "error");
          }
        });
      });
    };
    await act(".friend-accept", (id) => `/api/friends/requests/${id}/accept`, "Friend request accepted");
    await act(".friend-decline", (id) => `/api/friends/requests/${id}/decline`, "Friend request declined");

    document.querySelectorAll(".friend-remove").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await request(`/api/friends/${button.dataset.id}`, { method: "DELETE" });
          toast("Friend removed", "success");
          location.reload();
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  } catch (error) {
    incoming.innerHTML = `<div class="alert alert-error">Log in to manage friends: ${escapeHtml(error.message)}</div>`;
  }
}
