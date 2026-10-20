#!/usr/bin/env node
// Builds the REA Mobile Android app (APK) without Gradle, using the Android SDK tools.
//
// The APK contains:
//   lib/<abi>/libnode.so, libps.so   Termux's Android builds of Node.js and procps ps
//   assets/rea-libs-<abi>.zip         the shared libraries they load
//   assets/rea-runtime.zip            REA (rea-agents + dependencies) and REA Mobile's server
//   assets/www/                       the app interface and REA's docs
//
// Usage:
//   node android/build-apk.mjs [--rea-source <morluto/rea checkout or extracted zip>]
//                              [--rea <rea-agents .tgz or npm version>] [--abis arm64-v8a,x86_64]
//                              [--sdk <Android SDK>] [--keystore <file.jks>] [--out <dir>]
//
// REA comes from --rea, else is built from --rea-source, else the latest npm release.
// Docs come from --rea-source, else a clone of morluto/rea at the matching release tag.
// Needs: Node.js 22+, JDK 17+, git, curl, ar, tar, zip, readelf, and an Android SDK with
// build-tools 35 and platform 35 (pass --sdk, set ANDROID_HOME, or let the script download one).

import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { copyReaDocs } from "../scripts/rea-docs.mjs";
import { fetchTermuxTools, ABI_TO_TERMUX } from "./scripts/termux-tools.mjs";

const ANDROID_DIR = dirname(fileURLToPath(import.meta.url));
const APP_DIR = resolve(ANDROID_DIR, "..");
const SRC = join(ANDROID_DIR, "app");

const APP_VERSION = "1.0.0";
const VERSION_CODE = 1;
const MIN_SDK = 24;
const TARGET_SDK = 35;
const BUILD_TOOLS = "35.0.0";
const PLATFORM = `android-${TARGET_SDK}`;
const CMDLINE_TOOLS = "commandlinetools-linux-9862592_latest.zip";

function option(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index === -1 ? fallback : process.argv[index + 1];
}

const run = (cmd, args, opts = {}) => execFileSync(cmd, args, { stdio: "inherit", ...opts });
const capture = (cmd, args, opts = {}) => execFileSync(cmd, args, { encoding: "utf8", ...opts }).trim();
const step = (text) => console.log(`\n==> ${text}`);

const abis = option("abis", "arm64-v8a").split(",");
for (const abi of abis) if (!ABI_TO_TERMUX[abi]) throw new Error(`Unsupported ABI ${abi} (use arm64-v8a or x86_64)`);
const outDir = resolve(option("out", join(ANDROID_DIR, "dist")));
const cacheDir = resolve(option("cache", join(homedir(), ".cache", "rea-mobile-android")));
const build = join(ANDROID_DIR, "build");
const reaSource = option("rea-source") && resolve(option("rea-source"));

rmSync(build, { recursive: true, force: true });
mkdirSync(build, { recursive: true });
mkdirSync(outDir, { recursive: true });

// ---- Android SDK ----
const sdk = resolveSdk();
const tools = join(sdk, "build-tools", BUILD_TOOLS);
const androidJar = join(sdk, "platforms", PLATFORM, "android.jar");

// ---- REA package ----
step("REA package");
const reaSpec = resolveRea();
console.log(`Using ${reaSpec}`);

// ---- Runtime: REA + server, installed for Android ----
step("REA runtime for Android");
const runtime = join(build, "runtime");
const reaDir = join(runtime, "rea");
mkdirSync(reaDir, { recursive: true });
writeFileSync(join(reaDir, "package.json"), JSON.stringify({ private: true, name: "rea-runtime" }, null, 2));
// JavaScript dependencies are identical across Android ABIs; REA has no Android-native modules.
run("npm", ["install", reaSpec, "--omit=dev", "--no-audit", "--no-fund", "--ignore-scripts", "--os=android", "--cpu=arm64"], { cwd: reaDir });
const reaVersion = JSON.parse(readFileSync(join(reaDir, "node_modules", "rea-agents", "package.json"), "utf8")).version;
trimNodeModules(join(reaDir, "node_modules"));
mkdirSync(join(runtime, "app"));
cpSync(join(APP_DIR, "server.mjs"), join(runtime, "app", "server.mjs"));

const assets = join(build, "assets");
mkdirSync(assets, { recursive: true });
zipDir(runtime, join(assets, "rea-runtime.zip"));

// ---- Native executables and libraries per ABI ----
const nativeRoot = join(build, "native");
const versions = {};
for (const abi of abis) {
  step(`Termux Node.js and ps for ${abi}`);
  const fetched = join(build, `termux-${abi}`);
  Object.assign(versions, fetchTermuxTools({ abi, cacheDir: join(cacheDir, "termux"), outDir: fetched }));
  mkdirSync(join(nativeRoot, "lib", abi), { recursive: true });
  cpSync(join(fetched, "bin", "node"), join(nativeRoot, "lib", abi, "libnode.so"));
  cpSync(join(fetched, "bin", "ps"), join(nativeRoot, "lib", abi, "libps.so"));
  zipDir(fetched, join(assets, `rea-libs-${abi}.zip`), ["lib"]);
}
writeFileSync(
  join(assets, "rea-runtime.json"),
  JSON.stringify({ app: APP_VERSION, rea: reaVersion, node: versions.node, ps: versions.ps, built: new Date().toISOString() }),
);

// ---- Interface and docs ----
step("App interface and REA docs");
const www = join(assets, "www");
cpSync(join(APP_DIR, "public"), www, { recursive: true });
rmSync(join(www, "sw.js"), { force: true }); // assets are served by the app itself
copyReaDocs(resolveDocsSource(reaVersion), join(www, "rea-docs"), reaVersion);

// ---- Compile ----
step("Compile resources and code");
const versionName = `${APP_VERSION} (REA ${reaVersion})`;
run(join(tools, "aapt2"), ["compile", "--dir", join(SRC, "res"), "-o", join(build, "res.zip")]);
const gen = join(build, "gen");
mkdirSync(gen);
run(join(tools, "aapt2"), [
  "link", "-o", join(build, "app.unaligned.apk"),
  "-I", androidJar,
  "--manifest", join(SRC, "AndroidManifest.xml"),
  "--java", gen,
  "--min-sdk-version", String(MIN_SDK),
  "--target-sdk-version", String(TARGET_SDK),
  "--version-code", String(VERSION_CODE),
  "--version-name", versionName,
  "-A", assets,
  "-0", "zip", // the runtime zips are already compressed
  join(build, "res.zip"),
]);

const classes = join(build, "classes");
mkdirSync(classes);
const sources = [...listFiles(join(SRC, "java")), ...listFiles(gen)].filter((f) => f.endsWith(".java"));
run("javac", ["--release", "8", "-classpath", androidJar, "-Xlint:-options", "-encoding", "UTF-8", "-d", classes, ...sources]);
run(join(tools, "d8"), ["--release", "--min-api", String(MIN_SDK), "--lib", androidJar, "--output", build, ...listFiles(classes)]);

step("Package and sign");
const unaligned = join(build, "app.unaligned.apk");
run("zip", ["-q", "-j", unaligned, join(build, "classes.dex")]);
run("zip", ["-q", "-r", unaligned, "lib"], { cwd: nativeRoot });
const aligned = join(build, "app.aligned.apk");
run(join(tools, "zipalign"), ["-f", "-P", "16", "4", unaligned, aligned]);

const keystore = resolve(option("keystore", join(cacheDir, "rea-mobile.jks")));
const storePass = process.env.REA_MOBILE_KEYSTORE_PASSWORD || "rea-mobile";
if (!existsSync(keystore)) {
  console.log(`Creating signing key ${keystore} (keep it: app updates must be signed with the same key)`);
  mkdirSync(dirname(keystore), { recursive: true });
  run("keytool", [
    "-genkeypair", "-keystore", keystore, "-alias", "rea-mobile", "-keyalg", "RSA", "-keysize", "3072",
    "-validity", "10000", "-storepass", storePass, "-keypass", storePass, "-dname", "CN=REA Mobile",
  ]);
}
const apk = join(outDir, `rea-mobile-${APP_VERSION}-${abis.join("-")}.apk`);
run(join(tools, "apksigner"), ["sign", "--ks", keystore, "--ks-pass", `pass:${storePass}`, "--out", apk, aligned]);
run(join(tools, "apksigner"), ["verify", apk]);
console.log(`\nBuilt ${apk} (${(statSync(apk).size / 1048576).toFixed(0)} MB): REA ${reaVersion}, Node.js ${versions.node}, ${abis.join(", ")}`);

// ---- Helpers ----

function resolveSdk() {
  const candidates = [option("sdk"), process.env.ANDROID_HOME, process.env.ANDROID_SDK_ROOT, join(cacheDir, "sdk")].filter(Boolean);
  const found = candidates.find((dir) => existsSync(join(dir, "build-tools", BUILD_TOOLS)) && existsSync(join(dir, "platforms", PLATFORM)));
  if (found) return found;
  const target = candidates.find((dir) => existsSync(join(dir, "cmdline-tools"))) || join(cacheDir, "sdk");
  step(`Android SDK (${target})`);
  let sdkmanager = join(target, "cmdline-tools", "latest", "bin", "sdkmanager");
  if (!existsSync(sdkmanager)) {
    mkdirSync(join(target, "cmdline-tools"), { recursive: true });
    const zip = join(cacheDir, CMDLINE_TOOLS);
    run("curl", ["-fsSL", "--retry", "4", "-o", zip, `https://dl.google.com/android/repository/${CMDLINE_TOOLS}`]);
    run("unzip", ["-q", "-o", zip, "-d", join(target, "cmdline-tools")]);
    cpSync(join(target, "cmdline-tools", "cmdline-tools"), join(target, "cmdline-tools", "latest"), { recursive: true });
    rmSync(join(target, "cmdline-tools", "cmdline-tools"), { recursive: true, force: true });
  }
  execFileSync(sdkmanager, [`--sdk_root=${target}`, "--licenses"], { input: "y\n".repeat(20), stdio: ["pipe", "ignore", "inherit"] });
  run(sdkmanager, [`--sdk_root=${target}`, `platforms;${PLATFORM}`, `build-tools;${BUILD_TOOLS}`]);
  return target;
}

function resolveRea() {
  const given = option("rea");
  if (given) return existsSync(given) ? resolve(given) : `rea-agents@${given}`;
  if (!reaSource) return `rea-agents@${capture("npm", ["view", "rea-agents", "version"])}`;
  // Build the package from the given source tree, the same way its maintainers publish it.
  const packed = join(cacheDir, "rea-from-source");
  mkdirSync(packed, { recursive: true });
  if (!existsSync(join(reaSource, "dist"))) {
    run("npm", ["ci", "--no-audit", "--no-fund"], { cwd: reaSource });
    run("npm", ["run", "build"], { cwd: reaSource });
  }
  const name = capture("npm", ["pack", "--ignore-scripts", "--silent", "--pack-destination", packed], { cwd: reaSource }).split("\n").pop();
  return join(packed, name);
}

function resolveDocsSource(version) {
  if (reaSource) return reaSource;
  const clone = join(build, "rea-src");
  run("git", ["-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1", "--branch", `rea-agents-${version}`, "https://github.com/morluto/rea", clone], {
    env: { ...process.env, GIT_LFS_SKIP_SMUDGE: "1" },
  });
  return clone;
}

/** Drop files no program reads at runtime: Markdown, type declarations and source maps of dependencies. */
function trimNodeModules(dir) {
  let removed = 0;
  const walk = (current, depth) => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = join(current, entry.name);
      // rea-agents reads its own Markdown (skills, instructions), so leave the package itself alone.
      if (entry.name === "rea-agents" && depth === 0) continue;
      if (entry.isDirectory()) walk(full, depth + 1);
      else if (/(\.d\.[mc]?ts|\.map|\.md|\.markdown)$/i.test(entry.name)) {
        rmSync(full, { force: true });
        removed++;
      }
    }
  };
  walk(dir, 0);
  console.log(`Trimmed ${removed} files from node_modules`);
}

function zipDir(dir, zipFile, entries = ["."]) {
  rmSync(zipFile, { force: true });
  run("zip", ["-q", "-r", "-9", "-X", zipFile, ...entries], { cwd: dir });
}

function listFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? listFiles(join(dir, e.name)) : [join(dir, e.name)],
  );
}
