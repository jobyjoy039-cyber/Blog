package com.productvideostudio.ui;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.VideoView;

import com.productvideostudio.model.Project;
import com.productvideostudio.service.GallerySaver;
import com.productvideostudio.service.RenderState;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.util.Locale;

/** Render progress, then the finished video with share actions. */
public class RenderActivity extends Activity implements RenderState.Listener {
    public static final String EXTRA_PROJECT = "project";

    private ProjectStore store;
    private String projectId;
    private LinearLayout progressBox, resultBox;
    private ProgressBar bar;
    private TextView stage, percent;
    private VideoView video;
    private Button cancel;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.styleWindow(this);
        store = new ProjectStore(this);
        projectId = getIntent().getStringExtra(EXTRA_PROJECT);

        FrameLayout root = new FrameLayout(this);
        int pad = Ui.dp(this, 24);

        progressBox = Ui.column(this);
        progressBox.setGravity(Gravity.CENTER);
        progressBox.setPadding(pad, pad, pad, pad);
        TextView t = Ui.title(this, "Producing your video");
        t.setGravity(Gravity.CENTER);
        progressBox.addView(t);
        percent = Ui.text(this, "0%", 56, Ui.ACCENT);
        percent.setGravity(Gravity.CENTER);
        progressBox.addView(percent, Ui.margins(this, 24));
        bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(1000);
        bar.setProgressTintList(android.content.res.ColorStateList.valueOf(Ui.ACCENT));
        progressBox.addView(bar, Ui.margins(this, 16));
        stage = Ui.text(this, "", 15, Ui.MUTED);
        stage.setGravity(Gravity.CENTER);
        progressBox.addView(stage, Ui.margins(this, 12));
        TextView hint = Ui.text(this, "You can leave the app. Rendering continues in the background and you'll get a notification.", 13, 0xFF6E6C75);
        hint.setGravity(Gravity.CENTER);
        progressBox.addView(hint, Ui.margins(this, 28));
        cancel = Ui.secondary(this, "Cancel");
        cancel.setOnClickListener(v -> RenderState.get().cancelRequested = true);
        progressBox.addView(cancel, Ui.margins(this, 20));
        root.addView(progressBox, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        resultBox = Ui.column(this);
        resultBox.setPadding(pad, Ui.dp(this, 16), pad, pad);
        video = new VideoView(this);
        FrameLayout videoFrame = new FrameLayout(this);
        videoFrame.addView(video, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.CENTER));
        resultBox.addView(videoFrame, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        Button share = Ui.primary(this, "Share video");
        share.setOnClickListener(v -> share());
        resultBox.addView(share, Ui.margins(this, 14));
        LinearLayout row = Ui.row(this);
        Button caption = Ui.secondary(this, "Copy caption");
        caption.setOnClickListener(v -> {
            Project p = store.load(projectId);
            if (p != null) StoryboardActivity.copyCaption(this, p.caption);
        });
        Button home = Ui.secondary(this, "All projects");
        home.setOnClickListener(v -> startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)));
        LinearLayout.LayoutParams h1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        LinearLayout.LayoutParams h2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        h2.leftMargin = Ui.dp(this, 10);
        row.addView(caption, h1);
        row.addView(home, h2);
        resultBox.addView(row, Ui.margins(this, 10));
        TextView saved = Ui.text(this, "Saved to your gallery in Movies/" + GallerySaver.FOLDER + ".", 12, 0xFF6E6C75);
        saved.setGravity(Gravity.CENTER);
        resultBox.addView(saved, Ui.margins(this, 10));
        resultBox.setVisibility(View.GONE);
        root.addView(resultBox, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
    }

    @Override
    protected void onResume() {
        super.onResume();
        RenderState.get().addListener(this);
    }

    @Override
    protected void onPause() {
        super.onPause();
        RenderState.get().removeListener(this);
        video.pause();
    }

    @Override
    public void onRenderUpdate(RenderState st) {
        boolean mine = projectId != null && projectId.equals(st.projectId);
        if (mine && st.status == RenderState.Status.RUNNING) {
            progressBox.setVisibility(View.VISIBLE);
            resultBox.setVisibility(View.GONE);
            bar.setProgress(Math.round(st.progress * 1000));
            percent.setText(String.format(Locale.ROOT, "%d%%", Math.round(st.progress * 100)));
            stage.setText(st.stage);
            return;
        }
        if (mine && st.status == RenderState.Status.FAILED) {
            percent.setText("⚠");
            stage.setText("Rendering failed: " + st.error);
            cancel.setText("Back");
            cancel.setOnClickListener(v -> finish());
            return;
        }
        if (mine && st.status == RenderState.Status.CANCELLED) {
            finish();
            return;
        }
        showResult();
    }

    private void showResult() {
        Project p = store.load(projectId);
        if (p == null || p.outputPath == null || !new File(p.outputPath).exists()) {
            stage.setText("No video yet.");
            return;
        }
        progressBox.setVisibility(View.GONE);
        resultBox.setVisibility(View.VISIBLE);
        video.setVideoPath(p.outputPath);
        video.setOnPreparedListener(mp -> {
            mp.setLooping(true);
            video.start();
        });
    }

    private void share() {
        Project p = store.load(projectId);
        if (p == null) return;
        if (p.outputUri == null) {
            Toast.makeText(this, "The video couldn't be saved to the gallery, so it can't be shared yet.", Toast.LENGTH_LONG).show();
            return;
        }
        Intent send = new Intent(Intent.ACTION_SEND)
                .setType("video/mp4")
                .putExtra(Intent.EXTRA_STREAM, Uri.parse(p.outputUri))
                .putExtra(Intent.EXTRA_TEXT, p.caption)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(send, "Share your video"));
    }
}
