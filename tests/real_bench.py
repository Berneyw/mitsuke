"""Hover test on real game screenshots (tests/real/*.png — kept local, not in the repository).

Every word that a careful full-frame OCR finds is hovered through exactly the app's path (strip capture, OCR
passes, wide recapture, parser, dictionary). Reports words read differently than the reference, and words
that end up with no dictionary entry. usage: python tests/real_bench.py [frame.png ...]"""
import glob
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PIL import Image  # noqa: E402

from config import Config, data_dir  # noqa: E402
from dictcore import clean_token  # noqa: E402
from engine import Engine  # noqa: E402
from ocrword import Ocr  # noqa: E402


class FrameGrab:
    def __init__(self, frame):
        self.frame = frame

    def __call__(self, left, top, w, h):
        canvas = Image.new("RGB", (w, h), self.frame.getpixel((0, 0)))
        canvas.paste(self.frame, (-left, -top))
        return w, h, canvas.convert("RGBA").tobytes("raw", "BGRA")


def reference_words(ocr, frame):
    """Words of the whole frame read in tiles at 2x (the reference), as (text, cx, cy)."""
    out, seen = [], set()
    W, H = frame.size
    for ty in range(0, H, 180):
        for tx in range(0, W, 640):
            boxes, _px, _py, _w, _h = ocr._recognize(tx + 320, ty + 90, 330, 100, "upscale")
            s = ocr._last_s
            left, top = ocr._last_origin[:2]
            for b in boxes:
                cx, cy = left + (b.x + b.w / 2) / s, top + (b.y + b.h / 2) / s
                key = (round(cx / 12), round(cy / 12))
                t = clean_token(b.text)
                if len(t) < 3 or not any(ch.isalpha() for ch in t) or key in seen:
                    continue
                if not (8 < cx < W - 8 and 8 < cy < H - 8):
                    continue
                seen.add(key)
                out.append((b.text, int(cx), int(cy)))
    return out


def run(paths):
    eng = Engine(Config(), data_dir())
    d = eng.dict
    result = {}

    def work():
        ocr = Ocr("de", scale=2)
        ocr.half_w = 600
        for p in paths:
            frame = Image.open(p).convert("RGB")
            ocr.grab = FrameGrab(frame)
            rows = []
            for text, cx, cy in reference_words(ocr, frame):
                ctx = ocr.context_at(cx, cy, score=eng.reading_score)
                entries, word = eng.lookup_context(ctx) if ctx else ([], "")
                word = word or (ctx.word if ctx else "")
                rows.append((text, word, entries[0].word if entries else "", (cx, cy)))
            result[p] = rows

    th = threading.Thread(target=work)
    th.start()
    th.join()
    total = misread = missing = 0
    for p, rows in result.items():
        print(f"\n== {os.path.basename(p)}: {len(rows)} words")
        for ref, read, got, (cx, cy) in rows:
            total += 1
            bad_read = clean_token(read).lower() != clean_token(ref).lower()
            bad_entry = not got
            misread += bad_read
            missing += bad_entry
            if bad_read or bad_entry:
                print(f"  {ref!r:28} read {read!r:28} -> {got or '—':24} @({cx},{cy})")
    print(f"\n{total} words: read differently {misread}, no dictionary entry {missing}")


if __name__ == "__main__":
    run(sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "tests", "real", "*.png"))))
