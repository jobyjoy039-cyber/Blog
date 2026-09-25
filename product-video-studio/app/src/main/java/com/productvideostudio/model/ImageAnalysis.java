package com.productvideostudio.model;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** What the analyzer learned about one product photo. Coordinates are normalized to 0..1. */
public class ImageAnalysis {
    public String file;
    public int width;
    public int height;

    /** Dominant colors, most common first (ARGB). */
    public List<Integer> palette = new ArrayList<>();
    /** The most saturated color that still covers a meaningful area. */
    public int accentColor;
    public int backgroundColor;

    /** True when the border is a near-uniform color, i.e. a packshot we can cut out. */
    public boolean plainBackground;
    /** Tight box around the product (left, top, right, bottom). */
    public float[] subjectBox = {0f, 0f, 1f, 1f};
    /** Visual center of interest. */
    public float focusX = 0.5f, focusY = 0.5f;
    /** Center of the most detailed region, used for macro shots. */
    public float detailX = 0.5f, detailY = 0.5f;

    public float sharpness;
    public float brightness;
    public float colorfulness;
    /** Fraction of clipped highlights, a hint of gloss/metal/glass. */
    public float specular;
    /** 0..1, how much of the subject box the product fills (1 = boxy, ~0.78 = round). */
    public float fillRatio = 1f;
    /** "tall", "wide", "square" or "round". */
    public String shape = "square";

    /** Labels from on-device image labeling, most confident first. */
    public List<String> labels = new ArrayList<>();
    /** Text found on the packaging, largest first. */
    public List<String> texts = new ArrayList<>();
    public List<String> materials = new ArrayList<>();

    /** "packshot" or "lifestyle". */
    public String kind = "packshot";
    /** Angle the photo appears to be taken from. */
    public Enums.CameraAngle viewAngle = Enums.CameraAngle.FRONT;

    public float quality() {
        return 0.55f * Math.min(1f, sharpness) + 0.25f * (1f - Math.abs(brightness - 0.55f) * 1.6f)
                + 0.2f * Math.min(1f, colorfulness * 1.5f);
    }

    public boolean isLifestyle() {
        return "lifestyle".equals(kind);
    }

    public JSONObject toJson() throws JSONException {
        JSONObject o = new JSONObject();
        o.put("file", file);
        o.put("width", width);
        o.put("height", height);
        o.put("palette", new JSONArray(palette));
        o.put("accentColor", accentColor);
        o.put("backgroundColor", backgroundColor);
        o.put("plainBackground", plainBackground);
        JSONArray box = new JSONArray();
        for (float f : subjectBox) box.put((double) f);
        o.put("subjectBox", box);
        o.put("focusX", focusX);
        o.put("focusY", focusY);
        o.put("detailX", detailX);
        o.put("detailY", detailY);
        o.put("sharpness", sharpness);
        o.put("brightness", brightness);
        o.put("colorfulness", colorfulness);
        o.put("specular", specular);
        o.put("fillRatio", fillRatio);
        o.put("shape", shape);
        o.put("labels", new JSONArray(labels));
        o.put("texts", new JSONArray(texts));
        o.put("materials", new JSONArray(materials));
        o.put("kind", kind);
        o.put("viewAngle", viewAngle.name());
        return o;
    }

    public static ImageAnalysis fromJson(JSONObject o) throws JSONException {
        ImageAnalysis a = new ImageAnalysis();
        a.file = o.getString("file");
        a.width = o.optInt("width");
        a.height = o.optInt("height");
        readInts(o.optJSONArray("palette"), a.palette);
        a.accentColor = o.optInt("accentColor");
        a.backgroundColor = o.optInt("backgroundColor");
        a.plainBackground = o.optBoolean("plainBackground");
        JSONArray box = o.optJSONArray("subjectBox");
        if (box != null && box.length() == 4) {
            for (int i = 0; i < 4; i++) a.subjectBox[i] = (float) box.getDouble(i);
        }
        a.focusX = (float) o.optDouble("focusX", 0.5);
        a.focusY = (float) o.optDouble("focusY", 0.5);
        a.detailX = (float) o.optDouble("detailX", 0.5);
        a.detailY = (float) o.optDouble("detailY", 0.5);
        a.sharpness = (float) o.optDouble("sharpness", 0.5);
        a.brightness = (float) o.optDouble("brightness", 0.5);
        a.colorfulness = (float) o.optDouble("colorfulness", 0.3);
        a.specular = (float) o.optDouble("specular", 0);
        a.fillRatio = (float) o.optDouble("fillRatio", 1);
        a.shape = o.optString("shape", "square");
        readStrings(o.optJSONArray("labels"), a.labels);
        readStrings(o.optJSONArray("texts"), a.texts);
        readStrings(o.optJSONArray("materials"), a.materials);
        a.kind = o.optString("kind", "packshot");
        a.viewAngle = Enums.parse(Enums.CameraAngle.class, o.optString("viewAngle"), Enums.CameraAngle.FRONT);
        return a;
    }

    static void readInts(JSONArray arr, List<Integer> out) throws JSONException {
        if (arr != null) for (int i = 0; i < arr.length(); i++) out.add(arr.getInt(i));
    }

    static void readStrings(JSONArray arr, List<String> out) throws JSONException {
        if (arr != null) for (int i = 0; i < arr.length(); i++) out.add(arr.getString(i));
    }
}
