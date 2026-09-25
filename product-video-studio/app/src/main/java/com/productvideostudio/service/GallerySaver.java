package com.productvideostudio.service;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Publishes a finished video to the phone's gallery (Movies/Product Video Studio). */
public final class GallerySaver {
    public static final String FOLDER = "Product Video Studio";

    private GallerySaver() {}

    /** Returns a content:// URI that other apps can open and share. */
    public static Uri save(Context ctx, File video, String displayName) throws IOException {
        ContentResolver cr = ctx.getContentResolver();
        String name = displayName.replaceAll("[^\\p{L}\\p{N} _-]", "").trim();
        if (name.isEmpty()) name = "product-video";
        name = name + " " + System.currentTimeMillis() / 1000 + ".mp4";

        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Video.Media.DISPLAY_NAME, name);
            v.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");
            v.put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/" + FOLDER);
            v.put(MediaStore.Video.Media.IS_PENDING, 1);
            Uri uri = cr.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new IOException("MediaStore insert failed");
            try (OutputStream out = cr.openOutputStream(uri); InputStream in = new FileInputStream(video)) {
                if (out == null) throw new IOException("Cannot write to gallery");
                copy(in, out);
            }
            v.clear();
            v.put(MediaStore.Video.Media.IS_PENDING, 0);
            cr.update(uri, v, null, null);
            return uri;
        }

        File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES), FOLDER);
        //noinspection ResultOfMethodCallIgnored
        dir.mkdirs();
        File dest = new File(dir, name);
        try (InputStream in = new FileInputStream(video); OutputStream out = new FileOutputStream(dest)) {
            copy(in, out);
        }
        CountDownLatch latch = new CountDownLatch(1);
        final Uri[] result = new Uri[1];
        MediaScannerConnection.scanFile(ctx, new String[]{dest.getAbsolutePath()}, new String[]{"video/mp4"},
                (path, uri) -> { result[0] = uri; latch.countDown(); });
        try {
            latch.await(10, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        if (result[0] == null) throw new IOException("Gallery scan failed");
        return result[0];
    }

    private static void copy(InputStream in, OutputStream out) throws IOException {
        byte[] buf = new byte[1 << 16];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
    }
}
