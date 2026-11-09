import http.server, os, subprocess, sys, tempfile, threading, types
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
from dictcore import Dictionary


def build():
    out = os.path.join(tempfile.mkdtemp(), "t.sqlite")
    subprocess.check_call([sys.executable, os.path.join(root, "build_dict.py"), "--en", os.path.join(root, "tests/sample_en.jsonl"),
                           "--de", os.path.join(root, "tests/sample_de.jsonl"), "--out", out], stdout=subprocess.DEVNULL)
    return Dictionary(out)


def test_lookup():
    d = build()
    e = d.lookup("Häuser,")[0]
    assert (e.word, e.gender, e.plural, e.article) == ("Haus", "n", "Häuser", "das") and e.via
    assert d.lookup("ging")[0].word == "gehen"
    assert d.lookup("haus")[0].word == "Haus"
    # an unknown compound: one entry for the whole word (gender / plural from its last part), then the parts
    k = d.lookup("Küchentisch")
    assert [x.word for x in k] == ["Küchentisch", "Tisch", "Küche"] and k[0].parts == ["Küche", "Tisch"]
    assert k[0].gender == k[1].gender
    assert d.lookup("Quatsch") == []
    assert d.lookup("Haus")[0].de == ["Gebäude, das Menschen als Wohnung oder Arbeitsstätte dient"]  # без «Genitiv … Hau»
    assert len(d.lookup("Häuser")) == 1                                  # без дублей
    assert d.lookup("Schrank")[0].plural == "Schränke"                   # мн. число даже с лишними тегами
    assert d.lookup("Kühlschrank")[0].plural == "Kühlschränke"           # мн. число из заголовка


def ctx(d, text, word, tight=None):
    toks = text.split()
    return d.lookup_context(toks, toks.index(word), tight)


def test_context():
    d = build()
    # раздельный глагол: курсор на глаголе и на приставке
    ents, w = ctx(d, "Ich räume das Zimmer auf.", "räume")
    assert ents[0].word == "aufräumen" and ents[0].match == "räume … auf"
    assert ctx(d, "Ich räume das Zimmer auf.", "auf.")[0][0].word == "aufräumen"
    assert ctx(d, "Er räumt heute auf, weil", "räumt")[0][0].word == "aufräumen"
    # через лемму, без таблицы форм: rufe + an -> anrufen
    assert ctx(d, "Ich rufe dich morgen an.", "rufe")[0][0].word == "anrufen"
    # «auf» не в конце предложения — это предлог, а не приставка
    ents, _ = ctx(d, "Ich räume auf den Tisch.", "räume")
    assert ents[0].word == "räumen"
    # фраза
    ents, _ = ctx(d, "Das mache ich auf jeden Fall morgen.", "jeden")
    assert ents[0].word == "auf jeden Fall" and ents[0].match == "auf jeden Fall"
    ents, _ = ctx(d, "Das mache ich auf jeden Fall morgen.", "Fall")
    assert ents[0].word == "auf jeden Fall" and any(e.word == "Fall" for e in ents)
    # глагол + предлог: нужное значение первым
    ents, _ = ctx(d, "Ich warte auf dich.", "warte")
    assert ents[0].word == "warten" and ents[0].en[0]["gloss"] == "to wait (for)  [+ auf + Akk.]" and ents[0].hint == "warten auf …"
    # обрывки слова от OCR склеиваются
    ents, w = ctx(d, "Der Küch entisch ist", "Küch", [False, True, False])
    assert w == "Küchentisch" and ents[0].word == "Küchentisch"
    ents, w = ctx(d, "Der Kühl schrank ist", "schrank", [False, True, False])
    assert w == "Kühlschrank" and ents[0].word == "Kühlschrank"
    # обычный пробел между известными словами не склеивается
    assert ctx(d, "Das Haus Tisch", "Haus")[1] == "Haus"
    # ручной ввод фразы
    assert d.lookup("auf jeden Fall")[0].word == "auf jeden Fall"
    assert d.lookup("räumt auf")[0].word == "aufräumen"


def test_card_layout_and_config():
    import render as R
    from config import Config
    d = build()
    ents, _ = ctx(d, "Ich räume das Zimmer auf.", "räume")
    full = R.build(ents, "räume", opts={"entries": 6})
    compact = R.build(ents, "räume", opts={"entries": 6, "compact_rest": True, "examples": False})
    assert full[0][0] == "title" and any(l[0] == "sep" for l in full)
    assert len(compact) <= len(full)
    assert any(l[0] == "para" and "räume … auf" in l[1] for l in compact)
    haus = d.lookup("Haus")[0]
    assert R.forms_line(haus) == "plural Häuser · genitive Hauses"
    p = tempfile.mkdtemp()
    cfg = Config(p + "/c.json")
    cfg.set("card_width", 500)
    cfg.export(p + "/x.json")
    cfg.reset()
    assert cfg["card_width"] == 440
    assert cfg.import_(p + "/x.json") >= 1 and cfg["card_width"] == 500


def test_reflexive_and_free_phrases():
    d = build()
    e = ctx(d, "Ich freue mich auf das Wochenende.", "freue")[0][0]
    assert e.word == "freuen" and e.hint == "sich freuen auf …" and e.en[0]["gloss"].startswith("to look forward")
    e = ctx(d, "Das freut mich sehr.", "freut")[0][0]           # object, not reflexive
    assert e.en[0]["gloss"].startswith("to gladden") and not e.hint
    ents, _ = ctx(d, "Ich weiß davon Bescheid.", "weiß")
    assert ents[0].word == "Bescheid wissen" and ents[0].match == "weiß … Bescheid"
    assert ctx(d, "Ich räume heute das Zimmer und den Flur auf.", "räume")[0][0].word == "aufräumen"
    assert ctx(d, "Ich räume auf und er kocht.", "räume")[0][0].word == "aufräumen"


def test_build_context_multiline():
    from ocrword import Box, build_context
    boxes = [Box("Ich", 10, 0, 30, 12, 0), Box("räume", 46, 0, 50, 12, 0),
             Box("heute", 10, 20, 50, 12, 1), Box("das", 66, 20, 30, 12, 1),
             Box("Zimmer", 10, 40, 60, 12, 2), Box("auf.", 76, 40, 30, 12, 2)]
    c = build_context(boxes, 70, 6, 400, img_h=100)
    assert c.tokens == ["Ich", "räume", "heute", "das", "Zimmer", "auf."] and c.word == "räume"
    c = build_context(boxes, 90, 46, 400, img_h=53)                  # cursor on the particle, verb two lines up
    assert c.word == "auf." and c.tokens[1] == "räume" and c.cut_bottom
    d = build()
    assert d.lookup_context(c.tokens, c.idx)[0][0].word == "aufräumen"
    assert d.lookup_context(c.tokens, 1)[0][0].word == "aufräumen"


def test_word_store():
    from words import WordStore, DAY
    d = build()
    s = WordStore(os.path.join(tempfile.mkdtemp(), "w.sqlite"))
    e = d.lookup("Haus")[0]
    wid, created = s.add_entry(e, "Das Haus ist groß.")
    assert created and s.has("Haus", "noun") and not s.add_entry(e)[1]
    assert s.due_count() == 1
    iv = s.review(wid, "good")
    assert iv == 1.0 and s.due_count() == 0 and s.due_count(now=__import__("time").time() + 2 * DAY) == 1
    card = s.all()[0]
    assert s.schedule(card, "again")[0] < 0.01 and s.schedule(card, "easy")[0] > s.schedule(card, "good")[0]
    p = os.path.join(tempfile.mkdtemp(), "anki.txt")
    assert s.export_anki(p) == 1
    lines = open(p, encoding="utf-8").read().splitlines()
    assert lines[0] == "#separator:tab" and lines[3].split("\t")[0] == "das Haus" and "Das Haus ist groß." in lines[3]
    s.remove(wid)
    assert s.count() == 0


def test_updater():
    import hashlib, io, json, zipfile
    import updater as up
    assert up.parse_version("2.10") > up.parse_version("2.9") and up.parse_version("v2.0") == (2, 0)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Mitsuke/Mitsuke.exe", b"MZ fake")
    payload = buf.getvalue()
    good_sha = hashlib.sha256(payload).hexdigest()
    state = {"sha": good_sha}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path.endswith("/releases/latest"):
                body = json.dumps({"tag_name": "v9.1", "body": "notes", "html_url": base, "assets": [
                    {"name": "Mitsuke-9.1-win64.zip", "browser_download_url": base + "/z", "size": len(payload)},
                    {"name": "Mitsuke-9.1-win64.zip.sha256", "browser_download_url": base + "/s"}]}).encode()
            elif self.path == "/z":
                body = payload
            else:
                body = state["sha"].encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    up.API = f"http://127.0.0.1:{srv.server_port}"
    os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
    assert up.check("me/mitsuke", "9.1") is None                       # already current
    info = up.check("me/mitsuke", "2.0")
    assert info["version"] == "9.1"
    new = up.download(info)
    assert os.path.exists(os.path.join(new, "Mitsuke.exe"))
    state["sha"] = "0" * 64                                              # tampered download is refused
    try:
        up.download(info)
        assert False, "checksum mismatch not detected"
    except ValueError:
        pass
    try:
        up.check("not a repo", "1.0")
        assert False
    except ValueError:
        pass
    srv.shutdown()


def test_block_and_highlight_spans():
    from ocrword import Box, build_context
    from render import linked_spans
    # our paragraph on the left; another window's text on the same lines far to the right
    boxes = [Box("Ich", 10, 0, 30, 12, 0), Box("räume", 46, 0, 50, 12, 0), Box("Zimmer", 102, 0, 60, 12, 0),
             Box("Fremd", 900, 0, 60, 12, 0), Box("auf.", 10, 18, 30, 12, 1), Box("Text", 900, 18, 40, 12, 1)]
    c = build_context(boxes, 70, 6, 1200)
    assert c.tokens == ["Ich", "räume", "Zimmer", "auf."] and len(c.rects) == len(c.tokens)
    d = build()
    ents, word = d.lookup_context(c.tokens, c.idx, c.tight)
    assert ents[0].word == "aufräumen"
    prim, sec = linked_spans(c, ents, word)
    assert prim == [1] and sec == [3]                    # the verb filled, its particle outlined


def test_build_context():
    from ocrword import Box, build_context
    # «Ich räume das» / «Zim-» на 1-й строке, «mer auf.» на 2-й; «Küch»+«entisch» почти без зазора
    boxes = [Box("Ich", 10, 0, 30, 12, 0), Box("räume", 46, 0, 50, 12, 0), Box("Küch", 102, 0, 40, 12, 0),
             Box("entisch", 143, 0, 60, 12, 0), Box("Zim-", 210, 0, 40, 12, 0),
             Box("mer", 10, 20, 30, 12, 1), Box("auf.", 46, 20, 30, 12, 1)]
    c = build_context(boxes, 70, 6, 400)
    assert c.word == "räume" and c.tokens[-2:] == ["mer", "auf."] and c.tight[:4] == [False, False, True, False]
    assert not c.cut_left and not c.cut_right
    assert build_context(boxes, 230, 6, 400).word == "Zimmer"           # перенос склеен
    assert build_context(boxes, 20, 26, 400).word == "Zimmer"
    c = build_context(boxes, 70, 6, 251)                                  # «Zim-» упирается в край — выброшен
    assert c.cut_right and "Zim-" not in c.tokens
    c = build_context([Box("ame", 0, 0, 30, 12, 0), Box("Zimmer", 40, 0, 60, 12, 0), Box("auf.", 106, 0, 30, 12, 0)],
                      120, 6, 400)
    assert c.cut_left and c.tokens == ["Zimmer", "auf."]


def test_pick_word():
    from ocrword import Box, part_under_cursor, pick_word
    # две строки: «Das Haus ist groß» (y 0..12) и «Küche/Bad» (y 20..32)
    boxes = [Box("Das", 0, 0, 30, 12), Box("Haus", 35, 0, 40, 12), Box("ist", 80, 0, 20, 12),
             Box("Küche/Bad", 0, 20, 90, 12)]
    assert pick_word(boxes, 50, 6) == "Haus"
    assert pick_word(boxes, 36, 6) == "Haus"          # самый край слова
    assert pick_word(boxes, 32.5, 6) is None          # промежуток между словами — ничего, не соседнее
    assert pick_word(boxes, 50, 16) is None           # между строками — ничего
    assert pick_word(boxes, 300, 100) is None
    assert pick_word(boxes, 20, 26) == "Küche"        # склейка: левая часть
    assert pick_word(boxes, 80, 26) == "Bad"          # склейка: правая часть
    assert part_under_cursor("Haus,", 0, 50, 10) == "Haus"
    assert part_under_cursor("Sims", 0, 40, 20) == "Sims"
    assert part_under_cursor("E-Mail", 0, 60, 50) == "E-Mail"   # дефис внутри слова не режем


def test_download_resume():
    import build_dict as bd
    payload = os.urandom(3_000_000)

    class H(http.server.BaseHTTPRequestHandler):
        fail_once = [True]
        def log_message(self, *a): pass
        def do_GET(self):
            rng = self.headers.get("Range")
            start = int(rng.split("=")[1].split("-")[0]) if rng else 0
            body = payload[start:]
            self.send_response(206 if rng else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if H.fail_once[0] and not rng:       # обрыв на середине первой попытки
                H.fail_once[0] = False
                self.wfile.write(body[:1_200_000])
                self.wfile.flush()
                self.connection.close()
                return
            self.wfile.write(body)
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dest = os.path.join(tempfile.mkdtemp(), "f.bin")
    bd.download(f"http://127.0.0.1:{srv.server_port}/f", dest)
    assert open(dest, "rb").read() == payload
    srv.shutdown()


def test_online_and_config():
    from online import Online, parse_response
    from config import Config
    from engine import Engine
    d = tempfile.mkdtemp()
    data = {"de": [{"partOfSpeech": "Noun", "definitions": [{"definition": "<b>house</b>"}]}]}
    o = Online(d + "/c.sqlite"); calls = []
    o._fetch = lambda t: (calls.append(t), data if t == "Haus" else None)[1]
    assert o.lookup("haus")[0].en[0]["gloss"] == "house"
    n = len(calls); o.lookup("haus"); assert len(calls) == n        # из кэша
    cfg = Config(d + "/cfg.json"); cfg.set("key", "alt")
    assert Config(d + "/cfg.json")["key"] == "alt"
    eng = Engine(cfg, d); eng.online._fetch = o._fetch
    assert eng.lookup("Haus")[1] == "online"


def test_recapture_when_word_cut():
    from ocrword import Box, Ocr
    o = Ocr.__new__(Ocr)
    o.scale, o.half_w, o.half_h = 1, 50, 20
    calls = []

    def fake(cx, cy, hw, hh, mode="raw"):
        calls.append(hw)
        if hw == 50:   # узкий снимок: слово упирается в правый край -> обрубок
            return [Box("Küchent", 40, 10, 60, 14)], 50, 20, 100, 40
        return [Box("Küchentisch", 90, 10, 90, 14)], 100, 20, 200, 40
    o._recognize = fake
    assert o.word_at(500, 300) == "Küchentisch" and calls == [50, 100]


def test_prebuilt_dictionary():
    """The ready-made dictionary is downloaded, checked against its SHA-256 and rejected when damaged."""
    import hashlib, json, sqlite3, zipfile, functools
    import dictdl
    tmp = tempfile.mkdtemp()
    srv_dir = os.path.join(tmp, "srv"); os.makedirs(srv_dir)
    db = sqlite3.connect(os.path.join(tmp, "dict.sqlite"))
    db.executescript("CREATE TABLE entries(id INTEGER PRIMARY KEY, word TEXT); CREATE TABLE forms(lower TEXT);")
    db.executemany("INSERT INTO entries(word) VALUES(?)", [(f"w{i}",) for i in range(dictdl.MIN_ENTRIES + 5)])
    db.commit(); db.close()
    zp = os.path.join(srv_dir, "mitsuke-dictionary.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(tmp, "dict.sqlite"), "dict.sqlite")
    meta = {"format": 1, "sha256": hashlib.sha256(open(zp, "rb").read()).hexdigest(), "entries": dictdl.MIN_ENTRIES + 5}
    json.dump(meta, open(os.path.join(srv_dir, "mitsuke-dictionary.json"), "w"))
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=srv_dir)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    work = os.path.join(tmp, "work"); os.makedirs(work)
    try:
        new, m = dictdl.fetch("x/y", work, base=base)
        assert os.path.exists(new) and m["entries"] == dictdl.MIN_ENTRIES + 5
        meta["sha256"] = "0" * 64                                          # damaged download is refused
        json.dump(meta, open(os.path.join(srv_dir, "mitsuke-dictionary.json"), "w"))
        try:
            dictdl.fetch("x/y", work, base=base)
            assert False, "a checksum mismatch must be rejected"
        except ValueError:
            pass
    finally:
        srv.shutdown()
