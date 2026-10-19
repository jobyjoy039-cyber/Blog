#!/usr/bin/env node
// REA Mobile bridge: serves the phone app and runs REA (https://github.com/morluto/rea)
// commands on this computer on behalf of an authenticated phone on the same network.
// Zero dependencies; requires Node.js 22+ (same as REA itself).

import { createServer } from "node:http";
import { spawn, execFileSync } from "node:child_process";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { createReadStream, createWriteStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { networkInterfaces, homedir } from "node:os";
import { basename, extname, join, resolve, dirname, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = join(HERE, "public");
const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || "0.0.0.0";
// Offline bundle layout: <bundle>/app (this file), <bundle>/rea, <bundle>/rea-docs, <bundle>/node.
const BUNDLED_REA = join(HERE, "..", "rea", "node_modules", "rea-agents", "scripts", "rea.mjs");
const DOCS_DIR = resolve(process.env.REA_MOBILE_DOCS || join(HERE, "..", "rea-docs"));
const TOKEN_FILE = process.env.REA_MOBILE_TOKEN_FILE || join(homedir(), ".rea-mobile-token");
const TOKEN = process.env.REA_MOBILE_TOKEN || loadOrCreateToken();
const UPLOAD_DIR = resolve(process.env.REA_MOBILE_UPLOADS || join(homedir(), "rea-mobile-uploads"));
const RUN_TIMEOUT_MS = Number(process.env.REA_MOBILE_TIMEOUT_MS || 15 * 60 * 1000);
const MAX_UPLOAD_BYTES = Number(process.env.REA_MOBILE_MAX_UPLOAD_MB || 2048) * 1024 * 1024;

// Commands that change this computer's REA installation or agent configuration.
// They are interactive or host-altering, so they stay on the desktop.
const BLOCKED_COMMANDS = new Set(["setup", "uninstall", "update"]);

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json",
  ".md": "text/markdown; charset=utf-8",
  ".jpg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
};

/** Keep the token across restarts so a paired phone stays paired. */
function loadOrCreateToken() {
  try {
    const saved = readFileSync(TOKEN_FILE, "utf8").trim();
    if (saved) return saved;
  } catch {
    /* first run */
  }
  const token = randomBytes(18).toString("base64url");
  try {
    writeFileSync(TOKEN_FILE, token, { mode: 0o600 });
  } catch {
    /* read-only home: token lasts for this run only */
  }
  return token;
}

/** Resolve how to launch REA: [executable, ...prefixArgs]. */
function resolveRea() {
  const fromEnv = process.env.REA_BIN;
  if (fromEnv) {
    return /\.(m?js|cjs)$/.test(fromEnv) ? [process.execPath, fromEnv] : [fromEnv];
  }
  if (existsSync(BUNDLED_REA)) return [process.execPath, BUNDLED_REA];
  if (process.platform === "win32") {
    // .cmd shims cannot be spawned without a shell, so run the package entry point with node.
    try {
      const root = execFileSync("npm root -g", { shell: true, encoding: "utf8" }).trim();
      const entry = join(root, "rea-agents", "scripts", "rea.mjs");
      statSync(entry);
      return [process.execPath, entry];
    } catch {
      console.error("REA not found. Run `npm install --global rea-agents` or set REA_BIN.");
      process.exit(1);
    }
  }
  try {
    execFileSync("which", ["rea"], { stdio: "ignore" });
    return ["rea"];
  } catch {
    return ["npx", "-y", "rea-agents@latest"];
  }
}

const REA = resolveRea();

function runRea(args, { onData, signal } = {}) {
  return new Promise((done) => {
    const child = spawn(REA[0], [...REA.slice(1), ...args], {
      env: { ...process.env, NO_COLOR: "1", FORCE_COLOR: "0" },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let out = "";
    const push = (chunk) => {
      const text = chunk.toString();
      out += text;
      onData?.(text);
    };
    child.stdout.on("data", push);
    child.stderr.on("data", push);
    const timer = setTimeout(() => child.kill("SIGTERM"), RUN_TIMEOUT_MS);
    signal?.addEventListener("abort", () => child.kill("SIGTERM"));
    child.on("error", (error) => push(`\n[rea-mobile] failed to start REA: ${error.message}\n`));
    child.on("close", (code) => {
      clearTimeout(timer);
      done({ code, out });
    });
  });
}

/** Parse the command table from `rea --help`. */
async function loadCommands() {
  const { out } = await runRea(["--help"]);
  const commands = [];
  let inTable = false;
  for (const line of out.split("\n")) {
    if (/^Commands:/.test(line)) {
      inTable = true;
      continue;
    }
    if (!inTable) continue;
    const match = /^ {2}([a-z0-9][a-z0-9-]*)\s{2,}(.*)$/.exec(line);
    if (match) {
      if (!BLOCKED_COMMANDS.has(match[1])) commands.push({ name: match[1], description: match[2].trim() });
    } else if (line.trim() && !line.startsWith(" ")) {
      inTable = false;
    }
  }
  return commands;
}

let commandsPromise = loadCommands();

function authorized(req) {
  const header = req.headers.authorization || "";
  const given = Buffer.from(header.replace(/^Bearer\s+/i, ""));
  const expected = Buffer.from(TOKEN);
  return given.length === expected.length && timingSafeEqual(given, expected);
}

function sendJson(res, status, body) {
  res.writeHead(status, { "content-type": MIME[".json"], "cache-control": "no-store" });
  res.end(JSON.stringify(body));
}

async function readJson(req, limit = 1024 * 1024) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new Error("Request body too large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString() || "{}");
}

async function handleRun(req, res) {
  const body = await readJson(req);
  const command = String(body.command || "");
  const args = Array.isArray(body.args) ? body.args.map(String) : [];
  const known = (await commandsPromise).some((c) => c.name === command);
  if (!known) return sendJson(res, 400, { error: `Unknown or blocked command: ${command}` });

  res.writeHead(200, {
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  const controller = new AbortController();
  res.on("close", () => controller.abort());
  const { code } = await runRea([command, ...args], {
    signal: controller.signal,
    onData: (text) => res.write(text),
  });
  res.end(`\n[rea-mobile] exit ${code ?? "killed"}\n`);
}

async function handleUpload(req, res, url) {
  const name = basename(url.searchParams.get("name") || "upload.bin").replace(/[^\w.\- ]/g, "_");
  const dir = join(UPLOAD_DIR, `${Date.now()}-${randomBytes(3).toString("hex")}`);
  mkdirSync(dir, { recursive: true });
  const target = join(dir, name || "upload.bin");
  const file = createWriteStream(target);
  let size = 0;
  try {
    for await (const chunk of req) {
      size += chunk.length;
      if (size > MAX_UPLOAD_BYTES) throw new Error("File too large");
      if (!file.write(chunk)) await new Promise((r) => file.once("drain", r));
    }
    await new Promise((r, j) => file.end((e) => (e ? j(e) : r())));
    sendJson(res, 200, { path: target, size });
  } catch (error) {
    file.destroy();
    sendJson(res, 413, { error: error.message });
  }
}

function serveStatic(res, pathname) {
  // REA's public documentation is served without the token so <img> tags can load its figures.
  const [root, rel] = pathname.startsWith("/rea-docs/")
    ? [DOCS_DIR, decodeURIComponent(pathname.slice("/rea-docs/".length))]
    : [PUBLIC_DIR, pathname === "/" ? "index.html" : decodeURIComponent(pathname.slice(1))];
  const file = resolve(root, rel);
  if (file !== root && !file.startsWith(root + sep)) return sendJson(res, 403, { error: "Forbidden" });
  try {
    if (!statSync(file).isFile()) throw new Error();
  } catch {
    return sendJson(res, 404, { error: "Not found" });
  }
  res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" });
  createReadStream(file).pipe(res);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  try {
    if (!url.pathname.startsWith("/api/")) return serveStatic(res, url.pathname);
    if (!authorized(req)) return sendJson(res, 401, { error: "Invalid or missing token" });

    if (req.method === "GET" && url.pathname === "/api/info") {
      return sendJson(res, 200, {
        rea: REA.join(" "),
        uploads: UPLOAD_DIR,
        docs: existsSync(join(DOCS_DIR, "index.json")),
        commands: await commandsPromise,
      });
    }
    if (req.method === "POST" && url.pathname === "/api/commands/reload") {
      commandsPromise = loadCommands();
      return sendJson(res, 200, { commands: await commandsPromise });
    }
    if (req.method === "GET" && url.pathname === "/api/help") {
      const command = url.searchParams.get("command") || "";
      if (!(await commandsPromise).some((c) => c.name === command)) {
        return sendJson(res, 400, { error: "Unknown command" });
      }
      const { out } = await runRea([command, "--help"]);
      return sendJson(res, 200, { help: out });
    }
    if (req.method === "POST" && url.pathname === "/api/run") return await handleRun(req, res);
    if (req.method === "POST" && url.pathname === "/api/upload") return await handleUpload(req, res, url);
    sendJson(res, 404, { error: "Not found" });
  } catch (error) {
    if (!res.headersSent) sendJson(res, 500, { error: error.message });
    else res.end(`\n[rea-mobile] error: ${error.message}\n`);
  }
});

server.listen(PORT, HOST, () => {
  const addresses = Object.values(networkInterfaces())
    .flat()
    .filter((i) => i && i.family === "IPv4" && !i.internal)
    .map((i) => i.address);
  console.log(`REA Mobile is running (REA via: ${REA.join(" ")})`);
  console.log(`Uploads are saved to ${UPLOAD_DIR}`);
  console.log(`Offline docs: ${existsSync(join(DOCS_DIR, "index.json")) ? DOCS_DIR : "not bundled"}\n`);
  console.log("Open one of these on your phone (same Wi-Fi):");
  for (const address of addresses.length ? addresses : ["localhost"]) {
    console.log(`  http://${address}:${PORT}/#token=${TOKEN}`);
  }
  console.log("\nAnyone with this link can run REA on this computer. Keep it private.");
});
