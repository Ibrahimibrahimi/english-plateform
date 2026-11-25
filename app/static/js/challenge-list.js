import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";
import { reveal } from "./motion.js";

const settings = await request("/api/config");
const skillText = (raw) => {
  const codes = (raw || "").split(",").filter(Boolean);
  if (!codes.length) return "All";
  return codes.map((code) => {
    const skill = settings.skills.find((item) => item.code === code);
    return skill ? `${skill.icon || "Skill"} ${skill.label}` : code;
  }).join(", ");
};

const empty = "<div class='empty-state'><strong>No open challenges</strong><span class='text-sm'>Create one and share the link with a friend.</span></div>";
const container = document.getElementById("challenge-list");
if (container) {
  try {
    const challenges = await request("/api/challenges");
    container.innerHTML = challenges.length ? challenges.map((challenge) => `
      <div class="panel panel-pad flex flex-col gap-3">
        <div class="flex items-center gap-3">
          ${avatarHtml(challenge.creator.avatar, challenge.creator.username, "w-12 text-2xl")}
          <div class="min-w-0">
            <h2 class="truncate font-display text-lg font-bold">${escapeHtml(challenge.creator.username)}</h2>
            <p class="text-xs opacity-70">${challenge.for_you ? "<span class='badge badge-warning badge-sm'>For you</span>" : "<span class='badge badge-ghost badge-sm'>Open</span>"} <span class="font-mono">${escapeHtml(challenge.allowed_letters)}</span></p>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-2 text-xs">
          <div class="stat-tile"><span>Skills</span><strong class="text-xs">${escapeHtml(skillText(challenge.skills))}</strong></div>
          <div class="stat-tile"><span>Record</span><strong class="text-xs">${challenge.creator.wins} wins</strong></div>
        </div>
        <div class="mt-auto flex flex-wrap gap-2 pt-2">
          <button class="btn btn-warning btn-sm join-challenge gap-2" data-key="${escapeHtml(challenge.key)}">Join challenge</button>
          <a class="btn btn-ghost btn-sm" href="${escapeHtml(challenge.creator.profile_url)}">Profile</a>
        </div>
      </div>`).join("") : empty;
    reveal(container.children);
    container.querySelectorAll(".join-challenge").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const match = await request(`/api/challenges/${button.dataset.key}/join`, { method: "POST", body: JSON.stringify({}) });
          location.href = `/playing/${match.id}`;
        } catch (error) {
          toast(error.message, "error");
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  }
}
