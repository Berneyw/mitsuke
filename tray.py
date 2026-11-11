"""Tray icon. Left click opens Mitsuke; right click shows the Liquid Glass menu (gui TrayMenu.qml).
The plain Windows menu remains only as a fallback while the interface is starting."""
import pystray
from PIL import Image, ImageDraw, ImageFont


def _asset(name):
    import os
    import sys
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "assets", name)


def make_icon(size=64) -> Image.Image:
    """The app icon: the "M" tile at small sizes (the word Mitsuke can't be read there), the full icon above."""
    try:
        name = "icon-small.png" if size <= 48 else "icon.png"
        return Image.open(_asset(name)).convert("RGBA").resize((size, size), Image.LANCZOS)
    except OSError:
        return _drawn_icon(size)


def _drawn_icon(size=64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((1, 1, size - 2, size - 2), radius=round(size * 0.24), fill=(0, 113, 227, 255))
    font = None
    for name in ("SF-Pro-Text-Semibold.otf", "seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(name, int(size * 0.62))
            break
        except OSError:
            continue
    d.text((size / 2, size / 2 + 1), "Ä", fill=(255, 255, 255, 255), font=font or ImageFont.load_default(), anchor="mm")
    return img


class _GlassIcon(pystray.Icon):
    """pystray icon whose right click opens our own glass menu instead of the native Win32 one."""
    on_menu = None

    def _assert_icon_handle(self):
        """Loads the tray frame straight from icon.ico at the small-icon size of this DPI, so Windows takes
        the pixel-aligned 16/20/24/32 px "M" drawn for it instead of shrinking a big image."""
        if self._icon_handle:
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            u.LoadImageW.restype = ctypes.c_void_p
            s = u.GetSystemMetricsForDpi(49, u.GetDpiForSystem()) if hasattr(u, "GetDpiForSystem") else u.GetSystemMetrics(49)
            h = u.LoadImageW(None, _asset("icon.ico"), 1, s, s, 0x10)   # IMAGE_ICON, LR_LOADFROMFILE
            if h:
                self._icon_handle = h
                return
        except Exception:  # noqa
            pass
        super()._assert_icon_handle()

    def _on_notify(self, wparam, lparam):
        try:
            from pystray._win32 import win32
            if lparam == win32.WM_RBUTTONUP and self.on_menu:
                import ctypes
                from ctypes import wintypes
                pt = wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                self.on_menu(pt.x, pt.y)
                return
        except Exception:  # noqa
            pass
        super()._on_notify(wparam, lparam)


class Tray:
    def __init__(self, app):
        self.app = app
        a, cfg = app, app.cfg
        M, I = pystray.Menu, pystray.MenuItem

        def key_item(k, label):
            return I(label, lambda: a.ui.call(a.set_setting, "key", k), checked=lambda _i: cfg["key"] == k, radio=True)

        menu = M(
            I("Open Mitsuke", lambda: a.show_window(), default=True),
            I(lambda _i: a.status_text(), None, enabled=False),
            M.SEPARATOR,
            I(lambda _i: "Resume Scanning" if not cfg["enabled"] else "Pause Scanning",
              lambda: a.ui.call(a.set_setting, "enabled", not cfg["enabled"])),
            I("Trigger Key", M(key_item("shift", "Shift"), key_item("ctrl", "Ctrl"), key_item("alt", "Alt"))),
            I("Settings…", lambda: a.show_window("settings")),
            M.SEPARATOR,
            I("Quit Mitsuke", lambda: a.quit()),
        )
        self.icon = _GlassIcon("Mitsuke", make_icon(), "Mitsuke", menu)

        def glass_menu(x, y):
            gui = getattr(a, "gui", None)
            if gui is not None and getattr(gui, "tray_menu", None) is not None:
                a.ui.call(gui.tray_menu.open, x, y)
        self.icon.on_menu = glass_menu

    def run(self):
        self.icon.run_detached()

    def notify(self, msg, title="Mitsuke"):
        try:
            self.icon.notify(msg, title)
        except Exception:  # noqa
            pass

    def refresh(self):
        try:
            self.icon.update_menu()
        except Exception:  # noqa
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:  # noqa
            pass
