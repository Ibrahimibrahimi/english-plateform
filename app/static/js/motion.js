const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

const Motion = globalThis.Motion || {};
const animate = Motion.animate || (() => {});
const stagger = Motion.stagger || (value => value);

export function prefersReducedMotion() {
  return reduced.matches;
}

export function runTransition(update) {
  if (prefersReducedMotion() || typeof document.startViewTransition !== "function") {
    update();
    return;
  }
  document.startViewTransition(update);
}

export function reveal(targets, options = {}) {
  if (prefersReducedMotion()) return;
  const elements = typeof targets === "string"
    ? document.querySelectorAll(targets)
    : targets instanceof Element ? [targets] : Array.from(targets || []);
  if (!elements.length) return;
  animate(elements, {
    opacity: [0, 1],
    y: [12, 0],
    duration: 0.45,
    ease: "easeOut",
    delay: stagger(0.045),
    ...options,
  });
}

export function slideIn(element, options = {}) {
  if (prefersReducedMotion() || !element) return;
  animate(element, {
    opacity: [0, 1],
    x: [24, 0],
    duration: 0.28,
    ease: "easeOut",
    ...options,
  });
}

export function pop(element, options = {}) {
  if (prefersReducedMotion() || !element) return;
  animate(element, {
    scale: [1, 1.08, 1],
    duration: 0.34,
    ease: "easeOut",
    ...options,
  });
}

export function settle(element, options = {}) {
  if (prefersReducedMotion() || !element) return;
  animate(element, {
    opacity: [0, 1],
    scale: [0.96, 1],
    y: [10, 0],
    duration: 0.32,
    ease: "easeOut",
    ...options,
  });
}
