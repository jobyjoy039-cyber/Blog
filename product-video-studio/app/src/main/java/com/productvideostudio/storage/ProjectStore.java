package com.productvideostudio.storage;

import android.content.ContentResolver;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.util.Log;
import android.webkit.MimeTypeMap;

import com.productvideostudio.model.Project;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Projects live in app storage, one folder each, holding project.json plus copies of every image,
 * logo and audio file, so autosaved drafts survive restarts and gallery clean-ups.
 */
public final class ProjectStore {
    private static final String TAG = "ProjectStore";
    private final File root;

    public ProjectStore(Context ctx) {
        root = new File(ctx.getFilesDir(), "projects");
        //noinspection ResultOfMethodCallIgnored
        root.mkdirs();
    }

    public File dir(Project p) {
        File d = new File(root, p.id);
        //noinspection ResultOfMethodCallIgnored
        d.mkdirs();
        return d;
    }

    public Project create() {
        Project p = new Project();
        p.id = UUID.randomUUID().toString().substring(0, 12);
        p.createdAt = p.updatedAt = System.currentTimeMillis();
        p.seed = System.currentTimeMillis() % 100000;
        save(p);
        return p;
    }

    public synchronized void save(Project p) {
        p.updatedAt = System.currentTimeMillis();
        File d = dir(p);
        File tmp = new File(d, "project.json.tmp");
        try (OutputStream out = new FileOutputStream(tmp)) {
            out.write(p.toJson().toString().getBytes(StandardCharsets.UTF_8));
        } catch (IOException | JSONException e) {
            Log.e(TAG, "save failed", e);
            return;
        }
        File dest = new File(d, "project.json");
        if (!tmp.renameTo(dest)) Log.e(TAG, "rename failed");
    }

    public synchronized Project load(String id) {
        File f = new File(new File(root, id), "project.json");
        if (!f.exists()) return null;
        try {
            String json = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
            return Project.fromJson(new JSONObject(json));
        } catch (IOException | JSONException e) {
            Log.e(TAG, "load failed for " + id, e);
            return null;
        }
    }

    public List<Project> list() {
        List<Project> out = new ArrayList<>();
        File[] dirs = root.listFiles();
        if (dirs != null) {
            for (File d : dirs) {
                Project p = load(d.getName());
                if (p != null) out.add(p);
            }
        }
        out.sort((a, b) -> Long.compare(b.updatedAt, a.updatedAt));
        return out;
    }

    public void delete(Project p) {
        deleteRecursive(new File(root, p.id));
    }

    /** Copies a picked document into the project folder and returns its file name. */
    public String importUri(Context ctx, Project p, Uri uri, String prefix) throws IOException {
        ContentResolver cr = ctx.getContentResolver();
        String ext = extension(ctx, uri);
        String name = prefix + "_" + System.nanoTime() % 1_000_000_000L + ext;
        File dest = new File(dir(p), name);
        try (InputStream in = cr.openInputStream(uri); OutputStream out = new FileOutputStream(dest)) {
            if (in == null) throw new IOException("Cannot open " + uri);
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
        return name;
    }

    public void deleteFile(Project p, String name) {
        if (name == null) return;
        //noinspection ResultOfMethodCallIgnored
        new File(dir(p), name).delete();
    }

    private static String extension(Context ctx, Uri uri) {
        String type = ctx.getContentResolver().getType(uri);
        String ext = type == null ? null : MimeTypeMap.getSingleton().getExtensionFromMimeType(type);
        if (ext == null) {
            try (Cursor c = ctx.getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                if (c != null && c.moveToFirst()) {
                    String n = c.getString(0);
                    int dot = n == null ? -1 : n.lastIndexOf('.');
                    if (dot > 0) ext = n.substring(dot + 1);
                }
            } catch (RuntimeException ignored) {
            }
        }
        return ext == null ? "" : "." + ext.toLowerCase(java.util.Locale.ROOT);
    }

    /** Display name of a picked document (for showing the chosen music file). */
    public static String displayName(Context ctx, Uri uri) {
        try (Cursor c = ctx.getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (RuntimeException ignored) {
        }
        return uri.getLastPathSegment();
    }

    private static void deleteRecursive(File f) {
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) deleteRecursive(k);
        //noinspection ResultOfMethodCallIgnored
        f.delete();
    }
}
