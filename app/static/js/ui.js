const $ = (id) => document.getElementById(id);

export function toast(message, type = "info") {
  const container = $("toasts");
  if (!container) return;
  const element = document.createElement("div");
  element.className = `alert alert-${type} shadow`;
  element.textContent = message;
  container.appendChild(element);
  setTimeout(() => element.remove(), 3500);
}

const year = $("year");
if (year) year.textContent = new Date().getFullYear();

const themeToggle = $("theme-toggle");
if (themeToggle) {
  try {
    const saved = localStorage.getItem("theme");
    if (saved) {
      document.documentElement.setAttribute("data-theme", saved);
      themeToggle.checked = saved === "dark";
    }
  } catch (error) {
    toast("Theme preferences are unavailable", "warning");
  }
  themeToggle.addEventListener("change", () => {
    const theme = themeToggle.checked ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (error) {
      toast("Theme could not be saved", "warning");
    }
  });
}

const drawer = $("menu-drawer");
if (drawer) {
  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea")) return;
    if (event.key.toLowerCase() === "m") drawer.checked = !drawer.checked;
    if (event.key === "Escape") drawer.checked = false;
  });
  document.querySelectorAll("#side-menu a").forEach((link) => {
    link.classList.toggle("active", link.getAttribute("href") === location.pathname);
  });
}

const howtoButton = $("howto-btn");
const howtoModal = $("howto-modal");
if (howtoModal) {
  document.querySelectorAll("#howto-btn, [data-open-howto]").forEach((button) => {
    button.addEventListener("click", () => howtoModal.showModal());
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
