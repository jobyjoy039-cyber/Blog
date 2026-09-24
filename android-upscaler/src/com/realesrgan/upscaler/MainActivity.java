package com.realesrgan.upscaler;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Constructor;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends Activity {

    private static final int REQ_PICK = 1;
    private static final int REQ_WRITE_PERM = 2;

    /** Largest output we allow, to keep the bitmap (4 bytes/pixel) within memory. */
    private static final long MAX_OUTPUT_PIXELS = 32_000_000L;
    private static final int TILE = 192;
    private static final int TILE_PAD = 10;
    private static final int PREVIEW_MAX = 2048;

    private static final String[] MODEL_FILES = {"realesr-general-x4v3.onnx", "realesr-animevideov3.onnx"};

    private final Handler ui = new Handler(Looper.getMainLooper());

    private ImageView preview;
    private ImageView cropBefore, cropAfter;
    private LinearLayout cropRow;
    private TextView info, status;
    private ProgressBar progress;
    private Button pickBtn, runBtn, cancelBtn, saveBtn, shareBtn;
    private RadioGroup modelGroup, scaleGroup;

    private Uri sourceUri;
    private String sourceName = "image";
    private Bitmap input, inputPreview;
    private Bitmap result, resultPreview;
    private int resultScale;
    private Uri savedUri;
    private boolean shareAfterSave;

    private Upscaler upscaler;
    private int upscalerModel = -1;
    private volatile boolean cancelled;
    private boolean running;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        handleIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent != null && Intent.ACTION_SEND.equals(intent.getAction())) {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null && !running) loadImage(uri);
        }
    }

    // ---------------------------------------------------------------- UI

    private int dp(float v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private TextView label(String text, float sizeSp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(sizeSp);
        t.setTextColor(0xFF1B2233);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        return b;
    }

    private LinearLayout.LayoutParams lp(int w, int h, float weight) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(w, h, weight);
        p.topMargin = dp(6);
        return p;
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xFFF4F6FA);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(12), dp(16), dp(24));
        scroll.addView(root);

        TextView intro = label("Upscale photos and drawings 4x with Real-ESRGAN, fully on your phone. "
                + "No internet needed.", 14, false);
        intro.setTextColor(0xFF545B6B);
        root.addView(intro);

        pickBtn = button("Choose image");
        root.addView(pickBtn, lp(-1, -2, 0));
        pickBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.setType("image/*");
                i.addCategory(Intent.CATEGORY_OPENABLE);
                startActivityForResult(Intent.createChooser(i, "Choose image"), REQ_PICK);
            }
        });

        preview = new ImageView(this);
        preview.setAdjustViewBounds(true);
        preview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xFFE3E7EF);
        bg.setCornerRadius(dp(8));
        preview.setBackground(bg);
        preview.setMinimumHeight(dp(180));
        root.addView(preview, lp(-1, -2, 0));
        // Press and hold the result to compare with the original.
        preview.setOnTouchListener(new View.OnTouchListener() {
            @Override
            public boolean onTouch(View v, MotionEvent e) {
                if (resultPreview == null || inputPreview == null) return false;
                int a = e.getActionMasked();
                if (a == MotionEvent.ACTION_DOWN) {
                    preview.setImageBitmap(inputPreview);
                } else if (a == MotionEvent.ACTION_UP || a == MotionEvent.ACTION_CANCEL) {
                    preview.setImageBitmap(resultPreview);
                }
                return true;
            }
        });

        info = label("No image selected", 13, false);
        info.setTextColor(0xFF545B6B);
        root.addView(info, lp(-1, -2, 0));

        cropRow = new LinearLayout(this);
        cropRow.setOrientation(LinearLayout.VERTICAL);
        cropRow.setVisibility(View.GONE);
        root.addView(cropRow, lp(-1, -2, 0));
        cropRow.addView(label("Detail at 100% (before | after)", 13, true));
        LinearLayout crops = new LinearLayout(this);
        crops.setOrientation(LinearLayout.HORIZONTAL);
        cropRow.addView(crops, lp(-1, -2, 0));
        cropBefore = new ImageView(this);
        cropAfter = new ImageView(this);
        for (ImageView iv : new ImageView[]{cropBefore, cropAfter}) {
            iv.setAdjustViewBounds(true);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, -2, 1);
            p.setMargins(dp(2), 0, dp(2), 0);
            crops.addView(iv, p);
        }

        root.addView(label("Model", 15, true), lp(-1, -2, 0));
        modelGroup = new RadioGroup(this);
        RadioButton m0 = new RadioButton(this);
        m0.setText("Photo / general (realesr-general-x4v3)");
        m0.setId(View.generateViewId());
        RadioButton m1 = new RadioButton(this);
        m1.setText("Anime / illustration (realesr-animevideov3, faster)");
        m1.setId(View.generateViewId());
        modelGroup.addView(m0);
        modelGroup.addView(m1);
        modelGroup.check(m0.getId());
        root.addView(modelGroup);

        root.addView(label("Output size", 15, true), lp(-1, -2, 0));
        scaleGroup = new RadioGroup(this);
        scaleGroup.setOrientation(RadioGroup.HORIZONTAL);
        RadioButton s4 = new RadioButton(this);
        s4.setText("4x");
        s4.setId(View.generateViewId());
        RadioButton s2 = new RadioButton(this);
        s2.setText("2x");
        s2.setId(View.generateViewId());
        scaleGroup.addView(s4);
        scaleGroup.addView(s2);
        scaleGroup.check(s4.getId());
        scaleGroup.setOnCheckedChangeListener(new RadioGroup.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(RadioGroup group, int checkedId) {
                updateInfo();
            }
        });
        root.addView(scaleGroup);

        LinearLayout runRow = new LinearLayout(this);
        runRow.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(runRow, lp(-1, -2, 0));
        runBtn = button("Upscale");
        cancelBtn = button("Cancel");
        runRow.addView(runBtn, new LinearLayout.LayoutParams(0, -2, 2));
        runRow.addView(cancelBtn, new LinearLayout.LayoutParams(0, -2, 1));
        runBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startUpscale();
            }
        });
        cancelBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                cancelled = true;
                status.setText("Cancelling…");
            }
        });

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        root.addView(progress, lp(-1, -2, 0));
        status = label("", 13, false);
        root.addView(status, lp(-1, -2, 0));

        LinearLayout outRow = new LinearLayout(this);
        outRow.setOrientation(LinearLayout.HORIZONTAL);
        root.addView(outRow, lp(-1, -2, 0));
        saveBtn = button("Save to gallery");
        shareBtn = button("Share");
        outRow.addView(saveBtn, new LinearLayout.LayoutParams(0, -2, 1));
        outRow.addView(shareBtn, new LinearLayout.LayoutParams(0, -2, 1));
        saveBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                shareAfterSave = false;
                save();
            }
        });
        shareBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (savedUri != null) {
                    share(savedUri);
                } else {
                    shareAfterSave = true;
                    save();
                }
            }
        });

        TextView credit = label("Models: Real-ESRGAN by Xintao Wang et al. (BSD-3-Clause). "
                + "Runs with ONNX Runtime.", 11, false);
        credit.setTextColor(0xFF8A90A0);
        LinearLayout.LayoutParams cp = lp(-1, -2, 0);
        cp.topMargin = dp(20);
        root.addView(credit, cp);

        setContentView(scroll);
        refreshButtons();
    }

    private void refreshButtons() {
        pickBtn.setEnabled(!running);
        runBtn.setEnabled(!running && input != null);
        cancelBtn.setEnabled(running);
        modelGroup.setEnabled(!running);
        for (int i = 0; i < modelGroup.getChildCount(); i++) modelGroup.getChildAt(i).setEnabled(!running);
        for (int i = 0; i < scaleGroup.getChildCount(); i++) scaleGroup.getChildAt(i).setEnabled(!running);
        saveBtn.setEnabled(!running && result != null);
        shareBtn.setEnabled(!running && result != null);
        progress.setVisibility(running ? View.VISIBLE : View.INVISIBLE);
    }

    private int selectedModel() {
        return modelGroup.indexOfChild(modelGroup.findViewById(modelGroup.getCheckedRadioButtonId()));
    }

    private int selectedScale() {
        return scaleGroup.indexOfChild(scaleGroup.findViewById(scaleGroup.getCheckedRadioButtonId())) == 1 ? 2 : 4;
    }

    private void updateInfo() {
        if (input == null) return;
        int s = selectedScale();
        info.setText(input.getWidth() + " × " + input.getHeight() + "  →  "
                + (input.getWidth() * s) + " × " + (input.getHeight() * s)
                + "   (hold the picture to compare)");
    }

    // ---------------------------------------------------------------- loading

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_PICK && resultCode == RESULT_OK && data != null && data.getData() != null) {
            loadImage(data.getData());
        }
    }

    private void loadImage(final Uri uri) {
        status.setText("Loading image…");
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    final Bitmap bmp = decode(uri);
                    final String name = queryName(uri);
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            setInput(uri, name, bmp);
                        }
                    });
                } catch (final Throwable t) {
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            status.setText("Could not open image: " + t.getMessage());
                        }
                    });
                }
            }
        }).start();
    }

    private void setInput(Uri uri, String name, Bitmap bmp) {
        clearResult();
        if (input != null && input != bmp) input.recycle();
        sourceUri = uri;
        sourceName = name;
        input = bmp;
        inputPreview = scaleForPreview(bmp);
        preview.setImageBitmap(inputPreview);
        status.setText("");
        updateInfo();
        refreshButtons();
    }

    private void clearResult() {
        if (result != null) result.recycle();
        result = null;
        resultPreview = null;
        savedUri = null;
        cropRow.setVisibility(View.GONE);
    }

    private String queryName(Uri uri) {
        String name = "image";
        try {
            Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null);
            if (c != null) {
                try {
                    if (c.moveToFirst() && c.getString(0) != null) name = c.getString(0);
                } finally {
                    c.close();
                }
            }
        } catch (Exception ignored) {
        }
        int dot = name.lastIndexOf('.');
        if (dot > 0) name = name.substring(0, dot);
        return name;
    }

    private Bitmap decode(Uri uri) throws Exception {
        ContentResolver cr = getContentResolver();
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        InputStream is = cr.openInputStream(uri);
        try {
            BitmapFactory.decodeStream(is, null, o);
        } finally {
            is.close();
        }
        if (o.outWidth <= 0 || o.outHeight <= 0) throw new Exception("unsupported format");

        // Decode with subsampling if the photo is far bigger than we can upscale anyway.
        long maxIn = MAX_OUTPUT_PIXELS / 4;
        int sample = 1;
        while ((long) (o.outWidth / (sample * 2)) * (o.outHeight / (sample * 2)) >= maxIn) sample *= 2;
        BitmapFactory.Options d = new BitmapFactory.Options();
        d.inSampleSize = sample;
        d.inPreferredConfig = Bitmap.Config.ARGB_8888;
        is = cr.openInputStream(uri);
        Bitmap bmp;
        try {
            bmp = BitmapFactory.decodeStream(is, null, d);
        } finally {
            is.close();
        }
        if (bmp == null) throw new Exception("unsupported format");

        int rotation = exifRotation(uri);
        if (rotation != 0) {
            Matrix m = new Matrix();
            m.postRotate(rotation);
            Bitmap r = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
            if (r != bmp) bmp.recycle();
            bmp = r;
        }
        if (bmp.getConfig() != Bitmap.Config.ARGB_8888) {
            Bitmap c = bmp.copy(Bitmap.Config.ARGB_8888, false);
            bmp.recycle();
            bmp = c;
        }
        return bmp;
    }

    /** ExifInterface(InputStream) is API 24; call it reflectively since we compile against API 23. */
    private int exifRotation(Uri uri) {
        InputStream is = null;
        try {
            is = getContentResolver().openInputStream(uri);
            Class<?> cls = Class.forName("android.media.ExifInterface");
            Constructor<?> ctor = cls.getConstructor(InputStream.class);
            Object exif = ctor.newInstance(is);
            int orientation = (Integer) cls.getMethod("getAttributeInt", String.class, int.class)
                    .invoke(exif, "Orientation", 1);
            switch (orientation) {
                case 6:
                    return 90;
                case 3:
                    return 180;
                case 8:
                    return 270;
                default:
                    return 0;
            }
        } catch (Throwable t) {
            return 0;
        } finally {
            if (is != null) {
                try {
                    is.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    private static Bitmap scaleForPreview(Bitmap b) {
        int w = b.getWidth(), h = b.getHeight();
        int m = Math.max(w, h);
        if (m <= PREVIEW_MAX) return b;
        float f = PREVIEW_MAX / (float) m;
        return Bitmap.createScaledBitmap(b, Math.max(1, Math.round(w * f)), Math.max(1, Math.round(h * f)), true);
    }

    // ---------------------------------------------------------------- processing

    private void startUpscale() {
        if (input == null || running) return;
        final int modelIdx = selectedModel();
        final int scale = selectedScale();

        Bitmap src = input;
        long outPixels = (long) src.getWidth() * src.getHeight() * scale * scale;
        if (outPixels > MAX_OUTPUT_PIXELS) {
            double f = Math.sqrt(MAX_OUTPUT_PIXELS / (double) outPixels);
            int nw = Math.max(1, (int) (src.getWidth() * f));
            int nh = Math.max(1, (int) (src.getHeight() * f));
            src = Bitmap.createScaledBitmap(src, nw, nh, true);
            Toast.makeText(this, "Image is large, input reduced to " + nw + " × " + nh
                    + " to fit in memory", Toast.LENGTH_LONG).show();
        }
        final Bitmap work = src;

        clearResult();
        preview.setImageBitmap(inputPreview);
        running = true;
        cancelled = false;
        progress.setProgress(0);
        status.setText("Loading model…");
        refreshButtons();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        new Thread(new Runnable() {
            @Override
            public void run() {
                final long start = SystemClock.elapsedRealtime();
                try {
                    if (upscaler == null || upscalerModel != modelIdx) {
                        if (upscaler != null) upscaler.close();
                        upscaler = null;
                        upscaler = new Upscaler(readAsset(MODEL_FILES[modelIdx]));
                        upscalerModel = modelIdx;
                    }
                    final Bitmap out = upscaler.upscale(work, scale, TILE, TILE_PAD, new Upscaler.Listener() {
                        @Override
                        public void onProgress(final int done, final int total) {
                            final long elapsed = SystemClock.elapsedRealtime() - start;
                            ui.post(new Runnable() {
                                @Override
                                public void run() {
                                    progress.setProgress(done * 1000 / total);
                                    long eta = done > 0 ? elapsed * (total - done) / done : 0;
                                    status.setText("Upscaling… " + (done * 100 / total) + "%  ·  "
                                            + fmt(elapsed) + " elapsed" + (done < total ? ", ~" + fmt(eta) + " left" : ""));
                                }
                            });
                        }

                        @Override
                        public boolean isCancelled() {
                            return cancelled;
                        }
                    });
                    final Bitmap outPreview = scaleForPreview(out);
                    final long took = SystemClock.elapsedRealtime() - start;
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            finishRun(work, out, outPreview, scale, "Done in " + fmt(took) + ". Output "
                                    + out.getWidth() + " × " + out.getHeight() + ".");
                        }
                    });
                } catch (Upscaler.CancelledException e) {
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            finishRun(work, null, null, scale, "Cancelled.");
                        }
                    });
                } catch (final Throwable t) {
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            finishRun(work, null, null, scale, "Error: " + t);
                        }
                    });
                }
            }
        }).start();
    }

    private void finishRun(Bitmap work, Bitmap out, Bitmap outPreview, int scale, String message) {
        running = false;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        status.setText(message);
        if (out != null) {
            result = out;
            resultScale = scale;
            resultPreview = outPreview;
            preview.setImageBitmap(resultPreview);
            showCrops(work, out, scale);
        }
        if (work != input) work.recycle();
        refreshButtons();
    }

    private void showCrops(Bitmap in, Bitmap out, int scale) {
        int cs = Math.min(96, Math.min(in.getWidth(), in.getHeight()));
        int cx = (in.getWidth() - cs) / 2, cy = (in.getHeight() - cs) / 2;
        Bitmap before = Bitmap.createBitmap(in, cx, cy, cs, cs);
        before = Bitmap.createScaledBitmap(before, cs * scale, cs * scale, true);
        Bitmap after = Bitmap.createBitmap(out, cx * scale, cy * scale, cs * scale, cs * scale);
        cropBefore.setImageBitmap(before);
        cropAfter.setImageBitmap(after);
        cropRow.setVisibility(View.VISIBLE);
    }

    private byte[] readAsset(String name) throws Exception {
        InputStream is = getAssets().open(name);
        try {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[1 << 16];
            int n;
            while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
            return bos.toByteArray();
        } finally {
            is.close();
        }
    }

    private static String fmt(long ms) {
        long s = ms / 1000;
        return s >= 60 ? (s / 60) + "m " + (s % 60) + "s" : s + "s";
    }

    // ---------------------------------------------------------------- saving

    private void save() {
        if (result == null) return;
        if (Build.VERSION.SDK_INT < 29
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_WRITE_PERM);
            return;
        }
        final Bitmap bmp = result;
        final boolean png = bmp.hasAlpha();
        final String name = sourceName + "_x" + resultScale
                + "_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date())
                + (png ? ".png" : ".jpg");
        running = true;
        refreshButtons();
        progress.setVisibility(View.INVISIBLE);
        status.setText("Saving…");
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    final Uri uri = writeToGallery(bmp, name, png);
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            running = false;
                            savedUri = uri;
                            status.setText("Saved to Pictures/Real-ESRGAN/" + name);
                            refreshButtons();
                            if (shareAfterSave) share(uri);
                        }
                    });
                } catch (final Throwable t) {
                    ui.post(new Runnable() {
                        @Override
                        public void run() {
                            running = false;
                            status.setText("Save failed: " + t.getMessage());
                            refreshButtons();
                        }
                    });
                }
            }
        }).start();
    }

    private Uri writeToGallery(Bitmap bmp, String name, boolean png) throws Exception {
        String mime = png ? "image/png" : "image/jpeg";
        Bitmap.CompressFormat fmt = png ? Bitmap.CompressFormat.PNG : Bitmap.CompressFormat.JPEG;
        ContentResolver cr = getContentResolver();
        ContentValues v = new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        if (Build.VERSION.SDK_INT >= 29) {
            v.put("relative_path", Environment.DIRECTORY_PICTURES + "/Real-ESRGAN");
            v.put("is_pending", 1);
            Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new Exception("could not create gallery entry");
            OutputStream os = cr.openOutputStream(uri);
            try {
                bmp.compress(fmt, 97, os);
            } finally {
                os.close();
            }
            ContentValues done = new ContentValues();
            done.put("is_pending", 0);
            cr.update(uri, done, null, null);
            return uri;
        } else {
            File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "Real-ESRGAN");
            if (!dir.isDirectory() && !dir.mkdirs()) throw new Exception("cannot create " + dir);
            File f = new File(dir, name);
            FileOutputStream os = new FileOutputStream(f);
            try {
                bmp.compress(fmt, 97, os);
            } finally {
                os.close();
            }
            v.put(MediaStore.MediaColumns.DATA, f.getAbsolutePath());
            Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new Exception("could not create gallery entry");
            return uri;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == REQ_WRITE_PERM) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                save();
            } else {
                Toast.makeText(this, "Storage permission is needed to save", Toast.LENGTH_LONG).show();
            }
        }
    }

    private void share(Uri uri) {
        Intent s = new Intent(Intent.ACTION_SEND);
        s.setType(result != null && result.hasAlpha() ? "image/png" : "image/jpeg");
        s.putExtra(Intent.EXTRA_STREAM, uri);
        s.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(s, "Share upscaled image"));
    }

    @Override
    protected void onDestroy() {
        cancelled = true;
        super.onDestroy();
    }
}
