package com.productvideostudio.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** The director's complete plan for one video: scenes, text, sound and style. */
public class Storyboard {
    public Enums.Mood mood = Enums.Mood.HOME;
    public Enums.Look look = Enums.Look.MODERN;
    public int bpm = 100;
    /** Time of the first downbeat in the music, in seconds. */
    public float beatOffset = 0f;
    public float totalSec = 15f;
    public int fps = 30;

    /** Font family name for {@link android.graphics.Typeface#create(String, int)}. */
    public String font = "sans-serif";
    public boolean fontBold = true;
    public float letterSpacing = 0f;
    public boolean uppercaseHeadlines = false;

    public int primaryColor = 0xFF111111;
    public int accentColor = 0xFFFFC107;
    public int textColor = 0xFFFFFFFF;
    /** Studio backdrop: center and edge of the radial gradient. */
    public int backdropInner = 0xFF2A2A2A;
    public int backdropOuter = 0xFF050505;

    public List<Scene> scenes = new ArrayList<>();
    public List<SfxCue> sfx = new ArrayList<>();
    public List<VoiceLine> voice = new ArrayList<>();
    /** Plain-language notes on why the director chose what it chose. */
    public List<String> notes = new ArrayList<>();
    public String caption = "";

    public static class Scene {
        public Enums.SceneType type = Enums.SceneType.FRONT_VIEW;
        public int image;
        public Enums.Layout layout = Enums.Layout.CARD;
        public Enums.CameraAngle angle = Enums.CameraAngle.EYE_LEVEL;
        public Enums.Movement movement = Enums.Movement.SLOW_ZOOM_IN;
        public List<Enums.Effect> effects = new ArrayList<>();
        /** Transition into the next scene. */
        public Enums.TransitionType transition = Enums.TransitionType.DISSOLVE;
        /** Cut point where this scene begins (the middle of the incoming transition). */
        public float start;
        public float duration;
        /** Region of the source image to show (l, t, r, b), normalized. */
        public float[] crop = {0f, 0f, 1f, 1f};
        /** Where the product sits on screen for STUDIO/CARD layouts: center y and max height (fractions of screen). */
        public float productY = 0.44f;
        public float productHeight = 0.52f;
        /** Movement strength multiplier (beat energy, scene role). */
        public float intensity = 1f;
        /** Sign for directional choices so consecutive scenes alternate. */
        public int direction = 1;
        public List<TextItem> texts = new ArrayList<>();

        public boolean has(Enums.Effect e) { return effects.contains(e); }
        public float end() { return start + duration; }

        JSONObject toJson() throws JSONException {
            JSONObject o = new JSONObject();
            o.put("type", type.name());
            o.put("image", image);
            o.put("layout", layout.name());
            o.put("angle", angle.name());
            o.put("movement", movement.name());
            JSONArray fx = new JSONArray();
            for (Enums.Effect e : effects) fx.put(e.name());
            o.put("effects", fx);
            o.put("transition", transition.name());
            o.put("start", start);
            o.put("duration", duration);
            JSONArray c = new JSONArray();
            for (float f : crop) c.put((double) f);
            o.put("crop", c);
            o.put("productY", productY);
            o.put("productHeight", productHeight);
            o.put("intensity", intensity);
            o.put("direction", direction);
            JSONArray t = new JSONArray();
            for (TextItem ti : texts) t.put(ti.toJson());
            o.put("texts", t);
            return o;
        }

        static Scene fromJson(JSONObject o) throws JSONException {
            Scene s = new Scene();
            s.type = Enums.parse(Enums.SceneType.class, o.optString("type"), Enums.SceneType.FRONT_VIEW);
            s.image = o.optInt("image");
            s.layout = Enums.parse(Enums.Layout.class, o.optString("layout"), Enums.Layout.CARD);
            s.angle = Enums.parse(Enums.CameraAngle.class, o.optString("angle"), Enums.CameraAngle.EYE_LEVEL);
            s.movement = Enums.parse(Enums.Movement.class, o.optString("movement"), Enums.Movement.SLOW_ZOOM_IN);
            JSONArray fx = o.optJSONArray("effects");
            if (fx != null) {
                for (int i = 0; i < fx.length(); i++) {
                    Enums.Effect e = Enums.parse(Enums.Effect.class, fx.getString(i), null);
                    if (e != null) s.effects.add(e);
                }
            }
            s.transition = Enums.parse(Enums.TransitionType.class, o.optString("transition"), Enums.TransitionType.DISSOLVE);
            s.start = (float) o.optDouble("start");
            s.duration = (float) o.optDouble("duration", 2);
            JSONArray c = o.optJSONArray("crop");
            if (c != null && c.length() == 4) for (int i = 0; i < 4; i++) s.crop[i] = (float) c.getDouble(i);
            s.productY = (float) o.optDouble("productY", 0.44);
            s.productHeight = (float) o.optDouble("productHeight", 0.52);
            s.intensity = (float) o.optDouble("intensity", 1);
            s.direction = o.optInt("direction", 1);
            JSONArray t = o.optJSONArray("texts");
            if (t != null) for (int i = 0; i < t.length(); i++) s.texts.add(TextItem.fromJson(t.getJSONObject(i)));
            return s;
        }
    }

    public static class TextItem {
        public Enums.TextRole role = Enums.TextRole.FEATURE;
        public String text = "";
        public Enums.TextAnim anim = Enums.TextAnim.SLIDE_UP;
        /** Seconds relative to the scene start. */
        public float in;
        public float out;
        /** Center position, fractions of the screen. */
        public float x = 0.5f, y = 0.8f;
        /** Text size in pixels on the 1080-wide canvas. */
        public float size = 72f;
        public int color = 0xFFFFFFFF;
        /** 0 for none; otherwise the pill/badge fill color. */
        public int background;
        public boolean bold = true;
        /** Light sweep across the text (CTA buttons). */
        public boolean shine;

        JSONObject toJson() throws JSONException {
            JSONObject o = new JSONObject();
            o.put("role", role.name());
            o.put("text", text);
            o.put("anim", anim.name());
            o.put("in", in);
            o.put("out", out);
            o.put("x", x);
            o.put("y", y);
            o.put("size", size);
            o.put("color", color);
            o.put("background", background);
            o.put("bold", bold);
            o.put("shine", shine);
            return o;
        }

        static TextItem fromJson(JSONObject o) throws JSONException {
            TextItem t = new TextItem();
            t.role = Enums.parse(Enums.TextRole.class, o.optString("role"), Enums.TextRole.FEATURE);
            t.text = o.optString("text");
            t.anim = Enums.parse(Enums.TextAnim.class, o.optString("anim"), Enums.TextAnim.SLIDE_UP);
            t.in = (float) o.optDouble("in");
            t.out = (float) o.optDouble("out");
            t.x = (float) o.optDouble("x", 0.5);
            t.y = (float) o.optDouble("y", 0.8);
            t.size = (float) o.optDouble("size", 72);
            t.color = o.optInt("color", 0xFFFFFFFF);
            t.background = o.optInt("background");
            t.bold = o.optBoolean("bold", true);
            t.shine = o.optBoolean("shine");
            return t;
        }
    }

    public static class SfxCue {
        public Enums.SfxType type;
        public float time;
        public float gain = 0.6f;
        public float pan;
        public float length = 0.5f;

        public SfxCue() {}
        public SfxCue(Enums.SfxType type, float time, float gain, float pan, float length) {
            this.type = type; this.time = time; this.gain = gain; this.pan = pan; this.length = length;
        }

        JSONObject toJson() throws JSONException {
            JSONObject o = new JSONObject();
            o.put("type", type.name());
            o.put("time", time);
            o.put("gain", gain);
            o.put("pan", pan);
            o.put("length", length);
            return o;
        }

        static SfxCue fromJson(JSONObject o) throws JSONException {
            SfxCue c = new SfxCue();
            c.type = Enums.parse(Enums.SfxType.class, o.optString("type"), Enums.SfxType.WHOOSH);
            c.time = (float) o.optDouble("time");
            c.gain = (float) o.optDouble("gain", 0.6);
            c.pan = (float) o.optDouble("pan");
            c.length = (float) o.optDouble("length", 0.5);
            return c;
        }
    }

    public static class VoiceLine {
        public float time;
        public String text;

        public VoiceLine() {}
        public VoiceLine(float time, String text) { this.time = time; this.text = text; }
    }

    public JSONObject toJson() throws JSONException {
        JSONObject o = new JSONObject();
        o.put("mood", mood.name());
        o.put("look", look.name());
        o.put("bpm", bpm);
        o.put("beatOffset", beatOffset);
        o.put("totalSec", totalSec);
        o.put("fps", fps);
        o.put("font", font);
        o.put("fontBold", fontBold);
        o.put("letterSpacing", letterSpacing);
        o.put("uppercaseHeadlines", uppercaseHeadlines);
        o.put("primaryColor", primaryColor);
        o.put("accentColor", accentColor);
        o.put("textColor", textColor);
        o.put("backdropInner", backdropInner);
        o.put("backdropOuter", backdropOuter);
        JSONArray sc = new JSONArray();
        for (Scene s : scenes) sc.put(s.toJson());
        o.put("scenes", sc);
        JSONArray fx = new JSONArray();
        for (SfxCue c : sfx) fx.put(c.toJson());
        o.put("sfx", fx);
        JSONArray vo = new JSONArray();
        for (VoiceLine v : voice) vo.put(new JSONObject().put("time", v.time).put("text", v.text));
        o.put("voice", vo);
        o.put("notes", new JSONArray(notes));
        o.put("caption", caption);
        return o;
    }

    public static Storyboard fromJson(JSONObject o) throws JSONException {
        Storyboard b = new Storyboard();
        b.mood = Enums.parse(Enums.Mood.class, o.optString("mood"), Enums.Mood.HOME);
        b.look = Enums.parse(Enums.Look.class, o.optString("look"), Enums.Look.MODERN);
        b.bpm = o.optInt("bpm", 100);
        b.beatOffset = (float) o.optDouble("beatOffset");
        b.totalSec = (float) o.optDouble("totalSec", 15);
        b.fps = o.optInt("fps", 30);
        b.font = o.optString("font", "sans-serif");
        b.fontBold = o.optBoolean("fontBold", true);
        b.letterSpacing = (float) o.optDouble("letterSpacing");
        b.uppercaseHeadlines = o.optBoolean("uppercaseHeadlines");
        b.primaryColor = o.optInt("primaryColor", b.primaryColor);
        b.accentColor = o.optInt("accentColor", b.accentColor);
        b.textColor = o.optInt("textColor", b.textColor);
        b.backdropInner = o.optInt("backdropInner", b.backdropInner);
        b.backdropOuter = o.optInt("backdropOuter", b.backdropOuter);
        JSONArray sc = o.optJSONArray("scenes");
        if (sc != null) for (int i = 0; i < sc.length(); i++) b.scenes.add(Scene.fromJson(sc.getJSONObject(i)));
        JSONArray fx = o.optJSONArray("sfx");
        if (fx != null) for (int i = 0; i < fx.length(); i++) b.sfx.add(SfxCue.fromJson(fx.getJSONObject(i)));
        JSONArray vo = o.optJSONArray("voice");
        if (vo != null) {
            for (int i = 0; i < vo.length(); i++) {
                JSONObject v = vo.getJSONObject(i);
                b.voice.add(new VoiceLine((float) v.optDouble("time"), v.optString("text")));
            }
        }
        ImageAnalysis.readStrings(o.optJSONArray("notes"), b.notes);
        b.caption = o.optString("caption");
        return b;
    }

    public float beatSec() {
        return 60f / bpm;
    }
}
