"""Снимок полоски вокруг курсора + Windows OCR (pywinrt 4) -> слово под курсором.

Ускорения: снимаем только узкую полоску (по умолчанию 440×72 px), mss создаётся один раз на поток,
кадр BGRA отдаётся в OCR напрямую (без конвертаций), ожидание результата синхронное (.get()).
"""
import ctypes
import re
import threading
from dataclasses import dataclass


@dataclass
class Box:
    text: str
    x: float
    y: float
    w: float
    h: float
    line: int = -1          # номер строки по данным OCR (-1 — неизвестно, группируем по высоте)


@dataclass
class Context:
    """Строка текста вокруг курсора: tokens — слова строки (и следующей строки), idx — слово под курсором,
    tight[i] — между словами i и i+1 почти нет зазора (OCR мог разрезать одно слово), cut_right — строка
    упирается в правый край снимка (продолжение не видно)."""
    tokens: list
    idx: int
    tight: list
    cut_right: bool = False
    cut_left: bool = False
    cut_bottom: bool = False
    mode: str = "raw"            # which recognition pass produced it
    frac: float = 0.5            # cursor position inside the hovered word's box (0 = left edge, 1 = right)
    rects: list = None           # per token: list of (x, y, w, h) boxes — screen pixels once context_at returns
    capture: tuple = None        # the screen rectangle that was recognised (x, y, w, h)

    @property
    def word(self):
        return self.tokens[self.idx]

    def key(self):
        return tuple(self.tokens), self.idx


TIGHT_GAP = 0.18            # зазор меньше 18% высоты строки — это не пробел между словами
# a word broken at the line end: the hyphen is often misread («+», «•», «¬», «=», «~», «—»)
_HYPHEN_END = re.compile(r"[A-Za-zÄÖÜäöüß][-‐‑­–—+•¬=~]{1,2}$")
_HYPHEN_TAIL = re.compile(r"[-‐‑­–—+•¬=~]{1,2}$")


def _rows(boxes):
    """Группировка рамок по строкам (сверху вниз), внутри строки — слева направо."""
    if boxes and all(b.line >= 0 for b in boxes):
        rows = {}
        for b in boxes:
            rows.setdefault(b.line, []).append(b)
        out = [sorted(r, key=lambda b: b.x) for _, r in sorted(rows.items())]
    else:
        out = []
        for b in sorted(boxes, key=lambda b: b.y + b.h / 2):
            cy = b.y + b.h / 2
            for r in out:
                if abs(r[0].y + r[0].h / 2 - cy) < max(r[0].h, b.h) * 0.6:
                    r.append(b)
                    break
            else:
                out.append([b])
        out = [sorted(r, key=lambda b: b.x) for r in out]
    return sorted(out, key=lambda r: min(b.y for b in r))


def _segments(row, lh):
    """Splits a row where words are far apart (another column, another window)."""
    segs, cur = [], [row[0]]
    for a, b in zip(row, row[1:]):
        if b.x - (a.x + a.w) > 2.5 * lh:
            segs.append(cur)
            cur = []
        cur.append(b)
    segs.append(cur)
    return segs


def _same_block(rows, ri, hit):
    """Keeps only the text block the cursor is in: the hovered row's own segment, and neighbouring rows in
    the same column without a large vertical gap. Text of other UI columns or windows is dropped."""
    row = rows[ri]
    if not row:
        return rows, ri
    lh = max(b.h for b in row) or 1
    seg = next(s for s in _segments(row, lh) if any(b is hit for b in s))
    x0, x1 = seg[0].x, seg[-1].x + seg[-1].w
    margin = 0.35 * (x1 - x0) + 3 * lh
    lo, hi = x0 - margin, x1 + margin

    def pick(r):
        if not r:
            return []
        best = max(_segments(r, lh), key=lambda s: max(0.0, min(hi, s[-1].x + s[-1].w) - max(lo, s[0].x)))
        return best if min(hi, best[-1].x + best[-1].w) - max(lo, best[0].x) > 0 else []
    out = [seg]

    def top(r):
        return min(b.y for b in r)

    def bottom(r):
        return max(b.y + b.h for b in r)
    above = out[0]
    for r in reversed(rows[:ri]):                     # walk up; rows of other columns/windows are skipped
        p = pick(r)
        if not p:
            continue
        if top(above) - bottom(p) > 1.6 * lh:         # a gap in our own column ends the block
            break
        out.insert(0, p)
        above = p
    new_ri = len(out) - 1
    below = seg
    for r in rows[ri + 1:]:
        p = pick(r)
        if not p:
            continue
        if top(p) - bottom(below) > 1.6 * lh:
            break
        out.append(p)
        below = p
    return out, new_ri


def build_context(boxes, px, py, img_w, pad_x=2.0, pad_y=3.0, edge=2.0, img_h=None):
    """Строка вокруг слова под курсором (None — курсор не на слове)."""
    hit = pick_box(boxes, px, py, pad_x, pad_y)
    if hit is None:
        return None
    rows = _rows(boxes)
    ri = next(i for i, r in enumerate(rows) if any(b is hit for b in r))
    # слова, обрезанные краем снимка («al» вместо «auf»), — мусор: выбрасываем (кроме слова под курсором)
    cut_left = cut_right = False
    for k, r in enumerate(rows):
        keep = []
        for b in r:
            at_l, at_r = b.x <= edge, b.x + b.w >= img_w - edge
            if (at_l or at_r) and b is not hit:
                if k == ri:
                    cut_left, cut_right = cut_left or at_l, cut_right or at_r
                continue
            keep.append(b)
        rows[k] = keep
    rows, ri = _same_block(rows, ri, hit)
    row = rows[ri]
    cut_right = cut_right or row[-1].x + row[-1].w >= img_w - edge
    cut_left = cut_left or row[0].x <= edge
    i = next(k for k, b in enumerate(row) if b is hit)
    lh = max(b.h for b in row) or 1

    def box(b):
        return (b.x, b.y, b.w, b.h)
    tokens = [b.text for b in row]
    rects = [[box(b)] for b in row]                  # where each token is (capture coordinates)
    tight = [row[k + 1].x - (row[k].x + row[k].w) < TIGHT_GAP * lh for k in range(len(row) - 1)]
    tokens[i] = part_under_cursor(hit.text, hit.x, hit.w, px)
    # перенос: «Küchen-» в конце строки + «tisch» в начале следующей
    nxt = rows[ri + 1] if ri + 1 < len(rows) and rows[ri + 1] else None
    prv = rows[ri - 1] if ri > 0 and rows[ri - 1] else None
    if i == len(row) - 1 and nxt and _HYPHEN_END.search(tokens[i]) and nxt[0].text[:1].islower():
        tokens[i] = _HYPHEN_TAIL.sub("", tokens[i]) + nxt[0].text
        rects[i].append(box(nxt[0]))
        nxt = nxt[1:]
    elif i == 0 and prv and _HYPHEN_END.search(prv[-1].text) and tokens[i][:1].islower():
        tokens[i] = _HYPHEN_TAIL.sub("", prv[-1].text) + tokens[i]
        rects[i].insert(0, box(prv[-1]))
        prv = prv[:-1]

    def gaps(r):
        return [r[k + 1].x - (r[k].x + r[k].w) < TIGHT_GAP * (max(b.h for b in r) or 1) for k in range(len(r) - 1)]
    # the sentence may continue on the following lines (separable particle far away: «Ich räume … / … / auf.»)
    for r in ([nxt] if nxt else []) + [x for x in rows[ri + 2:] if x]:
        tight.append(False)
        tokens += [b.text for b in r]
        rects += [[box(b)] for b in r]
        tight += gaps(r)
    # …or begin on earlier lines (cursor on the particle, verb further up); clause bounds come from punctuation
    for r in reversed([x for x in rows[:max(0, ri - 1)] if x] + ([prv] if prv else [])):
        tokens = [b.text for b in r] + tokens
        rects = [[box(b)] for b in r] + rects
        tight = gaps(r) + [False] + tight
        i += len(r)
    last = next((x for x in reversed(rows) if x), row)
    cut_bottom = img_h is not None and max(b.y + b.h for b in last) >= img_h - edge
    frac = max(0.0, min(1.0, (px - hit.x) / max(1.0, hit.w)))
    return Context(tokens, i, tight, cut_right, cut_left, cut_bottom, frac=frac, rects=rects)


# OCR иногда склеивает соседние слова в один «word» через разделитель: Haus/Wohnung, Küche,Bad


def pick_box(boxes, px, py, pad_x=2.0, pad_y=3.0):
    """Рамка слова строго под курсором: сначала строка (по вертикали), потом слово (по горизонтали).
    Курсор в промежутке между словами или строками -> None (а не «ближайшее» слово)."""
    row = [b for b in boxes if b.y - pad_y <= py <= b.y + b.h + pad_y]
    hit = [b for b in row if b.x - pad_x <= px <= b.x + b.w + pad_x]
    if not hit:
        return None
    # если рамки пересекаются (бывает на стыке), берём ту, чей центр ближе к курсору
    return min(hit, key=lambda b: (abs(b.y + b.h / 2 - py), abs(b.x + b.w / 2 - px)))


def part_under_cursor(text, x, w, px):
    """Если в рамке несколько слов через разделитель — оставить то, над которым курсор
    (позиция символа оценивается пропорционально ширине рамки)."""
    parts = [(m.start(), m.end()) for m in re.finditer(r"[^/\\|·•…,;:()\[\]{}<>«»„“”\"\s–—]+", text)]
    if not parts:
        return text
    if len(parts) == 1:
        return text[parts[0][0]:parts[0][1]]
    i = (px - x) / max(w, 1) * len(text)
    best = min(parts, key=lambda se: 0 if se[0] <= i <= se[1] else min(abs(i - se[0]), abs(i - se[1])))
    return text[best[0]:best[1]]


def pick_word(boxes, px, py, pad_x=2.0, pad_y=3.0):
    b = pick_box(boxes, px, py, pad_x, pad_y)
    return part_under_cursor(b.text, b.x, b.w, px) if b else None


class OcrUnavailable(RuntimeError):
    pass


class Ocr:
    def __init__(self, lang="de", scale=2, half_w=600, half_h=48):
        self.scale, self.half_w, self.half_h = scale, half_w, half_h
        self._tls = threading.local()
        try:
            from winrt.windows.globalization import Language
            from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
            from winrt.windows.media.ocr import OcrEngine
        except ImportError as e:
            raise OcrUnavailable(f"не установлен пакет winrt: {e}") from e
        self._SB, self._fmt, self._alpha = SoftwareBitmap, BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED
        language = Language(lang)
        if not OcrEngine.is_language_supported(language):
            raise OcrUnavailable("lang-missing")
        self.engine = OcrEngine.try_create_from_language(language)
        if self.engine is None:
            raise OcrUnavailable("lang-missing")

    def _sct(self):
        s = getattr(self._tls, "sct", None)
        if s is None:
            import mss
            s = self._tls.sct = (getattr(mss, "MSS", None) or mss.mss)()
        return s

    frozen = None            # (left, top, PIL image): a paused screen — reads come from this picture

    def freeze(self, left, top, w, h):
        """Photographs a whole monitor; until thaw() every read comes from this picture, so text that the game
        hides as soon as the mouse moves (tooltips) stays readable. Returns (w, h, BGRA) for display."""
        from PIL import Image
        shot = self._sct().grab({"left": left, "top": top, "width": w, "height": h})
        self.frozen = (left, top, Image.frombuffer("RGBA", (shot.width, shot.height), shot.bgra, "raw", "BGRA", 0, 1))
        return shot.width, shot.height, shot.bgra

    def thaw(self):
        self.frozen = None

    def grab(self, left, top, w, h):
        """Screen pixels (BGRA). Replaceable: the OCR test bench feeds synthetic game frames through here."""
        fz = self.frozen
        if fz is not None:
            fl, ft, img = fz
            if left < fl + img.width and top < ft + img.height and left + w > fl and top + h > ft:
                part = img.crop((left - fl, top - ft, left - fl + w, top - ft + h))
                return part.width, part.height, part.tobytes("raw", "BGRA")
        shot = self._sct().grab({"left": left, "top": top, "width": w, "height": h})
        return shot.width, shot.height, shot.bgra

    # Recognition passes. "raw" is tried first and is enough for ordinary game text; the others run only when
    # it found no plausible word under the cursor (accept() said no):
    #   upscale — one step more magnification for small or soft text;
    #   bright / dark — keep only the brightest / darkest pixels around the cursor, i.e. lift light (outlined)
    #                   or dark text off a busy scene, as black text on white;
    #   gray — grayscale + autocontrast (+ invert when the background is dark) for low-contrast text.
    PASSES = ("raw", "upscale", "sharp", "bright:0.86", "dark:0.14", "bright:0.93", "bright:0.76", "dark:0.07", "gray")

    def _prepare(self, data, w, h, mode, cy_rel):
        from PIL import Image, ImageFilter, ImageOps
        img = Image.frombuffer("RGBA", (w, h), data, "raw", "BGRA", 0, 1).convert("RGB")
        kind, _, arg = mode.partition(":")
        if kind in ("bright", "dark", "gray"):
            g = img.convert("L")
            band = g.crop((0, max(0, cy_rel - 18), w, min(h, cy_rel + 18)))   # statistics on the line itself
            hist = band.histogram()
            total = sum(hist) or 1

            def pct(p):
                acc = 0
                for v, n in enumerate(hist):
                    acc += n
                    if acc >= total * p:
                        return v
                return 255
            if kind == "bright":                        # light (often outlined) text off a busy scene
                t = max(pct(float(arg)), 100)
                img = g.point(lambda v: 0 if v >= t else 255).convert("RGB")
            elif kind == "dark":
                t = min(pct(float(arg)), 150)
                img = g.point(lambda v: 0 if v <= t else 255).convert("RGB")
            else:
                g = ImageOps.autocontrast(g, cutoff=2)
                if sum(i * n for i, n in enumerate(hist)) / total < 110:
                    g = ImageOps.invert(g)
                img = g.convert("RGB")
        elif kind == "sharp":                           # soft text: blurred or rendered at a lower resolution
            img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=180, threshold=1))
        s = min(4, self.scale + 1) if kind in ("upscale", "sharp") else self.scale
        if s != 1:
            img = img.resize((w * s, h * s), Image.LANCZOS if kind in ("upscale", "sharp") else Image.BICUBIC)
        return img.convert("RGBA").tobytes("raw", "BGRA"), img.width, img.height, s

    def _recognize(self, cx, cy, hw, hh, mode="raw"):
        left, top = max(cx - hw, 0), max(cy - hh, 0)
        w, h, data = self.grab(left, top, hw * 2, hh * 2)
        data, w, h, s = self._prepare(data, w, h, mode, cy - top)
        bmp = self._SB.create_copy_from_buffer(data, self._fmt, w, h, self._alpha)
        res = self.engine.recognize_async(bmp).get()
        boxes = [Box(wd.text, wd.bounding_rect.x, wd.bounding_rect.y, wd.bounding_rect.width, wd.bounding_rect.height, n)
                 for n, line in enumerate(res.lines) for wd in line.words]
        self._last_s = s
        self._last_origin = (left, top, w / s, h / s)
        return boxes, (cx - left) * s, (cy - top) * s, w, h

    def context_at(self, cx, cy, wide=False, accept=None, score=None, good=0.85, size=None):
        """Context of the word under the cursor, or None.
        score(ctx) -> 0..1 rates a reading (is the word a real word? how much of the line is?). Passes run in
        order until one scores >= good; otherwise the best-scoring reading wins. accept(ctx) -> bool is the
        older yes/no form of the same idea."""
        if score is None and accept is not None:
            score = lambda c: 1.0 if accept(c) else 0.0  # noqa: E731
        best, best_s = None, -1.0
        for mode in (self.PASSES if score else ("raw",)):
            ctx = self._context_pass(cx, cy, wide, mode, size)
            if ctx is None:
                continue
            ctx.mode = mode
            if score is None:
                return ctx
            sc = score(ctx)
            if sc > best_s:
                best, best_s = ctx, sc
            if sc >= good:
                break
        return best

    def _context_pass(self, cx, cy, wide, mode, size=None):
        hw, hh = size or (self.half_w * (2 if wide else 1), self.half_h * (2 if wide else 1))
        ctx = None
        for _ in range(2):
            boxes, px, py, w, h = self._recognize(cx, cy, hw, hh, mode)
            s = getattr(self, "_last_s", self.scale)
            b = pick_box(boxes, px, py, pad_x=2 * s, pad_y=3 * s)
            if b is None:
                return None
            edge = 2 * s
            ctx = build_context(boxes, px, py, w, pad_x=2 * s, pad_y=3 * s, edge=edge, img_h=h)
            cut_x = b.x <= edge or b.x + b.w >= w - edge          # слово обрезано краем снимка
            cut_y = b.y <= edge or b.y + b.h >= h - edge
            if not (cut_x or cut_y):
                break
            hw, hh = hw * 2 if cut_x else hw, hh * 2 if cut_y else hh   # переснять шире и повторить
        origin = getattr(self, "_last_origin", None)
        if ctx is not None and origin and ctx.rects:     # capture coordinates -> screen pixels
            left, top, cw, ch = origin
            ctx.rects = [[(left + x / s, top + y / s, w_ / s, h_ / s) for x, y, w_, h_ in rs] for rs in ctx.rects]
            ctx.capture = (left, top, cw, ch)
        return ctx

    def peek_below(self, ctx):
        """Reads the band right under the last line of the block at extra magnification and appends what it
        finds. Windows OCR often misses a short word that sits alone on a new line («… Training / an.»)."""
        if not ctx or not ctx.rects:
            return None
        flat = [r for rs in ctx.rects for r in rs]
        lh = max(r[3] for r in flat) or 12
        x0 = int(min(r[0] for r in flat)) - int(lh)
        x1 = int(max(r[0] + r[2] for r in flat)) + int(lh)
        y0 = int(max(r[1] + r[3] for r in flat)) + 1
        h = int(lh * 2.4)
        w = max(40, x1 - x0)
        left, top = max(0, x0), max(0, y0)
        cw, ch, data = self.grab(left, top, w, h)
        from PIL import Image
        img = Image.frombuffer("RGBA", (cw, ch), data, "raw", "BGRA", 0, 1).convert("RGB")
        s = 4
        img = img.resize((cw * s, ch * s), Image.LANCZOS)
        bmp = self._SB.create_copy_from_buffer(img.convert("RGBA").tobytes("raw", "BGRA"), self._fmt,
                                               img.width, img.height, self._alpha)
        res = self.engine.recognize_async(bmp).get()
        lines = [[wd for wd in line.words] for line in res.lines]
        if not lines:
            return None
        first = sorted(lines, key=lambda ln: min(wd.bounding_rect.y for wd in ln))[0]
        first = sorted(first, key=lambda wd: wd.bounding_rect.x)
        extra = [wd.text for wd in first]
        rects = [[(left + wd.bounding_rect.x / s, top + wd.bounding_rect.y / s,
                   wd.bounding_rect.width / s, wd.bounding_rect.height / s)] for wd in first]
        from dataclasses import replace
        return replace(ctx, tokens=list(ctx.tokens) + extra, tight=list(ctx.tight) + [False] * len(extra),
                       rects=list(ctx.rects) + rects)

    def sentence_at(self, cx, cy, score=None):
        """The whole text block around the cursor — a paragraph, a tooltip — read in one large capture."""
        return self.context_at(cx, cy, score=score, good=0.7, size=(max(self.half_w, 700), 260))

    def word_at(self, cx, cy):
        ctx = self.context_at(cx, cy)
        return ctx.word if ctx else None


def cursor_pos():
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    p = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y
