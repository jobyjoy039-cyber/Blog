package io.github.jobyjoy039.reamobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;

/**
 * Keeps REA running while the app is in the background, so a long analysis
 * finishes even if you switch apps. Shows an ongoing notification with a Stop action.
 */
public class ReaService extends Service {
    private static final String CHANNEL = "rea";
    private static final int NOTIFICATION_ID = 1;
    private static final String ACTION_STOP = "io.github.jobyjoy039.reamobile.STOP";

    static void start(Context context) {
        Intent intent = new Intent(context, ReaService.class);
        if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent);
        else context.startService(intent);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            ReaRuntime.get(this).stop();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        showNotification(getString(R.string.notification_preparing));
        Thread worker = new Thread(() -> {
            ReaRuntime runtime = ReaRuntime.get(this);
            runtime.start();
            String status = runtime.status();
            showNotification("running".equals(status) ? getString(R.string.notification_running) : status);
        }, "rea-start");
        worker.start();
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        ReaRuntime.get(this).stop();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void showNotification(String text) {
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(new NotificationChannel(
                    CHANNEL, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW));
        }
        int immutable = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class), immutable | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, ReaService.class).setAction(ACTION_STOP), immutable | PendingIntent.FLAG_UPDATE_CURRENT);

        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        Notification notification = builder
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(getString(R.string.app_name))
                .setContentText(text)
                .setContentIntent(open)
                .setOngoing(true)
                .addAction(new Notification.Action.Builder(null, getString(R.string.notification_stop), stop).build())
                .build();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }
}
