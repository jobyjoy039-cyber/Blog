package com.productvideostudio.ui;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.util.Log;

import com.productvideostudio.model.Enums;
import com.productvideostudio.model.Project;
import com.productvideostudio.service.Pipeline;
import com.productvideostudio.service.RenderService;
import com.productvideostudio.service.RenderState;
import com.productvideostudio.storage.ProjectStore;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.file.Files;

/**
 * End-to-end check used by CI on an emulator: draws sample product photos, runs analysis,
 * direction and a real background render, then copies the MP4 and plan to external files.
 * Start with: adb shell am start -n com.productvideostudio/.ui.MainActivity --ez selftest true
 */
final class SelfTest {
    private static final String TAG = "SelfTest";

    private SelfTest() {}

    static void start(Context ctx, Intent intent) {
        Context app = ctx.getApplicationContext();
        int duration = intent.getIntExtra("duration", 12);
        int fps = intent.getIntExtra("fps", 30);
        String voice = intent.getStringExtra("voice");
        String look = intent.getStringExtra("look");
        new Thread(() -> run(app, duration, fps, voice, look), "selftest").start();
    }

    private static void run(Context ctx, int duration, int fps, String voice, String look) {
        File outDir = ctx.getExternalFilesDir(null);
        File done = new File(outDir, "selftest.done"), error = new File(outDir, "selftest.error");
        //noinspection ResultOfMethodCallIgnored
        done.delete();
        //noinspection ResultOfMethodCallIgnored
        error.delete();
        try {
            ProjectStore store = new ProjectStore(ctx);
            Project p = store.create();
            p.name = "Aurora Glow Serum";
            p.description = "Vitamin C brightening serum\nLightweight, fast-absorbing formula\nWith hyaluronic acid and niacinamide\nYour skin will love the glow\nDermatologist tested";
            p.price = "39";
            p.discount = "20%";
            p.url = "https://aurora-skin.example/glow";
            p.durationSec = duration;
            p.fps = fps;
            p.voiceMode = voice == null ? Project.VOICE_TTS : voice;
            if (look != null) p.look = Enums.parse(Enums.Look.class, look, null);
            File dir = store.dir(p);
            p.images.add(save(packshot(), new File(dir, "img_front.jpg")));
            p.images.add(save(boxShot(), new File(dir, "img_box.jpg")));
            p.images.add(save(lifestyle(), new File(dir, "img_life.jpg")));
            p.logo = savePng(logo(), new File(dir, "logo.png"));
            store.save(p);

            Pipeline.prepare(ctx, store, p, m -> Log.i(TAG, m));
            Files.write(new File(outDir, "selftest-plan.json").toPath(), p.toJson().toString(2).getBytes("UTF-8"));

            RenderService.start(ctx, p.id);
            RenderState st = RenderState.get();
            long deadline = System.currentTimeMillis() + 20 * 60_000L;
            while (System.currentTimeMillis() < deadline) {
                Thread.sleep(500);
                if (st.status == RenderState.Status.DONE || st.status == RenderState.Status.FAILED) break;
                Log.i(TAG, "progress " + Math.round(st.progress * 100) + "% " + st.stage);
            }
            if (st.status != RenderState.Status.DONE) throw new IllegalStateException("render ended as " + st.status + ": " + st.error);
            Project finished = store.load(p.id);
            // Written as a new file (not Files.copy, which keeps app-private permissions) so adb can pull it.
            Files.write(new File(outDir, "selftest.mp4").toPath(), Files.readAllBytes(new File(finished.outputPath).toPath()));
            Files.write(done.toPath(), ("gallery=" + finished.outputUri + "\n").getBytes("UTF-8"));
            Log.i(TAG, "self-test passed");
        } catch (Throwable t) {
            Log.e(TAG, "self-test failed", t);
            StringWriter sw = new StringWriter();
            t.printStackTrace(new PrintWriter(sw));
            try {
                Files.write(error.toPath(), sw.toString().getBytes("UTF-8"));
            } catch (IOException ignored) {
            }
        }
    }

    // ------------------------------------------------------------------------------------
    // Sample photos

    private static String save(Bitmap b, File f) throws IOException {
        try (FileOutputStream out = new FileOutputStream(f)) {
            b.compress(Bitmap.CompressFormat.JPEG, 92, out);
        }
        b.recycle();
        return f.getName();
    }

    private static String savePng(Bitmap b, File f) throws IOException {
        try (FileOutputStream out = new FileOutputStream(f)) {
            b.compress(Bitmap.CompressFormat.PNG, 100, out);
        }
        b.recycle();
        return f.getName();
    }

    /** Amber glass dropper bottle on a seamless off-white background. */
    static Bitmap packshot() {
        Bitmap b = Bitmap.createBitmap(1200, 1600, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        c.drawColor(0xFFF3F1EE);
        drawBottle(c, 600, 1500, 1f);
        return b;
    }

    static void drawBottle(Canvas c, float cx, float bottom, float s) {
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        float w = 420 * s, h = 760 * s;
        RectF body = new RectF(cx - w / 2, bottom - h, cx + w / 2, bottom);
        p.setShader(new LinearGradient(body.left, 0, body.right, 0,
                new int[]{0xFF6B3A12, 0xFFC7772E, 0xFFE9A252, 0xFFB5641F, 0xFF5A2E0C}, null, Shader.TileMode.CLAMP));
        c.drawRoundRect(body, 70 * s, 70 * s, p);
        // Shoulder, neck and dropper cap.
        RectF neck = new RectF(cx - 90 * s, bottom - h - 70 * s, cx + 90 * s, bottom - h + 30 * s);
        c.drawRoundRect(neck, 30 * s, 30 * s, p);
        p.setShader(new LinearGradient(cx - 110 * s, 0, cx + 110 * s, 0,
                new int[]{0xFF1A1A1A, 0xFF5A5A5A, 0xFF2A2A2A}, null, Shader.TileMode.CLAMP));
        RectF cap = new RectF(cx - 110 * s, bottom - h - 250 * s, cx + 110 * s, bottom - h - 60 * s);
        c.drawRoundRect(cap, 40 * s, 40 * s, p);
        p.setShader(new LinearGradient(cx - 110 * s, 0, cx + 110 * s, 0,
                new int[]{0xFF8C6A2B, 0xFFE8C877, 0xFF8C6A2B}, null, Shader.TileMode.CLAMP));
        c.drawRect(cx - 112 * s, bottom - h - 90 * s, cx + 112 * s, bottom - h - 60 * s, p);
        // Label.
        p.setShader(null);
        p.setColor(0xFFF8F4EC);
        RectF label = new RectF(cx - w / 2 + 50 * s, bottom - h * 0.66f, cx + w / 2 - 50 * s, bottom - h * 0.2f);
        c.drawRoundRect(label, 16 * s, 16 * s, p);
        p.setColor(0xFF2B1A0C);
        p.setTypeface(Typeface.create("serif", Typeface.BOLD));
        p.setTextAlign(Paint.Align.CENTER);
        p.setTextSize(64 * s);
        p.setLetterSpacing(0.12f);
        c.drawText("AURORA", cx, label.top + 110 * s, p);
        p.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        p.setTextSize(30 * s);
        p.setLetterSpacing(0.2f);
        c.drawText("GLOW SERUM", cx, label.top + 170 * s, p);
        p.setTextSize(24 * s);
        c.drawText("VITAMIN C · 30 ML", cx, label.bottom - 40 * s, p);
        // Glass highlight.
        p.setColor(0x66FFFFFF);
        c.drawRoundRect(new RectF(body.left + 40 * s, body.top + 60 * s, body.left + 80 * s, body.bottom - 60 * s), 20 * s, 20 * s, p);
    }

    /** The retail box, shot wide on light grey. */
    static Bitmap boxShot() {
        Bitmap b = Bitmap.createBitmap(1600, 1200, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        c.drawColor(0xFFE9E7E4);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        RectF front = new RectF(260, 420, 1180, 900);
        p.setShader(new LinearGradient(0, front.top, 0, front.bottom, 0xFFF6EBDD, 0xFFE2CDB2, Shader.TileMode.CLAMP));
        c.drawRect(front, p);
        p.setShader(new LinearGradient(front.right, 0, front.right + 160, 0, 0xFFCDB598, 0xFFB39C80, Shader.TileMode.CLAMP));
        android.graphics.Path side = new android.graphics.Path();
        side.moveTo(front.right, front.top);
        side.lineTo(front.right + 160, front.top - 110);
        side.lineTo(front.right + 160, front.bottom - 110);
        side.lineTo(front.right, front.bottom);
        side.close();
        c.drawPath(side, p);
        p.setShader(null);
        p.setColor(0xFFF9F1E6);
        android.graphics.Path top = new android.graphics.Path();
        top.moveTo(front.left, front.top);
        top.lineTo(front.left + 160, front.top - 110);
        top.lineTo(front.right + 160, front.top - 110);
        top.lineTo(front.right, front.top);
        top.close();
        c.drawPath(top, p);
        p.setColor(0xFFC7772E);
        c.drawRect(front.left, front.bottom - 70, front.right, front.bottom - 40, p);
        p.setColor(0xFF2B1A0C);
        p.setTypeface(Typeface.create("serif", Typeface.BOLD));
        p.setTextAlign(Paint.Align.CENTER);
        p.setTextSize(120);
        p.setLetterSpacing(0.15f);
        c.drawText("AURORA", front.centerX(), front.centerY() + 10, p);
        p.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        p.setTextSize(40);
        p.setLetterSpacing(0.3f);
        c.drawText("GLOW SERUM", front.centerX(), front.centerY() + 90, p);
        return b;
    }

    /** Bottle on a marble counter with warm window light and bokeh. */
    static Bitmap lifestyle() {
        Bitmap b = Bitmap.createBitmap(1080, 1440, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setShader(new LinearGradient(0, 0, 0, 1000, 0xFF8FA39A, 0xFFE8D8C0, Shader.TileMode.CLAMP));
        c.drawRect(0, 0, 1080, 1000, p);
        java.util.Random r = new java.util.Random(4);
        for (int i = 0; i < 26; i++) {
            float x = r.nextFloat() * 1080, y = r.nextFloat() * 900, rad = 30 + r.nextFloat() * 90;
            p.setShader(new RadialGradient(x, y, rad, 0x66FFF3D6, 0x00FFF3D6, Shader.TileMode.CLAMP));
            c.drawCircle(x, y, rad, p);
        }
        p.setShader(new LinearGradient(0, 1000, 0, 1440, 0xFFEDEAE4, 0xFFC9C3BA, Shader.TileMode.CLAMP));
        c.drawRect(0, 1000, 1080, 1440, p);
        p.setShader(null);
        p.setStrokeWidth(3);
        p.setColor(0x33707070);
        for (int i = 0; i < 9; i++) c.drawLine(r.nextFloat() * 1080, 1000, r.nextFloat() * 1080, 1440, p);
        p.setColor(0x33000000);
        c.drawOval(new RectF(330, 1210, 750, 1270), p);
        drawBottle(c, 540, 1240, 0.62f);
        // A leaf, for a spa feel.
        p.setColor(0xFF4F7A55);
        c.drawOval(new RectF(760, 1150, 1010, 1230), p);
        return b;
    }

    static Bitmap logo() {
        Bitmap b = Bitmap.createBitmap(640, 200, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(0xFFE8C877);
        p.setTypeface(Typeface.create("serif", Typeface.BOLD));
        p.setTextAlign(Paint.Align.CENTER);
        p.setTextSize(120);
        p.setLetterSpacing(0.2f);
        c.drawText("AURORA", 320, 140, p);
        return b;
    }
}
