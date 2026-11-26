import { avatarHtml, escapeHtml, request } from "./api.js";
import { reveal } from "./motion.js";

const podium = document.getElementById("medal-podium");
const body = document.getElementById("leaderboard-body");
const empty = "<div class='empty-state sm:col-span-3'><strong>No players yet</strong><span class='text-sm'>Be the first to earn points.</span></div>";

const medals = {
  1: { label: "1", color: "#c27803", ring: "ring-accent", badge: "badge-accent" },
  2: { label: "2", color: "#c0c8d1", ring: "ring-base-content/40", badge: "badge-ghost" },
  3: { label: "3", color: "#cd7f32", ring: "ring-error/50", badge: "badge-error" },
};

const avatarFor = (row, size) => avatarHtml(row.avatar, row.username, size);

try {
  const rows = await request("/api/leaderboard");

  if (podium) {
    const byRank = new Map(rows.filter((row) => row.medal).slice(0, 3).map((row) => [row.rank, row]));
    const winners = [2, 1, 3].map((rank) => byRank.get(rank)).filter(Boolean);
    podium.innerHTML = winners.length
      ? winners.map((row) => {
          const medal = medals[row.rank];
          const first = row.rank === 1;
          return `
            <a href="${escapeHtml(row.profile_url)}" class="panel panel-pad flex flex-col items-center gap-2 text-center ring-2 transition hover:-translate-y-1 ${medal.ring} ${first ? "podium-first" : ""}">
              <span class="badge ${medal.badge} badge-lg font-display">${medal.label}</span>
              ${avatarFor(row, first ? "w-28 text-5xl" : "w-24 text-4xl")}
              <h3 class="font-display text-lg font-bold">${escapeHtml(row.username)}</h3>
              <p class="text-3xl font-extrabold" style="color:${medal.color}">${row.points}</p>
              <p class="text-xs uppercase tracking-wider opacity-60">Learning points</p>
              <p class="text-sm opacity-70">${row.wins} wins · ${row.losses} losses</p>
              <span class="badge badge-outline badge-sm">View profile</span>
            </a>`;
        }).join("")
      : empty;
    reveal(podium.children);
  }

  if (body) {
    body.innerHTML = rows.length
      ? rows.map((row) => `
          <tr class="${row.medal ? "bg-accent/10" : ""}">
            <th>${row.rank}</th>
            <td><div class="flex items-center gap-3">${avatarFor(row, "w-14 text-2xl")}<span class="font-semibold">${escapeHtml(row.username)}</span></div></td>
            <td class="font-extrabold text-accent">${row.points}</td>
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
