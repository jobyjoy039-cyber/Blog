#!/usr/bin/env node
// Builds a self-contained, offline REA Mobile bundle for one platform:
//
//   rea-mobile-offline-<target>/
//   ├── node/        portable Node.js runtime (no install needed)
//   ├── rea/         REA (rea-agents) with every npm dependency for <target>
//   ├── rea-docs/    REA's documentation, README and license from the source repo
//   ├── app/         REA Mobile server and phone app
//   └── start.sh | start.command | start.bat
//
// Usage: node scripts/build-offline.mjs [--target linux-x64] [--rea-version 6.7.0]
//                                        [--node-version 22.22.0] [--out dist] [--no-archive]
// Needs internet, git, tar, and zip/unzip for Windows targets. The result needs none of them.

import { execFileSync } from "node:child_process";
import { chmodSync, cpSync, mkdirSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { copyReaDocs } from "./rea-docs.mjs";

const APP_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const TARGETS = {
  "linux-x64": { os: "linux", cpu: "x64", node: "linux-x64", archive: "tar.xz" },
  "linux-arm64": { os: "linux", cpu: "arm64", node: "linux-arm64", archive: "tar.xz" },
  "macos-x64": { os: "darwin", cpu: "x64", node: "darwin-x64", archive: "tar.gz" },
  "macos-arm64": { os: "darwin", cpu: "arm64", node: "darwin-arm64", archive: "tar.gz" },
  "windows-x64": { os: "win32", cpu: "x64", node: "win-x64", archive: "zip" },
};

function option(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? fallback : process.argv[index + 1];
}

function hostTarget() {
  const os = { linux: "linux", darwin: "macos", win32: "windows" }[process.platform];
  return `${os}-${process.arch}`;
}

const targetName = option("target", hostTarget());
const target = TARGETS[targetName];
if (!target) {
  console.error(`Unknown target ${targetName}. Choose one of: ${Object.keys(TARGETS).join(", ")}`);
  process.exit(1);
}
const nodeVersion = option("node-version", "22.22.0");
const outDir = resolve(option("out", join(APP_DIR, "dist")));
const archive = !process.argv.includes("--no-archive");

const run = (cmd, args, opts = {}) => execFileSync(cmd, args, { stdio: "inherit", ...opts });
const capture = (cmd, args) => execFileSync(cmd, args, { encoding: "utf8" }).trim();
const step = (text) => console.log(`\n==> ${text}`);

const reaVersion = option("rea-version", capture("npm", ["view", "rea-agents", "version"]));
const name = `rea-mobile-offline-${targetName}`;
const bundle = join(outDir, name);
const work = join(outDir, `.work-${targetName}`);

rmSync(bundle, { recursive: true, force: true });
rmSync(work, { recursive: true, force: true });
mkdirSync(bundle, { recursive: true });
mkdirSync(work, { recursive: true });

step(`REA ${reaVersion} + dependencies for ${target.os}/${target.cpu}`);
const reaDir = join(bundle, "rea");
mkdirSync(reaDir);
writeFileSync(join(reaDir, "package.json"), JSON.stringify({ private: true, name: "rea-bundle" }, null, 2));
// --os/--cpu select the matching prebuilt native packages (e.g. node-pty) for the target, not this host.
run("npm", [
  "install",
  `rea-agents@${reaVersion}`,
  "--omit=dev",
  "--no-audit",
  "--no-fund",
  "--ignore-scripts",
  `--os=${target.os}`,
  `--cpu=${target.cpu}`,
  ...(target.os === "linux" ? ["--libc=glibc"] : []),
], { cwd: reaDir });

step(`Portable Node.js ${nodeVersion} (${target.node})`);
const nodeBase = `node-v${nodeVersion}-${target.node}`;
const nodeArchive = join(work, `${nodeBase}.${target.archive}`);
run("curl", ["-fsSL", "--retry", "4", "-o", nodeArchive, `https://nodejs.org/dist/v${nodeVersion}/${nodeBase}.${target.archive}`]);
const sums = capture("curl", ["-fsSL", "--retry", "4", `https://nodejs.org/dist/v${nodeVersion}/SHASUMS256.txt`]);
const expected = sums.split("\n").find((l) => l.endsWith(`  ${nodeBase}.${target.archive}`))?.split(" ")[0];
const actual = capture(process.platform === "darwin" ? "shasum" : "sha256sum", process.platform === "darwin" ? ["-a", "256", nodeArchive] : [nodeArchive]).split(" ")[0];
if (!expected || expected !== actual) throw new Error(`Node.js checksum mismatch for ${nodeBase}`);
if (target.archive === "zip") run("unzip", ["-q", nodeArchive, "-d", work]);
else run("tar", ["-xf", nodeArchive, "-C", work]);
renameSync(join(work, nodeBase), join(bundle, "node"));
// Headers, docs, npm and corepack are not needed to run REA; drop them to keep the bundle small.
const nodeExtras = target.os === "win32"
  ? ["node_modules", "npm", "npm.cmd", "npm.ps1", "npx", "npx.cmd", "npx.ps1", "corepack", "corepack.cmd", "install_tools.bat", "nodevars.bat", "CHANGELOG.md", "README.md"]
  : ["include", "share", "lib", "bin/npm", "bin/npx", "bin/corepack", "CHANGELOG.md", "README.md"];
for (const extra of nodeExtras) {
  rmSync(join(bundle, "node", extra), { recursive: true, force: true });
}

step(`REA source repository (rea-agents-${reaVersion}) for offline docs`);
const repo = join(work, "rea-src");
run("git", ["-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1", "--branch", `rea-agents-${reaVersion}`, "https://github.com/morluto/rea", repo], {
  env: { ...process.env, GIT_LFS_SKIP_SMUDGE: "1" },
});
copyReaDocs(repo, join(bundle, "rea-docs"), reaVersion);

step("REA Mobile app");
const appDir = join(bundle, "app");
mkdirSync(appDir);
cpSync(join(APP_DIR, "server.mjs"), join(appDir, "server.mjs"));
cpSync(join(APP_DIR, "public"), join(appDir, "public"), { recursive: true });
cpSync(join(APP_DIR, "README.md"), join(bundle, "README.md"));
writeLaunchers();

rmSync(work, { recursive: true, force: true });

if (archive) {
  step("Archive");
  const file = target.os === "win32" ? `${name}.zip` : `${name}.tar.gz`;
  rmSync(join(outDir, file), { force: true });
  if (target.os === "win32") run("zip", ["-qr", "-9", file, name], { cwd: outDir });
  else run("tar", ["-czf", file, name], { cwd: outDir });
  console.log(`\nBuilt ${join(outDir, file)} (${(statSync(join(outDir, file)).size / 1048576).toFixed(0)} MB)`);
} else {
  console.log(`\nBuilt ${bundle}`);
}

function writeLaunchers() {
  const sh = `#!/bin/sh
# Starts REA Mobile with the bundled Node.js and REA. No internet needed.
cd "$(dirname "$0")" || exit 1
exec ./node/bin/node app/server.mjs "$@"
`;
  if (target.os === "win32") {
    writeFileSync(
      join(bundle, "start.bat"),
      `@echo off\r\nrem Starts REA Mobile with the bundled Node.js and REA. No internet needed.\r\ncd /d "%~dp0"\r\nnode\\node.exe app\\server.mjs %*\r\npause\r\n`,
    );
    return;
  }
  writeFileSync(join(bundle, "start.sh"), sh);
  chmodSync(join(bundle, "start.sh"), 0o755);
  if (target.os === "darwin") {
    // Double-clickable in Finder. Clearing quarantine lets the downloaded node binary run.
    writeFileSync(
      join(bundle, "start.command"),
      `#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nxattr -dr com.apple.quarantine . 2>/dev/null\nexec ./start.sh\n`,
    );
    chmodSync(join(bundle, "start.command"), 0o755);
  }
}
