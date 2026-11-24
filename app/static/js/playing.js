import { request } from "./api.js";
import { toast } from "./ui.js";

const meta = document.getElementById("match-meta");
if (meta) {
  const matchId = meta.dataset.matchId;
  let myId = null;
  try {
    myId = (await request("/api/auth/me")).id;
  } catch (error) {
    toast("Log in to play this match", "error");
  }
  const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/match/${matchId}`);

  const wordInput = document.getElementById("word-input");

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
    document.getElementById(`skill-${side}`).textContent = player.skill_label || "-";
    document.getElementById(`status-${side}`).textContent = player.connected ? (player.blocked ? "Blocked" : "") : "Disconnected";
  };

  const renderState = (payload) => {
    const players = Object.entries(payload.players).map(([id, player]) => ({ ...player, id: Number(id) }));
    if (!myId && players.length) myId = players[0].id;
    const mine = players.find((player) => player.id === myId) || players[0];
    const opponent = players.find((player) => player.id !== mine.id) || players[1];
    if (!ids.length && players.length === 2) {
      ids.push(mine.id, opponent.id);
    }
    if (mine) renderPlayer(mine, "p1", true);
    if (opponent) renderPlayer(opponent, "p2", false);
    document.getElementById("round-label").textContent = `Round ${Math.min(payload.round_index + 1, payload.total_rounds)} / ${payload.total_rounds}`;
    document.getElementById("timer").textContent = `${payload.seconds_left}s`;
    renderLetters(payload.letters);
  };

  socket.addEventListener("open", () => {
    document.getElementById("connection").textContent = "Connected";
  });

  socket.addEventListener("close", () => {
    document.getElementById("connection").textContent = "Disconnected";
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") return renderState(message.payload);
    if (message.type === "round_start") {
      addLog(`Round ${message.payload.index + 1} started (${message.payload.letters})`);
      return renderLetters(message.payload.letters);
    }
    if (message.type === "word") {
      addLog(`${message.payload.word} (+${message.payload.points})`);
      return;
    }
    if (message.type === "event") {
      addLog(message.payload?.message || message.event || "Event");
      return;
    }
    if (message.type === "error") return toast(message.message, "error");
    if (message.type === "match_end") {
      const won = message.payload.winner_id === myId;
      document.getElementById("result").classList.remove("hidden");
      document.getElementById("result").textContent = won ? "Victory! Your tank wins." : "Defeat. Better spelling next round.";
      addLog(`Match ended: ${message.payload.reason}`);
    }
  });

  document.getElementById("answer-form").addEventListener("submit", (event) => {
    event.preventDefault();
    socket.send(JSON.stringify({ type: "answer.submit", word: wordInput.value }));
    wordInput.value = "";
    wordInput.focus();
  });

  const send = (type, payload = {}) => socket.send(JSON.stringify({ type, ...payload }));
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
}
