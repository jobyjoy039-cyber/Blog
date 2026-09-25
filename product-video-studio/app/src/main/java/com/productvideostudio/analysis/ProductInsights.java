package com.productvideostudio.analysis;

import android.graphics.Color;

import com.productvideostudio.model.Enums;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Project;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Combines per-image analyses and the user's words into a picture of the product: what it is,
 * what it is made of, whose brand it is, and which creative mood suits it.
 */
public class ProductInsights {
    public Enums.Mood mood = Enums.Mood.HOME;
    public String category = "";
    public String brand = "";
    public List<String> materials = new ArrayList<>();
    public List<Integer> palette = new ArrayList<>();
    public int accent = 0xFFFFC107;
    public boolean darkProduct;
    public boolean glossy;
    public List<String> notes = new ArrayList<>();

    private static final String[][] MOOD_WORDS = {
            /* LUXURY */ {"jewel", "watch", "ring", "necklace", "bracelet", "earring", "gold", "diamond", "perfume", "fragrance", "luxury", "premium", "silk", "handbag", "cologne", "elegant", "crystal"},
            /* TECH */ {"electronic", "gadget", "phone", "mobile", "laptop", "computer", "headphone", "earbud", "speaker", "camera", "keyboard", "device", "smart", "wireless", "bluetooth", "battery", "charger", "gaming", "drone", "screen", "tech", "usb", "led", "monitor", "mouse"},
            /* NATURE */ {"plant", "flower", "organic", "natural", "herbal", "herb", "eco", "leaf", "ayurved", "bamboo", "tea", "essential oil", "garden", "vegan", "sustainable", "botanical", "forest", "wood"},
            /* PLAYFUL */ {"toy", "game", "kid", "child", "baby", "fun", "candy", "colorful", "colourful", "cartoon", "pet", "dog", "cat", "balloon", "party", "gift"},
            /* FASHION */ {"clothing", "dress", "shirt", "jacket", "shoe", "sneaker", "footwear", "fashion", "bag", "sunglasses", "hat", "jeans", "apparel", "outfit", "textile", "denim", "saree", "kurta", "wear"},
            /* BEAUTY */ {"cosmetic", "skin", "cream", "lotion", "serum", "makeup", "lipstick", "beauty", "hair", "nail", "spa", "face", "moistur", "soap", "shampoo", "glow"},
            /* FOOD */ {"food", "drink", "beverage", "coffee", "juice", "snack", "chocolate", "cake", "fruit", "cuisine", "tableware", "wine", "beer", "cooking", "spice", "honey", "sauce", "baked", "dessert", "meal", "tasty", "flavor", "flavour"},
            /* SPORT */ {"sport", "fitness", "gym", "running", "bicycle", "ball", "yoga", "workout", "hiking", "protein", "athletic", "training", "bike", "outdoor"},
            /* HOME */ {"furniture", "home", "kitchen", "lamp", "decor", "interior", "chair", "table", "bed", "room", "pillow", "candle", "mug", "cup", "vase", "cookware", "appliance", "sofa", "shelf"},
    };
    private static final Enums.Mood[] MOOD_ORDER = {
            Enums.Mood.LUXURY, Enums.Mood.TECH, Enums.Mood.NATURE, Enums.Mood.PLAYFUL, Enums.Mood.FASHION,
            Enums.Mood.BEAUTY, Enums.Mood.FOOD, Enums.Mood.SPORT, Enums.Mood.HOME};

    private static final String[] MATERIALS = {"leather", "wood", "metal", "glass", "plastic", "ceramic", "porcelain",
            "cotton", "silk", "denim", "steel", "gold", "silver", "paper", "bamboo", "rubber", "stone", "marble",
            "wool", "linen", "aluminium", "aluminum", "brass", "copper", "velvet", "fabric", "clay"};

    private static final Set<String> GENERIC = new LinkedHashSet<>();
    static {
        for (String g : new String[]{"product", "font", "rectangle", "text", "pattern", "circle", "material", "design",
                "logo", "brand", "graphics", "illustration", "art", "still life", "close-up", "macro photography",
                "event", "fun", "room", "cool", "sky", "smile", "beauty"}) GENERIC.add(g);
    }

    public static ProductInsights from(Project p) {
        ProductInsights in = new ProductInsights();
        StringBuilder corpus = new StringBuilder();
        corpus.append(p.name).append(' ').append(p.description).append(' ');
        Set<String> labels = new LinkedHashSet<>();
        for (ImageAnalysis a : p.analyses) labels.addAll(a.labels);
        for (String l : labels) corpus.append(l).append(' ');
        String text = corpus.toString().toLowerCase(Locale.ROOT);

        // Mood from words, with image evidence as a tie-breaker.
        int[] score = new int[MOOD_WORDS.length];
        for (int m = 0; m < MOOD_WORDS.length; m++) {
            for (String w : MOOD_WORDS[m]) {
                // Short words must match whole (plurals allowed) so "cat" doesn't hit "category".
                String re = w.length() <= 4 ? "\\b" + Pattern.quote(w) + "(s|es)?\\b" : "\\b" + Pattern.quote(w);
                Matcher mt = Pattern.compile(re).matcher(text);
                while (mt.find()) score[m] += 2;
            }
        }
        float sat = 0, val = 0, green = 0, gold = 0;
        int nColors = 0;
        for (ImageAnalysis a : p.analyses) {
            for (int c : a.palette) {
                float[] hsv = new float[3];
                Color.colorToHSV(c, hsv);
                sat += hsv[1]; val += hsv[2]; nColors++;
                if (hsv[0] > 75 && hsv[0] < 160 && hsv[1] > 0.25f) green++;
                if (hsv[0] > 30 && hsv[0] < 55 && hsv[1] > 0.35f && hsv[2] > 0.45f) gold++;
            }
            if (a.specular > 0.03f) in.glossy = true;
        }
        if (nColors > 0) {
            sat /= nColors;
            val /= nColors;
            if (sat > 0.55f) score[3] += 1;                  // playful
            if (green / nColors > 0.3f) score[2] += 2;       // nature
            if (gold > 0 && val < 0.5f) score[0] += 2;       // luxury
            if (sat < 0.18f && val < 0.45f) score[1] += 1;   // dark, desaturated: tech
            if (sat < 0.15f && val > 0.7f) score[8] += 1;    // light, neutral: home/minimal
            in.darkProduct = val < 0.35f;
        }
        int best = 8;
        for (int m = 0; m < score.length; m++) if (score[m] > score[best]) best = m;
        in.mood = MOOD_ORDER[best];

        // Category: first specific label.
        for (String l : labels) {
            if (!GENERIC.contains(l.toLowerCase(Locale.ROOT))) {
                in.category = l;
                break;
            }
        }

        // Materials from labels and description.
        Set<String> mats = new LinkedHashSet<>();
        for (String m : MATERIALS) if (text.contains(m)) mats.add(capitalize(m));
        for (ImageAnalysis a : p.analyses) a.materials.clear();
        for (ImageAnalysis a : p.analyses) {
            for (String l : a.labels) {
                for (String m : MATERIALS) if (l.toLowerCase(Locale.ROOT).contains(m)) a.materials.add(capitalize(m));
            }
            if (a.specular > 0.03f && !a.materials.contains("Glossy finish")) a.materials.add("Glossy finish");
        }
        if (in.glossy) mats.add("Glossy finish");
        in.materials.addAll(mats);

        // Brand: the most prominent packaging text, preferring words shared with the product name.
        String nameLower = p.name == null ? "" : p.name.toLowerCase(Locale.ROOT);
        String bestText = "";
        for (ImageAnalysis a : p.analyses) {
            for (String t : a.texts) {
                String clean = t.replaceAll("[^\\p{L}\\p{N}&' .-]", "").trim();
                if (clean.length() < 2 || clean.length() > 22 || !clean.matches(".*\\p{L}.*")) continue;
                if (!nameLower.isEmpty() && nameLower.contains(clean.toLowerCase(Locale.ROOT))) {
                    bestText = clean;
                    break;
                }
                if (bestText.isEmpty()) bestText = clean;
            }
        }
        in.brand = bestText;

        // Palette across images, brand colors first.
        in.palette.addAll(p.brandColors);
        for (ImageAnalysis a : p.analyses) {
            for (int c : a.palette) if (in.palette.size() < 8) in.palette.add(c);
        }
        if (!p.brandColors.isEmpty()) {
            in.accent = p.brandColors.get(0);
        } else {
            float bestScore = -1;
            for (ImageAnalysis a : p.analyses) {
                float[] hsv = new float[3];
                Color.colorToHSV(a.accentColor, hsv);
                float s = hsv[1] * hsv[2];
                if (s > bestScore) { bestScore = s; in.accent = a.accentColor; }
            }
            float[] hsv = new float[3];
            Color.colorToHSV(in.accent, hsv);
            if (hsv[1] < 0.2f) in.accent = defaultAccent(in.mood);
        }

        in.notes.add("Mood: " + in.mood.label + (in.category.isEmpty() ? "" : " (looks like " + in.category.toLowerCase(Locale.ROOT) + ")"));
        if (!in.materials.isEmpty()) in.notes.add("Materials: " + String.join(", ", in.materials));
        if (!in.brand.isEmpty()) in.notes.add("Packaging text: “" + in.brand + "”");
        return in;
    }

    public static int defaultAccent(Enums.Mood mood) {
        switch (mood) {
            case LUXURY: return 0xFFD4AF37;
            case TECH: return 0xFF3D8BFF;
            case NATURE: return 0xFF6FA35A;
            case PLAYFUL: return 0xFFFF5A8A;
            case FASHION: return 0xFFE8E2D6;
            case BEAUTY: return 0xFFE9A0A8;
            case FOOD: return 0xFFFF8A3D;
            case SPORT: return 0xFFC6FF3D;
            default: return 0xFFE0B279;
        }
    }

    static String capitalize(String s) {
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }
}
