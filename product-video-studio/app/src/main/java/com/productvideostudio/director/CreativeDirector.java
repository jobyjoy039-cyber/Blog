package com.productvideostudio.director;

import com.productvideostudio.analysis.ProductInsights;
import com.productvideostudio.audio.MusicGenerator;
import com.productvideostudio.model.Enums.CameraAngle;
import com.productvideostudio.model.Enums.Effect;
import com.productvideostudio.model.Enums.Layout;
import com.productvideostudio.model.Enums.Look;
import com.productvideostudio.model.Enums.Mood;
import com.productvideostudio.model.Enums.Movement;
import com.productvideostudio.model.Enums.SceneType;
import com.productvideostudio.model.Enums.SfxType;
import com.productvideostudio.model.Enums.TextAnim;
import com.productvideostudio.model.Enums.TextRole;
import com.productvideostudio.model.Enums.TransitionType;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Project;
import com.productvideostudio.model.Storyboard;
import com.productvideostudio.model.Storyboard.Scene;
import com.productvideostudio.model.Storyboard.SfxCue;
import com.productvideostudio.model.Storyboard.TextItem;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;

/**
 * The "AI creative director": a deterministic, seedable rule system that turns product analysis
 * into a beat-synced storyboard. Every choice (scene order, image, angle, camera move, effect,
 * transition, copy, sound) is made here so the renderer only has to execute the plan.
 */
public final class CreativeDirector {
    private static final float SCREEN_ASPECT = 9f / 16f;

    private final Project project;
    private final ProductInsights insights;
    private final Random rnd;
    private final Storyboard board = new Storyboard();
    private CopyWriter copy;
    private final Set<Integer> usedImages = new HashSet<>();
    private boolean used360;
    private boolean usedFreeze;
    private boolean usedSpeedRamp;

    /** A scene the director would like to include, before fitting to the duration. */
    private static class Slot {
        final SceneType type;
        final int priority;
        int beats;
        String text;
        int image = -1;
        Slot(SceneType type, int priority, int beats) { this.type = type; this.priority = priority; this.beats = beats; }
    }

    private CreativeDirector(Project project, ProductInsights insights) {
        this.project = project;
        this.insights = insights;
        this.rnd = new Random(project.seed * 7919L + 17);
    }

    /**
     * @param detectedBpm   tempo of the user's music, or 0 to use the mood's tempo
     * @param detectedOffset first downbeat of the user's music in seconds
     */
    public static Storyboard direct(Project project, ProductInsights insights, int detectedBpm, float detectedOffset) {
        CreativeDirector d = new CreativeDirector(project, insights);
        return d.run(detectedBpm, detectedOffset);
    }

    private Storyboard run(int detectedBpm, float detectedOffset) {
        Mood mood = insights.mood;
        board.mood = mood;
        board.look = project.look != null ? project.look : mood.look;
        board.bpm = detectedBpm > 0 ? detectedBpm : mood.bpm;
        board.beatOffset = detectedBpm > 0 ? detectedOffset : 0f;
        board.totalSec = Math.max(6, project.durationSec);
        board.fps = project.fps == 60 ? 60 : 30;
        copy = CopyWriter.write(project, insights, rnd);
        styleTypography(mood);
        styleColors();

        List<Slot> slots = planSlots();
        fitToDuration(slots);
        buildScenes(slots);
        planSound();
        planVoice();

        board.caption = copy.caption(mood, insights.category);
        board.notes.addAll(insights.notes);
        board.notes.add("Look: " + board.look.label + " · Music: " + board.bpm + " BPM"
                + (detectedBpm > 0 ? " (detected from your track)" : " (" + mood.label.toLowerCase(Locale.ROOT) + " score)"));
        board.notes.add(board.scenes.size() + " scenes cut on the beat, " + String.format(Locale.ROOT, "%.0f", board.totalSec) + " s total");
        return board;
    }

    // ---------------------------------------------------------------------------------------
    // Style

    private void styleTypography(Mood mood) {
        switch (mood) {
            case LUXURY: board.font = "serif"; board.fontBold = false; board.letterSpacing = 0.16f; board.uppercaseHeadlines = true; break;
            case TECH: board.font = "sans-serif-medium"; board.fontBold = false; board.letterSpacing = 0.06f; board.uppercaseHeadlines = true; break;
            case NATURE: board.font = "serif"; board.fontBold = true; board.letterSpacing = 0.02f; break;
            case PLAYFUL: board.font = "sans-serif-black"; board.fontBold = true; board.letterSpacing = 0f; break;
            case FASHION: board.font = "sans-serif-condensed"; board.fontBold = true; board.letterSpacing = 0.12f; board.uppercaseHeadlines = true; break;
            case BEAUTY: board.font = "sans-serif-light"; board.fontBold = false; board.letterSpacing = 0.1f; board.uppercaseHeadlines = true; break;
            case FOOD: board.font = "sans-serif-black"; board.fontBold = true; board.letterSpacing = 0.01f; break;
            case SPORT: board.font = "sans-serif-condensed"; board.fontBold = true; board.letterSpacing = 0.04f; board.uppercaseHeadlines = true; break;
            default: board.font = "sans-serif"; board.fontBold = true; board.letterSpacing = 0.02f;
        }
    }

    private boolean darkLook() {
        switch (board.look) {
            case LUXURY: case DARK: case CINEMATIC: case PREMIUM: case MODERN: case COOL: return true;
            default: return false;
        }
    }

    private void styleColors() {
        int accent = insights.accent;
        board.accentColor = accent;
        board.primaryColor = project.brandColors.size() > 1 ? project.brandColors.get(1) : accent;
        if (darkLook()) {
            board.backdropInner = mix(0xFF262626, accent, 0.18f);
            board.backdropOuter = mix(0xFF050505, accent, 0.05f);
            board.textColor = 0xFFFFFFFF;
        } else {
            board.backdropInner = mix(0xFFFAF8F5, accent, 0.08f);
            board.backdropOuter = mix(0xFFD9D4CC, accent, 0.14f);
            board.textColor = 0xFF151515;
            // A very light product disappears on a light set; drop the set to a mid tone.
            float productLight = 0;
            int n = 0;
            for (ImageAnalysis a : project.analyses) {
                if (!a.palette.isEmpty()) { productLight += luminance(a.palette.get(0)); n++; }
            }
            if (n > 0 && productLight / n > 0.82f) {
                board.backdropInner = mix(0xFFBFBAB2, accent, 0.12f);
                board.backdropOuter = mix(0xFF8E8880, accent, 0.12f);
            }
        }
    }

    // ---------------------------------------------------------------------------------------
    // Scene plan

    private List<Slot> planSlots() {
        List<Slot> s = new ArrayList<>();
        int images = project.images.size();
        List<Integer> lifestyle = new ArrayList<>();
        for (int i = 0; i < images; i++) if (analysis(i).isLifestyle()) lifestyle.add(i);
        boolean fast = board.bpm >= 115;

        s.add(new Slot(SceneType.HERO_REVEAL, 100, 6));
        s.add(new Slot(SceneType.FRONT_VIEW, 75, 4));
        Slot f1 = new Slot(SceneType.FEATURE_HIGHLIGHT, 90, 4);
        f1.text = copy.features.size() > 0 ? copy.features.get(0) : null;
        s.add(f1);
        s.add(new Slot(SceneType.SIDE_VIEW, 60, 3));
        s.add(new Slot(SceneType.CLOSE_UP, 86, 3));
        if (copy.features.size() > 1) {
            Slot f2 = new Slot(SceneType.FEATURE_HIGHLIGHT, 70, 4);
            f2.text = copy.features.get(1);
            s.add(f2);
        }
        for (int k = 0; k < lifestyle.size(); k++) {
            Slot l = new Slot(SceneType.LIFESTYLE, k == 0 ? 85 : 50 - k, 5);
            l.image = lifestyle.get(k);
            s.add(l);
        }
        s.add(new Slot(SceneType.TOP_VIEW, hasAngle(CameraAngle.TOP_DOWN) ? 50 : 30, 4));
        s.add(new Slot(SceneType.MACRO_DETAIL, 55, 4));
        if (copy.features.size() > 2) {
            Slot f3 = new Slot(SceneType.FEATURE_HIGHLIGHT, 40, 4);
            f3.text = copy.features.get(2);
            s.add(f3);
        }
        // Give every remaining photo a chance to appear in longer videos.
        for (int i = 0; i < images; i++) {
            if (lifestyle.contains(i)) continue;
            SceneType t;
            switch (analysis(i).viewAngle) {
                case SIDE_PROFILE: t = SceneType.SIDE_VIEW; break;
                case TOP_DOWN: t = SceneType.TOP_VIEW; break;
                default: t = SceneType.FRONT_VIEW;
            }
            Slot extra = new Slot(t, 35 - i, 4);
            extra.image = i;
            s.add(s.size(), extra);
        }
        if (copy.features.size() > 3) {
            Slot f4 = new Slot(SceneType.FEATURE_HIGHLIGHT, 25, 4);
            f4.text = copy.features.get(3);
            s.add(f4);
        }
        s.add(new Slot(SceneType.BENEFITS, 65, 6));
        s.add(new Slot(SceneType.CALL_TO_ACTION, 100, 6));
        return s;
    }

    private void fitToDuration(List<Slot> slots) {
        float beat = board.beatSec();
        boolean fast = board.bpm >= 115;
        // Keep the first cut on the music's downbeat grid.
        int available = Math.max(8, Math.round((board.totalSec - board.beatOffset) / beat));

        // Pacing: social ads cut every ~1.6-2.2 s; text scenes need time to be read.
        for (Slot sl : slots) sl.beats = beatsFor(sl.type, beat, fast);

        // Hero and CTA always stay; fill the rest by priority, skipping what doesn't fit.
        List<Slot> byPriority = new ArrayList<>(slots);
        byPriority.sort((a, b) -> Integer.compare(b.priority, a.priority));
        Set<Slot> chosen = new HashSet<>();
        int used = 0;
        for (Slot sl : byPriority) {
            if (sl.priority >= 100 || used + sl.beats <= available) {
                chosen.add(sl);
                used += sl.beats;
            }
        }
        slots.retainAll(chosen);

        int minBeats = Math.max(2, (int) Math.ceil(1.1f / beat));
        // Too long even with only the essentials (very short videos): compress evenly.
        int guard = 0;
        while (sumBeats(slots) > available && guard++ < 100) {
            boolean changed = false;
            for (Slot sl : slots) {
                if (sumBeats(slots) <= available) break;
                if (sl.beats > minBeats) { sl.beats--; changed = true; }
            }
            if (!changed) break;
        }
        // Too short: lengthen scenes that benefit from time, then add extra angles.
        SceneType[] growOrder = {SceneType.CALL_TO_ACTION, SceneType.HERO_REVEAL, SceneType.LIFESTYLE, SceneType.BENEFITS,
                SceneType.FEATURE_HIGHLIGHT};
        guard = 0;
        while (sumBeats(slots) < available && guard++ < 200) {
            boolean grew = false;
            for (SceneType t : growOrder) {
                for (Slot sl : slots) {
                    if (sumBeats(slots) >= available) break;
                    int cap = beatsFor(sl.type, beat, fast) + (sl.type == SceneType.CALL_TO_ACTION ? 3 : 1);
                    if (sl.type == t && sl.beats < cap) { sl.beats++; grew = true; }
                }
            }
            if (!grew) {
                // Every scene is at a comfortable length: add another angle of the product.
                SceneType[] pool = {SceneType.CLOSE_UP, SceneType.SIDE_VIEW, SceneType.MACRO_DETAIL, SceneType.TOP_VIEW, SceneType.FRONT_VIEW};
                SceneType type = pool[rnd.nextInt(pool.length)];
                Slot extra = new Slot(type, 20, Math.min(beatsFor(type, beat, fast), Math.max(minBeats, available - sumBeats(slots))));
                slots.add(Math.max(1, slots.size() - 2), extra);
            }
        }
    }

    /** Nominal scene length in beats. */
    private static int beatsFor(SceneType type, float beat, boolean fast) {
        float sec;
        switch (type) {
            case HERO_REVEAL: sec = 2.8f; break;
            case CALL_TO_ACTION: sec = 3.4f; break;
            case BENEFITS: sec = 2.8f; break;
            case FEATURE_HIGHLIGHT: sec = fast ? 1.9f : 2.2f; break;
            case LIFESTYLE: sec = fast ? 2.0f : 2.3f; break;
            default: sec = fast ? 1.4f : 1.8f;
        }
        return Math.max(2, Math.round(sec / beat));
    }

    private static int sumBeats(List<Slot> slots) {
        int s = 0;
        for (Slot sl : slots) s += sl.beats;
        return s;
    }

    private void buildScenes(List<Slot> slots) {
        float beat = board.beatSec();
        float t = 0;
        int beatCount = 0;
        Movement previousMove = null;
        TransitionType previousTransition = null;
        int direction = rnd.nextBoolean() ? 1 : -1;
        for (int i = 0; i < slots.size(); i++) {
            Slot sl = slots.get(i);
            Scene sc = new Scene();
            sc.type = sl.type;
            sc.start = t;
            beatCount += sl.beats;
            float end = i == slots.size() - 1 ? board.totalSec : board.beatOffset + beatCount * beat;
            sc.duration = end - t;
            t = end;
            sc.direction = direction;
            direction = -direction;

            sc.image = sl.image >= 0 ? sl.image : chooseImage(sl.type);
            usedImages.add(sc.image);
            ImageAnalysis a = analysis(sc.image);
            chooseLayout(sc, a);
            chooseAngle(sc, a, i);
            sc.movement = chooseMovement(sc, a, previousMove);
            previousMove = sc.movement;
            chooseEffects(sc, a);
            sc.intensity = sc.type == SceneType.HERO_REVEAL || sc.type == SceneType.CALL_TO_ACTION ? 0.85f : 1f;
            if (board.bpm >= 118) sc.intensity *= 1.15f;
            if (i < slots.size() - 1) {
                sc.transition = chooseTransition(previousTransition, slots.get(i + 1).type);
                previousTransition = sc.transition;
            } else {
                sc.transition = TransitionType.CUT;
            }
            board.scenes.add(sc);
            sc.texts.addAll(textsFor(sc, sl));
        }
        // Clamp transition lengths to what the neighbouring scenes can absorb.
        for (int i = 0; i < board.scenes.size() - 1; i++) {
            Scene a = board.scenes.get(i), b = board.scenes.get(i + 1);
            if (transitionSeconds(a) > 0.45f * Math.min(a.duration, b.duration)) a.transition = TransitionType.CUT;
        }
        // Text leaves before the outgoing transition starts.
        for (int i = 0; i < board.scenes.size(); i++) {
            Scene sc = board.scenes.get(i);
            float tailOut = i == board.scenes.size() - 1 ? sc.duration + 1f : sc.duration - transitionSeconds(sc) / 2f - 0.08f;
            float headIn = i == 0 ? 0f : transitionSeconds(board.scenes.get(i - 1)) / 2f;
            for (TextItem ti : sc.texts) {
                ti.in = Math.max(ti.in, headIn + 0.05f);
                ti.out = Math.min(ti.out <= 0 ? tailOut : ti.out, tailOut);
                if (ti.out - ti.in < 0.6f) ti.in = Math.max(0f, ti.out - 0.6f);
            }
        }
    }

    public static float transitionSeconds(Scene sc) {
        return sc.transition.seconds;
    }

    private int chooseImage(SceneType type) {
        int n = project.images.size();
        int best = 0;
        float bestScore = -1e9f;
        for (int i = 0; i < n; i++) {
            ImageAnalysis a = analysis(i);
            float s = a.quality();
            switch (type) {
                case HERO_REVEAL:
                case CALL_TO_ACTION:
                case BENEFITS:
                    s += a.plainBackground ? 1.2f : 0f;
                    if (type != SceneType.HERO_REVEAL) s += i == heroImage() ? 0.3f : 0f;
                    break;
                case FRONT_VIEW:
                    s += a.viewAngle == CameraAngle.FRONT ? 0.8f : 0f;
                    s += a.plainBackground ? 0.4f : 0f;
                    break;
                case SIDE_VIEW:
                    s += a.viewAngle == CameraAngle.SIDE_PROFILE || a.viewAngle == CameraAngle.ANGLE_45 ? 1f : 0f;
                    break;
                case TOP_VIEW:
                    s += a.viewAngle == CameraAngle.TOP_DOWN ? 1f : 0f;
                    break;
                case CLOSE_UP:
                case MACRO_DETAIL:
                    s += a.sharpness * 1.2f + (a.width * (long) a.height > 4_000_000L ? 0.4f : 0f);
                    break;
                case LIFESTYLE:
                    s += a.isLifestyle() ? 2f : 0f;
                    break;
                default:
                    s += a.plainBackground ? 0.3f : 0f;
            }
            // Prefer variety: photos not yet shown win unless much worse.
            if (usedImages.contains(i) && type != SceneType.CALL_TO_ACTION) s -= 0.9f;
            s += rnd.nextFloat() * 0.15f;
            if (s > bestScore) { bestScore = s; best = i; }
        }
        return best;
    }

    private int heroImage() {
        return board.scenes.isEmpty() ? 0 : board.scenes.get(0).image;
    }

    private void chooseLayout(Scene sc, ImageAnalysis a) {
        float imgAspect = a.width / (float) Math.max(1, a.height);
        boolean portraitish = imgAspect < 0.8f;
        switch (sc.type) {
            case CLOSE_UP:
                sc.layout = Layout.FULL_BLEED;
                sc.crop = coverCrop(a, a.plainBackground ? a.focusX : a.focusX, a.focusY, a.plainBackground ? 0.62f : 0.6f);
                return;
            case MACRO_DETAIL:
                sc.layout = Layout.FULL_BLEED;
                sc.crop = coverCrop(a, a.detailX, a.detailY, 0.34f);
                return;
            case LIFESTYLE:
                float[] c = coverCrop(a, a.focusX, a.focusY, 1f);
                boolean fits = (a.subjectBox[2] - a.subjectBox[0]) <= (c[2] - c[0]) * 1.15f;
                sc.layout = fits || portraitish ? Layout.FULL_BLEED : Layout.CARD;
                sc.crop = sc.layout == Layout.FULL_BLEED ? c : new float[]{0, 0, 1, 1};
                return;
            default:
                if (a.plainBackground) {
                    sc.layout = Layout.STUDIO;
                    float pad = 0.05f;
                    sc.crop = new float[]{
                            Math.max(0, a.subjectBox[0] - pad), Math.max(0, a.subjectBox[1] - pad),
                            Math.min(1, a.subjectBox[2] + pad), Math.min(1, a.subjectBox[3] + pad)};
                } else if (portraitish && (sc.type == SceneType.HERO_REVEAL || sc.type == SceneType.FRONT_VIEW
                        || sc.type == SceneType.FEATURE_HIGHLIGHT)) {
                    sc.layout = Layout.FULL_BLEED;
                    sc.crop = coverCrop(a, a.focusX, a.focusY, 1f);
                } else {
                    sc.layout = Layout.CARD;
                    sc.crop = new float[]{0, 0, 1, 1};
                }
        }
        switch (sc.type) {
            case HERO_REVEAL: sc.productY = 0.42f; sc.productHeight = 0.54f; break;
            case FEATURE_HIGHLIGHT: sc.productY = 0.40f; sc.productHeight = 0.5f; break;
            case BENEFITS: sc.productY = 0.3f; sc.productHeight = 0.36f; break;
            case CALL_TO_ACTION: sc.productY = 0.36f; sc.productHeight = 0.42f; break;
            default: sc.productY = 0.45f; sc.productHeight = 0.6f;
        }
    }

    /** A crop with the screen's aspect ratio, {@code zoom} = 1 being the largest that fits. */
    static float[] coverCrop(ImageAnalysis a, float cx, float cy, float zoom) {
        float w = Math.max(1, a.width), h = Math.max(1, a.height);
        float maxW = Math.min(w, h * SCREEN_ASPECT);
        float cw = maxW * zoom, ch = cw / SCREEN_ASPECT;
        float x = cx * w - cw / 2, y = cy * h - ch / 2;
        x = Math.max(0, Math.min(w - cw, x));
        y = Math.max(0, Math.min(h - ch, y));
        return new float[]{x / w, y / h, (x + cw) / w, (y + ch) / h};
    }

    private void chooseAngle(Scene sc, ImageAnalysis a, int index) {
        switch (sc.type) {
            case HERO_REVEAL: sc.angle = sc.layout == Layout.STUDIO ? CameraAngle.LOW_ANGLE : CameraAngle.EYE_LEVEL; break;
            case FRONT_VIEW: sc.angle = CameraAngle.FRONT; break;
            case SIDE_VIEW: sc.angle = a.viewAngle == CameraAngle.SIDE_PROFILE ? CameraAngle.SIDE_PROFILE : CameraAngle.ANGLE_45; break;
            case TOP_VIEW: sc.angle = a.viewAngle == CameraAngle.TOP_DOWN ? CameraAngle.TOP_DOWN : CameraAngle.HIGH_ANGLE; break;
            case CLOSE_UP: sc.angle = rnd.nextBoolean() ? CameraAngle.EYE_LEVEL : CameraAngle.ANGLE_45; break;
            case MACRO_DETAIL: sc.angle = CameraAngle.MACRO; break;
            case LIFESTYLE: sc.angle = CameraAngle.EYE_LEVEL; break;
            case FEATURE_HIGHLIGHT: {
                CameraAngle[] opts = {CameraAngle.ISOMETRIC, CameraAngle.ANGLE_45, CameraAngle.HIGH_ANGLE, CameraAngle.LOW_ANGLE};
                sc.angle = sc.layout == Layout.STUDIO ? opts[(index + rnd.nextInt(2)) % opts.length] : CameraAngle.EYE_LEVEL;
                break;
            }
            default: sc.angle = CameraAngle.FRONT;
        }
    }

    private Movement chooseMovement(Scene sc, ImageAnalysis a, Movement previous) {
        Movement[] options;
        boolean studio = sc.layout == Layout.STUDIO;
        boolean full = sc.layout == Layout.FULL_BLEED;
        int d = sc.direction;
        switch (sc.type) {
            case HERO_REVEAL:
                options = studio ? new Movement[]{Movement.PUSH_IN, Movement.CRANE_UP, Movement.DOLLY_IN, d > 0 ? Movement.ORBIT_RIGHT : Movement.ORBIT_LEFT}
                        : new Movement[]{Movement.PUSH_IN, Movement.DOLLY_IN, Movement.SLOW_ZOOM_IN};
                break;
            case FRONT_VIEW:
                options = full ? new Movement[]{Movement.KEN_BURNS, Movement.SLOW_ZOOM_IN, Movement.GIMBAL}
                        : new Movement[]{Movement.SLOW_ZOOM_IN, Movement.FLOATING, Movement.GIMBAL, Movement.PARALLAX, Movement.DOLLY_IN};
                break;
            case SIDE_VIEW:
                options = new Movement[]{d > 0 ? Movement.ORBIT_RIGHT : Movement.ORBIT_LEFT, d > 0 ? Movement.TRUCK_RIGHT : Movement.TRUCK_LEFT,
                        d > 0 ? Movement.PAN_RIGHT : Movement.PAN_LEFT};
                break;
            case TOP_VIEW:
                options = new Movement[]{Movement.CRANE_DOWN, Movement.SLOW_ZOOM_OUT, Movement.GIMBAL};
                break;
            case CLOSE_UP:
                options = new Movement[]{Movement.PUSH_IN, Movement.SLOW_ZOOM_IN, d > 0 ? Movement.TRUCK_RIGHT : Movement.TRUCK_LEFT,
                        d > 0 ? Movement.TILT_UP : Movement.TILT_DOWN, Movement.HANDHELD};
                break;
            case MACRO_DETAIL:
                options = new Movement[]{Movement.RACK_FOCUS, Movement.SLOW_ZOOM_IN, d > 0 ? Movement.PAN_RIGHT : Movement.PAN_LEFT};
                break;
            case LIFESTYLE:
                options = new Movement[]{Movement.KEN_BURNS, Movement.HANDHELD, Movement.DOLLY_OUT, Movement.GIMBAL, d > 0 ? Movement.PAN_RIGHT : Movement.PAN_LEFT};
                break;
            case FEATURE_HIGHLIGHT: {
                List<Movement> list = new ArrayList<>();
                if (studio) {
                    list.add(Movement.FLOATING);
                    list.add(d > 0 ? Movement.ORBIT_RIGHT : Movement.ORBIT_LEFT);
                    list.add(Movement.PARALLAX);
                    list.add(Movement.CRANE_DOWN);
                    list.add(Movement.PULL_BACK);
                    boolean energetic = board.bpm >= 110;
                    if (!used360 && energetic && a.plainBackground) list.add(Movement.ROTATE_360);
                } else {
                    list.add(d > 0 ? Movement.TRUCK_RIGHT : Movement.TRUCK_LEFT);
                    list.add(Movement.GIMBAL);
                    list.add(Movement.TILT_UP);
                    list.add(Movement.PULL_BACK);
                }
                options = list.toArray(new Movement[0]);
                break;
            }
            case BENEFITS:
                options = new Movement[]{Movement.FLOATING, Movement.SLOW_ZOOM_OUT, Movement.GIMBAL};
                break;
            default:
                options = new Movement[]{Movement.PULL_BACK, Movement.SLOW_ZOOM_IN, Movement.FLOATING};
        }
        Movement m = options[rnd.nextInt(options.length)];
        if (m == previous && options.length > 1) m = options[(indexOf(options, m) + 1) % options.length];
        if (m == Movement.ROTATE_360) used360 = true;
        return m;
    }

    private void chooseEffects(Scene sc, ImageAnalysis a) {
        boolean studio = sc.layout == Layout.STUDIO;
        Mood mood = board.mood;
        boolean shinyMood = mood == Mood.LUXURY || mood == Mood.BEAUTY || mood == Mood.TECH || board.look == Look.PREMIUM;
        boolean energetic = board.bpm >= 115;
        if (studio || sc.layout == Layout.CARD) sc.effects.add(Effect.SHADOW);
        if (studio && (shinyMood || darkLook()) && sc.type != SceneType.TOP_VIEW) sc.effects.add(Effect.REFLECTION);
        if (studio && (darkLook() || mood == Mood.LUXURY)) sc.effects.add(Effect.GLOW);
        switch (sc.type) {
            case HERO_REVEAL:
                sc.effects.add(Effect.BLUR_REVEAL);
                sc.effects.add(Effect.LIGHT_SWEEP);
                break;
            case CLOSE_UP:
                if (insights.glossy || shinyMood) sc.effects.add(Effect.SHINE);
                break;
            case FEATURE_HIGHLIGHT:
                if (energetic && !usedSpeedRamp) { sc.effects.add(Effect.SPEED_RAMP); usedSpeedRamp = true; }
                else if (!usedFreeze && (mood == Mood.FASHION || mood == Mood.SPORT || mood == Mood.PLAYFUL)) {
                    sc.effects.add(Effect.FREEZE_FRAME);
                    usedFreeze = true;
                }
                break;
            case CALL_TO_ACTION:
                sc.effects.add(Effect.LIGHT_SWEEP);
                break;
            default:
        }
        if (energetic && (sc.movement == Movement.PUSH_IN || sc.movement == Movement.ROTATE_360
                || sc.movement == Movement.TRUCK_LEFT || sc.movement == Movement.TRUCK_RIGHT)) {
            sc.effects.add(Effect.MOTION_BLUR);
        }
    }

    private TransitionType chooseTransition(TransitionType previous, SceneType next) {
        TransitionType[] palette;
        switch (board.mood) {
            case LUXURY: palette = new TransitionType[]{TransitionType.DISSOLVE, TransitionType.LIGHT_LEAK, TransitionType.FADE, TransitionType.BLUR, TransitionType.ZOOM}; break;
            case TECH: palette = new TransitionType[]{TransitionType.PUSH, TransitionType.WHIP_PAN, TransitionType.ZOOM, TransitionType.FLASH, TransitionType.SWIPE, TransitionType.BLUR}; break;
            case NATURE: palette = new TransitionType[]{TransitionType.DISSOLVE, TransitionType.LIGHT_LEAK, TransitionType.MORPH, TransitionType.BLUR, TransitionType.FADE}; break;
            case PLAYFUL: palette = new TransitionType[]{TransitionType.SWIPE, TransitionType.ZOOM, TransitionType.PUSH, TransitionType.FLASH, TransitionType.WHIP_PAN}; break;
            case FASHION: palette = new TransitionType[]{TransitionType.FLASH, TransitionType.WHIP_PAN, TransitionType.FILM_BURN, TransitionType.PUSH, TransitionType.ZOOM}; break;
            case BEAUTY: palette = new TransitionType[]{TransitionType.DISSOLVE, TransitionType.LIGHT_LEAK, TransitionType.BLUR, TransitionType.MORPH, TransitionType.ZOOM}; break;
            case FOOD: palette = new TransitionType[]{TransitionType.WHIP_PAN, TransitionType.LIGHT_LEAK, TransitionType.ZOOM, TransitionType.SWIPE, TransitionType.DISSOLVE}; break;
            case SPORT: palette = new TransitionType[]{TransitionType.WHIP_PAN, TransitionType.FLASH, TransitionType.ZOOM, TransitionType.PUSH, TransitionType.FILM_BURN}; break;
            default: palette = new TransitionType[]{TransitionType.DISSOLVE, TransitionType.PUSH, TransitionType.BLUR, TransitionType.FADE, TransitionType.SWIPE};
        }
        if (next == SceneType.CALL_TO_ACTION) {
            TransitionType[] finale = board.bpm >= 110
                    ? new TransitionType[]{TransitionType.ZOOM, TransitionType.FLASH}
                    : new TransitionType[]{TransitionType.LIGHT_LEAK, TransitionType.ZOOM, TransitionType.DISSOLVE};
            TransitionType t = finale[rnd.nextInt(finale.length)];
            return t == previous ? finale[(indexOf(finale, t) + 1) % finale.length] : t;
        }
        TransitionType t = palette[rnd.nextInt(palette.length)];
        if (t == previous) t = palette[(indexOf(palette, t) + 1) % palette.length];
        return t;
    }

    // ---------------------------------------------------------------------------------------
    // Copy on screen

    private List<TextItem> textsFor(Scene sc, Slot sl) {
        List<TextItem> out = new ArrayList<>();
        boolean full = sc.layout == Layout.FULL_BLEED;
        int textColor = full ? 0xFFFFFFFF : board.textColor;
        TextAnim headlineAnim = headlineAnim();
        float beat = board.beatSec();
        switch (sc.type) {
            case HERO_REVEAL: {
                float reveal = beat * MusicGenerator.INTRO_BEATS;
                TextItem name = text(TextRole.PRODUCT_NAME, headline(copy.headline), headlineAnim, reveal, 0.5f, 0.775f, 96, textColor);
                name.bold = board.fontBold;
                out.add(name);
                out.add(text(TextRole.TAGLINE, copy.tagline, TextAnim.FADE, reveal + 0.45f, 0.5f, 0.885f, 44, withAlpha(textColor, 0.85f)));
                if (!copy.brand.isEmpty() && !copy.headline.toLowerCase(Locale.ROOT).contains(copy.brand.toLowerCase(Locale.ROOT))) {
                    out.add(text(TextRole.BRAND, copy.brand.toUpperCase(Locale.ROOT), TextAnim.FADE, reveal * 0.6f, 0.5f, 0.1f, 36, withAlpha(textColor, 0.8f)));
                }
                break;
            }
            case FEATURE_HIGHLIGHT: {
                String f = sl.text != null ? sl.text : copy.tagline;
                out.add(text(TextRole.FEATURE, f, headlineAnim == TextAnim.BLUR_REVEAL ? TextAnim.BLUR_REVEAL : TextAnim.SLIDE_UP,
                        0.2f, 0.5f, full ? 0.8f : 0.8f, 84, textColor));
                break;
            }
            case LIFESTYLE:
                out.add(text(TextRole.TAGLINE, copy.benefits.size() > 1 ? copy.benefits.get(1) : copy.tagline,
                        TextAnim.SLIDE_UP, 0.35f, 0.5f, 0.82f, 72, 0xFFFFFFFF));
                break;
            case CLOSE_UP:
            case MACRO_DETAIL: {
                String m = null;
                for (String mat : insights.materials) {
                    if (!"Glossy finish".equals(mat)) { m = mat; break; }
                }
                if (sc.type == SceneType.MACRO_DETAIL && m != null) {
                    out.add(text(TextRole.FEATURE, m, TextAnim.FADE, 0.4f, 0.5f, 0.86f, 52, 0xFFFFFFFF));
                }
                break;
            }
            case BENEFITS: {
                float y = 0.6f;
                int k = 0;
                for (String b : copy.benefits) {
                    if (k >= 3) break;
                    TextItem ti = text(TextRole.BENEFIT, "✓  " + b, TextAnim.SLIDE_LEFT, 0.25f + k * Math.max(0.3f, beat * 0.5f), 0.5f, y, 58, textColor);
                    out.add(ti);
                    y += 0.085f;
                    k++;
                }
                break;
            }
            case CALL_TO_ACTION: {
                out.add(text(TextRole.PRODUCT_NAME, headline(copy.headline), headlineAnim, 0.2f, 0.5f, 0.635f, 80, textColor));
                float y = 0.73f;
                if (!copy.price.isEmpty()) {
                    out.add(text(TextRole.PRICE, copy.price, TextAnim.SCALE, 0.5f, 0.5f, y, 64, textColor));
                    y += 0.07f;
                }
                if (!copy.discount.isEmpty()) {
                    TextItem d = text(TextRole.DISCOUNT, copy.discount, TextAnim.BOUNCE, 0.7f, 0.78f, project.logo != null ? 0.2f : 0.14f, 58, contrastOn(board.accentColor));
                    d.background = board.accentColor;
                    out.add(d);
                }
                TextItem cta = text(TextRole.CTA, copy.cta.toUpperCase(Locale.ROOT), TextAnim.BOUNCE, 0.8f, 0.5f, Math.max(y + 0.03f, 0.8f), 60, contrastOn(board.accentColor));
                cta.background = board.accentColor;
                cta.shine = true;
                out.add(cta);
                if (!copy.website.isEmpty()) {
                    out.add(text(TextRole.WEBSITE, copy.website, TextAnim.FADE, 1.1f, 0.5f, Math.max(y + 0.03f, 0.8f) + 0.075f, 40, withAlpha(textColor, 0.85f)));
                }
                break;
            }
            default:
        }
        return out;
    }

    private TextAnim headlineAnim() {
        switch (board.mood) {
            case LUXURY: case BEAUTY: return TextAnim.BLUR_REVEAL;
            case TECH: return TextAnim.TYPE_ON;
            case PLAYFUL: case FOOD: return TextAnim.BOUNCE;
            case FASHION: case SPORT: return TextAnim.SLIDE_UP;
            default: return TextAnim.FADE;
        }
    }

    private String headline(String s) {
        return board.uppercaseHeadlines ? s.toUpperCase(Locale.ROOT) : s;
    }

    private TextItem text(TextRole role, String s, TextAnim anim, float in, float x, float y, float size, int color) {
        TextItem t = new TextItem();
        t.role = role;
        t.text = s;
        t.anim = anim;
        t.in = in;
        t.out = 0;
        t.x = x;
        t.y = y;
        t.size = size;
        t.color = color;
        t.bold = board.fontBold || role == TextRole.CTA || role == TextRole.DISCOUNT;
        return t;
    }

    // ---------------------------------------------------------------------------------------
    // Sound design

    private void planSound() {
        Mood mood = board.mood;
        List<SfxCue> sfx = board.sfx;
        Scene hero = board.scenes.get(0);
        float drop = board.beatSec() * MusicGenerator.INTRO_BEATS;
        sfx.add(new SfxCue(SfxType.RISER, 0f, 0.35f, 0f, Math.max(0.6f, drop)));
        sfx.add(new SfxCue(SfxType.IMPACT, drop, 0.55f, 0f, 1.2f));
        if (mood == Mood.LUXURY || mood == Mood.BEAUTY) sfx.add(new SfxCue(SfxType.SHIMMER, drop + 0.1f, 0.4f, 0.2f, 2f));
        if (mood == Mood.TECH) sfx.add(new SfxCue(SfxType.TECH_BLIP, drop + 0.05f, 0.35f, 0f, 0.3f));
        if (mood == Mood.NATURE) sfx.add(new SfxCue(SfxType.NATURE_AMBIENCE, 0f, 0.28f, 0f, board.totalSec));

        for (int i = 0; i < board.scenes.size() - 1; i++) {
            Scene sc = board.scenes.get(i);
            float cut = board.scenes.get(i + 1).start;
            float pan = sc.direction * 0.4f;
            switch (sc.transition) {
                case WHIP_PAN: sfx.add(new SfxCue(SfxType.WHOOSH, cut - 0.22f, 0.55f, pan, 0.45f)); break;
                case PUSH: case SWIPE: case ZOOM: sfx.add(new SfxCue(SfxType.WHOOSH, cut - 0.25f, 0.38f, pan, 0.5f)); break;
                case FLASH: sfx.add(new SfxCue(SfxType.CAMERA_SHUTTER, cut - 0.02f, 0.4f, 0f, 0.25f)); break;
                case FILM_BURN: sfx.add(new SfxCue(SfxType.SWOOSH_SOFT, cut - 0.4f, 0.4f, pan, 0.9f)); break;
                case DISSOLVE: case BLUR: case MORPH: case LIGHT_LEAK: case FADE:
                    sfx.add(new SfxCue(SfxType.SWOOSH_SOFT, cut - 0.35f, 0.22f, pan, 0.8f)); break;
                default:
            }
            if (sc.has(Effect.FREEZE_FRAME)) sfx.add(new SfxCue(SfxType.CAMERA_SHUTTER, sc.start + sc.duration * 0.45f, 0.45f, 0f, 0.25f));
        }
        SfxType textSfx = mood == Mood.PLAYFUL || mood == Mood.FOOD ? SfxType.POP : mood == Mood.TECH ? SfxType.TECH_BLIP : SfxType.CLICK;
        for (Scene sc : board.scenes) {
            if (sc == hero) continue;
            for (TextItem ti : sc.texts) {
                if (ti.role == TextRole.FEATURE || ti.role == TextRole.BENEFIT || ti.role == TextRole.PRICE) {
                    sfx.add(new SfxCue(textSfx, sc.start + ti.in, 0.22f, 0f, 0.2f));
                } else if (ti.role == TextRole.CTA) {
                    sfx.add(new SfxCue(SfxType.POP, sc.start + ti.in + 0.05f, 0.4f, 0f, 0.25f));
                    if (mood == Mood.LUXURY || mood == Mood.BEAUTY) sfx.add(new SfxCue(SfxType.SHIMMER, sc.start + ti.in + 0.3f, 0.3f, 0f, 1.6f));
                } else if (ti.role == TextRole.DISCOUNT) {
                    sfx.add(new SfxCue(SfxType.POP, sc.start + ti.in, 0.35f, 0.3f, 0.2f));
                }
            }
        }
    }

    private void planVoice() {
        if (Project.VOICE_OFF.equals(project.voiceMode)) return;
        if (Project.VOICE_FILE.equals(project.voiceMode)) {
            board.voice.add(new Storyboard.VoiceLine(0.3f, ""));
            return;
        }
        List<String> lines = copy.voiceScript(project.voiceScript, board.totalSec);
        if (lines.isEmpty()) return;
        // Anchor lines to scenes: intro on the hero, features on feature scenes, CTA on the finale.
        List<Float> anchors = new ArrayList<>();
        anchors.add(0.35f);
        for (Scene sc : board.scenes) {
            if (sc.type == SceneType.FEATURE_HIGHLIGHT || sc.type == SceneType.LIFESTYLE || sc.type == SceneType.BENEFITS) {
                anchors.add(sc.start + 0.15f);
            }
        }
        Scene last = board.scenes.get(board.scenes.size() - 1);
        for (int i = 0; i < lines.size(); i++) {
            float at;
            if (i == lines.size() - 1) at = last.start + 0.2f;
            else if (i < anchors.size()) at = anchors.get(i);
            else at = anchors.get(anchors.size() - 1) + (i - anchors.size() + 1) * 1.8f;
            board.voice.add(new Storyboard.VoiceLine(at, lines.get(i)));
        }
    }

    // ---------------------------------------------------------------------------------------

    private ImageAnalysis analysis(int i) {
        ImageAnalysis found = project.analysisFor(project.images.get(i));
        if (found != null) return found;
        ImageAnalysis a = new ImageAnalysis();
        a.file = project.images.get(i);
        a.width = 1080;
        a.height = 1080;
        return a;
    }

    private boolean hasAngle(CameraAngle angle) {
        for (int i = 0; i < project.images.size(); i++) if (analysis(i).viewAngle == angle) return true;
        return false;
    }

    private static <T> int indexOf(T[] arr, T v) {
        for (int i = 0; i < arr.length; i++) if (arr[i] == v) return i;
        return 0;
    }

    static int mix(int a, int b, float t) {
        int ar = (a >> 16) & 0xFF, ag = (a >> 8) & 0xFF, ab = a & 0xFF;
        int br = (b >> 16) & 0xFF, bg = (b >> 8) & 0xFF, bb = b & 0xFF;
        return 0xFF000000 | (Math.round(ar + (br - ar) * t) << 16) | (Math.round(ag + (bg - ag) * t) << 8) | Math.round(ab + (bb - ab) * t);
    }

    static float luminance(int c) {
        return (0.2126f * ((c >> 16) & 0xFF) + 0.7152f * ((c >> 8) & 0xFF) + 0.0722f * (c & 0xFF)) / 255f;
    }

    static int contrastOn(int bg) {
        return luminance(bg) > 0.6f ? 0xFF111111 : 0xFFFFFFFF;
    }

    static int withAlpha(int c, float a) {
        return (Math.round(a * 255) << 24) | (c & 0xFFFFFF);
    }
}
