# Video tools

Standalone renderers built on the backend's audio and graphics code. Run them with the backend's environment:
`../backend/.venv/bin/python <tool> ...`

| Tool | What it makes |
|---|---|
| `motion_poster.py POSTER OUT.mp4 [16x9\|9x16]` | A 22s cinematic motion poster from one still: camera moves across the artwork, drifting fog, light flicker, grain, flash cuts, and a synthesized suspense score (drone, heartbeat, impacts, riser) mastered to -14 LUFS. Shot framing is set in `SHOTS_WIDE` / `SHOTS_TALL` for the poster you use. |
| `restoration_video.py PHOTO OUT.mp4 [CLIPS_DIR]` | A 90s "scrap to showroom" restoration video. Scenes 1-2 are built from the photo (push-in with dust and light rays, macro close-ups with rack focus and handheld shake; licence plates are blurred). Scenes 3-9 show storyboard cards with the AI prompt for each shot until you drop generated clips named `scene3.mp4` ... `scene9.mp4` into `CLIPS_DIR`. Then they are graded teal and orange and cut to the same soundtrack, including the synthesized engine start. |

Only use artwork and photos you have the rights to. Movie and TV key art belongs to its studio, so a motion poster made from it is fine for personal or fan use but not for paid ads.
