package com.stykanimate.ai;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ContentValues;
import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Hosts the AI Studio and the StykAnimate editor in a WebView served from the APK's assets. */
public class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String START_URL = "https://" + HOST + "/assets/www/index.html";
    private static final int FILE_CHOOSER = 1;
    /** The only hosts the page may reach through the native HTTP bridge. */
    private static final String[] API_HOSTS = {"api.anthropic.com", "api.openai.com"};

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private final ExecutorService io = Executors.newCachedThreadPool();
    private final Map<String, PendingFile> saves = new HashMap<>();

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        webView = new WebView(this);
        webView.setBackgroundColor(0xFF0F1115);
        setContentView(webView);
        applyInsets(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);

        final AssetManager assets = getAssets();
        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .setDomain(HOST)
                .addPathHandler("/assets/", path -> serveAsset(assets, path))
                .build();

        webView.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(@NonNull WebView view, @NonNull WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(@NonNull WebView view, @NonNull WebResourceRequest request) {
                Uri url = request.getUrl();
                if (HOST.equals(url.getHost())) return false;
                // External links (docs, Discord, community) open in the browser.
                try { startActivity(new Intent(Intent.ACTION_VIEW, url)); } catch (ActivityNotFoundException ignored) { }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent intent = params.createIntent();
                intent.setType("*/*");
                String[] accept = params.getAcceptTypes();
                if (accept != null && accept.length == 1 && accept[0].contains("/") && !accept[0].contains(",")) intent.setType(accept[0]);
                try {
                    startActivityForResult(intent, FILE_CHOOSER);
                } catch (ActivityNotFoundException e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        webView.addJavascriptInterface(new Bridge(), "Android");
        if (savedInstanceState != null) webView.restoreState(savedInstanceState);
        else webView.loadUrl(START_URL);
    }

    private void applyInsets(View view) {
        view.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
    }

    /** Serves files from assets/ with the MIME types ES modules and WebAssembly require. */
    private static WebResourceResponse serveAsset(AssetManager assets, String path) {
        try {
            String clean = path.split("[?#]")[0];
            if (clean.endsWith("/")) clean += "index.html";
            InputStream in = assets.open(clean, AssetManager.ACCESS_STREAMING);
            WebResourceResponse res = new WebResourceResponse(mimeFor(clean), null, in);
            Map<String, String> headers = new HashMap<>();
            headers.put("Cache-Control", "no-cache");
            res.setResponseHeaders(headers);
            return res;
        } catch (IOException e) {
            WebResourceResponse missing = new WebResourceResponse("text/plain", "utf-8", new java.io.ByteArrayInputStream(new byte[0]));
            missing.setStatusCodeAndReasonPhrase(404, "Not Found");
            return missing;
        }
    }

    private static String mimeFor(String path) {
        String ext = path.substring(path.lastIndexOf('.') + 1).toLowerCase();
        switch (ext) {
            case "html": return "text/html";
            case "js": case "mjs": case "cjs": return "text/javascript";
            case "css": return "text/css";
            case "json": case "map": return "application/json";
            case "webmanifest": return "application/manifest+json";
            case "wasm": return "application/wasm";
            case "svg": return "image/svg+xml";
            case "png": return "image/png";
            case "jpg": case "jpeg": return "image/jpeg";
            case "gif": return "image/gif";
            case "webp": return "image/webp";
            case "ico": return "image/x-icon";
            case "woff2": return "font/woff2";
            case "woff": return "font/woff";
            case "ttf": return "font/ttf";
            case "otf": return "font/otf";
            case "mp3": return "audio/mpeg";
            case "wav": return "audio/wav";
            case "ogg": return "audio/ogg";
            case "mp4": return "video/mp4";
            case "webm": return "video/webm";
            case "zip": return "application/zip";
            case "txt": return "text/plain";
            default: return "application/octet-stream";
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        webView.destroy();
        super.onDestroy();
    }

    private void deliver(String id, int status, String text) {
        String q = JSONObject.quote(id);
        String js = "window.__androidHttp&&window.__androidHttp[" + q + "]&&window.__androidHttp[" + q + "](" + status + "," + JSONObject.quote(text) + ")";
        runOnUiThread(() -> webView.evaluateJavascript(js, null));
    }

    private static final class PendingFile {
        final OutputStream out;
        final Uri uri;
        final String where;
        PendingFile(OutputStream out, Uri uri, String where) { this.out = out; this.uri = uri; this.where = where; }
    }

    /** Methods callable from the page as window.Android.* */
    private final class Bridge {
        @JavascriptInterface
        public void httpPost(String id, String url, String headersJson, String body) {
            io.execute(() -> {
                HttpURLConnection conn = null;
                try {
                    URL u = new URL(url);
                    boolean allowed = false;
                    for (String h : API_HOSTS) allowed |= h.equals(u.getHost());
                    if (!"https".equals(u.getProtocol()) || !allowed) throw new IOException("Blocked request to " + u.getHost());
                    conn = (HttpURLConnection) u.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(30_000);
                    conn.setReadTimeout(600_000); // long generations can take minutes
                    conn.setDoOutput(true);
                    JSONObject headers = new JSONObject(headersJson);
                    for (Iterator<String> it = headers.keys(); it.hasNext(); ) {
                        String k = it.next();
                        conn.setRequestProperty(k, headers.getString(k));
                    }
                    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                    conn.setFixedLengthStreamingMode(bytes.length);
                    try (OutputStream out = conn.getOutputStream()) { out.write(bytes); }
                    int status = conn.getResponseCode();
                    InputStream in = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
                    deliver(id, status, in == null ? "" : readAll(in));
                } catch (Exception e) {
                    deliver(id, 0, e.getClass().getSimpleName() + ": " + e.getMessage());
                } finally {
                    if (conn != null) conn.disconnect();
                }
            });
        }

        @JavascriptInterface
        public String saveBegin(String name, String mime) {
            String safe = name.replaceAll("[\\\\/:*?\"<>|]", "_");
            try {
                String token = Long.toHexString(System.nanoTime());
                PendingFile file;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.DISPLAY_NAME, safe);
                    v.put(MediaStore.Downloads.MIME_TYPE, mime);
                    v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/StykAnimate");
                    v.put(MediaStore.Downloads.IS_PENDING, 1);
                    Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (uri == null) return "ERR:Could not create the file in Downloads.";
                    file = new PendingFile(getContentResolver().openOutputStream(uri), uri, "Downloads/StykAnimate");
                } else {
                    File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
                    if (dir == null) return "ERR:Storage is unavailable.";
                    File f = new File(dir, safe);
                    file = new PendingFile(new FileOutputStream(f), null, dir.getAbsolutePath());
                }
                synchronized (saves) { saves.put(token, file); }
                return token;
            } catch (Exception e) {
                return "ERR:" + e.getMessage();
            }
        }

        @JavascriptInterface
        public boolean saveChunk(String token, String base64) {
            PendingFile f;
            synchronized (saves) { f = saves.get(token); }
            if (f == null) return false;
            try {
                f.out.write(Base64.decode(base64, Base64.DEFAULT));
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public String saveEnd(String token) {
            PendingFile f;
            synchronized (saves) { f = saves.remove(token); }
            if (f == null) return "ERR:Unknown file.";
            try {
                f.out.close();
                if (f.uri != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.IS_PENDING, 0);
                    getContentResolver().update(f.uri, v, null, null);
                }
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Saved to " + f.where, Toast.LENGTH_SHORT).show());
                return f.where;
            } catch (Exception e) {
                return "ERR:" + e.getMessage();
            }
        }
    }

    private static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] b = new byte[16384];
        int n;
        while ((n = in.read(b)) > 0) buf.write(b, 0, n);
        in.close();
        return buf.toString("UTF-8");
    }
}
