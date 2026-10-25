"""
camera.py - optional local camera capture (OpenCV).

Camera access is strictly opt-in: ``camera_enabled`` must be true, the user must
have granted permission, and every capture is a single on-demand photo (no
continuous streaming or background capture).  A captured frame may be sent to
Gemini for review only if the user asked for that explicitly, and never to
third-party services.
"""

from __future__ import annotations

import base64
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger("jarvis.camera")

WINDOWS = sys.platform.startswith("win")


class CameraController:
    """On-demand photo capture from a local camera device."""

    def __init__(
        self,
        enabled: bool = False,
        save_dir: Optional[Path] = None,
        device_index: int = 0,
        permission_granted: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.save_dir = Path(save_dir) if save_dir else (Path.home() / "Pictures" / "JARVIS Photos")
        self.device_index = int(device_index)
        self.permission_granted = bool(permission_granted)
        self._camera = None
        self._last_frame = None

    # -- capability ---------------------------------------------------------

    def is_available(self) -> bool:
        if not self.enabled or not WINDOWS:
            return False
        if not self.permission_granted:
            return False
        try:
            import cv2  # type: ignore

            return hasattr(cv2, "VideoCapture")
        except ImportError:
            log.info("OpenCV (opencv-python) is not installed")
            return False

    def status_text(self) -> str:
        if not self.enabled:
            return "Camera is switched off."
        if not self.permission_granted:
            return "Camera permission has not been granted yet."
        if not WINDOWS:
            return "Camera capture currently requires Windows."
        if not self.is_available():
            return "OpenCV is not installed, so the camera cannot be used."
        return "Camera is ready (capture only, no streaming)."

    # -- capture ------------------------------------------------------------

    def _open_camera(self):
        if self._camera is not None:
            return self._camera
        try:
            import cv2  # type: ignore

            capture = cv2.VideoCapture(self.device_index)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self._camera = capture
            return capture
        except Exception as exc:
            log.error("could not open camera: %s", exc)
            return None

    def take_photo(self, label: Optional[str] = None, timeout: float = 6.0) -> Tuple[bool, str, Optional[Path]]:
        """Capture one photo and save it to the JARVIS photo directory."""
        if not self.enabled:
            return False, "Camera is switched off. Turn it on in Settings to use it.", None
        if not self.permission_granted:
            return False, "Camera permission has not been granted yet.", None
        if not self.is_available():
            return False, self.status_text(), None

        capture = self._open_camera()
        if capture is None:
            return False, "No camera device could be opened.", None
        try:
            frame = None
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                ok, frame = capture.read()
                if ok and frame is not None and frame.size:
                    break
                time.sleep(0.15)
            if frame is None:
                return False, "The camera returned no frame - check that no other app is using it.", None

            self._last_frame = frame
            self.save_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            suffix = label if isinstance(label, str) and label and all(ord(c) < 128 for c in label) else "photo"
            target = self.save_dir / f"jarvis-{suffix}-{stamp}.png"

            import cv2  # type: ignore

            cv2.imwrite(str(target), frame)
            self._last_frame = None
            return True, f"Photo saved to {target.name}", target
        except Exception as exc:
            return False, f"Camera capture failed: {exc}", None
        finally:
            try:
                if self._camera is not None:
                    self._camera.release()
                self._camera = None
            except Exception:
                pass

    def frame_to_png(self, frame) -> bytes:
        """Encode a numpy frame to PNG bytes (used when sending to Gemini)."""
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            if frame is None:
                return b""
            ok, buffer = cv2.imencode(".png", frame)
            if ok and buffer is not None:
                return bytes(buffer.tobytes())
            return b""
        except Exception as exc:
            log.warning("frame encoding failed: %s", exc)
            return b""

    def frame_base64(self, frame) -> str:
        payload = self.frame_to_png(frame)
        if not payload:
            return ""
        return base64.b64encode(payload).decode("ascii")

    def release(self) -> None:
        if self._camera is not None:
            try:
                self._camera.release()
            except Exception:
                pass
            self._camera = None
        self._last_frame = None


__all__ = ["CameraController", "WINDOWS"]
