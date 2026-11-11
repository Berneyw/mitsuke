"""Qt side of Mitsuke: the application object, the QML engine, the thread bridge (call / ask), the main
window with its native material, and the in-game overlays. main.App talks only to this facade."""
import ctypes
import ctypes.wintypes as wt
import logging
import os
import sys
import threading

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Qt, QTimer, QUrl, Signal, Slot, qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

from . import native
from .bridge import Bridge
from .overlay import Backdrop, CardOverlay, FreezeOverlay, Grabber, Highlighter, PinnedCard, TrayMenu

HERE = os.path.dirname(os.path.abspath(__file__))
QML_DIR = os.path.join(HERE, "qml")


def _qt_log(mode, ctx, msg):
    """Qt's own messages (QML errors, graphics backend problems) go to mitsuke.log."""
    if "propagateSizeHints" in msg or "Retrying to obtain clipboard" in msg or "QThreadStorage" in msg:
        return
    logging.warning("qt: %s", msg)


def configure():
    """Must run before the QGuiApplication exists. OpenGL gives per-pixel window alpha on Windows (the
    see-through parts show Acrylic); the glass shaders run on it through Qt's RHI."""
    qInstallMessageHandler(_qt_log)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    os.environ.setdefault("QSG_RENDER_LOOP", "basic")
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    QQuickWindow.setDefaultAlphaBuffer(True)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


class _NativeFilter(QAbstractNativeEventFilter):
    def __init__(self, frameless):
        super().__init__()
        self.frameless = frameless

    def nativeEventFilter(self, event_type, message):
        try:
            msg = wt.MSG.from_address(int(message))
            if msg.message not in (native.WM_NCCALCSIZE, native.WM_NCHITTEST):
                return False, 0
            r = self.frameless.handle(msg)
            if r is None:
                return False, 0
            return True, r
        except Exception:  # noqa
            return False, 0


class Gui(QObject):
    _invoke = Signal(object)

    def __init__(self, app, start_hidden=False):
        super().__init__()
        self.app = app
        configure()
        self.qapp = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setApplicationName("Mitsuke")
        if os.path.exists(app.icon_path):
            self.qapp.setWindowIcon(QIcon(app.icon_path))
        families = set(QFontDatabase.families())
        self.has_sf = "SF Pro Text" in families and "SF Pro Display" in families
        f = QFont("SF Pro Text" if self.has_sf else "Segoe UI Variable Text")
        f.setPixelSize(13)
        f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.qapp.setFont(f)
        self._invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)

        from .audio import Player, german_voice_available
        self.voice_available = german_voice_available()
        self.player = Player(app.data_dir, on_state=lambda key, playing: self.call(self.bridge.set_playing, key, playing))
        self.player.volume = app.cfg["pron_volume"]
        self.bridge = Bridge(app)
        self.backdrop = Backdrop()
        self.grabber = Grabber()
        self.engine = QQmlApplicationEngine()
        self.engine.addImportPath(QML_DIR)
        self.engine.addImageProvider("backdrop", self.backdrop)
        ctx = self.engine.rootContext()
        ctx.setContextProperty("App", self.bridge)
        ctx.setContextProperty("hasSF", self.has_sf)
        self.engine.warnings.connect(lambda ws: [logging.warning("qml: %s", w.toString()) for w in ws])
        self.engine.load(QUrl.fromLocalFile(os.path.join(QML_DIR, "Mitsuke", "Main.qml")))
        if not self.engine.rootObjects():
            raise RuntimeError("the main window failed to load (see the log)")
        self.main = self.engine.rootObjects()[0]
        self.frameless = native.FramelessFilter()
        self._filter = _NativeFilter(self.frameless)
        self.qapp.installNativeEventFilter(self._filter)
        hwnd = int(self.main.winId())
        self.frameless.hwnds.add(hwnd)
        native.native_frame(hwnd)
        # The DWM material must be applied once the window has presented a frame; earlier, DWM can leave the
        # GL surface invisible.
        self._material_done = False
        self.main.frameSwapped.connect(self._first_frame)
        self.card = CardOverlay(self)
        self.highlight = Highlighter(self)
        self.freeze = FreezeOverlay(self)
        self.tray_menu = TrayMenu(self)
        self.pinned = None
        self._alerts = []
        self._restore_geometry()
        # Windows is shutting down or the user is signing out: write everything now
        self.qapp.commitDataRequest.connect(lambda *_: self.flush())
        self.qapp.aboutToQuit.connect(self.flush)
        if not start_hidden:
            self.show_window()

    # ------------------------------------------------------------------ plumbing
    def create_window(self, qml_file, props=None):
        comp = QQmlComponent(self.engine, QUrl.fromLocalFile(os.path.join(QML_DIR, "Mitsuke", qml_file)))
        obj = comp.createWithInitialProperties(props or {}) if props else comp.create()
        if obj is None:
            for e in comp.errors():
                logging.error("qml %s: %s", qml_file, e.toString())
            raise RuntimeError(f"{qml_file} failed to load")
        obj._component = comp
        return obj

    def call(self, fn, *args):
        """Run fn(*args) on the GUI thread (safe from any thread)."""
        self._invoke.emit((fn, args))

    @Slot(object)
    def _run(self, item):
        fn, args = item
        try:
            fn(*args)
        except Exception:  # noqa
            logging.exception("ui call failed")

    def ask(self, title, text, buttons, destructive=False):
        """Blocks the calling (non-GUI) thread until the user answers; returns the chosen value."""
        done, result = threading.Event(), []

        def answer(v):
            result.append(v)
            done.set()
        self.call(self.alert, title, text, buttons, answer, destructive)
        done.wait()
        return result[0]

    def alert(self, title, text, buttons, on_result=None, destructive=False):
        win = self.create_window("AlertWindow.qml")
        win.setProperty("title", title)
        win.setProperty("message", text)
        win.setProperty("buttons", [{"label": label, "value": v} for label, v in buttons])
        win.setProperty("destructive", destructive)
        self._alerts.append(win)
        hwnd = int(win.winId())
        native.native_frame(hwnd)
        self.frameless.hwnds.add(hwnd)
        self.frameless.fixed.add(hwnd)

        def done(v):
            self.frameless.hwnds.discard(hwnd)
            self.frameless.fixed.discard(hwnd)
            win.close()
            if win in self._alerts:
                self._alerts.remove(win)
            win.deleteLater()
            if on_result:
                on_result(v)
        win.answered.connect(done)
        if self.main.isVisible():
            g = self.main.geometry()
            win.setX(g.x() + (g.width() - win.width()) // 2)
            win.setY(g.y() + (g.height() - win.height()) // 3)
        else:
            s = QGuiApplication.primaryScreen().availableGeometry()
            win.setX(s.x() + (s.width() - win.width()) // 2)
            win.setY(s.y() + (s.height() - win.height()) // 3)
        mat = "acrylic" if not self.app.cfg["reduce_transparency"] else "solid"

        def first_frame():
            win.frameSwapped.disconnect(first_frame)
            QTimer.singleShot(30, lambda: (native.set_material(hwnd, mat, self.bridge.dark), self._repaint(win)))
        win.frameSwapped.connect(first_frame)
        win.show()
        win.raise_()
        win.requestActivate()

    # ------------------------------------------------------------------ main window
    def _first_frame(self):
        if not self._material_done:
            self._material_done = True
            QTimer.singleShot(30, self.apply_material)

    def apply_material(self):
        cfg = self.app.cfg
        material = "solid" if cfg["reduce_transparency"] else cfg["window_material"]
        native.set_material(int(self.main.winId()), material, self.bridge.dark)
        self._repaint(self.main)

    @staticmethod
    def _repaint(win):
        """DWM shows nothing new until the window presents a frame after a material change: ask for two."""
        win.update()
        QTimer.singleShot(60, win.update)
        QTimer.singleShot(250, win.update)

    def appearance_changed(self, dark):
        self.apply_material()
        self.app.current_word = None

    def show_window(self, page=None):
        if page:
            self.bridge.pageRequested.emit(page)
        self.bridge.refresh()
        w = self.main
        if w.visibility() == w.Visibility.Minimized:
            w.showNormal()
        w.show()
        w.raise_()
        w.requestActivate()
        try:                                          # bring it to the front even when launched from the tray
            ctypes.windll.user32.SetForegroundWindow(int(w.winId()))
        except Exception:  # noqa
            pass

    def hide_window(self):
        self._remember_geometry()
        self.main.hide()
        if not self.app.cfg["tray_hint_shown"]:            # once, not after every start
            self.app.cfg.set("tray_hint_shown", True)
            self.app.tray.notify("Mitsuke keeps running in the tray. Double-click the icon to open it.")

    # ------------------------------------------------------------------ persistence
    def _restore_geometry(self):
        g = self.app.cfg["win_geometry"]
        if not (isinstance(g, list) and len(g) == 4 and all(isinstance(v, (int, float)) for v in g)):
            return
        x, y, w, h = (int(v) for v in g)
        w, h = max(w, int(self.main.minimumWidth())), max(h, int(self.main.minimumHeight()))
        for s in QGuiApplication.screens():                # only if it's still on a connected screen
            a = s.availableGeometry()
            if a.x() - 40 <= x <= a.right() - 200 and a.y() - 10 <= y <= a.bottom() - 120:
                self.main.setWidth(min(w, a.width()))
                self.main.setHeight(min(h, a.height()))
                self.main.setX(x)
                self.main.setY(y)
                return

    def _remember_geometry(self):
        w = self.main
        try:
            if not w.isVisible() or w.visibility() != w.Visibility.Windowed:
                return
            g = [int(w.x()), int(w.y()), int(w.width()), int(w.height())]
            if g != self.app.cfg["win_geometry"]:
                self.app.cfg.set("win_geometry", g)
        except RuntimeError:
            pass

    def flush(self):
        """Everything that lives in memory goes to disk: slider values still settling, the window's place."""
        try:
            self.bridge._commit_live()
            self._remember_geometry()
            self.app.cfg.save()
        except Exception:  # noqa
            logging.exception("flush")

    def open_lookup(self, q):
        self.show_window()
        self.bridge.lookupRequested.emit(q)

    def refresh(self):
        self.bridge.refresh()

    def set_progress(self, text, frac=None, sub=""):
        self.bridge.set_progress(text, frac, sub)

    def settings_reloaded(self):
        self.apply_material()
        self.bridge.refresh()

    # ------------------------------------------------------------------ pronunciation
    def speak(self, key, word, audio):
        src = self.app.cfg["pron_source"]
        self.player.play(key, word, audio, source=src, voice_fallback=self.voice_available)

    # ------------------------------------------------------------------ overlays
    def pin(self, entries, word, src, context, x, y):
        self.card.hide()
        self.highlight.hide()
        if self.pinned:
            self.pinned.close()
        self.pinned = PinnedCard(self, entries, word, src, context, x, y, getattr(self.card, "last_avoid", None))

    def pin_sentence(self, text, translation, word, x, y, avoid=None):
        from .overlay import sentence_lines
        self.card.hide()
        self.highlight.hide()
        if self.pinned:
            self.pinned.close()
        self.pinned = PinnedCard(self, [], word, "", text, x, y, avoid,
                                 lines=sentence_lines(text, translation, "", self.app.cfg, pinned=True))

    # ------------------------------------------------------------------ lifetime
    def exec(self):
        return self.qapp.exec()

    def quit(self):
        self.flush()
        self.player.stop()
        self.card.stop_capture()
        if self.pinned:
            self.pinned.close()
        self.qapp.quit()
