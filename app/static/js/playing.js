import { request } from "./api.js";
import { toast } from "./ui.js";
import { settle } from "./motion.js";
import { createArenaFx } from "./arena-fx.js";

const meta = document.getElementById("match-meta");
if (meta) {
  const matchId = meta.dataset.matchId;
  const wordInput = document.getElementById("word-input");
  const connection = document.getElementById("connection");
  const roundLabel = document.getElementById("round-label");
  const timer = document.getElementById("timer");
  const result = document.getElementById("result");
  const resultKicker = document.getElementById("result-kicker");
  const resultTitle = document.getElementById("result-title");
  const resultMessage = document.getElementById("result-message");
  const resultScore = document.getElementById("result-score");
  const resultPrimary = document.getElementById("result-primary");
  const resultPrimaryLabel = document.getElementById("result-primary-label");
  const resultTournament = document.getElementById("result-tournament");
  const connectionBanner = document.getElementById("connection-banner");
  const connectionTitle = document.getElementById("connection-title");
  const connectionDetail = document.getElementById("connection-detail");
  const connectionRetry = document.getElementById("connection-retry");
  const connectionLogin = document.getElementById("connection-login");
  const connectionBack = document.getElementById("connection-back");
  const waitingPanel = document.getElementById("waiting-panel");
  const waitingTournament = document.getElementById("waiting-tournament");
  const waitingDetail = document.getElementById("waiting-detail");
  const controls = [
    document.getElementById("answer-form")?.querySelector("button"),
    wordInput,
    document.getElementById("skill-btn"),
    document.getElementById("health-btn"),
    document.getElementById("armor-btn"),
    document.getElementById("regen-skill-btn"),
  ].filter(Boolean);

  const fx = createArenaFx();
  const sideById = {};
  let myId = null;
  let socket = null;
  let ended = false;
  let retry = 0;
  let reconnectTimer = null;
  let startCountdownTimer = null;
  let isChallenge = false;
  let tournamentId = null;
  let finishedAtLoad = false;
  let rematchShown = false;
  let rematchRetries = 0;
  const rematchPanel = document.getElementById("rematch-panel");
  const rematchMessage = document.getElementById("rematch-message");
  const rematchButton = document.getElementById("rematch-btn");
  const rematchAccept = document.getElementById("rematch-accept-btn");
  const rematchDecline = document.getElementById("rematch-decline-btn");
  const rematchLink = document.getElementById("rematch-link");

  try {
    myId = (await request("/api/auth/me")).id;
  } catch (error) {
    toast("Log in to play this match", "error");
  }
  try {
    const snapshot = await request(`/api/matches/${matchId}`);
    isChallenge = snapshot.match.mode === "challenge";
    tournamentId = snapshot.match.tournament_id;
    finishedAtLoad = snapshot.match.status === "finished";
  } catch (error) {
    toast(error.message, "error");
  }

  const setConnectionBadge = (text, variant = "badge-ghost") => {
    if (!connection) return;
    connection.textContent = text;
    connection.className = `badge ${variant}`;
  };

  const setControlsEnabled = (enabled) => {
    for (const control of controls) control.disabled = !enabled;
  };

  const tournamentBackHref = () => (tournamentId ? `/tournament/${tournamentId}` : "/play");

  const showConnection = ({ title, detail, canRetry = false, needLogin = false, canGoBack = false }) => {
    if (!connectionBanner) return;
    connectionTitle.textContent = title;
    connectionDetail.textContent = detail;
    connectionRetry?.classList.toggle("hidden", !canRetry);
    connectionLogin?.classList.toggle("hidden", !needLogin);
    if (connectionBack) {
      connectionBack.href = tournamentBackHref();
      connectionBack.textContent = tournamentId ? "Back to tournament" : "Back to play";
      connectionBack.classList.toggle("hidden", !canGoBack);
    }
    connectionBanner.classList.remove("hidden");
  };

  const hideConnection = () => connectionBanner?.classList.add("hidden");

  const stopStartCountdown = () => {
    if (startCountdownTimer !== null) {
      clearInterval(startCountdownTimer);
      startCountdownTimer = null;
    }
  };

  const showWaitingPanel = () => {
    if (!waitingPanel) return;
    waitingPanel.classList.remove("hidden");
    if (waitingTournament) {
      waitingTournament.href = tournamentBackHref();
      waitingTournament.classList.toggle("hidden", !tournamentId);
    }
    if (waitingDetail) {
      waitingDetail.textContent = tournamentId
        ? "The match starts automatically when another player joins and connects. If you leave, you'll have a short grace period to reconnect."
        : "The match starts automatically when both players connect.";
    }
  };

  const hideWaitingPanel = () => waitingPanel?.classList.add("hidden");

  const showStartCountdown = (seconds) => {
    stopStartCountdown();
    hideWaitingPanel();
    let remaining = Math.max(1, Number(seconds) || 0);
    setConnectionBadge("Starting soon", "badge-accent");
    roundLabel.textContent = "Get ready";
    timer.textContent = `${remaining}s`;
    startCountdownTimer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        stopStartCountdown();
        timer.textContent = "0s";
        return;
      }
      timer.textContent = `${remaining}s`;
    }, 1000);
  };

  const renderResult = (payload) => {
    if (!result) return;
    const players = Object.entries(payload.players || {}).map(([id, player]) => ({ ...player, id: Number(id) }));
    const mine = players.find((player) => player.id === myId);
    const opponent = players.find((player) => player.id !== myId);
    const draw = payload.winner_id == null;
    const won = payload.winner_id === myId;
    result.className = `result-card ${draw ? "result-draw" : won ? "result-win" : "result-loss"}`;
    resultKicker.textContent = draw ? "Battle complete" : won ? "Match won" : "Battle complete";
    resultTitle.textContent = draw ? "Draw" : won ? "Victory" : "Defeat";
    resultMessage.textContent = draw
      ? "Both players finished level. The match ends in a draw."
      : won
        ? "You finished with the higher score."
        : "Your opponent held the lead. Try a longer word chain next round.";
    resultScore.textContent = mine && opponent ? `${mine.points} - ${opponent.points} points` : "";
    if (isChallenge) {
      resultPrimary.href = "/challenge/list";
      if (resultPrimaryLabel) resultPrimaryLabel.textContent = "New challenge";
    } else if (tournamentId) {
      resultPrimary.href = "/play-tournament";
      if (resultPrimaryLabel) resultPrimaryLabel.textContent = "Play tournament";
    } else {
      resultPrimary.href = "/play";
      if (resultPrimaryLabel) resultPrimaryLabel.textContent = "Play again";
    }
    resultTournament?.classList.toggle("hidden", !tournamentId);
    if (tournamentId && resultTournament) resultTournament.href = `/tournament/${tournamentId}`;
    settle(result);
  };

  const hideRematchActions = () => {
    [rematchButton, rematchAccept, rematchDecline, rematchLink].forEach((element) => {
      element?.classList.add("hidden");
    });
  };

  const refreshRematch = async () => {
    try {
      const data = await request(`/api/matches/${matchId}/rematch`);
      const offer = data.offer;
      hideRematchActions();
      if (!offer) {
        rematchMessage.textContent = "Challenge the same player again.";
        rematchButton.classList.remove("hidden");
        return;
      }
      if (offer.status === "accepted" && offer.url) {
        rematchMessage.textContent = "Rematch ready. Join when you are.";
        rematchLink.href = offer.url;
        rematchLink.classList.remove("hidden");
        return;
      }
      if (offer.status === "pending") {
        if (offer.can_accept) {
          rematchMessage.textContent = `${offer.from?.username || "Opponent"} wants a rematch.`;
          rematchAccept.classList.remove("hidden");
          rematchDecline.classList.remove("hidden");
        } else {
          rematchMessage.textContent = "Rematch request sent. Waiting for the other player.";
        }
        return;
      }
      rematchMessage.textContent = offer.status === "declined"
        ? "Rematch declined. You can request another."
        : "Rematch offer expired. You can request another.";
      rematchButton.classList.remove("hidden");
    } catch (error) {
      if (/not over yet/i.test(error.message) && rematchRetries < 10) {
        rematchRetries += 1;
        setTimeout(refreshRematch, 300);
        return;
      }
      toast(error.message, "error");
    }
  };

  const showRematch = () => {
    if (!isChallenge || rematchShown) return;
    rematchShown = true;
    rematchPanel?.classList.remove("hidden");
    refreshRematch();
  };

  rematchButton?.addEventListener("click", async () => {
    try {
      await request(`/api/matches/${matchId}/rematch`, { method: "POST", body: JSON.stringify({}) });
      toast("Rematch requested", "success");
      refreshRematch();
    } catch (error) {
      toast(error.message, "error");
    }
  });
  rematchAccept?.addEventListener("click", async () => {
    try {
      const data = await request(`/api/matches/${matchId}/rematch/accept`, { method: "POST", body: JSON.stringify({}) });
      toast("Rematch accepted", "success");
      if (data.url) location.href = data.url;
      else refreshRematch();
    } catch (error) {
      toast(error.message, "error");
    }
  });
  rematchDecline?.addEventListener("click", async () => {
    try {
      await request(`/api/matches/${matchId}/rematch/decline`, { method: "POST", body: JSON.stringify({}) });
      toast("Rematch declined", "info");
      refreshRematch();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  connectionRetry?.addEventListener("click", () => {
    if (socket && socket.readyState !== WebSocket.CLOSED) return;
    clearTimeout(reconnectTimer);
    hideConnection();
    connect();
  });

  if (finishedAtLoad) showRematch();

  const addLog = (text) => {
    const item = document.createElement("li");
    item.textContent = text;
    document.getElementById("event-log").prepend(item);
  };

  const renderLetters = (letters) => {
    const container = document.getElementById("letters");
    container.innerHTML = "";
    for (const letter of letters || "") {
      const tile = document.createElement("span");
      tile.className = "letter-tile badge badge-lg badge-outline";
      tile.textContent = letter;
      container.appendChild(tile);
    }
  };

  const renderPlayer = (player, side, me) => {
    document.getElementById(`name-${side}`).textContent = player.username + (me ? " (you)" : "");
    document.getElementById(`points-${side}`).textContent = player.points;
    document.getElementById(`health-text-${side}`).textContent = `${player.health}/${player.max_health}`;
    document.getElementById(`armor-text-${side}`).textContent = `${player.armor}/${player.max_armor}`;
    document.getElementById(`health-bar-${side}`).style.width = `${(player.health / Math.max(1, player.max_health)) * 100}%`;
    document.getElementById(`armor-bar-${side}`).style.width = `${(player.armor / Math.max(1, player.max_armor)) * 100}%`;
    document.getElementById(`attack-${side}`).textContent = player.attack;
    document.getElementById(`skill-${side}`).textContent = player.skill_label
      ? `${player.skill_icon || "•"} ${player.skill_label}`
      : "-";
    document.getElementById(`status-${side}`).textContent = player.connected ? (player.blocked ? "Blocked" : "") : "Disconnected";
    fx.sync(side, player);
  };

  const renderState = (payload) => {
    const players = Object.entries(payload.players).map(([id, player]) => ({ ...player, id: Number(id) }));
    const mine = players.find((player) => player.id === myId) || players[0];
    const opponent = players.find((player) => player.id !== mine?.id);
    if (mine) { sideById[mine.id] = "p1"; renderPlayer(mine, "p1", mine.id === myId); }
    if (opponent) { sideById[opponent.id] = "p2"; renderPlayer(opponent, "p2", false); }

    const round = payload.round_index + 1;
    if (payload.status === "waiting") {
      setControlsEnabled(false);
      if (payload.start_in > 0) {
        showStartCountdown(payload.start_in);
        return;
      }
      stopStartCountdown();
      setConnectionBadge("Waiting for opponent", "badge-accent");
      roundLabel.textContent = "Lobby";
      timer.textContent = "--";
      showWaitingPanel();
      return;
    }
    stopStartCountdown();
    hideWaitingPanel();
    if (payload.status === "finished") {
      setControlsEnabled(false);
      fx.end(payload.winner_id == null ? null : sideById[payload.winner_id]);
      setConnectionBadge("Match finished", "badge-success");
      timer.textContent = "0s";
      hideConnection();
      renderResult(payload);
      showRematch();
      return;
    }
    setControlsEnabled(true);
    setConnectionBadge("Connected", "badge-success");
    hideConnection();
    roundLabel.textContent = payload.total_rounds
      ? `Round ${round} / ${payload.total_rounds}`
      : `Round ${round} / ∞`;
    timer.textContent = `${payload.seconds_left}s`;
    renderLetters(payload.letters);
  };

  const connect = () => {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${location.host}/ws/match/${matchId}`);

    socket.addEventListener("open", () => {
      retry = 0;
      setConnectionBadge("Connected", "badge-success");
      hideConnection();
    });

    socket.addEventListener("close", (event) => {
      if (ended) return;
      stopStartCountdown();
      setControlsEnabled(false);
      if (event.code === 4401) {
        setConnectionBadge("Login required", "badge-accent");
        showConnection({
          title: "Login required",
          detail: "Sign in to join this match and keep your progress.",
          needLogin: true,
        });
        toast("Log in to play this match", "error");
        return;
      }
      if (event.code === 4000) {
        setConnectionBadge("Elsewhere", "badge-accent");
        showConnection({
          title: "Opened in another window",
          detail: "This match is now active in a different window.",
          canGoBack: true,
        });
        return;
      }
      if ([4403, 4404].includes(event.code)) {
        setConnectionBadge("Unavailable", "badge-error");
        showConnection({
          title: "Cannot join match",
          detail: tournamentId
            ? "This waiting lobby is no longer available. You can rejoin the tournament."
            : "This match is no longer available to join.",
          canGoBack: true,
        });
        return;
      }
      const delay = Math.min(8000, 1000 * 2 ** retry);
      setConnectionBadge("Reconnecting", "badge-accent");
      showConnection({
        title: "Connection lost",
        detail: `Trying again in ${Math.ceil(delay / 1000)}s. Your controls are paused until the arena reconnects.`,
        canRetry: true,
      });
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, delay);
      retry += 1;
    });

    socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (error) {
        return;
      }
      if (message.type === "state") return renderState(message.payload);
      if (message.type === "tick") {
        if (!ended && typeof message.payload?.seconds_left === "number") {
          timer.textContent = `${message.payload.seconds_left}s`;
        }
        return;
      }
      if (message.type === "round_start") {
        addLog(`Round ${message.payload.index + 1} started (${message.payload.letters})`);
        fx.banner(`Round ${message.payload.index + 1}`);
        return renderLetters(message.payload.letters);
      }
      if (message.type === "word") {
        addLog(`${message.payload.word} (+${message.payload.points})`);
        if (message.payload.points > 0) fx.attack(sideById[message.payload.user_id], message.payload.word);
        return;
      }
      if (message.type === "event") {
        addLog(message.payload?.message || message.event || "Event");
        fx.event(message.event, sideById[message.user_id], message.payload?.message);
        if (message.event === "sudden.death") fx.banner("Sudden death");
        return;
      }
      if (message.type === "error") return toast(message.message, "error");
      if (message.type === "match_end") {
        ended = true;
        setControlsEnabled(false);
        clearTimeout(reconnectTimer);
        for (const [id, player] of Object.entries(message.payload.players || {})) {
          if (sideById[id]) renderPlayer(player, sideById[id], Number(id) === myId);
        }
        fx.end(message.payload.winner_id == null ? null : sideById[message.payload.winner_id]);
        fx.whenIdle(() => renderResult(message.payload));
        addLog(`Match ended: ${message.payload.reason}`);
        showRematch();
      }
    });
  };

  const send = (type, payload = {}) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type, ...payload }));
    } else {
      toast("Not connected to the match", "warning");
    }
  };

  document.getElementById("answer-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!wordInput.value.trim()) return;
    send("answer.submit", { word: wordInput.value });
    wordInput.value = "";
    wordInput.focus();
  });

  document.getElementById("skill-btn").addEventListener("click", () => send("skill.activate"));
  document.getElementById("health-btn").addEventListener("click", () => send("resource.regenerate", { resource: "health" }));
  document.getElementById("armor-btn").addEventListener("click", () => send("resource.regenerate", { resource: "armor" }));
  document.getElementById("regen-skill-btn").addEventListener("click", () => send("skill.regenerate"));

  const shortcutActions = {
    "1": () => send("skill.activate"),
    "2": () => send("resource.regenerate", { resource: "health" }),
    "3": () => send("resource.regenerate", { resource: "armor" }),
    "4": () => send("skill.regenerate"),
  };
  const legacyShortcuts = { "0": "1", "1": "2", "2": "3", "3": "4" };

  document.addEventListener("keydown", (event) => {
    if (ended || event.repeat || event.isComposing) return;
    if (event.altKey || event.metaKey || event.shiftKey) return;
    const key = event.ctrlKey ? legacyShortcuts[event.key] : event.key;
    const action = shortcutActions[key];
    if (!action) return;
    event.preventDefault();
    action();
  });

  setControlsEnabled(false);
  connect();
}
