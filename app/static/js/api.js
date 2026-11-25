export async function request(path, options = {}) {
  const headers = options.body instanceof FormData
    ? { ...(options.headers || {}) }
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }
  if (!response.ok) {
    throw new Error((data && data.detail) || `Request failed (${response.status})`);
  }
  return data;
}

export function connectMatch(matchId, handlers = {}) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${location.host}/ws/match/${matchId}`);
  socket.addEventListener("message", (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    if (handlers.onMessage) handlers.onMessage(message);
  });
  socket.addEventListener("close", () => {
    if (handlers.onClose) handlers.onClose();
  });
  return socket;
}

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

export function avatarHtml(avatar, label, size = "w-10") {
  const inner = avatar?.image_url
    ? `<img src="${escapeHtml(avatar.image_url)}" alt="${escapeHtml(label)} avatar" class="h-full w-full object-cover" />`
    : `<span style="background:${escapeHtml(avatar?.color || "#f59e0b")}">${escapeHtml(avatar?.emoji || "🎮")}</span>`;
  return `<div class="avatar avatar-placeholder"><div class="${size} rounded-full overflow-hidden flex items-center justify-center text-xl">${inner}</div></div>`;
}
