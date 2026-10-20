// REA Mobile front end. It always talks to the REA server on its own origin:
// server.mjs in a browser, or inside the Android app (window.ReaAndroid present)
// either REA running on the phone (page at http://127.0.0.1:<port>) or the
// computer's server.mjs page, which the app opens directly in computer mode.

import { createDocs } from "./docs.js";

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

const android = window.ReaAndroid || null;

const COMPUTER_ACTIONS = [
  { label: "Doctor", command: "doctor" },
  { label: "Inspect file", command: "inspect-artifact" },
  { label: "Android APK", command: "inspect-android-package" },
  { label: "JS / Electron app", command: "analyze-javascript-application" },
  { label: "App overview", command: "analyze" },
  { label: "Go binary", command: "inspect-go-binary" },
  { label: ".NET assembly", command: "inspect-managed-artifact" },
  { label: "Providers", command: "providers" },
];
// Analyses REA can run on the phone itself: its built-in parsers, no desktop engines.
const PHONE_ACTIONS = [
  { label: "Phone app", command: "inspect-artifact", pickApp: true },
  { label: "Inspect file", command: "inspect-artifact" },
  { label: "Flutter app", command: "identify-flutter-build" },
  { label: "SQLite database", command: "inspect-sqlite-database" },
  { label: "JS / Electron app", command: "analyze-javascript-application" },
  { label: "Go binary", command: "inspect-go-binary" },
  { label: "Rust binary", command: "inspect-rust-binary" },
  { label: ".NET assembly", command: "inspect-managed-artifact" },
  { label: "Doctor", command: "doctor" },
];
const MAX_HISTORY = 50;
const MAX_SAVED_OUTPUT = 200_000;

const androidConfig = android ? JSON.parse(android.getConfig()) : null;
const mode = !android ? "browser" : location.origin === androidConfig.localBase ? "phone" : "computer";
let token = store.get("token", "");
let commands = [];
let running = null;
let connectTimer = null;
const docs = createDocs({ list: $("docs-list"), reader: $("docs-reader"), search: $("docs-search"), back: $("docs-back") });

// A token passed in the link fragment (#token=...) never reaches server logs.
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.get("token")) {
  token = fragment.get("token");
  store.set("token", token);
  history.replaceState(null, "", location.pathname);
}

function authToken() {
  return mode === "phone" ? androidConfig.localToken : token;
}

function api(path, options = {}) {
  return fetch(path, {
    ...options,
    headers: { ...(options.headers || {}), authorization: `Bearer ${authToken()}` },
  });
}

/** Accept a pasted link like http://192.168.1.20:8787/#token=abc. */
function parseComputerLink(text) {
  try {
    const url = new URL(text.trim());
    const linkToken = new URLSearchParams(url.hash.slice(1)).get("token");
    if (!/^https?:$/.test(url.protocol) || !linkToken) return null;
    return { base: url.origin, token: linkToken };
  } catch {
    return null;
  }
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
  if (name === "docs") docs.load();
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

function quickActions() {
  return mode === "phone" ? PHONE_ACTIONS : COMPUTER_ACTIONS;
}

function renderModeUi() {
  $("quick").innerHTML = quickActions()
    .map((q, i) => `<button type="button" data-i="${i}">${q.label}</button>`)
    .join("");
  $("target-label").textContent = mode === "phone" ? "Target path on this phone" : "Target path on computer";
  $("upload-btn").textContent = mode === "phone" ? "Choose file" : "Upload";
  $("mode-card").hidden = !android;
  $("token-fields").hidden = mode !== "browser";
  $("computer-fields").hidden = mode !== "computer";
  document.querySelectorAll('input[name="mode"]').forEach((r) => (r.checked = r.value === mode));
  if (android && androidConfig.computerBase) {
    $("computer-link").value = `${androidConfig.computerBase}/#token=${androidConfig.computerToken}`;
  }
}

async function connect() {
  clearTimeout(connectTimer);
  if (mode === "browser" && !token) {
    setStatus("No token", "err");
    showView("settings");
    $("server-info").textContent = "Paste the token printed by server.mjs, or open the link it prints.";
    return;
  }
  if (mode === "phone") {
    if (location.hash === "#computer-unreachable") {
      history.replaceState(null, "", location.pathname);
      alert("Couldn't reach your computer, so REA is running on this phone. Check that server.mjs is running and the phone is on the same Wi-Fi, then pick My computer in Settings again.");
    }
    // REA unpacks itself on first launch; keep checking until its server answers.
    // If another app took REA's port, the runtime moved; follow it.
    const current = JSON.parse(android.getConfig()).localBase;
    if (current !== location.origin) return void location.replace(`${current}/index.html`);
    const state = android.runtimeStatus();
    if (state !== "running") {
      setStatus(state.startsWith("error") ? "REA failed" : "Starting REA…", state.startsWith("error") ? "err" : "");
      $("server-info").textContent = state.startsWith("error")
        ? `REA could not start on this phone: ${state.slice(6)}`
        : `Preparing REA on this phone (${state}). The first launch takes a little while.`;
      if (!state.startsWith("error")) connectTimer = setTimeout(connect, 1000);
      return;
    }
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
    const where = mode === "phone" ? "on this phone" : mode === "computer" ? "on your computer" : "";
    $("server-info").innerHTML =
      `<strong>Connected ${where}</strong><p>${commands.length} REA commands available.<br>` +
      `REA: <code></code><br>Files: <code></code></p>`;
    const codes = $("server-info").querySelectorAll("code");
    codes[0].textContent = info.rea;
    codes[1].textContent = info.uploads;
    setStatus(mode === "phone" ? "On phone" : "Connected", "ok");
    describeCommand();
  } catch (error) {
    setStatus("Offline", "err");
    $("server-info").textContent = `Could not connect: ${error.message}`;
    if (mode === "phone") connectTimer = setTimeout(connect, 2000);
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
  const verb = mode === "phone" ? "Copying" : "Uploading";
  progress.textContent = `${verb} ${file.name}…`;
  // XHR (not fetch) so large files report progress on mobile browsers.
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/upload?name=${encodeURIComponent(file.name)}`);
  xhr.setRequestHeader("authorization", `Bearer ${authToken()}`);
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) progress.textContent = `${verb} ${file.name}… ${Math.round((e.loaded / e.total) * 100)}%`;
  };
  xhr.onload = () => {
    const body = JSON.parse(xhr.responseText || "{}");
    if (xhr.status === 200) {
      $("target").value = body.path;
      const where = mode === "phone" ? "Ready to analyze" : "Uploaded to computer";
      progress.textContent = `${where} (${(body.size / 1048576).toFixed(1)} MB)`;
    } else {
      progress.textContent = `Failed: ${body.error || xhr.status}`;
    }
  };
  xhr.onerror = () => (progress.textContent = "Failed: network error");
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

// ---- Installed apps (Android only) ----

let installedApps = [];

function openAppPicker(command) {
  $("apps-sheet").hidden = false;
  $("apps-sheet").dataset.command = command;
  $("apps-search").value = "";
  installedApps = JSON.parse(android.listApps($("apps-system").checked));
  renderApps();
}

function renderApps() {
  const query = $("apps-search").value.trim().toLowerCase();
  const list = $("apps-list");
  const shown = installedApps.filter((a) => !query || a.label.toLowerCase().includes(query) || a.pkg.includes(query));
  list.innerHTML = shown.length ? "" : '<li class="meta">No matching apps.</li>';
  for (const app of shown.slice(0, 300)) {
    const li = document.createElement("li");
    li.innerHTML = '<div class="title"></div><div class="meta"></div>';
    li.querySelector(".title").textContent = app.label;
    li.querySelector(".meta").textContent =
      `${app.pkg} · ${app.version || "?"} · ${(app.size / 1048576).toFixed(1)} MB${app.splits ? ` · ${app.splits} split APKs` : ""}`;
    li.addEventListener("click", () => chooseApp(app));
    list.appendChild(li);
  }
}

function chooseApp(app) {
  $("apps-sheet").hidden = true;
  $("command").value = $("apps-sheet").dataset.command;
  describeCommand();
  const progress = $("upload-progress");
  if (mode === "phone") {
    // Installed APKs are readable in place; no copy needed.
    $("target").value = app.path;
    progress.textContent = `${app.label} (${app.pkg})`;
    return;
  }
  const callback = `cb${Date.now()}`;
  window.__reaUpload = window.__reaUpload || {};
  window.__reaUpload[callback] = (event) => {
    if (event.progress !== undefined) progress.textContent = `Uploading ${app.label}… ${event.progress}%`;
    else if (event.path) {
      $("target").value = event.path;
      progress.textContent = `Uploaded ${app.label} to computer`;
      delete window.__reaUpload[callback];
    } else {
      progress.textContent = `Upload failed: ${event.error}`;
      delete window.__reaUpload[callback];
    }
  };
  progress.textContent = `Uploading ${app.label}…`;
  android.uploadFile(app.path, `${app.pkg}.apk`, `${location.origin}/api/upload`, authToken(), callback);
}

// ---- Wire up UI ----

$("quick").addEventListener("click", (event) => {
  const action = quickActions()[event.target.dataset.i];
  if (!action) return;
  if (action.pickApp) return openAppPicker(action.command);
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
$("copy-btn").addEventListener("click", () => {
  const text = $("output").textContent;
  if (android) android.copy(text);
  else navigator.clipboard?.writeText(text);
});
$("share-btn").addEventListener("click", () => {
  const text = $("output").textContent;
  if (android) android.share($("output-label").textContent, text);
  else if (navigator.share) navigator.share({ title: $("output-label").textContent, text }).catch(() => {});
  else navigator.clipboard?.writeText(text);
});
$("clear-history").addEventListener("click", () => {
  store.set("history", []);
  renderHistory();
});
$("token").value = token;
$("save-token").addEventListener("click", () => {
  if (android && !$("computer-fields").hidden) {
    const parsed = parseComputerLink($("computer-link").value);
    if (!parsed) {
      $("server-info").textContent = "That doesn't look like the link server.mjs prints (http://…:8787/#token=…).";
      return;
    }
    return android.useComputer(parsed.base, parsed.token);
  } else if (mode === "browser") {
    token = $("token").value.trim();
    store.set("token", token);
  } else if (android.runtimeStatus().startsWith("error")) {
    android.stopRuntime(); // retry: connect() starts it again
  }
  connect().then(() => commands.length && showView("run"));
});
document.querySelectorAll('input[name="mode"]').forEach((radio) =>
  radio.addEventListener("change", () => {
    if (radio.value === "phone") return android.usePhone();
    // Show the link field; Save & connect opens the computer.
    $("computer-fields").hidden = false;
    $("computer-link").focus();
  }),
);
$("reload-commands").addEventListener("click", async () => {
  await api("/api/commands/reload", { method: "POST" });
  connect();
});
$("apps-search").addEventListener("input", renderApps);
$("apps-system").addEventListener("change", () => openAppPicker($("apps-sheet").dataset.command));
$("apps-close").addEventListener("click", () => ($("apps-sheet").hidden = true));
document.querySelectorAll(".tabbar button").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));

// Android back button: close the app picker or a doc page before leaving the app.
window.reaBack = () => {
  if (!$("apps-sheet").hidden) {
    $("apps-sheet").hidden = true;
  } else if (!$("docs-back").hidden && $("view-docs").classList.contains("active")) {
    $("docs-back").click();
  } else if (!$("view-run").classList.contains("active")) {
    showView("run");
  } else {
    return false;
  }
  return true;
};

if (android) document.documentElement.classList.add("android");
else if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
renderModeUi();
connect();
