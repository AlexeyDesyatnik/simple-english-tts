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
const librarySearchEl = document.getElementById("library-search");
const librarySizeEl = document.getElementById("library-size");
const queuePanelEl = document.getElementById("queue-panel");
const queueEl = document.getElementById("queue");
const voicePanelEl = document.getElementById("voice-panel");
const sampleStatusEl = document.getElementById("sample-status");
const smallerEl = document.getElementById("smaller");
const biggerEl = document.getElementById("bigger");
const libraryPanelEl = document.getElementById("library-panel");
const workspaceEl = document.getElementById("text-workspace");
const narrowWindow = matchMedia("(max-width: 959px)");
libraryPanelEl.open = !narrowWindow.matches;
libraryPanelEl.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !narrowWindow.matches || !libraryPanelEl.open) return;
  event.preventDefault();
  event.stopPropagation();
  libraryPanelEl.open = false;
  libraryPanelEl.querySelector("summary").focus({ preventScroll: true });
});
const transportEl = document.querySelector(".transport");
const helpEl = document.querySelector(".keyboard-help");
for (const panel of [helpEl, queuePanelEl]) {
  panel.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !panel.open) return;
    event.preventDefault();
    event.stopPropagation();
    panel.open = false;
    panel.querySelector("summary").focus({ preventScroll: true });
  });
}
// Wrapping tools, expanded help and browser zoom all change the sticky panel's height.
new ResizeObserver(() => {
  paragraphsEl.style.setProperty("--transport-offset", `${transportEl.getBoundingClientRect().height + 16}px`);
  keepCurrentVisible();
}).observe(transportEl);
window.addEventListener("resize", () => keepCurrentVisible());

let shownTitle = "Новый текст";

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

const dialogEl = document.getElementById("text-dialog");
const dialogNameEl = document.getElementById("dialog-name");
const dialogErrorEl = document.getElementById("dialog-error");
const dialogSubmitEl = document.getElementById("dialog-submit");
const dialogCancelEl = document.getElementById("dialog-cancel");
const renameTitleEl = document.getElementById("rename-title");
let dialogAction = null;
let dialogOrigin = null;
let dialogRowId = null;
let dialogBusy = false;

function openTextDialog(text, title, description, action, rename = false) {
  dialogOrigin = document.activeElement;
  dialogRowId = dialogOrigin.closest("#library > li")?.dataset.id;
  dialogAction = action;
  dialogBusy = false;
  document.getElementById("dialog-title").textContent = title;
  document.getElementById("dialog-description").textContent = description;
  document.getElementById("rename-field").hidden = !rename;
  dialogNameEl.value = text.title;
  dialogNameEl.removeAttribute("aria-invalid");
  dialogErrorEl.textContent = "";
  dialogSubmitEl.textContent = rename ? "Сохранить" : "Удалить";
  dialogSubmitEl.classList.toggle("destructive", !rename);
  dialogSubmitEl.disabled = false;
  dialogCancelEl.disabled = false;
  dialogEl.showModal();
  if (rename) { dialogNameEl.focus(); dialogNameEl.select(); }
  else dialogCancelEl.focus();
}

// Rows can disappear after deletion or a rename that no longer matches the search.
dialogEl.addEventListener("close", () => {
  let target = dialogOrigin;
  if (dialogRowId) {
    const row = [...libraryEl.children].find((li) => li.dataset.id === dialogRowId);
    target = row?.querySelector("summary") ?? libraryEl.querySelector(".text-title") ?? librarySearchEl;
    if (!libraryPanelEl.open) target = libraryPanelEl.querySelector("summary");
  }
  if (!target?.isConnected || !target.getClientRects().length || target.disabled) target = sourceEl;
  target.focus();
  dialogAction = null;
});
dialogCancelEl.addEventListener("click", () => dialogEl.close());
dialogEl.addEventListener("cancel", (event) => {
  if (dialogBusy) event.preventDefault();
});
dialogEl.addEventListener("keydown", (event) => {
  if (event.key !== "Tab") return;
  const controls = [...dialogEl.querySelectorAll("input, button")].filter((el) => !el.disabled && el.getClientRects().length);
  if (!controls.length) { event.preventDefault(); return; }
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
document.getElementById("dialog-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (dialogBusy) return;
  const rename = !document.getElementById("rename-field").hidden;
  if (rename && !dialogNameEl.value.trim()) {
    dialogErrorEl.textContent = "Введите название текста. Название не может быть пустым.";
    dialogNameEl.setAttribute("aria-invalid", "true");
    dialogNameEl.focus();
    return;
  }
  dialogBusy = true;
  dialogSubmitEl.disabled = true;
  dialogCancelEl.disabled = true;
  dialogEl.setAttribute("aria-busy", "true");
  try {
    await dialogAction(dialogNameEl.value);
    await refresh();
    dialogEl.close();
  } catch (error) {
    dialogErrorEl.textContent = `Не удалось выполнить действие. ${error.message}`;
  } finally {
    dialogBusy = false;
    dialogSubmitEl.disabled = false;
    dialogCancelEl.disabled = false;
    dialogEl.removeAttribute("aria-busy");
  }
});

function renameText(text) {
  openTextDialog(text, "Изменить название", "Название поможет найти текст в Библиотеке.",
    (title) => command({ command: "rename_text", id: text.id, title }), true);
}

function deleteText(text) {
  openTextDialog(text, "Удалить текст?",
    `Текст «${text.title}» и его озвучки будут удалены из Библиотеки. Его озвучки будут убраны из очереди озвучки. Если этот текст открыт, воспроизведение остановится. Отменить удаление нельзя.`,
    async () => {
      clearSchedule();
      await command({ command: "delete_text", id: text.id });
      if (shownTextId === text.id) sourceEl.value = "";
    });
}

function deleteNarration(text, narration) {
  openTextDialog(text, "Удалить озвучку?",
    `Озвучка «${narrationLabel(narration)}» текста «${text.title}» будет удалена и убрана из очереди озвучки. Если она воспроизводится, воспроизведение остановится. Сам текст останется в Библиотеке; озвучку можно подготовить заново.`,
    () => { clearSchedule(); return command({ command: "delete_narration", id: text.id, voice: narration.voice, speed: narration.speed }); });
}

renameTitleEl.addEventListener("click", () => renameText({ id: snapshot.text.id, title: shownTitle }));

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1).replace(".", ",")} КБ`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1).replace(".", ",")} МБ`;
  return `${(bytes / 1024 ** 3).toFixed(1).replace(".", ",")} ГБ`;
}

function renderLibrary(library, currentId) {
  librarySizeEl.textContent = snapshot.library_bytes === null ? "Размер Библиотеки неизвестен" : `Библиотека · ${formatBytes(snapshot.library_bytes)}`;
  const searching = Boolean(snapshot.library_search);
  document.getElementById("library-empty").hidden = library.length > 0;
  document.getElementById("library-empty-title").textContent = searching ? "Ничего не найдено" : "В Библиотеке пока нет текстов";
  document.getElementById("library-empty-help").textContent = searching
    ? "Измените запрос или очистите поле поиска."
    : "Нажмите «Новый текст», вставьте текст и запустите воспроизведение или подготовку озвучки.";
  const key = JSON.stringify(library);
  if (key !== shownLibrary) {
    const focusedRow = document.activeElement?.closest("#library > li");
    const focusedId = focusedRow?.dataset.id;
    const focusedTitle = document.activeElement?.classList.contains("text-title");
    const openId = libraryEl.querySelector(".row-actions[open]")?.closest("li").dataset.id;
    shownLibrary = key;
    libraryEl.replaceChildren(
      ...library.map((t) => {
        const li = document.createElement("li");
        li.dataset.id = t.id;
        const row = document.createElement("div");
        row.className = "library-text";
        const open = document.createElement("button");
        open.type = "button";
        open.className = "text-title";
        const titleLabel = document.createElement("span");
        titleLabel.className = "library-title-label";
        titleLabel.textContent = t.title;
        open.append(titleLabel);
        open.title = t.title;
        open.dataset.id = t.id;
        open.addEventListener("click", async () => {
          clearSchedule();
          await act({ command: "open_text", id: t.id });
        });
        const rename = document.createElement("button");
        rename.type = "button";
        rename.className = "secondary library-action";
        rename.textContent = "Переименовать";
        rename.addEventListener("click", () => renameText(t));
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "secondary library-action destructive";
        remove.textContent = "Удалить текст и озвучки";
        remove.addEventListener("click", () => deleteText(t));
        const actions = document.createElement("details");
        actions.className = "row-actions";
        actions.open = t.id === openId;
        const menu = document.createElement("summary");
        menu.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>';
        menu.setAttribute("aria-label", `Действия с текстом «${t.title}»`);
        actions.append(menu, rename, remove);
        actions.addEventListener("toggle", () => {
          if (actions.open) {
            for (const other of libraryEl.querySelectorAll(".row-actions[open]")) {
              if (other !== actions) other.open = false;
            }
          }
        });
        actions.addEventListener("keydown", (event) => {
          if (event.key === "Tab") {
            // Let native focus move before hiding any of its current controls.
            setTimeout(() => {
              if (!actions.contains(document.activeElement)) actions.open = false;
            }, 0);
          }
          if (event.key !== "Escape" || !actions.open) return;
          event.preventDefault();
          event.stopPropagation();
          actions.open = false;
          menu.focus({ preventScroll: true });
        });
        row.append(open, actions);

        const narrations = document.createElement("div");
        narrations.className = "library-narrations";
        for (const n of t.narrations) {
          const label = narrationLabel(n);
          const ready = document.createElement("span");
          ready.className = "ready-narration";
          const removeNarration = document.createElement("button");
          removeNarration.type = "button";
          removeNarration.className = "secondary library-action destructive";
          removeNarration.textContent = `Удалить озвучку · ${label}`;
          removeNarration.title = `Удалить озвучку ${label}`;
          removeNarration.setAttribute("aria-label", `Удалить озвучку ${label} текста «${t.title}»`);
          removeNarration.addEventListener("click", () => deleteNarration(t, n));
          ready.textContent = `Готово · ${label}`;
          narrations.append(ready);
          actions.append(removeNarration);
        }
        li.append(row, narrations);
        return li;
      }),
    );
    if (focusedId) {
      const replacement = [...libraryEl.children].find((li) => li.dataset.id === focusedId);
      const target = replacement?.querySelector(focusedTitle ? ".text-title" : "summary")
        ?? libraryEl.querySelector(".text-title") ?? librarySearchEl;
      target.focus({ preventScroll: true });
    }
  }
  for (const button of libraryEl.querySelectorAll(".text-title")) {
    button.classList.toggle("current", button.dataset.id === currentId);
    if (button.dataset.id === currentId) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
}

document.addEventListener("click", (event) => {
  for (const actions of libraryEl.querySelectorAll(".row-actions[open]")) {
    if (!actions.contains(event.target)) actions.open = false;
  }
});

// "0,8×"; normal Speed is named so the teacher can find the way back to it
function speedLabel(speed) {
  return speed === 1 ? "1× — обычная" : `${String(speed).replace(".", ",")}×`;
}

// A Voice sample is ready-made: the core hands it over without synthesizing anything.
function playSample(voiceId) {
  sample?.pause();
  const clip = new Audio(`/api/sample/${encodeURIComponent(voiceId)}`);
  sample = clip;
  const name = snapshot.voices.find((v) => v.id === voiceId)?.label.split(" — ")[0] ?? voiceId;
  sampleStatusEl.textContent = `Загрузка образца · ${name}…`;
  clip.addEventListener("ended", () => {
    if (sample === clip) sampleStatusEl.textContent = `Образец прослушан · ${name}`;
  });
  clip.play().then(() => {
    if (sample === clip) sampleStatusEl.textContent = `Звучит образец · ${name}`;
  }).catch(() => {
    if (sample === clip) sampleStatusEl.textContent = `Не получилось проиграть образец · ${name}. Попробуйте ещё раз.`;
  });
}

function closeVoicePanel() {
  voicePanelEl.open = false;
  voicePanelEl.querySelector("summary").focus({ preventScroll: true });
}

async function chooseVoice(voiceId) {
  try {
    if (voiceId !== snapshot.voice) {
      // Another Voice is another Narration: the core stops the one playing.
      clearSchedule();
      await command({ command: "set_voice", voice: voiceId });
      await refresh();
    }
    closeVoicePanel();
  } catch (error) {
    showError(error.message);
  }
}

voicePanelEl.addEventListener("keydown", (event) => {
  if (!voicePanelEl.open) return;
  const direction = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[event.key];
  if (direction && !event.altKey && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    event.stopPropagation();
    const choices = [...voicesEl.querySelectorAll(".voice-choice")];
    const current = event.target.closest("#voices > li")?.querySelector(".voice-choice");
    const selected = choices.findIndex((choice) => choice.dataset.voice === snapshot.voice);
    const index = current ? (choices.indexOf(current) + direction + choices.length) % choices.length : Math.max(0, selected);
    choices[index]?.focus();
    return;
  }
  if (event.key !== "Escape" || !voicePanelEl.open) return;
  event.preventDefault();
  event.stopPropagation();
  closeVoicePanel();
});
voicePanelEl.addEventListener("focusout", (event) => {
  if (event.relatedTarget && !voicePanelEl.contains(event.relatedTarget)) voicePanelEl.open = false;
});
document.addEventListener("click", (event) => {
  if (!voicePanelEl.contains(event.target)) voicePanelEl.open = false;
});

function renderVoices() {
  const selectedVoice = snapshot.voices.find((v) => v.id === snapshot.voice);
  const availability = snapshot.voices_loading ? "загрузка…" : selectedVoice?.available ? "доступен" : "недоступен";
  document.getElementById("selected-voice").textContent = `${selectedVoice?.label.split(" — ")[0] ?? "Не выбран"} · ${availability}`;
  document.getElementById("voice-availability").textContent = snapshot.voices_loading
    ? "Голоса загружаются. Готовые озвучки и образцы можно слушать."
    : snapshot.voices.some((v) => !v.available)
      ? "Недоступный голос сейчас не может подготовить новую озвучку. Готовые озвучки и образцы можно слушать."
      : "Голоса доступны для подготовки озвучки.";
  // Availability changes update existing rows, preserving keyboard focus during loading.
  const key = JSON.stringify([snapshot.voices.map((v) => [v.id, v.label]), snapshot.speeds]);
  if (key !== shownVoices) {
    shownVoices = key;
    voicesEl.replaceChildren(
      ...snapshot.voices.map((v) => {
        const li = document.createElement("li");
        const choice = document.createElement("button");
        choice.type = "button";
        choice.className = "secondary voice-choice";
        choice.dataset.voice = v.id;
        choice.addEventListener("click", () => chooseVoice(v.id));
        const description = document.createElement("span");
        description.textContent = v.label;
        const availability = document.createElement("span");
        availability.className = "voice-state muted";
        choice.append(description, availability);
        const listen = document.createElement("button");
        listen.type = "button";
        listen.className = "secondary";
        listen.textContent = "Послушать";
        listen.setAttribute("aria-label", `Послушать образец · ${v.label.split(" — ")[0]}`);
        listen.addEventListener("click", () => playSample(v.id));
        li.append(choice, listen);
        return li;
      }),
    );
    speedEl.replaceChildren(...snapshot.speeds.map((s) => new Option(speedLabel(s), String(s))));
  }
  snapshot.voices.forEach((v, i) => {
    const row = voicesEl.children[i];
    row.querySelector(".voice-choice").setAttribute("aria-pressed", String(v.id === snapshot.voice));
    const availability = snapshot.voices_loading ? "Загрузка…" : v.available ? "Доступен" : "Недоступен";
    row.querySelector(".voice-state").textContent = `${v.id === snapshot.voice ? "Выбран · " : ""}${availability}`;
  });
  if (speedEl.value !== String(snapshot.speed)) speedEl.value = String(snapshot.speed);
}

// "George, 0,8×"
function narrationLabel(narration) {
  const voice = snapshot.voices.find((v) => v.id === narration.voice);
  return `${voice ? voice.label.split(" — ")[0] : narration.voice}, ${String(narration.speed).replace(".", ",")}×`;
}

function renderQueue(queue) {
  const active = queue.filter((n) => n.synthesizing).length;
  document.getElementById("queue-count").textContent = queue.length
    ? `${queue.length} · ${active ? "готовится" : "ожидает подготовки"}` : "пуста";
  document.getElementById("queue-empty").hidden = queue.length > 0;
  document.getElementById("queue-cancel-help").hidden = queue.length === 0;
  const key = JSON.stringify(queue.map((n) => n.id));
  if (key !== shownQueue) {
    const focusedId = document.activeElement?.closest("#queue > li")?.dataset.id;
    shownQueue = key;
    queueEl.replaceChildren(
      ...queue.map((n) => {
        const li = document.createElement("li");
        li.dataset.id = n.id;
        const title = document.createElement("span");
        title.className = "title";
        title.textContent = `${n.title} · ${narrationLabel(n)}`;
        const left = document.createElement("span");
        left.className = "muted";
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "secondary";
        cancel.textContent = "Отменить";
        cancel.setAttribute("aria-label", `Отменить подготовку · ${n.title} · ${narrationLabel(n)}`);
        cancel.setAttribute("aria-describedby", "queue-cancel-help");
        cancel.addEventListener("click", () => act({ command: "cancel", narration: n.id }));
        li.append(title, left, cancel);
        return li;
      }),
    );
    if (focusedId) {
      const replacement = [...queueEl.children].find((li) => li.dataset.id === focusedId);
      (replacement?.querySelector("button") ?? queuePanelEl.querySelector("summary")).focus({ preventScroll: true });
    }
  }
  queue.forEach((n, i) => {
    const state = n.synthesizing ? "Готовится" : "В очереди";
    const left = n.ready_in === null ? " · время пока неизвестно" : ` · готово через ${formatDuration(n.ready_in)}`;
    queueEl.children[i].querySelector(".muted").textContent = state + left;
  });
}

function renderParagraphs(text, textSizeChanged) {
  if (text?.content !== shownContent) {
    shownContent = text?.content ?? null;
    paragraphsEl.replaceChildren(
      ...(text?.paragraphs ?? []).map((p, i) => {
        const li = document.createElement("li");
        const content = document.createElement("span");
        content.textContent = p.text;
        const error = document.createElement("span");
        error.className = "paragraph-error";
        li.append(content, error);
        if (p.status !== "skipped") {
          li.tabIndex = 0;
          li.setAttribute("role", "button");
          li.addEventListener("keydown", (event) => {
            if (event.code !== "Enter" && event.code !== "Space") return;
            event.preventDefault();
            event.stopPropagation();
            playFrom(i);
          });
        }
        li.addEventListener("click", () => playFrom(i));
        return li;
      }),
    );
  }
  const playback = snapshot.playback;
  const highlighted = lingering ?? playback.paragraph ?? playback.ended_at;
  (text?.paragraphs ?? []).forEach((p, i) => {
    const li = paragraphsEl.children[i];
    const current = highlighted === i;
    const moved = current && !li.classList.contains("current");
    li.className = [p.status === "skipped" && "skipped", p.status === "failed" && "failed", current && "current"]
      .filter(Boolean)
      .join(" ");
    li.querySelector(".paragraph-error").textContent = p.status === "failed"
      ? `Не удалось озвучить: ${p.error}. Нажмите на абзац, чтобы повторить попытку.` : "";
    if (current) li.setAttribute("aria-current", "true");
    else li.removeAttribute("aria-current");
    if (moved || (current && textSizeChanged)) requestAnimationFrame(() => keepCurrentVisible(true));
  });
}

// Scroll within the space below the sticky controls, including at large Text sizes.
function keepCurrentVisible(center = false) {
  if (!document.body.classList.contains("playback")) return;
  const current = paragraphsEl.querySelector(".current");
  if (!current) return;
  const panelHeight = transportEl.getBoundingClientRect().height;
  const top = panelHeight + 16;
  const rect = current.getBoundingClientRect();
  const available = Math.max(0, innerHeight - top - 16);
  if (!center && rect.top >= top && (rect.bottom <= innerHeight - 16 || rect.height > available)) return;
  const offset = rect.height < available ? (available - rect.height) / 2 : 0;
  window.scrollBy({ top: rect.top - top - offset, behavior: "instant" });
}

// "~1 мин 20 с", "~45 с"
function formatDuration(seconds) {
  const s = Math.max(1, Math.ceil(seconds));
  const minutes = Math.floor(s / 60);
  return minutes ? `~${minutes} мин ${s % 60} с` : `~${s} с`;
}

function statusText(text, playback) {
  if (snapshot.library_error) return [snapshot.library_error, "error"];
  if (playback.state === "stopped" && sourceEl.value !== (text?.content ?? "")) {
    return ["Текст изменён. Будет сохранён при запуске или подготовке озвучки.", ""];
  }
  if (!text) return ["", ""];
  const readable = text.paragraphs.filter((p) => p.status !== "skipped");
  const failed = readable.find((p) => p.status === "failed");
  if (failed) return [`Не получилось озвучить абзац: ${failed.error}`, "error"];
  if (playback.ended_at != null) return ["Текст прочитан", ""];
  if (blocked && playback.state === "paused") return ["Нажмите «Продолжить», чтобы продолжить", ""];
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
  if (readable.length && ready === readable.length) parts.push(`Озвучка готова · ${ready} из ${readable.length} абзацев`);
  return [parts.join(" · "), ""];
}

function renderTextSize() {
  const changed = paragraphsEl.style.fontSize !== `${snapshot.text_size}px`;
  paragraphsEl.style.fontSize = `${snapshot.text_size}px`;
  document.getElementById("text-size-label").textContent = `Текст · ${snapshot.text_size}`;
  const at = snapshot.text_sizes.indexOf(snapshot.text_size);
  smallerEl.disabled = at <= 0;
  biggerEl.disabled = at === snapshot.text_sizes.length - 1;
  return changed;
}

function render(next) {
  const first = snapshot === null;
  const wasReading = document.body.classList.contains("playback");
  const startingPlayback = snapshot?.playback.state === "stopped" && next.playback.state !== "stopped";
  snapshot = next;
  // Playback mode: only the Text and the buttons, for the class to read on a projector.
  document.body.classList.toggle("playback", snapshot.playback.state !== "stopped" || snapshot.playback.ended_at != null);
  renderVoices();
  const textSizeChanged = renderTextSize();
  const textId = snapshot.text?.id ?? null;
  if (first || textId !== shownTextId) {
    shownTextId = textId;
    if (first || textId !== null) sourceEl.value = snapshot.text?.content ?? "";
  }
  if (librarySearchEl.value !== snapshot.library_search) librarySearchEl.value = snapshot.library_search;
  renderLibrary(snapshot.library, textId);
  shownTitle = snapshot.text?.title ?? "Новый текст";
  renameTitleEl.hidden = !textId;
  document.getElementById("text-title").textContent = shownTitle;
  document.getElementById("text-title").title = shownTitle;
  const playing = ["playing", "waiting"].includes(snapshot.playback.state);
  document.getElementById("play").textContent = playing ? "Пауза"
    : snapshot.playback.state === "paused" ? "Продолжить" : "Воспроизвести";
  const readable = snapshot.text?.paragraphs.filter((p) => p.status !== "skipped") ?? [];
  const current = snapshot.text?.paragraphs[lingering ?? snapshot.playback.paragraph ?? snapshot.playback.ended_at];
  document.getElementById("position").textContent = !current || !readable.length ? ""
    : `Абзац ${readable.indexOf(current) + 1} из ${readable.length}`;
  renderQueue(snapshot.queue);
  renderParagraphs(snapshot.text, textSizeChanged);
  if (document.body.classList.contains("playback") && (!wasReading || startingPlayback)) {
    workspaceEl.focus({ preventScroll: true });
  }
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

document.getElementById("play").addEventListener("click", () => {
  if (["playing", "waiting"].includes(snapshot?.playback.state)) pause();
  else play();
});
for (const [id, name] of [["previous", "previous_paragraph"], ["repeat", "repeat_paragraph"], ["next", "next_paragraph"]]) {
  document.getElementById(id).addEventListener("click", () => moveParagraph(name));
}

// Another Speed is another Narration: the core stops the one playing.
speedEl.addEventListener("change", () => {
  clearSchedule();
  act({ command: "set_speed", speed: Number(speedEl.value) });
});

document.getElementById("enqueue").addEventListener("click", () => actOnTypedText("enqueue"));

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

// Native controls and custom interactive widgets own their keyboard input.
const INTERACTIVE = [
  "input", "textarea", "select", "button", "summary", "a[href]", "audio[controls]", "video[controls]",
  "[role=button]", "[role=checkbox]", "[role=radio]", "[role=combobox]", "[role=listbox]", "[role=option]",
  "[role=menu]", "[role=menuitem]", "[role=slider]", "[role=spinbutton]", "[role=switch]", "[role=tab]",
  "[role=tree]", "[role=treeitem]", "[role=textbox]", "[contenteditable]:not([contenteditable=false])", "[tabindex]",
].join(", ");
function typing(e) {
  // The reading surface receives shortcuts; its interactive descendants keep their own keys.
  if (e.target === workspaceEl) return false;
  return e.target.closest(INTERACTIVE) || e.target.isContentEditable;
}

document.addEventListener("keydown", (e) => {
  const key = KEYS[e.code];
  if (!key || e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
  if (e.defaultPrevented || e.isComposing || dialogEl.open || typing(e)) return;
  // Native controls keep their own keys; the reading background handles playback shortcuts.
  e.preventDefault();
  if (!e.repeat) key();
});

// A focused button is pressed by Space on keyup.
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && !dialogEl.open && !typing(e)) e.preventDefault();
});

librarySearchEl.addEventListener("input", () => {
  act({ command: "search_library", query: librarySearchEl.value });
});

document.getElementById("new-text").addEventListener("click", () => {
  clearSchedule();
  sourceEl.value = "";
  if (!narrowWindow.matches) sourceEl.focus();
  act({ command: "new_text" });
});

document.getElementById("stop").addEventListener("click", async () => {
  clearSchedule();
  await act({ command: "stop" });
  sourceEl.focus();
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
