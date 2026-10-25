# JARVIS — requirements checklist

Master status table. **Verified here** means it runs and is covered by the test
suite on this (Linux) host. **Windows-only** means the code path needs Windows,
a GUI, a browser or a camera and has **not** been executed on this host.

Legend: ✅ implemented & tested · 🟡 implemented, unexecuted here · ⬜ not done · 🚫 deliberately excluded

## Phase 1 — core app and wake word

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Entry point loads/validates config, merges defaults | ✅ | `test_config_and_voice.py` |
| 2 | Two-stage listening: STANDBY/ACTIVE | ✅ | `voice.py`, `test_config_and_voice.py` |
| 3 | Local wake word (`Hey Jarvis`, `.onnx`) | ✅ | `voice.py` |
| 4 | Wake word never sends audio to the cloud while idle | ✅ | `MicStream` + `Vad` in standby |
| 5 | Speech → text: Google Web Speech / Whisper / Vosk | ✅ | `SpeechRecognizer` |
| 6 | Text → speech offline (SAPI5) | ✅ | `Speaker` |
| 7 | 27 local commands + Hinglish/Devanagari matching | ✅ | `test_brain.py` |
| 8 | File-search disambiguation (by number or name) | ✅ | `test_actions.py` |
| 9 | Permission rules + confirmation gating | ✅ | `test_actions.py` |
| 10 | Emergency stop `Ctrl+Alt+J`, releases input | ✅ | `GlobalHotkey`, `test_actions.py` |
| 11 | PySide6 window + system tray | ✅ | `ui.py` (unrendered here) |
| 12 | No API keys committed; `.env` ignored | ✅ | `.gitignore`, `.env.example` |

## Phase 2 — Gemini AI and voice conversation

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 13 | Gemini client with key from env/.env/profile | ✅ | `test_gemini.py` |
| 14 | Current model defaults (`gemini-3.8-flash`, `gemini-3.8-live`) | ✅ | `test_gemini.py` |
| 15 | Deprecated models rejected with an actionable message | ✅ | `test_gemini.py` |
| 16 | Bounded retries, timeouts, rate-limit/network error taxonomy | ✅ | `test_gemini.py` |
| 17 | Persisted, bounded conversation history | ✅ | `test_gemini.py` |
| 18 | 33 tool schemas + registry handlers, zero drift | ✅ | `test_gemini.py::test_every_declared_tool_has_a_registry_handler` |
| 19 | Agent tool loop (max rounds) with failure feedback | ✅ | `test_gemini.py` |
| 20 | Hybrid router: local first, AI only when needed | ✅ | `test_router.py` |
| 21 | Live API voice mode (`LiveVoiceSession`) | 🟡 | written, never connected — needs a key |
| 22 | Cascade fallback when Live API is unavailable | ✅ | mic → STT → text → TTS |

## Phase 3 — Windows and browser automation

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 23 | Mouse / keyboard / window / app / file primitives | 🟡 | `desktop.py` (needs Windows) |
| 24 | File intelligence: ranking, index, skip dirs, caps | ✅ | `test_desktop.py` |
| 25 | Screen understanding (screenshot + optional AI review) | 🟡 | `take_screenshot` (needs Windows) |
| 26 | Camera capture, opt-in, on-demand only | 🟡 | `camera.py` (needs Windows) |
| 27 | Browser automation via Playwright, lazy start | 🟡 | `test_browser.py` (no browser here) |
| 28 | Multi-step task planning + command chaining | ✅ | `test_planner.py` |
| 29 | Universal cancel ("Jarvis, cancel") | ✅ | `test_planner.py`, `test_router.py` |
| 30 | Task history (persisted, bounded) | ✅ | `test_planner.py` |
| 31 | Tool validation before execution; confirmation gating | ✅ | `test_desktop.py` |

## Phase 4 — UI

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 32 | Particle orb with 5 states (standby/listening/processing/speaking/error) | 🟡 | `orb.py` maths ✅ `test_orb.py`; rendering unexecuted |
| 33 | Compact / full / tray modes | 🟡 | `OrbViewModel.compact/tray` ✅ maths tested |
| 34 | Low-resource mode (fewer particles) | ✅ | `test_orb.py::test_low_resource_frame_has_fewer_particles` |
| 35 | Original icon (runtime-drawn, no binary asset) | ✅ | `ui.build_icon()` |
| 36 | First-run wizard (mic, key, permissions, startup) | 🟡 | `ui.run_first_run_wizard` (needs Qt) |
| 37 | Task history and diagnostics dialogs, tray menu | 🟡 | `ui.py` (needs Qt) |

## Phase 5 — packaging

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 38 | `JARVIS.spec` onedir, hidden imports, no console | 🟡 | written, never built |
| 39 | `build.ps1` reproducible build + size report + zip | 🟡 | written, never run |
| 40 | `uninstall.ps1` (app, startup entry, shortcuts, optional purge) | 🟡 | written, never run |
| 41 | CI workflow on `windows-latest` (tests + artifact) | 🟡 | written, never run |
| 42 | `README.txt` for end users | ✅ | `JARVIS/README.txt` |
| 43 | Actual `JARVIS.exe` built and launched | ⬜ | **impossible on this host** — see README §9 |

## Explicitly excluded (agreed)

- bundled local LLM, multiple AI providers, per-command computer vision
- continuous camera streaming, heavy 3D engine, plugin marketplace
- unrestricted file deletion, elevated privileges for normal operations
- multiple background agents, WhatsApp automation
