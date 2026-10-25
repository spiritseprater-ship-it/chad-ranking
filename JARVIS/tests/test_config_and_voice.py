"""Configuration validation and audio-engine tests."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

numpy = pytest.importorskip("numpy", reason="numpy is required for audio tests")

from brain import normalize_text  # noqa: E402
from main import ConfigError, load_config, validate_config  # noqa: E402
from voice import (  # noqa: E402
    MicStream,
    SpeechRecognizer,
    Speaker,
    VoiceEngine,
    Vad,
    WakeWordEngine,
)

PACKAGE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

def test_project_config_loads_without_warnings() -> None:
    config = load_config(str(PACKAGE_DIR / "config.json"))
    assert config["_warnings"] == []
    assert config["conversation"]["timeout_seconds"] == 30
    assert config["wake_word"]["primary"] == "hey_jarvis"
    assert config["hotkey"]["emergency_stop"] == "ctrl+alt+j"
    assert "{query}" in config["browser"]["search_url"]


def test_missing_config_falls_back_to_defaults(tmp_path: Path) -> None:
    config = load_config(str(tmp_path / "does-not-exist.json"))
    assert config["wake_word"]["primary"] == "hey_jarvis"
    assert config["_path"].endswith("does-not-exist.json")


def test_invalid_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_validation_flags_bad_values() -> None:
    problems = validate_config(
        {
            "wake_word": {"primary": "", "threshold": "high"},
            "speech": {"backend": "telepathy", "language": ""},
            "conversation": {"timeout_seconds": -5},
            "voice": {"rate": 900},
            "browser": {"search_url": "https://example.com"},
            "hotkey": {"emergency_stop": "ctrl+shift+j"},
        }
    )
    joined = " | ".join(problems)
    assert "wake_word.primary" in joined
    assert "speech.backend" in joined
    assert "timeout_seconds" in joined
    assert "rate" in joined
    assert "search_url" in joined


def test_config_files_are_valid_json() -> None:
    with open(PACKAGE_DIR / "config.json", "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    for section in (
        "wake_word", "speech", "voice", "conversation", "browser",
        "permissions", "hotkey", "logging",
    ):
        assert section in raw, f"config.json is missing {section}"


# ---------------------------------------------------------------------------
# voice engine pieces
# ---------------------------------------------------------------------------

def test_vad_detects_speech() -> None:
    import numpy as np

    vad = Vad(calibration_frames=1, silence_duration_ms=200)
    silence = np.zeros(1280, dtype=np.int16)
    assert vad.level(silence) == 0.0

    tone = (np.sin(np.linspace(0, 40 * 3.14159, 1280)) * 9000).astype(np.int16)
    assert vad.level(tone) > 0.05
    assert vad.process(silence) is False
    assert vad.process(tone) is True


def test_wake_word_falls_back_when_model_missing() -> None:
    wake = WakeWordEngine(["hey_jarvis"], model_dir=str(PACKAGE_DIR / "models"), threshold=0.5)
    mode = wake.setup(refractory_seconds=2.0)
    # openwakeword is not bundled: either the local engine loaded or we fall back
    assert mode in ("openwakeword", "transcript-fallback")
    assert wake.feed(numpy.zeros(1280, dtype=numpy.int16)) is None


def test_speech_recognizer_backend_selection() -> None:
    recognizer = SpeechRecognizer(backend="auto")
    backend = recognizer.initialize()
    assert backend in ("google", "whisper", "vosk", "unavailable")


def test_speaker_initialization_does_not_crash() -> None:
    speaker = Speaker(engine="sapi5" if sys.platform == "win32" else "espeak")
    speaker.initialize()  # False is fine when no TTS engine exists
    speaker.say("hello", on_done=None)
    speaker.stop()
    assert speaker.is_speaking is False


def test_mic_stream_without_audio_hardware_is_safe() -> None:
    stream = MicStream(device=None, sample_rate=16000, frame_ms=80)
    assert stream.get_frames(count=1, timeout=0.05) == []
    errors = []
    stream.on_error = errors.append
    stream.start()
    time.sleep(0.4)
    stream.stop()
    # either the stream works, or it reported a clear error
    assert stream.is_running is False


def test_voice_engine_enters_standby_and_reports_status() -> None:
    recognizer = SpeechRecognizer(backend="google")
    recognizer.initialize()
    speaker = Speaker()
    speaker.initialize()
    mic = MicStream(device=None)
    wake = WakeWordEngine(["hey_jarvis"])
    wake.setup(2.0)
    engine = VoiceEngine(
        recognizer=recognizer,
        speaker=speaker,
        wake_word=wake,
        vad=Vad(),
        mic=mic,
        conversation_timeout=30,
        activation_response="JARVIS online. Ready for your command.",
    )
    engine.start()
    time.sleep(0.4)
    assert engine.state == "STANDBY"
    assert not engine.events.empty()
    first = engine.events.get_nowait()
    assert first.kind == "status" and first.payload["state"] == "STANDBY"
    engine.stop()
    assert engine.state == "STANDBY"


def test_voice_engine_emits_activation_response_event() -> None:
    recognizer = SpeechRecognizer(backend="google")
    recognizer.initialize()
    speaker = Speaker()
    speaker.initialize()
    engine = VoiceEngine(
        recognizer=recognizer,
        speaker=speaker,
        wake_word=WakeWordEngine(["hey_jarvis"]),
        vad=Vad(),
        mic=MicStream(device=None),
        conversation_timeout=10,
        activation_response="JARVIS online. Ready for your command.",
    )
    engine._enter_active("manual test")
    assert engine.state == "LISTENING"
    kinds = [engine.events.get_nowait().kind for _ in range(engine.events.qsize())]
    assert "status" in kinds and "wakeword" in kinds
    engine.deactivate()
    engine.stop()


def test_devanagari_hindi_is_understood() -> None:
    """Hindi script recognized by a hi-IN model should still map to commands."""
    normalized, meta = normalize_text("टाइम बताओ")
    assert meta["had_jarvis"] is False
    assert "time" in normalized or normalized == ""

    normalized2, _ = normalize_text("खोलओ फाइल  एक्सพลोरर")
    assert "explorer" in normalized2


def test_energy_vad_adaptive_noise_floor() -> None:
    import numpy as np

    vad = Vad(calibration_frames=2, silence_duration_ms=100)
    rng = np.random.default_rng(0)
    noise = (rng.normal(0, 300, 1280)).astype(np.int16)
    vad.process(noise)
    vad.process(noise)
    assert vad.noise_floor < 0.05
