"""Словарное ядро: поиск немецкого слова (в т.ч. словоформы и составные слова) в SQLite."""
import json
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

ARTICLE = {"m": "der", "f": "die", "n": "das"}
POS_NAMES = {
    "noun": "сущ.", "verb": "глагол", "adj": "прил.", "adv": "нареч.", "prep": "предлог",
    "conj": "союз", "pron": "местоим.", "num": "числ.", "intj": "межд.", "particle": "частица",
    "det": "артикль/детерм.", "name": "имя", "phrase": "фраза", "prefix": "приставка", "suffix": "суффикс",
}
_STRIP = " \t\r\n.,;:!?\"'«»„“”‘’()[]{}<>…*/\\|0123456789•·™®©°^~_=+¬"


@dataclass
class Entry:
    word: str
    pos: str
    gender: str = ""          # m / f / n / "" (может быть "m or f")
    head: str = ""            # напр. "Haus n (strong, genitive Hauses, plural Häuser)"
    plural: str = ""
    genitive: str = ""
    en: list = field(default_factory=list)   # [{"gloss":..., "tags":[...], "example":{"text","english"}|None}]
    de: list = field(default_factory=list)   # ["Gebäude, ...", ...]
    via: str = ""             # если найдено как словоформа: "plural, nominative"
    parts: list = field(default_factory=list)  # для составных слов: ["Küchen", "tisch"]
    match: str = ""           # что найдено в тексте, если это не одно слово: "räumt … auf", "auf jeden Fall"
    hint: str = ""            # подсказка по управлению: "warten auf …"
    corrected: str = ""       # what OCR actually read when the word had to be corrected ("raume" -> räume)

    @property
    def article(self):
        g = self.gender.split()[0] if self.gender else ""
        return ARTICLE.get(g, "")


def clean_token(tok: str) -> str:
    tok = tok.strip(_STRIP)
    return tok


# отделяемые приставки: «räumt … auf» -> aufräumen
PARTICLES = frozenset("""ab an auf aus bei dabei dar durch ein empor entgegen entlang fehl fern fest fort frei her
herab heran herauf heraus herbei herein herum herunter hervor hin hinab hinauf hinaus hinein hinterher hinüber
hinunter hoch kennen los mit nach nieder rauf raus rein rüber runter statt teil um umher vor voran voraus vorbei
vorüber weg weiter wieder zu zurecht zurück zusammen""".split())
PREPOSITIONS = frozenset("""an auf aus bei durch für gegen hinter in mit nach neben ohne seit über um unter von vor
zu zwischen""".split())
# после этих слов отделяемая приставка уже не может стоять (новое придаточное/предложение)
CLAUSE_WORDS = frozenset("und oder aber denn sondern weil dass ob wenn als während bevor nachdem damit obwohl".split())
# a new clause starts here (subordinating); «und/oder/aber» may just join objects («das Zimmer und den Flur»)
CLAUSE_START = frozenset("weil dass ob wenn als während bevor nachdem damit obwohl denn sondern".split())
_CLAUSE_END = re.compile(r"[.!?;:,)\]»“”\"]$")
_PHRASE_MAX = 5
REFLEXIVE = frozenset("mich dich sich uns euch".split())
SENTENCE_STARTERS = frozenset("""der die das den dem ein eine ich du er sie es wir ihr man heute morgen gestern dann
danach jetzt bitte aber und hier dort""".split())
# short words OCR tends to lose that a phrase may be missing in tolerant matching
FUNCTION_WORDS = frozenset("auf an in im am zu zum zur um aus bei mit von vom der die das den dem des ein".split())
# «ich freue mich» is reflexive, «das freut mich» is not: mich/dich/uns/euch count only with their subject
_REFL_SUBJECT = {"mich": "ich", "dich": "du", "uns": "wir", "euch": "ihr"}


def _is_reflexive(clause_words):
    ws = set(clause_words)
    return "sich" in ws or any(p in ws and s in ws for p, s in _REFL_SUBJECT.items())


def _one_edit(a, b):
    """a and b differ by exactly one substitution, insertion or deletion."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, t = (a, b) if len(a) < len(b) else (b, a)
    return any(t[:i] + t[i + 1:] == s for i in range(len(t)))


_MARKS = re.compile(r"[•·|]+")
_COMMON_LOWER = frozenset("""ein eine einen einem einer und oder aber dass die der das den dem in im an am auf aus
mit von vom zu zum zur bei nach vor für über unter um wenn weil ob als wie was wer ist sind war hat habe haben
wird werden kann können sehr nicht noch schon auch nur mehr""".split())


def _LOWER_WORD(t):
    """A common lowercase word (cheap check without the database)."""
    return t.lower() in _COMMON_LOWER and t[:1].islower()


def _split_marks(raw, tight, idx, frac):
    """OCR sometimes reads a space as a bullet or bar and glues words: split those tokens apart."""
    if not any(_MARKS.search(t.strip("•·|")) for t in raw):
        return raw, tight, idx
    out, out_tight, new_idx = [], [], idx
    for k, t in enumerate(raw):
        parts = [p for p in _MARKS.split(t) if p] or [t]
        if k == idx and len(parts) > 1:
            pos = (frac if frac is not None else 0.5) * len(t)
            acc, pick = 0, len(parts) - 1
            for j, p in enumerate(parts):
                acc += len(p) + 1
                if pos <= acc:
                    pick = j
                    break
            new_idx = len(out) + pick
        elif k == idx:
            new_idx = len(out)
        out += parts
        out_tight += [False] * (len(parts) - 1)
        if k < len(tight):
            out_tight.append(tight[k])
    return out, out_tight[:max(0, len(out) - 1)], new_idx


def _join_spans(toks, ks):
    """'geht auf die Nerven' with gaps marked: adjacent tokens joined by spaces, gaps by ' … '."""
    out, prev = [], None
    for k in ks:
        out.append((" " if prev is not None and k == prev + 1 else " … " if prev is not None else "") + toks[k])
        prev = k
    return "".join(out)
# slot words in dictionary phrases («jemandem Bescheid sagen») that never appear literally in text
PLACEHOLDERS = frozenset("jemandem jemanden jemandes jemand etwas etw. jmdm. jmdn. jmds. sich einem einen einer".split())
_GOV = re.compile(r"\[\+ ([^\]]*)\]")


class Dictionary:
    def __init__(self, path: str):
        self.db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA mmap_size=1073741824")   # чтение через mmap — быстрее
        self.db.execute("PRAGMA cache_size=-65536")

    # --- низкоуровневый поиск ---
    def _by_form(self, form: str):
        rows = self.db.execute(
            "SELECT e.*, f.tags AS via, f.surface AS surface FROM forms f JOIN entries e ON e.id=f.entry_id "
            "WHERE f.lower=? ORDER BY e.freq DESC", (form.lower(),)).fetchall()
        return rows

    def _row_to_entry(self, r, via_override=None) -> Entry:
        e = Entry(word=r["word"], pos=r["pos"], gender=r["gender"] or "", head=r["head"] or "",
                  plural=r["plural"] or "", genitive=r["genitive"] or "",
                  en=json.loads(r["en"] or "[]"), de=json.loads(r["de"] or "[]"))
        e.via = via_override if via_override is not None else (r["via"] or "")
        return e

    def lookup(self, token: str, max_entries: int = 6):
        """Возвращает список Entry. Сначала точное совпадение формы, потом разбор составного слова."""
        tok = clean_token(token)
        if not tok:
            return []
        if " " in tok.strip():                           # ручной ввод фразы: «auf jeden Fall», «räumt auf»
            rows = self._by_form(" ".join(tok.split()))
            if rows:
                return self._rank(rows, tok)[:max_entries]
            words = tok.split()
            return self.lookup_context(words, 0)[0] or self.lookup(words[0], max_entries)
        rows = self._by_form(tok)
        if not rows and "-" in tok:
            rows = self._by_form(tok.replace("-", ""))
        if rows:
            return self._rank(rows, tok)[:max_entries]
        return self._compound(tok)

    def _rank(self, rows, tok):
        def key(r):
            is_lemma = 0 if (r["via"] == "") else 1          # сама лемма выше, чем словоформа
            case_match = 0 if r["surface"] == tok else 1       # Haus vs haus
            if tok[:1].islower():                              # «warte» — глагол warten важнее, чем die Warte
                return (case_match, is_lemma)
            return (is_lemma, case_match)
        rows = sorted(rows, key=key)
        seen, out = set(), []
        for r in rows:
            k = (r["word"], r["pos"], r["gender"], (r["en"] or "")[:80])   # дубли одной статьи
            if r["id"] in seen or k in seen:
                continue
            seen.update((r["id"], k))
            out.append(self._row_to_entry(r))
        return out

    # --- поиск с контекстом строки: обрывки слов, фразы, раздельные глаголы, глагол + предлог ---
    def known(self, tok: str) -> bool:
        tok = clean_token(tok)
        return bool(tok) and self.db.execute("SELECT 1 FROM forms WHERE lower=? LIMIT 1", (tok.lower(),)).fetchone() is not None

    def _lemmas(self, tok, pos=None, limit=3):
        out = []
        for r in self._by_form(tok):
            if (pos is None or r["pos"] == pos) and r["word"] not in out:
                out.append(r["word"])
        return out[:limit]

    def _entry_exact(self, word, pos=None):
        rows = [r for r in self._by_form(word) if r["via"] == "" and r["word"].lower() == word.lower()
                and (pos is None or r["pos"] == pos)]
        return self._rank(rows, word) if rows else []

    def repair(self, toks, idx, tight=None):
        """OCR иногда режет слово на куски («Küch» «entisch»). Склеиваем соседей, если так получается
        слово из словаря. Соседи через обычный пробел склеиваются, только если сам кусок не найден.
        -> (слово, первый индекс, последний индекс)."""
        tight = tight or [False] * len(toks)
        w = toks[idx]
        found = self.known(w)
        best = None
        for a in range(idx, max(-1, idx - 3), -1):
            for b in range(idx, min(len(toks), idx + 3)):
                if (a, b) == (idx, idx):
                    continue
                if any(not tight[k] and found for k in range(a, b)):
                    continue
                if any(_CLAUSE_END.search(toks[k]) for k in range(a, b)) or not all(toks[a:b + 1]):
                    continue
                joined = "".join(toks[a:b + 1])
                # a compound may be glued from fragments, but not from a piece that is a word on its own
                # («Essen» + «schmeckt» must stay two words)
                ok = self.known(joined) or (not found and all(tight[k] for k in range(a, b))
                                            and bool(self._compound(joined)))
                if len(joined) >= 3 and ok and (best is None or b - a > best[2] - best[1]):
                    best = (joined, a, b)
        return best or (w, idx, idx)

    def _is_end(self, raw, k):
        """raw[k] closes a clause. A full stop followed by a lowercase word is OCR noise («ir. eine»): after a
        real sentence end German continues with a capital letter. Punctuation stuck to an unreadable token
        («græößeneywohnung,») is unreliable and ignored."""
        t = raw[k].strip()
        if not _CLAUSE_END.search(t):
            return False
        core = clean_token(t)
        if len(core) > 4 and not self.known(core):
            return False
        if t.endswith((",", ";", ":")):
            return True
        nxt = raw[k + 1].strip() if k + 1 < len(raw) else ""
        if not nxt or not nxt[:1].islower():
            return True
        # «ir. eine» — a real lowercase word follows, so the stop is noise; «um. ber» (garbled «Der») — keep it
        return not _LOWER_WORD(clean_token(nxt))

    def _clause(self, raw, a, b):
        """Границы предложения/придаточного вокруг токенов a..b (по знакам препинания и союзам)."""
        lo = a
        while lo > 0 and not self._is_end(raw, lo - 1):
            lo -= 1
        hi = b
        while hi < len(raw) - 1 and not self._is_end(raw, hi):
            if clean_token(raw[hi + 1]).lower() in CLAUSE_START:
                break
            hi += 1
        return lo, hi

    def _phrases(self, toks, a, b):
        """Самая длинная фраза из словаря, которая покрывает слово под курсором: «auf jeden Fall», «zu Hause»."""
        n = len(toks)
        lem = {}
        for size in range(_PHRASE_MAX, 1, -1):
            for s in range(max(0, b - size + 1), min(a, n - size) + 1):
                win = toks[s:s + size]
                if not all(win) or s > a or s + size - 1 < b:
                    continue
                variants = [" ".join(win)]
                for i, t in enumerate(win):                # одно слово — в начальной форме: «ging nach Hause» -> «gehen …»
                    if t not in lem:
                        lem[t] = [x for x in self._lemmas(t) if x.lower() != t.lower() and " " not in x]
                    for x in lem[t][:2]:
                        variants.append(" ".join(win[:i] + [x] + win[i + 1:]))
                for v in variants:
                    rows = [r for r in self._by_form(v) if " " in r["word"]]
                    if rows:
                        ents = self._rank(rows, v)[:3]
                        for e in ents:
                            e.match = " ".join(win)
                        return ents, (s, s + size - 1)
        return [], None

    def _separable(self, toks, raw, a, b):
        """Раздельный глагол: «Ich räume das Zimmer auf» — курсор на räume или на auf."""
        lo, hi = self._clause(raw, a, b)
        hovered = toks[a].lower() if a == b else ""

        def final(k):          # the particle closes its clause: punctuation, end of text, or a conjunction next
            if k > hi:
                return False
            if self._is_end(raw, k) or k == len(raw) - 1 or clean_token(raw[k + 1]).lower() in CLAUSE_WORDS:
                return True
            # weak signal, used only when nothing else matched: OCR lost the full stop and the next sentence
            # starts with a capitalised function word («… Abend an. Morgen beginnt …», «… auf Der Hund …»).
            # A capitalised noun is not enough: «nach Hause» is a preposition with its noun.
            nxt = raw[k + 1].strip()
            return weak[0] and nxt[:1].isupper() and clean_token(nxt).lower() in SENTENCE_STARTERS \
                and not _CLAUSE_END.search(raw[k].strip())
        weak = [False]

        def join_one(verb_tok, p):
            rows = [r for r in self._by_form(f"{verb_tok} {p}") if r["pos"] == "verb"]   # «räume auf» в таблицах форм
            if rows:
                return self._rank(rows, verb_tok)[:2]
            for lemma in self._lemmas(verb_tok, "verb"):
                ents = self._entry_exact(p + lemma, "verb")
                if ents:
                    for e in ents:
                        e.via = e.via or f"{verb_tok} … {p}"
                    return ents[:2]
            return []

        def join(verb_tok, p):
            ents = join_one(verb_tok, p)
            if ents or len(verb_tok) < 3:
                return ents
            # the verb may be misread and still look like a word («raume» is a rare adjective form)
            for v in self._variants(verb_tok):
                if any(r["pos"] == "verb" for r in self._by_form(v)):
                    ents = join_one(v, p)
                    if ents:
                        return ents
            return []

        def attempt():
            if hovered in PARTICLES and final(a):       # курсор на приставке -> ищем глагол левее
                for k in range(lo, a):                  # глагол обычно второй: «Ich räume … auf», «Räum … auf!»
                    if not toks[k] or (toks[k][0].isupper() and k != lo):
                        continue
                    ents = join(toks[k], hovered)
                    if ents:
                        for e in ents:
                            e.match = f"{toks[k]} … {toks[a]}"
                        return ents
                return []
            for k in range(hi, b, -1):                  # курсор на глаголе -> приставка в конце предложения
                p = toks[k].lower()
                if p in PARTICLES and final(k):
                    ents = join(toks[a], p) if a == b else []
                    if ents:
                        for e in ents:
                            e.match = f"{toks[a]} … {toks[k]}"
                        return ents
            return []
        found = attempt()
        if not found:
            weak[0] = True
            found = attempt()
        if not found and a == b and hovered not in PARTICLES:
            # the clause's last word is a particle misread as a near-identical word («an.» -> «am», «zu.» -> «zw»)
            k = hi
            last = toks[k].lower() if 0 <= k < len(toks) else ""
            if k > b and 1 <= len(last) <= 4 and (self._is_end(raw, k) or k == len(raw) - 1):
                for p in sorted(PARTICLES, key=len):
                    if p != last and _one_edit(p, last):
                        ents = join(toks[a], p)
                        if ents:
                            for e in ents:
                                e.match = f"{toks[a]} … {p}"
                            return ents
        return found

    def _senses_in_context(self, entries, toks, raw, a, b):
        """Picks the meaning that fits the sentence: a reflexive pronoun (mich/dich/sich/uns/euch) favours
        reflexive senses, a preposition favours senses governed by it («freue mich auf» -> to look forward to)."""
        lo, hi = self._clause(raw, a, b)
        clause = [toks[k].lower() for k in range(lo, hi + 1) if not (a <= k <= b)]
        reflexive = _is_reflexive(clause)
        preps = [t for t in clause if t in PREPOSITIONS]
        for e in entries:
            if e.pos not in ("verb", "adj", "noun") or not e.en:
                continue

            def gov_has(s, p):
                pat = re.compile(rf"(?<![\w-]){re.escape(p)}(?![\w-])", re.I)
                return any(pat.search(g) for g in _GOV.findall(s.get("gloss", "")))

            def score(s):
                tags = s.get("tags", [])
                sc = 0
                if e.pos == "verb" and "reflexive" in tags:
                    sc += 1 if reflexive else -1
                if any(gov_has(s, p) for p in preps):
                    sc += 2
                return sc
            scored = sorted(e.en, key=score, reverse=True)
            best = scored[0]
            if score(best) <= 0:
                continue
            e.en = scored
            p = next((p for p in preps if gov_has(best, p)), None)
            refl = e.pos == "verb" and reflexive and "reflexive" in best.get("tags", [])
            e.hint = ("sich " if refl else "") + e.word + (f" {p} …" if p else "")

    _government = _senses_in_context                       # old name kept for callers/tests

    def _phrase_index(self):
        """Multi-word entries indexed by their content words (built lazily, ~4k phrases)."""
        if getattr(self, "_pidx", None) is None:
            idx = {}
            for (word,) in self.db.execute("SELECT DISTINCT word FROM entries WHERE word LIKE '% %' AND length(word) <= 40"):
                parts = [w.lower().strip(",.!?") for w in word.split()]
                content = [w for w in parts if w not in PLACEHOLDERS]
                if len(content) < 2 or len(parts) > _PHRASE_MAX:
                    continue
                for w in set(content):
                    idx.setdefault(w, []).append((word, content, "sich" in parts))
            self._pidx = idx
        return self._pidx

    def _free_phrases(self, toks, raw, a, b):
        """Phrase whose words all occur in the clause, in any order and inflected:
        «Ich weiß davon Bescheid» -> Bescheid wissen, «Das geht mir auf die Nerven» -> auf die Nerven gehen."""
        lo, hi = self._clause(raw, a, b)
        best = self._find_free(toks, a, b, lo, hi, tolerant=False)
        hovered_word = toks[a].lower() if a == b else ""
        if not best and hovered_word not in FUNCTION_WORDS and hovered_word not in PARTICLES and len(hovered_word) >= 4:
            # OCR noise: a stray full stop split the clause («auf die. Nerven») or a short word was lost
            # («… jeden Fall» without «auf»). Look once more across one boundary, tolerating one missing
            # function word — only when the cursor is on a content word, never on «auf»/«an» themselves.
            lo2 = self._clause(raw, lo - 1, lo - 1)[0] if lo > 0 else lo
            hi2 = self._clause(raw, hi + 1, hi + 1)[1] if hi + 1 < len(raw) else hi
            best = self._find_free(toks, a, b, lo2, hi2, tolerant=True, strict=(lo, hi))
        if not best:
            return []
        ents = self._entry_exact(best[0])
        shown = _join_spans(toks, best[2])
        for e in ents[:2]:
            e.match = shown
        return ents[:2]

    def _find_free(self, toks, a, b, lo, hi, tolerant, strict=None):
        lo_strict, hi_strict = strict or (lo, hi)
        forms = {}
        for k in range(lo, hi + 1):
            t = toks[k]
            if t:
                forms[k] = {t.lower()} | {x.lower() for x in self._lemmas(t) if " " not in x}
        hovered = set().union(*(forms.get(k, set()) for k in range(a, b + 1)))
        reflexive = _is_reflexive([toks[k].lower() for k in range(lo, hi + 1)])
        idx = self._phrase_index()
        best = None
        for h in hovered:
            for word, content, needs_sich in idx.get(h, ()):
                if needs_sich and not reflexive:
                    continue
                if tolerant and len(content) < 3:
                    continue
                used, missing = [], []
                for w in content:
                    k = next((k for k, f in forms.items() if w in f and k not in used), None)
                    if k is None:
                        missing.append(w)
                    else:
                        used.append(k)
                if missing and not (tolerant and len(missing) == 1 and missing[0] in FUNCTION_WORDS):
                    continue
                if tolerant and sum(1 for k in used if k < lo_strict or k > hi_strict) > 1:
                    continue                             # at most one word from beyond a doubtful boundary
                if not any(a <= k <= b for k in used):
                    continue
                if best is None or len(used) > len(best[2]):
                    best = (word, content, sorted(used))
        return best

    def lookup_context(self, tokens, idx, tight=None, max_entries=6, frac=None):
        """Поиск слова под курсором с учётом строки. tokens — слова строки (как их выдал OCR), idx — под курсором,
        tight[i] — между словом i и i+1 почти нет зазора (OCR, скорее всего, разрезал одно слово)."""
        raw = list(tokens)
        tight = list(tight) if tight else [False] * max(0, len(raw) - 1)
        raw, tight, idx = _split_marks(raw, tight, idx, frac)   # «Licht•aus.» -> «Licht», «aus.»
        if 0 <= idx < len(raw):
            raw, tight = self._split_glued_particles(raw, tight, idx)
        toks = [clean_token(t) for t in raw]
        if not 0 <= idx < len(toks) or not toks[idx]:
            return [], ""
        corrected = ""
        self._fix_particles(toks, raw)
        self._fix_neighbours(toks, raw, idx)
        t = toks[idx]
        glued = any(t[i].islower() and t[i + 1].isupper() for i in range(len(t) - 1))
        if self.known(t) and (self._names_only(t) or not self.case_known(t)):
            # «Hauser» (a surname) is usually «Häuser»; lowercase «raume» exists only as the noun «Raume»
            fixed = self.fix_ocr(t, accept=lambda v: not self._names_only(v) and self.case_known(v))
            if fixed:
                corrected, toks[idx] = t, fixed
                raw[idx] = raw[idx].replace(t, fixed) if t in raw[idx] else fixed
        elif not self.known(t) and not self._known_join(toks, idx, tight) and (glued or not self._compound(t)):
            seg = self.segment(t)
            if seg:                                      # OCR glued words: «aufjedenFall» -> auf jeden Fall
                tail = raw[idx][raw[idx].find(t) + len(t):] if t in raw[idx] else ""
                raw[idx:idx + 1] = seg[:-1] + [seg[-1] + tail]
                toks[idx:idx + 1] = seg
                tight[idx:idx] = [False] * (len(seg) - 1)
                if frac is not None:                     # the part under the cursor, by character position
                    pos, acc = frac * len(t), 0
                    for k, p in enumerate(seg):
                        acc += len(p)
                        if pos <= acc:
                            idx += k
                            break
                    else:
                        idx += len(seg) - 1
            else:
                fixed = self.fix_ocr(t)                  # «raume» -> räume, «Sctüssel» -> Schlüssel
                if fixed:
                    corrected = t
                    raw[idx] = raw[idx].replace(t, fixed) if t in raw[idx] else fixed
                    toks[idx] = fixed
        word, a, b = self.repair(toks, idx, tight)
        out = []
        phrase, span = self._phrases(toks, a, b)
        out += phrase
        sep = self._separable(toks, raw, a, b)
        if not phrase and not sep:                       # a separable verb beats a loosely matched phrase
            out += self._free_phrases(toks, raw, a, b)   # «Ich weiß davon Bescheid» -> Bescheid wissen
        out += sep
        single = self.lookup(word, max_entries)
        self._senses_in_context(single, toks, raw, a, b)
        single.sort(key=lambda e: not e.hint)            # совпало управление / возвратность — вперёд
        seen = {(e.word, e.pos) for e in out}
        out += [e for e in single if (e.word, e.pos) not in seen]
        if corrected:
            for e in out:
                e.corrected = corrected
        return out[:max_entries], word

    # --- OCR misreadings ---
    _SWAPS = (("a", "ä"), ("o", "ö"), ("u", "ü"), ("A", "Ä"), ("O", "Ö"), ("U", "Ü"), ("ss", "ß"), ("B", "ß"), ("b", "ß"),
              ("ß", "ss"), ("rn", "m"), ("m", "rn"), ("cl", "d"), ("l", "I"), ("I", "l"), ("1", "l"), ("0", "o"),
              ("vv", "w"), ("ii", "ü"), ("li", "h"), ("c", "e"), ("e", "c"), ("t", "l"), ("l", "t"), ("i", "l"),
              ("l", "i"), ("n", "h"), ("h", "n"), ("ct", "chl"), ("c", "ch"), ("i", "ei"), ("e", "ei"), ("ai", "ei"),
              ("il", "ll"), ("Fail", "Fall"), ("u", "n"), ("n", "u"), ("y", "v"), ("v", "y"), ("t", "i"),
              ("r", "n"), ("n", "r"), ("rr", "m"), ("tl", "ll"), ("u", "ll"), ("j", "i"), ("f", "t"), ("t", "f"))

    def _variants(self, tok):
        """One-substitution OCR variants of a token (no dictionary check)."""
        out = []
        for a, b in self._SWAPS:
            i = tok.find(a)
            while i != -1:
                v = tok[:i] + b + tok[i + len(a):]
                if v not in out and v != tok:
                    out.append(v)
                i = tok.find(a, i + 1)
        return out

    def case_known(self, tok):
        """Known with this capitalisation: «raume» isn't (only the noun form «Raume» exists), «räume» is.
        A capital first letter is always allowed (sentence start)."""
        tok = clean_token(tok)
        if not tok:
            return False
        rows = self.db.execute("SELECT surface FROM forms WHERE lower=? LIMIT 40", (tok.lower(),)).fetchall()
        if not rows:
            return False
        if tok[:1].isupper():
            return True
        return any(r[0] == tok or r[0][:1].islower() for r in rows)

    def _fix_neighbours(self, toks, raw, idx, span=8):
        """Light OCR correction (one substitution) for unknown words around the cursor, so the parser sees
        «räume … auf», «keine Ahnung», «um» instead of «raume», «kene», «urn»."""
        for k in range(max(0, idx - span), min(len(toks), idx + span + 1)):
            t = toks[k]
            if k == idx or len(t) < 2 or not t.isalpha() or self.case_known(t):
                continue
            fixed = self.fix_ocr(t, depth=1, limit=120, accept=self.case_known) if len(t) >= 3 else \
                next((v for a, b in self._SWAPS if a in t for v in [t.replace(a, b, 1)] if self.case_known(v)), None)
            if fixed:
                raw[k] = raw[k].replace(t, fixed) if t in raw[k] else fixed
                toks[k] = fixed

    _JUNK_TAIL = set("lkwiIj1!|-:;·•'´`")

    def _fix_particles(self, toks, raw):
        """A sentence-final particle whose full stop OCR misread as a letter or mark — «aus-», «aufl», «ank»,
        «umw» — becomes the particle again, closing the clause (only when the token isn't a real word)."""
        for k, t in enumerate(toks):
            low = t.lower()
            if len(low) < 3 or low[:-1] not in PARTICLES:
                continue
            nxt = raw[k + 1] if k + 1 < len(raw) else ""
            closes = not nxt or nxt[:1].isupper() or not nxt[:1].isalpha()
            # «aus-» is also a dictionary prefix entry, so a trailing hyphen doesn't need the unknown-word check;
            # at the very end of the text any one stray character after a particle is the misread stop («ausa»)
            junk = low[-1] in self._JUNK_TAIL or not nxt
            if closes and junk and (low[-1] == "-" or not self.known(low)):
                toks[k], raw[k] = low[:-1], low[:-1] + "."

    def _split_glued_particles(self, raw, tight, idx):
        """«wiederan.», «Rauchemauf» — a final particle glued to the word before it (after the cursor only)."""
        out_raw, out_tight = list(raw[:idx + 1]), list(tight[:idx])
        for k in range(idx + 1, len(raw)):
            t = raw[k]
            core = clean_token(t)
            low = core.lower()
            split = None
            if len(low) > 4 and core.isalpha() and not self.known(core):
                for p in sorted(PARTICLES, key=len, reverse=True):
                    head = core[:-len(p)]
                    if low.endswith(p) and len(head) >= 2 and self.known(head):
                        split = (head, p + t[t.find(core) + len(core):] if core in t else p)
                        break
            out_tight.append(tight[k - 1] if k - 1 < len(tight) else False)
            if split:
                out_raw += list(split)
                out_tight.append(False)
            else:
                out_raw.append(t)
        return out_raw, out_tight[:max(0, len(out_raw) - 1)]

    def reading_score(self, tokens, idx, tight=None, frac=None):
        """How believable an OCR reading is, 0..1: the hovered word is a real word read without correction
        (most weight), an entry was found at all, and how much of the line consists of real words."""
        near = tokens[max(0, idx - 6): idx + 7]                  # quality of the text around the cursor only
        words = [clean_token(t) for t in near]
        words = [w for w in words if len(w) >= 2 and w.isalpha()]
        line = sum(1 for w in words if self.known(w)) / max(1, len(words))
        hov = clean_token(tokens[idx]) if 0 <= idx < len(tokens) else ""
        exact = bool(hov) and self.known(hov) and not self._names_only(hov)
        ents = self.lookup_context(tokens, idx, tight, frac=frac)[0] if not exact else [True]
        corrected = bool(ents) and getattr(ents[0], "corrected", "")
        # a reading that shows where the sentence ends is more useful (separable particles live there)
        complete = 0.05 if any(t.rstrip("\"'»“”").endswith((".", "!", "?")) for t in tokens[idx:]) else 0.0
        return 0.55 * (1.0 if exact else 0.5 if ents and not corrected else 0.3 if ents else 0.0) + 0.45 * line + complete

    def _names_only(self, tok):
        rows = self._by_form(tok)
        return bool(rows) and all(r["pos"] == "name" for r in rows)

    def fix_ocr(self, tok, depth=2, limit=900, accept=None):
        """Closest dictionary word reachable by undoing typical OCR confusions (lost umlauts, ß/B/ss, rn/m, l/I…).
        Only accepts a candidate that exists in the dictionary (and passes accept, if given)."""
        tok = clean_token(tok)
        if len(tok) < 3 or not tok.isalpha():
            return None
        seen, frontier = {tok}, [tok]
        for _ in range(depth):
            nxt = []
            for w in frontier:
                for a, b in self._SWAPS:
                    i = w.find(a)
                    while i != -1:
                        v = w[:i] + b + w[i + len(a):]
                        if v not in seen:
                            seen.add(v)
                            if self.known(v) and (accept is None or accept(v)):
                                return v
                            nxt.append(v)
                            if len(seen) > limit:
                                return None
                        i = w.find(a, i + 1)
            frontier = nxt
        return None

    def segment(self, tok):
        """Splits words OCR glued together («aufjedenFall») into known words; None if it can't."""
        t = clean_token(tok)
        if len(t) < 6 or not t.isalpha():
            return None
        glued = any(t[i].islower() and t[i + 1].isupper() for i in range(len(t) - 1))
        best = {0: []}
        for i in range(len(t)):
            if i not in best:
                continue
            for j in range(i + 2, min(len(t), i + 18) + 1):
                part = t[i:j]
                if self.known(part) and (j not in best or len(best[i]) + 1 < len(best[j])):
                    best[j] = best[i] + [part]
        parts = best.get(len(t))
        if not parts or len(parts) < 2 or (not glued and any(len(p) < 3 for p in parts)):
            return None
        return parts

    def _known_join(self, toks, idx, tight):
        """The token is a fragment that joins with a tight neighbour into a known word (handled by repair)."""
        for a, b in ((idx - 1, idx), (idx, idx + 1)):
            if 0 <= a and b < len(toks) and tight[a] and toks[a] and toks[b] and self.known(toks[a] + toks[b]):
                return True
        return False

    # --- составные слова: Küchentisch -> Küche|n + Tisch ---
    LINKERS = ("", "s", "n", "en", "er", "e", "es", "ens")

    def _compound(self, tok: str):
        low = tok.lower()
        for i in range(len(low) - 3, 2, -1):             # хвост — самое длинное слово справа
            tail = low[i:]
            head = low[:i]
            tail_rows = self._by_form(tail)
            if not tail_rows:
                continue
            for link in self.LINKERS:
                if link and not head.endswith(link):
                    continue
                h = head[: len(head) - len(link)] if link else head
                if len(h) < 3:
                    continue
                head_rows = self._by_form(h)
                if head_rows:
                    ents = self._rank(tail_rows, tail)[:3]
                    hent = self._rank(head_rows, h)[:1]
                    for e in ents:
                        e.parts = [tok[:i], tok[i:]]
                    return hent_prefix(hent, tok[:i]) + ents
        return []


def hent_prefix(hents, text):
    for e in hents:
        e.parts = [text]
    return hents
