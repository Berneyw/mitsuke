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
}


def data_dir() -> str:
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


class Config:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "config.json")
        self._lock = threading.Lock()
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def __getitem__(self, k):
        return self.data[k]

    def set(self, k, v):
        with self._lock:
            self.data[k] = v
            self._save()

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

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
                if k in DEFAULTS and k != "dict_offered" and type(v) is type(DEFAULTS[k]):
                    self.data[k] = v
                    n += 1
            self._save()
        return n
