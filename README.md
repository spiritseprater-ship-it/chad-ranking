# JARVIS — Phase 1

**A real, working voice-controlled Windows assistant.** No mockups, no simulation:
wake word → speech recognition → local Windows automation → spoken reply.

Supports **English, Hindi and Hinglish** (including Devanagari input from
`hi-IN` recognisers and common Indian English pronunciations).

---

## 1. What works in this phase

| Area | Status |
| --- | --- |
| Two-stage listening (STANDBY / ACTIVE) | ✅ local wake word, cloud audio never used in standby |
| Wake words | ✅ `Hey Jarvis`, `Jarvis`, custom `.onnx` models |
| Speech → text | ✅ Google Web Speech (default), local Whisper, local Vosk |
| Text → speech | ✅ Windows SAPI5 offline voice, adjustable rate/volume/voice |
| 20 local commands | ✅ File Explorer, Chrome, Settings, Calculator, Notepad, folders, file search, file open, Google search, scroll, browser back/forward, volume, screenshot, time, date, stop, standby, exit |
| Natural-language matching | ✅ scored pattern matching — no exact string equality |
| File-search disambiguation | ✅ candidates listed, choose by number or name (voice or buttons) |
| Permission system | ✅ confirmation required for destructive/sensitive actions |
| Emergency stop | ✅ global **Ctrl + Alt + J**, releases held keyboard/mouse input |
| PySide6 UI | ✅ status panel, mic indicator, last command/action, settings, start/stop, system tray |
| Automated tests | ✅ 108 tests (`tests/`) |

---

## 2. Requirements

* **Windows 11, 64-bit**
* **Python 3.11 or 3.12** (64-bit — required by `numpy`/`onnxruntime`)
* A microphone
* Internet access **only** for the default Google Web Speech backend
  (a local Whisper/Vosk model removes that requirement)

---

## 3. Quick start

```bat
cd JARVIS

:: 1. Create a virtual environment
python -m venv venv

:: 2. Activate it
venv\Scripts\activate

:: 3. Install the dependencies
pip install -r requirements.txt

:: 4. Download the local wake-word model (one time, ~40 MB)
python -c "import openwakeword.utils; openwakeword.utils.download_models()"

:: 5. Check the environment
python main.py --check

:: 6. Launch
python main.py
```

Say **“Hey Jarvis”** — JARVIS answers
**“JARVIS online. Ready for your command.”** and stays active for the
configured conversation window (30 s by default).

Optional: copy `.env.example` to `.env` to add a Google API key or point
JARVIS at a local model folder. `.env` is ignored by Git.

---

## 4. Project structure

```
JARVIS/
├── main.py            # entry point, config loading, worker thread, wiring
├── brain.py           # speech -> canonical command (EN / HI / Hinglish)
├── actions.py         # command -> Windows action, permissions, emergency stop
├── voice.py           # mic capture, VAD, wake word, speech recognition, TTS
├── ui.py              # PySide6 panel + system tray + settings dialog
├── config.json        # all settings
├── .env.example       # optional secrets (never committed)
├── requirements.txt   # pinned, actively maintained libraries
├── assets/            # tray/window icon is generated here at runtime
├── tests/             # pytest suite (108 tests)
└── logs/              # rotating log file (created at runtime)
```

---

## 5. Configuration (`config.json`)

| Section | Key | Meaning |
| --- | --- | --- |
| `wake_word` | `primary`, `additional` | Wake-word model names |
| | `custom_models` | `{ "name": "C:/models/my.onnx" }` — your own trained model |
| | `threshold` | Trigger score 0–1 (lower = more sensitive) |
| | `refractory_seconds` | Minimum time between two activations |
| | `activation_phrases` | Extra phrases that activate JARVIS, e.g. `chalo kaam karte hain` |
| | `activation_response` | The spoken confirmation |
| `speech` | `backend` | `google` / `whisper` / `vosk` / `auto` |
| | `language` | Recognition language hint, e.g. `en-IN`, `hi-IN` |
| | `microphone.device`, `.name_contains` | Microphone selection (no hardcoded IDs) |
| | `vad.*` | Silence detection thresholds and timeouts |
| `voice` | `engine`, `voice_name`, `rate`, `volume` | Text-to-speech settings |
| `conversation` | `timeout_seconds` | Inactivity before returning to standby |
| `browser` | `default`, `chrome_path`, `search_url` | Browser and search endpoint |
| `automation` | `scroll_amount`, `volume_step`, `search_max_results` | Input tuning |
| `permissions` | `require_confirmation.*` | What needs a spoken/visual confirmation |
| | `allowed_file_roots`, `sensitive_paths` | Where JARVIS may look for files |
| `hotkey` | `emergency_stop` | `ctrl+alt+j` |
| `logging` | `level`, `max_bytes`, `backup_count` | Logging |

The file is validated on load; problems are logged as warnings and never crash
the app. Changes made in **Settings** are written back to `config.json`.

---

## 6. Supported commands

| # | Command | Say this (examples) |
| --- | --- | --- |
| 1 | Open File Explorer | `File Explorer kholo` / `Open File Explorer` / `files dikhao` |
| 2 | Open Chrome | `Chrome kholo` / `Open Chrome` / `Browser kholo` |
| 3 | Open Windows Settings | `Open settings` / `Settings kholo` |
| 4 | Open Calculator | `Open calculator` / `Calculator kholo` |
| 5 | Open Notepad | `Open notepad` / `Notepad kholo` |
| 6 | Open a folder | `Open folder Downloads` / `Downloads folder kholo` |
| 7 | Search for a file | `Search for resume` / `File search project report` |
| 8 | Open a file | `Open report.pdf` / `Open file report.pdf` |
| 9 | Google search | `Chrome par Python search karo` / `Search for weather` |
| 10 | Scroll up | `Scroll up` / `Page up` |
| 11 | Scroll down | `Scroll down` / `Scroll niche karo` |
| 12 | Browser back | `Go back` / `Browser back` |
| 13 | Browser forward | `Go forward` / `Next page` |
| 14 | Adjust volume | `Volume 60` / `Set volume to 80` / `Volume up` |
| 15 | Screenshot | `Take a screenshot` / `Screenshot le lo` |
| 16 | Time | `What time is it` / `Time batao` / `Waqt kya hai` |
| 17 | Date | `What is the date` / `Date batao` / `Tarikh kya hai` |
| 18 | Stop listening | `Stop listening` / `Band karo` |
| 19 | Return to standby | `Go to standby` / `Jarvis, sleep` |
| 20 | Exit JARVIS | `Exit Jarvis` / `Jarvis, bye` |

Extras implemented on top: `Open app Spotify`, `Close app Chrome`, `Mute`,
`Unmute`.

### How matching works

Text is normalised, Hindi/Hinglish words are translated into English keywords,
and every command is scored by how much of the sentence it covers. The best
score wins, so `Explorer kholo`, `Open File Explorer` and `files dikhao` all
resolve to the same action without any exact string comparison. Unrecognised
speech is reported back and asked to be repeated instead of guessed.

---

## 7. Wake-word models

JARVIS uses **openwakeword**, a fully local ONNX wake-word engine. The models
are **not** committed to Git (they are large binaries). Obtain them once:

```bat
:: download the built-in models (includes hey_jarvis)
python -c "import openwakeword.utils; openwakeword.utils.download_models()"
```

They land in `%USERPROFILE%\.cache\openwakeword`. To use your own place:

1. Train or obtain a `.onnx` wake-word model (e.g. with the
   **openwakeword training scripts** or **snowboy/porcupine** conversion).
2. Point JARVIS at it:

```json
{
  "wake_word": {
    "primary": "my_wake_word",
    "custom_models": { "my_wake_word": "C:/models/my_wake_word.onnx" }
  }
}
```

If no model can be loaded, JARVIS logs a loud warning and falls back to
**transcript mode** (light VAD + short recognition pass that listens for the
wake word). Transcript mode works, but it costs more CPU and — with the Google
backend — sends short audio to the cloud even in standby. The active mode is
always reported in the UI.

> No wake-word model is bundled and no fake model is claimed: the fallback is
> explicit, logged, and configurable.

---

## 8. Speech recognition backends

| Backend | Internet | Notes |
| --- | --- | --- |
| `google` (default) | **Yes** | Google Web Speech. Free for personal use; no key needed, but the unauthenticated endpoint is not guaranteed. Set `GOOGLE_SPEECH_API_KEY` in `.env` for reliability. |
| `whisper` | No | `faster-whisper`, fully local. Download a model first (`tiny` is ~75 MB). Best for Hinglish when combined with `initial_prompt`. |
| `vosk` | No | Small, fast, offline; needs a downloaded model (`VOSK_MODEL_PATH`). |
| `auto` | — | Whisper → Vosk → Google |

Hindi/Hinglish works with `en-IN` + `hi-IN` fallback and a Hinglish
`initial_prompt` for Whisper. Devanagari script returned by a `hi-IN`
recogniser is translated before matching.

---

## 9. Safety and permissions

* Only whitelisted applications are launched — executable paths are resolved
  from a lookup table, never from raw speech.
* No shell strings from speech, no `shell=True`, no `eval`/`exec`.
* Actions flagged in `permissions.require_confirmation` ask for confirmation
  (a dialog appears and JARVIS also accepts a spoken “yes”):

| Category | Covers |
| --- | --- |
| `delete_files` | deleting files |
| `overwrite_files` | overwriting files |
| `move_sensitive_files` | moving sensitive files |
| `external_communication` | web search, sending messages |
| `camera_access` | screenshots / screen capture |
| `install_software` | installing software |
| `system_configuration` | direct volume changes, mute, lock screen |

* **Emergency stop:** press **Ctrl + Alt + J** anywhere. Automation is
  interrupted, held keyboard/mouse input is released, and JARVIS returns to
  standby. PyAutoGUI’s fail-safe (slam the mouse into the top-left corner) is
  also enabled.
* The microphone indicator shows STANDBY / LISTENING explicitly; audio is
  never recorded silently.

---

## 10. Acceptance tests

Run through these with the app open (`logs/jarvis.log` records every event):

| # | Test | Expected |
| --- | --- | --- |
| 1 | Start the application | JARVIS enters **STANDBY**; tray icon appears |
| 2 | Say *“Hey Jarvis”* | JARVIS activates and says “JARVIS online. Ready for your command.” |
| 3 | Say *“File Explorer kholo”* | File Explorer opens |
| 4 | Say *“Chrome par Python search karo”* | Chrome opens with a Google search for Python |
| 5 | Say *“Scroll down”* | The active page scrolls down |
| 6 | Say *“Jarvis, stop listening”* | JARVIS returns to standby and says “Stopped listening.” |
| 7 | Press **Ctrl + Alt + J** | Automation stops immediately, inputs released |

### Automated tests

```bat
python -m pytest tests -q
```

108 tests cover command understanding (English/Hindi/Hinglish/Devanagari),
number parsing, permissions, disambiguation, emergency stop, configuration
validation and the audio engine (VAD, wake-word fallback, standby state).
Microphone-dependent behaviour is covered by manual tests above.

---

## 11. Packaging to a Windows EXE

```bat
pyinstaller ^
  --noconsole --onefile ^
  --name JARVIS ^
  --add-data "assets;assets" ^
  main.py
```

Output: `dist\JARVIS.exe`. Build on the target Windows machine (or a matching
Windows CI runner) — PyInstaller cannot cross-compile from Linux.

---

## 12. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `--check` shows `[MISS] PySide6` | `pip install -r requirements.txt` |
| No microphone found | Windows **Settings → Privacy → Microphone → Desktop app access** must be on; pick a device in **Settings** inside JARVIS |
| `could not register the emergency-stop hotkey` | Another app owns Ctrl+Alt+J; use the window's **Stop listening** button instead |
| Nothing happens when you speak | Say the wake word first; check that the tray icon is not in ERROR state; read `logs/jarvis.log` |
| Wake word never triggers | Lower `wake_word.threshold` (e.g. `0.4`) or check that the model downloaded (see §7) |
| JARVIS answers its own voice | `voice.self_echo_cooldown_ms` and the speaking-detection guard already handle this; raise the cooldown if needed |
| Google Web Speech fails | The backend needs internet, or set `GOOGLE_SPEECH_API_KEY` in `.env`, or switch `speech.backend` to `whisper` |
| Whisper/Vosk missing | Download the model and set `speech.backend`, `speech.whisper.model_size` or `VOSK_MODEL_PATH` |
| `settings.json` / permission errors | JARVIS logs the exact problem; the app keeps running with defaults |
| Volume commands fail | Requires Windows Mixed Volume Control (`pycaw`); some USB audio drivers do not expose it |
| Screenshot is blank | Some DRM/protected windows cannot be captured — a Windows limitation, not a bug |

---

## 13. Verification checklist

- [ ] `python -m venv venv` + `pip install -r requirements.txt` succeed
- [ ] `python main.py --check` reports `[OK]` for PySide6, sounddevice, numpy, openwakeword, SpeechRecognition, pyttsx3, pyautogui
- [ ] Wake-word model downloaded; log says `wake word engine mode: openwakeword`
- [ ] `config.json` loads with **no warnings**
- [ ] `python -m pytest tests -q` → **108 passed**
- [ ] App starts into STANDBY with a tray icon; closing the window hides to tray
- [ ] “Hey Jarvis” activates; “chalo kaam karte hain” also activates
- [ ] Commands 3–5, 7, 8, 14–17 execute as expected
- [ ] Multi-match file search asks for a choice; a number or name selects it
- [ ] Volume/screenshot ask for confirmation according to `config.json`
- [ ] Ctrl + Alt + J stops automation immediately
- [ ] No audio leaves the machine while in STANDBY (local wake word only)

---

## 14. Phase 2 (not implemented yet)

Gemini integration and the animated 3D orb are deliberately **not** in this
phase. The module boundaries (`brain` / `actions` / `voice` / `ui`) are ready
for them.
