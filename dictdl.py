"""The prebuilt offline dictionary: the same dict.sqlite the app would build from Wiktionary, built once by
GitHub Actions (.github/workflows/dictionary.yml) and published as the `dictionary` release (~55 MB instead
of downloading 4.3 GB and building for 15 minutes). Verified with SHA-256 before it replaces anything."""
import hashlib
import json
import os
import sqlite3
import urllib.request
import zipfile

DEFAULT_REPO = "Berneyw/mitsuke"
MIN_ENTRIES = 50000


def base_url(repo):
    return f"https://github.com/{repo or DEFAULT_REPO}/releases/download/dictionary/"


def fetch_meta(repo, timeout=20, base=None):
    req = urllib.request.Request((base or base_url(repo)) + "mitsuke-dictionary.json", headers={"User-Agent": "Mitsuke"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        meta = json.loads(r.read().decode("utf-8"))
    if meta.get("format") != 1 or not meta.get("sha256"):
        raise ValueError("unknown dictionary package format")
    return meta


def fetch(repo, work_dir, progress=None, base=None):
    """Downloads, verifies and unpacks the dictionary. Returns (path to the new dict.sqlite, meta).
    progress(done_bytes, total_bytes) is called while downloading."""
    import build_dict
    base = base or base_url(repo)
    meta = fetch_meta(repo, base=base)
    zpath = os.path.join(work_dir, "mitsuke-dictionary.zip")
    if os.path.exists(zpath):                 # a finished download from an earlier attempt may be outdated
        os.remove(zpath)
    build_dict.download(base + "mitsuke-dictionary.zip", zpath, progress)
    h = hashlib.sha256()
    with open(zpath, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != meta["sha256"]:
        os.remove(zpath)
        raise ValueError("the dictionary download is damaged (checksum mismatch)")
    out = os.path.join(work_dir, "dict.sqlite.new")
    with zipfile.ZipFile(zpath) as z:
        with z.open("dict.sqlite") as src, open(out, "wb") as dst:
            for chunk in iter(lambda: src.read(1 << 20), b""):
                dst.write(chunk)
    os.remove(zpath)
    db = sqlite3.connect(out)
    try:
        n = db.execute("SELECT count(*) FROM entries").fetchone()[0]
        db.execute("SELECT count(*) FROM forms").fetchone()
    finally:
        db.close()
    if n < MIN_ENTRIES:
        os.remove(out)
        raise ValueError(f"the dictionary looks incomplete ({n} entries)")
    return out, meta
