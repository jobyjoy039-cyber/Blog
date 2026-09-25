package com.productvideostudio.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.model.Enums;
import com.productvideostudio.model.Project;
import com.productvideostudio.model.Storyboard;
import com.productvideostudio.service.Pipeline;
import com.productvideostudio.service.RenderService;
import com.productvideostudio.service.RenderState;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Shows the director's plan, scene by scene, before rendering. */
public class StoryboardActivity extends Activity {
    public static final String EXTRA_PROJECT = "project";

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private ProjectStore store;
    private Project p;
    private LinearLayout content;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.styleWindow(this);
        store = new ProjectStore(this);
        p = store.load(getIntent().getStringExtra(EXTRA_PROJECT));
        if (p == null || p.storyboard == null) {
            finish();
            return;
        }
        FrameLayout frame = new FrameLayout(this);
        ScrollView scroll = new ScrollView(this);
        content = Ui.column(this);
        int pad = Ui.dp(this, 20);
        content.setPadding(pad, Ui.dp(this, 24), pad, Ui.dp(this, 170));
        scroll.addView(content);
        frame.addView(scroll);

        LinearLayout actions = Ui.column(this);
        actions.setPadding(pad, Ui.dp(this, 12), pad, Ui.dp(this, 20));
        actions.setBackgroundColor(0xF00E0E11);
        Button render = Ui.primary(this, "Render video");
        render.setOnClickListener(v -> startRender());
        Button shuffle = Ui.secondary(this, "↻  Try another direction");
        shuffle.setOnClickListener(v -> reshuffle());
        actions.addView(shuffle, Ui.matchWrap());
        actions.addView(render, Ui.margins(this, 10));
        frame.addView(actions, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM));
        setContentView(frame);
        show();
    }

    private void show() {
        content.removeAllViews();
        Storyboard b = p.storyboard;
        content.addView(Ui.title(this, "Director's cut"));
        content.addView(Ui.text(this, "Here is the plan for " + p.displayName() + ". Render it as is, or ask for another direction.", 14, Ui.MUTED), Ui.margins(this, 6));

        LinearLayout pills = Ui.row(this);
        for (String s : new String[]{b.mood.label, b.look.label + " look", b.bpm + " BPM",
                String.format(Locale.ROOT, "%.0f s · %d fps", b.totalSec, b.fps)}) {
            TextView t = Ui.text(this, s, 13, Ui.TEXT);
            t.setBackground(Ui.round(Ui.SURFACE_2, Ui.dp(this, 14)));
            t.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 12), Ui.dp(this, 6));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = Ui.dp(this, 8);
            pills.addView(t, lp);
        }
        android.widget.HorizontalScrollView hs = new android.widget.HorizontalScrollView(this);
        hs.setHorizontalScrollBarEnabled(false);
        hs.addView(pills);
        content.addView(hs, Ui.margins(this, 16));

        if (!b.notes.isEmpty()) {
            content.addView(Ui.heading(this, "What the director noticed"));
            StringBuilder sb = new StringBuilder();
            for (String n : b.notes) sb.append("• ").append(n).append('\n');
            content.addView(Ui.text(this, sb.toString().trim(), 14, Ui.TEXT));
        }

        content.addView(Ui.heading(this, "Scenes"));
        for (int i = 0; i < b.scenes.size(); i++) content.addView(sceneRow(i, b.scenes.get(i)), Ui.margins(this, i == 0 ? 0 : 10));

        if (!b.voice.isEmpty() && Project.VOICE_TTS.equals(p.voiceMode)) {
            content.addView(Ui.heading(this, "Voice-over script"));
            StringBuilder sb = new StringBuilder();
            for (Storyboard.VoiceLine v : b.voice) sb.append(String.format(Locale.ROOT, "%.1fs  ", v.time)).append(v.text).append('\n');
            content.addView(Ui.text(this, sb.toString().trim(), 14, Ui.TEXT));
        }

        content.addView(Ui.heading(this, "Post caption"));
        TextView cap = Ui.text(this, p.caption == null ? "" : p.caption, 14, Ui.TEXT);
        cap.setTextIsSelectable(true);
        content.addView(Ui.card(this, cap));
        Button copy = Ui.secondary(this, "Copy caption");
        copy.setOnClickListener(v -> copyCaption(this, p.caption));
        content.addView(copy, Ui.margins(this, 8));
    }

    private LinearLayout sceneRow(int i, Storyboard.Scene sc) {
        LinearLayout row = Ui.row(this);
        row.setBackground(Ui.round(Ui.SURFACE, Ui.dp(this, 16)));
        int pad = Ui.dp(this, 12);
        row.setPadding(pad, pad, pad, pad);
        row.setGravity(Gravity.TOP);

        ImageView thumb = new ImageView(this);
        thumb.setScaleType(ImageView.ScaleType.CENTER_CROP);
        thumb.setBackground(Ui.round(Ui.SURFACE_2, Ui.dp(this, 10)));
        thumb.setClipToOutline(true);
        row.addView(thumb, new LinearLayout.LayoutParams(Ui.dp(this, 54), Ui.dp(this, 96)));
        if (sc.image < p.images.size()) {
            File f = new File(store.dir(p), p.images.get(sc.image));
            float[] crop = sc.crop.clone();
            io.execute(() -> {
                Bitmap bmp = Bitmaps.decodeRegion(f.getAbsolutePath(), crop, 240);
                main.post(() -> thumb.setImageBitmap(bmp));
            });
        }

        LinearLayout col = Ui.column(this);
        col.setPadding(Ui.dp(this, 14), 0, 0, 0);
        TextView head = Ui.text(this, String.format(Locale.ROOT, "%02d  %s", i + 1, sc.type.label), 16, Ui.TEXT);
        head.setTypeface(Typeface.DEFAULT_BOLD);
        col.addView(head);
        col.addView(Ui.text(this, String.format(Locale.ROOT, "%.1f–%.1f s", sc.start, sc.end()), 12, Ui.MUTED));
        List<String> fx = new ArrayList<>();
        for (Enums.Effect e : sc.effects) fx.add(e.label);
        String camera = sc.angle.label + " · " + sc.movement.label;
        col.addView(Ui.text(this, camera, 14, Ui.TEXT), Ui.margins(this, 6));
        if (!fx.isEmpty()) col.addView(Ui.text(this, String.join(", ", fx), 13, Ui.MUTED));
        if (i < p.storyboard.scenes.size() - 1 && sc.transition != Enums.TransitionType.CUT) {
            col.addView(Ui.text(this, "→ " + sc.transition.label + " transition", 13, Ui.ACCENT), Ui.margins(this, 4));
        }
        for (Storyboard.TextItem t : sc.texts) {
            TextView tv = Ui.text(this, "“" + t.text + "”", 13, 0xFFD9D6CF);
            tv.setTypeface(Typeface.create(Typeface.DEFAULT, Typeface.ITALIC));
            col.addView(tv, Ui.margins(this, 4));
        }
        row.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return row;
    }

    private void reshuffle() {
        p.seed = p.seed * 31 + 7;
        TextView msg = Ui.text(this, "Rethinking…", 16, Ui.TEXT);
        int pad = Ui.dp(this, 24);
        msg.setPadding(pad, pad, pad, pad);
        AlertDialog d = new AlertDialog.Builder(this).setView(msg).setCancelable(false).show();
        io.execute(() -> {
            Pipeline.prepare(this, store, p, t -> main.post(() -> msg.setText(t)));
            main.post(() -> {
                d.dismiss();
                show();
            });
        });
    }

    private void startRender() {
        if (RenderState.get().isRunning() && !p.id.equals(RenderState.get().projectId)) {
            Toast.makeText(this, "Another video is rendering. It'll be done soon.", Toast.LENGTH_LONG).show();
            return;
        }
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 7);
        }
        if (Build.VERSION.SDK_INT < 29 && checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, 8);
        }
        RenderService.start(this, p.id);
        startActivity(new Intent(this, RenderActivity.class).putExtra(RenderActivity.EXTRA_PROJECT, p.id));
    }

    static void copyCaption(Activity a, String caption) {
        ClipboardManager cm = (ClipboardManager) a.getSystemService(CLIPBOARD_SERVICE);
        if (cm != null && caption != null) {
            cm.setPrimaryClip(ClipData.newPlainText("caption", caption));
            Toast.makeText(a, "Caption copied", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdown();
    }
}
