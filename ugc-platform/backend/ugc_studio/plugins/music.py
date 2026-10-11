"""Music beds. The built-in composer writes original, royalty-free tracks."""
from __future__ import annotations

from pathlib import Path

from . import audio_studio
from .base import MusicPlugin


class ProceduralMusic(MusicPlugin):
    name = "procedural"
    priority = 50
    license = "Original output of this project (royalty-free)"
    description = "Composes an original bed per ad: upbeat, energetic, chill or luxury."

    def compose(self, style: str, duration: float, out_path: Path, seed: int) -> Path:
        return audio_studio.compose_music(style, duration, out_path, seed)
