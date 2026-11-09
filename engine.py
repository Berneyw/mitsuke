"""Объединяет офлайн-словарь (с кэшем в памяти) и онлайн-поиск."""
import os
import threading
from collections import OrderedDict

from dictcore import Dictionary
from online import Online

DB_NAME = "dict.sqlite"


class Engine:
    def __init__(self, cfg, data_dir, cache_size=4096):
        self.cfg, self.dir = cfg, data_dir
        self.db_path = os.path.join(data_dir, DB_NAME)
        self.online = Online(os.path.join(data_dir, "online_cache.sqlite"))
        self.dict = None
        self._lock = threading.Lock()
        self._cache, self._cache_size = OrderedDict(), cache_size
        self._stats = ""
        self.reload()

    @property
    def has_offline(self):
        return self.dict is not None

    @property
    def has_pronunciation(self):
        """Dictionaries built before 2.2 have no IPA / recordings columns."""
        if self.dict is None:
            return False
        try:
            return any(r[1] == "audio" for r in self.dict.db.execute("PRAGMA table_info(entries)"))
        except Exception:  # noqa
            return False

    def stats(self):
        return self._stats

    def close(self):
        with self._lock:
            if self.dict:
                self.dict.db.close()
            self.dict = None
            self._cache.clear()

    def reload(self):
        self.close()
        with self._lock:
            if os.path.exists(self.db_path):
                try:
                    self.dict = Dictionary(self.db_path)
                    n = self.dict.db.execute("SELECT count(*) FROM entries").fetchone()[0]
                    self._stats = f"{n:,} entries · {os.path.getsize(self.db_path) >> 20} MB"
                except Exception:  # noqa  битый файл
                    self.dict = None

    def lookup_offline(self, word):
        with self._lock:
            if word in self._cache:
                self._cache.move_to_end(word)
                return self._cache[word]
            res = self.dict.lookup(word) if self.dict else []
            self._cache[word] = res
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            return res

    def lookup_context(self, ctx):
        """Слово под курсором с учётом строки (Context из ocrword) -> (entries, слово для заголовка/онлайна)."""
        key = ("ctx",) + ctx.key()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            if self.dict:
                res = self.dict.lookup_context(ctx.tokens, ctx.idx, ctx.tight, frac=getattr(ctx, "frac", None))
            else:
                from dictcore import clean_token
                res = [], clean_token(ctx.word)
            self._cache[key] = res
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            return res

    def reading_score(self, ctx):
        """Quality of an OCR reading (see Dictionary.reading_score); without the offline dictionary every
        reading is taken as is."""
        if not self.dict:
            return 1.0
        with self._lock:
            return self.dict.reading_score(ctx.tokens, ctx.idx, ctx.tight, frac=getattr(ctx, "frac", None))

    def lookup(self, word):
        """Полный (блокирующий) поиск -> (entries, source)."""
        entries = self.lookup_offline(word)
        if entries:
            return entries, "offline"
        if self.cfg["online_fallback"]:
            entries = self.online.lookup(word)
            if entries:
                return entries, "online"
        return [], ""
