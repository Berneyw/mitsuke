#version 440
// Liquid Glass material: one pass draws the drop shadow, the refracted + blurred backdrop, the tint,
// the specular rim lit from `light`, an inner reflection on the opposite edge, and anti-aliased corners.
// All lengths are in item pixels. The backdrop texture covers exactly the item rectangle.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    vec4 shape;        // glass rectangle inside the item: x, y, w, h
    float radius;      // corner radius (capped to a capsule)
    float bezel;       // width of the curved rim that bends light
    float refraction;  // displacement at the very edge, px
    float zoom;        // magnification of the centre (1 = none)
    float dispersion;  // chromatic aberration on the rim, 0..1
    float blur;        // backdrop blur radius, px
    vec4 tint;         // straight-alpha tint over the backdrop
    vec2 light;        // light position, item px (follows the cursor)
    float specular;    // rim highlight strength
    float shadow;      // drop shadow opacity
    float shadowSize;  // drop shadow softness, px
    float hasSource;   // 0: no backdrop, the tint is the whole fill
    float saturation;  // backdrop saturation boost (1 = none)
    float lift;        // 0..1 pressed/dragged state: stronger lens, brighter rim
    float edge;        // hairline rim opacity
    float darkMode;
    vec4 srcRect;      // the item's rectangle inside the backdrop texture, normalized
    vec4 base;         // colour assumed behind transparent backdrop pixels (the window material)
    float fadeBottom;  // px over which the surface fades out at its bottom edge (scroll-edge effect)
    float passAlpha;   // 1: see-through parts of the backdrop stay see-through (the window material shows)
};
layout(binding = 1) uniform sampler2D source;

float sdRound(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

vec4 backdrop(vec2 px, float lod) {               // premultiplied
    vec2 uv = clamp(srcRect.xy + px / itemSize * srcRect.zw, vec2(0.001), vec2(0.999));
    return textureLod(source, uv, lod);
}

vec4 blurred(vec2 px) {
    if (blur < 0.75)
        return backdrop(px, 0.0);
    // golden-angle spiral taps on a mip level matched to the radius: smooth, cheap, no banding
    float lod = max(0.0, log2(blur / 3.0));
    vec4 acc = vec4(0.0);
    const int N = 16;
    for (int i = 0; i < N; ++i) {
        float a = float(i) * 2.39996323;
        float r = blur * sqrt((float(i) + 0.5) / float(N));
        acc += backdrop(px + vec2(cos(a), sin(a)) * r, lod);
    }
    return acc / float(N);
}

void main() {
    vec2 p = qt_TexCoord0 * itemSize;
    vec2 half_ = shape.zw * 0.5;
    vec2 c = shape.xy + half_;
    float r = min(radius, min(half_.x, half_.y));
    vec2 lp = p - c;
    float d = sdRound(lp, half_, r);

    // outward normal from the distance field
    float e = 0.75;
    vec2 n = vec2(sdRound(lp + vec2(e, 0.0), half_, r) - sdRound(lp - vec2(e, 0.0), half_, r),
                  sdRound(lp + vec2(0.0, e), half_, r) - sdRound(lp - vec2(0.0, e), half_, r));
    n = length(n) > 1e-4 ? normalize(n) : vec2(0.0, -1.0);

    // ---- drop shadow (outside the shape), slightly offset down
    float ds = sdRound(lp - vec2(0.0, shadowSize * 0.28), half_, r);
    float sh = shadow * exp(-max(ds, 0.0) * 2.6 / max(shadowSize, 1.0)) * smoothstep(-shadowSize, 0.0, ds);
    float coverage = clamp(0.5 - d, 0.0, 1.0);
    if (fadeBottom > 0.0)
        coverage *= clamp((shape.y + shape.w - p.y) / fadeBottom, 0.0, 1.0);
    if (coverage <= 0.0) {
        fragColor = vec4(0.0, 0.0, 0.0, sh) * qt_Opacity;
        return;
    }

    // ---- lens: a convex rim bends the backdrop inward; the centre can magnify
    float bz = max(bezel, 1.0);
    float t = clamp(1.0 + d / bz, 0.0, 1.0);              // 0 inside the flat part, 1 at the edge
    float profile = 1.0 - sqrt(max(0.0, 1.0 - t * t));    // circular bevel
    float strength = refraction * (1.0 + 0.6 * lift);
    vec2 base0 = c + (p - c) / max(zoom, 0.01);
    vec3 col;
    float srcA = 1.0;
    if (hasSource > 0.5) {
        vec2 disp = -n * strength * profile;
        float k = dispersion * profile;
        vec4 s;
        if (k > 0.002) {
            vec4 g = blurred(base0 + disp);
            s = vec4(blurred(base0 + disp * (1.0 + 0.9 * k)).r, g.g, blurred(base0 + disp * (1.0 - 0.9 * k)).b, g.a);
        } else {
            s = blurred(base0 + disp);
        }
        if (passAlpha > 0.5) {
            srcA = s.a;
            col = s.a > 0.001 ? s.rgb / s.a : vec3(0.0);
        } else {
            col = s.rgb + (1.0 - s.a) * base.rgb;    // see-through parts of the backdrop show `base`
        }
        float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col = mix(vec3(l), col, saturation);
        col = mix(col, tint.rgb, tint.a);
        srcA = srcA + (1.0 - srcA) * tint.a;
    } else {
        col = tint.rgb;
    }

    // ---- light: rim facing the light, a softer inner reflection on the far rim, a faint top sheen
    vec2 ld = light - c;
    ld = length(ld) > 1e-3 ? normalize(ld) : vec2(-0.45, -0.89);
    float rim = smoothstep(-2.2 - 2.0 * lift, 0.0, d);    // thin band at the edge
    float facing = max(dot(n, ld), 0.0);
    float away = max(dot(n, -ld), 0.0);
    float spec = rim * (pow(facing, 2.0) * 0.9 + pow(away, 3.0) * 0.45) * specular * (1.0 + 0.5 * lift);
    float inner = smoothstep(-bz * 0.9, 0.0, d) * (1.0 - rim) * 0.10 * specular * profile;
    float sheen = (1.0 - smoothstep(0.0, half_.y * 1.2, p.y - shape.y)) * 0.05 * specular * (1.0 - darkMode * 0.4);
    // a hot spot travelling with the light, only near the surface edge
    float hot = exp(-pow(length(p - light) / max(min(half_.x, half_.y) * 1.6, 8.0), 2.0)) * 0.10 * specular * profile;
    float L = spec + inner + sheen + hot;
    float fa = hasSource > 0.5 ? srcA : tint.a;         // without a backdrop the tint itself is translucent
    // depth: the lower rim sits a little darker
    vec3 body = col * fa * (1.0 - 0.06 * profile * clamp(n.y, 0.0, 1.0));
    vec3 pm = body + vec3(L);
    float fillA = min(1.0, fa + L);
    // hairline edge so glass reads on any backdrop
    float hair = (1.0 - smoothstep(0.0, 1.2, abs(d + 0.6))) * edge * (0.45 + 0.55 * max(facing, away * 0.6));
    pm = pm * (1.0 - hair) + vec3(hair);
    fillA = fillA * (1.0 - hair) + hair;

    pm *= coverage;
    fillA *= coverage;
    float outA = fillA + sh * (1.0 - fillA);
    fragColor = vec4(pm, outA) * qt_Opacity;
}
