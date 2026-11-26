import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, Media, Session, setAuthLostHandler, Status } from "./api";
import { fmtBytes, ResumableUpload, UploadProgress } from "./upload";

// ------------------------------------------------------------------ formatting helpers
const pad = (n: number) => String(Math.floor(n)).padStart(2, "0");
function hms(sec: number) {
  sec = Math.max(0, sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.floor(sec % 60);
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
function fmtTime(ts: number | null | undefined, tz: string) {
  if (!ts) return "—";
  return new Intl.DateTimeFormat("en-IN", { timeZone: tz, dateStyle: "medium", timeStyle: "short" }).format(ts * 1000);
}
async function copy(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  }
}
const LIVE_STATES = new Set(["live"]);
const WARN_STATES = new Set(["reconnecting", "end_pending", "failed", "stopping"]);

function useToast() {
  const [msg, setMsg] = useState<string | null>(null);
  const t = useRef<number>();
  const show = useCallback((m: string) => {
    setMsg(m); window.clearTimeout(t.current); t.current = window.setTimeout(() => setMsg(null), 2600);
  }, []);
  return { msg, show };
}

// ------------------------------------------------------------------ login
function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const expired = new URLSearchParams(location.search).get("expired");
  return (
    <div className="login">
      <form className="card" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setErr(null);
        try { await api("/api/login", { method: "POST", json: { password: pw } }); onDone(); }
        catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
      }}>
        <h1><span className="logo">⟳</span> Replay Studio</h1>
        {expired && <p className="muted">Your session expired. Log in again.</p>}
        <label>Dashboard password
          <input type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} autoFocus />
        </label>
        {err && <p className="error">{err}</p>}
        <button className="primary" disabled={busy || !pw}>Log in</button>
      </form>
    </div>
  );
}

// ------------------------------------------------------------------ live panel
function LivePanel({ s, tz, now, toast, onChange }: { s: Session; tz: string; now: number; toast: (m: string) => void; onChange: () => void }) {
  const [confirmStop, setConfirmStop] = useState(false);
  const [events, setEvents] = useState<{ ts: number; level: string; message: string }[]>([]);
  const [showLog, setShowLog] = useState(false);
  const isLive = LIVE_STATES.has(s.state);
  const liveFor = s.live_since ? (s.ended_at || now) - s.live_since : 0;
  const pct = s.media_duration ? (s.loop_position / s.media_duration) * 100 : 0;

  useEffect(() => {
    if (!showLog) return;
    api<{ events: any[] }>(`/api/sessions/${s.id}`).then((d) => setEvents(d.events)).catch(() => {});
  }, [showLog, s.id, s.state, s.reconnect_attempts]);

  const stop = async () => {
    setConfirmStop(false);
    try { await api(`/api/sessions/${s.id}/stop`, { method: "POST" }); toast("Stop requested — ending the broadcast"); onChange(); }
    catch (e) { toast((e as Error).message); }
  };
  const m = s.metrics || {};
  const metric = (v: string | undefined) => (v === undefined || v === null ? <span className="na">Unavailable</span> : v);

  return (
    <section className="card live-card">
      <div className="row between">
        <span className={`badge ${isLive ? "live" : WARN_STATES.has(s.state) ? "warn" : "info"}`}>
          {isLive && <span className="dot" />}{s.state_label}
        </span>
        <span className="muted small">{s.privacy}{s.made_for_kids ? " · made for kids" : ""} · Loop until I stop</span>
      </div>
      <h2 className="title">{s.title}</h2>
      <p className="muted small">Video: {s.media_name}</p>
      {s.error && <p className={s.state === "reconnecting" ? "warnbox" : "error"}>{s.error}</p>}
      {s.state === "scheduled" && <p>Starts {fmtTime(s.scheduled_start_utc, tz)} ({tz}). It will loop until you stop it.</p>}

      {s.watch_url && (
        <div className="linkbox">
          <a href={s.watch_url} target="_blank" rel="noreferrer">{s.watch_url}</a>
          <div className="row wrap">
            <button onClick={async () => toast((await copy(s.watch_url!)) ? "Watch link copied" : "Copy failed")}>Copy watch link</button>
            <a className="button" href={s.watch_url} target="_blank" rel="noreferrer">Open on YouTube</a>
            <a className="button" href={s.studio_url!} target="_blank" rel="noreferrer">Open in YouTube Studio</a>
          </div>
        </div>
      )}

      <div className="stats">
        <div><span className="k">Time live</span><span className="v">{isLive || s.live_since ? hms(liveFor) : "—"}</span></div>
        <div><span className="k">Completed loops</span><span className="v">{s.loops_completed}</span></div>
        <div><span className="k">Position in loop</span><span className="v">{hms(s.loop_position)} / {hms(s.media_duration)}</span></div>
        <div><span className="k">Total played</span><span className="v">{hms(s.played_total)}</span></div>
      </div>
      <div className="progress"><div style={{ width: `${pct}%` }} /></div>

      <h3>Ingest health</h3>
      <div className="stats">
        <div><span className="k">YouTube stream</span><span className="v">{s.ingest?.stream_status ?? <span className="na">Not checked yet</span>}</span></div>
        <div><span className="k">YouTube health</span><span className={`v health-${s.ingest?.health}`}>{s.ingest?.health ?? <span className="na">Unavailable</span>}</span></div>
        <div><span className="k">Encoder speed</span><span className="v">{s.encoder ? `${s.encoder.speed.toFixed(2)}×` : "—"}</span></div>
        <div><span className="k">Bitrate / FPS</span><span className="v">{s.encoder ? `${Math.round(s.encoder.bitrate_kbps)} kbps · ${s.encoder.fps.toFixed(0)}` : "—"}</span></div>
      </div>
      {s.ingest?.issues?.length ? (
        <ul className="issues">{s.ingest.issues.map((i, k) => <li key={k}><b>{i.severity}</b> {i.description || i.reason}</li>)}</ul>
      ) : null}
      {s.reconnect_attempts > 0 && <p className="muted small">Reconnect attempts: {s.reconnect_attempts}</p>}

      <h3>Audience (from YouTube API)</h3>
      <div className="stats">
        <div><span className="k">Watching now</span><span className="v">{metric(m.concurrent_viewers)}</span></div>
        <div><span className="k">Views</span><span className="v">{metric(m.view_count)}</span></div>
        <div><span className="k">Likes</span><span className="v">{metric(m.like_count)}</span></div>
        <div><span className="k">Live chat</span><span className="v">{m.has_live_chat === undefined ? <span className="na">Unavailable</span> : m.has_live_chat ? "Active" : "Not active"}</span></div>
      </div>
      <p className="muted small">"Unavailable" means YouTube did not return that number (it hides some counts, e.g. viewers on unlisted or not-yet-live streams).</p>

      {s.state === "failed" && !s.stop_requested && (
        <button onClick={async () => { await api(`/api/sessions/${s.id}/retry`, { method: "POST" }); onChange(); }}>Retry same broadcast</button>
      )}
      <button className="link" onClick={() => setShowLog(!showLog)}>{showLog ? "Hide" : "Show"} activity log</button>
      {showLog && <ul className="log">{events.map((e, i) => <li key={i} className={e.level}><span>{fmtTime(e.ts, tz)}</span> {e.message}</li>)}</ul>}

      {s.active && (
        <div className="stopbar">
          {s.stop_requested ? (
            <button className="stop" disabled>{s.state === "end_pending" ? "End confirmation pending…" : "Stopping…"}</button>
          ) : confirmStop ? (
            <div className="row">
              <button className="stop" onClick={stop}>Yes, end the broadcast</button>
              <button onClick={() => setConfirmStop(false)}>Keep streaming</button>
            </div>
          ) : (
            <button className="stop" onClick={() => setConfirmStop(true)}>■ Stop stream</button>
          )}
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ YouTube account
function Account({ st, toast, refresh }: { st: Status; toast: (m: string) => void; refresh: () => void }) {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<{ matches: boolean; value: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const connect = async () => {
    setErr(null);
    try { const { url } = await api<{ url: string }>("/api/youtube/connect"); location.href = url; }
    catch (e) { setErr((e as Error).message); }
  };
  if (!st.connected || !st.channel) {
    return (
      <section className="card">
        <h2>1 · Connect YouTube</h2>
        <p className="muted">Sign in with the Google account that owns your channel. Tokens stay on the host.</p>
        {!st.oauth_configured && <p className="warnbox">Google OAuth is not configured on the host yet. See README → “Google Cloud OAuth”.</p>}
        {err && <p className="error">{err}</p>}
        <button className="primary" onClick={connect} disabled={!st.oauth_configured}>Connect YouTube account</button>
      </section>
    );
  }
  return (
    <section className="card">
      <h2>1 · YouTube channel</h2>
      <div className="row">
        {st.channel.avatar && <img className="avatar" src={st.channel.avatar} alt="" referrerPolicy="no-referrer" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />}
        <div>
          <b>{st.channel.title}</b>
          <div className="muted small">{st.channel.handle || st.channel.id}</div>
        </div>
      </div>
      <form className="row wrap" onSubmit={async (e) => {
        e.preventDefault(); setErr(null); setResult(null);
        try { setResult(await api("/api/youtube/verify-channel", { method: "POST", json: { url } })); }
        catch (e) { setErr((e as Error).message); }
      }}>
        <input placeholder="Optional: paste youtube.com/@handle or /channel/ID to verify" value={url} onChange={(e) => setUrl(e.target.value)} />
        <button disabled={!url}>Verify</button>
      </form>
      {result && (result.matches
        ? <p className="ok">✓ {result.value} is the connected channel.</p>
        : <p className="error">✗ {result.value} is not the connected channel. Disconnect and sign in with the right Google account / brand channel.</p>)}
      {err && <p className="error">{err}</p>}
      <button className="link" onClick={async () => {
        try { await api("/api/youtube/disconnect", { method: "POST" }); refresh(); toast("Disconnected"); } catch (e) { toast((e as Error).message); }
      }}>Disconnect</button>
    </section>
  );
}

// ------------------------------------------------------------------ media library
function Library({ selected, setSelected, toast }: { selected: string | null; setSelected: (id: string | null) => void; toast: (m: string) => void }) {
  const [lib, setLib] = useState<{ items: Media[]; usage_bytes: number; quota_bytes: number; free_bytes: number; pending_uploads: any[] } | null>(null);
  const [folder, setFolder] = useState<{ root: string; exists: boolean; files: { path: string; size: number }[] } | null>(null);
  const [prog, setProg] = useState<UploadProgress | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const up = useRef<ResumableUpload | null>(null);
  const load = useCallback(() => api("/api/media").then(setLib).catch((e) => setErr(e.message)), []);
  useEffect(() => { load(); const t = setInterval(load, 3000); return () => clearInterval(t); }, [load]);

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    const u = new ResumableUpload(f, setProg);
    up.current = u;
    try { const m = await u.run(); setSelected(m.id); toast("Upload complete — checking the file"); load(); }
    catch (e) { setErr((e as Error).message); }
    finally { up.current = null; }
  };
  const sel = lib?.items.find((m) => m.id === selected);

  return (
    <section className="card">
      <h2>2 · Video</h2>
      <div className="row wrap">
        <label className="button primary filebtn">Upload video from this device
          <input type="file" accept="video/*,.mp4,.mov,.mkv" onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
        <button onClick={() => api("/api/media/folder").then(setFolder).catch((e) => setErr(e.message))}>Choose from host media folder</button>
      </div>
      {lib?.pending_uploads?.length ? <p className="muted small">Unfinished upload: {lib.pending_uploads.map((u) => `${u.filename} (${fmtBytes(u.received)} of ${fmtBytes(u.size)})`).join(", ")}. Select the same file again to resume.</p> : null}
      {prog && prog.state !== "done" && (
        <div className="upload">
          <div className="row between small"><span>{prog.name}</span><span>{fmtBytes(prog.sent)} / {fmtBytes(prog.total)}{prog.bytesPerSec ? ` · ${fmtBytes(prog.bytesPerSec)}/s` : ""}</span></div>
          <div className="progress"><div style={{ width: `${(prog.sent / prog.total) * 100}%` }} /></div>
          {prog.message && <p className={prog.state === "error" ? "error" : "muted small"}>{prog.message}</p>}
          <div className="row">
            {prog.state === "paused" ? <button onClick={() => up.current?.resume()}>Resume</button> : <button onClick={() => up.current?.pause()}>Pause</button>}
            <button onClick={() => { up.current?.cancel(); setProg(null); }}>Cancel</button>
          </div>
        </div>
      )}
      {folder && (
        <div className="folder">
          <p className="muted small">Host folder: {folder.root}{!folder.exists && " (does not exist — set paths.media_dir)"}</p>
          {folder.files.length === 0 && <p className="muted small">No video files found.</p>}
          <ul>{folder.files.map((f) => (
            <li key={f.path}><button className="link" onClick={async () => {
              try { const m = await api<Media>("/api/media/import", { method: "POST", json: { path: f.path } }); setSelected(m.id); setFolder(null); load(); }
              catch (e) { setErr((e as Error).message); }
            }}>{f.path}</button> <span className="muted small">{fmtBytes(f.size)}</span></li>
          ))}</ul>
        </div>
      )}
      {err && <p className="error">{err}</p>}
      <ul className="media">
        {lib?.items.map((m) => (
          <li key={m.id} className={m.id === selected ? "sel" : ""} onClick={() => setSelected(m.id)}>
            <img src={m.status === "ok" ? `/api/media/${m.id}/thumb` : undefined} alt="" />
            <div className="grow">
              <div className="name">{m.name}</div>
              <div className="small muted">
                {m.status === "ok" && m.probe ? `${hms(m.probe.duration)} · ${m.probe.width}×${m.probe.height} · ${m.probe.has_audio ? "audio" : "no audio (silent track added)"}` :
                  m.status === "invalid" ? <span className="error">{m.error}</span> :
                  m.status === "preparing" ? "Preparing loop-ready copy…" : "Checking file…"}
              </div>
            </div>
            <span className={`badge ${m.status === "ok" ? "okb" : m.status === "invalid" ? "bad" : "info"}`}>{m.status === "ok" ? "Ready" : m.status}</span>
          </li>
        ))}
      </ul>
      {lib && <p className="muted small">Library: {fmtBytes(lib.usage_bytes)} of {fmtBytes(lib.quota_bytes)} · host free space {fmtBytes(lib.free_bytes)}</p>}
      {sel && sel.status === "ok" && sel.probe && (
        <div className="preview">
          <video src={`/api/media/${sel.id}/file`} controls playsInline preload="metadata" />
          <dl>
            <dt>Duration</dt><dd>{hms(sel.probe.duration)}</dd>
            <dt>Resolution</dt><dd>{sel.probe.width}×{sel.probe.height} @ {sel.probe.fps} fps ({sel.probe.video_codec})</dd>
            <dt>Audio</dt><dd>{sel.probe.has_audio ? `Yes (${sel.probe.audio_codec})` : "No — a silent track is added for YouTube"}</dd>
            <dt>Loop-ready copy</dt><dd>{sel.probe.loop_ready?.video ?? "—"}; audio aligned to the exact video length</dd>
            {sel.probe.issues.length > 0 && <><dt>Fixed for looping</dt><dd>{sel.probe.issues.join("; ")}</dd></>}
          </dl>
          {!sel.in_use && <button className="link danger" onClick={async () => { await api(`/api/media/${sel.id}`, { method: "DELETE" }); setSelected(null); load(); }}>Remove from library</button>}
        </div>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ overlay
type OverlayCfg = { enabled: boolean; text: string; every_minutes: number; show_seconds: number; position: "top" | "bottom" };
function OverlayEditor({ ov, setOv, mediaId }: { ov: OverlayCfg; setOv: (o: OverlayCfg) => void; mediaId: string | null }) {
  const [img, setImg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const preview = async () => {
    setErr(null);
    try {
      const blob = await api<Blob>(`/api/overlay/preview${mediaId ? `?media_id=${mediaId}` : ""}`, { method: "POST", json: ov });
      setImg(URL.createObjectURL(blob));
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <fieldset>
      <legend>Subscribe overlay (optional)</legend>
      <label className="check"><input type="checkbox" checked={ov.enabled} onChange={(e) => setOv({ ...ov, enabled: e.target.checked })} /> Show a subscribe reminder on the video</label>
      <label>Text<input maxLength={120} value={ov.text} onChange={(e) => setOv({ ...ov, text: e.target.value })} /></label>
      <div className="row">
        <label>Every (minutes)<input type="number" min={1} max={1440} value={ov.every_minutes} onChange={(e) => setOv({ ...ov, every_minutes: Number(e.target.value) })} /></label>
        <label>Show for (seconds)<input type="number" min={2} max={600} value={ov.show_seconds} onChange={(e) => setOv({ ...ov, show_seconds: Number(e.target.value) })} /></label>
        <label>Position<select value={ov.position} onChange={(e) => setOv({ ...ov, position: e.target.value as "top" | "bottom" })}><option value="bottom">Bottom</option><option value="top">Top</option></select></label>
      </div>
      <button type="button" onClick={preview}>Preview overlay</button>
      {err && <p className="error">{err}</p>}
      {img && <img className="ovprev" src={img} alt="Overlay preview" />}
      <p className="muted small">Rendered by the same FFmpeg filter used on the stream. Overlay settings apply when a stream starts.</p>
    </fieldset>
  );
}

// ------------------------------------------------------------------ stream form
function StreamForm({ st, mediaId, toast, onStarted }: { st: Status; mediaId: string | null; toast: (m: string) => void; onStarted: () => void }) {
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [privacy, setPrivacy] = useState("unlisted");
  const [kids, setKids] = useState<"" | "yes" | "no">("");
  const [rights, setRights] = useState(false);
  const [publicOk, setPublicOk] = useState(false);
  const [mode, setMode] = useState<"now" | "schedule">("now");
  const [when, setWhen] = useState("");
  const [ov, setOv] = useState<OverlayCfg>({ enabled: false, text: "Enjoying the stream? Subscribe!", every_minutes: 10, show_seconds: 8, position: "bottom" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const idem = useRef(crypto.randomUUID ? crypto.randomUUID() : String(Math.random()));
  useEffect(() => {
    api("/api/defaults").then((d) => { setDesc(d.description); setOv(d.overlay); }).catch(() => {});
  }, []);
  const tz = st.timezone;
  // datetime-local is wall-clock time in the dashboard time zone (default Asia/Kolkata); the server stores UTC.
  const scheduleUtc = when || null;
  const ready = st.connected && mediaId && title.trim() && kids && rights && (privacy !== "public" || publicOk) && (mode === "now" || scheduleUtc);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try {
      await api("/api/settings/overlay", { method: "PUT", json: ov }).catch(() => {});
      await api("/api/sessions", { method: "POST", json: {
        media_id: mediaId, title, description: desc, privacy, made_for_kids: kids === "yes",
        confirm_rights: rights, confirm_public: publicOk, scheduled_start: mode === "schedule" ? when : null,
        idempotency_key: idem.current, overlay: ov,
      } });
      toast(mode === "now" ? "Starting stream…" : "Stream scheduled");
      idem.current = crypto.randomUUID ? crypto.randomUUID() : String(Math.random());
      onStarted();
    } catch (e) {
      const ae = e as ApiError;
      setErr(ae.message);
      if (ae.status === 409) onStarted();
    } finally { setBusy(false); }
  };

  return (
    <form className="card" onSubmit={submit}>
      <h2>3 · Stream details</h2>
      <label>Title<input maxLength={100} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What viewers will see" /></label>
      <label>Description<textarea rows={4} maxLength={5000} value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
      <p className="muted small">Keep the disclosure that this is a prerecorded video on repeat.</p>
      <div className="row wrap">
        <label>Privacy<select value={privacy} onChange={(e) => { setPrivacy(e.target.value); setPublicOk(false); }}>
          <option value="unlisted">Unlisted (default)</option><option value="private">Private</option><option value="public">Public</option>
        </select></label>
        <label>Playback<select disabled value="loop"><option value="loop">Loop until I stop</option></select></label>
      </div>
      {privacy === "public" && (
        <label className="check warnbox"><input type="checkbox" checked={publicOk} onChange={(e) => setPublicOk(e.target.checked)} />
          I understand this broadcast will be <b>public</b> and visible to anyone, {mode === "schedule" ? "and will be listed as an upcoming stream" : "starting now"}.</label>
      )}
      <fieldset>
        <legend>Audience (required by YouTube)</legend>
        <label className="check"><input type="radio" name="kids" checked={kids === "no"} onChange={() => setKids("no")} /> No, it's not made for kids</label>
        <label className="check"><input type="radio" name="kids" checked={kids === "yes"} onChange={() => setKids("yes")} /> Yes, it's made for kids (disables live chat)</label>
      </fieldset>
      <label className="check"><input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
        I own or have the rights to rebroadcast this video and its audio on YouTube.</label>
      <fieldset>
        <legend>When</legend>
        <label className="check"><input type="radio" checked={mode === "now"} onChange={() => setMode("now")} /> Start now</label>
        <label className="check"><input type="radio" checked={mode === "schedule"} onChange={() => setMode("schedule")} /> Schedule</label>
        {mode === "schedule" && (
          <label>Start time ({tz})<input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></label>
        )}
        <p className="muted small">The stream repeats the video in one broadcast until you press Stop stream. No time or loop limit.</p>
      </fieldset>
      <OverlayEditor ov={ov} setOv={setOv} mediaId={mediaId} />
      {err && <p className="error">{err}</p>}
      {!st.worker.online && <p className="warnbox">The stream worker service is not running on the host. Start it: <code>sudo systemctl start replay-studio-worker</code></p>}
      <button className="primary big" disabled={!ready || busy}>{mode === "now" ? "▶ Start stream" : "Schedule stream"}</button>
      {!mediaId && <p className="muted small">Select a ready video above.</p>}
    </form>
  );
}

// ------------------------------------------------------------------ audience helpers
function AudienceTools({ session, toast }: { session: Session | null; toast: (m: string) => void }) {
  const [msgs, setMsgs] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  useEffect(() => { api("/api/defaults").then((d) => setMsgs(d.chat.messages)).catch(() => {}); }, []);
  const save = (m: string[]) => { setMsgs(m); api("/api/settings/chat", { method: "PUT", json: { messages: m } }).catch(() => {}); };
  const share = session?.watch_url ? `${session.title} — live now, on repeat: ${session.watch_url}` : "";
  return (
    <section className="card">
      <h2>Chat & sharing helpers</h2>
      <p className="muted small">Prepare messages and post them yourself in YouTube live chat. Replay Studio never posts, views, likes or subscribes automatically.</p>
      <ul className="chat">{msgs.map((m, i) => (
        <li key={i}><span className="grow">{m}</span>
          <button onClick={async () => toast((await copy(m)) ? "Copied — paste it in live chat" : "Copy failed")}>Copy</button>
          <button className="link" onClick={() => save(msgs.filter((_, k) => k !== i))}>✕</button></li>))}
      </ul>
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) { save([...msgs, draft.trim()]); setDraft(""); } }}>
        <input maxLength={200} placeholder="Add a chat message or discussion question" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button>Add</button>
      </form>
      {share && <button onClick={async () => toast((await copy(share)) ? "Share text copied" : "Copy failed")}>Copy share text</button>}
    </section>
  );
}

// ------------------------------------------------------------------ app
export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [st, setSt] = useState<Status | null>(null);
  const [netErr, setNetErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now() / 1000);
  const { msg, show } = useToast();
  const params = new URLSearchParams(location.search);
  const [banner, setBanner] = useState<string | null>(params.get("error") ? `YouTube connection failed: ${params.get("error")}` : params.get("connected") ? "YouTube account connected." : null);

  const refresh = useCallback(async () => {
    try { const s = await api<Status>("/api/status"); setSt(s); setAuthed(true); setNetErr(null); }
    catch (e) {
      const ae = e as ApiError;
      if (ae.status === 401) setAuthed(false); else setNetErr(ae.message);
    }
  }, []);
  useEffect(() => { setAuthLostHandler(() => setAuthed(false)); refresh(); }, [refresh]);
  useEffect(() => {
    if (!authed) return;
    const t = setInterval(refresh, 2000);
    const c = setInterval(() => setNow(Date.now() / 1000), 1000);
    const vis = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", vis);
    return () => { clearInterval(t); clearInterval(c); document.removeEventListener("visibilitychange", vis); };
  }, [authed, refresh]);
  useEffect(() => { if (banner) history.replaceState(null, "", "/"); }, [banner]);

  if (authed === false) return <Login onDone={() => { setAuthed(true); refresh(); }} />;
  if (!st) return <div className="center muted">{netErr || "Loading…"}</div>;
  // skew-correct the client clock against the server for "time live"
  const serverNow = now + (st.server_time - Date.now() / 1000);

  return (
    <div className={`app ${st.session?.active ? "has-stop" : ""}`}>
      <header>
        <h1><span className="logo">⟳</span> Replay Studio</h1>
        <div className="row">
          <span className={`pill ${st.worker.online ? "ok" : "bad"}`} title="Background stream worker on the host">{st.worker.online ? "Worker online" : "Worker offline"}</span>
          {st.channel?.avatar && <img className="avatar sm" src={st.channel.avatar} alt="" referrerPolicy="no-referrer" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />}
          <button className="link" onClick={async () => { await api("/api/logout", { method: "POST" }); setAuthed(false); }}>Log out</button>
        </div>
      </header>
      {netErr && <p className="warnbox">{netErr} The stream keeps running on the host.</p>}
      {banner && <p className={banner.includes("failed") ? "error" : "ok"} onClick={() => setBanner(null)}>{banner}</p>}
      <main>
        {st.session ? (
          <LivePanel s={st.session} tz={st.timezone} now={serverNow} toast={show} onChange={refresh} />
        ) : (
          <>
            <Account st={st} toast={show} refresh={refresh} />
            <Library selected={selected} setSelected={setSelected} toast={show} />
            <StreamForm st={st} mediaId={selected} toast={show} onStarted={refresh} />
          </>
        )}
        <AudienceTools session={st.session} toast={show} />
        {st.recent.length > 0 && (
          <section className="card">
            <h2>History</h2>
            <ul className="history">{st.recent.map((s) => (
              <li key={s.id}>
                <div className="grow"><b>{s.title}</b><div className="small muted">{fmtTime(s.created_at, st.timezone)} · {s.state_label} · {s.loops_completed} loops</div>
                  {s.error && !s.active && <div className="small error">{s.error}</div>}</div>
                {s.watch_url && <a href={s.watch_url} target="_blank" rel="noreferrer">Watch</a>}
              </li>))}
            </ul>
          </section>
        )}
        <p className="muted small center">Times shown in {st.timezone}. The stream runs on the host and keeps going if you close this page.</p>
      </main>
      {msg && <div className="toast">{msg}</div>}
    </div>
  );
}
