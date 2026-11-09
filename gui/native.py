"""Win32 glue for the Qt windows: the Acrylic / Mica material, a frameless window that still behaves like a
native one (snap, shadow, rounded corners, resize borders), and the overlay flags (never activated,
click-through, excluded from screen capture so OCR and our own glass never see it)."""
import ctypes
import ctypes.wintypes as wt
import logging
import os

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CAPTION, WS_THICKFRAME, WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0xC00000, 0x40000, 0x20000, 0x10000, 0x80000
WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x08000000, 0x80, 0x20, 0x80000
WDA_EXCLUDEFROMCAPTURE = 0x11
DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWA_SYSTEMBACKDROP_TYPE = 20, 33, 38
WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
HTCLIENT, HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT, HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = \
    1, 10, 11, 12, 13, 14, 15, 16, 17

user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]


class _MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


class _ACCENT(ctypes.Structure):
    _fields_ = [("state", ctypes.c_int), ("flags", ctypes.c_int), ("color", ctypes.c_uint), ("anim", ctypes.c_int)]


class _WCAD(ctypes.Structure):
    _fields_ = [("attr", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]


def _attr(hwnd, attr, value):
    v = ctypes.c_int(value)
    return dwmapi.DwmSetWindowAttribute(wt.HWND(hwnd), attr, ctypes.byref(v), 4)


def set_material(hwnd, material, dark):
    """material: acrylic | mica | solid. The window must be per-pixel transparent (alpha buffer):
    whatever QML leaves see-through shows the material, live, including when the window is inactive."""
    try:
        _attr(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
        _attr(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, 2)
        dwmapi.DwmExtendFrameIntoClientArea(wt.HWND(hwnd), ctypes.byref(_MARGINS(-1, -1, -1, -1)))
        if material == "acrylic":
            _attr(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, 1)
            # ACCENT_ENABLE_ACRYLICBLURBEHIND: the live blur of the desktop and windows behind. Colour is AABBGGRR;
            # QML lays its own tint on top, so this one stays nearly clear.
            tint = 0x01161618 if dark else 0x01f4f4f6
            _accent(hwnd, 4, tint)
        elif material == "mica":
            _accent(hwnd, 0, 0)
            _attr(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, 2)
        else:
            _accent(hwnd, 0, 0)
            _attr(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, 1)
    except Exception:  # noqa
        logging.info("material unavailable", exc_info=True)


def _accent(hwnd, state, color):
    acc = _ACCENT(state, 2, color, 0)
    data = _WCAD(19, ctypes.cast(ctypes.byref(acc), ctypes.c_void_p), ctypes.sizeof(acc))
    user32.SetWindowCompositionAttribute(wt.HWND(hwnd), ctypes.byref(data))


def round_corners(hwnd, small=False):
    try:
        _attr(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, 3 if small else 2)
    except Exception:  # noqa
        pass


def native_frame(hwnd):
    """A frameless Qt window gets back the styles that give it snap, minimize animation and the DWM shadow;
    FramelessFilter then removes the visible frame."""
    st = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (st | WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
                             & ~WS_SYSMENU)   # no system menu: DWM then draws no caption buttons under ours
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0027)        # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED


def overlay_window(hwnd, click_through=True):
    """In-game card / highlight: never takes focus, optionally ignores the mouse, invisible to screen capture."""
    try:
        st = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        st |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        if click_through:
            st |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, st)
        if not os.environ.get("MITSUKE_CAPTURABLE"):     # test screenshots only
            user32.SetWindowDisplayAffinity(wt.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE)
    except Exception:  # noqa
        logging.info("overlay styles partly unavailable", exc_info=True)


def exclude_from_capture(hwnd):
    """Invisible to screen capture (our own live glass must not photograph itself)."""
    try:
        if not os.environ.get("MITSUKE_CAPTURABLE"):
            user32.SetWindowDisplayAffinity(wt.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE)
        st = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, st | WS_EX_TOOLWINDOW)
    except Exception:  # noqa
        pass


def is_maximized(hwnd):
    return bool(user32.IsZoomed(wt.HWND(hwnd)))


def work_area(x, y):
    """Work area (without taskbar) of the monitor that contains (x, y), physical pixels."""
    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
    try:
        user32.MonitorFromPoint.restype = wt.HANDLE
        user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
        hmon = user32.MonitorFromPoint(wt.POINT(int(x), int(y)), 2)
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcWork
        return r.left, r.top, r.right, r.bottom
    except Exception:  # noqa
        return 0, 0, 1920, 1080


def system_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return True


class FramelessFilter:
    """Native event handling for the main window (installed through QAbstractNativeEventFilter):
    WM_NCCALCSIZE removes the frame, WM_NCHITTEST gives resize borders. Dragging and the caption buttons are
    QML (startSystemMove keeps Aero Snap)."""

    def __init__(self, border=6):
        self.hwnds = set()
        self.fixed = set()                 # frameless but not resizable (alerts)
        self.border = border

    def handle(self, msg):
        if msg.hWnd not in self.hwnds:
            return None
        if msg.message == WM_NCCALCSIZE and msg.wParam:
            if is_maximized(msg.hWnd):                # a maximized window overhangs the screen by its frame
                params = ctypes.cast(msg.lParam, ctypes.POINTER(wt.RECT))
                f = user32.GetSystemMetrics(32) + user32.GetSystemMetrics(92)   # SM_CXFRAME + SM_CXPADDEDBORDER
                r = params[0]
                r.left += f
                r.top += f
                r.right -= f
                r.bottom -= f
            return 0
        if msg.message == WM_NCHITTEST:
            if msg.hWnd in self.fixed or is_maximized(msg.hWnd):
                return HTCLIENT
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            r = wt.RECT()
            user32.GetWindowRect(msg.hWnd, ctypes.byref(r))
            b = self.border
            left, right = x < r.left + b, x >= r.right - b
            top, bottom = y < r.top + b, y >= r.bottom - b
            if top and left:
                return HTTOPLEFT
            if top and right:
                return HTTOPRIGHT
            if bottom and left:
                return HTBOTTOMLEFT
            if bottom and right:
                return HTBOTTOMRIGHT
            if left:
                return HTLEFT
            if right:
                return HTRIGHT
            if top:
                return HTTOP
            if bottom:
                return HTBOTTOM
            return HTCLIENT
        return None
