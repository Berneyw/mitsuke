"""The `App` object QML talks to: settings (live while a slider moves, saved when it settles), app state
(status, dictionary, updates, OCR), Lookup results, My Words and review. Everything here runs on the GUI
thread; background work reports back through Ui.call."""
import os
import time
import urllib.parse

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

import render as R
from config import DEFAULTS

KEY_NAMES = {"shift": "Shift", "ctrl": "Ctrl", "alt": "Alt"}
RECENT_MAX = 8


def _local(url):
    """QML file dialogs give file:// URLs."""
    if isinstance(url, QUrl):
        return url.toLocalFile()
    s = str(url)
    return QUrl(s).toLocalFile() if s.startswith("file:") else s


class Bridge(QObject):
    settingsChanged = Signal()
    stateChanged = Signal()
    resultChanged = Signal()
    wordsChanged = Signal()
    historyChanged = Signal()
    darkChanged = Signal()
    pageRequested = Signal(str)
    lookupRequested = Signal(str)
    flash = Signal(str)
    playingChanged = Signal()

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._state = {}
        self._result = {"query": "", "lines": [], "has": False, "empty": "start", "footer": "", "saved": False}
        self._progress = None
        self._pending_remember = None
        self._live = {}
        self._dark = True
        self._playing = ""
        self._save_timer = QTimer(self, singleShot=True, interval=450, timeout=self._commit_live)
        self.refresh()

    # ------------------------------------------------------------------ settings
    @Property("QVariantMap", notify=settingsChanged)
    def settings(self):
        return dict(self.app.cfg.data)

    @Property(str, constant=True)
    def version(self):
        return self.app.version

    @Property(bool, notify=darkChanged)
    def dark(self):
        return self._dark

    @Slot(bool)
    def setDark(self, dark):
        """QML resolves the appearance (System follows Windows) and tells Python, which recolours native parts."""
        if dark != self._dark:
            self._dark = dark
            self.darkChanged.emit()
            self.app.gui.appearance_changed(dark)

    @staticmethod
    def _coerce(key, value):
        d = DEFAULTS.get(key)
        if isinstance(d, bool):
            return bool(value)
        if isinstance(d, int):
            return int(round(float(value)))
        if isinstance(d, float):
            return float(value)
        return value

    @Slot(str, "QVariant")
    def set(self, key, value):
        value = self._coerce(key, value)
        self._live.pop(key, None)
        if self.app.cfg[key] == value and key not in ("appearance",):
            return
        self.app.set_setting(key, value)
        if key == "pron_volume":
            self.app.gui.player.set_volume(value)
        self.settingsChanged.emit()

    @Slot(str, "QVariant")
    def setLive(self, key, value):
        """While a slider is dragged: applied in memory at once (cards, previews), written to disk when it settles."""
        value = self._coerce(key, value)
        if self.app.cfg.data.get(key) == value:
            return
        self.app.cfg.data[key] = value
        self._live[key] = value
        if key == "pron_volume":
            self.app.gui.player.set_volume(value)
        self.app.current_word = None
        self.settingsChanged.emit()
        self._save_timer.start()

    def _commit_live(self):
        live, self._live = self._live, {}
        for k, v in live.items():
            self.app.set_setting(k, v)

    # ------------------------------------------------------------------ pronunciation
    @Property(str, notify=playingChanged)
    def playingKey(self):
        return self._playing

    def set_playing(self, key, playing):
        if playing:
            self._playing = key
        elif self._playing == key:
            self._playing = ""
        self.playingChanged.emit()

    @Slot(str, str, "QVariant")
    def speak(self, key, word, audio):
        self.app.gui.speak(key, word, audio or [])

    @Slot()
    def stopSpeaking(self):
        self.app.gui.player.stop()
        self.set_playing(self._playing, False)

    # ------------------------------------------------------------------ state
    @Property("QVariantMap", notify=stateChanged)
    def state(self):
        return self._state

    def refresh(self):
        a, cfg = self.app, self.app.cfg
        key = KEY_NAMES.get(cfg["key"], "Shift")
        if not cfg["enabled"]:
            kind, title, detail = "paused", "Paused", "Scanning is off."
        elif a.ocr_error:
            kind, title, detail = "error", "Needs attention", "Text recognition isn’t available."
        else:
            kind, title, detail = "ok", "Active", f"Hold {key} over a word in the game."
        if a.building:
            dict_status, dict_btn, dict_primary, dict_enabled = \
                "Downloading and building — you can keep playing.", "Updating…", False, False
        elif a.engine.has_offline:
            info = a.engine.stats()
            try:
                info += " · updated " + time.strftime("%d %b %Y", time.localtime(os.path.getmtime(a.engine.db_path)))
            except OSError:
                pass
            dict_status, dict_btn, dict_primary, dict_enabled = f"Installed · {info}", "Update", False, True
        else:
            dict_status, dict_btn, dict_primary, dict_enabled = \
                "Not installed. Words are looked up online, without gender.", "Download…", True, True
        ustate, utext = a.update_state
        if not cfg["update_repo"]:
            update = {"text": f"Mitsuke {a.version}. Add an update source above to get new versions.",
                      "button": "Check Now", "enabled": False, "primary": False}
        else:
            update = {"text": utext or f"Mitsuke {a.version}.",
                      "button": "Install and Restart" if ustate == "available" else "Check Now",
                      "enabled": ustate not in ("checking", "downloading", "installing"),
                      "primary": ustate == "available"}
        p = self._progress
        self._state = {
            "statusKind": kind, "statusTitle": title, "statusDetail": detail, "keyName": key,
            "ocrError": bool(a.ocr_error), "ocrHelp": a.ocr_help() if a.ocr_error else "",
            "building": a.building, "hasOffline": a.engine.has_offline,
            "hasPronunciation": a.engine.has_pronunciation,
            "dictStatus": dict_status, "dictButton": dict_btn, "dictPrimary": dict_primary,
            "dictEnabled": dict_enabled,
            "progress": {"active": p is not None, "text": p[0] if p else "", "frac": (p[1] or 0) if p else 0,
                         "sub": p[2] if p else ""},
            "update": update,
            "due": a.words.due_count(), "total": a.words.count(),
            "recent": list(cfg["recent"]),
            "voiceAvailable": getattr(self.app.gui, "voice_available", True) if hasattr(self.app, "gui") else True,
        }
        self.stateChanged.emit()
        self.settingsChanged.emit()

    def set_progress(self, text, frac=None, sub=""):
        self._progress = None if text is None else (text, frac, sub)
        self.refresh()

    # ------------------------------------------------------------------ lookup
    @Property("QVariantMap", notify=resultChanged)
    def result(self):
        return self._result

    @Slot(str, bool)
    def search(self, q, remember):
        q = q.strip()
        if not q:
            self._result = {"query": "", "lines": [], "has": False, "empty": "start", "footer": "", "saved": False}
            self._entries = None
            self.resultChanged.emit()
            return
        self._pending_remember = q if remember else None
        self._result = dict(self._result, footer="Searching…", query=q)
        self.resultChanged.emit()
        self.app.lookup_async(q, self._show_result)

    def _show_result(self, entries, query, source):
        if query != self._result.get("query"):
            return                                   # an older search finished after a newer one
        self._entries = entries
        if not entries:
            self._result = {"query": query, "lines": [], "has": False, "empty": "none", "footer": "", "saved": False}
            self.resultChanged.emit()
            return
        if self._pending_remember == query:
            self._remember(query)
            try:                                       # a deliberate search (Enter / chip) goes into History
                self.app.words.seen(entries[0], "", "lookup")
                self.history_changed()
            except Exception:  # noqa
                pass
        n = len(entries)
        ms = f"{self.app.last_ms} ms" if self.app.last_ms >= 1 else "<1 ms"
        src = "Offline dictionary" if source == "offline" else "Wiktionary online"
        self._lines = R.build(entries, query, source)
        self._result = {"query": query, "lines": R.to_qml(self._lines), "has": True, "empty": "",
                        "footer": f"{n} result{'s' if n != 1 else ''} · {src} · {ms}",
                        "saved": self._is_saved(), "word": entries[0].word or query}
        self.resultChanged.emit()

    def _is_saved(self):
        e = self._entries[0] if getattr(self, "_entries", None) else None
        return bool(e and self.app.words.has(e.word, e.pos or ""))

    def _remember(self, q):
        recent = [x for x in self.app.cfg["recent"] if x.lower() != q.lower()]
        self.app.cfg.set("recent", ([q] + recent)[:RECENT_MAX])
        self.refresh()

    @Slot()
    def clearRecent(self):
        self.app.cfg.set("recent", [])
        self.refresh()

    @Slot()
    def toggleSave(self):
        if not getattr(self, "_entries", None):
            return
        e = self._entries[0]
        if self.app.words.has(e.word, e.pos or ""):
            self.app.words.remove_word(e.word, e.pos or "")
            self.flash.emit(f"Removed “{e.word}” from My Words.")
        else:
            self.app.words.add_entry(e, self._result.get("query", ""), "lookup")
            self.flash.emit(f"Saved “{e.word}” to My Words.")
        self._result = dict(self._result, saved=self._is_saved())
        self.resultChanged.emit()
        self.words_changed()

    @Slot()
    def copyResult(self):
        if getattr(self, "_lines", None) and self._result.get("has"):
            self.copyText(R.plain_text(self._lines))
            self.flash.emit("Copied to the clipboard.")

    @Slot(str)
    def copyText(self, s):
        QGuiApplication.clipboard().setText(s)

    @Slot(str)
    def openWiktionary(self, word):
        QDesktopServices.openUrl(QUrl("https://en.wiktionary.org/wiki/" + urllib.parse.quote(word) + "#German"))

    # ------------------------------------------------------------------ my words
    def words_changed(self):
        self.wordsChanged.emit()
        self.refresh()

    @Slot(str, result="QVariantList")
    def words(self, query):
        out = []
        for r in self.app.words.all(query)[:300]:
            g = R.GENDER.get(r["gender"])
            out.append({"id": r["id"], "word": r["word"], "pos": R.POS_NAMES.get(r["pos"], r["pos"] or ""),
                        "article": g[1] if g else "", "genderColor": g[0] if g else "",
                        "gloss": r["gloss"] or "", "context": r["context"] or "", "forms": r["forms"] or "",
                        "added": time.strftime("%d %b", time.localtime(r["added"] or 0))})
        return out

    @Slot(str, result=int)
    def wordsMatching(self, query):
        return len(self.app.words.all(query))

    @Slot(int)
    def removeWord(self, wid):
        self.app.words.remove(wid)
        if self._result.get("has"):
            self._result = dict(self._result, saved=self._is_saved())
            self.resultChanged.emit()
        self.words_changed()

    @Slot("QVariant", result=str)
    def exportAnki(self, url):
        try:
            n = self.app.words.export_anki(_local(url))
            return f"Exported {n} word{'s' if n != 1 else ''}. In Anki choose File → Import and pick this file."
        except OSError as e:
            return f"Couldn’t export: {e.strerror or e}."

    @Slot(result="QVariantList")
    def dueCards(self):
        from words import WordStore, interval_label
        cards = []
        for c in self.app.words.due():
            g = R.GENDER.get(c["gender"])
            ivs = [interval_label(WordStore.schedule(c, gr)[0]) for gr in ("again", "hard", "good", "easy")]
            cards.append({"id": c["id"], "word": c["word"], "article": g[1] if g else "",
                          "genderColor": g[0] if g else "", "gloss": c["gloss"] or "",
                          "forms": c["forms"] or "", "context": c["context"] or "", "intervals": ivs})
        return cards

    @Slot(int, str)
    def grade(self, wid, g):
        self.app.words.review(wid, g)
        self.refresh()

    @Slot()
    def reviewEnded(self):
        self.words_changed()

    # ------------------------------------------------------------------ history
    def history_changed(self):
        self.historyChanged.emit()

    @Slot(str, str, str, result="QVariantList")
    def history(self, period, query, order):
        since = {"today": time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1)),
                 "week": time.time() - 7 * 86400}.get(period, 0.0)
        out = []
        now = time.time()
        for r in self.app.words.history(since, query, order):
            g = R.GENDER.get(r["gender"])
            age = now - (r["last_seen"] or now)
            when = ("just now" if age < 90 else f"{int(age // 60)} min ago" if age < 3600
                    else time.strftime("%H:%M", time.localtime(r["last_seen"])) if age < 86400
                    else time.strftime("%d %b", time.localtime(r["last_seen"])))
            out.append({"id": r["id"], "word": r["word"], "pos": R.POS_NAMES.get(r["pos"], r["pos"] or ""),
                        "article": g[1] if g else "", "gloss": r["gloss"] or "", "context": r["context"] or "",
                        "count": r["count"], "when": when, "saved": bool(r["saved"]),
                        "source": r["source"] or ""})
        return out

    @Slot(str, result=int)
    def historyCount(self, period):
        since = {"today": time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1)),
                 "week": time.time() - 7 * 86400}.get(period, 0.0)
        return self.app.words.history_count(since)

    @Slot(int)
    def saveFromHistory(self, hid):
        if self.app.words.save_from_history(hid):
            self.flash.emit("Saved to My Words.")
        self.words_changed()
        self.history_changed()

    @Slot(int)
    def forgetHistory(self, hid):
        self.app.words.forget(hid)
        self.history_changed()

    @Slot()
    def clearHistory(self):
        self.app.words.clear_history()
        self.history_changed()

    # ------------------------------------------------------------------ actions
    @Slot(bool)
    def startDictionary(self, from_wiktionary=False):
        """Prebuilt download by default; from_wiktionary builds it here from the latest Wiktionary data."""
        self.app.start_dictionary_build(ask=False, from_wiktionary=bool(from_wiktionary))

    @Slot()
    def retryOcr(self):
        self.app.retry_ocr()

    @Slot()
    def updateAction(self):
        a = self.app
        if a.update_info and a.update_state[0] in ("available", "error"):
            a.install_update()
        else:
            a.check_updates(manual=True)

    @Slot()
    def openDataDir(self):
        self.app.open_data_dir()

    @Slot(result=bool)
    def openLog(self):
        p = os.path.join(self.app.data_dir, "mitsuke.log")
        if os.path.exists(p):
            os.startfile(p)  # noqa
            return True
        return False

    @Slot("QVariant", result=str)
    def exportSettings(self, url):
        p = _local(url)
        try:
            self.app.cfg.export(p)
            return f"Exported to {os.path.basename(p)}."
        except OSError as e:
            return f"Couldn’t export: {e.strerror or e}."

    @Slot("QVariant", result=str)
    def importSettings(self, url):
        try:
            n = self.app.cfg.import_(_local(url))
        except (OSError, ValueError) as e:
            return f"Couldn’t import: {e}."
        self.app.settings_reloaded()
        self.refresh()
        return f"Imported {n} settings."

    @Slot()
    def resetSettings(self):
        self.app.cfg.reset()
        self.app.settings_reloaded()
        self.refresh()
        self.flash.emit("All settings were reset.")

    @Slot(str)
    def rememberPage(self, page):
        if page in ("lookup", "words", "history", "dictionary", "settings") and self.app.cfg["last_page"] != page:
            self.app.cfg.set("last_page", page)

    @Slot()
    def hideWindow(self):
        self.app.gui.hide_window()

    @Slot()
    def quit(self):
        self.app.quit()
