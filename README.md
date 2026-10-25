# JARVIS — a Windows 11 AI assistant

**A real, working voice-controlled Windows assistant.** No mockups, no simulation:
wake word → speech recognition → Gemini → Windows automation → spoken reply.

Supports **English, Hindi and Hinglish** (including Devanagari input from `hi-IN`
recognisers and common Indian English pronunciations).

---

## 1. What it does

| Phase | Capability | Status |
| --- | --- | --- |
| 1 | Two-stage listening (STANDBY / ACTIVE), local wake word, offline STT/TTS fallbacks | ✅ works |
| 2 | Gemini conversation, tool use, task planning, Live API voice mode, persisted history | ✅ implemented, needs a real key to run |
| 3 | Windows + browser automation, file intelligence, screen understanding, camera, multi-step tasks | ✅ implemented, needs Windows to run |
| 4 | Premium particle-orb UI: 5 states, compact/full/tray, low-resource mode, tray icon | ✅ implemented, needs PySide6 to render |
| 5 | PyInstaller onedir EXE, startup setting, tray, uninstaller, graceful missing-key errors | ✅ build script + CI, **not built here** (see §9) |

Detailed status per requirement: [`JARVIS/CHECKLIST.md`](JARVIS/CHECKLIST.md).

---

## 2. Requirements

- **Windows 11 x64**, Python **3.11 or 3.12** only for *building* — the shipped
  `JARVIS.exe` needs no Python.
- A microphone. A webcam only if you enable camera support.
- A **Gemini API key** (free tier is enough) from
  <https://aistudio.google.com/app/apikey>.
- No local LLM, no downloaded STT model and no bundled browser are required.

---

## 3. Install (developer / from source)

```powershell
cd JARVIS
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium      # optional: browser automation
python main.py                   # first run shows the setup wizard
```

Command line:

```powershell
python main.py                   # normal launch
python main.py --check           # environment/dependency report
python main.py --diagnostics     # full self-diagnostic report
python main.py --config other.json
python -m pytest tests -q        # 255 tests
```

---

## 4. Architecture

```
main.py        entry point, config, logging, worker thread, JarvisApp orchestration
brain.py       natural-language matching + Router (local command vs Gemini)
actions.py     Phase 1 action engine + ToolRegistry (validated tool dispatch)
voice.py       mic stream, VAD, wake word, speech recognition, TTS
gemini.py      Gemini client, conversation history, tool schemas, Live API wrapper
desktop.py     Windows control: mouse, keyboard, windows, apps, files, screenshots
browser.py     Playwright browser controller (lazy, optional)
camera.py      on-demand webcam capture (optional)
planner.py     multi-step task planning, command chaining, cancellation, history
orb.py         particle-orb visualisation (pure maths + lazy Qt widget)
ui.py          PySide6 window, settings, first-run wizard, dialogs
diagnostics.py "Check my JARVIS" self-tests
```

**Routing.** Every utterance goes through `brain.Router`:

1. `cancel` — always local, works offline.
2. `local` — matched by the local command table. Lifecycle, safety and system
   controls are **always local**, so volume, mute, exit, cancel and the emergency
   stop never depend on the cloud.
3. `ai` — conversational or unrecognised requests go to Gemini, which may call
   the validated tool registry.
4. `unknown` — nothing matched and Gemini is unavailable; JARVIS asks you to
   repeat instead of guessing.

**Tool safety.** Gemini never receives shell access. It may only call the 33
tools declared in `gemini.TOOL_SCHEMAS`, each of which is validated in
`actions.ToolRegistry` before it touches the operating system:

- unknown tool names, missing arguments and out-of-range values are rejected
- destructive tools (`file_delete`, `window_close`, `keyboard_*`,
  `mouse_*`, `take_screenshot`, `camera_photo`, `summarize_page`) require an
  explicit confirmation from you
- protected paths (`Windows`, `System32`, `AppData`, `$Recycle.Bin`, …) are
  refused outright
- no `eval`/`exec`, no `shell=True`, no arbitrary commands from model output
- model output and web content are treated as untrusted data, never as code

---

## 5. Using it

Wake it with **"Hey Jarvis"** (or click the orb / tray icon).

| You say | What happens |
| --- | --- |
| `open Chrome` | launches the app |
| `find my budget file` | searches your files, lists matches, asks you to pick |
| `open the third one` | opens the chosen match |
| `search the web for flights to Mumbai` | browser search |
| `search for flights and open the third result` | multi-step task, planned and executed |
| `Jarvis, cancel` / `cancel` | stops the running task |
| `volume 40`, `mute`, `scroll down` | system control, offline |
| `take a screenshot` | asks for confirmation, then captures |
| `what is the exchange rate` | Gemini conversation |
| `Check my JARVIS` | self-diagnostics |
| `Show task history` | recent tasks and their outcome |
| `Turn on low resource mode` | fewer orb particles, lower CPU |
| `exit jarvis` | speaks goodbye and exits |

**Emergency stop:** `Ctrl + Alt + J` at any time. It releases held
keyboard/mouse input and does not need Gemini to be online.

---

## 6. Settings

`Settings` writes `config.json`:

- **Gemini** — enable/disable, API key, model. The key is stored in
  `%USERPROFILE%\.jarvis\gemini_key.txt` (0600) rather than in `config.json`.
- **Tools** — tick exactly which automation tools JARVIS may use, or use
  *Recommended set only*. Unticked tools are refused even if Gemini asks.
- **Wake word / speech / voice** — as in Phase 1.
- **Startup / Interface** — launch at Windows start, low-resource mode, compact
  window.

The current verified Gemini models are `gemini-3.8-flash` (text/tools) and
`gemini-3.8-live` (voice). `gemini-2.0-flash` and friends are shut down and are
rejected with a clear message.

---

## 7. Packaging (Phase 5)

```powershell
cd JARVIS
powershell -ExecutionPolicy Bypass -File build.ps1
powershell -ExecutionPolicy Bypass -File build.ps1 -WithBrowser
powershell -ExecutionPolicy Bypass -File build.ps1 -SkipTests
```

`build.ps1` creates a clean venv, installs requirements, runs the tests, builds
with `JARVIS.spec` (onedir, hidden imports, no console window) and zips
`dist/JARVIS` into `JARVIS-Windows.zip` together with `README.txt`.

**Measured size is reported by the script** (`JARVIS.exe`, runtime folder,
zip). The 50–100 MB target applies to the *download*; the runtime folder is
larger because `onnxruntime` (wake word) and PySide6 are unavoidable. Playwright's
Chromium is deliberately **not** bundled — run `playwright install chromium`
once on the target PC if you want browser automation.

Uninstall:

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1 -AppDir "C:\Program Files\JARVIS"
# add -Purge to also delete history, screenshots, photos and the stored key
```

GitHub Actions runs the same build on `windows-latest` and uploads the artifact
(`.github/workflows/jarvis-windows.yml`).

---

## 8. Tests

```powershell
python -m pytest tests -q        # 255 passed, 1 skipped
```

| File | Covers |
| --- | --- |
| `test_brain.py` | command matching (Phase 1) |
| `test_actions.py` | action engine, permissions, disambiguation |
| `test_config_and_voice.py` | config validation, voice plumbing |
| `test_router.py` | new task commands, hybrid routing |
| `test_gemini.py` | keys, models, errors, planning, tool loop, schema drift |
| `test_desktop.py` | file ranking, index, controller, registry gating |
| `test_browser.py` | provider mapping, tab state, error paths |
| `test_orb.py` | palettes, particle maths, transitions |
| `test_planner.py` | chaining, validation, cancellation, history |
| `test_integration.py` | Router + planner + registry + Phase 1 engine together |

Everything that needs Windows, a GUI, a browser or a camera is either
parameterised or skipped: the suite runs green on Linux CI.

---

## 9. Honest status of the Windows build

This repository was developed and tested on **Linux**. PyInstaller cannot produce
a Windows executable here, so:

- **No `JARVIS.exe` exists in this repository and it has never been executed.**
- `JARVIS.spec`, `build.ps1`, `uninstall.ps1` and the CI workflow are written and
  reviewed, but unverified on a real Windows machine.
- Everything *below* the OS layer (routing, planning, tools, ranking, orb maths,
  diagnostics, config, tests) is implemented and unit-tested here.
- PySide6, Playwright, pyautogui, pycaw, camera and window-management code paths
  are **not executed** on this host; they are guarded and documented, and their
  pure logic is tested where possible.

Before shipping: run `build.ps1` on Windows 11 x64, confirm the EXE starts,
complete the first-run wizard, and report the measured size.

---

## 10. Safety rules

- no `eval`/`exec`, no arbitrary shell commands from model output
- every tool call is validated before execution
- confirmation before deleting files, sending messages, uploading, sharing
  personal data, purchasing or changing system settings
- the emergency stop never depends on Gemini being online
- UAC, Windows Defender and app permission prompts are never bypassed
- the API key lives outside the app folder in the user profile and is never logged

---

## 11. Deliberately not included

Bundled local LLMs, multiple AI providers, per-command computer vision,
continuous camera streaming, a heavy 3D engine, a plugin marketplace,
unrestricted file deletion, elevated privileges for normal operations,
multiple background agents, and WhatsApp automation. Each was considered and
postponed to keep the app small, auditable and safe.
