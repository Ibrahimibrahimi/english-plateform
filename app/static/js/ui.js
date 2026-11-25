import { reveal, runTransition, settle, slideIn } from "./motion.js";

const $ = (id) => document.getElementById(id);

export function toast(message, type = "info") {
  const container = $("toasts");
  if (!container) return;
  const safeType = ["info", "success", "warning", "error"].includes(type) ? type : "info";
  const element = document.createElement("div");
  element.className = `alert alert-${safeType} shadow-lg`;
  element.textContent = message;
  container.appendChild(element);
  slideIn(element);
  setTimeout(() => element.remove(), 3800);
}

const year = $("year");
if (year) year.textContent = new Date().getFullYear();

const themeToggle = $("theme-toggle");
if (themeToggle) {
  themeToggle.checked = document.documentElement.dataset.theme === "dark";
  try {
    const saved = localStorage.getItem("theme");
    const theme = saved === "dark" || saved === "arena" ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
    themeToggle.checked = theme === "dark";
  } catch (error) {
    toast("Theme preferences are unavailable", "warning");
  }
  themeToggle.addEventListener("change", () => {
    const theme = themeToggle.checked ? "dark" : "light";
    runTransition(() => document.documentElement.setAttribute("data-theme", theme));
    try {
      localStorage.setItem("theme", theme);
    } catch (error) {
      toast("Theme could not be saved", "warning");
    }
  });
}

const path = location.pathname.replace(/\/+$/, "") || "/";
document.querySelectorAll("[data-nav]").forEach((link) => {
  const href = link.getAttribute("href").replace(/\/+$/, "") || "/";
  const active = href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
  link.classList.toggle("active", active);
  if (active) link.setAttribute("aria-current", "page");
  else link.removeAttribute("aria-current");
});

reveal("[data-stagger] > *");

const drawer = $("menu-drawer");
if (drawer) {
  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea")) return;
    if (event.key.toLowerCase() === "m") drawer.checked = !drawer.checked;
    if (event.key === "Escape") drawer.checked = false;
  });
}

const howtoModal = $("howto-modal");
if (howtoModal) {
  document.querySelectorAll("#howto-btn, [data-open-howto]").forEach((button) => {
    button.addEventListener("click", () => {
      howtoModal.showModal();
      settle(howtoModal.querySelector(".modal-box"));
    });
  });
}

const logoutButton = $("logout-btn");
if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    const { request } = await import("./api.js");
    try {
      await request("/api/auth/logout", { method: "POST" });
      location.href = "/";
    } catch (error) {
      toast(error.message, "error");
    }
  });
}

const userId = document.body?.dataset.userId;
if (userId) {
  const { request, escapeHtml } = await import("./api.js");
  const countEl = $("notification-count");
  const listEl = $("notification-list");
  const friendCountEl = $("friend-request-count");

  const renderFriendBadge = async () => {
    if (!friendCountEl) return;
    try {
      const data = await request("/api/friends/count");
      friendCountEl.textContent = data.count;
      friendCountEl.classList.toggle("hidden", !data.count);
    } catch (error) {
      toast(error.message, "error");
    }
  };

  const renderNotifications = async () => {
    try {
      const data = await request("/api/notifications");
      if (countEl) {
        countEl.textContent = data.unread_count;
        countEl.classList.toggle("hidden", !data.unread_count);
      }
      if (listEl) {
        listEl.innerHTML = `<li class="menu-title flex items-center justify-between">Notifications<button id="notif-read-all" class="btn btn-ghost btn-xs">Mark all read</button></li>` +
          (data.items.length
            ? data.items.map((item) => `
              <li>
                <a href="${escapeHtml(item.link || "#")}" data-id="${item.id}" class="notification-item ${item.read ? "opacity-60" : "font-semibold"}">
                  <span>${escapeHtml(item.message)}</span>
                </a>
              </li>`).join("")
            : `<li><span class="opacity-60 text-sm">No notifications yet.</span></li>`);
        listEl.querySelectorAll(".notification-item").forEach((link) => {
          link.addEventListener("click", () => {
            request(`/api/notifications/${link.dataset.id}/read`, { method: "POST", body: JSON.stringify({}) }).catch(() => {});
          });
        });
        listEl.querySelector("#notif-read-all")?.addEventListener("click", async (event) => {
          event.preventDefault();
          try {
            await request("/api/notifications/read", { method: "POST", body: JSON.stringify({}) });
            renderNotifications();
          } catch (error) {
            toast(error.message, "error");
          }
        });
      }
    } catch (error) {
      toast(error.message, "error");
    }
  };

  renderNotifications();
  renderFriendBadge();

  const scheme = location.protocol === "https:" ? "wss" : "ws";
  let notificationSocket = null;
  let pingTimer = null;
  const connectNotifications = () => {
    notificationSocket = new WebSocket(`${scheme}://${location.host}/ws/presence`);
    notificationSocket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (error) {
        return;
      }
      if (message.type === "notification") {
        toast(message.payload.message, "warning");
        renderNotifications();
        renderFriendBadge();
      }
    });
    notificationSocket.addEventListener("close", () => {
      clearInterval(pingTimer);
      if (document.body?.dataset.userId) {
        setTimeout(connectNotifications, 3000);
      }
    });
  };
  connectNotifications();
  pingTimer = setInterval(() => {
    if (notificationSocket?.readyState === WebSocket.OPEN) {
      notificationSocket.send(JSON.stringify({ type: "ping" }));
    }
  }, 20000);
}
