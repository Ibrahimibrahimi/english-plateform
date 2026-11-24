import { request } from "./api.js";

const badge = document.querySelector(".badge-warning.badge-outline");
try {
  const players = await request("/api/players/online");
  if (badge) badge.textContent = `${players.length + 1} players are online`;
} catch (error) {
  if (badge) badge.textContent = "Join a battle";
}
