package com.productvideostudio.analysis;

import android.text.Html;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Reads a product page's title, description and share image (Open Graph tags). */
public class UrlMetadata {
    public String title = "";
    public String description = "";
    public String imageUrl = "";

    public static UrlMetadata fetch(String pageUrl) throws IOException {
        String url = normalize(pageUrl);
        String html = new String(download(url, 1_500_000), StandardCharsets.UTF_8);
        UrlMetadata m = new UrlMetadata();
        m.title = firstNonEmpty(meta(html, "og:title"), meta(html, "twitter:title"), tag(html, "title"));
        m.description = firstNonEmpty(meta(html, "og:description"), meta(html, "description"), meta(html, "twitter:description"));
        String img = firstNonEmpty(meta(html, "og:image"), meta(html, "twitter:image"));
        if (!img.isEmpty()) m.imageUrl = new URL(new URL(url), img).toString();
        return m;
    }

    public static void downloadTo(String url, File dest) throws IOException {
        byte[] data = download(url, 15_000_000);
        try (FileOutputStream out = new FileOutputStream(dest)) {
            out.write(data);
        }
    }

    public static String normalize(String url) {
        String u = url.trim();
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "https://" + u;
        return u;
    }

    static byte[] download(String url, int limit) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(10000);
        c.setInstanceFollowRedirects(true);
        c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) ProductVideoStudio/1.0");
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0 && out.size() < limit) out.write(buf, 0, n);
            return out.toByteArray();
        } finally {
            c.disconnect();
        }
    }

    static String meta(String html, String key) {
        Pattern p1 = Pattern.compile("<meta[^>]+(?:property|name)\\s*=\\s*[\"']" + Pattern.quote(key)
                + "[\"'][^>]*content\\s*=\\s*[\"']([^\"']*)[\"']", Pattern.CASE_INSENSITIVE);
        Matcher m = p1.matcher(html);
        if (m.find()) return clean(m.group(1));
        Pattern p2 = Pattern.compile("<meta[^>]+content\\s*=\\s*[\"']([^\"']*)[\"'][^>]*(?:property|name)\\s*=\\s*[\"']"
                + Pattern.quote(key) + "[\"']", Pattern.CASE_INSENSITIVE);
        m = p2.matcher(html);
        return m.find() ? clean(m.group(1)) : "";
    }

    static String tag(String html, String tag) {
        Matcher m = Pattern.compile("<" + tag + "[^>]*>([^<]*)</" + tag + ">", Pattern.CASE_INSENSITIVE).matcher(html);
        return m.find() ? clean(m.group(1)) : "";
    }

    static String clean(String s) {
        return Html.fromHtml(s, Html.FROM_HTML_MODE_LEGACY).toString().replaceAll("\\s+", " ").trim();
    }

    static String firstNonEmpty(String... values) {
        for (String v : values) if (v != null && !v.isEmpty()) return v;
        return "";
    }
}
