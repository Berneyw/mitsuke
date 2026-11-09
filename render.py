"""Word card model, independent of the UI toolkit: entries -> lines that the QML WordCard draws (in the main
window, the in-game card and the pinned card), plus the plain-text form for the clipboard."""
import re

GENDER = {"m": ("#1f5fb8", "der"), "f": ("#b8325a", "die"), "n": ("#1d7a43", "das")}

POS_NAMES = {
    "noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb", "prep": "preposition",
    "conj": "conjunction", "pron": "pronoun", "num": "numeral", "intj": "interjection", "particle": "particle",
    "det": "article", "name": "proper noun", "phrase": "phrase", "prep_phrase": "phrase", "prefix": "prefix",
    "suffix": "suffix", "abbrev": "abbreviation", "article": "article", "character": "letter",
}
KEEP_TAGS = {"transitive", "intransitive", "reflexive", "colloquial", "informal", "formal", "figuratively",
             "archaic", "dated", "regional", "slang", "vulgar", "rare", "impersonal", "plural-only", "uncountable"}
DEFAULTS = {"entries": 6, "senses": 5, "examples": True, "german": True}


def _via(text):
    text = (text or "").replace("first-person", "1st person").replace("second-person", "2nd person") \
        .replace("third-person", "3rd person")
    parts = [p.strip() for p in text.split(",") if p.strip() and p.strip() not in ("indicative",)]
    return " · ".join(parts)


def forms_line(e):
    """Short, useful inflection summary instead of the raw Wiktionary headline."""
    h = e.head or ""
    if e.pos == "noun":
        bits = []
        if e.plural:
            bits.append(f"plural {e.plural}")
        if e.genitive:
            bits.append(f"genitive {e.genitive}")
        return " · ".join(bits)
    if e.pos == "verb":
        g = lambda rx: (re.search(rx, h) or [None, None])[1]  # noqa: E731
        pres = g(r"third-person singular present ([^,()]+)")
        past = g(r"past tense ([^,()]+)")
        pp = g(r"past participle ([^,()]+)")
        aux = g(r"auxiliary (haben|sein)")
        bits = [x.strip() for x in (pres, past) if x]
        if pp:
            bits.append(({"haben": "hat ", "sein": "ist "}.get(aux, "") + pp.strip()))
        return " · ".join(bits)
    if e.pos == "adj":
        comp = re.search(r"comparative ([^,()]+)", h)
        sup = re.search(r"superlative ([^,()]+)", h)
        return " · ".join(m.group(1).strip() for m in (comp, sup) if m)
    return ""


def build(entries, query, source="", opts=None):
    """-> list of lines: ('title', items) | ('para', text, style, prefix) | ('sep',)
    items: ('text', s, style) | ('pill', s, fill, fg)   (fill 'neutral' = theme pill colors)"""
    o = dict(DEFAULTS, **(opts or {}))
    out = []
    for i, e in enumerate(entries[:o["entries"]]):
        if i:
            out.append(("sep",))
        g = e.gender.split()[0] if e.gender else ""
        gender = [("pill", GENDER[g][1], GENDER[g][0], "#ffffff")] if g in GENDER else []
        pos = [("pill", POS_NAMES.get(e.pos, e.pos), "neutral", None)] if e.pos else []
        if i and o.get("compact_rest"):              # secondary results: one line of meaning
            out.append(("title", gender + [("text", e.word or query, "word2")] + pos))
            if e.match:
                out.append(("para", f"Found in text as “{e.match}”", "match", None))
            if e.en:
                out.append(("para", e.en[0]["gloss"], "gloss", None))
            continue
        items = gender + [("text", e.word or query, "word")] + pos
        if e.match and "…" in e.match:
            items.append(("pill", "separable", "neutral", None))
        out.append(("title", items))
        if e.corrected:
            out.append(("para", f"Text read as “{e.corrected}” — corrected", "meta", None))
        if e.match:
            out.append(("para", f"Found in text as “{e.match}”", "match", None))
        if e.hint:
            out.append(("para", f"Used with: {e.hint}", "match", None))
        if e.via and not e.match:
            out.append(("para", f"Form: {_via(e.via)}", "meta", None))
        if len(e.parts) == 2:
            out.append(("para", f"Compound: {e.parts[0]} + {e.parts[1]}", "meta", None))
        fl = forms_line(e)
        if fl:
            out.append(("para", fl, "meta", None))
        senses = e.en[:o["senses"]]
        for k, s in enumerate(senses, 1):
            tags = [t for t in s.get("tags", []) if t in KEEP_TAGS][:2]
            gloss = s["gloss"] + (f"  ({', '.join(tags)})" if tags else "")
            out.append(("para", gloss, "gloss", str(k) if len(senses) > 1 else None))
            ex = s.get("example")
            if o["examples"] and ex and ex.get("text") and (i == 0 or not o.get("compact_rest")):
                out.append(("para", ex["text"] + (f" — {ex['english']}" if ex.get("english") else ""), "example",
                            "" if len(senses) > 1 else None))
        if o["german"]:
            for d in e.de[:o.get("german_max", 2)]:
                out.append(("para", d, "german", None))
    if len(entries) > o["entries"]:
        n = len(entries) - o["entries"]
        out.append(("para", f"{n} more result{'s' if n > 1 else ''} — open Mitsuke to see all", "meta", None))
    if source == "online":
        out.append(("para", "From Wiktionary online · gender appears once the offline dictionary is installed",
                    "meta", None))
    return out


def plain_text(lines):
    """For the clipboard."""
    out = []
    for ln in lines:
        if ln[0] == "sep":
            out.append("")
        elif ln[0] == "title":
            out.append(" ".join(it[1] for it in ln[1]))
        else:
            out.append((f"{ln[3]}. " if ln[3] else "") + ln[1])
    return "\n".join(out)


def to_qml(lines):
    """Lines as plain dicts for QML: {kind: title|para|sep, items:[{kind,text,style,fill,fg}], text, style, prefix}."""
    out = []
    for ln in lines:
        if ln[0] == "sep":
            out.append({"kind": "sep"})
        elif ln[0] == "title":
            items = []
            for it in ln[1]:
                if it[0] == "text":
                    items.append({"kind": "text", "text": it[1], "style": it[2]})
                else:
                    items.append({"kind": "pill", "text": it[1], "fill": it[2], "fg": it[3] or ""})
            out.append({"kind": "title", "items": items})
        else:
            out.append({"kind": "para", "text": ln[1], "style": ln[2],
                        "prefix": "" if ln[3] is None else ln[3], "indent": ln[3] is not None})
    return out


def linked_spans(ctx, entries, word):
    """Token indexes to highlight: (primary — the word itself, incl. fragments OCR split off;
    secondary — words the result is linked to, e.g. the separable particle or the rest of a phrase)."""
    from dictcore import clean_token
    toks = [clean_token(t).lower() for t in ctx.tokens]
    i = ctx.idx
    primary = [i]
    w = clean_token(word or "").lower()
    if w and toks[i] and toks[i] != w and toks[i] in w:      # fragments joined into one word («Kü» + «hlschrank»)
        lo = hi = i
        while lo > 0 and toks[lo - 1] and "".join(toks[lo - 1:hi + 1]) in w:
            lo -= 1
        while hi + 1 < len(toks) and toks[hi + 1] and "".join(toks[lo:hi + 2]) in w:
            hi += 1
        primary = list(range(lo, hi + 1))
    secondary = []
    match = entries[0].match if entries and getattr(entries[0], "match", "") else ""
    for part in [p for p in re.split(r"\s+|…", match.lower()) if p]:
        part = clean_token(part).lower()
        cands = [k for k, t in enumerate(toks) if t == part and k not in primary and k not in secondary]
        if cands:
            secondary.append(min(cands, key=lambda k: abs(k - i)))
    return primary, secondary
