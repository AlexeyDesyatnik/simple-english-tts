// The page is only a view (ADR-0003): it sends commands, renders the polled snapshot
// and plays the paragraphs the core says to play, reporting when each starts and finishes.

const PARAGRAPH_PAUSE = 0.7; // seconds of silence between paragraphs
const FADE = 0.005; // seconds; pieces fade in and out so they join without clicks

const sourceEl = document.getElementById("source");
const saveStatusEl = document.getElementById("save-status");
const statusEl = document.getElementById("status");
const voicesEl = document.getElementById("voices");
const speedEl = document.getElementById("speed");
const paragraphsEl = document.getElementById("paragraphs");
const libraryEl = document.getElementById("library");
const librarySearchEl = document.getElementById("library-search");
const librarySizeEl = document.getElementById("library-size");
const queueEl = document.getElementById("queue");
const smallerEl = document.getElementById("smaller");
const biggerEl = document.getElementById("bigger");
const playEl = document.getElementById("play");
const progressEl = document.getElementById("paragraph-progress");
const playbackErrorEl = document.getElementById("playback-error");
const titleEl = document.getElementById("text-title");
const titleActionsEl = document.getElementById("title-actions");
const titleErrorEl = document.getElementById("title-error");
const deleteDialogEl = document.getElementById("delete-dialog");
const libraryPanelEl = document.getElementById("library-panel");
const narrowWindow = matchMedia("(max-width: 900px)");

// Disclosures are page presentation only; resizing never sends a Core command.
function resizeLibrary() {
  if (narrowWindow.matches && libraryPanelEl.contains(document.activeElement)) {
    closeMenu(false);
    libraryPanelEl.querySelector("summary").focus();
  }
  libraryPanelEl.open = !narrowWindow.matches;
}
narrowWindow.addEventListener("change", resizeLibrary);
let titleDirty = false;
let replacingText = false;
let savingTitle = false;
let activeMenu = null;
resizeLibrary();

function revealWorkspace() {
  if (narrowWindow.matches) libraryPanelEl.open = false;
  sourceEl.focus();
}

for (const panel of [libraryPanelEl, document.getElementById("voice-panel"), document.getElementById("playback-help")]) {
  panel.addEventListener("keydown", (e) => {
    if (e.defaultPrevented || e.key !== "Escape" || !panel.open || activeMenu || deleteDialogEl.open) return;
    panel.open = false;
    panel.querySelector("summary").focus();
    e.preventDefault();
    e.stopPropagation();
  });
}
libraryPanelEl.addEventListener("toggle", () => {
  if (!libraryPanelEl.open) closeMenu(false);
});

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

function command(body, keepalive = false) {
  issued++;
  return serial(async () => {
    const response = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive,
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
    if (issued !== before) return false; // the refresh after that command brings a newer one
    render(next);
    return true;
  });
}

// Sends a command or event, then shows its effect at once.
function act(body) {
  return command(body)
    .then(refresh)
    .catch((e) => showError(e.message));
}

// ---------------------------------------------------------------- autosave

const AUTOSAVE_DELAY = 700;
let editVersion = 0;
let savedVersion = 0;
let saveTimer = null;
let saveInFlight = null;

function showSaveState(state, message = "") {
  const labels = {
    unsaved: "Изменения не сохранены",
    saving: "Сохранение…",
    saved: "Сохранено",
    failed: message || "Не удалось сохранить изменения",
  };
  saveStatusEl.textContent = labels[state];
  saveStatusEl.className = state === "failed" ? "error" : "muted";
  saveStatusEl.dataset.state = state;
}

function cancelScheduledSave() {
  clearTimeout(saveTimer);
  saveTimer = null;
}

function scheduleSave() {
  cancelScheduledSave();
  saveTimer = setTimeout(() => saveEdits().catch(() => {}), AUTOSAVE_DELAY);
}

function saveEdits() {
  cancelScheduledSave();
  if (saveInFlight) return saveInFlight;
  if (editVersion === savedVersion) {
    showSaveState("saved");
    return Promise.resolve();
  }
  const version = editVersion;
  const text = sourceEl.value;
  showSaveState("saving");
  saveInFlight = (async () => {
    try {
      const saved = await command({ command: "set_text", text });
      await refresh();
      if (!saved) throw new Error(snapshot?.text?.save_error || "Не удалось сохранить Библиотеку");
      savedVersion = version;
      if (editVersion === version) {
        showSaveState("saved");
      } else {
        showSaveState("unsaved");
        scheduleSave();
      }
    } catch (e) {
      showSaveState("failed", `Не удалось сохранить изменения: ${e.message}`);
      if (editVersion !== version) scheduleSave();
      throw e;
    } finally {
      saveInFlight = null;
    }
  })();
  return saveInFlight;
}

async function flushEdits() {
  cancelScheduledSave();
  while (editVersion !== savedVersion || saveInFlight) await saveEdits();
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

async function actAfterFlush(body, clear = false) {
  try {
    await flushEdits();
    await saveTitle();
    if (clear) clearSchedule();
    await act(body);
  } catch (e) {
    showError(e.message);
  }
}

async function replaceText(body) {
  if (replacingText) return false;
  replacingText = true;
  sourceEl.disabled = true;
  titleEl.disabled = true;
  try {
    await flushEdits();
    await saveTitle();
  } catch (e) {
    replacingText = false;
    sourceEl.disabled = false;
    renderTitle();
    if (titleErrorEl.textContent) titleEl.focus();
    showError(e.message);
    return false;
  }
  // Typing resumes only after a current snapshot has actually been rendered.
  clearSchedule();
  try {
    await command(body);
  } catch (e) {
    showError(e.message);
  }
  let rendered = false;
  while (!rendered) {
    try {
      rendered = await refresh();
    } catch {
      showError("Не удалось показать текст. Повторяю…");
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  replacingText = false;
  sourceEl.disabled = false;
  renderTitle();
  return true;
}

function renderTitle() {
  titleEl.disabled = replacingText || savingTitle || !snapshot.text?.id;
  titleEl.placeholder = "Введите текст, чтобы дать ему название";
  if (!titleDirty) titleEl.value = snapshot.text?.title ?? "";
  titleActionsEl.hidden = !titleDirty;
}

async function saveTitle() {
  if (!titleDirty) return;
  const title = titleEl.value;
  if (!title.trim()) {
    titleErrorEl.textContent = "Название текста не может быть пустым";
    titleEl.setAttribute("aria-invalid", "true");
    titleEl.focus();
    throw new Error(titleErrorEl.textContent);
  }
  savingTitle = true;
  titleEl.disabled = true;
  try {
    await command({ command: "rename_text", id: snapshot.text.id, title });
    await refresh();
    if (snapshot.library_error) throw new Error(snapshot.library_error);
    if (titleEl.value === title) titleDirty = false;
  } finally {
    savingTitle = false;
    renderTitle();
  }
}

async function renameText(text) {
  if (await replaceText({ command: "open_text", id: text.id })) {
    if (narrowWindow.matches) libraryPanelEl.open = false;
    titleEl.focus();
    titleEl.select();
  }
}

function restoreLibraryFocus(trigger, textId) {
  if (!libraryPanelEl.open) {
    libraryPanelEl.querySelector("summary").focus();
    return;
  }
  const row = [...libraryEl.querySelectorAll(".text-title")].find((el) => el.dataset.id === textId);
  const label = trigger.getAttribute("aria-label");
  const replacement = label ? [...(row?.closest("li").querySelectorAll("button") ?? [])]
    .find((el) => el.getAttribute("aria-label") === label) ?? row : row;
  (trigger.isConnected ? trigger : replacement ?? document.getElementById("new-text")).focus();
}

function confirmDeletion(heading, consequences, trigger, textId, remove) {
  if (deleteDialogEl.open) return;
  document.getElementById("delete-heading").textContent = heading;
  document.getElementById("delete-consequences").textContent = consequences;
  deleteDialogEl.returnValue = "cancel";
  deleteDialogEl.addEventListener("close", async () => {
    if (deleteDialogEl.returnValue === "delete") await remove();
    restoreLibraryFocus(trigger, textId);
  }, { once: true });
  deleteDialogEl.showModal();
  document.getElementById("cancel-delete").focus();
}

deleteDialogEl.addEventListener("keydown", (e) => {
  if (e.key !== "Tab") return;
  const buttons = [...deleteDialogEl.querySelectorAll("button")];
  const first = buttons[0];
  const last = buttons.at(-1);
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
});

function deleteText(text, trigger) {
  confirmDeletion(`Удалить текст «${text.title}»?`,
    "Текст, его готовые озвучки и задания в очереди будут удалены из Библиотеки. Восстановить их нельзя.",
    trigger, text.id, () => replaceText({ command: "delete_text", id: text.id }));
}

function deleteNarration(text, narration, trigger) {
  const label = narrationLabel(narration);
  confirmDeletion(`Удалить озвучку «${label}»?`,
    `Готовая озвучка текста «${text.title}» будет удалена. Сам текст останется; озвучку можно создать заново.`,
    trigger, text.id, () => actAfterFlush(
      { command: "delete_narration", id: text.id, voice: narration.voice, speed: narration.speed }, true));
}

function closeMenu(restore = true) {
  if (!activeMenu) return;
  const { menu, trigger } = activeMenu;
  menu.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  activeMenu = null;
  if (restore) trigger.focus();
}

function libraryMenu(text, trigger) {
  const menu = document.createElement("div");
  menu.id = `text-menu-${text.id}`;
  menu.className = "library-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", `Действия с текстом «${text.title}»`);
  menu.hidden = true;
  trigger.setAttribute("aria-controls", menu.id);
  const actions = [
    ["Переименовать", () => renameText(text)],
    ["Удалить текст…", () => deleteText(text, trigger)],
  ];
  for (const [label, action] of actions) {
    const item = document.createElement("button");
    item.type = "button";
    item.tabIndex = -1;
    item.setAttribute("role", "menuitem");
    item.className = label.startsWith("Удалить") ? "secondary destructive" : "secondary";
    item.textContent = label;
    item.addEventListener("click", () => { closeMenu(); action(); });
    menu.append(item);
  }
  function openMenu(last = false) {
    closeMenu(false);
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    activeMenu = { menu, trigger };
    (last ? menu.lastElementChild : menu.firstElementChild).focus();
  }
  trigger.addEventListener("click", () => activeMenu?.trigger === trigger ? closeMenu() : openMenu());
  trigger.addEventListener("keydown", (e) => {
    if (!["ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    openMenu(e.key === "ArrowUp");
  });
  menu.addEventListener("keydown", (e) => {
    const items = [...menu.children];
    const index = items.indexOf(document.activeElement);
    const positions = { ArrowDown: (index + 1) % items.length,
      ArrowUp: (index + items.length - 1) % items.length, Home: 0, End: items.length - 1 };
    if (e.key in positions) {
      e.preventDefault();
      items[positions[e.key]].focus();
    } else if (e.key === "Escape" || e.key === "Tab") {
      closeMenu();
      if (e.key === "Escape") e.preventDefault();
    }
  });
  return menu;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1).replace(".", ",")} КБ`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1).replace(".", ",")} МБ`;
  return `${(bytes / 1024 ** 3).toFixed(1).replace(".", ",")} ГБ`;
}

function renderLibrary(library, currentId) {
  librarySizeEl.textContent = snapshot.library_bytes === null ? "Размер неизвестен" : formatBytes(snapshot.library_bytes);
  const key = JSON.stringify(library);
  if (key !== shownLibrary) {
    const focused = document.activeElement;
    const focusedId = focused.closest("#library > li")?.querySelector(".text-title").dataset.id;
    const menuId = activeMenu?.menu.id;
    const menuIndex = activeMenu ? [...activeMenu.menu.children].indexOf(focused) : -1;
    closeMenu(false);
    shownLibrary = key;
    libraryEl.replaceChildren(
      ...library.map((t) => {
        const li = document.createElement("li");
        const row = document.createElement("div");
        row.className = "library-text";
        const open = document.createElement("button");
        open.type = "button";
        open.className = "text-title";
        open.textContent = t.title;
        open.dataset.id = t.id;
        open.addEventListener("click", async () => {
          if (await replaceText({ command: "open_text", id: t.id })) revealWorkspace();
        });
        const trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "secondary menu-trigger";
        trigger.textContent = "⋯";
        trigger.setAttribute("aria-label", `Действия с текстом «${t.title}»`);
        trigger.setAttribute("aria-haspopup", "menu");
        trigger.setAttribute("aria-expanded", "false");
        row.append(open, trigger, libraryMenu(t, trigger));

        const narrations = document.createElement("div");
        narrations.className = "library-narrations";
        for (const n of t.narrations) {
          const label = narrationLabel(n);
          const ready = document.createElement("span");
          ready.className = "ready-narration";
          ready.title = `Готовая озвучка: ${label}`;
          const icon = document.createElement("span");
          icon.setAttribute("aria-hidden", "true");
          icon.textContent = "♪";
          const removeNarration = document.createElement("button");
          removeNarration.type = "button";
          removeNarration.className = "delete-narration";
          removeNarration.textContent = "×";
          removeNarration.title = `Удалить озвучку ${label}`;
          removeNarration.setAttribute("aria-label", `Удалить озвучку ${label}`);
          removeNarration.addEventListener("click", () => deleteNarration(t, n, removeNarration));
          ready.append(icon, ` ${label}`, removeNarration);
          narrations.append(ready);
        }
        li.append(row, narrations);
        return li;
      }),
    );
    const menu = menuId ? document.getElementById(menuId) : null;
    if (menu && !deleteDialogEl.open) {
      const trigger = menu.previousElementSibling;
      menu.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      activeMenu = { menu, trigger };
      if (menuIndex >= 0) menu.children[menuIndex].focus();
    } else if (focusedId && !deleteDialogEl.open) restoreLibraryFocus(focused, focusedId);
  }
  for (const button of libraryEl.querySelectorAll(".text-title")) {
    button.classList.toggle("current", button.dataset.id === currentId);
    if (button.dataset.id === currentId) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
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
  const key = JSON.stringify([snapshot.voices.map((v) => [v.id, v.label]), snapshot.speeds]);
  if (key !== shownVoices) {
    shownVoices = key;
    voicesEl.replaceChildren(
      ...snapshot.voices.map((v, i) => {
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
        const text = document.createElement("span");
        text.className = "voice-text";
        const [name, ...description] = v.label.split(" — ");
        const title = document.createElement("strong");
        title.textContent = name;
        const detail = document.createElement("span");
        detail.className = "muted";
        detail.textContent = description.join(" — ");
        const state = document.createElement("span");
        state.id = `voice-state-${i}`;
        state.className = "voice-state";
        state.setAttribute("aria-live", "polite");
        radio.setAttribute("aria-describedby", state.id);
        text.append(title, detail, state);
        label.append(radio, text);
        const listen = document.createElement("button");
        listen.type = "button";
        listen.className = "secondary";
        listen.textContent = "Образец";
        listen.setAttribute("aria-label", `Послушать образец: ${name}`);
        listen.addEventListener("click", () => playSample(v.id));
        li.append(label, listen);
        return li;
      }),
    );
    speedEl.replaceChildren(...snapshot.speeds.map((s) => new Option(speedLabel(s), String(s))));
  }
  snapshot.voices.forEach((v, i) => {
    const row = voicesEl.children[i];
    const selected = v.id === snapshot.voice;
    const availability = v.available ? "ready" : snapshot.voices_loading ? "loading" : "unavailable";
    row.dataset.availability = availability;
    row.classList.toggle("selected", selected);
    row.querySelector("input").checked = selected;
    const state = [selected && "Выбран", availability === "loading" && "Загрузка…",
      availability === "unavailable" && "Недоступен"].filter(Boolean).join(" · ");
    const stateEl = row.querySelector(".voice-state");
    if (stateEl.textContent !== state) stateEl.textContent = state;
  });
  if (speedEl.value !== String(snapshot.speed)) speedEl.value = String(snapshot.speed);
  const voice = snapshot.voices.find((v) => v.id === snapshot.voice);
  document.getElementById("voice-summary").textContent =
    `${voice ? voice.label.split(" — ")[0] : snapshot.voice} · ${speedLabel(snapshot.speed)}`;
}

// "George, 0,8×"
function narrationLabel(narration) {
  const voice = snapshot.voices.find((v) => v.id === narration.voice);
  return `${voice ? voice.label.split(" — ")[0] : narration.voice}, ${String(narration.speed).replace(".", ",")}×`;
}

function renderQueue(queue) {
  document.getElementById("queue-empty").hidden = queue.length !== 0;
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
        if (p.status !== "skipped") {
          li.tabIndex = 0;
          li.setAttribute("role", "button");
          li.addEventListener("keydown", (e) => {
            if (!["Enter", " "].includes(e.key)) return;
            e.preventDefault();
            if (!e.repeat) playFrom(i);
          });
        }
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
      const behavior = matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";
      li.scrollIntoView({ block, behavior });
    }
    li.className = [p.status === "skipped" && "skipped", p.status === "failed" && "failed", current && "current"]
      .filter(Boolean)
      .join(" ");
    li.title = p.error ?? "";
    if (current) li.setAttribute("aria-current", "true");
    else li.removeAttribute("aria-current");
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
  if (blocked && playback.state === "paused") return ["Нажмите «Продолжить», чтобы включить звук", ""];
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

function renderPlayback() {
  const { state, paragraph } = snapshot.playback;
  const active = state === "playing" || state === "waiting";
  playEl.textContent = active ? "Пауза" : state === "paused" ? "Продолжить" : "Воспроизвести";
  playEl.title = active ? "Приостановить (Пробел)" : "Начать или продолжить (Пробел)";
  const readable = (snapshot.text?.paragraphs ?? []).flatMap((p, i) => p.status === "skipped" ? [] : [i]);
  playEl.disabled = readable.length === 0 && !sourceEl.value.trim();
  document.getElementById("stop").disabled = state === "stopped";
  document.getElementById("enqueue").hidden = state !== "stopped";
  const current = readable.indexOf(lingering ?? paragraph);
  progressEl.textContent = current < 0 ? `Абзацев для чтения: ${readable.length}` : `Абзац ${current + 1} из ${readable.length}`;
  for (const id of ["previous", "repeat", "next"]) {
    document.getElementById(id).disabled = readable.length === 0;
  }
}

function render(next) {
  const first = snapshot === null;
  const wasPlaying = document.body.classList.contains("playback");
  snapshot = next;
  // Playback mode: only the Text and the buttons, for the class to read on a projector.
  document.body.classList.toggle("playback", snapshot.playback.state !== "stopped");
  const isPlaying = snapshot.playback.state !== "stopped";
  if (wasPlaying !== isPlaying) {
    closeMenu(false);
    if (document.activeElement.closest("#library-panel, .workspace-header, #source, #enqueue") ||
        (!isPlaying && document.activeElement.id === "stop")) playEl.focus();
  }
  renderVoices();
  renderTextSize();
  const textId = snapshot.text?.id ?? null;
  const textChanged = textId !== shownTextId;
  if ((first || textChanged) && editVersion === savedVersion) {
    sourceEl.value = snapshot.text?.content ?? "";
  }
  if (first || textChanged) shownTextId = textId;
  renderTitle();
  if (first && editVersion === savedVersion) {
    const saveError = snapshot.text?.save_error;
    if (saveError) {
      savedVersion = -1; // the next edit or action retries the save that failed before the reload
      showSaveState("failed", saveError);
    } else {
      showSaveState("saved");
    }
  }
  if (librarySearchEl.value !== snapshot.library_search) librarySearchEl.value = snapshot.library_search;
  renderLibrary(snapshot.library, textId);
  renderQueue(snapshot.queue);
  renderPlayback();
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
  document.getElementById("playback-error-message").textContent = message;
  playbackErrorEl.hidden = false;
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
  actOnTypedText({ command: "play_from", paragraph: index });
}

async function actOnTypedText(body) {
  try {
    const edited = editVersion !== savedVersion;
    await flushEdits();
    await saveTitle();
    if (edited) clearSchedule();
    await act(body);
  } catch (e) {
    showError(e.message);
  }
}

function play() {
  allowSound();
  actOnTypedText({ command: "play" });
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
    await flushEdits();
    if (await command({ command: name })) clearSchedule();
    await refresh();
  } catch (e) {
    showError(e.message);
  }
}

sourceEl.addEventListener("input", () => {
  editVersion++;
  showSaveState("unsaved");
  scheduleSave();
});

titleEl.addEventListener("input", () => {
  titleDirty = true;
  titleActionsEl.hidden = false;
  titleErrorEl.textContent = "";
  titleEl.removeAttribute("aria-invalid");
});

function cancelTitle() {
  titleDirty = false;
  titleErrorEl.textContent = "";
  titleEl.removeAttribute("aria-invalid");
  renderTitle();
  titleEl.focus();
}

document.getElementById("cancel-title").addEventListener("click", cancelTitle);
titleEl.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { e.preventDefault(); cancelTitle(); }
});
document.getElementById("title-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await flushEdits();
    await saveTitle();
    titleEl.focus();
  } catch (error) {
    titleErrorEl.textContent = error.message;
  }
});

document.addEventListener("click", (e) => {
  if (activeMenu && !activeMenu.trigger.contains(e.target) && !activeMenu.menu.contains(e.target)) closeMenu();
});

function togglePlayback() {
  if (["playing", "waiting"].includes(snapshot?.playback.state)) pause();
  else play();
}

playEl.addEventListener("click", togglePlayback);
document.getElementById("dismiss-error").addEventListener("click", () => { playbackErrorEl.hidden = true; });
document.getElementById("previous").addEventListener("click", () => moveParagraph("previous_paragraph"));
document.getElementById("repeat").addEventListener("click", () => moveParagraph("repeat_paragraph"));
document.getElementById("next").addEventListener("click", () => moveParagraph("next_paragraph"));

// Another Speed is another Narration: the core stops the one playing.
speedEl.addEventListener("change", () => {
  clearSchedule();
  act({ command: "set_speed", speed: Number(speedEl.value) });
});

document.getElementById("enqueue").addEventListener("click", () => actOnTypedText({ command: "enqueue" }));

smallerEl.addEventListener("click", () => act({ command: "smaller_text" }));
biggerEl.addEventListener("click", () => act({ command: "bigger_text" }));

// Keys by their place on the keyboard (code), so R works in the Russian layout too.
// Presenter remotes send the arrows or PageUp / PageDown.
const KEYS = {
  Space: togglePlayback,
  ArrowLeft: () => moveParagraph("previous_paragraph"),
  PageUp: () => moveParagraph("previous_paragraph"),
  ArrowRight: () => moveParagraph("next_paragraph"),
  PageDown: () => moveParagraph("next_paragraph"),
  KeyR: () => moveParagraph("repeat_paragraph"),
};

// Playback shortcuts must not steal keys while the teacher types in a field.
function typing(e) {
  const field = e.target;
  const textInput = field.matches("input") && !["radio", "checkbox", "button", "submit"].includes(field.type);
  return textInput || field.matches("textarea") || field.isContentEditable;
}

function usesOwnKeys(e) {
  return typing(e) || e.target.closest("select, summary, #voice-panel, #library-panel, dialog, #title-form") ||
    (e.code === "Space" && e.target.closest("button, [role=button]")) || deleteDialogEl.open;
}

document.addEventListener("keydown", (e) => {
  const key = KEYS[e.code];
  if (!key || e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
  if (e.defaultPrevented || usesOwnKeys(e)) return;
  // The keys also win over a focused button, radio or list, which would otherwise take them too.
  e.preventDefault();
  if (!e.repeat) key();
});

// A focused button is pressed by Space on keyup.
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && !usesOwnKeys(e)) e.preventDefault();
});

librarySearchEl.addEventListener("input", () => {
  act({ command: "search_library", query: librarySearchEl.value });
});

document.getElementById("new-text").addEventListener("click", async () => {
  if (await replaceText({ command: "new_text" })) revealWorkspace();
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
function saveOnPageHide() {
  if (editVersion === savedVersion && !saveInFlight) return;
  // Keep the latest save behind any older one; an independent beacon could reach Core first and then be overwritten.
  command({ command: "set_text", text: sourceEl.value }, true).catch(() => {});
}
window.addEventListener("pagehide", () => {
  saveOnPageHide();
  navigator.sendBeacon("/api/command", heartbeat("page_closing"));
});
document.addEventListener("freeze", () => {
  saveOnPageHide();
  navigator.sendBeacon("/api/command", heartbeat("page_frozen"));
});
document.addEventListener("resume", sendHeartbeat);
setInterval(sendHeartbeat, 5000);
sendHeartbeat();

setInterval(tick, 50);
poll();
