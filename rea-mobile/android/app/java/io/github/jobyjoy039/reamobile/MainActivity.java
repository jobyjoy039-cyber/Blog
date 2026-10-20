package io.github.jobyjoy039.reamobile;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.SharedPreferences;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Hosts REA Mobile's web interface.
 *
 * Phone mode: the page lives at REA's own local address (http://127.0.0.1:port). Requests for
 * the interface and docs are answered from the APK's assets; /api/ requests reach REA running
 * on the phone ({@link ReaRuntime}). Keeping the page and the API on one origin avoids the
 * browser's cross-origin and local-network restrictions.
 *
 * Computer mode: the page is the computer's own REA Mobile server, opened directly.
 *
 * Both get window.ReaAndroid for phone features: installed apps, sharing and copying.
 */
public class MainActivity extends Activity {
    private static final int PICK_FILE = 1;
    private static final int MAX_SHARE_CHARS = 100_000;

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences prefs;
    private ReaRuntime runtime;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(isNight() ? Color.parseColor("#111318") : Color.parseColor("#F6F7F9"));
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        applyInsets(root);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        // Computer mode talks to http://<LAN address> from the https asset origin.
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webView.addJavascriptInterface(new Bridge(), "ReaAndroid");
        webView.setWebViewClient(new AssetClient());
        webView.setWebChromeClient(new ChromeClient());
        prefs = getSharedPreferences("rea", MODE_PRIVATE);
        runtime = ReaRuntime.get(this);
        String computer = prefs.getString("computer_base", null);
        if ("computer".equals(prefs.getString("mode", "phone")) && computer != null) openComputer(computer, prefs.getString("computer_token", ""));
        else openPhone("");

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[] {Manifest.permission.POST_NOTIFICATIONS}, 0);
        }
    }

    /** Keep the page clear of the status bar, navigation bar and keyboard (Android 15 draws edge to edge). */
    private void applyInsets(View root) {
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return WindowInsets.CONSUMED;
            }
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        if (Build.VERSION.SDK_INT >= 30 && !isNight()) {
            getWindow().getInsetsController().setSystemBarsAppearance(
                    android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                            | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                    android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                            | android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        }
    }

    private void openPhone(String hash) {
        prefs.edit().putString("mode", "phone").apply();
        webView.loadUrl(runtime.baseUrl() + "/index.html" + hash);
    }

    private void openComputer(String base, String token) {
        prefs.edit().putString("mode", "computer").putString("computer_base", base).putString("computer_token", token).apply();
        webView.loadUrl(base + "/#token=" + Uri.encode(token));
    }

    private boolean isPhonePage(Uri url) {
        return "127.0.0.1".equals(url.getHost()) && url.getPort() == runtime.port();
    }

    private boolean isNight() {
        return Build.VERSION.SDK_INT >= 29
                && (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
    }

    @Override
    public void onBackPressed() {
        webView.evaluateJavascript("window.reaBack ? window.reaBack() : false", handled -> {
            if (!"true".equals(handled)) moveTaskToBack(true);
        });
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        super.onDestroy();
    }

    // ---- Serving the interface from assets/www ----

    private final class AssetClient extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            String path = url.getPath() == null || url.getPath().equals("/") ? "/index.html" : url.getPath();
            // Only the phone page's interface files come from the APK; its /api/ calls go to REA.
            if (!isPhonePage(url) || path.startsWith("/api/")) return null;
            if (path.contains("..")) return notFound();
            try {
                InputStream in = getAssets().open("www" + path);
                String ext = path.substring(path.lastIndexOf('.') + 1).toLowerCase(java.util.Locale.ROOT);
                String mime = mimeType(ext);
                Map<String, String> headers = new HashMap<>();
                headers.put("Cache-Control", "no-cache");
                return new WebResourceResponse(mime, mime.startsWith("text/") || mime.endsWith("javascript") || mime.endsWith("json") ? "utf-8" : null,
                        200, "OK", headers, in);
            } catch (IOException missing) {
                return notFound();
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            String computer = prefs.getString("computer_base", "");
            if (isPhonePage(url) || (!computer.isEmpty() && url.toString().startsWith(computer + "/"))) return false;
            // Links to the web open in the browser, not inside the app.
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, url));
            } catch (ActivityNotFoundException ignored) {
                // no browser installed
            }
            return true;
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
            // The computer is off or on another network: fall back to REA on the phone.
            if (request.isForMainFrame() && !isPhonePage(request.getUrl())) openPhone("#computer-unreachable");
        }

        private WebResourceResponse notFound() {
            return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null,
                    new java.io.ByteArrayInputStream(new byte[0]));
        }

        private String mimeType(String ext) {
            switch (ext) {
                case "js":
                case "mjs":
                    return "text/javascript";
                case "css":
                    return "text/css";
                case "html":
                    return "text/html";
                case "md":
                    return "text/markdown";
                case "json":
                case "webmanifest":
                    return "application/json";
                case "svg":
                    return "image/svg+xml";
                default:
                    String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
                    return mime != null ? mime : "application/octet-stream";
            }
        }
    }

    private final class ChromeClient extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
            if (fileCallback != null) fileCallback.onReceiveValue(null);
            fileCallback = callback;
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE)
                    .setType("*/*");
            try {
                startActivityForResult(intent, PICK_FILE);
            } catch (ActivityNotFoundException e) {
                fileCallback = null;
                return false;
            }
            return true;
        }
    }

    // ---- window.ReaAndroid ----

    private final class Bridge {
        @JavascriptInterface
        public String getConfig() {
            try {
                return new JSONObject()
                        .put("localBase", runtime.baseUrl())
                        .put("localToken", runtime.token())
                        .put("computerBase", prefs.getString("computer_base", ""))
                        .put("computerToken", prefs.getString("computer_token", ""))
                        .toString();
            } catch (org.json.JSONException e) {
                return "{}";
            }
        }

        /** Start REA on the phone if it isn't running; returns its status. */
        @JavascriptInterface
        public String runtimeStatus() {
            String status = runtime.status();
            if (status.equals("not started") || status.equals("stopped")) {
                runOnUiThread(() -> ReaService.start(MainActivity.this));
                return "starting";
            }
            return status;
        }

        /** Stop REA on the phone; the next runtimeStatus() call starts it again. */
        @JavascriptInterface
        public void stopRuntime() {
            runtime.stop();
        }

        /** Switch to REA on the phone. */
        @JavascriptInterface
        public void usePhone() {
            runOnUiThread(() -> openPhone(""));
        }

        /** Switch to a computer running server.mjs, e.g. http://192.168.1.20:8787 with its token. */
        @JavascriptInterface
        public void useComputer(String base, String token) {
            Uri url = Uri.parse(base);
            if (!"http".equals(url.getScheme()) && !"https".equals(url.getScheme())) return;
            runOnUiThread(() -> openComputer(url.getScheme() + "://" + url.getEncodedAuthority(), token));
        }

        @JavascriptInterface
        public String listApps(boolean includeSystem) {
            PackageManager pm = getPackageManager();
            List<JSONObject> apps = new ArrayList<>();
            for (ApplicationInfo info : pm.getInstalledApplications(0)) {
                boolean system = (info.flags & (ApplicationInfo.FLAG_SYSTEM | ApplicationInfo.FLAG_UPDATED_SYSTEM_APP)) != 0;
                if ((system && !includeSystem) || info.packageName.equals(getPackageName()) || info.sourceDir == null) continue;
                try {
                    long size = new File(info.sourceDir).length();
                    int splits = info.splitSourceDirs == null ? 0 : info.splitSourceDirs.length;
                    if (info.splitSourceDirs != null) for (String split : info.splitSourceDirs) size += new File(split).length();
                    PackageInfo pkg = pm.getPackageInfo(info.packageName, 0);
                    apps.add(new JSONObject()
                            .put("label", String.valueOf(info.loadLabel(pm)))
                            .put("pkg", info.packageName)
                            .put("path", info.sourceDir)
                            .put("splits", splits)
                            .put("size", size)
                            .put("version", pkg.versionName == null ? "" : pkg.versionName)
                            .put("system", system));
                } catch (Exception skipped) {
                    // app uninstalled meanwhile
                }
            }
            Collections.sort(apps, (a, b) -> a.optString("label").compareToIgnoreCase(b.optString("label")));
            return new JSONArray(apps).toString();
        }

        /** Send a file (e.g. an installed APK) to the computer's REA server, reporting progress to JS. */
        @JavascriptInterface
        public void uploadFile(String path, String name, String uploadUrl, String token, String callback) {
            new Thread(() -> {
                HttpURLConnection connection = null;
                try {
                    File file = new File(path);
                    connection = (HttpURLConnection) new URL(uploadUrl + "?name=" + URLEncoder.encode(name, "UTF-8")).openConnection();
                    connection.setRequestMethod("POST");
                    connection.setDoOutput(true);
                    connection.setRequestProperty("Authorization", "Bearer " + token);
                    connection.setRequestProperty("Content-Type", "application/octet-stream");
                    connection.setFixedLengthStreamingMode(file.length());
                    byte[] buffer = new byte[256 * 1024];
                    long sent = 0;
                    int lastPercent = -1;
                    try (InputStream in = new FileInputStream(file); OutputStream out = connection.getOutputStream()) {
                        int n;
                        while ((n = in.read(buffer)) > 0) {
                            out.write(buffer, 0, n);
                            sent += n;
                            int percent = (int) (sent * 100 / Math.max(1, file.length()));
                            if (percent != lastPercent) {
                                lastPercent = percent;
                                notifyUpload(callback, new JSONObject().put("progress", percent));
                            }
                        }
                    }
                    InputStream body = connection.getResponseCode() == 200 ? connection.getInputStream() : connection.getErrorStream();
                    JSONObject result = new JSONObject(readAll(body));
                    if (connection.getResponseCode() == 200) notifyUpload(callback, new JSONObject().put("path", result.getString("path")));
                    else notifyUpload(callback, new JSONObject().put("error", result.optString("error", "HTTP " + connection.getResponseCode())));
                } catch (Exception error) {
                    try {
                        notifyUpload(callback, new JSONObject().put("error", String.valueOf(error.getMessage())));
                    } catch (org.json.JSONException ignored) {
                        // cannot happen
                    }
                } finally {
                    if (connection != null) connection.disconnect();
                }
            }, "rea-upload").start();
        }

        @JavascriptInterface
        public void copy(String text) {
            runOnUiThread(() -> {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                clipboard.setPrimaryClip(ClipData.newPlainText("REA output", text));
                Toast.makeText(MainActivity.this, R.string.copied, Toast.LENGTH_SHORT).show();
            });
        }

        @JavascriptInterface
        public void share(String title, String text) {
            // Intents carry at most ~1 MB; very long reports are trimmed.
            String body = text.length() > MAX_SHARE_CHARS
                    ? text.substring(0, MAX_SHARE_CHARS) + "\n\n[trimmed: output was " + text.length() + " characters]"
                    : text;
            Intent send = new Intent(Intent.ACTION_SEND)
                    .setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, title)
                    .putExtra(Intent.EXTRA_TEXT, body);
            runOnUiThread(() -> startActivity(Intent.createChooser(send, title)));
        }
    }

    private void notifyUpload(String callback, JSONObject event) {
        if (!callback.matches("[A-Za-z0-9_]+")) return;
        String script = "window.__reaUpload && window.__reaUpload." + callback + " && window.__reaUpload." + callback + "(" + event + ")";
        runOnUiThread(() -> webView.evaluateJavascript(script, null));
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "{}";
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int n;
        while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
        return out.toString("UTF-8");
    }
}
