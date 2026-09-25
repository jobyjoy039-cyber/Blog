package com.productvideostudio.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.text.format.DateUtils;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.model.Project;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Home: start a new video or reopen an autosaved project. */
public class MainActivity extends Activity {
    public static final String EXTRA_SELF_TEST = "selftest";

    private ProjectStore store;
    private LinearLayout list;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.styleWindow(this);
        store = new ProjectStore(this);

        if (getIntent().getBooleanExtra(EXTRA_SELF_TEST, false)) {
            SelfTest.start(this, getIntent());
        }

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root = Ui.column(this);
        int pad = Ui.dp(this, 20);
        root.setPadding(pad, Ui.dp(this, 28), pad, pad);
        scroll.addView(root);

        root.addView(Ui.title(this, "Product Video Studio"));
        TextView sub = Ui.text(this, "Add product photos. Get a finished, publish-ready video for Reels, TikTok, Shorts and ads.", 15, Ui.MUTED);
        root.addView(sub, Ui.margins(this, 6));

        Button create = Ui.primary(this, "+  New product video");
        create.setOnClickListener(v -> {
            Project p = store.create();
            open(p);
        });
        root.addView(create, Ui.margins(this, 24));

        root.addView(Ui.heading(this, "Your projects"));
        list = Ui.column(this);
        root.addView(list, Ui.matchWrap());
        setContentView(scroll);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh();
    }

    private void refresh() {
        io.execute(() -> {
            List<Project> projects = store.list();
            runOnUiThread(() -> show(projects));
        });
    }

    private void show(List<Project> projects) {
        list.removeAllViews();
        if (projects.isEmpty()) {
            TextView empty = Ui.text(this, "No projects yet. Your drafts are saved automatically.", 14, Ui.MUTED);
            list.addView(empty);
            return;
        }
        for (Project p : projects) {
            LinearLayout row = Ui.row(this);
            row.setBackground(Ui.round(Ui.SURFACE, Ui.dp(this, 16)));
            int pad = Ui.dp(this, 12);
            row.setPadding(pad, pad, pad, pad);

            ImageView thumb = new ImageView(this);
            thumb.setScaleType(ImageView.ScaleType.CENTER_CROP);
            thumb.setBackground(Ui.round(Ui.SURFACE_2, Ui.dp(this, 10)));
            thumb.setClipToOutline(true);
            int size = Ui.dp(this, 64);
            row.addView(thumb, new LinearLayout.LayoutParams(size, size));
            if (!p.images.isEmpty()) {
                File f = new File(store.dir(p), p.images.get(0));
                io.execute(() -> {
                    Bitmap b = Bitmaps.decode(f.getAbsolutePath(), 192);
                    runOnUiThread(() -> thumb.setImageBitmap(b));
                });
            }

            LinearLayout texts = Ui.column(this);
            texts.setPadding(Ui.dp(this, 14), 0, 0, 0);
            TextView name = Ui.text(this, p.displayName(), 17, Ui.TEXT);
            name.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
            texts.addView(name);
            String status = p.outputPath != null && new File(p.outputPath).exists()
                    ? "Video ready · " + p.durationSec + " s"
                    : p.images.isEmpty() ? "Draft · no photos yet" : "Draft · " + p.images.size() + " photo" + (p.images.size() == 1 ? "" : "s");
            texts.addView(Ui.text(this, status, 13, Ui.MUTED));
            texts.addView(Ui.text(this, DateUtils.getRelativeTimeSpanString(p.updatedAt).toString(), 12, 0xFF6E6C75));
            row.addView(texts, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            TextView chevron = Ui.text(this, "›", 28, Ui.MUTED);
            chevron.setGravity(Gravity.CENTER);
            row.addView(chevron);

            row.setOnClickListener(v -> open(p));
            row.setOnLongClickListener(v -> {
                new AlertDialog.Builder(this)
                        .setTitle("Delete “" + p.displayName() + "”?")
                        .setMessage("The project and its copies of your photos will be removed. Videos saved to your gallery stay.")
                        .setPositiveButton("Delete", (d, w) -> {
                            store.delete(p);
                            refresh();
                        })
                        .setNegativeButton("Cancel", null)
                        .show();
                return true;
            });
            list.addView(row, Ui.margins(this, 10));
        }
    }

    private void open(Project p) {
        startActivity(new Intent(this, EditorActivity.class).putExtra(EditorActivity.EXTRA_PROJECT, p.id));
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdown();
    }
}
