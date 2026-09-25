package com.productvideostudio.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import com.productvideostudio.model.Project;
import com.productvideostudio.render.VideoRenderer;
import com.productvideostudio.storage.ProjectStore;
import com.productvideostudio.ui.RenderActivity;

import java.io.File;
import java.util.concurrent.CancellationException;

/**
 * Renders in the background as a foreground service, so the user can leave the app while the
 * video is produced. Progress is shown in a notification and published through {@link RenderState}.
 */
public class RenderService extends Service {
    private static final String TAG = "RenderService";
    public static final String EXTRA_PROJECT = "project";
    private static final String CHANNEL = "render";
    private static final int NOTIFY_ID = 42;

    private PowerManager.WakeLock wakeLock;

    public static void start(Context ctx, String projectId) {
        RenderState st = RenderState.get();
        if (st.isRunning()) return;
        st.projectId = projectId;
        st.cancelRequested = false;
        st.error = null;
        st.update(RenderState.Status.RUNNING, "Starting…", 0f);
        Intent i = new Intent(ctx, RenderService.class).putExtra(EXTRA_PROJECT, projectId);
        if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i);
        else ctx.startService(i);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String id = intent == null ? null : intent.getStringExtra(EXTRA_PROJECT);
        createChannel();
        Notification n = notification("Preparing your video…", 0, true, id);
        if (Build.VERSION.SDK_INT >= 29) startForeground(NOTIFY_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        else startForeground(NOTIFY_ID, n);
        if (id == null) {
            stopSelf();
            return START_NOT_STICKY;
        }
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "pvs:render");
        wakeLock.acquire(30 * 60 * 1000L);
        new Thread(() -> run(id), "render").start();
        return START_NOT_STICKY;
    }

    private void run(String id) {
        RenderState st = RenderState.get();
        ProjectStore store = new ProjectStore(this);
        Project p = store.load(id);
        NotificationManager nm = getSystemService(NotificationManager.class);
        try {
            if (p == null) throw new IllegalStateException("Project not found");
            File out = new File(store.dir(p), "video.mp4");
            final long[] lastNotify = {0};
            VideoRenderer.render(this, p, store.dir(p), out, new VideoRenderer.Listener() {
                @Override
                public void onProgress(String stage, float fraction) {
                    st.update(RenderState.Status.RUNNING, stage, fraction * 0.97f);
                    long now = System.currentTimeMillis();
                    if (now - lastNotify[0] > 700) {
                        lastNotify[0] = now;
                        nm.notify(NOTIFY_ID, notification(stage, Math.round(fraction * 100), false, id));
                    }
                }

                @Override
                public boolean isCancelled() {
                    return st.cancelRequested;
                }
            });
            st.update(RenderState.Status.RUNNING, "Saving to your gallery…", 0.98f);
            p.outputPath = out.getAbsolutePath();
            try {
                Uri uri = GallerySaver.save(this, out, p.displayName());
                p.outputUri = uri.toString();
            } catch (Exception e) {
                Log.w(TAG, "gallery save failed", e);
                p.outputUri = null;
            }
            store.save(p);
            st.update(RenderState.Status.DONE, "Your video is ready", 1f);
            nm.notify(NOTIFY_ID + 1, done(p));
        } catch (CancellationException e) {
            st.update(RenderState.Status.CANCELLED, "Cancelled", 0f);
        } catch (Throwable t) {
            Log.e(TAG, "render failed", t);
            st.error = t.getClass().getSimpleName() + ": " + t.getMessage();
            st.update(RenderState.Status.FAILED, "Rendering failed", 0f);
        } finally {
            if (wakeLock != null && wakeLock.isHeld()) wakeLock.release();
            stopForeground(true);
            stopSelf();
        }
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Video rendering", NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Progress while your product video is produced");
            nm.createNotificationChannel(ch);
        }
    }

    private PendingIntent openRender(String id) {
        Intent i = new Intent(this, RenderActivity.class).putExtra(RenderActivity.EXTRA_PROJECT, id)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(this, 1, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification notification(String text, int percent, boolean indeterminate, String id) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle("Creating your product video")
                .setContentText(text)
                .setOnlyAlertOnce(true)
                .setOngoing(true)
                .setProgress(100, percent, indeterminate);
        if (id != null) b.setContentIntent(openRender(id));
        return b.build();
    }

    private Notification done(Project p) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return b.setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle(p.displayName() + " is ready")
                .setContentText("Tap to watch and share")
                .setAutoCancel(true)
                .setContentIntent(openRender(p.id))
                .build();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
