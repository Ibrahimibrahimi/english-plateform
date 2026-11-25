import { request } from "./api.js";
import { toast } from "./ui.js";

const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(loginForm);
    try {
      await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      location.reload();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

const signupForm = document.getElementById("signup-form");
if (signupForm) {
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(signupForm);
    try {
      await request("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      location.reload();
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

const usernameForm = document.getElementById("username-form");
if (usernameForm) {
  usernameForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await request("/api/me", {
        method: "PATCH",
        body: JSON.stringify({ username: document.getElementById("new-username").value }),
      });
      toast("Username updated", "success");
      location.reload();
    } catch (error) {
      toast(error.message, "error");
    }
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
          option.classList.toggle("border-warning", option === button);
          option.classList.toggle("border-transparent", option !== button);
        });
        const preview = document.getElementById("profile-avatar");
        if (preview) {
          preview.textContent = choice.textContent;
          preview.style.background = choice.style.background;
        }
        const navAvatar = document.getElementById("avatar-initials");
        if (navAvatar) {
          navAvatar.textContent = choice.textContent;
          navAvatar.parentElement.style.background = choice.style.background;
        }
        document.getElementById("avatar-feedback").textContent = "Profile picture saved.";
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
    historyList.innerHTML = history.length ? history.map((match) => `<div class="flex justify-between border-b border-base-300 py-2"><span>#${match.id} · ${match.mode}</span><span class="${match.won ? "text-success" : "text-error"}">${match.won ? "Won" : "Lost"} · ${match.points} pts</span></div>`).join("") : "<p class='opacity-70'>No matches yet.</p>";
    const canvas = document.getElementById("progress-chart");
    if (canvas && history.length) {
      const ctx = canvas.getContext("2d");
      const points = history.slice().reverse().map((match) => match.points);
      const max = Math.max(...points, 10);
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 3;
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
    historyList.textContent = error.message;
  }
}
