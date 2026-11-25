import { escapeHtml, request } from "./api.js";

const podium = document.getElementById("medal-podium");
const body = document.getElementById("leaderboard-body");

const medals = [
  { rank: 1, emoji: "🥇", color: "#f5c518", ring: "ring-warning" },
  { rank: 2, emoji: "🥈", color: "#c0c8d1", ring: "ring-base-content/40" },
  { rank: 3, emoji: "🥉", color: "#cd7f32", ring: "ring-error/50" },
];

const avatarHtml = (row, size = "w-10") => `
  <div class="avatar avatar-placeholder">
    <div class="${size} rounded-full text-xl flex items-center justify-center" style="background:${escapeHtml(row.avatar.color)}">${row.avatar.emoji}</div>
  </div>`;

try {
  const rows = await request("/api/leaderboard");

  if (podium) {
    const winners = rows.filter((row) => row.medal).slice(0, 3);
    podium.innerHTML = winners.length
      ? winners.map((row, index) => {
          const medal = medals[index];
          return `
            <a href="${escapeHtml(row.profile_url)}" class="card bg-base-100 border-2 border-base-300 hover:-translate-y-1 transition ${medal.ring} ring-2">
              <div class="card-body items-center text-center gap-2 py-6">
                <div class="text-4xl">${medal.emoji}</div>
                ${avatarHtml(row, "w-16")}
                <h3 class="card-title text-lg">${escapeHtml(row.username)}</h3>
                <p class="text-3xl font-extrabold" style="color:${medal.color}">${row.points}</p>
                <p class="text-xs opacity-60 uppercase tracking-wide">learning points</p>
                <p class="text-sm opacity-70">${row.wins} wins · ${row.losses} losses</p>
                <span class="badge badge-sm">View profile →</span>
              </div>
            </a>`;
        }).join("")
      : "<div class='alert sm:col-span-3'>No players yet. Be the first to earn points!</div>";
  }

  if (body) {
    body.innerHTML = rows.length
      ? rows.map((row) => `
          <tr class="${row.medal ? "bg-warning/10" : ""}">
            <th>${row.rank}${row.medal ? " " + medals[row.rank - 1].emoji : ""}</th>
            <td><div class="flex items-center gap-3">${avatarHtml(row)}<span class="font-semibold">${escapeHtml(row.username)}</span></div></td>
            <td class="font-extrabold text-warning">${row.points}</td>
            <td>${row.wins} W / ${row.losses} L</td>
            <td>${row.tournaments_played}</td>
            <td><a href="${escapeHtml(row.profile_url)}" class="btn btn-ghost btn-xs">Profile</a></td>
          </tr>`).join("")
      : "<tr><td colspan='6' class='text-center'>No players yet.</td></tr>";
  }
} catch (error) {
  const message = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  if (podium) podium.innerHTML = message;
  if (body) body.innerHTML = `<tr><td colspan="6">${message}</td></tr>`;
}
