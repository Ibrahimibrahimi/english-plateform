import { avatarHtml, escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const settings = await request("/api/config");
const skillText = (raw) => {
  const codes = (raw || "").split(",").filter(Boolean);
  if (!codes.length) return "All";
  return codes.map((code) => {
    const skill = settings.skills.find((item) => item.code === code);
    return skill ? `${skill.icon || "✨"} ${skill.label}` : code;
  }).join(", ");
};

const container = document.getElementById("challenge-list");
if (container) {
  try {
    const challenges = await request("/api/challenges");
    container.innerHTML = challenges.length ? challenges.map((challenge) => `
      <div class="card bg-base-100 border border-base-300">
        <div class="card-body p-4 gap-2">
          <div class="flex items-center gap-3">
            ${avatarHtml(challenge.creator.avatar, challenge.creator.username, "w-12 text-2xl")}
            <div class="min-w-0">
              <h2 class="font-bold truncate">${escapeHtml(challenge.creator.username)}</h2>
              <p class="text-xs opacity-70">
                ${challenge.for_you ? "<span class='badge badge-warning badge-sm'>For you</span>" : "Open to anyone"}
                · ${escapeHtml(challenge.allowed_letters)}
              </p>
            </div>
          </div>
          <p class="text-xs opacity-70">Skills: ${escapeHtml(skillText(challenge.skills))}</p>
          <p class="text-xs opacity-70">
            ${challenge.creator.lifetime_learning_points} points · ${challenge.creator.wins} wins
          </p>
          <div class="card-actions mt-2">
            <button class="btn btn-warning btn-sm join-challenge" data-key="${escapeHtml(challenge.key)}">Join challenge</button>
            <a class="btn btn-ghost btn-sm" href="${escapeHtml(challenge.creator.profile_url)}">Profile</a>
          </div>
        </div>
      </div>`).join("") : "<div class='alert'>No open challenges right now. Create one and share the link!</div>";
    container.querySelectorAll(".join-challenge").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const match = await request(`/api/challenges/${button.dataset.key}/join`, { method: "POST", body: JSON.stringify({}) });
          location.href = `/playing/${match.id}`;
        } catch (error) {
          toast(error.message, "error");
        }
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
  }
}
