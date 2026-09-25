package com.productvideostudio.director;

import com.productvideostudio.analysis.ProductInsights;
import com.productvideostudio.model.Enums;
import com.productvideostudio.model.Project;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;

/**
 * Writes the on-screen copy. It keeps the user's own words wherever possible (short feature
 * phrases pulled from the description) and fills gaps with mood-appropriate lines.
 */
public class CopyWriter {
    public String headline;
    public String tagline;
    public List<String> features = new ArrayList<>();
    public List<String> benefits = new ArrayList<>();
    public String cta;
    public String price = "";
    public String discount = "";
    public String website = "";
    public String brand = "";

    private static final String[] BENEFIT_WORDS = {"you", "your", "feel", "save", "enjoy", "easy", "easily", "perfect",
            "keep", "keeps", "help", "helps", "comfort", "never", "every", "anywhere", "all day", "boost", "protect",
            "effortless", "love", "worry", "confidence", "relax", "life"};

    public static CopyWriter write(Project p, ProductInsights in, Random rnd) {
        CopyWriter c = new CopyWriter();
        c.brand = in.brand;
        String name = p.name == null ? "" : p.name.trim();
        if (name.isEmpty()) name = !in.brand.isEmpty() ? in.brand : (!in.category.isEmpty() ? in.category : "New arrival");
        c.headline = name;

        List<String> phrases = phrases(p.description == null ? "" : p.description);
        String tag = null;
        for (String ph : phrases) {
            int words = ph.split("\\s+").length;
            if (isBenefit(ph)) {
                if (c.benefits.size() < 3) c.benefits.add(ph);
            } else if (words <= 6 && c.features.size() < 4) {
                c.features.add(ph);
            } else if (tag == null && words <= 8) {
                tag = ph;
            }
        }
        for (String m : in.materials) {
            if (c.features.size() >= 3) break;
            if ("Glossy finish".equals(m)) continue;
            String line = "Premium " + m.toLowerCase(Locale.ROOT);
            if (!containsIgnoreCase(c.features, m)) c.features.add(line);
        }
        String[] defaultsF = defaultFeatures(in.mood);
        for (int i = 0; c.features.size() < 2 && i < defaultsF.length; i++) {
            if (!c.features.contains(defaultsF[i])) c.features.add(defaultsF[i]);
        }
        String[] defaultsB = defaultBenefits(in.mood);
        int start = rnd.nextInt(defaultsB.length);
        for (int i = 0; c.benefits.size() < 2 && i < defaultsB.length; i++) {
            String b = defaultsB[(start + i) % defaultsB.length];
            if (!c.benefits.contains(b)) c.benefits.add(b);
        }
        c.tagline = tag != null ? tag : pick(taglines(in.mood), rnd);

        c.price = p.price == null ? "" : formatPrice(p.price.trim());
        c.discount = p.discount == null ? "" : formatDiscount(p.discount.trim());
        c.website = displayUrl(p.url);
        if (p.cta != null && !p.cta.trim().isEmpty()) c.cta = p.cta.trim();
        else if (!c.discount.isEmpty()) c.cta = "Limited Offer";
        else if (in.mood == Enums.Mood.TECH || in.mood == Enums.Mood.FOOD) c.cta = "Order Today";
        else if (c.website.isEmpty() && c.price.isEmpty()) c.cta = "Learn More";
        else c.cta = "Shop Now";
        return c;
    }

    /** Voice-over script, one entry per line of narration. */
    public List<String> voiceScript(String custom, float seconds) {
        List<String> lines = new ArrayList<>();
        if (custom != null && !custom.trim().isEmpty()) {
            for (String s : custom.split("(?<=[.!?])\\s+|\\n+")) if (!s.trim().isEmpty()) lines.add(s.trim());
            return lines;
        }
        // Roughly one line per 2.6 s leaves room to breathe between lines.
        int budget = Math.max(2, (int) (seconds / 2.6f));
        List<String> middle = new ArrayList<>();
        middle.add(sentence(tagline));
        if (!features.isEmpty()) middle.add(sentence(features.get(0)));
        if (!benefits.isEmpty()) middle.add(sentence(benefits.get(0)));
        if (features.size() > 1) middle.add(sentence(features.get(1)));
        lines.add("Introducing " + headline + ".");
        for (int i = 0; i < middle.size() && lines.size() < budget - 1; i++) lines.add(middle.get(i));
        String end = cta;
        if (!discount.isEmpty()) end = discount.replace("-", "") + " off. " + cta;
        if (!website.isEmpty()) {
            String host = website.contains("/") ? website.substring(0, website.indexOf('/')) : website;
            end += " at " + host.replace(".", " dot ");
        }
        lines.add(sentence(end));
        return lines;
    }

    public String caption(Enums.Mood mood, String category) {
        StringBuilder sb = new StringBuilder();
        sb.append(headline).append(" — ").append(tagline).append('\n');
        for (String f : features) sb.append("✦ ").append(f).append('\n');
        if (!discount.isEmpty()) sb.append(discount).append(" for a limited time").append('\n');
        if (!price.isEmpty()) sb.append(price).append('\n');
        sb.append(cta);
        if (!website.isEmpty()) sb.append(" → ").append(website);
        sb.append("\n\n");
        Set<String> tags = new LinkedHashSet<>();
        tags.add(hashtag(headline));
        if (!brand.isEmpty()) tags.add(hashtag(brand));
        if (category != null && !category.isEmpty()) tags.add(hashtag(category));
        switch (mood) {
            case LUXURY: tags.add("#luxury"); tags.add("#premium"); break;
            case TECH: tags.add("#tech"); tags.add("#gadgets"); break;
            case NATURE: tags.add("#natural"); tags.add("#organic"); break;
            case PLAYFUL: tags.add("#fun"); tags.add("#gifts"); break;
            case FASHION: tags.add("#fashion"); tags.add("#style"); break;
            case BEAUTY: tags.add("#beauty"); tags.add("#skincare"); break;
            case FOOD: tags.add("#foodie"); tags.add("#delicious"); break;
            case SPORT: tags.add("#fitness"); tags.add("#sport"); break;
            default: tags.add("#home"); tags.add("#design");
        }
        tags.add("#newarrival");
        tags.add("#shopnow");
        tags.add("#reels");
        tags.remove("#");
        sb.append(String.join(" ", tags));
        return sb.toString();
    }

    // ----------------------------------------------------------------------------------------

    static List<String> phrases(String description) {
        List<String> out = new ArrayList<>();
        for (String raw : description.split("[\\n\\r•;·|]+|(?<=[.!?])\\s+")) {
            String s = raw.replaceAll("^[\\s\\-*–—\\d.)]+", "").replaceAll("[.!?\\s]+$", "").trim();
            if (s.isEmpty()) continue;
            if (s.split("\\s+").length > 6) {
                // Long sentence: try its comma/"and" parts as separate phrases.
                boolean split = false;
                for (String part : s.split(",\\s*|\\s+and\\s+|\\s+with\\s+")) {
                    String t = part.trim();
                    int words = t.split("\\s+").length;
                    if (words >= 2 && words <= 6) {
                        out.add(capitalize(t));
                        split = true;
                    }
                }
                if (split) continue;
            }
            out.add(capitalize(s));
        }
        return out;
    }

    static boolean isBenefit(String s) {
        String l = " " + s.toLowerCase(Locale.ROOT) + " ";
        for (String w : BENEFIT_WORDS) if (l.contains(" " + w + " ") || l.contains(" " + w + ",")) return true;
        return false;
    }

    static String[] taglines(Enums.Mood m) {
        switch (m) {
            case LUXURY: return new String[]{"Elegance, redefined", "Made to be noticed", "Timeless by design"};
            case TECH: return new String[]{"The future, in your hands", "Smarter by design", "Power meets simplicity"};
            case NATURE: return new String[]{"Pure by nature", "Rooted in nature", "Naturally better"};
            case PLAYFUL: return new String[]{"Made for fun", "Joy in every box", "Play more"};
            case FASHION: return new String[]{"Wear the moment", "Style that speaks", "Made to stand out"};
            case BEAUTY: return new String[]{"Beauty that shows", "Your daily ritual", "Glow, naturally"};
            case FOOD: return new String[]{"Taste the difference", "Made to be savored", "Flavor first"};
            case SPORT: return new String[]{"Go further", "Built to perform", "Push your limits"};
            default: return new String[]{"Made for everyday living", "Designed for home", "Simply better"};
        }
    }

    static String[] defaultFeatures(Enums.Mood m) {
        switch (m) {
            case LUXURY: return new String[]{"Crafted to perfection", "Exquisite detail"};
            case TECH: return new String[]{"Cutting-edge design", "Seamless performance"};
            case NATURE: return new String[]{"Naturally sourced", "Gentle and pure"};
            case PLAYFUL: return new String[]{"Bright, bold, fun", "Made to delight"};
            case FASHION: return new String[]{"Tailored fit", "Statement style"};
            case BEAUTY: return new String[]{"Gentle formula", "Visible results"};
            case FOOD: return new String[]{"Fresh ingredients", "Rich flavor"};
            case SPORT: return new String[]{"Lightweight build", "Made to move"};
            default: return new String[]{"Thoughtful design", "Built to last"};
        }
    }

    static String[] defaultBenefits(Enums.Mood m) {
        switch (m) {
            case LUXURY: return new String[]{"Make every moment special", "A gift they'll never forget", "Luxury you can feel"};
            case TECH: return new String[]{"Do more, effortlessly", "Stay connected anywhere", "Save time every day"};
            case NATURE: return new String[]{"Feel good, naturally", "Kind to you and the planet", "Nature's best, every day"};
            case PLAYFUL: return new String[]{"Smiles guaranteed", "Fun for everyone", "Make every day brighter"};
            case FASHION: return new String[]{"Look good, feel great", "Confidence in every step", "Your style, your rules"};
            case BEAUTY: return new String[]{"Feel confident every day", "Your skin will love it", "Self-care made simple"};
            case FOOD: return new String[]{"Enjoy every bite", "Treat yourself today", "Perfect for sharing"};
            case SPORT: return new String[]{"Train harder, recover faster", "Comfort all day long", "Reach your goals"};
            default: return new String[]{"Makes life easier", "Comfort every day", "Love where you live"};
        }
    }

    static String formatPrice(String p) {
        if (p.isEmpty()) return "";
        if (p.matches("[\\d.,]+")) return "$" + p;
        return p;
    }

    static String formatDiscount(String d) {
        if (d.isEmpty()) return "";
        String digits = d.replaceAll("[^\\d.]", "");
        if (d.contains("%") || (d.matches("[\\d.]+") && !digits.isEmpty())) return "-" + digits + "%";
        return d;
    }

    public static String displayUrl(String url) {
        if (url == null) return "";
        String u = url.trim().replaceFirst("^https?://", "").replaceFirst("^www\\.", "");
        int slash = u.indexOf('/');
        if (slash > 0 && slash < u.length() - 1 && u.length() > 28) u = u.substring(0, slash);
        if (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        return u;
    }

    static String sentence(String s) {
        String t = s.trim();
        if (t.isEmpty()) return t;
        char last = t.charAt(t.length() - 1);
        return (last == '.' || last == '!' || last == '?') ? t : t + ".";
    }

    static String hashtag(String s) {
        String t = s.replaceAll("[^\\p{L}\\p{N}]", "");
        return "#" + t.toLowerCase(Locale.ROOT);
    }

    static String capitalize(String s) {
        return s.isEmpty() ? s : Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    static boolean containsIgnoreCase(List<String> list, String needle) {
        String n = needle.toLowerCase(Locale.ROOT);
        for (String s : list) if (s.toLowerCase(Locale.ROOT).contains(n)) return true;
        return false;
    }

    static <T> T pick(T[] arr, Random rnd) {
        return arr[rnd.nextInt(arr.length)];
    }
}
