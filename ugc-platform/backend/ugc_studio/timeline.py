"""Shared ad timeline: when each scene starts and when its voice line plays.

Used by the orchestrator (to size the music bed) and the studio renderer (to
cut picture, captions and SFX), so audio and video always agree.
"""
from __future__ import annotations

from dataclasses import dataclass

LEAD_IN = 0.12     # picture lands a beat before the voice
GAP = 0.32         # breath between lines
END_HOLD = 1.1     # let the CTA card sit
TRANSITION = 0.4   # transition length, centred on each scene boundary


@dataclass(frozen=True)
class Timeline:
    starts: list[float]       # scene start times
    voice_at: list[float]     # voice clip start times
    durations: list[float]    # scene lengths
    total: float

    def scene_at(self, t: float) -> int:
        i = 0
        while i + 1 < len(self.starts) and t >= self.starts[i + 1]:
            i += 1
        return i


def plan(voice_durations: list[float]) -> Timeline:
    starts, voice_at, durs = [], [], []
    t = 0.0
    for i, d in enumerate(voice_durations):
        dur = LEAD_IN + d + GAP + (END_HOLD if i == len(voice_durations) - 1 else 0.0)
        starts.append(round(t, 3))
        voice_at.append(round(t + LEAD_IN, 3))
        durs.append(round(dur, 3))
        t += dur
    return Timeline(starts, voice_at, durs, round(t, 3))
