---
title: "Learning Video Editing: A DaVinci Resolve Post-Production Guide"
date: 2026-08-20
tags: [video-editing, davinci-resolve, color-grading, audio-mixing]
---

# Learning Video Editing: A DaVinci Resolve Post-Production Guide

A structured guide to post-production in DaVinci Resolve, covering editing fundamentals, color grading, audio mixing, and audio sync — built around a curated set of video tutorials.

## Section 1: Fundamentals & Video Editing Basics

### Program Overview & System Setup

- **System requirements**: DaVinci Resolve is hardware-intensive. A dedicated GPU (a mid-range gaming PC or a Mac M2 or later) is recommended for smooth operation.
- **Free vs. Studio version**: The free version covers roughly 90% of editing, color grading, and audio needs. DaVinci Resolve Studio adds advanced tools like neural-engine AI, noise reduction, and advanced visual effects.
- **Page layout**: Resolve houses multiple post-production tools under one roof, navigated via tabs at the bottom:
  - **Cut** — fast-paced trimming and quick rough cuts
  - **Edit** — the core timeline-based editing workspace
  - **Fusion** — node-based visual effects (VFX) and motion graphics
  - **Color** — professional color grading and correction
  - **Fairlight** — multitrack audio mixing, sound design, and mastering
  - **Deliver** — rendering and exporting the final video

### Media Management & Organization

- **Media Pool & bins**: organize raw footage, audio, and graphics into bins.
- **Smart Bins & keywords**: tag clips with keywords to auto-generate dynamic Smart Bins for quick sorting (e.g., separating close-ups from over-the-shoulder shots).

### Assembly & Trimming Techniques

- **Source & Timeline viewer**: preview raw clips on the left (Source Viewer) and timeline playback on the right (Timeline Viewer).
- **In/Out points (I / O)**: mark the start (I) and end (O) of a source clip before dropping it into the timeline, trimming unneeded footage up front.
- **Basic cut & trimming**: use blade tools and selection handles to trim excess from clip ends.
- **Multi-shot story construction**: combine A-roll (primary narrative) with B-roll (supplemental coverage) to maintain rhythm and hide cuts.

## Section 2: Color Grading & Color Science

### Understanding Color Management & Color Spaces

- **Why shoot in Log?** Raw/Log camera footage captures maximum dynamic range and color data, which is why it looks flat and desaturated before grading.
- **Color space vs. gamut**:
  - *Color space* defines the accessible brightness levels and color boundaries (e.g., Rec.709 vs. DaVinci Wide Gamut).
  - *Gamut* is the exact range of colors a device can actually reproduce.
- **Color management approaches**:
  - **DaVinci YRGB (display-referred)** — manual control over input and output space via tools like the Color Space Transform (CST) plugin.
  - **DaVinci YRGB Color Managed (scene-referred)** — an automated system that matches clips to a unified working space based on input selection.
- **Standard workspaces**:
  - Working space: DaVinci Wide Gamut / Intermediate.
  - Output space: Rec.709 with Gamma 2.2 (web/monitors) or Gamma 2.4 (broadcast/TV). On macOS, Rec.709-A corrects the Apple gamma shift.

### Node Graph Foundations

Unlike layer-based editors, Resolve uses a non-destructive, left-to-right node network:

- **In-N-Out nodes**: place CST conversions at the start and end of the chain, doing all creative grading between them in wide color space.
- **Serial nodes**: process sequentially (left → right); each node builds on the previous step.
- **Parallel nodes**: run independently on separate branches and blend into a single output — useful for isolating lighting or secondary tweaks without disturbing the primary grade.

### Color Correction vs. Creative Grading Workflow

1. **Exposure & contrast** — adjust global brightness with HDR tools or the Lift/Gamma/Gain wheels.
2. **White balance & color correction** — balance neutrals using the Offset wheel or Linear gamma mode with Gain adjustments.
3. **Saturation** — use HSV space (disabling channels 1 and 3) for smooth, natural saturation.
4. **Secondary corrections & isolation**:
   - **Power Windows** — vector shapes to brighten or darken targeted areas (e.g., isolating a subject).
   - **Qualifiers & HSL curves** — select specific hues/saturation ranges (e.g., separating skin tones from background).
   - **Magic Mask** — AI tool that isolates and tracks a subject automatically.
5. **Creative look & finishing** — split-toning, film-look simulation, LUTs, grain, and sharpening, applied last.

### Color Evaluation Tools (Scopes)

- **Waveform** — pixel luminosity from pure black (0) to pure white (100), plotted horizontally across the image.
- **Vector scope** — hue and saturation on a circular wheel, with a skin-tone reference line.
- **Parade scope** — splits Red, Green, and Blue into separate graphs for white balancing.

## Section 3: Audio Mixing & Sound Design

### Thinking About Audio in Editing

- **Decouple video and audio**: treat them as separate storytelling threads rather than locked blocks.
- **Reading music waveforms**:
  - *Intros* build entrance momentum into a scene.
  - *Outros* bring energy or a transition to a clean resolution.
  - *Variations/shifts* — level changes (quiet-to-loud or the reverse) — are ideal transition points.

### Strategic Music Edits

- **Transition outro drop**: place a music outro at the start of a new scene to smoothly land the viewer from one scene into the next.
- **Variation scene shifts**: align a musical drop or shift precisely with a scene cut to convey an emotional shift.
- **Hard cut hit**: align a strong song intro beat with the very first frame of a scene transition for high-energy momentum.

## Section 4: Audio Synchronization

### Manual Audio Syncing

1. Place camera video/audio alongside externally recorded high-quality microphone audio.
2. Align peak audio markers (slates, claps, or snaps) manually by zooming into the waveform timeline.
3. Mute or delete the camera's mic track and link the clean external audio clip (Ctrl/Cmd + L).

### Automatic Waveform Syncing (in DaVinci Resolve)

1. In the Media Pool, select both the video clip and the external audio file.
2. Right-click and choose **Auto Sync Audio Based on Waveform**.
3. Resolve matches audio peaks automatically and replaces/links the camera's internal audio with the clean external track.

## Recommended Learning Roadmap

- **Week 1 — Fundamentals**: master navigating the Edit page, setting In/Out points, organizing bins, and cutting a basic project.
- **Week 2 — Audio & sync**: practice auto-syncing double-system audio and editing music tracks around waveform shifts.
- **Week 3 — Color correction**: set up DaVinci YRGB CST nodes, balance exposure/contrast, and fix white balance.
- **Week 4 — Advanced color & delivery**: practice secondary masks, Power Windows, creative LUT placement, and exporting on the Deliver page.

## Video Resources

### Fundamentals

- [Video 1](https://youtu.be/MCDVcQIA3UM)
- [Video 2](https://youtu.be/iDVRnKXCk34)
- [Video 3](https://youtu.be/tAt6nwbjrfc)
- [Video 4](https://youtu.be/sNjyOSADDxE)
- [Video 5](https://youtu.be/A3ESexsIHuk)
- [Video 6](https://youtu.be/YtULPT1aBWM)

### Color Grading

- [Video 1](https://youtu.be/hvwQIQcXFbI)
- [Video 2](https://youtu.be/IBwLq8vtfJ4)
- [Video 3](https://youtu.be/8LmQA9Nl0IE)
- [Video 4](https://youtu.be/r2nD_knsNrc)

### Audio Mixing

- [Video 1](https://youtu.be/-B13nDMxC1k)
- [Video 2](https://youtu.be/x3vxD_Dgt5M)
- [Video 3](https://youtu.be/LFHtCTjwKjc)
- [Video 4](https://youtu.be/jNeu1DRxe9E)
- [Video 5](https://youtu.be/4vdxrEgeP4E)

### Audio Sync

- [Video 1](https://youtu.be/e-KVUPz8EUQ)
- [Video 2](https://youtu.be/AK9TQegGzpg)
- [Video 3](https://youtu.be/oqaVL9mbyT0)
