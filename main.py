"""Mitsuke — German dictionary overlay for games. Lives in the tray; hold a key (Shift by default) over a word.
The interface is Qt Quick / QML with Liquid Glass (package gui); this module is the toolkit-free core."""
import ctypes
import logging
import os
import socket
import subprocess
import sys
import threading
import time

from config import OLD_APP, Config, data_dir
from engine import DB_NAME, Engine

VERSION = "2.3"
VK = {"shift": 0x10, "ctrl": 0x11, "alt": 0x12}
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
INSTANCE_PORT = 47653


def claim_instance():
    """A local socket acts as the single-instance lock. Returns the socket, or None if Mitsuke is already
    running (then asks that instance to show its window)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", INSTANCE_PORT))
        srv.listen(2)
        return srv
    except OSError:
        srv.close()
        try:
            with socket.create_connection(("127.0.0.1", INSTANCE_PORT), timeout=1) as c:
                c.sendall(b"show")
        except OSError:
            pass
        return None


def sentence_around(tokens, idx):
    """The sentence containing tokens[idx] (for My Words): from the previous . ! ? to the next one."""
    ends = (".", "!", "?", "…")
    lo = idx
    while lo > 0 and not tokens[lo - 1].rstrip("\"“”»«'").endswith(ends):
        lo -= 1
    hi = idx
    while hi < len(tokens) - 1 and not tokens[hi].rstrip("\"“”»«'").endswith(ends):
        hi += 1
    return " ".join(tokens[lo:hi + 1])


def exe_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw}" "{os.path.abspath(__file__)}" --tray'


class App:
    version = VERSION

    def __init__(self, start_hidden=False):
        self.data_dir = data_dir()
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(os.path.join(self.data_dir, "mitsuke.log"), maxBytes=1 << 20, backupCount=1,
                                      encoding="utf-8")                # the log never grows past ~2 MB
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
        logging.info("Mitsuke %s, Python %s", VERSION, sys.version.split()[0])
        sys.excepthook = lambda *a: logging.error("uncaught", exc_info=a)
        threading.excepthook = lambda a: logging.error("thread", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
        self.cfg = Config()
        logging.info("settings: %s%s", self.cfg.loaded_from, f" ({self.cfg.problem})" if self.cfg.problem else "")
        self.engine = Engine(self.cfg, self.data_dir)
        from words import WordStore
        self.words = WordStore(os.path.join(self.data_dir, "words.sqlite"))
        if self.words.restored:
            logging.warning("words.sqlite was damaged; restored from the backup")
        self._tidy_data_dir()
        self.pinned = None
        self.update_state = ("idle", "")
        self._last_card = None
        self._ctx_text = ""
        self.update_info = None
        self.icon_path = os.path.join(BASE, "assets", "icon.ico")
        self.building = False
        self.ocr = None
        self.ocr_error = ""
        self.last_ms = 0
        self.current_word = None
        self.stop_flag = threading.Event()

        from gui.qtapp import Gui
        from tray import Tray
        self.tray = Tray(self)
        self.gui = Gui(self, start_hidden)
        self.ui = self.gui                         # call() / ask() from any thread
        self.overlay = self.gui.card
        self.highlight = self.gui.highlight

    # ---------- used by the window and the tray (any thread) ----------
    def status_text(self):
        if not self.cfg["enabled"]:
            state = "Paused"
        elif self.ocr_error:
            state = "Text recognition unavailable"
        else:
            state = f"Active · hold {self.cfg['key'].capitalize()}"
        return f"Mitsuke {VERSION} — {state}" + (" · updating dictionary…" if self.building else "")

    def show_window(self, page=None):
        self.ui.call(self.gui.show_window, page)

    def refresh_window(self):
        self.ui.call(self.gui.refresh)
        self.tray.refresh()

    def set_setting(self, key, value):
        """Single entry point for settings changes: saves, then applies side effects."""
        self.cfg.set(key, value)
        if key in ("window_material", "reduce_transparency"):
            self.ui.call(self.gui.apply_material)
        elif key == "autostart":
            self.apply_autostart()
        self.current_word = None                   # next hover redraws the card with new settings
        self.refresh_window()

    def settings_reloaded(self):
        self.apply_autostart()
        self.ui.call(self.gui.settings_reloaded)

    def open_data_dir(self):
        os.startfile(self.data_dir)  # noqa

    def apply_autostart(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE) as k:
                try:                                    # the entry from before the rename
                    winreg.DeleteValue(k, OLD_APP)
                except FileNotFoundError:
                    pass
                if self.cfg["autostart"]:
                    winreg.SetValueEx(k, "Mitsuke", 0, winreg.REG_SZ, exe_command())
                else:
                    try:
                        winreg.DeleteValue(k, "Mitsuke")
                    except FileNotFoundError:
                        pass
        except Exception:  # noqa
            logging.exception("autostart")

    def lookup_async(self, word, callback):
        def run():
            t0 = time.perf_counter()
            entries, src = self.engine.lookup(word)
            self.last_ms = int(1000 * (time.perf_counter() - t0))
            self.ui.call(callback, entries, word, src)
        threading.Thread(target=run, daemon=True).start()

    def _tidy_data_dir(self):
        """Leftovers of older versions and interrupted writes."""
        import glob
        stale = [os.path.join(self.data_dir, n) for n in ("dict.sqlite.old", "config.json.tmp", "simsdict.log")]
        stale += [p for p in glob.glob(os.path.join(self.data_dir, "*.tmp"))
                  if time.time() - os.path.getmtime(p) > 3600]
        for p in stale:
            try:
                if os.path.isfile(p):
                    os.remove(p)
            except OSError:
                pass

    def quit(self):
        self.stop_flag.set()
        self.tray.stop()
        self.ui.call(self.gui.quit)

    # ---------- OCR ----------
    def ocr_help(self):
        if self.ocr_error == "lang-missing":
            return ("Windows needs its German text-recognition component (a few MB). "
                    "Choose Try Again to install it — Windows will ask for administrator permission.")
        return "Hovering over words won’t work until it starts. Typing in Lookup still works. Details are in the log."

    def retry_ocr(self):
        def run():
            if self.init_ocr(prompt=False, install=True) and not getattr(self, "_worker_started", False):
                self._start_worker()
            self.refresh_window()
        threading.Thread(target=run, daemon=True).start()

    def _start_worker(self):
        self._worker_started = True
        threading.Thread(target=self.worker, daemon=True).start()

    def init_ocr(self, prompt=True, install=False) -> bool:
        from ocrword import Ocr, OcrUnavailable
        lang = self.cfg["lang"]
        for attempt in range(2):
            try:
                self.ocr = Ocr(lang=lang)
                self.ocr_error = ""
                self.refresh_window()
                return True
            except OcrUnavailable as e:
                self.ocr_error = str(e)
                logging.warning("ocr: %s", e)
                if str(e) != "lang-missing" or attempt == 1:
                    break
                if prompt and not install:
                    ans = self.ui.ask(
                        "Install German text recognition?",
                        "Mitsuke reads words on screen with Windows’ built-in text recognition. Windows needs "
                        "its German component (a few MB) and will ask for administrator permission.",
                        [("Install", "yes"), ("Not Now", "no")])
                    if ans != "yes":
                        break
                elif not install:
                    break
                cap = f"Language.OCR~~~{lang}-{lang.upper()}~0.0.1.0"
                ps = ("Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "
                      f"'-NoProfile','-Command','Add-WindowsCapability -Online -Name {cap}'")
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000)
            except Exception as e:  # noqa
                self.ocr_error = str(e)
                logging.exception("ocr init")
                break
        self.refresh_window()
        return False

    # ---------- dictionary ----------
    def start_dictionary_build(self, ask=True, from_wiktionary=False):
        """Installs the offline dictionary: normally the prebuilt one (~55 MB, see dictdl.py); with
        from_wiktionary — or if that download fails — built here from the latest Wiktionary (4.3 GB)."""
        if self.building:
            return
        if ask:
            ans = self.ui.ask(
                "Download the offline dictionary?",
                "Right now words are looked up online — without gender, and a little slower.\n\n"
                "The offline dictionary adds gender, plural, inflections, examples and German definitions, and "
                "works instantly without internet. It's a download of about 55 MB (about 180 MB installed).",
                [("Download", "yes"), ("Later", "no")])
            self.cfg.set("dict_offered", True)
            if ans != "yes":
                return
        self.building = True
        self.refresh_window()
        threading.Thread(target=self._build, args=(from_wiktionary,), daemon=True).start()

    def _progress(self, text, frac=None, sub=""):
        self.ui.call(self.gui.set_progress, text, frac, sub)

    def _install_prebuilt(self):
        """True when the prebuilt dictionary was downloaded, verified and installed."""
        import dictdl
        try:
            new, meta = dictdl.fetch(
                self.cfg["update_repo"], self.data_dir,
                lambda d, t: self._progress("Downloading the dictionary", d / t if t else None,
                                            f"{d >> 20} of {t >> 20} MB" if t else f"{d >> 20} MB"))
        except Exception as e:  # noqa — no network, no release yet, damaged download: build it here instead
            logging.info("prebuilt dictionary unavailable: %s", e)
            return False
        self._progress("Installing", 1)
        self.engine.close()
        os.replace(new, self.engine.db_path)
        self.engine.reload()
        logging.info("installed prebuilt dictionary %s (%s entries)", meta.get("built"), meta.get("entries"))
        return True

    def _build(self, from_wiktionary=False):
        try:
            if not from_wiktionary and self._install_prebuilt():
                self.tray.notify("The offline dictionary is ready: instant lookups with gender and word forms.")
            else:
                self._build_from_wiktionary()
        except Exception as e:  # noqa
            logging.exception("build")
            self.engine.reload()
            self.tray.notify(f"Couldn’t install the dictionary ({e}). Online lookup still works.")
        finally:
            self.building = False
            self._progress(None)
            self.refresh_window()

    def _build_from_wiktionary(self):
        import build_dict as bd
        stages = {"Читаю английский Wiktionary": "Reading English Wiktionary",
                  "Читаю немецкий Wiktionary": "Reading German Wiktionary",
                  "Связываю словоформы": "Linking word forms", "Строю индексы": "Building indexes"}
        def dl(name):
            return lambda d, t: self._progress(f"Downloading {name}", d / t if t else None,
                                               f"{d >> 20:,} of {t >> 20:,} MB" if t else f"{d >> 20:,} MB")
        en = bd.download(bd.EN_URL, os.path.join(self.data_dir, "kaikki-en.jsonl"), dl("English Wiktionary"))
        de = None
        if self.cfg["german_definitions"]:
            de = bd.download(bd.DE_URL, os.path.join(self.data_dir, "kaikki-de.jsonl"), dl("German Wiktionary"))
        new = os.path.join(self.data_dir, DB_NAME + ".new")
        bd.build_database(new, en, de, lambda s, f: self._progress(stages.get(s, s), f,
                                                                   "" if f is None else f"{f:.0%}"))
        self._progress("Installing", 1)
        self.engine.close()
        os.replace(new, self.engine.db_path)
        self.engine.reload()
        for p in (en, de):
            if p and os.path.exists(p):
                os.remove(p)
        self.tray.notify("The offline dictionary is ready: instant lookups with gender and word forms.")

    # ---------- main loop: key -> OCR -> lookup ----------
    def worker(self):
        from ocrword import cursor_pos
        get_key = ctypes.windll.user32.GetAsyncKeyState
        last_pos, down_since, shown = None, None, False
        was_down, released_at, card_at_release, pin_hold = False, 0.0, None, False
        while not self.stop_flag.is_set():
            cfg = self.cfg
            down = cfg["enabled"] and bool(get_key(VK.get(cfg["key"], 0x10)) & 0x8000)
            now = time.perf_counter()
            if down and not was_down:                      # key pressed: a quick second tap pins the card
                if cfg["pin_double_tap"] and card_at_release and now - released_at < 0.4:
                    self.ui.call(self.pin_card, *card_at_release)
                    pin_hold = True
                card_at_release = None
            elif was_down and not down:                    # key released
                released_at = now
                card_at_release = self._last_card if shown else None
                pin_hold = False
            was_down = down
            if pin_hold:                                   # the pinning tap doesn't start a new scan
                time.sleep(0.02)
                continue
            if not down:
                if shown:
                    self.ui.call(self.overlay.hide)
                if last_pos is not None:
                    self.ui.call(self.highlight.hide)
                last_pos = down_since = self.current_word = None
                shown = False
                time.sleep(0.025)
                continue
            now = time.perf_counter()
            down_since = down_since or now
            if (now - down_since) * 1000 < cfg["hold_ms"]:
                time.sleep(0.015)
                continue
            pos = cursor_pos()
            if pos != last_pos:
                last_pos = pos
                time.sleep(0.04)
                if cursor_pos() != pos:
                    continue                       # the cursor is still moving
                try:
                    word = self.lookup_at(pos)
                except Exception:  # noqa
                    logging.exception("lookup")
                    word = None
                if word is None and shown:
                    self.ui.call(self.overlay.hide)
                shown = word is not None
            time.sleep(0.015)

    def lookup_at(self, pos):
        t0 = time.perf_counter()
        self.ocr.scale = self.cfg["scale"]
        self.ocr.half_w = max(200, int(self.cfg["capture_width"]) // 2)
        score = self.engine.reading_score                 # extra OCR passes only when the reading looks wrong
        ctx = self.ocr.context_at(*pos, score=score)
        if ctx is None:
            self.current_word = None
            self.ui.call(self.highlight.hide)
            return None
        entries, word = self.engine.lookup_context(ctx)
        if self._may_continue(entries, ctx):
            wide = self.ocr.context_at(*pos, wide=True, score=score)    # the sentence goes on beyond the strip
            if wide is not None:
                ctx = wide
                entries, word = self.engine.lookup_context(ctx)
            if self._may_continue(entries, ctx):          # still unfinished: read the next line on its own
                more = self.ocr.peek_below(ctx)
                if more is not None:
                    e2, w2 = self.engine.lookup_context(more)
                    if e2 and any(e.match for e in e2):
                        ctx, entries, word = more, e2, w2
        word = word or ctx.word
        self._ctx_text = sentence_around(ctx.tokens, ctx.idx)
        self._avoid = None
        if ctx.rects:                                     # the text block on screen: the card must not cover it
            flat = [r for rs in ctx.rects for r in rs]
            self._avoid = (min(r[1] for r in flat), max(r[1] + r[3] for r in flat))
        self._show_highlight(ctx, entries, word)
        shown_key = (word, tuple(e.word for e in entries))
        if shown_key == self.current_word:
            return word
        self.current_word = shown_key
        x, y = pos
        if entries:
            self._shown(entries, word, x, y, "offline", t0)
        elif self.cfg["online_fallback"]:
            self.ui.call(self.overlay.show_note, word, "Searching online…", x, y, self._avoid)

            def fetch():                            # the network never blocks cursor tracking
                res = self.engine.online.lookup(word)
                if self.current_word == shown_key:
                    self._shown(res, word, x, y, "online" if res else "", t0)
            threading.Thread(target=fetch, daemon=True).start()
        else:
            self._shown([], word, x, y, "", t0)
        return word

    def _show_highlight(self, ctx, entries, word):
        cfg = self.cfg
        if not ctx.rects or not (cfg["highlight"] or cfg["highlight_area"]):
            self.ui.call(self.highlight.hide)
            return
        from render import linked_spans
        prim, sec = linked_spans(ctx, entries, word) if cfg["highlight"] else ([], [])
        flat = lambda ks: [r for k in ks if 0 <= k < len(ctx.rects) for r in ctx.rects[k]]  # noqa: E731
        self.ui.call(self.highlight.show, flat(prim), flat(sec),
                     ctx.capture if cfg["highlight_area"] else None)

    @staticmethod
    def _may_continue(entries, ctx):
        """Recapture wider when a verb is under the cursor and its particle / the sentence end isn't visible."""
        from dictcore import PARTICLES, clean_token
        if any(e.match for e in entries):
            return False
        ends = (".", "!", "?")
        if clean_token(ctx.word).lower() in PARTICLES:  # a particle: is its verb above / left of the strip?
            return not any(t.rstrip().endswith(ends) for t in ctx.tokens[:ctx.idx])
        # a verb whose sentence doesn't end inside the strip: the particle may be on a line we didn't capture
        if any(t.rstrip().endswith(ends) for t in ctx.tokens[ctx.idx + 1:]):
            return False
        return any(e.pos == "verb" for e in entries)

    def _shown(self, entries, word, x, y, src, t0):
        self.last_ms = int(1000 * (time.perf_counter() - t0))
        logging.info("%r -> %d (%s) %d ms", word, len(entries), src, self.last_ms)
        self._last_card = (entries, word, src, self._ctx_text, x, y) if entries else None
        self.ui.call(self.overlay.show, entries, word, x, y, src, getattr(self, "_avoid", None))

    def pin_card(self, entries, word, src, context, x, y):
        self.gui.pin(entries, word, src, context, x, y)
        logging.info("pinned %r", word)

    # ---------- updates ----------
    def check_updates(self, manual=False):
        """Background check. Automatic checks run at most once a day and stay silent unless there's news."""
        import updater
        cfg = self.cfg
        if not manual and (not cfg["update_check"] or not cfg["update_repo"]
                           or time.time() - cfg["update_last_check"] < 86400):
            return
        self.update_state = ("checking", "Checking for updates…")
        self.refresh_window()

        def run():
            try:
                info = updater.check(cfg["update_repo"], VERSION)
                cfg.set("update_last_check", time.time())
                self.update_info = info
                if info:
                    self.update_state = ("available", f"Mitsuke {info['version']} is available.")
                    self.tray.notify(f"Mitsuke {info['version']} is available. Open Settings → Updates to install it.")
                else:
                    self.update_state = ("current", f"Mitsuke {VERSION} is up to date.")
            except Exception as e:  # noqa
                logging.info("update check: %s", e)
                self.update_state = ("error", f"Couldn’t check for updates: {e}")
            self.refresh_window()
        threading.Thread(target=run, daemon=True).start()

    def install_update(self):
        import updater
        info = self.update_info
        if not info:
            return
        if not updater.is_frozen():
            self.update_state = ("error", "Updates install into the built Mitsuke.exe, not when running from source.")
            self.refresh_window()
            return

        def run():
            try:
                def prog(d, t):
                    self.update_state = ("downloading", f"Downloading {info['version']}… "
                                         + (f"{d * 100 // t}%" if t else f"{d >> 20} MB"))
                    self.refresh_window()
                new = updater.download(info, prog)
                self.update_state = ("installing", "Restarting to finish the update…")
                self.refresh_window()
                updater.install_on_exit(new)
                logging.info("update %s staged, restarting", info["version"])
                self.quit()
            except Exception as e:  # noqa
                logging.exception("update")
                self.update_state = ("error", f"Update failed: {e}")
                self.refresh_window()
        threading.Thread(target=run, daemon=True).start()

    def open_in_lookup(self, q):
        self.ui.call(self.gui.open_lookup, q)

    def listen_instance(self, srv):
        def loop():
            while not self.stop_flag.is_set():
                try:
                    c, _ = srv.accept()
                    with c:
                        if c.recv(16) == b"show":
                            self.show_window()
                except OSError:
                    return
        threading.Thread(target=loop, daemon=True).start()

    def run(self):
        self.tray.run()
        self.apply_autostart()                      # refresh the path if the exe moved; drop the pre-rename entry

        def boot():
            if self.init_ocr():
                self._start_worker()
            self.refresh_window()
            if not self.engine.has_offline and not self.cfg["dict_offered"]:
                self.start_dictionary_build(ask=True)
            self.check_updates()
            if self.words.backup():
                logging.info("saved words backed up")
            if self.cfg.loaded_from == "backup":
                self.tray.notify("Your settings file was damaged and has been restored from its backup copy.")
            elif self.words.restored:
                self.tray.notify("Your saved words file was damaged and has been restored from its backup copy.")
        threading.Thread(target=boot, daemon=True).start()
        try:
            self.gui.exec()
        except KeyboardInterrupt:
            pass


def main():
    if os.name != "nt":
        print("Mitsuke runs on Windows only.")
        return
    srv = claim_instance()
    if srv is None:
        return
    app = App(start_hidden="--tray" in sys.argv)
    app.listen_instance(srv)
    app.run()


if __name__ == "__main__":
    main()
