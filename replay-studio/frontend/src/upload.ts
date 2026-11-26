import { api, ApiError, Media } from "./api";

export type UploadProgress = {
  name: string; sent: number; total: number; bytesPerSec: number; state: "uploading" | "retrying" | "paused" | "done" | "error";
  message?: string;
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const keyFor = (f: File) => `rs-upload:${f.name}:${f.size}:${f.lastModified}`;

/** Chunked, resumable upload. Survives dropped connections (retries with backoff) and page reloads
 *  (the server remembers the offset; re-selecting the same file resumes). */
export class ResumableUpload {
  private paused = false;
  private cancelled = false;
  constructor(private file: File, private onProgress: (p: UploadProgress) => void) {}

  pause() { this.paused = true; }
  resume() { this.paused = false; }
  cancel() { this.cancelled = true; }

  async run(): Promise<Media> {
    const f = this.file;
    const created = await api<{ id: string; received: number; chunk_bytes: number }>("/api/uploads", {
      method: "POST", json: { filename: f.name, size: f.size },
    });
    try { localStorage.setItem(keyFor(f), created.id); } catch { /* private mode */ }
    let offset = created.received;
    const chunk = created.chunk_bytes;
    let failures = 0;
    let windowStart = performance.now(), windowBytes = 0, rate = 0;
    const report = (state: UploadProgress["state"], message?: string) =>
      this.onProgress({ name: f.name, sent: offset, total: f.size, bytesPerSec: rate, state, message });
    report("uploading", offset ? "Resuming previous upload" : undefined);
    while (offset < f.size) {
      if (this.cancelled) throw new Error("Upload cancelled");
      if (this.paused) { report("paused"); await sleep(400); continue; }
      const blob = f.slice(offset, Math.min(offset + chunk, f.size));
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 120_000);
        const res = await fetch(`/api/uploads/${created.id}?offset=${offset}`, {
          method: "PUT", body: blob, signal: ctrl.signal, credentials: "same-origin",
          headers: { "X-Replay-Studio": "1", "Content-Type": "application/octet-stream" },
        });
        clearTimeout(timer);
        const data = await res.json().catch(() => ({}));
        if (res.status === 409 && typeof data.received === "number") { offset = data.received; continue; }
        if (!res.ok) {
          if ([400, 401, 404, 413, 507].includes(res.status)) throw new ApiError(res.status, data.detail || "Upload refused", data);
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        windowBytes += data.received - offset;
        offset = data.received;
        failures = 0;
        const el = (performance.now() - windowStart) / 1000;
        if (el > 1) { rate = windowBytes / el; windowBytes = 0; windowStart = performance.now(); }
        if (data.complete) {
          try { localStorage.removeItem(keyFor(f)); } catch { /* ignore */ }
          report("done");
          return data.media as Media;
        }
        report("uploading", rate && rate < 200_000 ? "Slow connection: upload will take a while. Keep this page open." : undefined);
      } catch (e) {
        if (e instanceof ApiError) { report("error", e.message); throw e; }
        failures += 1;
        const wait = Math.min(30, 2 ** Math.min(failures, 5));
        report("retrying", `Connection unstable (attempt ${failures}). Resuming in ${wait}s from ${fmtBytes(offset)}.`);
        await sleep(wait * 1000);
        try { // ask the server where we really are
          const st = await api<{ received: number }>(`/api/uploads/${created.id}`);
          offset = st.received;
        } catch { /* still offline; loop retries */ }
      }
    }
    throw new Error("Upload ended unexpectedly");
  }
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}
