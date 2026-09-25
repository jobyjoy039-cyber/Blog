package com.productvideostudio.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Everything the user gave us plus the director's latest plan. Files referenced here live in the
 * project's own folder (see {@link com.productvideostudio.storage.ProjectStore}), so a project
 * survives the original gallery files being deleted.
 */
public class Project {
    public static final String MUSIC_AUTO = "auto";
    public static final String MUSIC_FILE = "file";
    public static final String MUSIC_NONE = "none";

    public static final String VOICE_OFF = "off";
    public static final String VOICE_TTS = "tts";
    public static final String VOICE_FILE = "file";

    public String id;
    public long createdAt;
    public long updatedAt;

    public String name = "";
    public String description = "";
    public String price = "";
    public String discount = "";
    public String url = "";
    /** Empty means the director chooses. */
    public String cta = "";

    /** File names inside the project folder. */
    public List<String> images = new ArrayList<>();
    public String logo;
    /** Up to three ARGB colors; empty means "take them from the images". */
    public List<Integer> brandColors = new ArrayList<>();

    public String musicMode = MUSIC_AUTO;
    public String musicFile;
    public String voiceMode = VOICE_OFF;
    public String voiceFile;
    /** Optional user-written voice-over script; empty means generate one. */
    public String voiceScript = "";

    /** Null means the director picks the look from the mood. */
    public Enums.Look look;
    public int durationSec = 15;
    public int fps = 30;
    public long seed = 1;

    public List<ImageAnalysis> analyses = new ArrayList<>();
    public Storyboard storyboard;

    /** Absolute path of the last rendered video in app storage. */
    public String outputPath;
    /** content:// URI of the copy saved to the gallery. */
    public String outputUri;
    public String caption;

    public JSONObject toJson() throws JSONException {
        JSONObject o = new JSONObject();
        o.put("id", id);
        o.put("createdAt", createdAt);
        o.put("updatedAt", updatedAt);
        o.put("name", name);
        o.put("description", description);
        o.put("price", price);
        o.put("discount", discount);
        o.put("url", url);
        o.put("cta", cta);
        o.put("images", new JSONArray(images));
        o.putOpt("logo", logo);
        o.put("brandColors", new JSONArray(brandColors));
        o.put("musicMode", musicMode);
        o.putOpt("musicFile", musicFile);
        o.put("voiceMode", voiceMode);
        o.putOpt("voiceFile", voiceFile);
        o.put("voiceScript", voiceScript);
        o.putOpt("look", look == null ? null : look.name());
        o.put("durationSec", durationSec);
        o.put("fps", fps);
        o.put("seed", seed);
        JSONArray a = new JSONArray();
        for (ImageAnalysis an : analyses) a.put(an.toJson());
        o.put("analyses", a);
        if (storyboard != null) o.put("storyboard", storyboard.toJson());
        o.putOpt("outputPath", outputPath);
        o.putOpt("outputUri", outputUri);
        o.putOpt("caption", caption);
        return o;
    }

    public static Project fromJson(JSONObject o) throws JSONException {
        Project p = new Project();
        p.id = o.getString("id");
        p.createdAt = o.optLong("createdAt");
        p.updatedAt = o.optLong("updatedAt");
        p.name = o.optString("name");
        p.description = o.optString("description");
        p.price = o.optString("price");
        p.discount = o.optString("discount");
        p.url = o.optString("url");
        p.cta = o.optString("cta");
        JSONArray imgs = o.optJSONArray("images");
        if (imgs != null) for (int i = 0; i < imgs.length(); i++) p.images.add(imgs.getString(i));
        p.logo = o.has("logo") ? o.getString("logo") : null;
        JSONArray cols = o.optJSONArray("brandColors");
        if (cols != null) for (int i = 0; i < cols.length(); i++) p.brandColors.add(cols.getInt(i));
        p.musicMode = o.optString("musicMode", MUSIC_AUTO);
        p.musicFile = o.has("musicFile") ? o.getString("musicFile") : null;
        p.voiceMode = o.optString("voiceMode", VOICE_OFF);
        p.voiceFile = o.has("voiceFile") ? o.getString("voiceFile") : null;
        p.voiceScript = o.optString("voiceScript");
        p.look = o.has("look") ? Enums.parse(Enums.Look.class, o.getString("look"), null) : null;
        p.durationSec = o.optInt("durationSec", 15);
        p.fps = o.optInt("fps", 30);
        p.seed = o.optLong("seed", 1);
        JSONArray an = o.optJSONArray("analyses");
        if (an != null) for (int i = 0; i < an.length(); i++) p.analyses.add(ImageAnalysis.fromJson(an.getJSONObject(i)));
        if (o.has("storyboard")) p.storyboard = Storyboard.fromJson(o.getJSONObject("storyboard"));
        p.outputPath = o.has("outputPath") ? o.getString("outputPath") : null;
        p.outputUri = o.has("outputUri") ? o.getString("outputUri") : null;
        p.caption = o.has("caption") ? o.getString("caption") : null;
        return p;
    }

    public String displayName() {
        return name == null || name.trim().isEmpty() ? "Untitled product" : name.trim();
    }

    /** Analysis for an image file, or null if it has not been analyzed yet. */
    public ImageAnalysis analysisFor(String file) {
        for (ImageAnalysis a : analyses) if (a.file.equals(file)) return a;
        return null;
    }
}
