package com.replaystudio.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import org.json.JSONObject;

/**
 * Foreground service that owns the streaming engine: the embedded Python API server + stream worker and the
 * FFmpeg process they start. It keeps the CPU (wake lock) and Wi-Fi (Wi-Fi lock) awake so the stream keeps
 * running with the screen off, the app closed, or the phone locked.
 */
public class StreamService extends Service {
    static final String CHANNEL = "stream";
    static final int NOTIFICATION_ID = 1;
    private static final String TAG = "ReplayStudio";
    static volatile boolean engineStarted = false;

    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private String lastText = "";

    public static void start(Context ctx) {
        Intent i = new Intent(ctx, StreamService.class);
        if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i); else ctx.startService(i);
    }

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Stream status", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Shows whether your Replay Studio stream is live");
            nm.createNotificationChannel(ch);
        }
        Notification n = build("Starting streaming engine…");
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIFICATION_ID, n);
        }
        PowerManager pm = getSystemService(PowerManager.class);
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ReplayStudio:stream");
        wakeLock.setReferenceCounted(false);
        wakeLock.acquire();
        WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        if (wm != null) {
            wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "ReplayStudio:wifi");
            wifiLock.setReferenceCounted(false);
            wifiLock.acquire();
        }
        new Thread(this::startEngine, "engine-start").start();
        handler.postDelayed(this::refreshNotification, 5000);
    }

    private synchronized void startEngine() {
        if (engineStarted) return;
        try {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
            String movies = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES).getAbsolutePath();
            Python.getInstance().getModule("replay_studio.android_app").callAttr("start",
                    getFilesDir().getAbsolutePath(), getApplicationInfo().nativeLibraryDir, movies);
            engineStarted = true;
        } catch (Throwable t) {
            Log.e(TAG, "Engine failed to start", t);
            update("Engine failed to start: " + t.getMessage());
        }
    }

    private void refreshNotification() {
        new Thread(() -> {
            try {
                if (engineStarted) {
                    PyObject r = Python.getInstance().getModule("replay_studio.android_app").callAttr("status");
                    update(new JSONObject(r.toString()).optString("text", ""));
                }
            } catch (Throwable t) {
                Log.w(TAG, "status failed", t);
            }
        }).start();
        handler.postDelayed(this::refreshNotification, 15000);
    }

    private void update(String text) {
        if (text.equals(lastText)) return;
        lastText = text;
        getSystemService(NotificationManager.class).notify(NOTIFICATION_ID, build(text));
    }

    private Notification build(String text) {
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        return b.setContentTitle("Replay Studio")
                .setContentText(text)
                .setSmallIcon(R.drawable.ic_loop)
                .setContentIntent(pi)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;  // Android restarts the service (and the engine) if it is ever killed
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
        if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
