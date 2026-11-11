"""Builds the small icon sizes (assets/icon-small.png and the 16–48 px frames of assets/icon.ico).

The full icon (assets/icon.png) carries the word "Mitsuke", which can't be read below ~64 px. Small sizes get
the same glass tile — navy with a lavender glow top-left and a blue glow bottom-right, a light rim — with a
monogram "M" instead, drawn pixel-aligned for each size. usage: python tools/make_icons.py"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "SF-Pro-Display-Semibold.otf"),
         r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeuib.ttf"]


def squircle(n, s, inset=0.0, exp=5.0):
    a = n / 2 - inset
    pts = []
    for i in range(720):
        t = 2 * math.pi * i / 720
        c, sn = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / exp), c) + n / 2, a * math.copysign(abs(sn) ** (2 / exp), sn) + n / 2))
    return pts


def glow(n, cx, cy, r, color, alpha):
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(r * 0.55))


def tile(size, letter=True):
    S = 8                                                     # supersampling
    n = size * S
    img = Image.new("RGBA", (n, n), (20, 24, 44, 255))
    img.alpha_composite(glow(n, n * 0.12, n * 0.08, n * 0.62, (150, 146, 200), 210))   # lavender, top-left
    img.alpha_composite(glow(n, n * 0.95, n * 0.95, n * 0.60, (104, 132, 222), 220))  # blue, bottom-right
    img.alpha_composite(glow(n, n * 0.5, n * 0.42, n * 0.30, (14, 17, 32), 170))      # dark heart
    if letter:
        font = next((f for f in FONTS if os.path.exists(f)), None)
        fsize = int(n * (0.66 if size <= 20 else 0.62))
        f = ImageFont.truetype(font, fsize) if font else ImageFont.load_default()
        d = ImageDraw.Draw(img)
        bbox = d.textbbox((0, 0), "M", font=f)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (n - w) / 2 - bbox[0]
        y = (n - h) / 2 - bbox[1] + n * 0.01
        x, y = round(x / S) * S, round(y / S) * S              # whole pixels at the final size: crisp stems
        d.text((x, y), "M", font=f, fill=(244, 246, 255, 255))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).polygon(squircle(n, S, inset=S * 0.25), fill=255)
    out = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    rim = Image.new("L", (n, n), 0)                          # glass rim
    ImageDraw.Draw(rim).line(squircle(n, S, inset=S * 0.6) + [squircle(n, S, inset=S * 0.6)[0]],
                             fill=120 if size >= 24 else 80, width=max(S, n // 64))
    white = Image.new("RGBA", (n, n), (255, 255, 255, 0))
    white.putalpha(rim)
    out.alpha_composite(white)
    return out.resize((size, size), Image.LANCZOS)


def main():
    assets = os.path.join(ROOT, "assets")
    big = Image.open(os.path.join(assets, "icon.png")).convert("RGBA")
    small_sizes = [16, 20, 24, 32, 40, 48]
    frames = {s: tile(s) for s in small_sizes}
    for s in (64, 96, 128, 256):
        frames[s] = big.resize((s, s), Image.LANCZOS)
    tile(256).save(os.path.join(assets, "icon-small.png"))
    order = sorted(frames)
    frames[order[-1]].save(os.path.join(assets, "icon.ico"), sizes=[(s, s) for s in order],
                           append_images=[frames[s] for s in order[:-1]])
    sheet = Image.new("RGBA", (sum(order) + 10 * len(order), max(order) + 20), (32, 32, 36, 255))
    x = 10
    for s in order:
        sheet.alpha_composite(frames[s], (x, 10))
        x += s + 10
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "icon-sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out)
    print("icon.ico:", order, "| sheet:", out)


if __name__ == "__main__":
    main()
