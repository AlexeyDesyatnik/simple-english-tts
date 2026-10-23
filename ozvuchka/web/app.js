// The page is only a view (ADR-0003): it sends commands, renders the polled snapshot
// and plays the paragraphs the core says to play, reporting when each starts and finishes.

const PARAGRAPH_PAUSE = 0.7; // seconds of silence between paragraphs
const FADE = 0.005; // seconds; pieces fade in and out so they join without clicks

const sourceEl = document.getElementById("source");
const statusEl = document.getElementById("status");
const voiceEl = document.getElementById("voice");
const paragraphsEl = document.getElementById("paragraphs");
const libraryEl = document.getElementById("library");

let snapshot = null;
let shownContent = null; // the Text the paragraph list was built for
let shownTextId = null; // the Text put in the text box; another one replaces what is typed there
let shownLibrary = null; // the Library the list was built for
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
  if (playback.state === "paused") {
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

function renderParagraphs(text) {
  if (text?.content !== shownContent) {
    shownContent = text?.content ?? null;
    paragraphsEl.replaceChildren(
      ...(text?.paragraphs ?? []).map((p) => {
        const li = document.createElement("li");
        li.textContent = p.text;
        return li;
      }),
    );
  }
  const playback = snapshot.playback;
  const highlighted = lingering ?? (playback.state === "stopped" ? null : playback.paragraph);
  (text?.paragraphs ?? []).forEach((p, i) => {
    const li = paragraphsEl.children[i];
    const current = highlighted === i;
    if (current && !li.classList.contains("current")) li.scrollIntoView({ block: "nearest", behavior: "smooth" });
    li.className = [p.status === "skipped" && "skipped", p.status === "failed" && "failed", current && "current"]
      .filter(Boolean)
      .join(" ");
    li.title = p.error ?? "";
  });
}

function statusText(text, playback) {
  if (snapshot.library_error) return [snapshot.library_error, "error"];
  if (!text) return ["", ""];
  const readable = text.paragraphs.filter((p) => p.status !== "skipped");
  const failed = readable.find((p) => p.status === "failed");
  if (failed) return [`Не получилось озвучить абзац: ${failed.error}`, "error"];
  if (blocked && playback.state === "paused") return ["Нажмите Play, чтобы продолжить", ""];
  const current = playback.paragraph === null ? null : text.paragraphs[playback.paragraph];
  if (playback.state === "playing" && current && current.status !== "ready") return ["Готовлю озвучку абзаца…", ""];
  const ready = readable.filter((p) => p.status === "ready").length;
  const progress = ready < readable.length && readable.some((p) => p.status === "synthesizing");
  const parts = [];
  if (playback.state === "paused") parts.push("Пауза");
  if (progress) parts.push(`Озвучено абзацев: ${ready} из ${readable.length}`);
  return [parts.join(" · "), ""];
}

function render(next) {
  const first = snapshot === null;
  snapshot = next;
  const voice = snapshot.voices.find((v) => v.id === snapshot.voice);
  voiceEl.textContent = voice ? `Голос: ${voice.label}` : "";
  const textId = snapshot.text?.id ?? null;
  if (first || textId !== shownTextId) {
    shownTextId = textId;
    if (first || textId !== null) sourceEl.value = snapshot.text?.content ?? "";
  }
  renderLibrary(snapshot.library, textId);
  renderParagraphs(snapshot.text);
  const [message, className] = statusText(snapshot.text, snapshot.playback);
  statusEl.textContent = message;
  statusEl.className = className;
  if (first && snapshot.playback.state === "playing") {
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

document.getElementById("play").addEventListener("click", async () => {
  // Created and resumed inside the click, so the browser allows it to play sound.
  audioContext ??= new AudioContext();
  audioContext.resume();
  blocked = false;
  try {
    if (sourceEl.value !== snapshot?.text?.content) {
      clearSchedule();
      await command({ command: "set_text", text: sourceEl.value });
    }
    await act({ command: "play" });
  } catch (e) {
    showError(e.message);
  }
});

document.getElementById("pause").addEventListener("click", () => {
  audioContext?.suspend();
  act({ command: "pause" });
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

setInterval(tick, 50);
poll();
