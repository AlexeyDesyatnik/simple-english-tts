// The page is only a view (ADR-0003): it sends commands, renders the polled snapshot
// and plays the paragraphs the core says to play, reporting when each starts and finishes.

const PARAGRAPH_PAUSE = 0.7; // seconds of silence between paragraphs
const FADE = 0.005; // seconds; pieces fade in and out so they join without clicks

const sourceEl = document.getElementById("source");
const statusEl = document.getElementById("status");
const voicesEl = document.getElementById("voices");
const speedEl = document.getElementById("speed");
const paragraphsEl = document.getElementById("paragraphs");
const libraryEl = document.getElementById("library");
const queuePanelEl = document.getElementById("queue-panel");
const queueEl = document.getElementById("queue");
const smallerEl = document.getElementById("smaller");
const biggerEl = document.getElementById("bigger");

let snapshot = null;
let shownContent = null; // the Text the paragraph list was built for
let shownTextId = null; // the Text put in the text box; another one replaces what is typed there
let shownLibrary = null; // the Library the list was built for
let shownQueue = null; // the Narration queue the list was built for
let shownVoices = null; // the Voices and Speeds the pickers were built for
let sample = null; // the Voice sample playing
let audioContext = null;
let buffers = new Map(); // audio id -> Promise<AudioBuffer>
// Paragraphs handed to WebAudio, in play order: {paragraph, start, end, nodes, started}.
let scheduled = [];
let epoch = 0; // grows when the schedule is thrown away, so an unfinished scheduling step knows it is stale
let scheduling = false;
let lingering = null; // the paragraph just heard: it stays highlighted through the pause before the next one
let blocked = false; // the browser would not play sound after a reload until Play is pressed

// Requests go one at a time, so a snapshot is never older than an event the page has sent.
let queue = Promise.resolve();
function serial(task) {
  const result = queue.then(task);
  queue = result.catch(() => {});
  return result;
}

let issued = 0; // commands sent so far: a snapshot fetched before the latest one may undo it, so it is dropped

function command(body) {
  issued++;
  return serial(async () => {
    const response = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const reply = await response.json();
    if (!response.ok) throw new Error(reply.error);
    return reply.result;
  });
}

function refresh() {
  return serial(async () => {
    const before = issued;
    const next = await (await fetch("/api/state")).json();
    if (issued === before) render(next); // otherwise the refresh after that command brings a newer one
  });
}

// Sends a command or event, then shows its effect at once.
function act(body) {
  return command(body)
    .then(refresh)
    .catch((e) => showError(e.message));
}

// ---------------------------------------------------------------- player

function audioBuffer(id) {
  if (!buffers.has(id)) {
    const loading = fetch(`/api/audio/${id}`)
      .then((r) => r.arrayBuffer())
      .then((data) => audioContext.decodeAudioData(data));
    loading.catch(() => buffers.delete(id));
    buffers.set(id, loading);
  }
  return buffers.get(id);
}

function clearSchedule() {
  epoch++;
  lingering = null;
  for (const item of scheduled) {
    for (const node of item.nodes) {
      try {
        node.stop();
      } catch {}
    }
  }
  scheduled = [];
}

function schedule(paragraph, pieces) {
  const previous = scheduled.at(-1);
  const now = audioContext.currentTime + 0.05;
  let t = previous ? Math.max(previous.end + PARAGRAPH_PAUSE, now) : now;
  const item = { paragraph, start: t, nodes: [], started: false };
  for (const buffer of pieces) {
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    const gain = audioContext.createGain();
    gain.gain.setValueAtTime(0, t);
    gain.gain.linearRampToValueAtTime(1, t + FADE);
    gain.gain.setValueAtTime(1, t + buffer.duration - FADE);
    gain.gain.linearRampToValueAtTime(0, t + buffer.duration);
    source.connect(gain).connect(audioContext.destination);
    source.start(t);
    item.nodes.push(source);
    t += buffer.duration;
  }
  item.end = t;
  scheduled.push(item);
}

// Makes what WebAudio plays match the snapshot: the current paragraph and the next one, once ready.
async function sync() {
  const playback = snapshot.playback;
  if (playback.state === "stopped") return clearSchedule();
  if (!audioContext) return;
  // While waiting for the Start delay, what was scheduled before a pause stays held where it is.
  if (playback.state === "paused" || playback.state === "waiting") {
    if (audioContext.state === "running") await audioContext.suspend();
    return;
  }
  if (audioContext.state !== "running") await audioContext.resume();

  const wanted = [playback.paragraph, playback.next].filter((n) => n !== null);
  if (scheduled.length && !wanted.includes(scheduled[0].paragraph)) clearSchedule(); // the core moved elsewhere
  if (scheduling) return;
  scheduling = true;
  try {
    const last = scheduled.at(-1);
    const from = last ? wanted.indexOf(last.paragraph) + 1 : 0;
    const mine = epoch;
    for (const n of wanted.slice(from)) {
      const paragraph = snapshot.text.paragraphs[n];
      if (paragraph.status !== "ready") break; // waited for: the next poll tries again
      const pieces = await Promise.all(paragraph.audio.map(audioBuffer));
      if (epoch !== mine) return;
      schedule(n, pieces);
    }
  } finally {
    scheduling = false;
  }
}

// Reports what WebAudio has started and finished; its clock stops while paused.
function tick() {
  if (!audioContext) return;
  const now = audioContext.currentTime;
  for (const item of [...scheduled]) {
    if (!item.started && item.start <= now) {
      item.started = true;
      lingering = null;
      act({ command: "paragraph_started", paragraph: item.paragraph });
    }
    if (item.end <= now) {
      scheduled.splice(scheduled.indexOf(item), 1);
      lingering = scheduled.length ? item.paragraph : null;
      act({ command: "paragraph_finished", paragraph: item.paragraph });
    }
  }
}

// After F5 the page has no permission to play until a click; it asks the core to pause instead.
async function startAfterReload() {
  audioContext = new AudioContext();
  audioContext.resume();
  await new Promise((resolve) => setTimeout(resolve, 300));
  if (audioContext.state !== "running") {
    blocked = true;
    await act({ command: "pause" });
  }
}

// ---------------------------------------------------------------- view

function renderLibrary(library, currentId) {
  const key = JSON.stringify(library);
  if (key !== shownLibrary) {
    shownLibrary = key;
    libraryEl.replaceChildren(
      ...library.map((t) => {
        const li = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = t.title;
        button.dataset.id = t.id;
        button.addEventListener("click", () => {
          clearSchedule();
          act({ command: "open_text", id: t.id });
        });
        li.append(button);
        return li;
      }),
    );
  }
  for (const button of libraryEl.querySelectorAll("button")) {
    button.classList.toggle("current", button.dataset.id === currentId);
  }
}

// "0,8×"; normal Speed is named so the teacher can find the way back to it
function speedLabel(speed) {
  return speed === 1 ? "1× — обычная" : `${String(speed).replace(".", ",")}×`;
}

// A Voice sample is ready-made: the core hands it over without synthesizing anything.
function playSample(voiceId) {
  sample?.pause();
  sample = new Audio(`/api/sample/${encodeURIComponent(voiceId)}`);
  sample.play().catch(() => showError("Не получилось проиграть образец голоса"));
}

function renderVoices() {
  const key = JSON.stringify([snapshot.voices, snapshot.speeds, snapshot.voices_loading]);
  if (key !== shownVoices) {
    shownVoices = key;
    voicesEl.replaceChildren(
      ...snapshot.voices.map((v) => {
        const li = document.createElement("li");
        const label = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "voice";
        radio.value = v.id;
        // Another Voice is another Narration: the core stops the one playing.
        radio.addEventListener("change", () => {
          clearSchedule();
          act({ command: "set_voice", voice: v.id });
        });
        // While the Voices load they are not available yet, but nothing is wrong with them.
        const unavailable = !v.available && !snapshot.voices_loading;
        label.append(radio, ` ${unavailable ? `${v.label} (недоступен)` : v.label}`);
        const listen = document.createElement("button");
        listen.type = "button";
        listen.className = "secondary";
        listen.textContent = "Послушать";
        listen.addEventListener("click", () => playSample(v.id));
        li.append(label, listen);
        return li;
      }),
    );
    speedEl.replaceChildren(...snapshot.speeds.map((s) => new Option(speedLabel(s), String(s))));
  }
  for (const radio of voicesEl.querySelectorAll("input")) radio.checked = radio.value === snapshot.voice;
  if (speedEl.value !== String(snapshot.speed)) speedEl.value = String(snapshot.speed);
}

// "George, 0,8×"
function narrationLabel(narration) {
  const voice = snapshot.voices.find((v) => v.id === narration.voice);
  return `${voice ? voice.label.split(" — ")[0] : narration.voice}, ${String(narration.speed).replace(".", ",")}×`;
}

function renderQueue(queue) {
  queuePanelEl.hidden = queue.length === 0;
  const key = JSON.stringify(queue.map((n) => n.id));
  if (key !== shownQueue) {
    shownQueue = key;
    queueEl.replaceChildren(
      ...queue.map((n) => {
        const li = document.createElement("li");
        const title = document.createElement("span");
        title.className = "title";
        title.textContent = `${n.title} · ${narrationLabel(n)}`;
        const left = document.createElement("span");
        left.className = "muted";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "secondary";
        cancel.textContent = "Отменить";
        cancel.addEventListener("click", () => act({ command: "cancel", narration: n.id }));
        li.append(title, left, cancel);
        return li;
      }),
    );
  }
  queue.forEach((n, i) => {
    const state = n.synthesizing ? "озвучивается" : "ждёт";
    const left = n.ready_in === null ? "" : ` · готово через ${formatDuration(n.ready_in)}`;
    queueEl.children[i].querySelector(".muted").textContent = state + left;
  });
}

function renderParagraphs(text) {
  if (text?.content !== shownContent) {
    shownContent = text?.content ?? null;
    paragraphsEl.replaceChildren(
      ...(text?.paragraphs ?? []).map((p, i) => {
        const li = document.createElement("li");
        li.textContent = p.text;
        li.addEventListener("click", () => playFrom(i));
        return li;
      }),
    );
  }
  const playback = snapshot.playback;
  const highlighted = lingering ?? (playback.state === "stopped" ? null : playback.paragraph);
  (text?.paragraphs ?? []).forEach((p, i) => {
    const li = paragraphsEl.children[i];
    const current = highlighted === i;
    if (current && !li.classList.contains("current")) {
      // On a projector the class reads ahead, so the current Paragraph is kept in the middle of the screen.
      const block = document.body.classList.contains("playback") ? "center" : "nearest";
      li.scrollIntoView({ block, behavior: "smooth" });
    }
    li.className = [p.status === "skipped" && "skipped", p.status === "failed" && "failed", current && "current"]
      .filter(Boolean)
      .join(" ");
    li.title = p.error ?? "";
  });
}

// "~1 мин 20 с", "~45 с"
function formatDuration(seconds) {
  const s = Math.max(1, Math.ceil(seconds));
  const minutes = Math.floor(s / 60);
  return minutes ? `~${minutes} мин ${s % 60} с` : `~${s} с`;
}

function statusText(text, playback) {
  if (snapshot.library_error) return [snapshot.library_error, "error"];
  if (!text) return ["", ""];
  const readable = text.paragraphs.filter((p) => p.status !== "skipped");
  const failed = readable.find((p) => p.status === "failed");
  if (failed) return [`Не получилось озвучить абзац: ${failed.error}`, "error"];
  if (blocked && playback.state === "paused") return ["Нажмите Play, чтобы продолжить", ""];
  if (playback.state === "waiting") {
    if (snapshot.voices_loading && playback.start_delay === null) return ["Голоса загружаются…", ""];
    if (playback.start_delay === null) return ["Оцениваю, сколько ждать начала…", ""];
    return [`Начнётся через ${formatDuration(playback.start_delay)}`, ""];
  }
  const current = playback.paragraph === null ? null : text.paragraphs[playback.paragraph];
  if (playback.state === "playing" && current && current.status !== "ready") return ["Готовлю озвучку абзаца…", ""];
  const ready = readable.filter((p) => p.status === "ready").length;
  const progress = ready < readable.length && readable.some((p) => p.status === "synthesizing");
  const parts = [];
  if (playback.state === "paused") parts.push("Пауза");
  if (progress) parts.push(`Озвучено абзацев: ${ready} из ${readable.length}`);
  if (snapshot.voices_loading && snapshot.queue.length) parts.push("Голоса загружаются…");
  return [parts.join(" · "), ""];
}

function renderTextSize() {
  paragraphsEl.style.fontSize = `${snapshot.text_size}px`;
  const at = snapshot.text_sizes.indexOf(snapshot.text_size);
  smallerEl.disabled = at <= 0;
  biggerEl.disabled = at === snapshot.text_sizes.length - 1;
}

function render(next) {
  const first = snapshot === null;
  snapshot = next;
  // Playback mode: only the Text and the buttons, for the class to read on a projector.
  document.body.classList.toggle("playback", snapshot.playback.state !== "stopped");
  renderVoices();
  renderTextSize();
  const textId = snapshot.text?.id ?? null;
  if (first || textId !== shownTextId) {
    shownTextId = textId;
    if (first || textId !== null) sourceEl.value = snapshot.text?.content ?? "";
  }
  renderLibrary(snapshot.library, textId);
  renderQueue(snapshot.queue);
  renderParagraphs(snapshot.text);
  const [message, className] = statusText(snapshot.text, snapshot.playback);
  statusEl.textContent = message;
  statusEl.className = className;
  if (first && ["playing", "waiting"].includes(snapshot.playback.state)) {
    startAfterReload().then(sync);
  } else {
    sync().catch((e) => showError(`Ошибка воспроизведения: ${e.message}`));
  }
}

function showError(message) {
  statusEl.textContent = message;
  statusEl.className = "error";
}

async function poll() {
  try {
    await refresh();
  } catch (e) {
    showError("Нет связи с программой");
  }
  setTimeout(poll, 500);
}

// ---------------------------------------------------------------- buttons

// Created and resumed inside a click, so the browser allows it to play sound.
function allowSound() {
  audioContext ??= new AudioContext();
  audioContext.resume();
  blocked = false;
}

function playFrom(index) {
  if (snapshot.text.paragraphs[index].status === "skipped") return;
  allowSound();
  clearSchedule();
  act({ command: "play_from", paragraph: index });
}

// Saves what is typed in the text box as the current Text, before a command for it.
async function saveTypedText() {
  if (sourceEl.value !== snapshot?.text?.content) {
    clearSchedule();
    await command({ command: "set_text", text: sourceEl.value });
  }
}

async function actOnTypedText(name) {
  try {
    await saveTypedText();
    await act({ command: name });
  } catch (e) {
    showError(e.message);
  }
}

function play() {
  allowSound();
  actOnTypedText("play");
}

function pause() {
  audioContext?.suspend();
  act({ command: "pause" });
}

// The core answers whether playback moves; only then is what was scheduled thrown away,
// so a key pressed at the end of the Text does not interrupt the Paragraph playing.
async function moveParagraph(name) {
  allowSound();
  try {
    await saveTypedText();
    if (await command({ command: name })) clearSchedule();
    await refresh();
  } catch (e) {
    showError(e.message);
  }
}

document.getElementById("play").addEventListener("click", play);

// Another Speed is another Narration: the core stops the one playing.
speedEl.addEventListener("change", () => {
  clearSchedule();
  act({ command: "set_speed", speed: Number(speedEl.value) });
});

document.getElementById("enqueue").addEventListener("click", () => actOnTypedText("enqueue"));

document.getElementById("pause").addEventListener("click", pause);

smallerEl.addEventListener("click", () => act({ command: "smaller_text" }));
biggerEl.addEventListener("click", () => act({ command: "bigger_text" }));

// Keys by their place on the keyboard (code), so R works in the Russian layout too.
// Presenter remotes send the arrows or PageUp / PageDown.
const KEYS = {
  Space: () => (["playing", "waiting"].includes(snapshot?.playback.state) ? pause() : play()),
  ArrowLeft: () => moveParagraph("previous_paragraph"),
  PageUp: () => moveParagraph("previous_paragraph"),
  ArrowRight: () => moveParagraph("next_paragraph"),
  PageDown: () => moveParagraph("next_paragraph"),
  KeyR: () => moveParagraph("repeat_paragraph"),
};

// The text box hidden in Playback mode may still hold the focus from typing before Play.
function typing(e) {
  return e.target === sourceEl && !document.body.classList.contains("playback");
}

document.addEventListener("keydown", (e) => {
  const key = KEYS[e.code];
  if (!key || e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
  if (typing(e)) return;
  // The keys also win over a focused button, radio or list, which would otherwise take them too.
  e.preventDefault();
  if (!e.repeat) key();
});

// A focused button is pressed by Space on keyup.
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && !typing(e)) e.preventDefault();
});

document.getElementById("new-text").addEventListener("click", () => {
  clearSchedule();
  sourceEl.value = "";
  sourceEl.focus();
  act({ command: "new_text" });
});

document.getElementById("stop").addEventListener("click", () => {
  clearSchedule();
  act({ command: "stop" });
});

// ---------------------------------------------------------------- heartbeat

// The program ends when its window is closed: it learns that when the heartbeat stops (ADR-0003).
// Not sent in turn with the commands: it says nothing about the snapshot.
function heartbeat(event) {
  return JSON.stringify({ command: event });
}
function sendHeartbeat() {
  fetch("/api/command", { method: "POST", body: heartbeat("page_alive") }).catch(() => {});
}
window.addEventListener("pagehide", () => navigator.sendBeacon("/api/command", heartbeat("page_closing")));
document.addEventListener("freeze", () => navigator.sendBeacon("/api/command", heartbeat("page_frozen")));
document.addEventListener("resume", sendHeartbeat);
setInterval(sendHeartbeat, 5000);
sendHeartbeat();

setInterval(tick, 50);
poll();
