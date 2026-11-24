import { request } from "./api.js";

const body = document.getElementById("leaderboard-body");
if (body) {
  try {
    const rows = await request("/api/leaderboard");
    body.innerHTML = rows.map((row) => `<tr><td>${row.rank}</td><td>${row.username}</td><td>${row.points}</td><td>${row.wins}</td></tr>`).join("") || "<tr><td colspan='4' class='text-center'>No players yet.</td></tr>";
  } catch (error) {
    body.innerHTML = `<tr><td colspan="4" class="text-error">${error.message}</td></tr>`;
  }
}
