"""Synthetic game-UI OCR bench.

Renders German sentences the way games show them — many fonts, sizes, color schemes, busy scenes, outlines,
translucent panels, and degradations (blur, JPEG, low render resolution, noise) — then sends every frame
through the *production* path: capture strip around a cursor point -> Windows OCR -> line parsing ->
dictionary. Reports how often the word under the cursor is read correctly and the right entry is found.

    python tests/ocr_bench.py                 # ~1200 random samples, real dictionary
    python tests/ocr_bench.py --n 300 --save-fails fails/
"""
import argparse
import collections
import io
import os
import random
import sys
import threading
import time

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dictcore import Dictionary, clean_token  # noqa: E402
from ocrword import Ocr  # noqa: E402

FONT_DIRS = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
             os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")]
FONTS = {
    "Segoe UI": "segoeui.ttf", "Segoe Semibold": "seguisb.ttf", "Arial": "arial.ttf", "Verdana": "verdana.ttf",
    "Tahoma": "tahoma.ttf", "Calibri": "calibri.ttf", "Trebuchet": "trebuc.ttf", "Georgia": "georgia.ttf",
    "Rounded (Sims-like)": "SF-Pro-Rounded-Medium.otf", "Comic Sans": "comic.ttf", "Consolas": "consola.ttf",
}
SIZES = [11, 13, 15, 18, 22]
STYLES = {
    "paper dialog": {"bg": (245, 242, 234), "fg": (29, 42, 58)},
    "white on blue": {"bg": (36, 102, 170), "fg": (255, 255, 255)},
    "dark HUD": {"bg": (28, 30, 36), "fg": (235, 235, 235)},
    "low contrast": {"bg": (120, 130, 140), "fg": (200, 206, 212)},
    "yellow on blue": {"bg": (25, 60, 120), "fg": (255, 214, 10)},
    "outline on scene": {"scene": True, "fg": (255, 255, 255), "stroke": (0, 0, 0)},
    "translucent panel": {"scene": True, "panel": (20, 24, 32, 170), "fg": (240, 240, 240)},
    "gradient": {"gradient": ((70, 140, 200), (240, 240, 250)), "fg": (20, 20, 30)},
}
DEGRADE = ["clean", "blur", "jpeg", "low-res", "noise"]

# (sentence, word under the cursor, entry that must come first)
SENTENCES = [
    ("Ich räume heute das Zimmer auf.", "räume", "aufräumen"),
    ("Ich räume heute das Zimmer auf.", "auf.", "aufräumen"),
    ("Der Kühlschrank ist leer.", "Kühlschrank", "Kühlschrank"),
    ("Die Häuser in der Nachbarschaft sind groß.", "Häuser", "Haus"),
    ("Die Häuser in der Nachbarschaft sind groß.", "Nachbarschaft", "Nachbarschaft"),
    ("Ich freue mich auf das Wochenende.", "freue", "freuen"),
    ("Das mache ich auf jeden Fall morgen.", "jeden", "auf jeden Fall"),
    ("Sag mir bitte Bescheid, wenn du kommst.", "Bescheid,", "Bescheid sagen"),
    ("Er ruft seine Mutter heute Abend an.", "ruft", "anrufen"),
    ("Möchtest du mit mir ins Kino gehen?", "Kino", "Kino"),
    ("Das Essen schmeckt wirklich gut.", "schmeckt", "schmecken"),
    ("Sie hat ihre Schlüssel vergessen.", "Schlüssel", "Schlüssel"),
    ("Er arbeitet als Koch im Restaurant.", "Koch", "Koch"),
    ("Das Badezimmer muss geputzt werden.", "Badezimmer", "Badezimmer"),
    ("Ich habe keine Ahnung, was du meinst.", "Ahnung,", "keine Ahnung"),
    ("Die Straße ist sehr schmal.", "Straße", "Straße"),
    ("Kannst du mir beim Umzug helfen?", "Umzug", "Umzug"),
    ("Das geht mir echt auf die Nerven.", "Nerven.", "auf die Nerven gehen"),
    ("Ich warte seit einer Stunde auf dich.", "warte", "warten"),
    ("Bitte mach das Licht aus.", "mach", "ausmachen"),
    ("Sie zieht nächste Woche in eine größere Wohnung um.", "zieht", "umziehen"),
    ("Gemütlichkeit ist ihm sehr wichtig.", "Gemütlichkeit", "Gemütlichkeit"),
    ("Fähigkeit: Kochen Stufe 3", "Fähigkeit:", "Fähigkeit"),
    ("Wir müssen morgen früh aufstehen.", "aufstehen.", "aufstehen"),
]
# held-out set: never used while tuning — guards against overfitting to SENTENCES
HOLDOUT = [
    ("Dein Sim hat Hunger und möchte etwas essen.", "Hunger", "Hunger"),
    ("Der Sim zieht sich schnell an.", "zieht", "anziehen"),
    ("Kannst du bitte den Müll rausbringen?", "Müll", "Müll"),
    ("Sie lädt ihre Freunde zur Party ein.", "lädt", "einladen"),
    ("Er sieht heute sehr müde aus.", "sieht", "aussehen"),
    ("Die Kinder spielen draußen im Schnee.", "draußen", "draußen"),
    ("Ich höre jetzt mit dem Rauchen auf.", "höre", "aufhören"),
    ("Wir fangen morgen mit dem Training an.", "fangen", "anfangen"),
    ("Die Nachbarin bringt einen Kuchen mit.", "bringt", "mitbringen"),
    ("Dein Sim fühlt sich gelangweilt.", "gelangweilt.", "gelangweilt"),
    ("Das Wetter ist heute schön.", "Wetter", "Wetter"),
    ("Bitte ruf mich später zurück.", "ruf", "zurückrufen"),
    ("Sie kauft im Supermarkt ein.", "kauft", "einkaufen"),
    ("Der Fernseher ist kaputt.", "Fernseher", "Fernseher"),
    ("Ich freue mich über das Geschenk.", "freue", "freuen"),
    ("Er macht die Tür zu.", "macht", "zumachen"),
    ("Die Waschmaschine muss repariert werden.", "Waschmaschine", "Waschmaschine"),
    ("Morgen fängt die Schule wieder an.", "fängt", "anfangen"),
    ("Sie schläft auf dem Sofa ein.", "schläft", "einschlafen"),
    ("Dein Sim braucht dringend eine Dusche.", "Dusche.", "Dusche"),
]
W_FRAME, H_FRAME = 1500, 300
LAYOUTS = ["line", "wrap", "paragraph", "hyphen"]
FILLER = ["Heute ist ein schöner Tag.", "Die Nachbarn kommen später vorbei.", "Vergiss nicht, die Pflanzen zu gießen.",
          "Der Hund schläft im Garten.", "Morgen beginnt die Schule wieder."]
# long targets that can be split with a hyphen at a line end
HYPHEN_OK = {"Kühlschrank", "Nachbarschaft", "Badezimmer", "Gemütlichkeit", "Schlüssel", "aufstehen."}


def font_path(name):
    f = FONTS[name]
    return next((os.path.join(d, f) for d in FONT_DIRS if os.path.exists(os.path.join(d, f))), None)


def scene(img, rng):
    d = ImageDraw.Draw(img)
    for _ in range(18):
        x, y = rng.randrange(-100, W_FRAME), rng.randrange(-60, H_FRAME)
        w, h = rng.randrange(60, 380), rng.randrange(40, 220)
        col = tuple(rng.randrange(40, 240) for _ in range(3))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)([x, y, x + w, y + h], fill=col)


def layout_tokens(sentence, target, layout, f, rng):
    """-> list of (text, x_offset, line) with line breaks, and the indexes of the target's visible piece(s)."""
    toks = sentence.split()
    if layout == "paragraph":                         # the sentence sits inside a longer paragraph
        before, after = rng.sample(FILLER, 2)
        toks = before.split() + toks + after.split()
    ti = toks.index(target) if layout != "paragraph" else len(before.split()) + sentence.split().index(target)
    space = f.getlength(" ")
    if layout == "hyphen":                            # target broken across two lines: «Kühl-» / «schrank»
        t = toks[ti]
        cut = max(3, len(t.rstrip(".,:")) // 2)
        line1 = toks[:ti] + [t[:cut] + "-"]
        line2 = [t[cut:]] + toks[ti + 1:]
        out = []
        x = 0
        for k, tok in enumerate(line1):
            out.append((tok, x, 0))
            x += f.getlength(tok) + space
        x = 0
        for tok in line2:
            out.append((tok, x, 1))
            x += f.getlength(tok) + space
        return out, [len(line1) - 1, len(line1)]
    max_w = {"line": 10 ** 6, "wrap": rng.choice([240, 320]), "paragraph": rng.choice([300, 380])}[layout]
    out, x, line = [], 0, 0
    for tok in toks:
        w = f.getlength(tok)
        if x > 0 and x + w > max_w:
            x, line = 0, line + 1
        out.append((tok, x, line))
        x += w + space
    return out, [ti]


def render(sentence, target, font_name, size, style, degrade, layout, rng):
    """-> (frame RGB, cursor point inside the target word)"""
    st = STYLES[style]
    img = Image.new("RGB", (W_FRAME, H_FRAME), st.get("bg", (90, 110, 100)))
    if "gradient" in st:
        a, b = st["gradient"]
        for y in range(H_FRAME):
            t = y / H_FRAME
            ImageDraw.Draw(img).line([(0, y), (W_FRAME, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    if st.get("scene"):
        scene(img, rng)
    f = ImageFont.truetype(font_path(font_name), size)
    lh = round(size * 1.45)
    toks, target_idx = layout_tokens(sentence, target, layout, f, rng)
    nlines = max(t[2] for t in toks) + 1
    x0 = rng.randrange(40, 400)
    y0 = max(16, min(rng.randrange(40, 120), H_FRAME - nlines * lh - 16))
    placed = [(tok, x0 + x, y0 + line * lh, f.getlength(tok)) for tok, x, line in toks]
    y = y0 + (nlines - 1) * lh
    if "panel" in st:
        over = Image.new("RGBA", img.size, (0, 0, 0, 0))
        right = max(p[1] + p[3] for p in placed)
        ImageDraw.Draw(over).rounded_rectangle([x0 - 16, y0 - 12, right + 16, y + lh + 10], 12, fill=st["panel"])
        img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(img)
    for tok, x, y, w in placed:
        kw = {"stroke_width": max(1, size // 9), "stroke_fill": st["stroke"]} if "stroke" in st else {}
        d.text((x, y), tok, font=f, fill=st["fg"], **kw)
    if degrade == "blur":
        img = img.filter(ImageFilter.GaussianBlur(0.8))
    elif degrade == "jpeg":
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=35)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    elif degrade == "low-res":                         # game rendered at 70% and upscaled to the screen
        img = img.resize((int(W_FRAME * 0.7), int(H_FRAME * 0.7)), Image.BILINEAR).resize((W_FRAME, H_FRAME), Image.BILINEAR)
    elif degrade == "noise":
        noise = Image.effect_noise((W_FRAME, H_FRAME), 18).convert("RGB")
        img = Image.blend(img, noise, 0.12)
    tok, x, y, w = placed[rng.choice(target_idx)]      # with a hyphen break: either half of the word
    cx = x + w * rng.uniform(0.15, 0.85)               # any part of the word, not just its centre
    asc, desc = f.getmetrics()
    cy = y + asc * rng.uniform(0.45, 0.8)
    return img, (int(cx), int(cy))


class FrameGrab:
    """Replaces the screen: crops the synthetic frame (padding outside it with the frame's edge colour)."""

    def __init__(self):
        self.frame = None

    def __call__(self, left, top, w, h):
        canvas = Image.new("RGB", (w, h), self.frame.getpixel((0, 0)))
        canvas.paste(self.frame, (-left, -top))
        return w, h, canvas.convert("RGBA").tobytes("raw", "BGRA")


def _may_continue(entries, ctx):
    sys.path.insert(0, ROOT)
    from main import App
    return App._may_continue(entries, ctx)


def run(n, dict_path, save_dir, seed, passes=True, sentences=None):
    rng = random.Random(seed)
    d = Dictionary(dict_path)
    sentences = sentences or SENTENCES

    def accept(c):                                  # same reading score as the app
        return d.reading_score(c.tokens, c.idx, c.tight, frac=c.frac)
    fonts = [f for f in FONTS if font_path(f)]
    # sanity: every expected entry must be what the parser returns on clean text
    usable = []
    for s, t, want in sentences:
        toks = s.split()
        got = d.lookup_context(toks, toks.index(t))[0]
        if got and got[0].word == want:
            usable.append((s, t, want))
        else:
            print(f"  (dictionary/parser baseline fails, skipped) «{s}» [{t}] -> {got[0].word if got else '—'}")
    results = []
    out = {}

    def worker():
        ocr = Ocr("de", scale=2)
        grab = FrameGrab()
        ocr.grab = grab
        for i in range(n):
            s, t, want = rng.choice(usable)
            fnt, size, style, deg = rng.choice(fonts), rng.choice(SIZES), rng.choice(list(STYLES)), rng.choice(DEGRADE)
            layout = rng.choice([x for x in LAYOUTS if x != "hyphen" or t in HYPHEN_OK])
            img, (cx, cy) = render(s, t, fnt, size, style, deg, layout, rng)
            grab.frame = img
            t0 = time.perf_counter()
            ctx = ocr.context_at(cx, cy, score=accept) if passes else ocr.context_at(cx, cy)
            if ctx is not None and passes:                       # same second look as the app (wider/taller)
                ents0, _ = d.lookup_context(ctx.tokens, ctx.idx, ctx.tight, frac=ctx.frac)
                if _may_continue(ents0, ctx):
                    wide = ocr.context_at(cx, cy, wide=True, score=accept)
                    ctx = wide or ctx
                    ents0, _ = d.lookup_context(ctx.tokens, ctx.idx, ctx.tight, frac=ctx.frac)
                    if _may_continue(ents0, ctx):                # same targeted look at the next line
                        more = ocr.peek_below(ctx)
                        if more is not None:
                            e2, _ = d.lookup_context(more.tokens, more.idx, more.tight, frac=more.frac)
                            if e2 and any(e.match for e in e2):
                                ctx = more
            entries, word = d.lookup_context(ctx.tokens, ctx.idx, ctx.tight, frac=ctx.frac) if ctx else ([], "")
            ms = (time.perf_counter() - t0) * 1000
            read_ok = bool(ctx) and clean_token(word or "").lower() == clean_token(t).lower()
            top1 = bool(entries) and entries[0].word == want
            top3 = any(e.word == want for e in entries[:3])
            tier = "realistic" if size >= 13 and deg in ("clean", "jpeg", "noise") else "extreme"
            kind = "ok" if top1 else "not found" if ctx is None else "misread" if not read_ok else "parse"
            r = dict(sentence=s, target=t, want=want, font=fnt, size=size, style=style, degrade=deg, tier=tier,
                      kind=kind, layout=layout, mode=(ctx.mode if ctx else "-"), read=(word or ""),
                      tokens=(ctx.tokens if ctx else None), read_ok=read_ok,
                      top1=top1, top3=top3, got=(entries[0].word if entries else ""), ms=ms)
            results.append(r)
            if save_dir and not top1 and len(os.listdir(save_dir)) < 80:
                im = img.copy()
                ImageDraw.Draw(im).ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=(255, 0, 0), width=2)
                im.save(os.path.join(save_dir, f"{i:04d}_{fnt[:8]}_{size}_{style[:8]}_{deg}.png".replace(" ", "")))
        out["done"] = True

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    th = threading.Thread(target=worker)
    th.start()
    th.join()
    return results


def report(results):
    def pct(rs, k):
        return 100.0 * sum(r[k] for r in rs) / max(1, len(rs))

    print(f"\nSamples: {len(results)}   word read correctly: {pct(results, 'read_ok'):.1f}%   "
          f"right entry first: {pct(results, 'top1'):.1f}%   in top 3: {pct(results, 'top3'):.1f}%   "
          f"median time: {sorted(r['ms'] for r in results)[len(results) // 2]:.0f} ms")
    for dim in ("tier", "kind", "layout", "style", "size", "degrade", "font", "mode"):
        groups = collections.defaultdict(list)
        for r in results:
            groups[r[dim]].append(r)
        print(f"\nby {dim}:")
        for k, rs in sorted(groups.items(), key=lambda kv: pct(kv[1], "top1")):
            print(f"  {str(k):22} n={len(rs):4}  read {pct(rs, 'read_ok'):5.1f}%  entry {pct(rs, 'top1'):5.1f}%")
    fails = [r for r in results if not r["top1"]]
    fails.sort(key=lambda r: r["tier"] != "realistic")          # realistic failures first: they matter most
    print(f"\nexamples of failures ({len(fails)}):")
    for r in fails[:30]:
        print(f"  {r['tier'][:4]} {r['kind']:9} [{r['target']}] {r['font']} {r['size']}px {r['style']} {r['degrade']} {r['layout']} {r['mode']}"
              f" -> read {r['read']!r}, got {r['got']!r}; tokens {r['tokens'][:8] if r['tokens'] else None}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dict", default=os.path.join(os.environ.get("APPDATA", ""), "Mitsuke", "dict.sqlite"))
    ap.add_argument("--save-fails")
    ap.add_argument("--single-pass", action="store_true", help="baseline: no extra recognition passes")
    ap.add_argument("--holdout", action="store_true", help="use the held-out sentence set")
    a = ap.parse_args()
    t0 = time.time()
    res = run(a.n, a.dict, a.save_fails, a.seed, passes=not a.single_pass,
              sentences=HOLDOUT if a.holdout else SENTENCES)
    report(res)
    print(f"\ntotal {time.time() - t0:.0f} s")
