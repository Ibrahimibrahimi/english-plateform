import { escapeHtml } from "./api.js";
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

export function matchRequest({ id, message, link, createdAt, type, onRead } = {}) {
  const container = $("toasts");
  if (!container) return;
  const safeLink = typeof link === "string" && link.startsWith("/") && !link.startsWith("//") ? link : "";
  const title = type === "rematch.offered" ? "Rematch request" : "Match request";
  const fallback = type === "rematch.offered" ? "Your opponent wants a rematch." : "You received a match request.";
  const card = document.createElement("div");
  card.className = "match-request-card";
  const time = createdAt ? new Date(createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "now";
  card.innerHTML = `
    <div class="match-request-accent"></div>
    <div class="match-request-body">
      <div class="match-request-head">
        <span class="match-request-icon" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 17.5L3 6V3h3l11.5 11.5"/><path d="M13 19l6-6"/><path d="M16 16l4 4"/><path d="M19 21l2-2"/></svg>
        </span>
        <div class="match-request-copy">
          <p class="match-request-title"></p>
          <p class="match-request-message"></p>
        </div>
        <button type="button" class="match-request-close" aria-label="Dismiss notification">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="match-request-foot">
        <span class="match-request-time">${escapeHtml(time)}</span>
        <div class="match-request-actions">
          <button type="button" class="btn btn-ghost btn-xs match-request-dismiss">Later</button>
          ${safeLink ? `<a class="btn btn-primary btn-xs match-request-join" href="${escapeHtml(safeLink)}">View</a>` : ""}
        </div>
      </div>
    </div>`;
  card.querySelector(".match-request-title").textContent = title;
  card.querySelector(".match-request-message").textContent = message || fallback;

  let closed = false;
  let dismissTimer = null;
  const markRead = () => {
    if (!id) return Promise.resolve();
    return fetch(`/api/notifications/${id}/read`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }).then(() => onRead?.()).catch(() => {});
  };
  const close = (shouldMarkRead = true) => {
    if (closed) return;
    closed = true;
    if (dismissTimer) clearTimeout(dismissTimer);
    if (shouldMarkRead) markRead();
    card.classList.add("is-leaving");
    setTimeout(() => card.remove(), 220);
  };

  card.querySelector(".match-request-close").addEventListener("click", () => close(true));
  card.querySelector(".match-request-dismiss").addEventListener("click", () => close(true));
  card.querySelector(".match-request-join")?.addEventListener("click", () => close(true));
  card.addEventListener("mouseenter", () => { if (dismissTimer) clearTimeout(dismissTimer); });
  card.addEventListener("focusin", () => { if (dismissTimer) clearTimeout(dismissTimer); });
  card.addEventListener("mouseleave", () => { if (!closed) dismissTimer = setTimeout(() => close(false), 4000); });
  card.addEventListener("focusout", (event) => {
    if (!closed && !card.contains(event.relatedTarget)) dismissTimer = setTimeout(() => close(false), 4000);
  });

  container.appendChild(card);
  slideIn(card);
  dismissTimer = setTimeout(() => close(false), 12000);
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
        const payload = message.payload || {};
        if (payload.type === "challenge.received" || payload.type === "rematch.offered") {
          matchRequest({ ...payload, onRead: renderNotifications });
        } else {
          toast(payload.message, "warning");
        }
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
