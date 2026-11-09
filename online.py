"""Запасной онлайн-поиск через Wiktionary REST API с кэшем (работает, пока офлайн-словарь не собран
или если слова в нём нет). Род здесь недоступен — он есть только в офлайн-словаре."""
import html
import json
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from dictcore import Entry

UA = "Mitsuke/1.0 (German learning overlay)"
API = "https://en.wiktionary.org/api/rest_v1/page/definition/"
POS_MAP = {"noun": "noun", "verb": "verb", "adjective": "adj", "adverb": "adv", "preposition": "prep",
           "conjunction": "conj", "pronoun": "pron", "numeral": "num", "interjection": "intj",
           "particle": "particle", "article": "det", "proper noun": "name", "contraction": "phrase"}
NEG_TTL = 24 * 3600


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_response(data: dict):
    """JSON Wiktionary REST -> список Entry (только немецкий раздел)."""
    out = []
    for item in data.get("de", []):
        senses = []
        for d in item.get("definitions", []):
            gloss = _strip(d.get("definition", ""))
            if not gloss:
                continue
            ex = None
            for x in d.get("examples", []) or d.get("parsedExamples", []):
                t = _strip(x if isinstance(x, str) else x.get("example", ""))
                if t:
                    ex = {"text": t, "english": ""}
                    break
            senses.append({"gloss": gloss, "tags": [], "example": ex if len(senses) < 2 else None})
            if len(senses) >= 5:
                break
        if senses:
            pos = POS_MAP.get((item.get("partOfSpeech") or "").lower(), (item.get("partOfSpeech") or "").lower())
            out.append(Entry(word="", pos=pos, en=senses))
    return out


class Online:
    def __init__(self, cache_path: str, timeout: float = 3.5):
        self.timeout = timeout
        self.db = sqlite3.connect(cache_path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS cache(word TEXT PRIMARY KEY, data TEXT, ts REAL)")
        self.db.commit()

    def _cached(self, word):
        with self.lock:
            r = self.db.execute("SELECT data, ts FROM cache WHERE word=?", (word,)).fetchone()
        if not r:
            return None
        data = json.loads(r[0])
        if data is None and time.time() - r[1] > NEG_TTL:
            return None
        return data

    def _store(self, word, data):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (word, json.dumps(data), time.time()))
            self.db.commit()

    def _fetch(self, title):
        req = urllib.request.Request(API + urllib.parse.quote(title, safe=""), headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def lookup(self, token: str):
        """Возвращает список Entry или [] (нет слова / нет сети)."""
        variants = []
        for v in (token, token.lower(), token[:1].upper() + token[1:].lower()):
            if v and v not in variants:
                variants.append(v)
        for v in variants:
            data = self._cached(v)
            if data is None and self._cached_known_missing(v):
                continue
            if data is None:
                try:
                    data = self._fetch(v)
                except (urllib.error.URLError, OSError, TimeoutError, ValueError):
                    return []                      # нет сети: не кэшируем
                self._store(v, data)
            entries = parse_response(data) if data else []
            if entries:
                for e in entries:
                    e.word = v
                    e.via = "" if v == token or v.lower() == token.lower() else ""
                return entries
        return []

    def _cached_known_missing(self, word):
        with self.lock:
            r = self.db.execute("SELECT data, ts FROM cache WHERE word=?", (word,)).fetchone()
        return bool(r and json.loads(r[0]) is None and time.time() - r[1] <= NEG_TTL)
