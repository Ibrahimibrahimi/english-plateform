import { request } from "./api.js";
import { toast } from "./ui.js";
import { createArenaFx } from "./arena-fx.js";

const meta = document.getElementById("match-meta");
if (meta) {
  const matchId = meta.dataset.matchId;
  const wordInput = document.getElementById("word-input");
  const connection = document.getElementById("connection");
  const roundLabel = document.getElementById("round-label");
  const timer = document.getElementById("timer");
  const result = document.getElementById("result");
  const controls = [
    document.getElementById("answer-form")?.querySelector("button"),
    wordInput,
    document.getElementById("skill-btn"),
    document.getElementById("health-btn"),
    document.getElementById("armor-btn"),
    document.getElementById("regen-skill-btn"),
  ].filter(Boolean);

  const fx = createArenaFx();
  const sideById = {}; // user id -> "p1" (me) | "p2" (opponent)
  let myId = null;
  let socket = null;
  let ended = false;
  let retry = 0;
  let reconnectTimer = null;
  let isChallenge = false;
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
    finishedAtLoad = snapshot.match.status === "finished";
  } catch (error) {
    toast(error.message, "error");
  }

  const setControlsEnabled = (enabled) => {
    for (const control of controls) control.disabled = !enabled;
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
      ? `${player.skill_icon || "✨"} ${player.skill_label}`
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

    const round = Math.min(payload.round_index + 1, payload.total_rounds);
    if (payload.status === "waiting") {
      connection.textContent = "Waiting for opponent";
      roundLabel.textContent = "Lobby";
      timer.textContent = "--";
      setControlsEnabled(false);
      return;
    }
    if (payload.status === "finished") {
      setControlsEnabled(false);
      fx.end(payload.winner_id == null ? null : sideById[payload.winner_id]);
      connection.textContent = "Match finished";
      timer.textContent = "0s";
      if (result.classList.contains("hidden")) {
        result.classList.remove("hidden");
        if (payload.winner_id === null) {
          result.textContent = "Match ended in a draw.";
        } else if (payload.winner_id === myId) {
          result.textContent = "Victory! Your tank wins.";
        } else {
          result.textContent = "Defeat. Better spelling next round.";
        }
      }
      showRematch();
      return;
    }
    setControlsEnabled(true);
    connection.textContent = "Connected";
    roundLabel.textContent = `Round ${round} / ${payload.total_rounds}`;
    timer.textContent = `${payload.seconds_left}s`;
    renderLetters(payload.letters);
  };

  const connect = () => {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${location.host}/ws/match/${matchId}`);

    socket.addEventListener("open", () => {
      retry = 0;
      connection.textContent = "Connected";
    });

    socket.addEventListener("close", (event) => {
      if (ended) return;
      if (event.code === 4401) {
        connection.textContent = "Login required";
        toast("Log in to play this match", "error");
        return;
      }
      if (event.code === 4000) {
        connection.textContent = "Opened in another window";
        toast("This match is now open in another window", "warning");
        return;
      }
      if ([4403, 4404].includes(event.code)) {
        connection.textContent = "Cannot join match";
        return;
      }
      connection.textContent = "Reconnecting...";
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, Math.min(8000, 1000 * 2 ** retry));
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
      if (message.type === "round_start") {
        addLog(`Round ${message.payload.index + 1} started (${message.payload.letters})`);
        fx.banner(`Round ${message.payload.index + 1}`);
        return renderLetters(message.payload.letters);
      }
      if (message.type === "word") {
        addLog(`${message.payload.word} (+${message.payload.points})`);
        // The server only deals damage when the word scored, so only then does a soldier march.
        if (message.payload.points > 0) fx.attack(sideById[message.payload.user_id], message.payload.word);
        return;
      }
      if (message.type === "event") {
        addLog(message.payload?.message || message.event || "Event");
        // The server sends each skill/regen event twice; only the copy with a message is animated.
        fx.event(message.event, sideById[message.user_id], message.payload?.message);
        if (message.event === "sudden.death") fx.banner("Sudden death");
        return;
      }
      if (message.type === "error") return toast(message.message, "error");
      if (message.type === "match_end") {
        ended = true;
        setControlsEnabled(false);
        clearTimeout(reconnectTimer);
        // Final numbers come with the closing message: draw both cards and the arena from it.
        for (const [id, player] of Object.entries(message.payload.players || {})) {
          if (sideById[id]) renderPlayer(player, sideById[id], Number(id) === myId);
        }
        fx.end(message.payload.winner_id == null ? null : sideById[message.payload.winner_id]);
        // The result box waits until the last soldier has landed.
        fx.whenIdle(() => {
          result.classList.remove("hidden");
          if (message.payload.winner_id === null) {
            result.textContent = "Match ended in a draw.";
          } else if (message.payload.winner_id === myId) {
            result.textContent = "Victory! Your tank wins.";
          } else {
            result.textContent = "Defeat. Better spelling next round.";
          }
        });
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

  document.addEventListener("keydown", (event) => {
    if (event.target.matches("input, textarea")) return;
    if (event.ctrlKey && event.key === "0") { event.preventDefault(); send("skill.activate"); }
    if (event.ctrlKey && event.key === "1") { event.preventDefault(); send("resource.regenerate", { resource: "health" }); }
    if (event.ctrlKey && event.key === "2") { event.preventDefault(); send("resource.regenerate", { resource: "armor" }); }
    if (event.ctrlKey && event.key === "3") { event.preventDefault(); send("skill.regenerate"); }
  });

  setControlsEnabled(false);
  connect();
}
