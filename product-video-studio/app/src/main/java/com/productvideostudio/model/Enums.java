package com.productvideostudio.model;

/**
 * Vocabulary the creative director uses to describe a video. Every value has a human label so
 * the storyboard screen can explain the director's choices.
 */
public final class Enums {
    private Enums() {}

    public enum SceneType {
        HERO_REVEAL("Hero reveal"),
        FRONT_VIEW("Front view"),
        SIDE_VIEW("Side view"),
        TOP_VIEW("Top view"),
        CLOSE_UP("Close-up"),
        MACRO_DETAIL("Macro detail"),
        LIFESTYLE("Lifestyle showcase"),
        FEATURE_HIGHLIGHT("Feature highlight"),
        BENEFITS("Benefits"),
        CALL_TO_ACTION("Call to action");

        public final String label;
        SceneType(String label) { this.label = label; }
    }

    public enum CameraAngle {
        EYE_LEVEL("Eye level", 0, 0),
        LOW_ANGLE("Low angle", -9, 0),
        HIGH_ANGLE("High angle", 9, 0),
        TOP_DOWN("Top-down", 0, 0),
        ANGLE_45("45° angle", 4, 16),
        SIDE_PROFILE("Side profile", 0, 11),
        FRONT("Front", 0, 0),
        REAR("Rear", 0, 180),
        ISOMETRIC("Isometric", 12, 18),
        MACRO("Macro", 0, 0);

        public final String label;
        /** Simulated camera pitch (degrees, + looks down on the product). */
        public final float pitch;
        /** Simulated camera yaw (degrees). REAR shows the mirrored back face. */
        public final float yaw;
        CameraAngle(String label, float pitch, float yaw) {
            this.label = label; this.pitch = pitch; this.yaw = yaw;
        }
    }

    public enum Movement {
        SLOW_ZOOM_IN("Slow zoom in"),
        SLOW_ZOOM_OUT("Slow zoom out"),
        PUSH_IN("Push in"),
        PULL_BACK("Pull back"),
        DOLLY_IN("Dolly in"),
        DOLLY_OUT("Dolly out"),
        TRUCK_LEFT("Truck left"),
        TRUCK_RIGHT("Truck right"),
        PAN_LEFT("Pan left"),
        PAN_RIGHT("Pan right"),
        TILT_UP("Tilt up"),
        TILT_DOWN("Tilt down"),
        CRANE_UP("Crane up"),
        CRANE_DOWN("Crane down"),
        ORBIT_LEFT("Orbit left"),
        ORBIT_RIGHT("Orbit right"),
        ROTATE_360("360° rotation"),
        PARALLAX("Parallax"),
        FLOATING("Floating camera"),
        HANDHELD("Handheld"),
        GIMBAL("Gimbal smooth"),
        RACK_FOCUS("Rack focus"),
        KEN_BURNS("Ken Burns");

        public final String label;
        Movement(String label) { this.label = label; }
    }

    public enum TransitionType {
        CUT("Cut", 0f),
        FADE("Fade", 0.6f),
        DISSOLVE("Dissolve", 0.6f),
        ZOOM("Zoom", 0.45f),
        PUSH("Push", 0.45f),
        WHIP_PAN("Whip pan", 0.36f),
        FLASH("Flash", 0.3f),
        BLUR("Blur", 0.5f),
        SWIPE("Swipe", 0.45f),
        MORPH("Morph", 0.7f),
        LIGHT_LEAK("Light leak", 0.8f),
        FILM_BURN("Film burn", 0.8f);

        public final String label;
        public final float seconds;
        TransitionType(String label, float seconds) { this.label = label; this.seconds = seconds; }
    }

    /** Scene-level effects layered on top of the camera move. */
    public enum Effect {
        LIGHT_SWEEP("Light sweep"),
        SHINE("Shine"),
        GLOW("Glow"),
        SHADOW("Shadow"),
        REFLECTION("Reflection"),
        MOTION_BLUR("Motion blur"),
        SPEED_RAMP("Speed ramp"),
        FREEZE_FRAME("Freeze frame"),
        BLUR_REVEAL("Blur reveal");

        public final String label;
        Effect(String label) { this.label = label; }
    }

    public enum TextAnim {
        FADE, SLIDE_UP, SLIDE_LEFT, SCALE, BOUNCE, BLUR_REVEAL, TYPE_ON
    }

    public enum TextRole {
        PRODUCT_NAME, TAGLINE, FEATURE, BENEFIT, PRICE, DISCOUNT, WEBSITE, CTA, BRAND
    }

    public enum Look {
        LUXURY("Luxury"),
        MINIMAL("Minimal"),
        MODERN("Modern"),
        DARK("Dark"),
        BRIGHT("Bright"),
        CINEMATIC("Cinematic"),
        PREMIUM("Premium"),
        WARM("Warm"),
        COOL("Cool"),
        NATURAL("Natural");

        public final String label;
        Look(String label) { this.label = label; }
    }

    /** The overall creative direction, inferred from the product. Drives every other choice. */
    public enum Mood {
        LUXURY("Luxury", 88, Look.LUXURY),
        TECH("Tech", 118, Look.MODERN),
        NATURE("Natural & organic", 84, Look.NATURAL),
        PLAYFUL("Playful", 124, Look.BRIGHT),
        FASHION("Fashion", 112, Look.CINEMATIC),
        BEAUTY("Beauty", 96, Look.PREMIUM),
        FOOD("Food & drink", 104, Look.WARM),
        SPORT("Sport", 128, Look.DARK),
        HOME("Home", 96, Look.MINIMAL);

        public final String label;
        public final int bpm;
        public final Look look;
        Mood(String label, int bpm, Look look) { this.label = label; this.bpm = bpm; this.look = look; }
    }

    public enum Layout {
        /** Product cut out of a plain background, placed on a studio backdrop. */
        STUDIO,
        /** Photo shown as a floating card on a blurred copy of itself. */
        CARD,
        /** Photo fills the frame. */
        FULL_BLEED
    }

    public enum SfxType {
        WHOOSH, SWOOSH_SOFT, CLICK, POP, SHIMMER, TECH_BLIP, IMPACT, RISER, NATURE_AMBIENCE, CAMERA_SHUTTER
    }

    public static <E extends Enum<E>> E parse(Class<E> type, String name, E fallback) {
        if (name == null) return fallback;
        try {
            return Enum.valueOf(type, name);
        } catch (IllegalArgumentException e) {
            return fallback;
        }
    }
}
