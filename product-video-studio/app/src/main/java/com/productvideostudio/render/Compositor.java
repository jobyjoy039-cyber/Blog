package com.productvideostudio.render;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.opengl.GLES20;
import android.opengl.Matrix;

import com.productvideostudio.model.Enums.Effect;
import com.productvideostudio.model.Enums.Layout;
import com.productvideostudio.model.Enums.Movement;
import com.productvideostudio.model.Enums.TextAnim;
import com.productvideostudio.model.Enums.TextRole;
import com.productvideostudio.model.Storyboard;
import com.productvideostudio.model.Storyboard.Scene;
import com.productvideostudio.model.Storyboard.TextItem;

import java.nio.FloatBuffer;

/**
 * Draws frames on the GPU. Each scene is rendered into an offscreen buffer with a virtual
 * perspective camera; transitions blend two such buffers; grading and text go on top.
 */
final class Compositor {
    /** Screen half-width in world units (half-height is 1). */
    static final float HALF_W = 9f / 16f;
    private static final float DEPTH = 3f;

    final int width, height;
    private final Storyboard board;
    private final Grade grade;
    private final Gl.Program sprite, backdrop, transition, gradeProg;
    private final FloatBuffer quad = Gl.quad();
    private final Gl.Fbo fboA, fboB, fboC;
    private final float[] proj = new float[16], ortho = new float[16];
    private final float[] model = new float[16], mvp = new float[16], tmp = new float[16];
    private final Gl.Texture blob, scrim;

    Compositor(int width, int height, Storyboard board) {
        this.width = width;
        this.height = height;
        this.board = board;
        this.grade = Grade.of(board.look);
        sprite = new Gl.Program(Shaders.SPRITE_VS, Shaders.SPRITE_FS);
        backdrop = new Gl.Program(Shaders.FULL_VS, Shaders.BACKDROP_FS);
        transition = new Gl.Program(Shaders.FULL_VS, Shaders.TRANSITION_FS);
        gradeProg = new Gl.Program(Shaders.FULL_VS, Shaders.GRADE_FS);
        fboA = new Gl.Fbo(width, height);
        fboB = new Gl.Fbo(width, height);
        fboC = new Gl.Fbo(width, height);
        float n = 1f;
        Matrix.frustumM(proj, 0, -HALF_W * n / DEPTH, HALF_W * n / DEPTH, -n / DEPTH, n / DEPTH, n, 30f);
        Matrix.orthoM(ortho, 0, 0, width, height, 0, -1, 1);
        blob = Gl.upload(radialBlob(), false, 4096);
        scrim = Gl.upload(scrimGradient(), false, 4096);
        Gl.checkError("compositor init");
    }

    // ------------------------------------------------------------------------------------
    // Frame

    /**
     * @param a     scene being shown (or leaving)
     * @param b     incoming scene during a transition, else null
     * @param p     transition progress 0..1
     */
    void frame(Scene a, SceneAssets aa, Frame fa, Scene b, SceneAssets ab, Frame fb, float p, float time) {
        GLES20.glDisable(GLES20.GL_DEPTH_TEST);
        GLES20.glDisable(GLES20.GL_CULL_FACE);
        drawScene(a, aa, fa, fboA);
        Gl.Fbo src = fboA;
        float flash = fa.pose.flash;
        if (b != null) {
            drawScene(b, ab, fb, fboB);
            flash = Math.max(flash, fb.pose.flash);
            fboC.bind();
            GLES20.glDisable(GLES20.GL_BLEND);
            transition.use();
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, fboA.tex);
            GLES20.glActiveTexture(GLES20.GL_TEXTURE1);
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, fboB.tex);
            transition.set1i("uA", 0);
            transition.set1i("uB", 1);
            transition.set1f("uP", p);
            transition.set1i("uType", a.transition.ordinal());
            transition.set2f("uDir", a.direction, 0f);
            transition.set1f("uTime", time);
            int leak = mix(0xFFFF9A3C, board.accentColor, 0.3f);
            transition.setColor3("uLeak", leak);
            Gl.drawQuad(transition, quad);
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            src = fboC;
        }

        // Grade to the encoder surface.
        GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, 0);
        GLES20.glViewport(0, 0, width, height);
        GLES20.glDisable(GLES20.GL_BLEND);
        gradeProg.use();
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, src.tex);
        gradeProg.set1i("uTex", 0);
        gradeProg.set1f("uExposure", grade.exposure);
        gradeProg.set1f("uContrast", grade.contrast);
        gradeProg.set1f("uSaturation", grade.saturation);
        gradeProg.set3f("uShadows", grade.shadows[0], grade.shadows[1], grade.shadows[2]);
        gradeProg.set3f("uHighlights", grade.highlights[0], grade.highlights[1], grade.highlights[2]);
        gradeProg.set3f("uBalance", grade.balance[0], grade.balance[1], grade.balance[2]);
        gradeProg.set1f("uLift", grade.lift);
        gradeProg.set1f("uVignette", grade.vignette);
        gradeProg.set1f("uGrain", grade.grain);
        gradeProg.set1f("uTime", time % 97f);
        gradeProg.set1f("uFlash", flash);
        Gl.drawQuad(gradeProg, quad);

        // Text and logo on top, crisp and ungraded.
        GLES20.glEnable(GLES20.GL_BLEND);
        GLES20.glBlendFunc(GLES20.GL_ONE, GLES20.GL_ONE_MINUS_SRC_ALPHA);
        drawOverlays(a, aa, fa);
        if (b != null) drawOverlays(b, ab, fb);
    }

    /** Per-scene timing for one frame. */
    static final class Frame {
        float u, local, time;
        CameraRig.Pose pose, previous;
    }

    // ------------------------------------------------------------------------------------
    // Scene

    private void drawScene(Scene sc, SceneAssets as, Frame f, Gl.Fbo target) {
        target.bind();
        CameraRig.Pose pose = f.pose;
        GLES20.glClearColor(0, 0, 0, 1);
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);

        float[] size = productSize(sc, as);
        float w = size[0], h = size[1];
        float baseY = sc.layout == Layout.FULL_BLEED ? 0f : 1f - 2f * sc.productY;
        float tx = pose.tx, ty = pose.ty;
        if (sc.layout == Layout.FULL_BLEED) {
            float maxTx = Math.max(0, (w * pose.scale - 2 * HALF_W) / 2), maxTy = Math.max(0, (h * pose.scale - 2) / 2);
            tx = clamp(tx, -maxTx, maxTx);
            ty = clamp(ty, -maxTy, maxTy);
        }

        // 1. Backdrop.
        GLES20.glDisable(GLES20.GL_BLEND);
        if (sc.layout == Layout.STUDIO || as.backdrop == null) {
            backdrop.use();
            backdrop.setColor3("uInner", board.backdropInner);
            backdrop.setColor3("uOuter", board.backdropOuter);
            float cy = 1f - sc.productY + 0.06f;
            backdrop.set2f("uCenter", 0.5f + pose.bgTx * 0.5f, cy + pose.bgTy * 0.5f);
            backdrop.set1f("uAspect", 2 * HALF_W / 2f);
            float floor = sc.layout == Layout.STUDIO ? 1f - (sc.productY + h / 4f) + 0.01f + pose.bgTy * 0.5f : -1f;
            backdrop.set1f("uFloor", floor);
            backdrop.set1f("uSpot", 0.5f * pose.exposure);
            backdrop.set1f("uExposure", 0.35f + 0.65f * pose.exposure);
            Gl.drawQuad(backdrop, quad);
        } else {
            GLES20.glEnable(GLES20.GL_BLEND);
            GLES20.glBlendFunc(GLES20.GL_ONE, GLES20.GL_ONE_MINUS_SRC_ALPHA);
            float photoAspect = as.backdrop.width / (float) as.backdrop.height;
            float bw, bh;
            if (photoAspect > HALF_W) { bh = 2f; bw = 2f * photoAspect; } else { bw = 2 * HALF_W; bh = bw / photoAspect; }
            float s = 1.15f * pose.bgScale;
            placeFlat(pose.bgTx, pose.bgTy, bw * s, bh * s);
            beginSprite(as.backdrop);
            sprite.set1f("uBrightness", (sc.layout == Layout.CARD ? 0.55f : 0.75f) * pose.exposure);
            sprite.set1f("uTapBlur", 0.012f + pose.bgBlur * 0.004f);
            Gl.drawQuad(sprite, quad);
        }

        GLES20.glEnable(GLES20.GL_BLEND);
        boolean card = sc.layout == Layout.CARD || (sc.layout == Layout.STUDIO && !as.cutout);
        float corner = card ? 0.03f : 0f;

        // 2. Glow behind the product.
        if (sc.has(Effect.GLOW) && sc.layout != Layout.FULL_BLEED) {
            GLES20.glBlendFunc(GLES20.GL_ONE, GLES20.GL_ONE);
            placeProduct(sc, pose, tx, baseY + ty, w * 1.08f, h * 1.08f, 0, 0);
            beginSprite(as.product);
            sprite.set1f("uLod", 5.5f);
            sprite.set4f("uTint", r(board.accentColor), g(board.accentColor), b(board.accentColor), 1f);
            sprite.set1f("uAlpha", 0.45f * pose.exposure);
            sprite.set1f("uCorner", corner);
            sprite.set1f("uAspect", as.aspect);
            Gl.drawQuad(sprite, quad);
        }
        GLES20.glBlendFunc(GLES20.GL_ONE, GLES20.GL_ONE_MINUS_SRC_ALPHA);

        // 3. Shadows.
        if (sc.has(Effect.SHADOW) && sc.layout != Layout.FULL_BLEED) {
            if (as.cutout) {
                float contactModel = 0.5f - as.contactV;
                float cy = baseY + ty + contactModel * h * pose.scale;
                placeFlat(tx, cy - 0.01f, w * pose.scale * 1.05f, Math.max(0.05f, w * pose.scale * 0.16f));
                beginSprite(blob);
                sprite.set4f("uTint", 0, 0, 0, 1f);
                sprite.set1f("uAlpha", 0.55f * pose.exposure);
                Gl.drawQuad(sprite, quad);
            }
            placeProduct(sc, pose, tx + 0.02f, baseY + ty - 0.035f, w, h, 0, 0);
            beginSprite(as.product);
            sprite.set1f("uLod", 4.5f);
            sprite.set4f("uTint", 0, 0, 0, 1f);
            sprite.set1f("uAlpha", (as.cutout ? 0.3f : 0.55f) * pose.exposure);
            sprite.set1f("uCorner", corner);
            sprite.set1f("uAspect", as.aspect);
            Gl.drawQuad(sprite, quad);
        }

        // 4. Floor reflection.
        if (sc.has(Effect.REFLECTION) && as.cutout && sc.movement != Movement.ROTATE_360) {
            float m = 0.5f - as.contactV;
            placeProduct(sc, pose, tx, baseY + ty, w, h, 0, 0);
            Matrix.translateM(model, 0, 0, 2 * m, 0);
            Matrix.scaleM(model, 0, 1, -1, 1);
            Matrix.multiplyMM(mvp, 0, proj, 0, model, 0);
            beginSprite(as.product);
            sprite.setMat4("uMvp", mvp);
            sprite.set1f("uAlpha", 0.22f * pose.exposure);
            sprite.set1f("uFade", 0.38f);
            sprite.set1f("uLod", 1.2f);
            sprite.set1f("uBrightness", 0.9f);
            Gl.drawQuad(sprite, quad);
        }

        // 5. The product or photo.
        placeProduct(sc, pose, tx, baseY + ty, w, h, 0, 0);
        beginSprite(as.product);
        sprite.set1f("uBrightness", pose.exposure);
        sprite.set1f("uLod", pose.blur);
        sprite.set1f("uBackFlip", sc.movement == Movement.ROTATE_360 ? 1f : 0f);
        sprite.set1f("uCorner", corner);
        sprite.set1f("uAspect", as.aspect);
        if (!Float.isNaN(pose.sweep)) {
            sprite.set1f("uSweep", pose.sweep);
            sprite.set1f("uSweepGain", pose.sweepGain);
        }
        if ((sc.has(Effect.MOTION_BLUR) || sc.movement == Movement.ROTATE_360) && f.previous != null) {
            float fps = board.fps;
            float mx = (tx - f.previous.tx) / (w * pose.scale) * 0.8f * (30f / fps);
            float my = -(pose.ty - f.previous.ty) / (h * pose.scale) * 0.8f * (30f / fps);
            float dyaw = pose.yaw - f.previous.yaw;
            mx += dyaw / 360f * 0.9f * (30f / fps);
            float len = (float) Math.sqrt(mx * mx + my * my);
            if (len > 0.05f) { mx *= 0.05f / len; my *= 0.05f / len; }
            if (len > 0.002f) sprite.set2f("uMotion", mx, my);
        }
        Gl.drawQuad(sprite, quad);
        Gl.checkError("scene");
    }

    /** Product quad size in world units for this layout. */
    private float[] productSize(Scene sc, SceneAssets as) {
        float a = as.aspect;
        float w, h;
        if (sc.layout == Layout.FULL_BLEED) {
            if (a > HALF_W) { h = 2f; w = 2f * a; } else { w = 2 * HALF_W; h = w / a; }
            w *= 1.1f;
            h *= 1.1f;
        } else {
            float maxH = sc.productHeight * 2f;
            float maxW = 2 * HALF_W * (sc.layout == Layout.STUDIO ? 0.9f : 0.84f);
            h = maxH;
            w = h * a;
            if (w > maxW) { w = maxW; h = w / a; }
        }
        return new float[]{w, h};
    }

    private void placeProduct(Scene sc, CameraRig.Pose pose, float x, float y, float w, float h, float extraYaw, float extraPitch) {
        Matrix.setIdentityM(model, 0);
        Matrix.translateM(model, 0, x, y, -DEPTH);
        Matrix.rotateM(model, 0, pose.pitch + extraPitch, 1, 0, 0);
        Matrix.rotateM(model, 0, pose.yaw + extraYaw, 0, 1, 0);
        Matrix.rotateM(model, 0, pose.roll, 0, 0, 1);
        Matrix.scaleM(model, 0, w * pose.scale, h * pose.scale, 1);
        Matrix.multiplyMM(mvp, 0, proj, 0, model, 0);
    }

    private void placeFlat(float x, float y, float w, float h) {
        Matrix.setIdentityM(model, 0);
        Matrix.translateM(model, 0, x, y, -DEPTH);
        Matrix.scaleM(model, 0, w, h, 1);
        Matrix.multiplyMM(mvp, 0, proj, 0, model, 0);
    }

    /** Binds a texture to the sprite program and resets every effect uniform. */
    private void beginSprite(Gl.Texture t) {
        sprite.use();
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, t.id);
        sprite.set1i("uTex", 0);
        sprite.setMat4("uMvp", mvp);
        sprite.set2f("uTexel", 1f / t.width, 1f / t.height);
        sprite.set1f("uAlpha", 1f);
        sprite.set1f("uLod", 0f);
        sprite.set1f("uTapBlur", 0f);
        sprite.set2f("uMotion", 0f, 0f);
        sprite.set1f("uSweep", -10f);
        sprite.set1f("uSweepGain", 0f);
        sprite.set4f("uTint", 0, 0, 0, 0);
        sprite.set1f("uBrightness", 1f);
        sprite.set1f("uBackFlip", 0f);
        sprite.set1f("uFade", 0f);
        sprite.set1f("uCorner", 0f);
        sprite.set1f("uAspect", t.width / (float) t.height);
        sprite.set1f("uClipX", 1f);
    }

    // ------------------------------------------------------------------------------------
    // Text, scrim, logo

    private void drawOverlays(Scene sc, SceneAssets as, Frame f) {
        if (as.texts == null) return;
        float local = f.local;
        float scrimAlpha = 0;
        if (sc.layout == Layout.FULL_BLEED) {
            for (int i = 0; i < sc.texts.size(); i++) {
                TextItem t = sc.texts.get(i);
                if (t.y > 0.5f) scrimAlpha = Math.max(scrimAlpha, textAlpha(t, local));
            }
        }
        if (scrimAlpha > 0.001f) {
            placeScreen(width / 2f, height * 0.78f, width, height * 0.44f, 1, 1);
            beginSprite(scrim);
            sprite.setMat4("uMvp", mvp);
            sprite.set1f("uAlpha", 0.75f * scrimAlpha);
            Gl.drawQuad(sprite, quad);
        }

        if (as.logo != null && sc.type == com.productvideostudio.model.Enums.SceneType.CALL_TO_ACTION) {
            float a = Easing.clamp01((local - 0.3f) / 0.5f);
            if (a > 0) {
                float maxW = width * 0.34f, maxH = height * 0.075f;
                float lw = as.logo.width, lh = as.logo.height;
                float s = Math.min(maxW / lw, maxH / lh);
                float sc2 = 0.8f + 0.2f * Easing.outBack(a);
                placeScreen(width / 2f, height * 0.085f, lw * s * sc2, lh * s * sc2, 1, 1);
                beginSprite(as.logo);
                sprite.setMat4("uMvp", mvp);
                sprite.set1f("uAlpha", Easing.outCubic(a));
                float sw = (local - 1.0f) / 1.0f;
                if (sw > 0 && sw < 1) { sprite.set1f("uSweep", -0.5f + 2.5f * sw); sprite.set1f("uSweepGain", 0.5f); }
                Gl.drawQuad(sprite, quad);
            }
        }

        for (int i = 0; i < sc.texts.size(); i++) {
            TextItem t = sc.texts.get(i);
            Gl.Texture tex = as.texts[i];
            if (tex == null) continue;
            float alpha = textAlpha(t, local);
            if (alpha <= 0.001f) continue;
            float aIn = Easing.clamp01((local - t.in) / inDuration(t));
            float aOut = Easing.clamp01((t.out - local) / 0.3f);
            float dx = 0, dy = 0, s = 1, blur = 0, clip = 1;
            switch (t.anim) {
                case SLIDE_UP: dy = (1 - Easing.outCubic(aIn)) * 54; break;
                case SLIDE_LEFT: dx = (1 - Easing.outCubic(aIn)) * 80; break;
                case SCALE: s = 0.7f + 0.3f * Easing.outBack(aIn); break;
                case BOUNCE: s = Math.max(0.01f, Easing.outBounceSoft(aIn)); break;
                case BLUR_REVEAL: blur = (1 - Easing.outCubic(aIn)) * 0.035f; s = 1 + 0.06f * (1 - Easing.outCubic(aIn)); break;
                case TYPE_ON: clip = aIn; break;
                default:
            }
            dy -= (1 - Easing.outCubic(aOut)) * 24;
            if (t.role == TextRole.CTA && aIn >= 1) s *= 1 + 0.025f * (float) Math.sin(2 * Math.PI * 1.1 * (local - t.in));
            float cx = t.x * width + dx, cy = t.y * height + dy;
            placeScreen(cx, cy, tex.width * s, tex.height * s, 1, 1);
            beginSprite(tex);
            sprite.setMat4("uMvp", mvp);
            sprite.set1f("uAlpha", alpha);
            sprite.set1f("uTapBlur", blur);
            sprite.set1f("uClipX", clip >= 1 ? 1f : Math.max(0.001f, clip) * 1.02f);
            if (t.shine) {
                float per = 1.8f;
                float sw = ((local - t.in - 0.5f) % per) / 0.9f;
                if (local - t.in > 0.5f && sw < 1) {
                    sprite.set1f("uSweep", -0.5f + 2.5f * sw);
                    sprite.set1f("uSweepGain", 0.45f);
                }
            }
            Gl.drawQuad(sprite, quad);
        }
    }

    static float inDuration(TextItem t) {
        if (t.anim == TextAnim.TYPE_ON) return Math.min(1.2f, 0.045f * Math.max(4, t.text.length()));
        if (t.anim == TextAnim.BOUNCE) return 0.7f;
        return 0.5f;
    }

    static float textAlpha(TextItem t, float local) {
        if (local < t.in || local > t.out) return 0;
        float aIn = Easing.clamp01((local - t.in) / inDuration(t));
        float aOut = Easing.clamp01((t.out - local) / 0.3f);
        float in;
        switch (t.anim) {
            case TYPE_ON: in = aIn > 0 ? 1 : 0; break;
            case BOUNCE: in = Easing.clamp01(aIn * 4); break;
            default: in = Easing.outCubic(aIn);
        }
        return in * Easing.outCubic(aOut);
    }

    /** Screen-space quad centered at (cx, cy) pixels; the y scale is negated to keep bitmaps upright. */
    private void placeScreen(float cx, float cy, float w, float h, float sx, float sy) {
        Matrix.setIdentityM(model, 0);
        Matrix.translateM(model, 0, cx, cy, 0);
        Matrix.scaleM(model, 0, w * sx, -h * sy, 1);
        Matrix.multiplyMM(mvp, 0, ortho, 0, model, 0);
    }

    // ------------------------------------------------------------------------------------

    private static Bitmap radialBlob() {
        Bitmap b = Bitmap.createBitmap(128, 128, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setShader(new RadialGradient(64, 64, 64, new int[]{0xFF000000, 0x88000000, 0x00000000},
                new float[]{0f, 0.45f, 1f}, Shader.TileMode.CLAMP));
        c.drawCircle(64, 64, 64, p);
        return b;
    }

    private static Bitmap scrimGradient() {
        int h = 256;
        int[] px = new int[4 * h];
        for (int y = 0; y < h; y++) {
            float t = y / (float) (h - 1);
            int a = Math.round(255 * t * t * (3 - 2 * t));
            for (int x = 0; x < 4; x++) px[y * 4 + x] = a << 24;
        }
        return Bitmap.createBitmap(px, 4, h, Bitmap.Config.ARGB_8888);
    }

    void release() {
        sprite.release();
        backdrop.release();
        transition.release();
        gradeProg.release();
        fboA.release();
        fboB.release();
        fboC.release();
        blob.release();
        scrim.release();
    }

    static float clamp(float v, float lo, float hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    static float r(int c) { return ((c >> 16) & 0xFF) / 255f; }
    static float g(int c) { return ((c >> 8) & 0xFF) / 255f; }
    static float b(int c) { return (c & 0xFF) / 255f; }

    static int mix(int a, int b, float t) {
        int ar = (a >> 16) & 0xFF, ag = (a >> 8) & 0xFF, ab = a & 0xFF;
        int br = (b >> 16) & 0xFF, bg = (b >> 8) & 0xFF, bb = b & 0xFF;
        return 0xFF000000 | (Math.round(ar + (br - ar) * t) << 16) | (Math.round(ag + (bg - ag) * t) << 8) | Math.round(ab + (bb - ab) * t);
    }
}
