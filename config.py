"""Настройки приложения: %APPDATA%\\Mitsuke\\config.json."""
import json
import os
import threading

APP = "Mitsuke"
OLD_APP = "SimsDict"           # the app's former name: its data folder moves over on first start
DEFAULTS = {
    "key": "shift",            # shift | ctrl | alt
    "lang": "de",              # язык OCR
    "scale": 2,                # увеличение снимка перед OCR (1-3)
    "font_size": 11,
    "hold_ms": 150,            # сколько держать клавишу, прежде чем искать слово
    "enabled": True,
    "online_fallback": True,   # искать в Wiktionary, если слова нет в офлайн-словаре
    "german_definitions": True,  # добавлять толкования на немецком
    "autostart": False,
    "dict_offered": False,     # уже предлагали скачать офлайн-словарь
    # appearance
    "appearance": "system",    # system | light | dark
    "window_material": "acrylic",  # acrylic | mica | solid (sidebar + title bar, dark appearance)
    "recent": [],              # last searches in Lookup
    "pin_double_tap": True,    # double-tap the scan key to pin the card
    "highlight": True,         # tint the word being read (and words linked to it)
    "highlight_area": False,   # also outline the strip that is read (debugging aid)
    "update_check": True,      # look for new versions on start (once a day)
    "update_repo": "Berneyw/mitsuke",  # GitHub "owner/repo" that publishes Mitsuke releases
    "update_last_check": 0.0,
    # recognition
    "capture_width": 1200,     # ширина полосы захвата вокруг курсора, px
    # word card
    "card_width": 440,
    "card_entries": 3,         # сколько статей показывать
    "card_senses": 3,          # сколько значений у статьи
    "card_examples": True,
    "card_position": "below",  # below | above
    # Liquid Glass
    "glass": True,
    "glass_style": "glass",    # glass | clear | tinted
    "glass_transparency": 55,  # 0..100
    "glass_thickness": "regular",  # thin | regular | thick
    "glass_highlight": True,
    "reduce_transparency": False,
    "increase_contrast": False,
    "reduce_motion": False,
    # pronunciation
    "pron_source": "recordings",   # recordings (native speakers, Windows voice if none) | voice (Windows voice)
    "pron_ipa": True,              # show the IPA transcription next to the word
    "pron_autoplay": False,        # speak the word when the in-game card appears
    "pron_volume": 80,             # 0..100
    # window state
    "win_geometry": [],            # [x, y, width, height] of the main window
    "last_page": "lookup",
    "tray_hint_shown": False,      # the "keeps running in the tray" tip was shown once
    "history_imported": False,     # lookups from the log of versions before History were imported once
}


def data_dir() -> str:
    override = os.environ.get("MITSUKE_DATA_DIR")        # tests and portable setups: never the real profile
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    p = os.path.join(base, APP)
    old = os.path.join(base, OLD_APP)
    if not os.path.exists(p) and os.path.isdir(old):
        try:                               # settings, dictionary and saved words come along unchanged
            os.replace(old, p)
        except OSError:                    # a file is still open (the old app running): copy instead
            import shutil
            shutil.copytree(old, p, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.tmp", "*.new", "*.shot-bak"))
        log = os.path.join(p, "simsdict.log")
        if os.path.exists(log) and not os.path.exists(os.path.join(p, "mitsuke.log")):
            try:
                os.replace(log, os.path.join(p, "mitsuke.log"))
            except OSError:
                pass
    os.makedirs(p, exist_ok=True)
    return p


CHOICES = {"key": ("shift", "ctrl", "alt"), "appearance": ("system", "light", "dark"),
           "window_material": ("acrylic", "mica", "solid"), "card_position": ("below", "above"),
           "glass_style": ("glass", "clear", "tinted"), "glass_thickness": ("thin", "regular", "thick"),
           "pron_source": ("recordings", "voice"), "scale": (1, 2, 3)}


class Config:
    """Settings in config.json. Built not to lose them:
    - every save is written to a temporary file, flushed to disk (fsync) and swapped in atomically;
    - a second copy, config.json.bak, is written the same way and used if the main file is missing or damaged
      (power cut or forced shutdown in the middle of a write);
    - a damaged file is never silently replaced by defaults: it is kept as config.damaged-*.json;
    - each value is checked on load, so one bad value can't reset the others."""

    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "config.json")
        self.bak = self.path + ".bak"
        self._lock = threading.RLock()
        self.data = dict(DEFAULTS)
        self.loaded_from = "defaults"                    # main | backup | defaults (for the log)
        self.problem = ""
        raw = self._read(self.path)
        if raw is not None:
            self.loaded_from = "main"
        else:
            if os.path.exists(self.path):                # unreadable: keep it for inspection, don't overwrite
                self.problem = "config.json was damaged"
                try:
                    import time
                    os.replace(self.path, self.path.replace(".json", f".damaged-{int(time.time())}.json"))
                except OSError:
                    pass
            raw = self._read(self.bak)
            if raw is not None:
                self.loaded_from = "backup"
        if raw:
            for k, v in raw.items():
                if self._valid(k, v):
                    self.data[k] = v
            if self.loaded_from == "backup":
                with self._lock:
                    self._save()

    @staticmethod
    def _read(path):
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, dict) and raw else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _valid(k, v):
        if k not in DEFAULTS:
            return False
        d = DEFAULTS[k]
        if isinstance(d, bool):
            ok = isinstance(v, bool)
        elif isinstance(d, (int, float)):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        else:
            ok = type(v) is type(d)
        return ok and (k not in CHOICES or v in CHOICES[k])

    def __getitem__(self, k):
        return self.data[k]

    def set(self, k, v):
        with self._lock:
            self.data[k] = v
            self._save()

    def save(self):
        with self._lock:
            self._save()

    def _save(self):
        text = json.dumps(self.data, indent=2, ensure_ascii=False)
        for target in (self.path, self.bak):             # two independent copies, each swapped in atomically
            tmp = f"{target}.{os.getpid()}.tmp"          # per process: two instances can't clobber each other
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())                 # on disk before it replaces anything
                os.replace(tmp, target)
            except OSError:
                if target == self.path:
                    raise

    def reset(self):
        """Back to defaults (keeps the 'dictionary already offered' flag so the prompt doesn't reappear)."""
        with self._lock:
            offered = self.data.get("dict_offered", False)
            self.data = dict(DEFAULTS, dict_offered=offered)
            self._save()

    def export(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in self.data.items() if k != "dict_offered"}, f, indent=2, ensure_ascii=False)

    def import_(self, path):
        """Loads known keys with the same type as the default; returns how many were applied."""
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("not a Mitsuke settings file")
        n = 0
        with self._lock:
            for k, v in raw.items():
                if k != "dict_offered" and self._valid(k, v):
                    self.data[k] = v
                    n += 1
            self._save()
        return n
