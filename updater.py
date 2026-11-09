"""Auto-update from GitHub Releases.

A release must carry two assets: Mitsuke-<version>-win64.zip (the dist\\Mitsuke folder) and the same name
+ .sha256 (hex digest). The workflow in .github/workflows/release.yml produces both on every v* tag.
Install = download -> verify SHA-256 -> unpack to %LOCALAPPDATA%\\Mitsuke\\update -> after Mitsuke exits,
a small script copies the new files over the install folder and starts Mitsuke again.
Settings, the dictionary and My Words live in %APPDATA%\\Mitsuke and are never touched.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

UA = "Mitsuke-updater"
API = "https://api.github.com"


def parse_version(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def is_frozen():
    return getattr(sys, "frozen", False)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(repo, current):
    """-> dict(version, notes, zip_url, sha_url, size, page) when a newer release exists, else None."""
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo or ""):
        raise ValueError("Set the update source as owner/repository.")
    data = json.loads(_get(f"{API}/repos/{repo}/releases/latest"))
    ver = data.get("tag_name", "").lstrip("vV")
    if parse_version(ver) <= parse_version(current):
        return None
    assets = {a["name"]: a for a in data.get("assets", [])}
    z = next((a for n, a in assets.items() if n.lower().endswith(".zip")), None)
    if not z or (z["name"] + ".sha256") not in assets:
        raise ValueError(f"Release {ver} has no verified Windows build.")
    return {"version": ver, "notes": (data.get("body") or "").strip(), "zip_url": z["browser_download_url"],
            "sha_url": assets[z["name"] + ".sha256"]["browser_download_url"], "size": z.get("size", 0),
            "page": data.get("html_url", "")}


def download(info, progress=None):
    """Downloads and verifies the zip; returns the folder with the unpacked new Mitsuke."""
    expected = _get(info["sha_url"]).decode().split()[0].strip().lower()
    root = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "Mitsuke", "update")
    os.makedirs(root, exist_ok=True)
    zpath = os.path.join(root, f"Mitsuke-{info['version']}.zip")
    h = hashlib.sha256()
    req = urllib.request.Request(info["zip_url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(zpath, "wb") as f:
        total = int(r.headers.get("Content-Length") or info.get("size") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if h.hexdigest().lower() != expected:
        os.remove(zpath)
        raise ValueError("The download is damaged (checksum mismatch). Nothing was installed.")
    dest = os.path.join(root, info["version"])
    with zipfile.ZipFile(zpath) as z:
        for n in z.namelist():                                   # refuse paths that escape the folder
            if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                raise ValueError("Unsafe file name in the update archive.")
        z.extractall(dest)
    os.remove(zpath)
    inner = os.path.join(dest, "Mitsuke")
    new = inner if os.path.exists(os.path.join(inner, "Mitsuke.exe")) else dest
    if not os.path.exists(os.path.join(new, "Mitsuke.exe")):
        raise ValueError("The update archive doesn't contain Mitsuke.exe.")
    return new


def install_on_exit(new_dir):
    """Starts a hidden script that waits for this process to exit, copies the files and restarts Mitsuke."""
    install = os.path.dirname(sys.executable)
    pid = os.getpid()
    script = os.path.join(os.path.dirname(new_dir), "apply-update.cmd")
    with open(script, "w", encoding="utf-8") as f:
        f.write(f"""@echo off
chcp 65001 >nul
:wait
tasklist /FI "PID eq {pid}" | find "{pid}" >nul && (timeout /t 1 /nobreak >nul & goto wait)
robocopy "{new_dir}" "{install}" /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP >nul
start "" "{os.path.join(install, 'Mitsuke.exe')}" --tray
rmdir /s /q "{new_dir}"
del "%~f0"
""")
    subprocess.Popen(["cmd", "/c", script], creationflags=0x08000000 | 0x00000008)   # no window, detached
