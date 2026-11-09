"""In-game windows: the word card, the pinned card and the reading highlight.

Live glass: these windows are excluded from screen capture, so we can photograph exactly what is behind
them, many times a second, and hand that picture to the glass shader — the card refracts the moving game.
The tint never lets text contrast drop under 4.5:1: over bright scenes the glass thickens automatically.
"""
import logging
import threading
import time

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage
from PySide6.QtQuick import QQuickImageProvider

import render as R
from . import native

KEY_NAMES = {"shift": "Shift", "ctrl": "Ctrl", "alt": "Alt"}


# ---------------------------------------------------------------- coordinates
def screen_at(px, py):
    """(screen, dpr) for a physical pixel. On Windows a screen's logical top-left equals its native one."""
    for s in QGuiApplication.screens():
        g, r = s.geometry(), s.devicePixelRatio()
        if g.x() <= px < g.x() + g.width() * r and g.y() <= py < g.y() + g.height() * r:
            return s, r
    s = QGuiApplication.primaryScreen()
    return s, s.devicePixelRatio()


def to_logical(px, py):
    s, r = screen_at(px, py)
    g = s.geometry()
    return g.x() + (px - g.x()) / r, g.y() + (py - g.y()) / r, r


def to_physical(lx, ly, r, screen_origin):
    ox, oy = screen_origin
    return ox + (lx - ox) * r, oy + (ly - oy) * r


def _lum(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def min_tint(img, dark, style):
    """Smallest tint opacity that keeps the card's secondary text at 4.5:1 over the *worst* part of this
    backdrop (the brightest patch under a dark card, the darkest under a light one), not just its average."""
    if img is None or img.isNull():
        return 0.0
    small = img.scaled(8, 8)
    cells = []
    for y in range(small.height()):
        for x in range(small.width()):
            c = small.pixelColor(x, y)
            cells.append((c.red(), c.green(), c.blue()))
    worst = max(cells, key=_lum) if dark else min(cells, key=_lum)
    mean = [sum(c[i] for c in cells) / len(cells) for i in range(3)]
    probe = [0.6 * w + 0.4 * m for w, m in zip(worst, mean)]      # blur spreads a patch over its neighbours
    base = {"tinted": (11, 58, 134) if dark else (207, 224, 255),
            "clear": (0, 0, 0) if dark else (255, 255, 255)}.get(style, (28, 28, 31) if dark else (246, 246, 248))
    guard = ((255, 255, 255) if dark else (29, 29, 31)) if style == "clear" else         ((209, 209, 214) if dark else (58, 58, 60))
    a = 0.0
    while a < 0.97:
        mix = [a * b + (1 - a) * m for b, m in zip(base, probe)]
        if contrast(guard, mix) >= 4.5:
            break
        a += 0.03
    return min(0.97, a)


class Backdrop(QQuickImageProvider):
    """image://backdrop/<name>/<frame> — the latest capture behind each glass window."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.images = {}

    def requestImage(self, id_, size, requested):
        img = self.images.get(id_.split("/")[0])
        if img is None:
            img = QImage(2, 2, QImage.Format.Format_RGB32)
            img.fill(0)
        if isinstance(size, QSize):
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img


class Grabber:
    """Screen capture with mss, created lazily on the GUI thread (its device contexts are per thread)."""

    def __init__(self):
        self.sct = None

    def grab(self, x, y, w, h):
        try:
            if self.sct is None:
                import mss
                self.sct = (getattr(mss, "MSS", None) or mss.mss)()
            shot = self.sct.grab({"left": int(x), "top": int(y), "width": max(1, int(w)), "height": max(1, int(h))})
            buf = shot.bgra
            return QImage(buf, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32).copy()
        except Exception:  # noqa — secure desktop, display change…
            logging.debug("capture failed", exc_info=True)
            return None


def polish_tree(item):
    """Run pending layout (Column / Flow positioners lay out lazily) so implicit sizes can be read now."""
    for c in item.childItems():
        polish_tree(c)
    item.ensurePolished()


def measure(win, lines):
    """Height the card needs for these lines, measured synchronously before the window is shown."""
    win.setProperty("lines", lines)
    for _ in range(2):                 # second pass: wrapped text heights settle once widths are known
        polish_tree(win.contentItem())
    return float(win.property("naturalHeight") or 0)


class _LiveGlass:
    """Shared: a window whose glass is fed by live captures of the screen behind it.

    Captures run on a background thread (a GDI grab takes several ms), so the interface never waits for them.
    Adaptive rate: ~60 a second while the window or the pointer moves (dragging a pinned card, sliding along a
    sentence), ~20 when everything is still, so the game keeps its CPU."""
    name = "card"
    fast_s = 1 / 60
    idle_s = 1 / 20

    def __init__(self, gui, win):
        self.gui, self.win = gui, win
        self.timer = QTimer(interval=16, timeout=self.tick)            # cheap: follows position and pointer
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame = 0
        self.dpr = 1.0
        self.origin = (0, 0)
        self._last = None
        self._still_since = 0.0
        self._rect = None
        self._period = self.idle_s
        self._pending = False
        self._thread = None
        self._alive = False
        self._gen = 0

    @property
    def cfg(self):
        return self.gui.app.cfg

    def glass_on(self):
        return self.cfg["glass"] and not self.cfg["reduce_transparency"]

    def phys_rect(self):
        w = self.win
        x, y = to_physical(w.x(), w.y(), self.dpr, self.origin)
        return x, y, w.width() * self.dpr, w.height() * self.dpr

    # ---- GUI thread
    def tick(self):
        if not self.win.isVisible() and self.frame:
            self.stop_capture()
            return
        p = QCursor.pos()
        state = (self.win.x(), self.win.y(), self.win.width(), self.win.height(), p.x(), p.y())
        now = time.perf_counter()
        if state != self._last:
            self._last = state
            self._still_since = now
            self._rect = self.phys_rect() if self.glass_on() else None
        self._period = self.fast_s if now - self._still_since < 0.6 else self.idle_s
        self.win.setProperty("pointer", p - self.win.position())
        if not self.glass_on() and self.win.property("frame"):
            self.win.setProperty("frame", 0)
        self._ensure_thread()

    def capture(self):
        """One synchronous capture (before a window first appears, so it never shows bare tint)."""
        self._rect = self.phys_rect() if self.glass_on() else None
        if self._rect is None:
            self.win.setProperty("frame", 0)
            return
        self._apply(self.gui.grabber.grab(*self._rect), True)

    def _apply(self, img, contrast=True):
        self._pending = False
        if img is None or not self.glass_on():
            return
        self.gui.backdrop.images[self.name] = img
        self.frame += 1
        if contrast:
            self.win.setProperty("minTint", min_tint(img, self.gui.bridge.dark, self.cfg["glass_style"]))
        self.win.setProperty("frame", self.frame)

    def _ensure_thread(self):
        if not self._alive:
            self._alive = True
            self._gen += 1
            self._thread = threading.Thread(target=self._loop, args=(self._gen,), daemon=True, name=f"glass-{self.name}")
            self._thread.start()

    def stop_capture(self):
        self.timer.stop()
        self._alive = False
        self._pending = False

    # ---- capture thread
    def _loop(self, gen):
        grabber = Grabber()                      # its own device contexts: mss is per thread
        n = 0
        while self._alive and gen == self._gen:
            t0 = time.perf_counter()
            rect = self._rect
            if rect and not self._pending:       # never queue frames faster than the GUI shows them
                img = grabber.grab(*rect)
                if img is not None:
                    self._pending = True
                    n += 1
                    self.gui.call(self._apply, img, n % 6 == 0 or self._period == self.idle_s)
            time.sleep(max(0.002, self._period - (time.perf_counter() - t0)))


class CardOverlay(_LiveGlass):
    name = "card"

    def __init__(self, gui):
        super().__init__(gui, gui.create_window("CardWindow.qml"))
        native.overlay_window(int(self.win.winId()), click_through=False)
        self.hide_timer = QTimer(singleShot=True, interval=200, timeout=self._unmap)

    def hide(self):
        if self.win.isVisible() and self.win.property("shown"):
            self.win.setProperty("shown", False)
            self.stop_capture()
            self.hide_timer.start()

    def _unmap(self):
        if not self.win.property("shown"):
            self.win.hide()

    def show_note(self, title, note, x, y, avoid=None):
        self._present([[("title", [("text", title, "word")]), ("para", note, "meta", None)]], x, y, avoid)

    def show(self, entries, query, x, y, source="", avoid=None):
        c = self.cfg
        if not entries:
            self._present([[("title", [("text", query, "word")]), ("para", "Not in the dictionary", "meta", None)]],
                          x, y, avoid)
            return
        base = {"entries": c["card_entries"], "senses": c["card_senses"], "examples": c["card_examples"],
                "german": c["german_definitions"], "german_max": 1, "compact_rest": True}
        levels = [base, dict(base, examples=False), dict(base, examples=False, senses=min(2, base["senses"])),
                  dict(base, examples=False, senses=1, entries=min(2, base["entries"])),
                  dict(base, examples=False, senses=1, entries=1, german=False)]
        variants = [R.build(entries, query, source, o) for o in levels]
        if c["pin_double_tap"]:
            key = KEY_NAMES.get(c["key"], "Shift")
            for v in variants:
                v.append(("para", f"Double-tap {key} to pin this card", "meta", None))
        self._present(variants, x, y, avoid)

    def _present(self, variants, x, y, avoid=None):
        """x, y, avoid: physical pixels (from OCR). The card goes below (or above) the whole text block being
        read, so it never covers the rest of the sentence; detail drops until it fits."""
        self.hide_timer.stop()
        self.last_avoid = avoid
        c, w = self.cfg, self.win
        s, r = screen_at(x, y)
        self.dpr, self.origin = r, (s.geometry().x(), s.geometry().y())
        lx, ly, _ = to_logical(x, y)
        wl, wt, wr, wb = native.work_area(x, y)
        left, top = to_logical(wl, wt)[:2]
        right, bottom = to_logical(wr - 1, wb - 1)[:2]
        width = max(320, min(720, c["card_width"]))
        m = w.property("margin") or 26
        w.setProperty("cardWidth", width)
        w.setProperty("maxCardHeight", 4000)
        below, above_edge = ly + 26, ly - 14
        if avoid:
            a0, a1 = to_logical(x, avoid[0])[1], to_logical(x, avoid[1])[1]
            if a1 - ly < 300 and ly - a0 < 300:
                below = max(below, a1 + 10)
                above_edge = min(above_edge, a0 - 10)
        room_below, room_above = bottom - below - 4, above_edge - top - 4
        prefer_above = c["card_position"] == "above"
        h = 0
        for i, lines in enumerate(variants):
            h = measure(w, R.to_qml(lines))
            first, second = (room_above, room_below) if prefer_above else (room_below, room_above)
            if h <= first or h <= second or i == len(variants) - 1:
                break
        if prefer_above:
            side = "above" if h <= room_above or room_above >= room_below else "below"
        else:
            side = "below" if h <= room_below or room_below >= room_above else "above"
        h = min(h, max(room_below, room_above))
        w.setProperty("maxCardHeight", h)
        cy = below if side == "below" else above_edge - h
        cx = max(left + 4, min(lx - 14, right - width - 4))
        w.setX(int(round(cx - m)))
        w.setY(int(round(cy - m)))
        self.capture()                              # first picture before it appears: no flash of bare tint
        if not w.isVisible():
            w.setProperty("shown", False)
            w.show()
        w.raise_()                                  # above the game and any other topmost window
        w.setProperty("shown", True)
        if not self.timer.isActive():
            self.timer.start()


class Highlighter:
    """The marker over the word being read (see HighlightWindow.qml)."""

    def __init__(self, gui):
        self.gui = gui
        self.win = gui.create_window("HighlightWindow.qml")
        native.overlay_window(int(self.win.winId()), click_through=False)
        self.visible = None

    def show(self, primary, secondary=(), area=None):
        rects = list(primary) + list(secondary) + ([area] if area else [])
        if not rects:
            self.hide()
            return
        key = (tuple(map(tuple, primary)), tuple(map(tuple, secondary)), area)
        if key == self.visible:
            return
        self.visible = key
        pad = 8
        x0 = min(r[0] for r in rects) - pad
        y0 = min(r[1] for r in rects) - pad
        x1 = max(r[0] + r[2] for r in rects) + pad
        y1 = max(r[1] + r[3] for r in rects) + pad
        lx0, ly0, dpr = to_logical(x0, y0)

        def conv(r):
            return {"x": (r[0] - x0) / dpr, "y": (r[1] - y0) / dpr, "w": r[2] / dpr, "h": r[3] / dpr}
        w = self.win
        w.setProperty("primary", [conv(r) for r in primary])
        w.setProperty("secondary", [conv(r) for r in secondary])
        w.setProperty("area", conv(area) if area else None)
        w.setX(int(round(lx0)))
        w.setY(int(round(ly0)))
        w.setWidth(int((x1 - x0) / dpr) + 1)
        w.setHeight(int((y1 - y0) / dpr) + 1)
        if not w.isVisible():
            w.show()
        w.raise_()
        if self.gui.card.win.isVisible():           # the card stays above the marker
            self.gui.card.win.raise_()

    def hide(self):
        if self.visible is not None:
            self.visible = None
            self.win.setProperty("primary", [])
            self.win.setProperty("secondary", [])
            self.win.setProperty("area", None)
            self.win.hide()


class TrayMenu(_LiveGlass):
    """The tray icon's menu on live Liquid Glass (TrayMenu.qml)."""
    name = "tray"

    def __init__(self, gui):
        super().__init__(gui, gui.create_window("TrayMenu.qml"))
        native.exclude_from_capture(int(self.win.winId()))
        self.win.chosen.connect(self._chosen)

    def open(self, x, y):
        """x, y: the cursor in physical pixels (a tray click). The menu grows up and left from it."""
        w = self.win
        self.gui.bridge.refresh()
        s, r = screen_at(x, y)
        self.dpr, self.origin = r, (s.geometry().x(), s.geometry().y())
        lx, ly, _ = to_logical(x, y)
        wl, wt, wr, wb = native.work_area(x, y)
        left, top = to_logical(wl, wt)[:2]
        right, bottom = to_logical(wr - 1, wb - 1)[:2]
        m = w.property("margin") or 22
        polish_tree(w.contentItem())
        cw, ch = w.width() - 2 * m, w.height() - 2 * m
        cx = max(left + 6, min(lx - cw, right - cw - 6))
        cy = max(top + 6, min(ly - ch, bottom - ch - 6))
        w.setX(int(round(cx - m)))
        w.setY(int(round(cy - m)))
        w.setProperty("current", -1)
        self.capture()
        w.show()
        w.raise_()
        w.requestActivate()
        try:
            native.user32.SetForegroundWindow(int(w.winId()))
        except Exception:  # noqa
            pass
        w.setProperty("shown", True)
        self.timer.start()

    def _chosen(self, action):
        app = self.gui.app
        if action == "open":
            self.gui.show_window()
        elif action == "settings":
            self.gui.show_window("settings")
        elif action == "toggle":
            app.set_setting("enabled", not app.cfg["enabled"])
        elif action == "quit":
            app.quit()


class PinnedCard(_LiveGlass):
    """A card that stays after the scan key is released (double-tap to pin)."""
    name = "pin"

    def __init__(self, gui, entries, query, source, context, x, y, avoid=None):
        app = gui.app
        super().__init__(gui, gui.create_window("PinnedWindow.qml"))
        self.app, self.entries, self.query, self.source, self.context = app, entries, query, source, context
        w, c = self.win, app.cfg
        native.overlay_window(int(w.winId()), click_through=False)
        opts = {"entries": 6, "senses": c["card_senses"], "examples": c["card_examples"],
                "german": c["german_definitions"], "german_max": 2}
        self.lines = R.build(entries, query, source, opts)
        s, r = screen_at(x, y)
        self.dpr, self.origin = r, (s.geometry().x(), s.geometry().y())
        lx, ly, _ = to_logical(x, y)
        wl, wt, wr, wb = native.work_area(x, y)
        left, top = to_logical(wl, wt)[:2]
        right, bottom = to_logical(wr - 1, wb - 1)[:2]
        width = max(340, min(720, c["card_width"]))
        w.setProperty("cardWidth", width)
        below_y, above_y = ly + 26, ly - 14
        if avoid:                                    # keep the rest of the paragraph readable
            a0, a1 = to_logical(x, avoid[0])[1], to_logical(x, avoid[1])[1]
            if a1 - ly < 300 and ly - a0 < 300:
                below_y, above_y = max(below_y, a1 + 10), min(above_y, a0 - 10)
        room_below = bottom - below_y - 4
        room_above = above_y - top - 4
        below = room_below >= min(room_above, 360) or room_below >= room_above
        room = room_below if below else room_above
        m = w.property("margin") or 26
        head = w.property("headH") or 40
        w.setProperty("maxBodyHeight", max(120, min((bottom - top) * 0.7, room) - head))
        w.setProperty("lines", R.to_qml(self.lines))
        polish_tree(w.contentItem()); polish_tree(w.contentItem())
        w.setProperty("canSave", bool(entries))
        self._sync_saved()
        h = w.height() - 2 * m
        cx = max(left + 4, min(lx - 14, right - width - 4))
        cy = below_y if below else max(top + 4, above_y - h)
        w.setX(int(round(cx - m)))
        w.setY(int(round(cy - m)))
        w.action.connect(self._action)
        self.capture()
        w.show()
        w.raise_()
        self.timer.start()

    def _sync_saved(self):
        e = self.entries[0] if self.entries else None
        self.win.setProperty("saved", bool(e and self.app.words.has(e.word, e.pos or "")))

    def _action(self, name):
        if name == "close":
            self.close()
        elif name == "copy":
            QGuiApplication.clipboard().setText(R.plain_text(self.lines))
            self.win.setProperty("note", "Copied")
        elif name == "open":
            self.app.open_in_lookup(self.entries[0].word if self.entries else self.query)
        elif name == "save" and self.entries:
            e = self.entries[0]
            if self.app.words.has(e.word, e.pos or ""):
                self.app.words.remove_word(e.word, e.pos or "")
                self.win.setProperty("note", "Removed from My Words")
            else:
                self.app.words.add_entry(e, self.context, "game")
                self.win.setProperty("note", "Saved to My Words")
            self._sync_saved()
            self.gui.bridge.words_changed()

    def close(self):
        self.stop_capture()
        try:
            self.win.close()
            self.win.deleteLater()
        except RuntimeError:
            pass
