// The page is only a view (ADR-0003): it sends commands, renders the polled snapshot
// and plays the audio the core has made.

const statusEl = document.getElementById("status");
const voiceEl = document.getElementById("voice");

let audioContext = null;
let awaited = null; // id of the phrase Play was pressed for: sound never starts without Play, and plays once

async function command(body) {
  const response = await fetch("/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const reply = await response.json();
  if (!response.ok) throw new Error(reply.error);
  return reply.result;
}

async function play(audioId) {
  const response = await fetch(`/api/audio/${audioId}`);
  const buffer = await audioContext.decodeAudioData(await response.arrayBuffer());
  const source = audioContext.createBufferSource();
  source.buffer = buffer;
  source.connect(audioContext.destination);
  source.start();
}

function render(snapshot) {
  const voice = snapshot.voices.find((v) => v.id === snapshot.voice);
  voiceEl.textContent = voice ? `Голос: ${voice.label}` : "";
  const phrase = snapshot.phrase;
  statusEl.className = "";
  if (!phrase) {
    statusEl.textContent = "";
  } else if (phrase.status === "synthesizing") {
    statusEl.textContent = "Готовлю озвучку…";
  } else if (phrase.status === "failed") {
    statusEl.textContent = `Не получилось озвучить: ${phrase.error}`;
    statusEl.className = "error";
  } else {
    statusEl.textContent = "Готово";
    if (phrase.id === awaited) {
      awaited = null;
      play(phrase.audio).catch((e) => (statusEl.textContent = `Ошибка воспроизведения: ${e.message}`));
    }
  }
}

async function poll() {
  try {
    render(await (await fetch("/api/state")).json());
  } catch (e) {
    statusEl.textContent = "Нет связи с программой";
    statusEl.className = "error";
  }
  setTimeout(poll, 500);
}

document.getElementById("speak").addEventListener("submit", async (event) => {
  event.preventDefault();
  // Created inside the click, so the browser allows it to play sound later.
  audioContext ??= new AudioContext();
  await audioContext.resume();
  try {
    awaited = await command({ command: "speak", text: document.getElementById("phrase").value });
  } catch (e) {
    statusEl.textContent = e.message;
    statusEl.className = "error";
  }
});

poll();
