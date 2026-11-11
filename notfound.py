"""A diagnostic journal of words the app read on screen but couldn't find (OCR misreads, game-only words).

Not part of the interface: it lives in the data folder (notfound/), keeps the last 300 cases as JSON lines with
the tokens of the line, and a PNG of the strip that was read, so recognition problems can be studied later."""
import json
import logging
import os
import threading
import time

MAX_CASES = 300
_lock = threading.Lock()


def record(data_dir, word, ctx=None, grab=None):
    """word: what was read; ctx: the OCR context (tokens, capture rect); grab(left, top, w, h) -> (w, h, BGRA)."""
    try:
        folder = os.path.join(data_dir, "notfound")
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        image = ""
        cap = getattr(ctx, "capture", None) if ctx is not None else None
        if grab and cap:
            try:
                from PIL import Image
                x, y, w, h = (int(v) for v in cap)
                gw, gh, data = grab(x, y, w, h)
                image = f"{stamp}-{abs(hash(word)) % 10000:04d}.png"
                Image.frombytes("RGB", (gw, gh), data, "raw", "BGRX").save(os.path.join(folder, image), optimize=True)
            except Exception:  # noqa — the journal must never disturb the app
                image = ""
        case = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "word": word,
                "tokens": list(getattr(ctx, "tokens", []) or []), "idx": getattr(ctx, "idx", -1),
                "mode": getattr(ctx, "mode", ""), "image": image}
        path = os.path.join(folder, "notfound.jsonl")
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
            _trim(folder, path)
    except Exception:  # noqa
        logging.debug("notfound journal", exc_info=True)


def _trim(folder, path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if len(lines) <= MAX_CASES:
        return
    keep, drop = lines[-MAX_CASES:], lines[:-MAX_CASES]
    for line in drop:
        try:
            img = json.loads(line).get("image")
            if img:
                os.remove(os.path.join(folder, img))
        except (ValueError, OSError):
            pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(keep)
    os.replace(tmp, path)
