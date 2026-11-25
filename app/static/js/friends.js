import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const empty = (title, message) => `<div class="empty-state"><strong>${title}</strong><span class="text-sm">${message}</span></div>`;

function card(user, actions, extra = "") {
  return `
    <div class="panel panel-pad flex flex-col gap-3">
      <div class="flex items-center gap-3">
        ${avatarHtml(user.avatar, user.username, "w-12 text-2xl")}
        <div class="min-w-0">
          <h3 class="truncate font-display text-lg font-bold">${escapeHtml(user.username)}</h3>
          <p class="text-sm opacity-70">${extra}</p>
        </div>
      </div>
      <div class="mt-auto flex flex-wrap gap-2 pt-2">${actions}<a class="btn btn-ghost btn-sm" href="${escapeHtml(user.profile_url)}">Profile</a></div>
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
      : empty("No incoming requests", "New requests will appear here.");
    outgoing.innerHTML = data.outgoing.length
      ? data.outgoing.map((row) => card(row.user, "", "Request waiting")).join("")
      : empty("No sent requests", "Find players to add from the roster.");
    friends.innerHTML = data.friends.length
      ? data.friends.map((user) => card(
          user,
          `<button class="btn btn-ghost btn-sm friend-remove" data-id="${user.id}">Remove</button>`,
          `${user.wins} wins · ${user.lifetime_learning_points} pts`,
        )).join("")
      : empty("No friends yet", "Visit the players list to add some.");

    [incoming, outgoing, friends].forEach((container) => reveal(container.children));

    const act = (selector, path, success) => {
      document.querySelectorAll(selector).forEach((button) => {
        button.addEventListener("click", async () => {
          button.disabled = true;
          try {
            await request(path(button.dataset.id), { method: "POST", body: JSON.stringify({}) });
            toast(success, "success");
            location.reload();
          } catch (error) {
            toast(error.message, "error");
            button.disabled = false;
          }
        });
      });
    };
    act(".friend-accept", (id) => `/api/friends/requests/${id}/accept`, "Friend request accepted");
    act(".friend-decline", (id) => `/api/friends/requests/${id}/decline`, "Friend request declined");

    document.querySelectorAll(".friend-remove").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await request(`/api/friends/${button.dataset.id}`, { method: "DELETE" });
          toast("Friend removed", "success");
          location.reload();
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    const message = `<div class="alert alert-error">Log in to manage friends: ${escapeHtml(error.message)}</div>`;
    incoming.innerHTML = message;
    outgoing.innerHTML = "";
    friends.innerHTML = "";
  }
}
