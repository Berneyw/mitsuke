# Mitsuke

A German dictionary that works on top of games and any other Windows app. Hold a key, point at a German word on
screen, and a card appears next to it with the article (der / die / das), word forms, English translations,
German definitions and examples — without leaving the game.

![Word card over a game](docs/screenshots/game-card.png)

## Features

- **Reads any text on screen** with Windows' built-in text recognition (OCR) — game dialogue, menus, videos,
  anything that isn't selectable text.
- **Understands real sentences**: phrases (*auf jeden Fall*), separable verbs split across a sentence
  (*räume … auf* → **aufräumen**), verbs with prepositions, compound words, inflected forms and words broken
  across lines.
- **Highlights what it read**: the word under the cursor and the words linked to it, such as the particle of a
  separable verb.
- **Offline dictionary** built from English and German Wiktionary (about 200 000 entries, 1.2 million word forms), with
  online lookup as a fallback. Compounds that aren't in it (*Abschlussball*, *Live-Modus*) are explained from their
  parts, with gender and plural taken from the last part.
- **Translate whole sentences** with a second key (Ctrl by default): hold it over a sentence and its
  translation appears, into English or another language of your choice (by Google Translate, online). In a
  full-screen game the picture pauses while the key is held, so tooltips that vanish as soon as the mouse moves
  can be read — and looked up word by word — at leisure.
- **Pin a card** with a double-tap of the key to scroll it, move it and save the word.
- **History** of every word you looked up, with the sentence it was in and how often it came up.
- **My Words**: saved words with the sentence they came from, spaced-repetition review and Anki export.
- **Modern translucent interface** rendered on the GPU, dark and light appearance, and accessibility options
  (reduce transparency, increase contrast, reduce motion).
- **Updates** from GitHub Releases, verified with SHA-256.

## Screenshots

| | |
|---|---|
| ![Lookup](docs/screenshots/lookup.png) | ![My Words](docs/screenshots/my-words.png) |
| **Lookup** — search any word or phrase | **My Words** — saved words and review |
| ![Dictionary](docs/screenshots/dictionary.png) | ![Settings](docs/screenshots/settings.png) |
| **Dictionary** — offline data and sources | **Settings** — scanning, card and appearance |
| ![Pinned card](docs/screenshots/pinned-card.png) | ![Card preview](docs/screenshots/settings-card-preview.png) |
| **Pinned card** — stays open, scrolls, saves | **Card preview** — updates live with the settings |

<p align="center"><img src="docs/screenshots/tray-menu.png" alt="Tray menu" width="340"><br><b>Tray menu</b></p>

## Getting started

1. Download `MitsukeSetup-*.exe` from [Releases](../../releases) and run it — it installs for your user only,
   no administrator rights needed, and adds Mitsuke to the Start menu. It lives in the tray.
   Prefer no installer? Take `Mitsuke-*-win64.zip`, unzip it anywhere and run `Mitsuke.exe`.
   Your settings and words are kept in `%APPDATA%\Mitsuke`, also when you uninstall.
2. On first start Mitsuke offers to install Windows' German text recognition (a few MB) and to download the
   offline dictionary (about 55 MB; it's rebuilt from Wiktionary every month).
3. In the game, use **borderless windowed** mode, hold **Shift** (or Ctrl / Alt — see Settings) and point at a
   word.

Requires Windows 10 or 11 (64-bit).

## Building from source

- Python 3.10–3.14 (64-bit).
- `run_dev.bat` installs the requirements and starts the app.
- `build_exe.bat` builds `dist\Mitsuke\Mitsuke.exe` (keep the whole folder together); with
  [Inno Setup 6](https://jrsoftware.org/isinfo.php), `iscc /DAppVersion=2.5 installer\Mitsuke.iss` then makes
  `dist\MitsukeSetup-2.5.exe`.
- `python tools/make_icons.py` redraws the small icon sizes (16–48 px) in `assets/icon.ico`.
- The UI is Qt Quick (PySide6). The glass shader in `gui/qml/Mitsuke/shaders` is precompiled; after editing
  `glass.frag`, rebuild it with `pyside6-qsb` (from PySide6-Addons):

  ```
  pyside6-qsb --glsl "150,300es" --hlsl 50 --msl 12 -o glass.frag.qsb glass.frag
  ```

- Pushing a tag such as `v2.1` builds the app on GitHub Actions and publishes a release.
- The `dictionary` workflow rebuilds the offline dictionary from Wiktionary (monthly, or on demand) and publishes
  it as the `dictionary` pre-release that the app downloads.

| Path | Contents |
|---|---|
| `main.py` | app core: key → OCR → lookup → card |
| `ocrword.py` | screen capture, Windows OCR, context around the cursor |
| `dictcore.py`, `engine.py`, `build_dict.py`, `online.py` | dictionary: parsing, phrases, building the database from Wiktionary |
| `render.py` | word card model shared by the window and the overlays |
| `words.py` | My Words and spaced repetition |
| `gui/` | interface: Python ↔ QML bridge, overlays, Windows materials, QML components and shader |
| `tests/` | unit tests and an OCR accuracy bench on synthetic game frames |

## Data and privacy

Settings, the dictionary, saved words, history and the log stay on your computer in `%APPDATA%\Mitsuke`.
Screen captures are processed locally and never sent anywhere; the strip around a word that couldn't be found is
kept locally (`notfound`, the last 300) to help improve recognition. Network requests: the sentence you hold the
sentence key over is sent to Google Translate (translate.googleapis.com); online word lookups go to
en.wiktionary.org when a word isn't in the offline dictionary; plus dictionary downloads and update checks.

Dictionary data © Wiktionary contributors, licensed under CC BY-SA 4.0, via [kaikki.org](https://kaikki.org).
