package com.productvideostudio.ui;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.productvideostudio.analysis.Bitmaps;
import com.productvideostudio.analysis.ImageAnalyzer;
import com.productvideostudio.analysis.UrlMetadata;
import com.productvideostudio.model.Enums;
import com.productvideostudio.model.ImageAnalysis;
import com.productvideostudio.model.Project;
import com.productvideostudio.service.Pipeline;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Collects the product assets. Every field is optional except at least one photo (or a product URL). */
public class EditorActivity extends Activity {
    public static final String EXTRA_PROJECT = "project";
    private static final int PICK_IMAGES = 1, PICK_LOGO = 2, PICK_MUSIC = 3, PICK_VOICE = 4;
    private static final int MAX_IMAGES = 20;
    private static final String[] CTAS = {"Auto", "Shop Now", "Order Today", "Limited Offer", "Buy Now", "Learn More"};
    private static final int[] DURATIONS = {10, 15, 20, 30};

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Runnable saveTask = this::saveNow;
    private ProjectStore store;
    private Project p;

    private LinearLayout imagesRow, swatches, voiceBox;
    private EditText name, description, price, discount, url, voiceScript, hex;
    private Ui.Chips cta, music, voice, look, duration, fps;
    private TextView musicLabel, voiceLabel, logoLabel;
    private ImageView logoView;
    private final Map<String, List<Integer>> palettes = new LinkedHashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ui.styleWindow(this);
        store = new ProjectStore(this);
        p = store.load(getIntent().getStringExtra(EXTRA_PROJECT));
        if (p == null) {
            finish();
            return;
        }

        FrameLayout frame = new FrameLayout(this);
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = Ui.column(this);
        int pad = Ui.dp(this, 20);
        root.setPadding(pad, Ui.dp(this, 24), pad, Ui.dp(this, 110));
        scroll.addView(root);
        frame.addView(scroll);

        root.addView(Ui.title(this, "Your product"));
        root.addView(Ui.text(this, "Add what you have. The director handles the rest: angles, camera moves, transitions, copy, music and grading.", 14, Ui.MUTED), Ui.margins(this, 6));

        // Photos
        root.addView(Ui.heading(this, "Product photos · 1–20"));
        HorizontalScrollView hs = new HorizontalScrollView(this);
        hs.setHorizontalScrollBarEnabled(false);
        imagesRow = Ui.row(this);
        hs.addView(imagesRow);
        root.addView(hs);
        root.addView(Ui.text(this, "Tip: a clean packshot on a plain background gets studio treatment: cut-out, reflection and 3D moves. Tap a photo to remove it.", 12, 0xFF6E6C75), Ui.margins(this, 8));

        // Text
        root.addView(Ui.heading(this, "Name & description"));
        name = Ui.input(this, "Product name", false);
        root.addView(name);
        description = Ui.input(this, "Description, features, benefits (one per line works great)", true);
        root.addView(description, Ui.margins(this, 10));
        LinearLayout priceRow = Ui.row(this);
        price = Ui.input(this, "Price (optional)", false);
        discount = Ui.input(this, "Discount, e.g. 20%", false);
        LinearLayout.LayoutParams half = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        LinearLayout.LayoutParams half2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        half2.leftMargin = Ui.dp(this, 10);
        priceRow.addView(price, half);
        priceRow.addView(discount, half2);
        root.addView(priceRow, Ui.margins(this, 10));
        LinearLayout urlRow = Ui.row(this);
        url = Ui.input(this, "Product URL (optional)", false);
        url.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        urlRow.addView(url, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button fetch = Ui.secondary(this, "Fill in");
        LinearLayout.LayoutParams flp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        flp.leftMargin = Ui.dp(this, 10);
        urlRow.addView(fetch, flp);
        fetch.setOnClickListener(v -> fetchFromUrl());
        root.addView(urlRow, Ui.margins(this, 10));

        root.addView(Ui.heading(this, "Call to action"));
        cta = new Ui.Chips(this, CTAS, indexOf(CTAS, p.cta, 0), this::scheduleSave);
        root.addView(cta.view);

        // Brand
        root.addView(Ui.heading(this, "Brand"));
        LinearLayout logoRow = Ui.row(this);
        logoView = new ImageView(this);
        logoView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        logoView.setBackground(Ui.round(Ui.SURFACE, Ui.dp(this, 12)));
        int ls = Ui.dp(this, 56);
        logoRow.addView(logoView, new LinearLayout.LayoutParams(ls, ls));
        logoLabel = Ui.text(this, "", 14, Ui.TEXT);
        logoLabel.setPadding(Ui.dp(this, 12), 0, 0, 0);
        logoRow.addView(logoLabel, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button logoBtn = Ui.secondary(this, "Choose logo");
        logoBtn.setOnClickListener(v -> {
            if (p.logo != null) {
                store.deleteFile(p, p.logo);
                p.logo = null;
                refreshLogo();
                scheduleSave();
            } else {
                pick("image/*", false, PICK_LOGO);
            }
        });
        logoRow.addView(logoBtn);
        root.addView(logoRow);
        root.addView(Ui.text(this, "Brand colors (tap up to 3, or leave for automatic):", 13, Ui.MUTED), Ui.margins(this, 14));
        HorizontalScrollView sw = new HorizontalScrollView(this);
        sw.setHorizontalScrollBarEnabled(false);
        swatches = Ui.row(this);
        sw.addView(swatches);
        root.addView(sw, Ui.margins(this, 8));
        LinearLayout hexRow = Ui.row(this);
        hex = Ui.input(this, "Hex color, e.g. #1E6BFF", false);
        hexRow.addView(hex, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button addHex = Ui.secondary(this, "Add");
        addHex.setOnClickListener(v -> {
            int c = Ui.parseColor(hex.getText().toString());
            if (c == 0) {
                Toast.makeText(this, "That isn't a color like #FF6A3D", Toast.LENGTH_SHORT).show();
                return;
            }
            if (!p.brandColors.contains(c)) {
                if (p.brandColors.size() >= 3) p.brandColors.remove(0);
                p.brandColors.add(c);
            }
            hex.setText("");
            refreshSwatches();
            scheduleSave();
        });
        hexRow.addView(addHex, flp);
        root.addView(hexRow, Ui.margins(this, 8));

        // Audio
        root.addView(Ui.heading(this, "Music"));
        music = new Ui.Chips(this, new String[]{"Original score", "My track", "No music"},
                Project.MUSIC_FILE.equals(p.musicMode) ? 1 : Project.MUSIC_NONE.equals(p.musicMode) ? 2 : 0, this::onMusicChanged);
        root.addView(music.view);
        musicLabel = Ui.text(this, "", 13, Ui.MUTED);
        root.addView(musicLabel, Ui.margins(this, 6));

        root.addView(Ui.heading(this, "Voice-over"));
        voice = new Ui.Chips(this, new String[]{"Off", "AI voice", "My recording"},
                Project.VOICE_TTS.equals(p.voiceMode) ? 1 : Project.VOICE_FILE.equals(p.voiceMode) ? 2 : 0, this::onVoiceChanged);
        root.addView(voice.view);
        voiceBox = Ui.column(this);
        voiceLabel = Ui.text(this, "", 13, Ui.MUTED);
        voiceBox.addView(voiceLabel, Ui.margins(this, 6));
        voiceScript = Ui.input(this, "Script (optional, we'll write one from your description)", true);
        voiceBox.addView(voiceScript, Ui.margins(this, 8));
        root.addView(voiceBox);

        // Style
        root.addView(Ui.heading(this, "Look"));
        String[] looks = new String[Enums.Look.values().length + 1];
        looks[0] = "Auto";
        for (int i = 0; i < Enums.Look.values().length; i++) looks[i + 1] = Enums.Look.values()[i].label;
        look = new Ui.Chips(this, looks, p.look == null ? 0 : p.look.ordinal() + 1, this::scheduleSave);
        root.addView(look.view);

        root.addView(Ui.heading(this, "Length & frame rate"));
        String[] durLabels = {"10 s", "15 s", "20 s", "30 s"};
        int di = 1;
        for (int i = 0; i < DURATIONS.length; i++) if (DURATIONS[i] == p.durationSec) di = i;
        duration = new Ui.Chips(this, durLabels, di, this::scheduleSave);
        root.addView(duration.view);
        fps = new Ui.Chips(this, new String[]{"30 fps", "60 fps"}, p.fps == 60 ? 1 : 0, this::scheduleSave);
        root.addView(fps.view, Ui.margins(this, 10));
        root.addView(Ui.text(this, "Output: vertical 1080×1920 MP4, H.264, ready for Reels, TikTok, Shorts, Facebook and ads.", 12, 0xFF6E6C75), Ui.margins(this, 10));

        // Sticky action
        Button go = Ui.primary(this, "Direct my video  →");
        FrameLayout.LayoutParams glp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        glp.setMargins(pad, 0, pad, Ui.dp(this, 20));
        frame.addView(go, glp);
        go.setOnClickListener(v -> direct());

        setContentView(frame);
        bind();
    }

    private void bind() {
        name.setText(p.name);
        description.setText(p.description);
        price.setText(p.price);
        discount.setText(p.discount);
        url.setText(p.url);
        voiceScript.setText(p.voiceScript);
        TextWatcher w = new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) {}
            @Override public void afterTextChanged(Editable s) { scheduleSave(); }
        };
        for (EditText e : new EditText[]{name, description, price, discount, url, voiceScript}) e.addTextChangedListener(w);
        refreshImages();
        refreshLogo();
        refreshAudioLabels();
        for (String f : p.images) loadPalette(f);
    }

    // ------------------------------------------------------------------------------------

    private void refreshImages() {
        imagesRow.removeAllViews();
        int size = Ui.dp(this, 96);
        for (String f : new ArrayList<>(p.images)) {
            ImageView iv = new ImageView(this);
            iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
            iv.setBackground(Ui.round(Ui.SURFACE, Ui.dp(this, 14)));
            iv.setClipToOutline(true);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(size, size);
            lp.rightMargin = Ui.dp(this, 10);
            imagesRow.addView(iv, lp);
            File file = new File(store.dir(p), f);
            io.execute(() -> {
                Bitmap b = Bitmaps.decode(file.getAbsolutePath(), 256);
                main.post(() -> iv.setImageBitmap(b));
            });
            iv.setOnClickListener(v -> new AlertDialog.Builder(this)
                    .setTitle("Remove this photo?")
                    .setPositiveButton("Remove", (d, x) -> {
                        p.images.remove(f);
                        p.analyses.removeIf(a -> a.file.equals(f));
                        palettes.remove(f);
                        store.deleteFile(p, f);
                        refreshImages();
                        refreshSwatches();
                        scheduleSave();
                    })
                    .setNegativeButton("Keep", null)
                    .show());
        }
        if (p.images.size() < MAX_IMAGES) {
            TextView add = Ui.text(this, "+\nAdd photos", 13, Ui.TEXT);
            add.setGravity(Gravity.CENTER);
            add.setBackground(Ui.round(Ui.SURFACE_2, Ui.dp(this, 14)));
            add.setOnClickListener(v -> pick("image/*", true, PICK_IMAGES));
            imagesRow.addView(add, new LinearLayout.LayoutParams(size, size));
        }
    }

    private void refreshLogo() {
        if (p.logo == null) {
            logoView.setImageDrawable(null);
            logoLabel.setText("Optional: shown in the outro");
        } else {
            File f = new File(store.dir(p), p.logo);
            io.execute(() -> {
                Bitmap b = Bitmaps.decode(f.getAbsolutePath(), 256);
                main.post(() -> logoView.setImageBitmap(b));
            });
            logoLabel.setText("Logo added · tap Remove to change");
        }
        View parent = (View) logoLabel.getParent();
        Button b = (Button) ((LinearLayout) parent).getChildAt(2);
        b.setText(p.logo == null ? "Choose logo" : "Remove");
    }

    private void loadPalette(String file) {
        File f = new File(store.dir(p), file);
        io.execute(() -> {
            ImageAnalysis a = ImageAnalyzer.analyze(f.getAbsolutePath(), file);
            main.post(() -> {
                palettes.put(file, a.palette);
                refreshSwatches();
            });
        });
    }

    private void refreshSwatches() {
        swatches.removeAllViews();
        List<Integer> colors = new ArrayList<>(p.brandColors);
        for (List<Integer> pal : palettes.values()) {
            for (int c : pal) {
                boolean near = false;
                for (int o : colors) if (distance(o, c) < 40) { near = true; break; }
                if (!near && colors.size() < 14) colors.add(c);
            }
        }
        if (colors.isEmpty()) {
            swatches.addView(Ui.text(this, "Add photos to see their colors", 13, 0xFF6E6C75));
            return;
        }
        int size = Ui.dp(this, 40);
        for (int c : colors) {
            View v = new View(this);
            boolean on = p.brandColors.contains(c);
            android.graphics.drawable.GradientDrawable g = Ui.round(c, size / 2f);
            if (on) g.setStroke(Ui.dp(this, 3), Ui.TEXT);
            else g.setStroke(Ui.dp(this, 1), 0x33FFFFFF);
            v.setBackground(g);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(size, size);
            lp.rightMargin = Ui.dp(this, 10);
            v.setOnClickListener(x -> {
                if (p.brandColors.contains(c)) p.brandColors.remove((Integer) c);
                else {
                    if (p.brandColors.size() >= 3) p.brandColors.remove(0);
                    p.brandColors.add(c);
                }
                refreshSwatches();
                scheduleSave();
            });
            swatches.addView(v, lp);
        }
    }

    private void refreshAudioLabels() {
        switch (music.selected()) {
            case 1: musicLabel.setText(p.musicFile == null ? "Pick a track. Cuts will follow its beat." : "Your track is set. Cuts will follow its beat."); break;
            case 2: musicLabel.setText("Sound effects only."); break;
            default: musicLabel.setText("An original score composed for your product's mood, synced to every cut.");
        }
        int v = voice.selected();
        voiceBox.setVisibility(v == 0 ? View.GONE : View.VISIBLE);
        voiceScript.setVisibility(v == 1 ? View.VISIBLE : View.GONE);
        voiceLabel.setText(v == 1 ? "Narrated with your phone's text-to-speech voice; music ducks under it."
                : p.voiceFile == null ? "Pick a recording." : "Your recording is set; music ducks under it.");
    }

    private void onMusicChanged() {
        if (music.selected() == 1 && p.musicFile == null) pick("audio/*", false, PICK_MUSIC);
        refreshAudioLabels();
        scheduleSave();
    }

    private void onVoiceChanged() {
        if (voice.selected() == 2 && p.voiceFile == null) pick("audio/*", false, PICK_VOICE);
        refreshAudioLabels();
        scheduleSave();
    }

    private void pick(String type, boolean multiple, int code) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(type);
        if (multiple) i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        startActivityForResult(i, code);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) {
            if (requestCode == PICK_MUSIC && p.musicFile == null) music.select(0, false);
            if (requestCode == PICK_VOICE && p.voiceFile == null) voice.select(0, false);
            refreshAudioLabels();
            return;
        }
        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) for (int i = 0; i < clip.getItemCount(); i++) uris.add(clip.getItemAt(i).getUri());
        else if (data.getData() != null) uris.add(data.getData());
        io.execute(() -> {
            List<String> added = new ArrayList<>();
            try {
                for (Uri u : uris) {
                    if (requestCode == PICK_IMAGES && p.images.size() + added.size() >= MAX_IMAGES) break;
                    String prefix = requestCode == PICK_IMAGES ? "img" : requestCode == PICK_LOGO ? "logo" : requestCode == PICK_MUSIC ? "music" : "voice";
                    added.add(store.importUri(this, p, u, prefix));
                }
            } catch (Exception e) {
                main.post(() -> Toast.makeText(this, "Couldn't read that file: " + e.getMessage(), Toast.LENGTH_LONG).show());
            }
            main.post(() -> {
                if (added.isEmpty()) return;
                switch (requestCode) {
                    case PICK_IMAGES:
                        p.images.addAll(added);
                        refreshImages();
                        for (String f : added) loadPalette(f);
                        break;
                    case PICK_LOGO:
                        p.logo = added.get(0);
                        refreshLogo();
                        break;
                    case PICK_MUSIC:
                        store.deleteFile(p, p.musicFile);
                        p.musicFile = added.get(0);
                        break;
                    case PICK_VOICE:
                        store.deleteFile(p, p.voiceFile);
                        p.voiceFile = added.get(0);
                        break;
                    default:
                }
                refreshAudioLabels();
                scheduleSave();
            });
        });
    }

    private void fetchFromUrl() {
        String u = url.getText().toString().trim();
        if (u.isEmpty()) {
            Toast.makeText(this, "Paste your product page link first", Toast.LENGTH_SHORT).show();
            return;
        }
        Toast.makeText(this, "Reading the page…", Toast.LENGTH_SHORT).show();
        io.execute(() -> {
            try {
                UrlMetadata m = UrlMetadata.fetch(u);
                String imageName = null;
                if (p.images.isEmpty() && !m.imageUrl.isEmpty()) {
                    imageName = "img_url_" + System.currentTimeMillis() % 100000 + ".jpg";
                    UrlMetadata.downloadTo(m.imageUrl, new File(store.dir(p), imageName));
                }
                String img = imageName;
                main.post(() -> {
                    if (name.getText().toString().trim().isEmpty()) name.setText(m.title);
                    if (description.getText().toString().trim().isEmpty()) description.setText(m.description);
                    if (img != null) {
                        p.images.add(img);
                        refreshImages();
                        loadPalette(img);
                    }
                    scheduleSave();
                });
            } catch (Exception e) {
                main.post(() -> Toast.makeText(this, "Couldn't read that page", Toast.LENGTH_SHORT).show());
            }
        });
    }

    // ------------------------------------------------------------------------------------

    private void collect() {
        p.name = name.getText().toString();
        p.description = description.getText().toString();
        p.price = price.getText().toString();
        p.discount = discount.getText().toString();
        p.url = url.getText().toString();
        p.cta = cta.selected() == 0 ? "" : CTAS[cta.selected()];
        p.musicMode = music.selected() == 1 && p.musicFile != null ? Project.MUSIC_FILE : music.selected() == 2 ? Project.MUSIC_NONE : Project.MUSIC_AUTO;
        p.voiceMode = voice.selected() == 1 ? Project.VOICE_TTS : voice.selected() == 2 && p.voiceFile != null ? Project.VOICE_FILE : Project.VOICE_OFF;
        p.voiceScript = voiceScript.getText().toString();
        p.look = look.selected() == 0 ? null : Enums.Look.values()[look.selected() - 1];
        p.durationSec = DURATIONS[duration.selected()];
        p.fps = fps.selected() == 1 ? 60 : 30;
    }

    private void scheduleSave() {
        main.removeCallbacks(saveTask);
        main.postDelayed(saveTask, 700);
    }

    private void saveNow() {
        if (p == null) return;
        collect();
        Project snapshot = p;
        io.execute(() -> store.save(snapshot));
    }

    private void direct() {
        collect();
        if (p.images.isEmpty() && p.url.trim().isEmpty()) {
            Toast.makeText(this, "Add at least one product photo", Toast.LENGTH_LONG).show();
            return;
        }
        TextView msg = Ui.text(this, "Getting started…", 16, Ui.TEXT);
        int pad = Ui.dp(this, 24);
        msg.setPadding(pad, pad, pad, pad);
        AlertDialog dialog = new AlertDialog.Builder(this).setView(msg).setCancelable(false).show();
        io.execute(() -> {
            try {
                Pipeline.prepare(this, store, p, text -> main.post(() -> msg.setText(text)));
                main.post(() -> {
                    dialog.dismiss();
                    if (p.images.isEmpty()) {
                        Toast.makeText(this, "Couldn't find a product photo on that page. Please add one.", Toast.LENGTH_LONG).show();
                        return;
                    }
                    startActivity(new Intent(this, StoryboardActivity.class).putExtra(StoryboardActivity.EXTRA_PROJECT, p.id));
                });
            } catch (Exception e) {
                main.post(() -> {
                    dialog.dismiss();
                    new AlertDialog.Builder(this).setTitle("Something went wrong").setMessage(String.valueOf(e.getMessage()))
                            .setPositiveButton("OK", null).show();
                });
            }
        });
    }

    @Override
    protected void onPause() {
        super.onPause();
        main.removeCallbacks(saveTask);
        saveNow();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // The storyboard screen may have changed the seed; keep our copy current.
        if (p != null) {
            Project fresh = store.load(p.id);
            if (fresh != null) {
                p.seed = fresh.seed;
                p.storyboard = fresh.storyboard;
                p.analyses = fresh.analyses;
                p.outputPath = fresh.outputPath;
                p.outputUri = fresh.outputUri;
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        io.shutdown();
    }

    static int indexOf(String[] arr, String v, int fallback) {
        for (int i = 0; i < arr.length; i++) if (arr[i].equalsIgnoreCase(v == null ? "" : v)) return i;
        return fallback;
    }

    static int distance(int a, int b) {
        int dr = ((a >> 16) & 0xFF) - ((b >> 16) & 0xFF), dg = ((a >> 8) & 0xFF) - ((b >> 8) & 0xFF), db = (a & 0xFF) - (b & 0xFF);
        return (int) Math.sqrt(dr * dr + dg * dg + db * db);
    }
}
