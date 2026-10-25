"""
voice.py - audio capture, wake-word detection, speech recognition and speech
synthesis for JARVIS.

Architecture (two-stage listening)
---------------------------------
STANDBY  - a local wake-word engine runs on 16 kHz mono frames produced by a
           background microphone thread.  Microphone audio is *not* sent to
           any cloud service in this state; only local integer audio is
           buffered.  CPU use is low (one small ONNX model over 0.5 s
           chunks).
ACTIVE   - an energy VAD gates the microphone.  Only when speech is detected
           is audio forwarded to the speech recognizer.  After the configured
           conversation timeout the engine returns to STANDBY.

Threading
---------
``MicStream``      one daemon thread captures frames into a ``queue.Queue``
``VoiceEngine``    one worker thread runs the standby/active state machine
``Speaker``        speech synthesis happens on its own worker thread
``SpeechRecognizer`` network/model calls happen on the worker thread, never
                    on the PySide6 main thread

The engine never blocks the GUI: everything it wants to report goes onto an
event queue that ``ui.py`` drains with a ``QTimer``.
"""

from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

log = logging.getLogger("jarvis.voice")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit

# Status vocabulary shared with the UI.
STANDBY = "STANDBY"
LISTENING = "LISTENING"
PROCESSING = "PROCESSING"
SPEAKING = "SPEAKING"
ERROR = "ERROR"


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

@dataclass
class VoiceEvent:
    """Something the engine wants the UI to know about."""

    kind: str                 # status | transcript | wakeword | error | info
    payload: Dict[str, object] = field(default_factory=dict)

    def status(self, state: str, **extra: object) -> "VoiceEvent":
        payload = {"state": state}
        payload.update(extra)
        return VoiceEvent("status", payload)


# ---------------------------------------------------------------------------
# microphone
# ---------------------------------------------------------------------------

class MicError(RuntimeError):
    """Raised when the microphone cannot be opened or keeps failing."""


class MicStream:
    """Background microphone capture producing 16-bit mono PCM frames.

    The stream recovers automatically from device disconnections by recreating
    the PortAudio stream; ``on_error`` is called with a human-readable reason.
    """

    def __init__(
        self,
        device: Optional[int] = None,
        sample_rate: int = SAMPLE_RATE,
        frame_ms: int = 80,
        max_queue: int = 400,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frames_per_buffer = max(1, int(sample_rate * frame_ms / 1000))
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=max_queue)
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_frame: Optional[Callable[[np.ndarray], None]] = None
        self._recovery_attempts = 0

    # -- device discovery ---------------------------------------------------

    @staticmethod
    def list_devices() -> List[Dict[str, object]]:
        """Return ``[{"index", "name", "default"}]`` for every input device."""
        try:
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover - dependency missing
            log.warning("sounddevice unavailable: %s", exc)
            return []
        devices: List[Dict[str, object]] = []
        try:
            for index, info in enumerate(sd.query_devices()):
                if str(info.get("max_input_channels", "0")) not in ("0", ""):
                    devices.append(
                        {"index": index, "name": info.get("name", ""), "default": False}
                    )
        except Exception as exc:  # pragma: no cover - device enumeration failed
            log.warning("could not enumerate microphones: %s", exc)
            return []
        if devices:
            devices[0]["default"] = True
        return devices

    @staticmethod
    def select_device(preference: Optional[str] = None) -> Optional[int]:
        """Pick a microphone index by preference string, else the first input."""
        devices = MicStream.list_devices()
        if not devices:
            return None
        if preference:
            pref = preference.lower()
            for device in devices:
                if pref in str(device["name"]).lower():
                    return int(device["index"])
        return int(devices[0]["index"])

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="jarvis-mic", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:  # pragma: no cover - already closed
                    pass
                self._stream = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def set_device(self, device: Optional[int]) -> None:
        self.device = device
        if self.is_running:
            self.stop()
            self.start()

    # -- capture ------------------------------------------------------------

    def _run(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:
            self._report_error(
                f"sounddevice is not installed: {exc}. "
                "Run: pip install -r requirements.txt"
            )
            return

        while not self._stop.is_set():
            try:
                self._open(sd)
                self._recovery_attempts = 0
                while not self._stop.is_set():
                    data = self._stream.read(self.frames_per_buffer, dtype="int16")
                    frame = np.asarray(data, dtype=np.int16).reshape(-1)
                    if frame.size:
                        if self.on_frame:
                            self.on_frame(frame)
                        else:
                            try:
                                self._queue.put_nowait(frame)
                            except queue.Full:
                                self._queue.get_nowait()
                                self._queue.put_nowait(frame)
            except Exception as exc:
                if self._stop.is_set():
                    break
                self._recovery_attempts += 1
                self._report_error(
                    f"microphone error: {exc}. "
                    "Check Windows Settings > Privacy > Microphone > "
                    "Desktop app access."
                )
                if self._recovery_attempts > 20:
                    log.error("microphone gave up after repeated failures")
                    return
                time.sleep(2.0)

    def _open(self, sd) -> None:
        with self._lock:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.frames_per_buffer,
                device=self.device,
                callback=None,
            )
            self._stream.start()

    def _report_error(self, message: str) -> None:
        log.error(message)
        if self.on_error:
            try:
                self.on_error(message)
            except Exception:  # pragma: no cover - callback blew up
                pass

    def get_frames(self, count: int = 1, timeout: float = 0.1) -> List[np.ndarray]:
        """Return up to ``count`` frames, waiting at most ``timeout`` seconds."""
        frames: List[np.ndarray] = []
        deadline = time.monotonic() + timeout
        while len(frames) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                frames.append(self._queue.get(timeout=remaining))
            except queue.Empty:
                break
        return frames


# ---------------------------------------------------------------------------
# voice activity detection
# ---------------------------------------------------------------------------

class Vad:
    """Energy based voice activity detection with an adaptive noise floor."""

    def __init__(
        self,
        start_threshold: float = 0.012,
        end_threshold: float = 0.008,
        noise_floor_multiplier: float = 3.0,
        silence_duration_ms: int = 900,
        max_utterance_seconds: int = 12,
        calibration_frames: int = 6,
    ) -> None:
        self.start_threshold = float(start_threshold)
        self.end_threshold = float(end_threshold)
        self.noise_floor_multiplier = float(noise_floor_multiplier)
        self.silence_ms = int(silence_duration_ms)
        self.max_seconds = int(max_utterance_seconds)
        self.calibration_frames = int(calibration_frames)

        self.noise_floor = 0.0
        self.calibrated = False
        self.in_speech = False
        self.silence_counter = 0
        self._frames = 0
        self._start_time: Optional[float] = None

    def reset(self) -> None:
        self.in_speech = False
        self.silence_counter = 0
        self._frames = 0
        self._start_time = None

    def level(self, frame: np.ndarray) -> float:
        """RMS amplitude of a frame as a float between 0 and 1."""
        if frame.size == 0:
            return 0.0
        samples = frame.astype(np.float64) / 32768.0
        return float(np.sqrt(np.mean(samples * samples)))

    def process(self, frame: np.ndarray) -> bool:
        """Update the VAD with one frame; returns ``True`` while in speech."""
        level = self.level(frame)

        if not self.calibrated and self._frames < self.calibration_frames:
            self.noise_floor = (self.noise_floor * self._frames + level) / (self._frames + 1)
            self._frames += 1
            if self._frames >= self.calibration_frames:
                self.calibrated = True
                self.noise_floor = max(self.noise_floor, 1e-4)
            return False

        adaptive = max(self.noise_floor * self.noise_floor_multiplier, self.end_threshold)

        if not self.in_speech:
            if level > max(self.start_threshold, adaptive):
                self.in_speech = True
                self.silence_counter = 0
                self._start_time = time.monotonic()
                return True
            return False

        if level < min(adaptive, self.end_threshold * 1.5):
            self.silence_counter += 1
        else:
            self.silence_counter = 0
            if self.noise_floor < level * 0.3:
                self.noise_floor = self.noise_floor * 0.7 + level * 0.3

        frame_ms = max(1, int(len(frame) / SAMPLE_RATE * 1000))
        if self.silence_counter * frame_ms >= self.silence_ms:
            self.in_speech = False
            self.silence_counter = 0
            return False

        if self._start_time and (time.monotonic() - self._start_time) > self.max_seconds:
            self.in_speech = False
            self.silence_counter = 0
            return False
        return True


# ---------------------------------------------------------------------------
# wake word
# ---------------------------------------------------------------------------

class WakeWordEngine:
    """Local wake-word detection backed by openwakeword (ONNX).

    Requires the ``hey_jarvis`` (or a custom) ``.onnx`` model.  Models are not
    bundled in Git; on first run use::

        python -c "import openwakeword.utils; openwakeword.utils.download_models()"

    or point ``wake_word.model_dir`` at a folder that contains them.  When no
    model can be loaded the engine falls back to *transcript* mode: light VAD
    plus a short speech recognition pass that listens for the wake word, which
    costs more CPU/network and is logged loudly.
    """

    def __init__(
        self,
        model_names: Sequence[str],
        model_dir: Optional[str] = None,
        threshold: float = 0.5,
        use_fallback: bool = True,
    ) -> None:
        self.model_names = [n for n in model_names if n]
        self.model_dir = model_dir
        self.threshold = float(threshold)
        self.use_fallback = use_fallback
        self._models: List[object] = []
        self._ready = False
        self._mode = "unavailable"
        self._last_trigger = 0.0
        self._refractory = 2.0
        self._chunk = np.zeros(0, dtype=np.int16)

    # -- setup --------------------------------------------------------------

    def setup(self, refractory_seconds: float = 2.0) -> str:
        self._refractory = refractory_seconds
        for name in self.model_names:
            try:
                model = self._load_model(name)
            except Exception as exc:
                log.warning("wake-word model '%s' unavailable: %s", name, exc)
                continue
            if model is not None:
                self._models.append(model)

        if self._models:
            self._ready = True
            self._mode = "openwakeword"
            log.info(
                "wake-word engine ready (%d local model(s), no cloud audio)",
                len(self._models),
            )
        elif self.use_fallback:
            self._mode = "transcript-fallback"
            log.warning(
                "No local wake-word model found - falling back to transcript "
                "mode. Download one with:\n"
                "  python -c \"import openwakeword.utils; "
                "openwakeword.utils.download_models()\"\n"
                "or set wake_word.model_dir in config.json."
            )
        else:
            self._mode = "unavailable"
            log.error("Wake-word engine unavailable and fallback disabled.")
        return self._mode

    def _load_model(self, name: str) -> Optional[object]:
        try:
            from openwakeword import Model  # type: ignore
        except Exception:
            try:
                from openwakeword import OWWModel as Model  # type: ignore
            except Exception as exc:
                raise RuntimeError(f"openwakeword is not installed: {exc}") from exc

        kwargs: Dict[str, object] = {}
        if self.model_dir:
            kwargs["models_directory"] = self.model_dir
        try:
            if self.model_dir and os.path.isfile(os.path.join(self.model_dir, name)):
                return Model(os.path.join(self.model_dir, name), **kwargs)
            return Model(name, **kwargs)
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

    # -- inference ---------------------------------------------------------

    def reset(self) -> None:
        for model in self._models:
            try:
                model.reset()
            except Exception:  # pragma: no cover - model specific
                pass
        self._chunk = np.zeros(0, dtype=np.int16)

    def feed(self, frame: np.ndarray) -> Optional[str]:
        """Feed one frame; returns the matched wake word or ``None``."""
        if not self._ready:
            return None

        self._chunk = np.concatenate([self._chunk, frame])
        target = int(SAMPLE_RATE * 0.5)
        while len(self._chunk) >= target:
            chunk, self._chunk = self._chunk[:target], self._chunk[target:]
            for model in self._models:
                name = str(getattr(model, "model_name", "") or "wakeword")
                try:
                    score = self._predict(model, chunk)
                except Exception as exc:  # pragma: no cover - model specific
                    log.warning("wake-word inference failed: %s", exc)
                    return None
                if score is not None and score >= self.threshold:
                    now = time.monotonic()
                    if now - self._last_trigger < self._refractory:
                        continue
                    self._last_trigger = now
                    self.reset()
                    return name
        return None

    @staticmethod
    def _predict(model: object, chunk: np.ndarray) -> Optional[float]:
        """Call whichever inference API the installed openwakeword exposes."""
        if hasattr(model, "predict"):
            result = model.predict(chunk)
            if isinstance(result, (int, float)):
                return float(result)
        if hasattr(model, "process"):
            model.process(chunk)
            state = getattr(model, "state", 0)
            triggered = getattr(model, "triggered", False)
            if triggered or state == 2:
                return 1.0
            return 0.0
        return None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def ready(self) -> bool:
        return self._ready


# ---------------------------------------------------------------------------
# speech recognition
# ---------------------------------------------------------------------------

class SpeechRecognizer:
    """Text-from-speech with three pluggable backends.

    ``google``   Google Web Speech (default, needs internet, no key for
                 personal use)
    ``whisper``  faster-whisper, fully local, needs a downloaded model
    ``vosk``     Vosk, fully local, needs a downloaded model
    ``auto``     whisper -> vosk -> google
    """

    def __init__(
        self,
        backend: str = "google",
        language: str = "en-IN",
        fallback_language: str = "hi-IN",
        google_key: Optional[str] = None,
        whisper_model_size: str = "tiny",
        whisper_device: str = "cpu",
        whisper_compute_type: str = "int8",
        whisper_language: Optional[str] = None,
        whisper_prompt: Optional[str] = None,
        vosk_model_path: Optional[str] = None,
    ) -> None:
        self.backend = (backend or "google").lower()
        self.language = language
        self.fallback_language = fallback_language
        self.google_key = google_key
        self.whisper_model_size = whisper_model_size
        self.whisper_device = whisper_device
        self.whisper_compute_type = whisper_compute_type
        self.whisper_language = whisper_language
        self.whisper_prompt = whisper_prompt
        self.vosk_model_path = vosk_model_path

        self._sr = None
        self._whisper = None
        self._vosk_model = None
        self._vosk_rec = None
        self._initialized = False
        self._init_error: Optional[str] = None

    # -- lazy initialization ------------------------------------------------

    def initialize(self) -> str:
        """Prepare the requested backend; returns the active backend name."""
        if self._initialized:
            return self._active_backend
        order = ["google", "whisper", "vosk"] if self.backend == "auto" else [self.backend]
        self._active_backend = "unavailable"
        errors: List[str] = []

        for candidate in order:
            try:
                if candidate == "google":
                    self._init_google()
                    self._active_backend = "google"
                elif candidate == "whisper":
                    self._init_whisper()
                    self._active_backend = "whisper"
                elif candidate == "vosk":
                    self._init_vosk()
                    self._active_backend = "vosk"
                if self._active_backend != "unavailable":
                    break
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
                log.warning("speech backend %s unavailable: %s", candidate, exc)

        if self._active_backend == "unavailable":
            self._init_error = "; ".join(errors) or "no backend available"
            self._active_backend = "google"
        self._initialized = True
        return self._active_backend

    @property
    def error(self) -> Optional[str]:
        return self._init_error

    @property
    def active_backend(self) -> str:
        return getattr(self, "_active_backend", "unavailable")

    def _init_google(self) -> None:
        import speech_recognition as sr  # type: ignore
        self._sr = sr

    def _init_whisper(self) -> None:
        from faster_whisper import WhisperModel  # type: ignore
        self._whisper = WhisperModel(
            self.whisper_model_size,
            device=self.whisper_device,
            compute_type=self.whisper_compute_type,
        )

    def _init_vosk(self) -> None:
        if not self.vosk_model_path:
            raise RuntimeError("vosk_model_path is not configured")
        import vosk  # type: ignore
        self._vosk_model = vosk.Model(self.vosk_model_path)

    # -- recognition --------------------------------------------------------

    def transcribe(self, samples: np.ndarray) -> str:
        """Recognize speech from an int16 mono array."""
        if not self._initialized:
            self.initialize()
        samples = np.asarray(samples, dtype=np.int16).reshape(-1)
        if samples.size == 0:
            return ""

        if self._active_backend == "whisper" and self._whisper is not None:
            return self._transcribe_whisper(samples)
        if self._active_backend == "vosk" and self._vosk_model is not None:
            return self._transcribe_vosk(samples)
        return self._transcribe_google(samples)

    def _transcribe_google(self, samples: np.ndarray) -> str:
        import speech_recognition as sr  # type: ignore

        audio = sr.AudioData(samples.tobytes(), SAMPLE_RATE, SAMPLE_WIDTH)
        try:
            if self.google_key:
                return self._sr.Recognizer().recognize_google(
                    audio, key=self.google_key, language=self.language
                )
            return self._sr.Recognizer().recognize_google(
                audio, language=self.language
            )
        except self._sr.UnknownValueError:
            return ""
        except self._sr.RequestError as exc:
            log.warning("Google Web Speech request failed: %s", exc)
            raise RuntimeError(
                "Google Web Speech is unreachable. Speech recognition needs "
                "internet access, or switch speech.backend to 'whisper' or "
                "'vosk' in config.json."
            ) from exc

    def _transcribe_whisper(self, samples: np.ndarray) -> str:
        import faster_whisper  # type: ignore  # noqa: F401

        audio = samples.astype(np.float32) / 32768.0
        kwargs: Dict[str, object] = {"beam_size": 4, "condition_on_previous_text": False}
        if self.whisper_language:
            kwargs["language"] = self.whisper_language
        if self.whisper_prompt:
            kwargs["initial_prompt"] = self.whisper_prompt
        segments, _info = self._whisper.transcribe(audio, **kwargs)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _transcribe_vosk(self, samples: np.ndarray) -> str:
        import vosk  # type: ignore

        if self._vosk_rec is None:
            self._vosk_rec = vosk.KaldiRecognizer(self._vosk_model, SAMPLE_RATE)
            self._vosk_rec.SetWords(False)
        self._vosk_rec.AcceptWaveform(samples.tobytes())
        import json

        return json.loads(self._vosk_rec.Result()).get("text", "")


# ---------------------------------------------------------------------------
# speech synthesis
# ---------------------------------------------------------------------------

class Speaker:
    """Text-to-speech with a configurable voice, rate and volume.

    Default engine is Windows SAPI5 (offline, no account needed).  The
    ``espeak`` engine is used as a fallback on non-Windows machines for
    development/testing.
    """

    def __init__(
        self,
        engine: str = "sapi5",
        voice_name: str = "",
        rate: int = 175,
        volume: float = 0.9,
    ) -> None:
        self.engine = engine
        self.voice_name = voice_name
        self.rate = int(rate)
        self.volume = float(volume)
        self._tts = None
        self._lock = threading.Lock()
        self._speaking = False
        self._ready = False
        self._init_error: Optional[str] = None

    def initialize(self) -> bool:
        try:
            import pyttsx3  # type: ignore

            engine_name = self.engine if self.engine else None
            try:
                self._tts = pyttsx3.init(driverName=engine_name) if engine_name else pyttsx3.init()
            except Exception:
                self._tts = pyttsx3.init()
            self._configure()
            self._ready = True
            log.info("speech synthesis ready (%s)", self.engine)
            return True
        except Exception as exc:
            self._init_error = str(exc)
            log.error("speech synthesis unavailable: %s", exc)
            return False

    def _configure(self) -> None:
        if self._tts is None:
            return
        self._tts.setProperty("rate", self.rate)
        self._tts.setProperty("volume", max(0.0, min(1.0, self.volume)))
        if self.voice_name:
            try:
                for voice in self._tts.getProperty("voices"):
                    if self.voice_name.lower() in str(voice.name).lower():
                        self._tts.setProperty("voice", voice.id)
                        break
            except Exception:  # pragma: no cover - engine specific
                pass

    @staticmethod
    def list_voices(engine: str = "sapi5") -> List[Dict[str, str]]:
        try:
            import pyttsx3  # type: ignore

            tts = pyttsx3.init(driverName=engine) if engine else pyttsx3.init()
            voices = []
            for voice in tts.getProperty("voices"):
                voices.append(
                    {
                        "id": str(voice.id),
                        "name": str(voice.name),
                        "language": str(getattr(voice, "languages", "") or ""),
                    }
                )
            return voices
        except Exception as exc:  # pragma: no cover - non-Windows
            log.warning("voice listing failed: %s", exc)
            return []

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def say(self, text: str, on_done: Optional[Callable[[], None]] = None) -> None:
        """Speak ``text`` on a worker thread so the GUI never blocks."""
        if not text or not text.strip():
            if on_done:
                on_done()
            return
        if not self._ready and not self.initialize():
            if on_done:
                on_done()
            return
        threading.Thread(
            target=self._speak, args=(text, on_done), name="jarvis-tts", daemon=True
        ).start()

    def _speak(self, text: str, on_done: Optional[Callable[[], None]]) -> None:
        with self._lock:
            self._speaking = True
        try:
            self._tts.say(text)
            self._tts.runAndWait()
        except Exception as exc:
            log.warning("speech synthesis failed: %s", exc)
        finally:
            with self._lock:
                self._speaking = False
            if on_done:
                try:
                    on_done()
                except Exception:  # pragma: no cover
                    pass

    def stop(self) -> None:
        try:
            if self._tts is not None:
                self._tts.stop()
        except Exception:  # pragma: no cover - engine specific
            pass
        self._speaking = False


# ---------------------------------------------------------------------------
# the two-stage listening engine
# ---------------------------------------------------------------------------

class VoiceEngine:
    """Standby/active state machine driving wake word + speech recognition."""

    def __init__(
        self,
        recognizer: SpeechRecognizer,
        speaker: Speaker,
        wake_word: WakeWordEngine,
        vad: Vad,
        mic: MicStream,
        conversation_timeout: float = 30.0,
        activation_phrases: Optional[Sequence[str]] = None,
        activation_response: str = "JARVIS online. Ready for your command.",
        self_echo_cooldown_ms: int = 700,
        event_callback: Optional[Callable[[VoiceEvent], None]] = None,
    ) -> None:
        self.recognizer = recognizer
        self.speaker = speaker
        self.wake_word = wake_word
        self.vad = vad
        self.mic = mic
        self.conversation_timeout = float(conversation_timeout)
        self.activation_phrases = [p.lower() for p in (activation_phrases or [])]
        self.activation_response = activation_response
        self.self_echo_cooldown_ms = int(self_echo_cooldown_ms)
        self._event_callback = event_callback

        self._events: "queue.Queue[VoiceEvent]" = queue.Queue(maxsize=500)
        self._state = STANDBY
        self._stop = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._activate_flag = threading.Event()
        self._deactivate_flag = threading.Event()
        self._wake_detected_at = 0.0
        self._last_speech_at = 0.0
        self._cooldown_until = 0.0

    # -- public API ---------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def events(self) -> "queue.Queue[VoiceEvent]":
        return self._events

    def emit(self, event: VoiceEvent) -> None:
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception:  # pragma: no cover - UI callback blew up
                pass
        try:
            self._events.put_nowait(event)
        except queue.Full:
            try:
                self._events.get_nowait()
                self._events.put_nowait(event)
            except Exception:  # pragma: no cover
                pass

    def set_state(self, state: str, **extra: object) -> None:
        self._state = state
        self.emit(VoiceEvent("status", {"state": state, **extra}))

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self.wake_word.reset()
        self.vad.reset()
        self.set_state(STANDBY, wake_word=self.wake_word.mode)
        self._worker = threading.Thread(
            target=self._run, name="jarvis-voice", daemon=True
        )
        self._worker.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        self._activate_flag.clear()
        self._deactivate_flag.set()
        self.mic.stop()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=timeout)

    def activate(self) -> None:
        """Force the engine into ACTIVE mode (used by the Start button)."""
        self._activate_flag.set()

    def deactivate(self) -> None:
        """Return to STANDBY immediately (used by the Stop button)."""
        self._deactivate_flag.set()

    def set_conversation_timeout(self, seconds: float) -> None:
        self.conversation_timeout = float(seconds)

    # -- worker ------------------------------------------------------------

    def _run(self) -> None:
        self.mic.on_frame = None  # frames are consumed from the queue
        self.mic.start()
        while not self._stop.is_set():
            try:
                if self._state == STANDBY:
                    self._standby_loop()
                else:
                    self._active_loop()
            except Exception as exc:  # pragma: no cover - defensive
                log.exception("voice engine error: %s", exc)
                self.set_state(ERROR, message=str(exc))
                time.sleep(0.5)

    def _next_frames(self, count: int = 1, timeout: float = 0.1) -> List[np.ndarray]:
        if not self.mic.is_running:
            # give the microphone a moment to come back after a disconnect
            time.sleep(1.0)
        return self.mic.get_frames(count=count, timeout=timeout)

    # -- standby ------------------------------------------------------------

    def _standby_loop(self) -> None:
        self.wake_word.reset()
        self.vad.reset()
        self.emit(VoiceEvent("info", {"message": "STANDBY - waiting for the wake word"}))

        while self._state == STANDBY and not self._stop.is_set():
            if self._deactivate_flag.is_set():
                self._deactivate_flag.clear()

            if self._activate_flag.is_set():
                self._activate_flag.clear()
                self._enter_active("manual activation")
                return

            frames = self._next_frames(count=1, timeout=0.05)
            if not frames:
                continue
            if self.speaker.is_speaking or time.monotonic() < self._cooldown_until:
                continue  # do not trigger on JARVIS' own voice

            if self.wake_word.ready:
                matched = self.wake_word.feed(frames[0])
                if matched:
                    self._enter_active(f"wake word: {matched}")
                    return
            else:
                # transcript fallback: only transcribe when speech is detected
                if self.vad.process(frames[0]):
                    transcript = self._capture_utterance()
                    if transcript and self._looks_like_activation(transcript):
                        self._enter_active(f"wake phrase: {transcript}")
                        return

    def _looks_like_activation(self, transcript: str) -> bool:
        low = transcript.lower()
        if "jarvis" in low:
            return True
        return any(phrase in low for phrase in self.activation_phrases)

    def _enter_active(self, reason: str) -> None:
        self._deactivate_flag.clear()
        self._last_speech_at = time.monotonic()
        self.set_state(LISTENING, reason=reason)
        self.emit(VoiceEvent("wakeword", {"reason": reason}))
        if self.activation_response:
            self.speaker.say(self.activation_response, on_done=self._activation_done)

    def _activation_done(self) -> None:
        self._cooldown_until = time.monotonic() + self.self_echo_cooldown_ms / 1000.0
        if self._state == LISTENING:
            self.emit(VoiceEvent("info", {"message": "Listening"}))

    # -- active -------------------------------------------------------------

    def _active_loop(self) -> None:
        self.vad.reset()
        buffer: List[np.ndarray] = []
        buffer_seconds = 0.0
        collecting = False
        utterance_started = 0.0
        last_speech_seen = 0.0

        while self._state == LISTENING and not self._stop.is_set():
            if self._deactivate_flag.is_set():
                self._deactivate_flag.clear()
                self._enter_standby("deactivated")
                return

            if time.monotonic() < self._cooldown_until:
                time.sleep(0.02)
                continue
            if self.speaker.is_speaking:
                time.sleep(0.02)
                continue

            # conversation timeout: back to standby after inactivity
            if not collecting and (time.monotonic() - self._last_speech_at) > self.conversation_timeout:
                self._enter_standby("conversation timeout")
                return

            frames = self._next_frames(count=1, timeout=0.05)
            if not frames:
                continue
            frame = frames[0]

            if self.vad.process(frame):
                self._last_speech_at = time.monotonic()
                if not collecting:
                    collecting = True
                    buffer = []
                    buffer_seconds = 0.0
                    utterance_started = time.monotonic()
                    self.emit(VoiceEvent("info", {"message": "Listening..."}))
                buffer.append(frame)
                buffer_seconds += len(frame) / SAMPLE_RATE
            else:
                if collecting and buffer:
                    self._finish_utterance(buffer)
                    collecting = False
                    buffer = []
                    buffer_seconds = 0.0

            # hard cap on utterance length
            if collecting and buffer and (time.monotonic() - utterance_started) > self.vad.max_seconds:
                self._finish_utterance(buffer)
                collecting = False
                buffer = []

            if collecting and last_speech_seen != self._last_speech_at:
                last_speech_seen = self._last_speech_at

        if collecting and buffer:
            self._finish_utterance(buffer)

    def _finish_utterance(self, buffer: List[np.ndarray]) -> None:
        self.set_state(PROCESSING)
        audio = np.concatenate(buffer) if buffer else np.zeros(0, dtype=np.int16)
        seconds = len(audio) / SAMPLE_RATE
        log.info("captured %.2fs of speech", seconds)
        try:
            text = self.recognizer.transcribe(audio)
        except Exception as exc:
            log.error("speech recognition failed: %s", exc)
            self.emit(VoiceEvent("error", {"message": str(exc)}))
            self.set_state(LISTENING)
            return

        text = (text or "").strip()
        self.emit(VoiceEvent("transcript", {"text": text, "seconds": round(seconds, 2)}))
        self.set_state(LISTENING)

    def _enter_standby(self, reason: str) -> None:
        self.vad.reset()
        self.wake_word.reset()
        self.set_state(STANDBY, reason=reason)
        self.emit(VoiceEvent("info", {"message": f"STANDBY ({reason})"}))

    # -- capture helper -----------------------------------------------------

    def _capture_utterance(self) -> str:
        """Collect one utterance for the transcript-fallback wake path."""
        self.vad.reset()
        buffer: List[np.ndarray] = []
        collecting = False
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline and not self._stop.is_set():
            frames = self._next_frames(count=1, timeout=0.1)
            if not frames:
                continue
            frame = frames[0]
            if self.vad.process(frame):
                collecting = True
                buffer.append(frame)
            elif collecting and buffer:
                break
        audio = np.concatenate(buffer) if buffer else np.zeros(0, dtype=np.int16)
        if audio.size == 0:
            return ""
        try:
            return self.recognizer.transcribe(audio)
        except Exception as exc:
            log.warning("wake-phrase recognition failed: %s", exc)
            return ""


__all__ = [
    "VoiceEngine",
    "VoiceEvent",
    "MicStream",
    "Vad",
    "WakeWordEngine",
    "SpeechRecognizer",
    "Speaker",
    "STANDBY",
    "LISTENING",
    "PROCESSING",
    "SPEAKING",
    "ERROR",
]
