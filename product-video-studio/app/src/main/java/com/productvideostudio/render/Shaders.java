package com.productvideostudio.render;

/** GLSL ES 1.0 sources. All textures hold premultiplied alpha (Android bitmaps do). */
final class Shaders {
    private Shaders() {}

    static final String HEADER =
            "#ifdef GL_FRAGMENT_PRECISION_HIGH\n precision highp float;\n#else\n precision mediump float;\n#endif\n";

    /** Quad in model space (-0.5..0.5) with an MVP; v = 0 at the top of the image. */
    static final String SPRITE_VS =
            "attribute vec4 aPos;\n" +
            "attribute vec2 aUv;\n" +
            "uniform mat4 uMvp;\n" +
            "varying vec2 vUv;\n" +
            "void main() { vUv = aUv; gl_Position = uMvp * aPos; }\n";

    /**
     * Product photos, cutouts, text and overlays. Supports mip blur, tap blur, motion blur,
     * flat tint (shadows, glow), a light sweep, rounded corners, reflection fade and a
     * left-to-right reveal clip.
     */
    static final String SPRITE_FS = HEADER +
            "varying vec2 vUv;\n" +
            "uniform sampler2D uTex;\n" +
            "uniform vec2 uTexel;\n" +
            "uniform float uAlpha;\n" +
            "uniform float uLod;\n" +
            "uniform float uTapBlur;\n" +
            "uniform vec2 uMotion;\n" +
            "uniform float uSweep;\n" +
            "uniform float uSweepGain;\n" +
            "uniform vec4 uTint;\n" +
            "uniform float uBrightness;\n" +
            "uniform float uBackFlip;\n" +
            "uniform float uFade;\n" +
            "uniform float uCorner;\n" +
            "uniform float uAspect;\n" +
            "uniform float uClipX;\n" +
            "vec4 tap(vec2 uv) { return texture2D(uTex, uv, uLod); }\n" +
            "void main() {\n" +
            "  vec2 uv = vUv;\n" +
            "  float bright = uBrightness;\n" +
            "  if (uBackFlip > 0.5 && !gl_FrontFacing) { uv.x = 1.0 - uv.x; bright *= 0.6; }\n" +
            "  vec4 c;\n" +
            "  if (dot(uMotion, uMotion) > 1e-7) {\n" +
            "    c = vec4(0.0);\n" +
            "    for (int i = 0; i < 9; i++) { float f = float(i) / 8.0 - 0.5; c += tap(uv + uMotion * f); }\n" +
            "    c /= 9.0;\n" +
            "  } else if (uLod > 0.05 || uTapBlur > 0.0) {\n" +
            "    vec2 r = uTexel * exp2(uLod) * 1.2 + vec2(uTapBlur, uTapBlur * uAspect);\n" +
            "    c = tap(uv) * 0.2;\n" +
            "    c += tap(uv + vec2( r.x, 0.0)) * 0.1; c += tap(uv + vec2(-r.x, 0.0)) * 0.1;\n" +
            "    c += tap(uv + vec2(0.0,  r.y)) * 0.1; c += tap(uv + vec2(0.0, -r.y)) * 0.1;\n" +
            "    c += tap(uv + r * 0.7) * 0.1; c += tap(uv - r * 0.7) * 0.1;\n" +
            "    c += tap(uv + vec2(r.x, -r.y) * 0.7) * 0.1; c += tap(uv + vec2(-r.x, r.y) * 0.7) * 0.1;\n" +
            "  } else {\n" +
            "    c = texture2D(uTex, uv);\n" +
            "  }\n" +
            "  c.rgb *= bright;\n" +
            "  c.rgb = mix(c.rgb, uTint.rgb * c.a, uTint.a);\n" +
            "  if (uSweepGain > 0.0) {\n" +
            "    float s = (uv.x * 0.8 + uv.y * 0.5) - uSweep;\n" +
            "    float band = exp(-s * s / 0.012) + 0.35 * exp(-s * s / 0.08);\n" +
            "    c.rgb += band * uSweepGain * c.a;\n" +
            "  }\n" +
            "  float a = uAlpha;\n" +
            "  if (uFade > 0.0) a *= smoothstep(1.0 - uFade, 1.0, uv.y);\n" +
            "  if (uCorner > 0.0) {\n" +
            "    vec2 q = (vUv - 0.5) * vec2(uAspect, 1.0);\n" +
            "    vec2 hs = vec2(uAspect, 1.0) * 0.5 - vec2(uCorner);\n" +
            "    float dd = length(max(abs(q) - hs, 0.0)) - uCorner;\n" +
            "    a *= 1.0 - smoothstep(-0.004, 0.004, dd);\n" +
            "  }\n" +
            "  if (uClipX < 1.0) a *= 1.0 - smoothstep(uClipX - 0.02, uClipX, vUv.x);\n" +
            "  gl_FragColor = c * a;\n" +
            "}\n";

    /** Full-screen pass; uv (0,0) = bottom-left, matching framebuffer textures. */
    static final String FULL_VS =
            "attribute vec4 aPos;\n" +
            "varying vec2 vUv;\n" +
            "void main() { vUv = aPos.xy + 0.5; gl_Position = vec4(aPos.xy * 2.0, 0.0, 1.0); }\n";

    /** Studio backdrop: radial gradient, soft spotlight, floor and dithering. */
    static final String BACKDROP_FS = HEADER +
            "varying vec2 vUv;\n" +
            "uniform vec3 uInner;\n" +
            "uniform vec3 uOuter;\n" +
            "uniform vec2 uCenter;\n" +
            "uniform float uAspect;\n" +
            "uniform float uFloor;\n" +
            "uniform float uSpot;\n" +
            "uniform float uExposure;\n" +
            "float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }\n" +
            "void main() {\n" +
            "  vec2 d = (vUv - uCenter) * vec2(uAspect, 1.0);\n" +
            "  float r = length(d);\n" +
            "  vec3 col = mix(uInner, uOuter, smoothstep(0.0, 0.9, r));\n" +
            "  col += uSpot * exp(-r * r / 0.05) * (uInner * 0.6 + 0.08);\n" +
            "  if (uFloor > 0.0) {\n" +
            "    float below = smoothstep(uFloor + 0.004, uFloor - 0.05, vUv.y);\n" +
            "    col = mix(col, col * (0.78 + 0.22 * vUv.y / uFloor), below);\n" +
            "  }\n" +
            "  col *= uExposure;\n" +
            "  col += (hash(gl_FragCoord.xy) - 0.5) / 255.0;\n" +
            "  gl_FragColor = vec4(col, 1.0);\n" +
            "}\n";

    /** Two scenes in, one out. uType selects the transition. */
    static final String TRANSITION_FS = HEADER +
            "varying vec2 vUv;\n" +
            "uniform sampler2D uA;\n" +
            "uniform sampler2D uB;\n" +
            "uniform float uP;\n" +
            "uniform int uType;\n" +
            "uniform vec2 uDir;\n" +
            "uniform float uTime;\n" +
            "uniform vec3 uLeak;\n" +
            "float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }\n" +
            "float noise(vec2 p) {\n" +
            "  vec2 i = floor(p); vec2 f = fract(p); f = f * f * (3.0 - 2.0 * f);\n" +
            "  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);\n" +
            "}\n" +
            "float fbm(vec2 p) { return 0.5 * noise(p) + 0.25 * noise(p * 2.1) + 0.125 * noise(p * 4.3); }\n" +
            "vec4 sA(vec2 uv) { return texture2D(uA, clamp(uv, 0.0, 1.0)); }\n" +
            "vec4 sB(vec2 uv) { return texture2D(uB, clamp(uv, 0.0, 1.0)); }\n" +
            "vec4 blurA(vec2 uv, vec2 dir) { vec4 c = vec4(0.0); for (int i = 0; i < 9; i++) { c += sA(uv + dir * (float(i) / 8.0 - 0.5)); } return c / 9.0; }\n" +
            "vec4 blurB(vec2 uv, vec2 dir) { vec4 c = vec4(0.0); for (int i = 0; i < 9; i++) { c += sB(uv + dir * (float(i) / 8.0 - 0.5)); } return c / 9.0; }\n" +
            "vec4 discA(vec2 uv, float r) { return (sA(uv) * 2.0 + sA(uv + vec2(r, 0.0)) + sA(uv - vec2(r, 0.0)) + sA(uv + vec2(0.0, r * 0.56)) + sA(uv - vec2(0.0, r * 0.56)) + sA(uv + vec2(r, r * 0.56) * 0.7) + sA(uv - vec2(r, r * 0.56) * 0.7)) / 8.0; }\n" +
            "vec4 discB(vec2 uv, float r) { return (sB(uv) * 2.0 + sB(uv + vec2(r, 0.0)) + sB(uv - vec2(r, 0.0)) + sB(uv + vec2(0.0, r * 0.56)) + sB(uv - vec2(0.0, r * 0.56)) + sB(uv + vec2(r, r * 0.56) * 0.7) + sB(uv - vec2(r, r * 0.56) * 0.7)) / 8.0; }\n" +
            "float ease(float t) { return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0; }\n" +
            "void main() {\n" +
            "  vec2 uv = vUv; float p = clamp(uP, 0.0, 1.0);\n" +
            "  vec4 c;\n" +
            "  if (uType == 1) {\n" +              // FADE (through black)
            "    c = p < 0.5 ? sA(uv) * (1.0 - smoothstep(0.0, 0.5, p)) : sB(uv) * smoothstep(0.5, 1.0, p);\n" +
            "  } else if (uType == 2) {\n" +       // DISSOLVE (grainy)
            "    float n = hash(floor(uv * vec2(270.0, 480.0)));\n" +
            "    float m = smoothstep(0.0, 1.0, clamp(p * 1.5 - 0.25 + (n - 0.5) * 0.5, 0.0, 1.0));\n" +
            "    c = mix(sA(uv), sB(uv), m);\n" +
            "  } else if (uType == 3) {\n" +       // ZOOM (radial blur punch)
            "    float e = ease(p);\n" +
            "    vec2 ca = 0.5 + (uv - 0.5) / (1.0 + e * 0.9);\n" +
            "    vec2 cb = 0.5 + (uv - 0.5) * (1.35 - 0.35 * e);\n" +
            "    float s = sin(3.14159 * p) * 0.12;\n" +
            "    vec4 a = vec4(0.0); vec4 b = vec4(0.0);\n" +
            "    for (int i = 0; i < 8; i++) { float f = float(i) / 7.0; a += sA(ca - (ca - 0.5) * s * f); b += sB(cb - (cb - 0.5) * s * f); }\n" +
            "    c = mix(a / 8.0, b / 8.0, smoothstep(0.4, 0.6, p));\n" +
            "  } else if (uType == 4 || uType == 5) {\n" + // PUSH / WHIP PAN
            "    float e = ease(p);\n" +
            "    vec2 oa = uv + uDir * e; vec2 ob = uv + uDir * (e - 1.0);\n" +
            "    bool inA = oa.x >= 0.0 && oa.x <= 1.0 && oa.y >= 0.0 && oa.y <= 1.0;\n" +
            "    if (uType == 5) {\n" +
            "      vec2 bl = uDir * sin(3.14159 * p) * 0.35;\n" +
            "      c = inA ? blurA(oa, bl) : blurB(ob, bl);\n" +
            "    } else { c = inA ? sA(oa) : sB(ob); }\n" +
            "  } else if (uType == 6) {\n" +       // FLASH
            "    vec4 base = p < 0.5 ? sA(uv) : sB(uv);\n" +
            "    float w = pow(1.0 - abs(p - 0.5) * 2.0, 1.6);\n" +
            "    c = mix(base, vec4(1.0), w * 0.97);\n" +
            "  } else if (uType == 7) {\n" +       // BLUR
            "    float r = sin(3.14159 * p) * 0.045;\n" +
            "    c = mix(discA(uv, r), discB(uv, r), smoothstep(0.35, 0.65, p));\n" +
            "  } else if (uType == 8) {\n" +       // SWIPE (soft diagonal wipe with a light edge)
            "    vec2 dir = normalize(uDir + vec2(0.0, 0.35));\n" +
            "    float pos = dot(uv - 0.5, dir) / 0.62 + 0.5;\n" +
            "    float e = ease(p) * 1.2 - 0.1;\n" +
            "    float m = smoothstep(e - 0.03, e + 0.03, pos);\n" +
            "    c = mix(sB(uv), sA(uv), m);\n" +
            "    float edge = (pos - e) / 0.02;\n" +
            "    c.rgb += exp(-edge * edge) * 0.35;\n" +
            "  } else if (uType == 9) {\n" +       // MORPH (luminance displacement)
            "    vec4 a0 = sA(uv); vec4 b0 = sB(uv);\n" +
            "    float la = dot(a0.rgb, vec3(0.33)); float lb = dot(b0.rgb, vec3(0.33));\n" +
            "    vec2 da = vec2(lb - 0.5, la - 0.5) * p * 0.12;\n" +
            "    vec2 db = vec2(la - 0.5, lb - 0.5) * (1.0 - p) * 0.12;\n" +
            "    c = mix(sA(uv + da), sB(uv - db), smoothstep(0.2, 0.8, p));\n" +
            "  } else if (uType == 10) {\n" +      // LIGHT LEAK
            "    c = mix(sA(uv), sB(uv), smoothstep(0.3, 0.7, p));\n" +
            "    float s = sin(3.14159 * p);\n" +
            "    vec2 c1 = vec2(0.15 + 0.7 * p, 0.8 - 0.3 * p); vec2 c2 = vec2(0.9 - 0.5 * p, 0.2 + 0.4 * p);\n" +
            "    float g = exp(-dot(uv - c1, uv - c1) / 0.09) + 0.7 * exp(-dot(uv - c2, uv - c2) / 0.06);\n" +
            "    c.rgb += uLeak * g * s * 0.7 + vec3(0.07, 0.03, 0.0) * s;\n" +
            "  } else if (uType == 11) {\n" +      // FILM BURN
            "    float n = fbm(uv * vec2(3.0, 5.0) + vec2(uTime * 0.7, uTime * 0.3));\n" +
            "    float s = sin(3.14159 * p);\n" +
            "    float burn = smoothstep(1.0 - s * 0.9, 1.05 - s * 0.5, n + uv.x * 0.25 * s);\n" +
            "    c = mix(sA(uv), sB(uv), smoothstep(0.45, 0.55, p));\n" +
            "    vec3 fire = mix(vec3(0.9, 0.25, 0.02), vec3(1.0, 0.92, 0.7), burn);\n" +
            "    c.rgb = mix(c.rgb, fire, burn * s);\n" +
            "    c.rgb += vec3(0.25, 0.08, 0.0) * s * s;\n" +
            "  } else {\n" +                       // CUT
            "    c = p < 0.5 ? sA(uv) : sB(uv);\n" +
            "  }\n" +
            "  gl_FragColor = vec4(c.rgb, 1.0);\n" +
            "}\n";

    /** Color grading: exposure, contrast, saturation, split toning, temperature, vignette, grain. */
    static final String GRADE_FS = HEADER +
            "varying vec2 vUv;\n" +
            "uniform sampler2D uTex;\n" +
            "uniform float uExposure;\n" +
            "uniform float uContrast;\n" +
            "uniform float uSaturation;\n" +
            "uniform vec3 uShadows;\n" +
            "uniform vec3 uHighlights;\n" +
            "uniform vec3 uBalance;\n" +
            "uniform float uLift;\n" +
            "uniform float uVignette;\n" +
            "uniform float uGrain;\n" +
            "uniform float uTime;\n" +
            "uniform float uFlash;\n" +
            "float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }\n" +
            "void main() {\n" +
            "  vec3 c = texture2D(uTex, vUv).rgb;\n" +
            "  c *= uExposure * uBalance;\n" +
            "  c = (c - 0.5) * uContrast + 0.5;\n" +
            "  float l = dot(clamp(c, 0.0, 1.0), vec3(0.2126, 0.7152, 0.0722));\n" +
            "  c = mix(vec3(l), c, uSaturation);\n" +
            "  c += uShadows * (1.0 - l) * (1.0 - l) + uHighlights * l * l;\n" +
            "  c = uLift + c * (1.0 - uLift);\n" +
            "  vec2 q = (vUv - 0.5) * vec2(0.5625, 1.0) * 1.6;\n" +
            "  c *= 1.0 - uVignette * smoothstep(0.35, 1.0, length(q));\n" +
            "  c += (hash(vUv * 1000.0 + uTime) - 0.5) * uGrain;\n" +
            "  c = mix(c, vec3(1.0), uFlash);\n" +
            "  gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);\n" +
            "}\n";
}
