"""Runs the loop acceptance test with the FFmpeg built for the Android APK (arm64), executed through
qemu-aarch64 on a PC. Opt-in: set ANDROID_FFMPEG_DIR to the folder containing the static test build
(android/ffmpeg/build-ffmpeg.sh static), e.g.  ANDROID_FFMPEG_DIR=~/ffout/static/bin pytest -k android
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from av_analysis import analyse
from conftest import wait_for

ARM_DIR = os.environ.get("ANDROID_FFMPEG_DIR")
QEMU = shutil.which("qemu-aarch64-static") or shutil.which("qemu-aarch64")
pytestmark = pytest.mark.skipif(not (ARM_DIR and QEMU), reason="set ANDROID_FFMPEG_DIR and install qemu-user")


def wrapper(tmp: Path, name: str) -> Path:
    w = tmp / name
    w.write_text(f'#!/bin/sh\nexec {QEMU} {Path(ARM_DIR) / name} "$@"\n')
    w.chmod(0o755)
    return w


def test_android_arm64_ffmpeg_loops_seamlessly(stack_factory, test_video, tmp_path):
    env = {"REPLAY_STUDIO_ENCODER_MODE": "copy",
           "REPLAY_STUDIO_ENCODER_FFMPEG": str(wrapper(tmp_path, "ffmpeg")),
           "REPLAY_STUDIO_ENCODER_FFPROBE": str(wrapper(tmp_path, "ffprobe"))}
    stack = stack_factory(extra_env=env)
    mid = stack.upload(test_video)
    m = stack.client.get(f"/api/media/{mid}").json()
    assert m["status"] == "ok", m                       # probed + prepared by the arm64 build
    assert m["probe"]["loop_ready"]["mode"] == "copy"
    s = stack.start_session(mid)
    stack.current_id = s["id"]
    stack.wait_state("live", 90)
    wait_for(lambda: (x := stack.session()) and x["loops_completed"] >= 3 and x["played_total"] > 14, 90,
             what="3 loops")
    pid = stack.our_encoders()[0]
    cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
    assert str(Path(ARM_DIR) / "ffmpeg").encode() in cmd     # really the Android binary
    time.sleep(1)
    stack.client.post(f"/api/sessions/{s['id']}/stop")
    stack.wait_state("ended", 40)
    fs = stack.fake_state()
    seg = Path(list(fs["segments"].values())[0][0])
    r = analyse(seg, 4.0)
    print(r)
    assert len(r["flash_onsets"]) >= 4
    assert all(abs(g - 4.0) < 0.02 for g in r["loop_spacing"]), r["loop_spacing"]
    offs = r["av_offsets"]
    assert all(o is not None and abs(o) < 0.035 for o in offs) and max(offs) - min(offs) < 0.01, offs
    assert r["max_video_gap"] < 0.04 and r["max_audio_gap"] < 0.03 and not r["black"] and not r["silence"], r
