// REA Mobile front end. Talks to server.mjs on the same origin.

const $ = (id) => document.getElementById(id);
const store = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* storage unavailable (private mode); keep going in memory */
    }
  },
};

const QUICK_ACTIONS = [
  { label: "Doctor", command: "doctor" },
  { label: "Inspect file", command: "inspect-artifact" },
  { label: "Android APK", command: "inspect-android-package" },
  { label: "JS / Electron app", command: "analyze-javascript-application" },
  { label: "App overview", command: "analyze" },
  { label: "Go binary", command: "inspect-go-binary" },
  { label: ".NET assembly", command: "inspect-managed-artifact" },
  { label: "Providers", command: "providers" },
];
const MAX_HISTORY = 50;
const MAX_SAVED_OUTPUT = 200_000;

let token = store.get("token", "");
let commands = [];
let running = null;

// A token passed in the link fragment (#token=...) never reaches server logs.
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.get("token")) {
  token = fragment.get("token");
  store.set("token", token);
  history.replaceState(null, "", location.pathname);
}

function api(path, options = {}) {
  return fetch(path, {
    ...options,
    headers: { ...(options.headers || {}), authorization: `Bearer ${token}` },
  });
}

function setStatus(text, kind) {
  const el = $("status");
  el.textContent = text;
  el.className = `status ${kind || ""}`;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  if (name === "history") renderHistory();
}

/** Split a shell-like option string, honouring single and double quotes. */
function splitArgs(text) {
  const args = [];
  const re = /"((?:\\.|[^"\\])*)"|'([^']*)'|(\S+)/g;
  let match;
  while ((match = re.exec(text))) {
    args.push(match[1] !== undefined ? match[1].replace(/\\(.)/g, "$1") : (match[2] ?? match[3]));
  }
  return args;
}

function buildArgs() {
  const args = [];
  const target = $("target").value.trim();
  if (target) {
    // `doctor` takes its target as an option; other commands take it positionally.
    if ($("command").value.trim() === "doctor") args.push("--target");
    args.push(target);
  }
  args.push(...splitArgs($("extra").value));
  const format = $("format").value;
  if (format && !args.includes("--format")) args.push("--format", format);
  return args;
}

function describeCommand() {
  const found = commands.find((c) => c.name === $("command").value.trim());
  $("command-desc").textContent = found ? found.description : "";
}

async function connect() {
  if (!token) {
    setStatus("No token", "err");
    showView("settings");
    $("server-info").textContent = "Paste the token printed by server.mjs, or open the link it prints.";
    return;
  }
  setStatus("Connecting…");
  try {
    const res = await api("/api/info");
    if (res.status === 401) throw new Error("Token rejected");
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const info = await res.json();
    commands = info.commands;
    $("command-list").innerHTML = commands
      .map((c) => `<option value="${c.name}">${c.description.replace(/"/g, "&quot;")}</option>`)
      .join("");
    $("server-info").innerHTML =
      `<strong>Connected</strong><p>${commands.length} REA commands available.<br>` +
      `REA: <code></code><br>Uploads: <code></code></p>`;
    const codes = $("server-info").querySelectorAll("code");
    codes[0].textContent = info.rea;
    codes[1].textContent = info.uploads;
    setStatus("Connected", "ok");
    describeCommand();
  } catch (error) {
    setStatus("Offline", "err");
    $("server-info").textContent = `Could not connect: ${error.message}`;
  }
}

async function run() {
  const command = $("command").value.trim();
  if (!command) return void $("command").focus();
  const args = buildArgs();
  const output = $("output");
  output.textContent = "";
  $("output-label").textContent = `rea ${command} ${args.join(" ")}`;
  $("run-btn").disabled = true;
  $("stop-btn").hidden = false;
  output.scrollIntoView({ behavior: "smooth", block: "start" });

  const controller = new AbortController();
  running = controller;
  const started = Date.now();
  let text = "";
  try {
    const res = await api("/api/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ command, args }),
      signal: controller.signal,
    });
    if (!res.ok) {
      text = (await res.json().catch(() => ({}))).error || `Server error ${res.status}`;
    } else {
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        text += value;
        const atBottom = output.scrollHeight - output.scrollTop - output.clientHeight < 40;
        output.textContent = text;
        if (atBottom) output.scrollTop = output.scrollHeight;
      }
    }
  } catch (error) {
    text += controller.signal.aborted ? "\n[stopped]\n" : `\n[error] ${error.message}\n`;
  } finally {
    output.textContent = text;
    running = null;
    $("run-btn").disabled = false;
    $("stop-btn").hidden = true;
  }

  const entries = store.get("history", []);
  entries.unshift({
    command,
    target: $("target").value.trim(),
    extra: $("extra").value,
    format: $("format").value,
    at: started,
    ms: Date.now() - started,
    output: text.slice(-MAX_SAVED_OUTPUT),
  });
  store.set("history", entries.slice(0, MAX_HISTORY));
}

function renderHistory() {
  const list = $("history");
  const entries = store.get("history", []);
  list.innerHTML = entries.length ? "" : '<li class="meta">No runs yet.</li>';
  entries.forEach((entry, index) => {
    const li = document.createElement("li");
    li.innerHTML =
      '<div class="cmd"></div><div class="meta"></div>' +
      '<div class="row"><button class="secondary" data-act="view">View</button>' +
      '<button class="secondary" data-act="load">Edit &amp; rerun</button></div>';
    li.querySelector(".cmd").textContent = `${entry.command} ${entry.target} ${entry.extra}`.trim();
    li.querySelector(".meta").textContent =
      `${new Date(entry.at).toLocaleString()} · ${(entry.ms / 1000).toFixed(1)}s`;
    li.addEventListener("click", (event) => {
      const act = event.target.dataset?.act;
      if (!act) return;
      const e = store.get("history", [])[index];
      $("command").value = e.command;
      $("target").value = e.target;
      $("extra").value = e.extra;
      $("format").value = e.format;
      describeCommand();
      if (act === "view") {
        $("output").textContent = e.output;
        $("output-label").textContent = `rea ${e.command} (saved)`;
      }
      showView("run");
    });
    list.appendChild(li);
  });
}

async function upload(file) {
  const progress = $("upload-progress");
  progress.textContent = `Uploading ${file.name}…`;
  // XHR (not fetch) so large files report progress on mobile browsers.
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/upload?name=${encodeURIComponent(file.name)}`);
  xhr.setRequestHeader("authorization", `Bearer ${token}`);
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) progress.textContent = `Uploading ${file.name}… ${Math.round((e.loaded / e.total) * 100)}%`;
  };
  xhr.onload = () => {
    const body = JSON.parse(xhr.responseText || "{}");
    if (xhr.status === 200) {
      $("target").value = body.path;
      progress.textContent = `Uploaded to computer (${(body.size / 1048576).toFixed(1)} MB)`;
    } else {
      progress.textContent = `Upload failed: ${body.error || xhr.status}`;
    }
  };
  xhr.onerror = () => (progress.textContent = "Upload failed: network error");
  xhr.send(file);
}

async function showHelp() {
  const command = $("command").value.trim();
  if (!command) return void $("command").focus();
  $("output-label").textContent = `rea ${command} --help`;
  $("output").textContent = "Loading…";
  const res = await api(`/api/help?command=${encodeURIComponent(command)}`);
  const body = await res.json();
  $("output").textContent = body.help || body.error;
}

// Wire up UI
$("quick").innerHTML = QUICK_ACTIONS.map((q, i) => `<button type="button" data-i="${i}">${q.label}</button>`).join("");
$("quick").addEventListener("click", (event) => {
  const action = QUICK_ACTIONS[event.target.dataset.i];
  if (!action) return;
  $("command").value = action.command;
  describeCommand();
  if (action.command !== "doctor" && action.command !== "providers") $("target").focus();
});
$("command").addEventListener("input", describeCommand);
$("run-btn").addEventListener("click", run);
$("stop-btn").addEventListener("click", () => running?.abort());
$("help-btn").addEventListener("click", showHelp);
$("upload-btn").addEventListener("click", () => $("upload-file").click());
$("upload-file").addEventListener("change", (e) => e.target.files[0] && upload(e.target.files[0]));
$("copy-btn").addEventListener("click", () => navigator.clipboard?.writeText($("output").textContent));
$("share-btn").addEventListener("click", () => {
  const text = $("output").textContent;
  if (navigator.share) navigator.share({ title: $("output-label").textContent, text }).catch(() => {});
  else navigator.clipboard?.writeText(text);
});
$("clear-history").addEventListener("click", () => {
  store.set("history", []);
  renderHistory();
});
$("token").value = token;
$("save-token").addEventListener("click", () => {
  token = $("token").value.trim();
  store.set("token", token);
  connect().then(() => commands.length && showView("run"));
});
$("reload-commands").addEventListener("click", async () => {
  await api("/api/commands/reload", { method: "POST" });
  connect();
});
document.querySelectorAll(".tabbar button").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
connect();
