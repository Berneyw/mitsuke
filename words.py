"""My Words: saved words with the sentence they were found in, spaced-repetition review, Anki export.

Scheduling is a compact SM-2 variant (Again / Hard / Good / Easy), the same family Anki uses.
"""
import json
import sqlite3
import threading
import time

DAY = 86400.0
GRADES = ("again", "hard", "good", "easy")


class WordStore:
    def __init__(self, path):
        self.path = path
        self.backup_path = path.replace(".sqlite", ".backup.sqlite")
        self.restored = False                     # the file was damaged and the backup was used
        self.db = self._open(path)
        self.lock = threading.Lock()
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS words(
            id INTEGER PRIMARY KEY, word TEXT NOT NULL, pos TEXT DEFAULT '', gender TEXT DEFAULT '',
            gloss TEXT DEFAULT '', forms TEXT DEFAULT '', context TEXT DEFAULT '', source TEXT DEFAULT '',
            added REAL, due REAL, interval REAL DEFAULT 0, ease REAL DEFAULT 2.5, reps INTEGER DEFAULT 0,
            lapses INTEGER DEFAULT 0, UNIQUE(word, pos));
        """)
        self.db.commit()

    def _open(self, path):
        """Opens the database, checking it; a damaged file is set aside and the last backup takes its place."""
        import os
        try:
            db = sqlite3.connect(path, check_same_thread=False)
            if db.execute("PRAGMA quick_check").fetchone()[0] == "ok":
                db.execute("PRAGMA synchronous=FULL")          # every saved word is on disk before we continue
                return db
            db.close()
        except sqlite3.DatabaseError:
            pass
        try:
            os.replace(path, path.replace(".sqlite", f".damaged-{int(time.time())}.sqlite"))
        except OSError:
            pass
        if os.path.exists(self.backup_path):
            import shutil
            shutil.copy2(self.backup_path, path)
            self.restored = True
        return sqlite3.connect(path, check_same_thread=False)

    def backup(self, max_age=DAY):
        """A consistent copy next to the database (words.backup.sqlite), refreshed at most once a day and
        never from an empty list over a non-empty backup."""
        import os
        try:
            if os.path.exists(self.backup_path) and time.time() - os.path.getmtime(self.backup_path) < max_age:
                return False
            if self.count() == 0 and os.path.exists(self.backup_path):
                return False
            tmp = self.backup_path + ".tmp"
            if os.path.exists(tmp):
                os.remove(tmp)
            with self.lock:
                dst = sqlite3.connect(tmp)
                self.db.backup(dst)
                dst.close()
            os.replace(tmp, self.backup_path)
            return True
        except (OSError, sqlite3.Error):
            return False

    # ------------------------------------------------------------------ editing
    def add(self, word, pos="", gender="", gloss="", forms="", context="", source="game"):
        """Saves a word (or refreshes an existing one). Returns (id, created)."""
        now = time.time()
        with self.lock:
            row = self.db.execute("SELECT id, context FROM words WHERE word=? AND pos=?", (word, pos)).fetchone()
            if row:
                if context and not row[1]:
                    self.db.execute("UPDATE words SET context=? WHERE id=?", (context, row[0]))
                    self.db.commit()
                return row[0], False
            cur = self.db.execute(
                "INSERT INTO words(word,pos,gender,gloss,forms,context,source,added,due) VALUES(?,?,?,?,?,?,?,?,?)",
                (word, pos, gender, gloss, forms, context, source, now, now))
            self.db.commit()
            return cur.lastrowid, True

    def add_entry(self, e, context="", source="game"):
        import render
        gloss = "; ".join(s["gloss"] for s in e.en[:2]) if e.en else (e.de[0] if e.de else "")
        return self.add(e.word, e.pos or "", (e.gender.split()[0] if e.gender else ""), gloss,
                        render.forms_line(e), context.strip(), source)

    def has(self, word, pos=""):
        with self.lock:
            return self.db.execute("SELECT 1 FROM words WHERE word=? AND pos=?", (word, pos)).fetchone() is not None

    def remove(self, wid):
        with self.lock:
            self.db.execute("DELETE FROM words WHERE id=?", (wid,))
            self.db.commit()

    def remove_word(self, word, pos=""):
        with self.lock:
            self.db.execute("DELETE FROM words WHERE word=? AND pos=?", (word, pos))
            self.db.commit()

    # ------------------------------------------------------------------ reading
    def _rows(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def all(self, query=""):
        q = f"%{query.strip()}%"
        return self._rows("SELECT * FROM words WHERE word LIKE ? OR gloss LIKE ? OR context LIKE ? ORDER BY added DESC",
                          (q, q, q))

    def count(self):
        with self.lock:
            return self.db.execute("SELECT count(*) FROM words").fetchone()[0]

    def due(self, now=None):
        return self._rows("SELECT * FROM words WHERE due <= ? ORDER BY due", (now or time.time(),))

    def due_count(self, now=None):
        with self.lock:
            return self.db.execute("SELECT count(*) FROM words WHERE due <= ?", (now or time.time(),)).fetchone()[0]

    # ------------------------------------------------------------------ review
    @staticmethod
    def schedule(card, grade):
        """-> (interval_days, ease, reps, lapses). Again = relearn in 10 minutes."""
        iv, ease, reps, lapses = card["interval"] or 0.0, card["ease"] or 2.5, card["reps"] or 0, card["lapses"] or 0
        if grade == "again":
            return 10 / 1440, max(1.3, ease - 0.2), 0, lapses + 1
        if grade == "hard":
            return max(1.0, iv * 1.2) if reps else 1.0, max(1.3, ease - 0.15), reps + 1, lapses
        good = 1.0 if reps == 0 else 3.0 if reps == 1 else max(iv + 1, iv * ease)
        if grade == "good":
            return good, ease, reps + 1, lapses
        return good * 1.3, ease + 0.15, reps + 1, lapses              # easy

    def review(self, wid, grade, now=None):
        now = now or time.time()
        card = self._rows("SELECT * FROM words WHERE id=?", (wid,))[0]
        iv, ease, reps, lapses = self.schedule(card, grade)
        with self.lock:
            self.db.execute("UPDATE words SET interval=?, ease=?, reps=?, lapses=?, due=? WHERE id=?",
                            (iv, ease, reps, lapses, now + iv * DAY, wid))
            self.db.commit()
        return iv

    # ------------------------------------------------------------------ export
    def export_anki(self, path):
        """Tab-separated file that Anki imports directly (File → Import): Front, Back, Context, Tags."""
        rows = self._rows("SELECT * FROM words ORDER BY added")
        art = {"m": "der ", "f": "die ", "n": "das "}

        def clean(s):
            return (s or "").replace("\t", " ").replace("\n", " ").strip()
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("#separator:tab\n#html:false\n#tags column:4\n")
            for r in rows:
                front = art.get(r["gender"], "") + r["word"]
                back = r["gloss"] + (f"  ({r['forms']})" if r["forms"] else "")
                tags = " ".join(t for t in ("mitsuke", r["pos"].replace(" ", "_")) if t)
                f.write("\t".join(clean(x) for x in (front, back, r["context"], tags)) + "\n")
        return len(rows)

    def export_json(self):
        return json.dumps(self._rows("SELECT * FROM words"), ensure_ascii=False)


def interval_label(days):
    if days < 1 / 24:
        return f"{max(1, round(days * 1440))} min"
    if days < 1:
        return f"{round(days * 24)} h"
    if days < 30:
        return f"{round(days)} d"
    if days < 365:
        return f"{round(days / 30)} mo"
    return f"{days / 365:.1f} y"
