// Offline reader for REA's bundled documentation (served by server.mjs at /rea-docs/).

const escape = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/** Resolve a link inside a doc page relative to that page; external links stay as they are. */
function resolveLink(href, page) {
  if (/^[a-z]+:|^#/i.test(href)) return href;
  const base = new URL(page, "https://docs.invalid/");
  const url = new URL(href, base);
  return url.host === "docs.invalid" ? url.pathname.slice(1) + url.hash : href;
}

function inline(text, page) {
  // Code spans are pulled out first so nothing inside them is formatted.
  const codes = [];
  let out = escape(text).replace(/`([^`]+)`/g, (_, code) => `\u0000${codes.push(code) - 1}\u0000`);
  out = out
    // Linked remote images are badges: drop the link along with the image.
    .replace(/\[!\[[^\]]*\]\([a-z]+:[^)]*\)\]\([^)]*\)/gi, "")
    .replace(/!\[([^\]]*)\]\(([^)\s]+)[^)]*\)/g, (_, alt, src) => {
      const local = resolveLink(src, page);
      // Remote images are online status badges; skip them so the reader never leaves the local network.
      return /^[a-z]+:/i.test(local) ? "" : `<img alt="${alt}" src="rea-docs/${local}" loading="lazy">`;
    })
    .replace(/\[([^\]]+)\]\(([^)\s]+)[^)]*\)/g, (_, label, href) => {
      const target = resolveLink(href.replace(/&amp;/g, "&"), page);
      return /^[a-z]+:/i.test(target)
        ? `<a href="${target}" target="_blank" rel="noopener">${label}</a>`
        : `<a href="#" data-doc="${target}">${label}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
}

/** A small Markdown renderer covering what REA's docs use: headings, lists, code, tables, quotes. */
export function renderMarkdown(source, page) {
  const lines = source.replace(/^---\n[\s\S]*?\n---\n/, "").replace(/<!--[\s\S]*?-->/g, "").split("\n");
  const html = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = /^\s*(```|~~~)/.exec(line);
    if (fence) {
      const body = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(fence[1]); i++) body.push(lines[i]);
      i++;
      html.push(`<pre><code>${escape(body.join("\n"))}</code></pre>`);
    } else if (/^#{1,6}\s/.test(line)) {
      const level = /^#+/.exec(line)[0].length;
      html.push(`<h${level}>${inline(line.replace(/^#+\s*/, "").replace(/\s*#+$/, ""), page)}</h${level}>`);
      i++;
    } else if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim(), page));
      const head = cells(line);
      const rows = [];
      for (i += 2; i < lines.length && /^\s*\|/.test(lines[i]); i++) rows.push(cells(lines[i]));
      html.push(
        `<div class="table"><table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>` +
          rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("") +
          "</tbody></table></div>",
      );
    } else if (/^\s*([-*+]|\d+\.)\s/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && (/^\s*([-*+]|\d+\.)\s/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
        if (/^\s*([-*+]|\d+\.)\s/.test(lines[i])) items.push(lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, ""));
        else items[items.length - 1] += ` ${lines[i].trim()}`;
        i++;
      }
      const tag = ordered ? "ol" : "ul";
      html.push(`<${tag}>${items.map((it) => `<li>${inline(it, page)}</li>`).join("")}</${tag}>`);
    } else if (/^\s*>/.test(line)) {
      const quote = [];
      for (; i < lines.length && /^\s*>/.test(lines[i]); i++) quote.push(lines[i].replace(/^\s*>\s?/, ""));
      const text = quote.join(" ").replace(/^\[!(\w+)\]\s*/, (_, kind) => `**${kind[0]}${kind.slice(1).toLowerCase()}:** `);
      html.push(`<blockquote>${inline(text, page)}</blockquote>`);
    } else if (/^\s*(---|\*\*\*)\s*$/.test(line)) {
      html.push("<hr>");
      i++;
    } else if (!line.trim() || /^\s*<\/?[a-z]/i.test(line)) {
      i++; // blank line or raw layout HTML (badges, centered banners)
    } else {
      const para = [];
      for (; i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*~~~|\s*([-*+]|\d+\.)\s|\s*>|\s*\|)/.test(lines[i]); i++) {
        para.push(lines[i].trim());
      }
      if (!para.length) para.push(lines[i++].trim());
      html.push(`<p>${inline(para.join(" "), page)}</p>`);
    }
  }
  return html.join("\n");
}

export function createDocs({ list, reader, search, back }) {
  let pages = [];
  let loaded = false;

  function renderList() {
    const query = search.value.trim().toLowerCase();
    const shown = pages.filter((p) => !query || p.title.toLowerCase().includes(query) || p.path.includes(query));
    list.innerHTML = shown.length ? "" : '<li class="meta">No matching pages.</li>';
    for (const p of shown) {
      const li = document.createElement("li");
      li.innerHTML = '<div class="title"></div><div class="meta"></div>';
      li.querySelector(".title").textContent = p.title;
      li.querySelector(".meta").textContent = p.path;
      li.addEventListener("click", () => open(p.path));
      list.appendChild(li);
    }
  }

  async function open(path) {
    const [file, hash] = path.split("#");
    reader.innerHTML = '<p class="meta">Loading…</p>';
    list.hidden = true;
    search.hidden = true;
    back.hidden = false;
    reader.hidden = false;
    const res = await fetch(`rea-docs/${file}`);
    reader.innerHTML = res.ok ? renderMarkdown(await res.text(), file) : `<p>Page not found: ${escape(file)}</p>`;
    const anchor = hash && [...reader.querySelectorAll("h1,h2,h3,h4")].find((h) => slug(h.textContent) === hash);
    (anchor || reader).scrollIntoView({ block: "start" });
  }

  const slug = (text) => text.toLowerCase().trim().replace(/[^\w\s-]/g, "").replace(/\s+/g, "-");

  function showList() {
    list.hidden = false;
    search.hidden = false;
    back.hidden = true;
    reader.hidden = true;
  }

  reader.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-doc]");
    if (!link) return;
    event.preventDefault();
    const target = link.dataset.doc;
    if (target.split("#")[0].endsWith(".md")) open(target);
    else window.open(`rea-docs/${target}`, "_blank");
  });
  search.addEventListener("input", renderList);
  back.addEventListener("click", showList);

  return {
    async load() {
      if (loaded) return;
      try {
        const res = await fetch("rea-docs/index.json");
        if (!res.ok) throw new Error();
        pages = (await res.json()).pages;
        loaded = true;
        renderList();
      } catch {
        list.innerHTML =
          '<li class="meta">Docs are not bundled with this server. Build the offline bundle (see README) or set REA_MOBILE_DOCS to REA\'s docs folder.</li>';
      }
    },
  };
}
