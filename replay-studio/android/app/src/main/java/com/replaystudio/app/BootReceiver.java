package com.replaystudio.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Restarts the engine after a reboot or app update so a live stream resumes into the same broadcast.
 *  A stream you stopped stays stopped: the stop is stored in the app's database. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String a = intent.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(a) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)) {
            StreamService.start(context);
        }
    }
}
