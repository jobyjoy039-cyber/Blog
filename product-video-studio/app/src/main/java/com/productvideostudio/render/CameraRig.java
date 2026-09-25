package com.productvideostudio.render;

import com.productvideostudio.model.Enums.CameraAngle;
import com.productvideostudio.model.Enums.Effect;
import com.productvideostudio.model.Enums.Layout;
import com.productvideostudio.model.Enums.Movement;
import com.productvideostudio.model.Enums.SceneType;
import com.productvideostudio.model.Storyboard.Scene;

/**
 * Turns a named camera move into a virtual-camera pose for any moment of a scene. Photos are 2D,
 * so angles and moves are simulated with perspective, parallax between product and backdrop,
 * and focus changes, which is what reads as camera motion on a phone screen.
 */
public final class CameraRig {
    private CameraRig() {}

    public static final class Pose {
        /** Product/photo transform. Translation is in screen-height units (screen spans y -1..1). */
        public float scale = 1, tx, ty, pitch, yaw, roll;
        /** Blur of the product (mip level). */
        public float blur;
        /** Backdrop layer (parallax): offset, scale and blur. */
        public float bgTx, bgTy, bgScale = 1, bgBlur;
        /** 0 = black, 1 = fully lit. */
        public float exposure = 1;
        /** Light sweep position across the product (-0.5..2), or NaN when off. */
        public float sweep = Float.NaN;
        public float sweepGain = 0.55f;
        /** White flash overlay (freeze frame). */
        public float flash;
        /** Motion-blur vector in texture space. */
        public float motionX, motionY;
    }

    /**
     * @param u      progress through the scene's visible span, 0..1
     * @param local  seconds since the scene's cut point (can be negative during the incoming transition)
     * @param time   seconds since the start of the video (for continuous motion like floating)
     */
    public static Pose pose(Scene sc, float u, float local, float time, float beat) {
        Pose p = new Pose();
        float k = sc.intensity;
        int d = sc.direction;
        boolean full = sc.layout == Layout.FULL_BLEED;

        float e;
        if (sc.has(Effect.SPEED_RAMP)) e = Easing.speedRamp(u);
        else if (sc.has(Effect.FREEZE_FRAME)) e = Easing.inOutSine(Easing.freeze(u, 0.45f, 0.62f));
        else e = Easing.inOutSine(u);

        // Base angle: full-bleed photos can only take a hint of perspective before edges show.
        CameraAngle angle = sc.angle;
        float angleAmount = full ? 0.25f : 1f;
        p.pitch = angle.pitch * angleAmount;
        p.yaw = (angle == CameraAngle.REAR ? 180 : angle.yaw * d) * angleAmount;
        if (angle == CameraAngle.TOP_DOWN) p.roll = d * (-7 + 14 * e);

        switch (sc.movement) {
            case SLOW_ZOOM_IN: p.scale = 1 + 0.10f * k * e; break;
            case SLOW_ZOOM_OUT: p.scale = 1 + 0.10f * k * (1 - e); break;
            case PUSH_IN: {
                float q = Easing.inQuad(u) * 0.6f + e * 0.4f;
                p.scale = 1 + 0.3f * k * q;
                p.pitch *= 1 - 0.4f * q;
                p.bgScale = 1 + 0.08f * q;
                break;
            }
            case PULL_BACK: {
                float q = Easing.outCubic(u);
                p.scale = 1 + 0.3f * k * (1 - q);
                p.bgScale = 1 + 0.08f * (1 - q);
                break;
            }
            case DOLLY_IN:
                p.scale = 1 + 0.2f * k * e;
                p.pitch += 5 * (1 - e) * (full ? 0.3f : 1f);
                p.bgScale = 1 + 0.05f * e;
                break;
            case DOLLY_OUT:
                p.scale = 1 + 0.2f * k * (1 - e);
                p.pitch += 5 * e * (full ? 0.3f : 1f);
                p.bgScale = 1 + 0.05f * (1 - e);
                break;
            case TRUCK_LEFT:
            case TRUCK_RIGHT: {
                int dir = sc.movement == Movement.TRUCK_RIGHT ? 1 : -1;
                p.tx = -dir * (e - 0.5f) * 0.22f * k;
                p.bgTx = p.tx * 0.35f;
                p.scale = full ? 1.04f : 1f;
                break;
            }
            case PAN_LEFT:
            case PAN_RIGHT: {
                int dir = sc.movement == Movement.PAN_RIGHT ? 1 : -1;
                p.yaw += dir * (e - 0.5f) * (full ? 5 : 14) * k;
                p.tx = -dir * (e - 0.5f) * 0.1f * k;
                p.bgTx = -dir * (e - 0.5f) * 0.16f;
                break;
            }
            case TILT_UP:
            case TILT_DOWN: {
                int dir = sc.movement == Movement.TILT_UP ? 1 : -1;
                p.pitch += dir * (e - 0.5f) * (full ? 4 : 12) * k;
                p.ty = dir * (e - 0.5f) * 0.1f * k;
                break;
            }
            case CRANE_UP:
            case CRANE_DOWN: {
                int dir = sc.movement == Movement.CRANE_UP ? 1 : -1;
                float q = dir > 0 ? e : 1 - e;
                p.ty = (0.5f - q) * 0.16f * k;
                p.pitch += (full ? 3 : 12) * (q - 0.5f) * k;
                p.bgTy = -(0.5f - q) * 0.1f;
                p.scale = 1.04f;
                break;
            }
            case ORBIT_LEFT:
            case ORBIT_RIGHT: {
                int dir = sc.movement == Movement.ORBIT_RIGHT ? 1 : -1;
                p.yaw += dir * (-20 + 40 * e) * k * (full ? 0.2f : 1f);
                p.bgTx = -dir * (e - 0.5f) * 0.18f;
                p.scale = 1.02f;
                break;
            }
            case ROTATE_360:
                p.yaw += 360 * Easing.inOutCubic(Easing.clamp01((u - 0.1f) / 0.75f));
                break;
            case PARALLAX:
                p.scale = 1.04f + 0.07f * e * k;
                p.tx = d * (e - 0.5f) * 0.06f * k;
                p.bgTx = -d * (e - 0.5f) * 0.14f;
                p.bgScale = 1.1f;
                break;
            case FLOATING:
                p.ty = 0.022f * (float) Math.sin(2 * Math.PI * time * 0.42);
                p.roll += 1.4f * (float) Math.sin(2 * Math.PI * time * 0.3 + 1);
                p.yaw += 5f * (float) Math.sin(2 * Math.PI * time * 0.24);
                p.scale = 1.02f + 0.04f * e;
                p.bgTy = -p.ty * 0.3f;
                break;
            case HANDHELD:
                p.tx = 0.007f * Easing.noise(time * 2.2f, 11);
                p.ty = 0.007f * Easing.noise(time * 2.0f, 23);
                p.roll = 0.6f * Easing.noise(time * 1.6f, 37);
                p.scale = 1.06f + 0.03f * e;
                break;
            case GIMBAL:
                p.scale = 1.02f + 0.07f * e * k;
                p.tx = d * (e - 0.5f) * 0.05f;
                p.yaw += d * (e - 0.5f) * (full ? 2 : 7);
                p.bgTx = -d * (e - 0.5f) * 0.06f;
                break;
            case RACK_FOCUS:
                p.blur = 4.5f * (1 - Easing.smoothstep(0.08f, 0.5f, u));
                p.bgBlur = 1.5f + 2.5f * Easing.smoothstep(0.08f, 0.5f, u);
                p.scale = 1.03f + 0.05f * e;
                break;
            case KEN_BURNS:
                p.scale = 1 + 0.16f * e * k;
                p.tx = d * 0.05f * (1 - e);
                p.ty = 0.04f * (1 - e);
                break;
            default:
        }

        // Scene-level effects.
        if (sc.type == SceneType.HERO_REVEAL) {
            float reveal = Easing.smoothstep(0f, beat * 1.9f, local);
            p.exposure = 0.12f + 0.88f * reveal;
            if (sc.has(Effect.BLUR_REVEAL)) p.blur = Math.max(p.blur, 5f * (1 - reveal));
        }
        if (sc.has(Effect.LIGHT_SWEEP)) {
            float start = sc.type == SceneType.HERO_REVEAL ? beat * 1.7f : 0.6f;
            float s = (local - start) / 1.1f;
            if (s > 0 && s < 1) p.sweep = -0.5f + 2.5f * Easing.inOutSine(s);
            p.sweepGain = 0.5f;
        }
        if (sc.has(Effect.SHINE)) {
            float period = 2.2f;
            float s = ((local + 0.3f) % period) / 1.0f;
            if (local > 0 && s < 1) p.sweep = -0.5f + 2.5f * s;
            p.sweepGain = 0.35f;
        }
        if (sc.has(Effect.FREEZE_FRAME)) {
            float f = (u - 0.45f) / 0.04f;
            if (f > 0 && f < 1) p.flash = 0.85f * (1 - f);
            else if (f >= 1 && u < 0.62f) p.flash = 0.06f;
        }
        return p;
    }
}
