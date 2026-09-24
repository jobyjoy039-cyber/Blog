package com.jobyjoy.pixelboost;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import org.robolectric.shadows.ShadowLooper;

import android.app.Activity;
import android.app.Dialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.net.Uri;
import android.view.View;
import android.widget.Button;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.annotation.LooperMode;
import org.robolectric.shadows.ShadowDialog;

import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.Field;
import java.util.concurrent.Callable;
import java.util.concurrent.TimeUnit;

/**
 * Drives the real MainActivity end to end (load, upscale with every model and output size, save,
 * About) and writes 1080x1920 screenshots for the Play listing.
 */
@RunWith(RobolectricTestRunner.class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
@Config(sdk = 35, qualifiers = "w360dp-h640dp-xxhdpi")
public class AppFlowTest {

    private final File outDir = new File(System.getProperty("outDir"));
    private final File samples = new File(System.getProperty("samplesDir"));

    @SuppressWarnings("unchecked")
    private static <T> T field(Object o, String name) throws Exception {
        Field f = o.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return (T) f.get(o);
    }

    private static void idle() {
        ShadowLooper.idleMainLooper();
    }

    private static void waitFor(String what, long timeoutMs, Callable<Boolean> cond) throws Exception {
        long end = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < end) {
            idle();
            if (cond.call()) return;
            // Robolectric's clock is frozen; advance it in step with real time so the app's
            // elapsed/ETA texts are realistic.
            long t = System.currentTimeMillis();
            Thread.sleep(20);
            ShadowLooper.idleMainLooper(System.currentTimeMillis() - t, TimeUnit.MILLISECONDS);
        }
        throw new AssertionError("timed out waiting for " + what);
    }

    private MainActivity launch(String sample) {
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("image/jpeg");
        i.putExtra(Intent.EXTRA_STREAM, Uri.fromFile(new File(samples, sample)));
        MainActivity a = Robolectric.buildActivity(MainActivity.class, i).setup().get();
        idle();
        return a;
    }

    private static String text(MainActivity a, String field) throws Exception {
        return ((TextView) field(a, field)).getText().toString();
    }

    private static void select(RadioGroup g, int index) {
        g.check(g.getChildAt(index).getId());
        idle();
    }

    private static void waitForImage(final MainActivity a) throws Exception {
        waitFor("image to load", 20000, new Callable<Boolean>() {
            public Boolean call() throws Exception {
                return field(a, "input") != null;
            }
        });
    }

    private static void runAndWait(final MainActivity a, long timeoutMs) throws Exception {
        ((Button) field(a, "runBtn")).performClick();
        waitFor("upscale to finish", timeoutMs, new Callable<Boolean>() {
            public Boolean call() throws Exception {
                return !(Boolean) field(a, "running");
            }
        });
        String status = text(a, "status");
        assertTrue("unexpected status: " + status, status.startsWith("Done"));
    }

    private void screenshot(Activity a, String name, Dialog dialog) throws Exception {
        View root = a.getWindow().getDecorView();
        root.jumpDrawablesToCurrentState(); // finish radio-button animations
        Bitmap b = Bitmap.createBitmap(root.getWidth(), root.getHeight(), Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        root.draw(c);
        if (dialog != null) {
            c.drawColor(0x99000000);
            View d = dialog.getWindow().getDecorView();
            d.jumpDrawablesToCurrentState();
            c.save();
            c.translate((b.getWidth() - d.getWidth()) / 2f, (b.getHeight() - d.getHeight()) / 2f);
            d.draw(c);
            c.restore();
        }
        outDir.mkdirs();
        FileOutputStream os = new FileOutputStream(new File(outDir, name));
        b.compress(Bitmap.CompressFormat.PNG, 100, os);
        os.close();
    }

    @Test
    public void fourTimesUpscaleThenSaveAndAbout() throws Exception {
        MainActivity a = launch("coffee.jpg");
        waitForImage(a);
        Bitmap in = field(a, "input");
        assertEquals(300, in.getWidth());
        assertTrue(text(a, "info").contains("1200 × 800"));
        screenshot(a, "1-choose.png", null);

        runAndWait(a, 120000);
        Bitmap out = field(a, "result");
        assertEquals(1200, out.getWidth());
        assertEquals(800, out.getHeight());
        // The result must be a real image, not blank: check it has plenty of distinct colours.
        java.util.HashSet<Integer> colours = new java.util.HashSet<>();
        for (int y = 0; y < out.getHeight(); y += 7) {
            for (int x = 0; x < out.getWidth(); x += 7) colours.add(out.getPixel(x, y));
        }
        assertTrue("too few colours: " + colours.size(), colours.size() > 2000);
        assertTrue("opaque input must give an opaque result", !out.hasAlpha());
        assertEquals(View.VISIBLE, ((View) field(a, "cropRow")).getVisibility());

        // Scroll so the before/after detail is on screen.
        ScrollView sv = (ScrollView) ((View) field(a, "preview")).getParent().getParent();
        sv.scrollTo(0, ((View) field(a, "cropRow")).getTop());
        idle();
        screenshot(a, "2-result.png", null);

        ((Button) field(a, "saveBtn")).performClick();
        final MainActivity fa = a;
        waitFor("save", 20000, new Callable<Boolean>() {
            public Boolean call() throws Exception {
                return text(fa, "status").startsWith("Saved") || text(fa, "status").startsWith("Save failed");
            }
        });
        assertTrue(text(a, "status"), text(a, "status").startsWith("Saved to Pictures/PixelBoost/coffee_x4_"));
        assertTrue(text(a, "status"), text(a, "status").endsWith(".jpg"));
        assertNotNull(field(a, "savedUri"));

        // About dialog, then the licenses.
        View header = ((android.view.ViewGroup) a.findViewById(android.R.id.content)).getChildAt(0);
        View aboutLink = ((android.view.ViewGroup) ((android.view.ViewGroup) header).getChildAt(0)).getChildAt(1);
        aboutLink.performClick();
        idle();
        Dialog about = ShadowDialog.getLatestDialog();
        assertNotNull(about);
        assertTrue(about.isShowing());
        screenshot(a, "6-about.png", about);
        ((android.app.AlertDialog) about).getButton(android.content.DialogInterface.BUTTON_NEUTRAL).performClick();
        idle();
        Dialog lic = ShadowDialog.getLatestDialog();
        assertTrue(lic != about && lic.isShowing());
    }

    @Test
    public void fourKPresetUsesTwoPasses() throws Exception {
        MainActivity a = launch("chelsea.jpg");
        waitForImage(a);
        select((RadioGroup) field(a, "scaleGroup"), 2); // 4K
        String info = text(a, "info");
        assertTrue(info, info.contains("3240 × 2160 (2 passes, slower)"));
        final MainActivity fa = a;
        ((Button) field(a, "runBtn")).performClick();
        waitFor("second pass", 600000, new Callable<Boolean>() {
            public Boolean call() throws Exception {
                return text(fa, "status").contains("Pass 2 of 2… 3");
            }
        });
        assertTrue(((Button) field(a, "cancelBtn")).isEnabled());
        assertTrue(!((Button) field(a, "runBtn")).isEnabled());
        ScrollView sv0 = (ScrollView) ((View) field(a, "preview")).getParent().getParent();
        sv0.scrollTo(0, ((View) field(a, "info")).getTop() - 30);
        idle();
        screenshot(a, "3-progress.png", null);
        waitFor("upscale to finish", 600000, new Callable<Boolean>() {
            public Boolean call() throws Exception {
                return !(Boolean) field(fa, "running");
            }
        });
        assertTrue(text(a, "status"), text(a, "status").startsWith("Done"));
        Bitmap out = field(a, "result");
        assertEquals(3240, out.getWidth());
        assertEquals(2160, out.getHeight());
        assertEquals("4K", field(a, "resultTag"));
        ScrollView sv = (ScrollView) ((View) field(a, "preview")).getParent().getParent();
        sv.scrollTo(0, 0);
        idle();
        screenshot(a, "4-4k-result.png", null);
    }

    @Test
    public void bestQualityModelAndTwoTimes() throws Exception {
        MainActivity a = launch("astronaut.jpg");
        waitForImage(a);
        select((RadioGroup) field(a, "modelGroup"), 2); // RealESRGAN_x4plus
        select((RadioGroup) field(a, "scaleGroup"), 0); // 2x
        runAndWait(a, 600000);
        Bitmap out = field(a, "result");
        assertEquals(400, out.getWidth());
        assertEquals(400, out.getHeight());
        ScrollView sv = (ScrollView) ((View) field(a, "preview")).getParent().getParent();
        sv.scrollTo(0, ((View) field(a, "cropRow")).getTop());
        idle();
        screenshot(a, "5-best-quality.png", null);
    }

    @Test
    public void eightKPresetPlanAndIdleState() throws Exception {
        MainActivity a = launch("rocket.jpg");
        waitForImage(a);
        select((RadioGroup) field(a, "scaleGroup"), 3); // 8K
        String info = text(a, "info");
        assertTrue(info, info.contains("6467 × 4320 (2 passes, slower)"));
        // The anime model must be selectable and the Cancel button disabled while idle.
        assertTrue(((RadioGroup) field(a, "modelGroup")).getChildAt(1).isEnabled());
        assertTrue(!((Button) field(a, "cancelBtn")).isEnabled());
        assertTrue(((Button) field(a, "runBtn")).isEnabled());
        assertEquals(Color.TRANSPARENT, a.getWindow().getStatusBarColor());
    }
}
