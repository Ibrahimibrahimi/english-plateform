import { escapeHtml, request } from "./api.js";
import { toast } from "./ui.js";

const showError = (id, message) => {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = message;
  element.classList.remove("hidden");
};

const clearError = (id) => {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = "";
  element.classList.add("hidden");
};

const redirectPath = () => {
  const next = new URLSearchParams(location.search).get("next");
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/profile";
  return next;
};

const busy = async (button, task) => {
  if (!button) return task();
  button.disabled = true;
  button.classList.add("opacity-70");
  try {
    return await task();
  } finally {
    button.disabled = false;
    button.classList.remove("opacity-70");
  }
};

const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError("login-error");
    const form = new FormData(loginForm);
    await busy(loginForm.querySelector("button[type='submit']"), async () => {
      try {
        await request("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
        });
        location.href = redirectPath();
      } catch (error) {
        showError("login-error", error.message);
        toast(error.message, "error");
      }
    });
  });
}

const signupForm = document.getElementById("signup-form");
if (signupForm) {
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError("signup-error");
    const form = new FormData(signupForm);
    await busy(signupForm.querySelector("button[type='submit']"), async () => {
      try {
        await request("/api/auth/signup", {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            email: form.get("email"),
            password: form.get("password"),
          }),
        });
        location.href = redirectPath();
      } catch (error) {
        showError("signup-error", error.message);
        toast(error.message, "error");
      }
    });
  });
}

const usernameForm = document.getElementById("username-form");
if (usernameForm) {
  usernameForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const feedback = document.getElementById("username-feedback");
    await busy(usernameForm.querySelector("button[type='submit']"), async () => {
      try {
        const user = await request("/api/me", {
          method: "PATCH",
          body: JSON.stringify({ username: document.getElementById("new-username").value }),
        });
        document.getElementById("profile-name")?.replaceChildren(user.username);
        document.getElementById("account-username")?.replaceChildren(user.username);
        if (feedback) feedback.textContent = "Display name updated.";
        toast("Username updated", "success");
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
        toast(error.message, "error");
      }
    });
  });
}

const avatarPicker = document.getElementById("avatar-picker");
if (avatarPicker) {
  avatarPicker.querySelectorAll(".avatar-option").forEach((button) => {
    button.addEventListener("click", async () => {
      const choice = button.querySelector("span");
      try {
        await request("/api/me", {
          method: "PATCH",
          body: JSON.stringify({ avatar: button.dataset.key }),
        });
        avatarPicker.querySelectorAll(".avatar-option").forEach((option) => {
          option.classList.toggle("border-primary", option === button);
          option.classList.toggle("border-transparent", option !== button);
        });
        const preview = document.getElementById("profile-avatar");
        if (preview) {
          preview.replaceChildren(choice.textContent);
          preview.style.background = choice.style.background;
        }
        const navAvatar = document.getElementById("avatar-initials");
        if (navAvatar) {
          navAvatar.replaceChildren(choice.textContent);
          navAvatar.style.background = choice.style.background;
        }
        document.getElementById("avatar-feedback").textContent = "Profile picture saved.";
        toast("Profile picture updated", "success");
      } catch (error) {
        toast(error.message, "error");
      }
    });
  });
}

const avatarForm = document.getElementById("avatar-upload-form");
if (avatarForm) {
  avatarForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = document.getElementById("avatar-file").files[0];
    if (!file) return;
    const payload = new FormData();
    payload.append("image", file);
    await busy(avatarForm.querySelector("button[type='submit']"), async () => {
      try {
        const user = await request("/api/me/avatar", { method: "POST", body: payload });
        const image = `<img src="${escapeHtml(user.avatar.image_url)}" alt="Your avatar" class="h-full w-full object-cover" />`;
        const preview = document.getElementById("profile-avatar");
        if (preview) {
          preview.innerHTML = image;
          preview.style.background = "";
        }
        const navAvatar = document.getElementById("avatar-initials");
        if (navAvatar) {
          navAvatar.innerHTML = image;
          navAvatar.style.background = "";
        }
        avatarPicker?.querySelectorAll(".avatar-option").forEach((option) => {
          option.classList.remove("border-primary");
          option.classList.add("border-transparent");
        });
        document.getElementById("avatar-feedback").textContent = "Profile picture uploaded.";
        toast("Profile picture updated", "success");
      } catch (error) {
        toast(error.message, "error");
      }
    });
  });
}

const historyList = document.getElementById("history-list");
if (historyList) {
  try {
    const [stats, history] = await Promise.all([request("/api/me/statistics"), request("/api/me/history")]);
    document.getElementById("stat-points").textContent = stats.lifetime_learning_points;
    document.getElementById("stat-record").textContent = `${stats.wins} / ${stats.losses}`;
    document.getElementById("stat-tournaments").textContent = stats.tournaments_played;
    historyList.innerHTML = history.length
      ? `<div class="divide-y divide-base-300">${history.map((match) => `
          <div class="flex items-center justify-between gap-3 py-2">
            <span class="truncate">#${match.id} · ${escapeHtml(match.mode)}</span>
            <span class="badge ${match.won ? "badge-success" : "badge-error"} badge-sm shrink-0">${match.won ? "Won" : "Lost"} · ${match.points} pts</span>
          </div>`).join("")}</div>`
      : `<div class="empty-state"><strong>No matches yet</strong><span>Your first battle will appear here.</span></div>`;
    const canvas = document.getElementById("progress-chart");
    if (canvas && history.length) {
      const ctx = canvas.getContext("2d");
      const points = history.slice().reverse().map((match) => match.points);
      const max = Math.max(...points, 10);
      const primary = getComputedStyle(document.documentElement).getPropertyValue("--sb-primary").trim() || "#0f766e";
      ctx.strokeStyle = primary;
      ctx.lineWidth = 3;
      ctx.shadowBlur = 0;
      ctx.beginPath();
      points.forEach((point, index) => {
        const x = (index / Math.max(1, points.length - 1)) * (canvas.width - 20) + 10;
        const y = canvas.height - 20 - (point / max) * (canvas.height - 40);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
  } catch (error) {
    historyList.innerHTML = `<div class="empty-state"><strong>History unavailable</strong><span>${escapeHtml(error.message)}</span></div>`;
  }
}
