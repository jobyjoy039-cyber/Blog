"""End-to-end acceptance tests against the local fake YouTube API and a real RTMP receiver.

Everything runs as separate processes, as in production: fake YouTube, the API, and the worker.
"""
from __future__ import annotations

import concurrent.futures
import signal
import time
import uuid
from pathlib import Path

from av_analysis import analyse, make_test_source
from conftest import wait_for

LOOP = 4.0


def live_session(stack, test_video, **kw) -> dict:
    mid = stack.upload(test_video)
    s = stack.start_session(mid, **kw)
    stack.current_id = s["id"]
    return stack.wait_state("live", 60)


def stop_and_confirm(stack) -> dict:
    r = stack.client.post(f"/api/sessions/{stack.current_id}/stop")
    assert r.status_code == 200
    return stack.wait_state("ended", 40)


def test_three_loops_continuous_av_sync(stack, test_video):
    s = live_session(stack, test_video)
    bid = s["broadcast_id"]
    assert s["state_label"] == "Live" and s["watch_url"].endswith(bid)
    # Let it run for well over three passes of the 4-second file.
    s = wait_for(lambda: (x := stack.session()) and x["loops_completed"] >= 3 and x["played_total"] > 14 and x,
                 60, what="3 loops")
    assert s["state"] == "live" and s["broadcast_id"] == bid
    enc = s["encoder"]
    assert 0.9 <= enc["speed"] <= 1.1, enc            # real time
    time.sleep(1.5)
    stop_and_confirm(stack)

    fs = stack.fake_state()
    assert len(fs["broadcasts"]) == 1 and fs["insert_calls"] == 1
    assert fs["broadcasts"][0]["status"]["lifeCycleStatus"] == "complete"
    assert [t["to"] for t in fs["transitions"]] == ["live", "complete"]
    seg = Path(list(fs["segments"].values())[0][0])
    assert list(fs["connections"].values()) == [1], "one uninterrupted encoder connection"
    r = analyse(seg, LOOP)
    print(r)
    assert len(r["flash_onsets"]) >= 4, r              # start + >= 3 loop boundaries
    for gap in r["loop_spacing"]:
        assert abs(gap - LOOP) < 0.02, r["loop_spacing"]      # each pass is exactly one file length
    offs = r["av_offsets"]
    assert all(o is not None and abs(o) < 0.035 for o in offs), offs   # within one frame of sync
    assert max(offs) - min(offs) < 0.01, offs                 # and it does not drift loop to loop
    assert r["max_video_gap"] < 0.04, r                       # no dropped/held frames at boundaries
    assert r["max_audio_gap"] < 0.03 and r["audio_backwards"] == 0, r
    assert not r["black"], r["black"]
    assert not r["silence"], r["silence"]
    assert abs(r["video_span"] - r["audio_span"]) < 0.2


def test_survives_dashboard_closing_and_shows_current_session(stack, test_video):
    s = live_session(stack, test_video)
    bid = s["broadcast_id"]
    played = s["played_total"]
    stack.client.close()          # "browser closed"
    stack.stop_api()              # even the dashboard server goes away
    time.sleep(8)
    assert len(stack.our_encoders()) == 1
    stack.start_api()
    stack.login()                 # reopen the dashboard
    s2 = stack.session()
    assert s2["id"] == s["id"] and s2["state"] == "live" and s2["broadcast_id"] == bid
    assert s2["played_total"] > played + 6
    assert s2["watch_url"] == s["watch_url"]
    stop_and_confirm(stack)


def test_duplicate_starts_and_worker_restart_do_not_duplicate(stack, test_video):
    mid = stack.upload(test_video)
    body = {"media_id": mid, "title": "dup test", "made_for_kids": False, "confirm_rights": True}
    key = str(uuid.uuid4())

    def click(i):
        k = key if i < 8 else str(uuid.uuid4())   # repeated taps + a second tab
        return stack.client.post("/api/sessions", json={**body, "idempotency_key": k})
    with concurrent.futures.ThreadPoolExecutor(12) as ex:
        results = list(ex.map(click, range(12)))
    ids = {r.json().get("session", {}).get("id") or r.json().get("existing_id") for r in results}
    assert len(ids) == 1, [r.text for r in results]
    assert sum(1 for r in results if r.status_code == 200 and not r.json()["duplicate"]) == 1
    stack.current_id = ids.pop()
    s = stack.wait_state("live", 60)
    bid = s["broadcast_id"]

    # Crash the worker hard; its FFmpeg must die with it (no double ingest).
    stack.stop("worker", signal.SIGKILL)
    wait_for(lambda: not stack.our_encoders(), 10, what="encoder to exit with worker")
    stack.start_worker()
    time.sleep(3)
    s = stack.wait_state("live", 40)
    wait_for(lambda: stack.session()["encoder"]["run_seconds"] > 2, 20, what="resumed encoder")
    assert s["broadcast_id"] == bid
    assert len(stack.our_encoders()) == 1
    fs = stack.fake_state()
    assert fs["insert_calls"] == 1 and len(fs["broadcasts"]) == 1 and len(fs["streams"]) == 1
    assert [t["to"] for t in fs["transitions"]] == ["live"], "no second transition after restart"
    # Restart again in the middle of a normal run: still nothing new.
    stack.stop("worker")
    stack.start_worker()
    stack.wait_state("live", 40)
    time.sleep(3)
    stop_and_confirm(stack)
    fs = stack.fake_state()
    assert fs["insert_calls"] == 1 and [t["to"] for t in fs["transitions"]] == ["live", "complete"]


def test_network_failure_reconnects_then_stop_while_reconnecting_never_resumes(stack, test_video):
    s = live_session(stack, test_video)
    bid = s["broadcast_id"]
    # 1) outage then recovery into the same broadcast
    stack.fake.post("/_control/ingest", params={"up": False})
    stack.wait_state("reconnecting", 20)
    assert stack.session()["state_label"] == "Reconnecting"
    time.sleep(3)
    stack.fake.post("/_control/ingest", params={"up": True})
    s = stack.wait_state("live", 40)
    assert s["broadcast_id"] == bid
    pos_after = s["played_total"]
    assert pos_after > 0
    # 2) outage again, press Stop while reconnecting
    stack.fake.post("/_control/ingest", params={"up": False})
    stack.wait_state("reconnecting", 20)
    stack.client.post(f"/api/sessions/{stack.current_id}/stop")
    s = stack.wait_state("ended", 30)
    assert not stack.our_encoders()
    conns = stack.fake_state()["connections"]
    stack.fake.post("/_control/ingest", params={"up": True})   # network comes back
    time.sleep(8)
    assert not stack.our_encoders(), "worker resumed after Stop"
    assert stack.fake_state()["connections"] == conns
    # Restarting the worker must not resume a stopped stream either.
    stack.stop("worker")
    stack.start_worker()
    time.sleep(5)
    assert not stack.our_encoders()
    assert stack.client.get(f"/api/sessions/{stack.current_id}").json()["session"]["state"] == "ended"
    fs = stack.fake_state()
    assert fs["insert_calls"] == 1
    assert fs["broadcasts"][0]["status"]["lifeCycleStatus"] == "complete"


def test_stop_when_youtube_api_unreachable_retries_only_end(stack, test_video):
    live_session(stack, test_video)
    stack.fake.post("/_control/api_down", params={"down": True})
    t0 = time.time()
    stack.client.post(f"/api/sessions/{stack.current_id}/stop")
    wait_for(lambda: not stack.our_encoders(), 3, what="media stopped")
    assert time.time() - t0 < 3
    s = stack.wait_state("end_pending", 20)
    assert s["state_label"] == "End confirmation pending" and s["stop_requested"]
    time.sleep(4)
    assert not stack.our_encoders()
    stack.fake.post("/_control/api_down", params={"down": False})
    stack.wait_state("ended", 30)
    fs = stack.fake_state()
    assert fs["broadcasts"][0]["status"]["lifeCycleStatus"] == "complete"
    assert fs["insert_calls"] == 1


def test_youtube_ending_event_requires_manual_restart(stack, test_video):
    s = live_session(stack, test_video)
    stack.fake.post(f"/_control/end/{s['broadcast_id']}")
    s = stack.wait_state("ended_by_youtube", 20)
    assert "Start a new stream manually" in s["error"]
    time.sleep(4)
    assert not stack.our_encoders()
    assert stack.fake_state()["insert_calls"] == 1
    assert stack.status()["session"] is None        # slot free for a manual restart


def test_silent_video_gets_silent_audio_track(stack, tmp_path):
    src = make_test_source(tmp_path / "silent.mp4", seconds=3, audio=False)
    s = live_session(stack, src)
    time.sleep(4)
    stop_and_confirm(stack)
    seg = Path(list(stack.fake_state()["segments"].values())[0][0])
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "csv",
                          str(seg)], capture_output=True, text=True).stdout
    assert "audio,aac" in out.replace("stream,", "").replace("aac,audio", "audio,aac") or "aac" in out, out


def test_scheduled_stream_creates_link_early_then_loops(stack, test_video):
    mid = stack.upload(test_video)
    start = time.time() + 61
    from datetime import datetime
    from zoneinfo import ZoneInfo
    local = datetime.fromtimestamp(start, ZoneInfo("Asia/Kolkata")).replace(tzinfo=None).isoformat(timespec="seconds")
    s = stack.start_session(mid, scheduled_start=local)   # naive time = Asia/Kolkata
    stack.current_id = s["id"]
    assert s["state"] == "scheduled" and abs(s["scheduled_start_utc"] - start) < 1.5
    s = stack.wait_state("live", 60)       # lead time (55 s in tests) starts it ~6 s from now
    assert s["watch_url"]
    stop_and_confirm(stack)


def test_stop_before_live_cancels_and_deletes_upcoming(stack, test_video):
    mid = stack.upload(test_video)
    stack.fake.post("/_control/ingest", params={"up": False})    # never reaches live
    s = stack.start_session(mid)
    stack.current_id = s["id"]
    wait_for(lambda: stack.session()["broadcast_id"], 20, what="broadcast")
    stack.client.post(f"/api/sessions/{s['id']}/stop")
    stack.wait_state("cancelled", 30)
    assert stack.fake_state()["broadcasts"] == []
