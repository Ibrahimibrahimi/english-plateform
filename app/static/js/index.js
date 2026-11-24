    /* ---------- helpers ---------- */
    const $ = (id) => document.getElementById(id);
    document.getElementById("year").textContent = new Date().getFullYear();

    function toast(message, type = "info") {
      const el = document.createElement("div");
      el.className = `alert alert-${type} shadow`;
      el.innerHTML = `<span>${message}</span>`;
      $("toasts").appendChild(el);
      setTimeout(() => el.remove(), 2500);
    }

    /* ---------- theme (remembered) ---------- */
    const themeToggle = $("theme-toggle");
    try {
      const saved = localStorage.getItem("theme");
      if (saved) {
        document.documentElement.setAttribute("data-theme", saved);
        themeToggle.checked = saved === "dark";
      }
    } catch (e) {}
    themeToggle.addEventListener("change", () => {
      const theme = themeToggle.checked ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", theme);
      try { localStorage.setItem("theme", theme); } catch (e) {}
    });

    /* ---------- menu: keyboard shortcut + close on Esc ---------- */
    const drawer = $("menu-drawer");
    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, textarea")) return;
      if (e.key.toLowerCase() === "m") drawer.checked = !drawer.checked;
      if (e.key === "Escape") drawer.checked = false;
    });

    /* mark the current page as active in the menu */
    const current = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll("#side-menu a").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("href") === current);
    });

    /* ---------- how to play modal ---------- */
    $("btn-howto").addEventListener("click", () => $("howto-modal").showModal());

    /* ---------- 1 vs 1 demo ---------- */
    const TOTAL_ROUNDS = 5;
    const MAX_PER_ROUND = 30;
    const MAX_TOTAL = TOTAL_ROUNDS * MAX_PER_ROUND;

    let round = 0;
    let scores = { p1: 0, p2: 0 };

    const steps = [...document.querySelectorAll("#rounds-steps .step")];
    const btnRound = $("btn-round");
    const btnReset = $("btn-reset");

    function animateNumber(el, from, to, duration = 500) {
      const start = performance.now();
      function tick(now) {
        const t = Math.min((now - start) / duration, 1);
        el.textContent = Math.round(from + (to - from) * t);
        if (t < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
      el.classList.remove("score-pop");
      void el.offsetWidth; // restart animation
      el.classList.add("score-pop");
    }

    function randomPoints() {
      return Math.floor(Math.random() * (MAX_PER_ROUND + 1));
    }

    function playRound() {
      if (round >= TOTAL_ROUNDS) return;

      const gain1 = randomPoints();
      const gain2 = randomPoints();
      const old = { ...scores };
      scores.p1 += gain1;
      scores.p2 += gain2;

      animateNumber($("score-p1"), old.p1, scores.p1);
      animateNumber($("score-p2"), old.p2, scores.p2);
      $("bar-p1").value = (scores.p1 / MAX_TOTAL) * 100;
      $("bar-p2").value = (scores.p2 / MAX_TOTAL) * 100;

      steps[round].classList.add("step-warning");
      round++;
      toast(`Round ${round}: You +${gain1} · Rival +${gain2}`);

      btnReset.disabled = false;
      btnRound.textContent = round < TOTAL_ROUNDS ? `Next round (${round + 1}/${TOTAL_ROUNDS})` : "Match finished";

      if (round === TOTAL_ROUNDS) {
        btnRound.disabled = true;
        showResult();
      }
    }

    function showResult() {
      const box = $("result");
      box.classList.remove("hidden");
      $("card-p1").classList.remove("border-warning", "border-2");
      $("card-p2").classList.remove("border-warning", "border-2");

      if (scores.p1 === scores.p2) {
        box.innerHTML = `<div class="alert alert-info justify-center font-bold">It's a tie! Play a sudden-death round in the real game.</div>`;
        return;
      }
      const youWin = scores.p1 > scores.p2;
      box.innerHTML = youWin
        ? `<div class="alert alert-success justify-center font-bold">🏆 You win with ${scores.p1} points vs ${scores.p2}!</div>`
        : `<div class="alert alert-error justify-center font-bold">The rival wins with ${scores.p2} points vs ${scores.p1}. Try again!</div>`;
      $(youWin ? "card-p1" : "card-p2").classList.add("border-warning", "border-2");
    }

    function resetDemo() {
      round = 0;
      scores = { p1: 0, p2: 0 };
      $("score-p1").textContent = 0;
      $("score-p2").textContent = 0;
      $("bar-p1").value = 0;
      $("bar-p2").value = 0;
      steps.forEach((s) => s.classList.remove("step-warning"));
      $("result").classList.add("hidden");
      $("card-p1").classList.remove("border-warning", "border-2");
      $("card-p2").classList.remove("border-warning", "border-2");
      btnRound.disabled = false;
      btnRound.textContent = "Try a round";
      btnReset.disabled = true;
    }

    btnRound.addEventListener("click", playRound);
    btnReset.addEventListener("click", resetDemo);

