"""Pronunciation: native-speaker recordings from Wikimedia Commons (the files Wiktionary links to), cached on
disk, with Windows' own German voice when there is no recording.

Commons stores recordings as Ogg; it also serves an MP3 rendition of every file, which Windows plays through
MCI without extra libraries. File URLs are derived from the file name (Commons' md5 path scheme)."""
import ctypes
import hashlib
import logging
import os
import threading
import urllib.parse
import urllib.request

COMMONS = "https://upload.wikimedia.org/wikipedia/commons/"
UA = "Mitsuke (German dictionary overlay; https://github.com/Berneyw/mitsuke)"


def recording_url(name):
    """MP3 rendition of a Commons audio file: …/transcoded/a/ab/De-Haus.ogg/De-Haus.ogg.mp3."""
    name = name.replace(" ", "_")
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    q = urllib.parse.quote(name)
    if name.lower().endswith((".mp3", ".wav")):
        return f"{COMMONS}{h[0]}/{h[:2]}/{q}"
    return f"{COMMONS}transcoded/{h[0]}/{h[:2]}/{q}/{q}.mp3"


class Player:
    """Plays one thing at a time; a new request stops the previous one. on_state(key, playing) reports
    which word is sounding so the speaker buttons can animate."""

    def __init__(self, cache_dir, on_state=None):
        self.cache_dir = os.path.join(cache_dir, "audio")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.on_state = on_state or (lambda key, playing: None)
        self._gen = 0
        self._lock = threading.Lock()
        self._mci = ctypes.windll.winmm.mciSendStringW
        self._alias = None
        self.volume = 80                                   # 0..100

    def set_volume(self, percent):
        """Applies at once, also to a word that is sounding right now (the slider moves live)."""
        self.volume = max(0, min(100, int(percent)))
        alias = self._alias
        if alias:
            self._mci(f"setaudio {alias} volume to {self.volume * 10}", None, 0, 0)

    # ------------------------------------------------------------------ public
    def play(self, key, word, recordings, source="recordings", voice_fallback=True):
        """source: recordings (Wiktionary first, Windows voice if none) | voice (always the Windows voice)."""
        with self._lock:
            self._gen += 1
            gen = self._gen
        self.stop(notify=False)
        threading.Thread(target=self._run, args=(gen, key, word, list(recordings or []), source, voice_fallback),
                         daemon=True, name="pronounce").start()

    def stop(self, notify=True):
        alias = self._alias
        if alias:
            self._mci(f"stop {alias}", None, 0, 0)
            self._mci(f"close {alias}", None, 0, 0)
            self._alias = None

    def has_recording_cached(self, recordings):
        return any(os.path.exists(self._cache_path(r["f"])) for r in recordings or [])

    # ------------------------------------------------------------------ worker
    def _cache_path(self, name):
        base = name.replace(" ", "_")
        ext = ".wav" if base.lower().endswith(".wav") else ".mp3"
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in base)
        return os.path.join(self.cache_dir, safe + ("" if safe.lower().endswith(ext) else ext))

    def _fetch(self, name):
        path = self._cache_path(name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
        req = urllib.request.Request(recording_url(name), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if len(data) < 256:
            raise OSError("empty recording")
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return path

    def _run(self, gen, key, word, recordings, source, voice_fallback):
        self.on_state(key, True)
        try:
            if source != "voice":
                for rec in recordings:
                    if gen != self._gen:
                        return
                    try:
                        path = self._fetch(rec["f"])
                    except Exception as e:  # noqa — offline, file gone: try the next one, then the voice
                        logging.info("recording %s unavailable: %s", rec.get("f"), e)
                        continue
                    if gen == self._gen:
                        self._play_file(path, gen)
                    return
                if not voice_fallback:
                    return
            if gen == self._gen:
                path = self._speak_to_file(word)
                if path and gen == self._gen:
                    self._play_file(path, gen)
        except Exception:  # noqa
            logging.exception("pronunciation")
        finally:
            if gen == self._gen:
                self.on_state(key, False)

    def _play_file(self, path, gen):
        alias = f"mitsuke{gen}"
        # mpegvideo (DirectShow) plays both MP3 and WAV and, unlike waveaudio, has a volume control
        if self._mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0) != 0:
            raise OSError(f"cannot open {path}")
        self._alias = alias
        self._mci(f"setaudio {alias} volume to {self.volume * 10}", None, 0, 0)
        try:
            self._mci(f"play {alias} wait", None, 0, 0)          # returns when done or when stopped
        finally:
            self._mci(f"close {alias}", None, 0, 0)
            if self._alias == alias:
                self._alias = None

    def _speak_to_file(self, text):
        """Windows' German voice (Katja / Hedda / Stefan when installed) rendered to a cached WAV."""
        safe = "".join(ch if ch.isalnum() else "_" for ch in text)[:60]
        path = os.path.join(self.cache_dir, f"voice-{safe}-{hashlib.md5(text.encode('utf-8')).hexdigest()[:8]}.wav")
        if os.path.exists(path):
            return path
        try:
            from winrt.windows.media.speechsynthesis import SpeechSynthesizer
            from winrt.windows.storage.streams import DataReader
        except ImportError:
            logging.info("speech synthesis unavailable")
            return None
        synth = SpeechSynthesizer()
        german = [v for v in SpeechSynthesizer.all_voices if v.language.lower().startswith("de")]
        if not german:
            logging.info("no German voice installed")
            return None
        synth.voice = german[0]
        stream = synth.synthesize_text_to_stream_async(text).get()
        size = stream.size
        reader = DataReader(stream.get_input_stream_at(0))
        reader.load_async(size).get()
        buf = bytearray(size)
        reader.read_bytes(buf)
        with open(path, "wb") as f:
            f.write(bytes(buf))
        return path


def german_voice_available():
    try:
        from winrt.windows.media.speechsynthesis import SpeechSynthesizer
        return any(v.language.lower().startswith("de") for v in SpeechSynthesizer.all_voices)
    except Exception:  # noqa
        return False
