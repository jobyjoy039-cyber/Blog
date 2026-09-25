package com.productvideostudio.render;

import com.productvideostudio.model.Enums.Look;

/** One-tap color looks, expressed as parameters of the grading shader. */
final class Grade {
    float exposure = 1f, contrast = 1f, saturation = 1f, lift = 0f, vignette = 0.2f, grain = 0.012f;
    float[] shadows = {0, 0, 0};
    float[] highlights = {0, 0, 0};
    float[] balance = {1, 1, 1};

    static Grade of(Look look) {
        Grade g = new Grade();
        switch (look) {
            case LUXURY:
                g.contrast = 1.14f; g.saturation = 0.86f; g.vignette = 0.42f; g.exposure = 0.97f;
                g.shadows = new float[]{0.0f, -0.005f, -0.02f};
                g.highlights = new float[]{0.06f, 0.035f, -0.01f};
                g.grain = 0.018f;
                break;
            case MINIMAL:
                g.contrast = 0.94f; g.saturation = 0.88f; g.lift = 0.035f; g.vignette = 0.05f; g.exposure = 1.04f;
                g.grain = 0.006f;
                break;
            case MODERN:
                g.contrast = 1.1f; g.saturation = 1.08f; g.vignette = 0.22f;
                g.shadows = new float[]{-0.01f, 0.01f, 0.03f};
                g.highlights = new float[]{0.02f, 0.01f, 0f};
                break;
            case DARK:
                g.exposure = 0.86f; g.contrast = 1.22f; g.saturation = 0.92f; g.vignette = 0.55f;
                g.shadows = new float[]{-0.01f, -0.01f, 0.0f};
                g.grain = 0.02f;
                break;
            case BRIGHT:
                g.exposure = 1.1f; g.contrast = 1.02f; g.saturation = 1.12f; g.lift = 0.02f; g.vignette = 0.06f;
                break;
            case CINEMATIC:
                g.contrast = 1.16f; g.saturation = 0.95f; g.vignette = 0.36f;
                g.shadows = new float[]{-0.03f, 0.02f, 0.05f};
                g.highlights = new float[]{0.06f, 0.025f, -0.03f};
                g.grain = 0.022f;
                break;
            case PREMIUM:
                g.contrast = 1.1f; g.saturation = 0.95f; g.vignette = 0.28f;
                g.highlights = new float[]{0.03f, 0.02f, 0.0f};
                g.grain = 0.01f;
                break;
            case WARM:
                g.balance = new float[]{1.06f, 1.0f, 0.9f}; g.saturation = 1.05f; g.vignette = 0.18f;
                g.highlights = new float[]{0.03f, 0.015f, 0f};
                break;
            case COOL:
                g.balance = new float[]{0.92f, 1.0f, 1.07f}; g.contrast = 1.06f; g.vignette = 0.2f;
                g.shadows = new float[]{-0.01f, 0.0f, 0.03f};
                break;
            case NATURAL:
            default:
                g.contrast = 1.03f; g.saturation = 1.02f; g.vignette = 0.12f;
        }
        return g;
    }
}
