// Copies REA's documentation from a morluto/rea source tree into a folder the
// app's Docs tab can read, and writes the index.json table of contents it uses.

import { cpSync, existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

export function copyReaDocs(repoDir, docsDir, reaVersion) {
  cpSync(join(repoDir, "docs"), docsDir, { recursive: true });
  for (const file of ["LICENSE", "SECURITY.md", "DISCLAIMER.md", "THIRD_PARTY_NOTICES.md"]) {
    if (existsSync(join(repoDir, file))) cpSync(join(repoDir, file), join(docsDir, file));
  }
  // The README sits at the repo root, so its links into docs/ need one level removed.
  writeFileSync(
    join(docsDir, "README.md"),
    readFileSync(join(repoDir, "README.md"), "utf8").replace(/(\]\(|src=")docs\//g, "$1"),
  );
  writeDocsIndex(docsDir, reaVersion);
}

/** List every Markdown page with its first heading so the app can show a table of contents. */
function writeDocsIndex(dir, reaVersion) {
  const pages = [];
  const walk = (current) => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = join(current, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith(".md")) {
        const text = readFileSync(full, "utf8").slice(0, 4000);
        const body = text.replace(/^---\n[\s\S]*?\n---\n/, "");
        const title = /^#\s+(.+)$/m.exec(body)?.[1] || /^\s*text:\s*(.+)$/m.exec(text)?.[1] || entry.name.replace(/\.md$/, "");
        pages.push({ path: relative(dir, full).split("\\").join("/"), title: title.replace(/[*`]/g, "").trim() });
      }
    }
  };
  walk(dir);
  // Top-level guides first, then translated READMEs, specs and release notes.
  const rank = (p) => (p.path === "README.md" ? 0 : p.path.includes("/") ? 2 : 1);
  pages.sort((a, b) => rank(a) - rank(b) || a.path.localeCompare(b.path));
  writeFileSync(join(dir, "index.json"), JSON.stringify({ reaVersion, pages }, null, 1));
}
