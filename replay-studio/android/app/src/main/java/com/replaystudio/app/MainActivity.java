package com.replaystudio.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

/** Shows the Replay Studio dashboard (served by the app itself on 127.0.0.1:8787) in a WebView. */
public class MainActivity extends Activity {
    private static final String DASHBOARD = "http://127.0.0.1:8787/";
    private static final int REQ_FILE = 10;
    private static final int REQ_PERMS = 11;

    private WebView web;
    private TextView splash;
    private ValueCallback<Uri[]> fileCallback;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean loaded = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        StreamService.start(this);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(getColor(R.color.bg));
        web = new WebView(this);
        web.setVisibility(View.INVISIBLE);
        splash = new TextView(this);
        splash.setText("Starting Replay Studio…\n\n(the first start unpacks the engine and can take ~20 s)");
        splash.setTextColor(Color.WHITE);
        splash.setTextSize(17);
        splash.setGravity(Gravity.CENTER);
        splash.setPadding(48, 48, 48, 48);
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        root.addView(splash, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);

        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(true);
        ws.setMediaPlaybackRequiresUserGesture(true);
        ws.setSupportMultipleWindows(false);
        CookieManager.getInstance().setAcceptCookie(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return openOutside(req.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                web.setVisibility(View.VISIBLE);
                splash.setVisibility(View.GONE);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("video/*");
                try {
                    startActivityForResult(i, REQ_FILE);
                } catch (ActivityNotFoundException e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        askPermissions();
        waitForServer();
    }

    /** Google sign-in, YouTube and Studio links open in the browser/YouTube app; the dashboard stays here.
     *  (Google does not allow signing in inside an app WebView.) */
    private boolean openOutside(Uri uri) {
        String host = uri.getHost();
        if ("127.0.0.1".equals(host) || "localhost".equals(host)) return false;
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException ignored) {
        }
        return true;
    }

    private void waitForServer() {
        new Thread(() -> {
            for (int i = 0; i < 240 && !loaded; i++) {
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(DASHBOARD + "api/health").openConnection();
                    c.setConnectTimeout(1000);
                    c.setReadTimeout(1000);
                    if (c.getResponseCode() == 200) {
                        loaded = true;
                        handler.post(() -> web.loadUrl(DASHBOARD));
                        return;
                    }
                } catch (Exception ignored) {
                }
                try { Thread.sleep(500); } catch (InterruptedException e) { return; }
            }
            handler.post(() -> splash.setText("The streaming engine did not start.\nForce-stop the app and open it again."));
        }).start();
    }

    private void askPermissions() {
        List<String> perms = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= 33) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS);
            perms.add(Manifest.permission.READ_MEDIA_VIDEO);
        } else {
            perms.add(Manifest.permission.READ_EXTERNAL_STORAGE);
        }
        List<String> missing = new ArrayList<>();
        for (String p : perms) if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) missing.add(p);
        if (!missing.isEmpty()) requestPermissions(missing.toArray(new String[0]), REQ_PERMS);
        else askBackgroundExemptions();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        if (code == REQ_PERMS) askBackgroundExemptions();
    }

    /** Ask once to be excluded from battery optimisation; on Xiaomi/Redmi also point to MIUI Autostart. */
    @SuppressLint("BatteryLife")
    private void askBackgroundExemptions() {
        SharedPreferences prefs = getSharedPreferences("setup", MODE_PRIVATE);
        PowerManager pm = getSystemService(PowerManager.class);
        if (!pm.isIgnoringBatteryOptimizations(getPackageName())) {
            try {
                startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        Uri.parse("package:" + getPackageName())));
            } catch (ActivityNotFoundException ignored) {
            }
        }
        boolean xiaomi = Build.MANUFACTURER.equalsIgnoreCase("Xiaomi") || Build.BRAND.equalsIgnoreCase("Redmi")
                || Build.BRAND.equalsIgnoreCase("POCO");
        if (xiaomi && !prefs.getBoolean("miui_hint", false)) {
            prefs.edit().putBoolean("miui_hint", true).apply();
            new AlertDialog.Builder(this)
                    .setTitle("Keep streaming in the background")
                    .setMessage("MIUI stops background apps. Please:\n\n"
                            + "1. Turn ON Autostart for Replay Studio (next screen).\n"
                            + "2. App info → Battery saver → No restrictions.\n"
                            + "3. In Recent apps, lock Replay Studio (pull its card down → lock).\n\n"
                            + "Keep the phone charging and online while streaming.")
                    .setPositiveButton("Open Autostart", (d, w) -> openMiuiAutostart())
                    .setNegativeButton("Later", null)
                    .show();
        }
    }

    private void openMiuiAutostart() {
        Intent i = new Intent().setComponent(new ComponentName("com.miui.securitycenter",
                "com.miui.permcenter.autostart.AutoStartManagementActivity"));
        try {
            startActivity(i);
        } catch (Exception e) {
            startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:" + getPackageName())));
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE && fileCallback != null) {
            Uri[] result = (resultCode == RESULT_OK && data != null && data.getData() != null)
                    ? new Uri[]{data.getData()} : null;
            fileCallback.onReceiveValue(result);
            fileCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Coming back from Chrome after Google sign-in: refresh so the connected channel shows up.
        if (loaded) web.evaluateJavascript("document.dispatchEvent(new Event('visibilitychange'))", null);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else moveTaskToBack(true);  // keep running; Stop is in the dashboard
    }
}
