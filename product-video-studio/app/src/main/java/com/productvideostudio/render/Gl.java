package com.productvideostudio.render;

import android.graphics.Bitmap;
import android.opengl.EGL14;
import android.opengl.EGLConfig;
import android.opengl.EGLContext;
import android.opengl.EGLDisplay;
import android.opengl.EGLExt;
import android.opengl.EGLSurface;
import android.opengl.GLES20;
import android.opengl.GLUtils;
import android.view.Surface;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.HashMap;
import java.util.Map;

/** Small OpenGL ES 2.0 toolkit: EGL setup for the encoder surface, programs, textures, FBOs. */
final class Gl {
    private Gl() {}

    private static final int EGL_RECORDABLE_ANDROID = 0x3142;

    /** EGL display/context bound to a {@link Surface} (the video encoder's input). */
    static final class Egl {
        EGLDisplay display = EGL14.EGL_NO_DISPLAY;
        EGLContext context = EGL14.EGL_NO_CONTEXT;
        EGLSurface surface = EGL14.EGL_NO_SURFACE;

        Egl(Surface window) {
            display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
            int[] version = new int[2];
            if (!EGL14.eglInitialize(display, version, 0, version, 1)) throw new RuntimeException("eglInitialize failed");
            int[] attribs = {
                    EGL14.EGL_RED_SIZE, 8, EGL14.EGL_GREEN_SIZE, 8, EGL14.EGL_BLUE_SIZE, 8, EGL14.EGL_ALPHA_SIZE, 8,
                    EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
                    EGL_RECORDABLE_ANDROID, 1,
                    EGL14.EGL_NONE};
            EGLConfig[] configs = new EGLConfig[1];
            int[] num = new int[1];
            if (!EGL14.eglChooseConfig(display, attribs, 0, configs, 0, 1, num, 0) || num[0] == 0) {
                throw new RuntimeException("No recordable EGL config");
            }
            int[] ctxAttribs = {EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE};
            context = EGL14.eglCreateContext(display, configs[0], EGL14.EGL_NO_CONTEXT, ctxAttribs, 0);
            check("eglCreateContext");
            surface = EGL14.eglCreateWindowSurface(display, configs[0], window, new int[]{EGL14.EGL_NONE}, 0);
            check("eglCreateWindowSurface");
            if (!EGL14.eglMakeCurrent(display, surface, surface, context)) throw new RuntimeException("eglMakeCurrent failed");
        }

        void presentationTime(long nanos) {
            EGLExt.eglPresentationTimeANDROID(display, surface, nanos);
        }

        void swap() {
            EGL14.eglSwapBuffers(display, surface);
        }

        void release() {
            if (display != EGL14.EGL_NO_DISPLAY) {
                EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT);
                EGL14.eglDestroySurface(display, surface);
                EGL14.eglDestroyContext(display, context);
                EGL14.eglReleaseThread();
                EGL14.eglTerminate(display);
            }
            display = EGL14.EGL_NO_DISPLAY;
        }

        private static void check(String what) {
            int err = EGL14.eglGetError();
            if (err != EGL14.EGL_SUCCESS) throw new RuntimeException(what + ": EGL error 0x" + Integer.toHexString(err));
        }
    }

    /** A linked program with cached uniform locations. */
    static final class Program {
        final int id;
        final int aPos, aUv;
        private final Map<String, Integer> uniforms = new HashMap<>();

        Program(String vs, String fs) {
            int v = compile(GLES20.GL_VERTEX_SHADER, vs);
            int f = compile(GLES20.GL_FRAGMENT_SHADER, fs);
            id = GLES20.glCreateProgram();
            GLES20.glAttachShader(id, v);
            GLES20.glAttachShader(id, f);
            GLES20.glLinkProgram(id);
            int[] ok = new int[1];
            GLES20.glGetProgramiv(id, GLES20.GL_LINK_STATUS, ok, 0);
            if (ok[0] == 0) throw new RuntimeException("link failed: " + GLES20.glGetProgramInfoLog(id));
            GLES20.glDeleteShader(v);
            GLES20.glDeleteShader(f);
            aPos = GLES20.glGetAttribLocation(id, "aPos");
            aUv = GLES20.glGetAttribLocation(id, "aUv");
        }

        int u(String name) {
            Integer loc = uniforms.get(name);
            if (loc == null) {
                loc = GLES20.glGetUniformLocation(id, name);
                uniforms.put(name, loc);
            }
            return loc;
        }

        void use() { GLES20.glUseProgram(id); }
        void set1f(String n, float v) { GLES20.glUniform1f(u(n), v); }
        void set1i(String n, int v) { GLES20.glUniform1i(u(n), v); }
        void set2f(String n, float a, float b) { GLES20.glUniform2f(u(n), a, b); }
        void set3f(String n, float a, float b, float c) { GLES20.glUniform3f(u(n), a, b, c); }
        void set4f(String n, float a, float b, float c, float d) { GLES20.glUniform4f(u(n), a, b, c, d); }
        void setColor3(String n, int argb) {
            set3f(n, ((argb >> 16) & 0xFF) / 255f, ((argb >> 8) & 0xFF) / 255f, (argb & 0xFF) / 255f);
        }
        void setMat4(String n, float[] m) { GLES20.glUniformMatrix4fv(u(n), 1, false, m, 0); }
        void release() { GLES20.glDeleteProgram(id); }
    }

    static int compile(int type, String src) {
        int s = GLES20.glCreateShader(type);
        GLES20.glShaderSource(s, src);
        GLES20.glCompileShader(s);
        int[] ok = new int[1];
        GLES20.glGetShaderiv(s, GLES20.GL_COMPILE_STATUS, ok, 0);
        if (ok[0] == 0) {
            String log = GLES20.glGetShaderInfoLog(s);
            GLES20.glDeleteShader(s);
            throw new RuntimeException("shader compile failed: " + log);
        }
        return s;
    }

    /** Unit quad (-0.5..0.5) as a triangle strip: x, y, u, v. */
    static FloatBuffer quad() {
        float[] data = {
                -0.5f, 0.5f, 0f, 0f,
                -0.5f, -0.5f, 0f, 1f,
                0.5f, 0.5f, 1f, 0f,
                0.5f, -0.5f, 1f, 1f};
        FloatBuffer fb = ByteBuffer.allocateDirect(data.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        fb.put(data).position(0);
        return fb;
    }

    static void drawQuad(Program p, FloatBuffer quad) {
        quad.position(0);
        GLES20.glVertexAttribPointer(p.aPos, 2, GLES20.GL_FLOAT, false, 16, quad);
        GLES20.glEnableVertexAttribArray(p.aPos);
        if (p.aUv >= 0) {
            quad.position(2);
            GLES20.glVertexAttribPointer(p.aUv, 2, GLES20.GL_FLOAT, false, 16, quad);
            GLES20.glEnableVertexAttribArray(p.aUv);
        }
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
    }

    /** A GPU texture plus its pixel size. */
    static final class Texture {
        final int id, width, height;
        final boolean mipmapped;
        Texture(int id, int width, int height, boolean mipmapped) {
            this.id = id; this.width = width; this.height = height; this.mipmapped = mipmapped;
        }
        void release() { GLES20.glDeleteTextures(1, new int[]{id}, 0); }
    }

    static int largestPot(int v, int max) {
        int p = 1;
        while (p * 2 <= Math.min(v * 1.25f, max)) p *= 2;
        return Math.max(1, p);
    }

    /**
     * Uploads a bitmap. With {@code mipmap}, the bitmap is first scaled to power-of-two
     * dimensions (GLES2 requirement) so it can be blurred cheaply via mip bias.
     */
    static Texture upload(Bitmap bmp, boolean mipmap, int maxSize) {
        Bitmap src = bmp;
        if (mipmap) {
            int pw = largestPot(bmp.getWidth(), maxSize), ph = largestPot(bmp.getHeight(), maxSize);
            if (pw != bmp.getWidth() || ph != bmp.getHeight()) src = Bitmap.createScaledBitmap(bmp, pw, ph, true);
        }
        int[] id = new int[1];
        GLES20.glGenTextures(1, id, 0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, id[0]);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER,
                mipmap ? GLES20.GL_LINEAR_MIPMAP_LINEAR : GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, src, 0);
        if (mipmap) GLES20.glGenerateMipmap(GLES20.GL_TEXTURE_2D);
        Texture t = new Texture(id[0], src.getWidth(), src.getHeight(), mipmap);
        if (src != bmp) src.recycle();
        return t;
    }

    /** Offscreen render target. */
    static final class Fbo {
        final int fbo, tex, width, height;

        Fbo(int width, int height) {
            this.width = width;
            this.height = height;
            int[] ids = new int[1];
            GLES20.glGenTextures(1, ids, 0);
            tex = ids[0];
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, tex);
            GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D, 0, GLES20.GL_RGBA, width, height, 0, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, null);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
            GLES20.glGenFramebuffers(1, ids, 0);
            fbo = ids[0];
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, fbo);
            GLES20.glFramebufferTexture2D(GLES20.GL_FRAMEBUFFER, GLES20.GL_COLOR_ATTACHMENT0, GLES20.GL_TEXTURE_2D, tex, 0);
            int status = GLES20.glCheckFramebufferStatus(GLES20.GL_FRAMEBUFFER);
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, 0);
            if (status != GLES20.GL_FRAMEBUFFER_COMPLETE) throw new RuntimeException("FBO incomplete: 0x" + Integer.toHexString(status));
        }

        void bind() {
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, fbo);
            GLES20.glViewport(0, 0, width, height);
        }

        void release() {
            GLES20.glDeleteFramebuffers(1, new int[]{fbo}, 0);
            GLES20.glDeleteTextures(1, new int[]{tex}, 0);
        }
    }

    static void checkError(String where) {
        int e = GLES20.glGetError();
        if (e != GLES20.GL_NO_ERROR) throw new RuntimeException(where + ": GL error 0x" + Integer.toHexString(e));
    }
}
