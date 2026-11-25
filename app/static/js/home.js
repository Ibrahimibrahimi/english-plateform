import { request } from "./api.js";

const count = document.getElementById("online-count");
const status = document.getElementById("online-status");
try {
  const players = await request("/api/players/online");
  if (count) count.textContent = String(players.length + 1);
  if (status) status.textContent = "Players online";
} catch (error) {
  if (count) count.textContent = "Live";
  if (status) status.textContent = "Ready when you are";
}
