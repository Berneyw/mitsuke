"""Whole-sentence translation (the sentence key). Google Translate's public web endpoint: no key, no account.
Only the sentence under the cursor is sent; results are cached on disk, so a sentence read again is instant
and works offline."""
import json
import sqlite3
import threading
import time
import urllib.parse
import urllib.request

URL = "https://translate.googleapis.com/translate_a/single"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# target languages offered in Settings: (code, name in that language)
LANGUAGES = [("en", "English"), ("ru", "Русский"), ("uk", "Українська"), ("pl", "Polski"), ("tr", "Türkçe"),
             ("es", "Español"), ("fr", "Français"), ("it", "Italiano"), ("pt", "Português"), ("nl", "Nederlands"),
             ("cs", "Čeština"), ("ja", "日本語"), ("zh-CN", "中文"), ("ko", "한국어")]


class TranslateError(RuntimeError):
    pass


def parse(data):
    """Response of translate_a/single (dt=t) -> translated text."""
    try:
        return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
    except (TypeError, IndexError):
        raise TranslateError("unexpected response") from None


class Translator:
    def __init__(self, cache_path, timeout=6.0):
        self.timeout = timeout
        self.lock = threading.Lock()
        self.db = sqlite3.connect(cache_path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS sentences(src TEXT, lang TEXT, text TEXT, ts REAL,"
                        " PRIMARY KEY(src, lang))")
        self.db.commit()

    def cached(self, text, lang):
        with self.lock:
            row = self.db.execute("SELECT text FROM sentences WHERE src=? AND lang=?", (text, lang)).fetchone()
        return row[0] if row else None

    def translate(self, text, lang="en", source="de"):
        text = " ".join(text.split())
        if not text:
            return ""
        hit = self.cached(text, lang)
        if hit is not None:
            return hit
        body = urllib.parse.urlencode({"q": text}).encode()
        query = urllib.parse.urlencode({"client": "gtx", "sl": source, "tl": lang, "dt": "t", "ie": "UTF-8",
                                        "oe": "UTF-8"})
        req = urllib.request.Request(f"{URL}?{query}", data=body, headers={
            "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = parse(json.loads(r.read().decode("utf-8")))
        except TranslateError:
            raise
        except Exception as e:  # noqa — offline, blocked, rate-limited
            raise TranslateError(str(e)) from e
        if out:
            with self.lock:
                self.db.execute("INSERT OR REPLACE INTO sentences VALUES(?,?,?,?)", (text, lang, out, time.time()))
                self.db.commit()
        return out

    def close(self):
        with self.lock:
            self.db.close()
