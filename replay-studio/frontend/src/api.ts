export class ApiError extends Error {
  status: number;
  code?: string;
  body: any;
  constructor(status: number, message: string, body: any) {
    super(message);
    this.status = status;
    this.code = body?.code;
    this.body = body;
  }
}

let onAuthLost: () => void = () => {};
export function setAuthLostHandler(fn: () => void) {
  onAuthLost = fn;
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Replay-Studio": "1", ...(opts.headers as any) };
  let body = opts.body;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  let res: Response;
  try {
    res = await fetch(path, { ...opts, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Cannot reach the Replay Studio host. Check that your phone and the host are online.", null);
  }
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json") ? await res.json() : null;
  if (!res.ok) {
    if (res.status === 401 && data?.code === "auth_required") onAuthLost();
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((d: any) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ")
      : data?.detail;
    throw new ApiError(res.status, detail || `Request failed (${res.status})`, data);
  }
  return (data ?? (await res.blob())) as T;
}

export type Probe = {
  duration: number; width: number; height: number; fps: number; has_audio: boolean;
  video_codec: string; audio_codec: string | null; issues: string[]; loop_ready?: { video: string };
};
export type Media = {
  id: string; name: string; source: string; size: number; status: string; error: string | null;
  probe: Probe | null; loop_ready: boolean; in_use: boolean; created_at: number;
};
export type Session = {
  id: string; state: string; state_label: string; active: boolean; stop_requested: boolean;
  title: string; description: string; privacy: string; made_for_kids: boolean; media_name: string;
  scheduled_start_utc: number | null; broadcast_id: string | null; watch_url: string | null; studio_url: string | null;
  live_since: number | null; time_live_seconds: number; media_duration: number; played_total: number;
  loop_position: number; loops_completed: number;
  encoder: { fps: number; bitrate_kbps: number; speed: number; dropped: number; run_seconds: number } | null;
  ingest: { stream_status: string; health: string; issues: { severity: string; reason: string; description: string }[]; checked_at: number } | null;
  metrics: { concurrent_viewers?: string; view_count?: string; like_count?: string; comment_count?: string; has_live_chat?: boolean; fetched_at?: number } | null;
  error: string | null; error_kind: string | null; reconnect_attempts: number; created_at: number; ended_at: number | null;
};
export type Status = {
  connected: boolean; oauth_configured: boolean;
  channel: { id: string; title: string; handle: string; avatar: string } | null;
  session: Session | null; recent: Session[]; worker: { online: boolean; last_seen_seconds: number | null };
  timezone: string; server_time: number;
};
