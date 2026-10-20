// Downloads Termux's Android builds of Node.js and procps `ps`, plus the shared libraries they need.
// Termux packages are compiled against Android's bionic libc, so they run inside
// an ordinary app process. https://github.com/termux/termux-packages

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const REPO = "https://packages.termux.dev/apt/termux-main";
export const ABI_TO_TERMUX = { "arm64-v8a": "aarch64", x86_64: "x86_64" };
// Libraries every Android process already has; never bundle these.
const SYSTEM_LIBS = new Set(["libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so", "libz.so"]);
const PREFIX = "data/data/com.termux/files/usr";

function parsePackages(text) {
  const packages = new Map();
  for (const block of text.split("\n\n")) {
    const fields = Object.fromEntries(
      block.split("\n").filter((l) => /^[\w-]+: /.test(l)).map((l) => [l.slice(0, l.indexOf(":")), l.slice(l.indexOf(":") + 2)]),
    );
    if (fields.Package) packages.set(fields.Package, fields);
  }
  return packages;
}

function download(url, dest) {
  execFileSync("curl", ["-fsSL", "--retry", "4", "-o", dest, url], { stdio: "inherit" });
}

/** Resolve a package and its dependencies (Depends field) into a list of package records. */
function closure(packages, root) {
  const seen = new Map();
  const visit = (name) => {
    const clean = name.trim().split(/\s|\(/)[0];
    if (!clean || seen.has(clean)) return;
    const pkg = packages.get(clean);
    if (!pkg) return; // virtual or optional package
    seen.set(clean, pkg);
    (pkg.Depends || "").split(",").forEach((dep) => visit(dep.split("|")[0]));
  };
  visit(root);
  return [...seen.values()];
}

/** Termux packages and the executable each one contributes to the app. */
export const TERMUX_TOOLS = [
  { pkg: "nodejs-lts", bin: "bin/node", name: "node" },
  // REA checks process ownership with procps-style `ps -axo`; Android's toybox ps lacks it.
  { pkg: "procps", bin: "bin/ps", name: "ps" },
];

/**
 * Fetch the Termux tools for one ABI into `outDir`:
 *   outDir/bin/<name>    executables (shipped in the APK as lib<name>.so)
 *   outDir/lib/*.so*     shared libraries they load, with their original names
 * Returns { name: version } for each tool.
 */
export function fetchTermuxTools({ abi, cacheDir, outDir, tools = TERMUX_TOOLS }) {
  const arch = ABI_TO_TERMUX[abi];
  if (!arch) throw new Error(`Unsupported ABI ${abi}`);
  mkdirSync(cacheDir, { recursive: true });
  const index = join(cacheDir, `Packages-${arch}`);
  download(`${REPO}/dists/stable/main/binary-${arch}/Packages`, index);
  const packages = parsePackages(readFileSync(index, "utf8"));
  const wanted = new Map();
  for (const tool of tools) for (const pkg of closure(packages, tool.pkg)) wanted.set(pkg.Package, pkg);

  const root = join(cacheDir, `root-${arch}`);
  mkdirSync(root, { recursive: true });
  for (const pkg of wanted.values()) {
    const deb = join(cacheDir, pkg.Filename.split("/").pop());
    if (!existsSync(deb) || sha256(deb) !== pkg.SHA256) download(`${REPO}/${pkg.Filename}`, deb);
    if (sha256(deb) !== pkg.SHA256) throw new Error(`Checksum mismatch for ${pkg.Package}`);
    const work = join(cacheDir, `deb-${pkg.Package}-${arch}`);
    mkdirSync(work, { recursive: true });
    execFileSync("ar", ["x", deb], { cwd: work });
    const data = readdirSync(work).find((f) => f.startsWith("data.tar"));
    execFileSync("tar", ["-xf", join(work, data), "-C", root]);
  }

  const usr = join(root, PREFIX);
  const libDir = join(usr, "lib");
  mkdirSync(join(outDir, "bin"), { recursive: true });
  mkdirSync(join(outDir, "lib"), { recursive: true });

  // Walk DT_NEEDED from each executable and copy every non-system library it reaches.
  const copied = new Set();
  const queue = [];
  for (const tool of tools) {
    copyFileSync(join(usr, tool.bin), join(outDir, "bin", tool.name));
    queue.push(join(usr, tool.bin));
  }
  while (queue.length) {
    for (const needed of neededLibs(queue.shift())) {
      if (SYSTEM_LIBS.has(needed) || copied.has(needed)) continue;
      const source = join(libDir, needed);
      if (!existsSync(source)) throw new Error(`${needed} not found in Termux packages`);
      copyFileSync(source, join(outDir, "lib", needed));
      copied.add(needed);
      queue.push(source);
    }
  }
  const versions = Object.fromEntries(tools.map((t) => [t.name, packages.get(t.pkg).Version]));
  writeFileSync(
    join(outDir, "VERSION"),
    `Termux packages (${arch}): ${tools.map((t) => `${t.pkg} ${versions[t.name]}`).join(", ")}\n` +
      `Libraries: ${[...copied].sort().join(", ")}\n`,
  );
  return versions;
}

function neededLibs(file) {
  const out = execFileSync("readelf", ["-d", "-W", file], { encoding: "utf8" });
  return [...out.matchAll(/\(NEEDED\)\s+Shared library: \[([^\]]+)\]/g)].map((m) => m[1]);
}

function sha256(file) {
  return createHash("sha256").update(readFileSync(file)).digest("hex");
}
