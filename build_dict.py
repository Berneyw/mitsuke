"""Собирает словарь dict.sqlite из дампов Wiktionary (kaikki.org).

  python build_dict.py                     # скачает оба дампа (~1-2 ГБ) и соберёт базу
  python build_dict.py --en en.jsonl --de de.jsonl
  python build_dict.py --en tests/sample_en.jsonl --out test.sqlite --no-de

EN-дамп (английский Wiktionary, немецкие слова): перевод на английский, род, число, формы.
DE-дамп (немецкий Wiktionary): толкования на немецком (необязательно).
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import http.client
import time
import urllib.error
import urllib.request

try:
    import orjson as _fastjson          # в 3-5 раз быстрее разбор JSON
    _loads = _fastjson.loads
except ImportError:
    _loads = json.loads

EN_URL = "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl"
DE_URL = "https://kaikki.org/dewiktionary/Deutsch/kaikki.org-dictionary-Deutsch.jsonl"

POS_DE = {"substantiv": "noun", "verb": "verb", "adjektiv": "adj", "adverb": "adv", "präposition": "prep",
          "konjunktion": "conj", "pronomen": "pron", "numerale": "num", "interjektion": "intj",
          "partikel": "particle", "artikel": "det", "name": "name"}
SKIP_FORM_TAGS = {"table-tags", "inflection-template", "class", "romanization"}
GENDER_RE = re.compile(r"^\S+\s+(m or f|f or m|m or n|n or m|mf|m|f|n|pl)\b")
PLURAL_RE = re.compile(r"\bplural ([^\s,()]+)")
# немецкий Wiktionary: служебные «толкования» словоформ — «Genitiv Singular des Substantivs Hau»
DE_FORM_GLOSS = re.compile(
    r"^(\d\.\s*Person|Nominativ|Genitiv|Dativ|Akkusativ|Plural|Singular|Partizip|Imperativ|Infinitiv|"
    r"Komparativ|Superlativ|Positiv|Präteritum|Präsens|Konjunktiv|erweiterter Infinitiv|"
    r"(starke|schwache|gemischte) Deklination|Variante|Nebenform|alternative Schreibweise|veraltete Schreibweise)\b"
    r"|\b(des|der) (Substantivs|Verbs|Adjektivs|Pronomens|Artikels|Numerales|Wortes)\b", re.I)
DE_FORM_POS = re.compile(r"(dekliniert|konjugiert|flektiert|Form|Partizip|Komparativ|Superlativ)", re.I)


# управление в EN-Wiktionary: «to wait (for) [with auf (+ accusative)]»
GOV_RE = re.compile(r"\[with ([^\]]{1,80})\]")
_CASES = {"accusative": "Akk.", "dative": "Dat.", "genitive": "Gen.", "nominative": "Nom."}


def short_case(s):
    s = re.sub(r"\(\+ (accusative|dative|genitive|nominative)\)", lambda m: "+ " + _CASES[m.group(1)], s)
    return re.sub(r"\b(accusative|dative|genitive|nominative)\b", lambda m: _CASES[m.group(1)], s)


def separable_form(lemma, form):
    """Форма раздельного глагола «räume auf» для леммы aufräumen."""
    parts = form.split()
    if len(parts) != 2 or " " in lemma:
        return False
    return lemma.lower().startswith(parts[1].lower()) and len(parts[1]) < len(lemma)


UA = "SimsDict/1.0 (German learning overlay)"


def download(url, dest, progress=None, retries=6):
    """Скачивание с докачкой (Range) и повторами. progress(done_bytes, total_bytes)."""
    if os.path.exists(dest):
        return dest
    part = dest + ".part"
    last_err = None
    for attempt in range(retries):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                clen = int(r.headers.get("Content-Length") or 0)
                if r.status == 206:
                    mode, total = "ab", have + clen
                else:
                    mode, total, have = "wb", clen, 0
                with open(part, mode) as f:
                    done = have
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
                if total and done < total:      # обрыв соединения: http.client иногда молча отдаёт хвост пустым
                    raise OSError(f"получено {done} из {total} байт")
            break
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:        # файл уже докачан
                break
            last_err = e
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as e:
            last_err = e
        time.sleep(min(2 ** attempt, 20))
    else:
        raise RuntimeError(f"Не удалось скачать {url}: {last_err}")
    os.replace(part, dest)
    return dest


def init_db(path):
    if os.path.exists(path):
        os.remove(path)
    db = sqlite3.connect(path)
    db.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-262144;")
    db.executescript("""
    CREATE TABLE entries(id INTEGER PRIMARY KEY, word TEXT, pos TEXT, gender TEXT, head TEXT,
                         plural TEXT, genitive TEXT, en TEXT, de TEXT, freq INTEGER DEFAULT 0,
                         ipa TEXT DEFAULT '', audio TEXT DEFAULT '[]');
    CREATE TABLE forms(lower TEXT, surface TEXT, entry_id INTEGER, tags TEXT);
    CREATE TABLE formof(lower TEXT, surface TEXT, lemma TEXT, pos TEXT, tags TEXT);
    """)
    return db


def iter_jsonl(path, progress, stage):
    size = os.path.getsize(path) or 1
    pos = 0
    with open(path, "rb") as f:
        for i, line in enumerate(f):
            pos += len(line)
            if i % 20000 == 0:
                progress(stage, pos / size)
            if line.strip():
                yield _loads(line)
    progress(stage, 1.0)


def parse_gender(e):
    exp = ((e.get("head_templates") or [{}])[0].get("expansion") or "")
    if e.get("pos") not in ("noun", "name"):
        return "", exp                               # у прилагательных «das stolze» — не род слова
    m = GENDER_RE.match(exp)
    if m:
        return m.group(1), exp
    g = ""
    for f in e.get("forms", []):
        t = set(f.get("tags", []))
        if {"definite", "nominative", "singular"} <= t:
            g = {"masculine": "m", "feminine": "f", "neuter": "n"}.get(
                next((x for x in t if x in ("masculine", "feminine", "neuter")), ""), g)
    return g, exp


def simplify_senses(e, max_senses=6):
    out = []
    for s in e.get("senses", []):
        if s.get("form_of") or s.get("alt_of"):
            continue
        gl = s.get("glosses") or []
        if not gl:
            continue
        ex = None
        for x in s.get("examples", []):
            if x.get("text"):
                ex = {"text": x["text"], "english": x.get("english") or x.get("translation") or ""}
                break
        gloss = gl[-1]
        gov = GOV_RE.search(" ".join(s.get("raw_glosses") or []))
        if gov and gov.group(0) not in gloss:
            gloss += f"  [+ {short_case(gov.group(1))}]"
        out.append({"gloss": gloss, "tags": [t for t in s.get("tags", []) if t != "no-gloss"][:4],
                    "example": ex if len(out) < 3 else None})
        if len(out) >= max_senses:
            break
    return out


AUDIO_MAX = 4


DE_GENDER = {"masculine": "m", "feminine": "f", "neuter": "n"}
GERMAN_ONLY_POS = {"noun", "verb", "adj", "adv", "phrase", "prep_phrase", "intj"}   # no names: surnames crowd out words


def german_only_entry(e, pos):
    """A word only the German Wiktionary has (often a compound: Abschlussball, Maustaste): gender, number /
    case forms, German definitions, English translations per sense, pronunciation. -> (row, forms) or None."""
    de = []
    for sns in e.get("senses", []):
        if sns.get("form_of") or sns.get("alt_of") or "form-of" in (sns.get("tags") or []):
            continue
        g = (sns.get("glosses") or [""])[-1].strip()
        if g and not DE_FORM_GLOSS.search(g) and g not in de:
            de.append(g)
    if not de:
        return None
    by_sense = {}
    for t in e.get("translations", []):
        if t.get("lang_code") == "en" and t.get("word"):
            words = by_sense.setdefault(t.get("sense_index") or "", [])
            if t["word"] not in words and len(words) < 4:
                words.append(t["word"])
    en = [{"gloss": ", ".join(ws), "tags": []} for _k, ws in sorted(by_sense.items())][:6]
    tags = set(e.get("tags") or [])
    gender = next((DE_GENDER[t] for t in ("masculine", "feminine", "neuter") if t in tags), "")
    plural = genitive = ""
    forms = []
    for fm in e.get("forms", []):
        f, ft = fm.get("form", ""), set(fm.get("tags", []))
        if not f or f in ("-", "—", "…") or ft & SKIP_FORM_TAGS:
            continue
        if pos == "noun" and not plural and {"nominative", "plural"} <= ft:
            plural = f
        if pos == "noun" and not genitive and {"genitive", "singular"} <= ft:
            genitive = f
        forms.append((f, ", ".join(sorted(ft))))
    ipa, audio = parse_sounds(e)
    if "…" in ipa:
        ipa = ""
    return (e["word"], pos, gender, "", plural, genitive, json.dumps(en, ensure_ascii=False),
            json.dumps(de[:5], ensure_ascii=False), ipa, json.dumps(audio, ensure_ascii=False)), forms


def parse_sounds(e, ipa="", audio=None):
    """IPA and native-speaker recordings (Wikimedia Commons file names + region) of a Wiktionary entry.
    Only the file name is stored; the URL is derived from it (gui/audio.py)."""
    audio = list(audio or [])
    names = {a["f"] for a in audio}
    for snd in e.get("sounds", []):
        if not ipa and snd.get("ipa"):
            ipa = snd["ipa"]
        name = snd.get("audio")
        if name and name not in names and len(audio) < AUDIO_MAX and name.lower().endswith((".ogg", ".wav", ".mp3", ".flac", ".opus")):
            tags = [t for t in snd.get("tags", []) if t[:1].isupper()]      # Germany, Austria, Berlin …
            audio.append({"f": name, "r": ", ".join(tags[:2])})
            names.add(name)
    return ipa, audio


def build_en(db, path, progress):
    cur = db.cursor()
    for e in iter_jsonl(path, progress, "Читаю английский Wiktionary"):
        if e.get("lang_code", "de") != "de":
            continue
        word, pos = e["word"], e.get("pos", "")
        fo = None
        for s in e.get("senses", []):
            if s.get("form_of"):
                fo = (s["form_of"][0].get("word"), ", ".join(s.get("tags", [])) or (s.get("glosses") or [""])[-1])
                break
        if fo and fo[0]:
            cur.execute("INSERT INTO formof VALUES(?,?,?,?,?)", (word.lower(), word, fo[0], pos, fo[1]))
            continue
        senses = simplify_senses(e)
        if not senses:
            continue
        gender, head = parse_gender(e)
        plural = genitive = ""
        for fm in e.get("forms", []):
            t = set(fm.get("tags", []))
            f = fm.get("form", "")
            if not f or f == "-" or "definite" in t or "indefinite" in t:
                continue
            if not plural and pos == "noun" and "plural" in t and t <= {"plural", "nominative"}:
                plural = f
            if not genitive and pos == "noun" and "genitive" in t and "singular" in t:
                genitive = f
        if pos == "noun" and not plural:
            m = PLURAL_RE.search(head)
            plural = m.group(1) if m else ""
        ipa, audio = parse_sounds(e)
        cur.execute("INSERT INTO entries(word,pos,gender,head,plural,genitive,en,de,ipa,audio) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (word, pos, gender, head, plural, genitive, json.dumps(senses, ensure_ascii=False), "[]", ipa,
                     json.dumps(audio, ensure_ascii=False)))
        eid = cur.lastrowid
        cur.execute("INSERT INTO forms VALUES(?,?,?,?)", (word.lower(), word, eid, ""))
        seen = {word.lower()}
        for fm in e.get("forms", []):
            form = fm.get("form", "")
            tags = set(fm.get("tags", []))
            if not form or form == "-" or tags & SKIP_FORM_TAGS or form.lower() in seen:
                continue
            if " " in form and not separable_form(word, form):   # «räume auf» — да, «habe aufgeräumt» — нет
                continue
            seen.add(form.lower())
            cur.execute("INSERT INTO forms VALUES(?,?,?,?)", (form.lower(), form, eid, ", ".join(sorted(tags))))


def resolve_formof(db):
    """Привязываем словоформы (Häuser -> Haus) к статьям лемм."""
    db.executescript("""
    CREATE INDEX ix_e_wp ON entries(word,pos);
    INSERT INTO forms SELECT f.lower, f.surface, e.id, f.tags FROM formof f
        JOIN entries e ON e.word=f.lemma AND e.pos=f.pos;
    INSERT INTO forms SELECT f.lower, f.surface, e.id, f.tags FROM formof f
        JOIN entries e ON e.word=f.lemma
        WHERE NOT EXISTS (SELECT 1 FROM entries x WHERE x.word=f.lemma AND x.pos=f.pos);
    DROP TABLE formof;
    """)


def build_de(db, path, progress):
    cur = db.cursor()
    idx = {}
    sounds = {}
    for i, w, p, ipa, audio in cur.execute("SELECT id, word, pos, ipa, audio FROM entries").fetchall():
        idx.setdefault((w, p), i)
        sounds[i] = (ipa or "", json.loads(audio or "[]"))
    acc = {}
    more_sound = {}
    added = {}
    for e in iter_jsonl(path, progress, "Читаю немецкий Wiktionary"):
        if e.get("lang_code", "de") != "de":
            continue
        raw_pos = e.get("pos") or ""
        if DE_FORM_POS.search(raw_pos) or e.get("form_of"):
            continue                                     # статья-словоформа, а не само слово
        pos = POS_DE.get(raw_pos.lower(), raw_pos)
        eid = idx.get((e["word"], pos))
        if not eid:                                      # only the German Wiktionary has this word: add it
            if pos in GERMAN_ONLY_POS and e.get("word") and (e["word"], pos) not in added:
                made = german_only_entry(e, pos)
                if made:
                    row, forms = made
                    cur.execute("INSERT INTO entries(word,pos,gender,head,plural,genitive,en,de,ipa,audio) "
                                "VALUES(?,?,?,?,?,?,?,?,?,?)", row)
                    new_id = cur.lastrowid
                    added[(e["word"], pos)] = new_id
                    seen = {e["word"].lower()}
                    cur.execute("INSERT INTO forms VALUES(?,?,?,?)", (e["word"].lower(), e["word"], new_id, ""))
                    for f, ft in forms:
                        if f.lower() in seen or (" " in f and not separable_form(e["word"], f)):
                            continue
                        seen.add(f.lower())
                        cur.execute("INSERT INTO forms VALUES(?,?,?,?)", (f.lower(), f, new_id, ft))
            continue
        if e.get("sounds") and eid:                              # the German edition often has more recordings
            ipa0, audio0 = more_sound.get(eid, sounds[eid])
            more_sound[eid] = parse_sounds(e, ipa0, audio0)
        gl = acc.setdefault(eid, [])
        for s in e.get("senses", []):
            if s.get("form_of") or s.get("alt_of") or "form-of" in (s.get("tags") or []):
                continue
            g = (s.get("glosses") or [""])[-1].strip()
            if not g or DE_FORM_GLOSS.search(g) or g in gl:
                continue
            if len(gl) < 5:
                gl.append(g)
    cur.executemany("UPDATE entries SET de=? WHERE id=?",
                    [(json.dumps(g, ensure_ascii=False), i) for i, g in acc.items() if g])
    cur.executemany("UPDATE entries SET ipa=?, audio=? WHERE id=?",
                    [(ipa, json.dumps(a, ensure_ascii=False), i) for i, (ipa, a) in more_sound.items()])
    if progress:
        progress(f"German-only words: {len(added)}", None)


def build_database(out, en_path, de_path=None, progress=None):
    progress = progress or (lambda stage, frac: None)
    db = init_db(out)
    build_en(db, en_path, progress)
    progress("Связываю словоформы", None)
    resolve_formof(db)
    if de_path:
        build_de(db, de_path, progress)
    progress("Строю индексы", None)
    db.executescript("CREATE INDEX ix_forms ON forms(lower);")
    db.commit()
    db.execute("VACUUM")
    db.close()


def main():
    ap = argparse.ArgumentParser(description="Ручная сборка dict.sqlite (приложение делает это само)")
    ap.add_argument("--en"), ap.add_argument("--de")
    ap.add_argument("--out", default="dict.sqlite")
    ap.add_argument("--no-de", action="store_true")
    a = ap.parse_args()
    show = lambda s, f: print(f"\r{s}: {'' if f is None else f'{f:.0%}'}      ", end="", flush=True)
    en = a.en or download(EN_URL, "kaikki-en-German.jsonl", lambda d, t: show("Скачиваю EN", d / t if t else None))
    de = None if a.no_de else (a.de or download(DE_URL, "kaikki-de-Deutsch.jsonl", lambda d, t: show("Скачиваю DE", d / t if t else None)))
    build_database(a.out, en, de, show)
    print("\nГотово:", a.out, f"{os.path.getsize(a.out) >> 20} МБ")


if __name__ == "__main__":
    main()
