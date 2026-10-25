"""
orb.py - premium particle orb visualisation.

The visual is a 3-D particle sphere rendered with QPainter (a 2-D projection of a
rotating sphere). That gives the premium look without a heavy 3-D engine, which
matters for the 50-100 MB target and for low-resource machines.

All animation math lives in :class:`OrbScene` and :class:`OrbViewModel`, which are
pure Python and unit-tested here without Qt.  The Qt widget is built lazily by
:func:`create_orb_widget`, so importing this module never requires PySide6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# states
# ---------------------------------------------------------------------------


class OrbState(str, Enum):
    STANDBY = "standby"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


STATE_LABELS = {
    OrbState.STANDBY: "Ready",
    OrbState.LISTENING: "Listening",
    OrbState.PROCESSING: "Thinking",
    OrbState.SPEAKING: "Speaking",
    OrbState.ERROR: "Attention needed",
}

# (background, primary, secondary, core, glow) as (r, g, b)
PALETTES: Dict[OrbState, Dict[str, Tuple[int, int, int]]] = {
    OrbState.STANDBY: {
        "background": (8, 10, 22),
        "primary": (80, 120, 255),
        "secondary": (120, 160, 255),
        "core": (200, 220, 255),
        "glow": (60, 100, 220),
    },
    OrbState.LISTENING: {
        "background": (6, 14, 24),
        "primary": (60, 220, 200),
        "secondary": (110, 255, 230),
        "core": (220, 255, 245),
        "glow": (40, 200, 190),
    },
    OrbState.PROCESSING: {
        "background": (14, 8, 26),
        "primary": (160, 110, 255),
        "secondary": (220, 160, 255),
        "core": (245, 230, 255),
        "glow": (140, 80, 230),
    },
    OrbState.SPEAKING: {
        "background": (18, 8, 20),
        "primary": (255, 110, 150),
        "secondary": (255, 170, 190),
        "core": (255, 240, 248),
        "glow": (240, 90, 140),
    },
    OrbState.ERROR: {
        "background": (22, 8, 8),
        "primary": (255, 90, 90),
        "secondary": (255, 150, 130),
        "core": (255, 220, 220),
        "glow": (240, 70, 70),
    },
}

# (standard, low-resource) particle counts per state.
PARTICLE_COUNTS: Dict[OrbState, Tuple[int, int]] = {
    OrbState.STANDBY: (320, 140),
    OrbState.LISTENING: (340, 150),
    OrbState.PROCESSING: (420, 180),
    OrbState.SPEAKING: (380, 165),
    OrbState.ERROR: (300, 140),
}

# (speed, wobble, pulse) per state.
STATE_MOTION: Dict[OrbState, Tuple[float, float, float]] = {
    OrbState.STANDBY: (0.30, 0.00, 0.05),
    OrbState.LISTENING: (0.80, 0.10, 0.35),
    OrbState.PROCESSING: (1.50, 0.35, 0.85),
    OrbState.SPEAKING: (1.05, 0.22, 0.60),
    OrbState.ERROR: (0.55, 0.05, 0.15),
}

# Compact and tray modes shrink and thin the orb.
COMPACT_SCALE = 0.82
COMPACT_PARTICLE_RATIO = 0.72


def transition_progress(elapsed: float, duration: float) -> float:
    """Smoothstep easing used for every state change."""
    if duration <= 0:
        return 1.0
    value = min(1.0, max(0.0, elapsed / duration))
    return value * value * (3 - 2 * value)


def lerp_color(a: Tuple[int, int, int], b: Tuple[int, int, int], amount: float) -> Tuple[int, int, int]:
    amount = min(1.0, max(0.0, amount))
    return tuple(int(round(a[i] + (b[i] - a[i]) * amount)) for i in range(3))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# geometry (pure, testable)
# ---------------------------------------------------------------------------


@dataclass
class Particle:
    x: float
    y: float
    depth: float  # -1 (far) .. 1 (near)
    size: float
    alpha: float
    color: Tuple[int, int, int]


@dataclass
class OrbParameters:
    particle_count: int = 320
    speed: float = 1.0
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    wobble: float = 0.0
    pulse: float = 0.0
    radius: float = 1.0
    focus: float = 2.6
    bloom: bool = True

    @staticmethod
    def for_state(state: OrbState, low_resource: bool = False,
                  previous: Optional[OrbState] = None, mix: float = 1.0) -> "OrbParameters":
        particle_count = (
            PARTICLE_COUNTS[state][0] if not low_resource else PARTICLE_COUNTS[state][1]
        )
        speed, wobble, pulse = STATE_MOTION[state]
        params = OrbParameters(
            particle_count=particle_count,
            speed=speed,
            wobble=wobble,
            pulse=pulse,
            bloom=not low_resource,
        )
        if previous is not None and previous is not state and 0.0 <= mix < 1.0:
            previous_speed, previous_wobble, previous_pulse = STATE_MOTION[previous]
            params.speed = previous_speed + (speed - previous_speed) * mix
            params.wobble = previous_wobble + (wobble - previous_wobble) * mix
            params.pulse = previous_pulse + (pulse - previous_pulse) * mix
        return params


class OrbScene:
    """Fibonacci-distributed particle sphere with per-frame 2-D projection."""

    def __init__(self, max_particles: int = 600, radius: float = 1.0) -> None:
        self.max_particles = int(max_particles)
        self.radius = float(radius)
        self._unit: List[Tuple[float, float, float]] = []
        self._build()

    def _build(self) -> None:
        count = self.max_particles
        self._unit = []
        for index in range(count):
            y = 1.0 - 2.0 * (index + 0.5) / count
            ring_radius = math.sqrt(max(0.0, 1.0 - y * y))
            theta = math.pi * (1.0 + math.sqrt(5.0)) * index
            self._unit.append((math.cos(theta) * ring_radius, y, math.sin(theta) * ring_radius))

    def unit_points(self) -> List[Tuple[float, float, float]]:
        return list(self._unit)

    def _rotate(self, x: float, y: float, z: float,
                rx: float, ry: float, rz: float) -> Tuple[float, float, float]:
        cos_y, sin_y = math.cos(ry), math.sin(ry)
        x, z = x * cos_y - z * sin_y, x * sin_y + z * cos_y
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        y, z = y * cos_x - z * sin_x, y * sin_x + z * cos_x
        cos_z, sin_z = math.cos(rz), math.sin(rz)
        x, y = x * cos_z - y * sin_z, x * sin_z + y * cos_z
        return x, y, z

    def particles(
        self,
        elapsed: float,
        params: OrbParameters,
        width: int,
        height: int,
        palette: Dict[str, Tuple[int, int, int]],
        low_resource: bool = False,
    ) -> List[Particle]:
        width = max(1, int(width))
        height = max(1, int(height))
        scale = min(width, height) * 0.38 * params.radius
        focal = params.focus * max(min(width, height), 1) / 500.0

        count = min(params.particle_count, len(self._unit))
        wobble = math.sin(elapsed * 1.7) * params.wobble
        rotation_y = params.rotation_y + elapsed * params.speed * 0.45
        rotation_x = params.rotation_x + math.sin(elapsed * 0.6) * 0.25
        pulse = 1.0 + math.sin(elapsed * 3.1) * params.pulse * 0.06

        primary = palette.get("primary", (90, 130, 255))
        secondary = palette.get("secondary", (140, 180, 255))
        core = palette.get("core", (220, 240, 255))

        particles: List[Particle] = []
        for index in range(count):
            base_x, base_y, base_z = self._unit[index]
            phase = index / max(count, 1)
            x, y, z = self._rotate(
                base_x * (1.0 + wobble * math.sin(elapsed * 2.0 + phase * 6.28)),
                base_y,
                base_z,
                rotation_x,
                rotation_y,
                params.rotation_z + math.sin(elapsed * 1.1 + phase * 6.28) * params.wobble * 0.5,
            )
            depth = z
            cam = focal + 1.6
            perspective = cam / max(cam - depth, 0.35)
            projected_x = x * scale * perspective + width / 2.0
            projected_y = -y * scale * perspective + height / 2.0
            # clamp: wobble can push a particle slightly past the sphere
            near = min(1.0, max(0.0, (depth + 1.0) / 2.0))
            alpha = 0.28 + 0.72 * near
            size = max(0.6, (1.1 + 3.4 * near) * (0.9 + 0.3 * phase) * pulse)
            color = primary if low_resource else lerp_color(primary, secondary, phase)
            if near > 0.72:
                color = lerp_color(color, core, (near - 0.72) * 3.0)
            particles.append(
                Particle(
                    x=projected_x,
                    y=projected_y,
                    depth=depth,
                    size=size,
                    alpha=alpha,
                    color=color,
                )
            )
        return particles

    def core_glow(
        self, width: int, height: int, elapsed: float, pulse: float = 0.0
    ) -> Tuple[float, float, float]:
        scale = min(width, height) * 0.38
        radius = max(6.0, 0.22 * scale * (1.0 + math.sin(elapsed * 2.2) * pulse * 0.15))
        return width / 2.0, height / 2.0, radius


# ---------------------------------------------------------------------------
# animation controller
# ---------------------------------------------------------------------------


@dataclass
class OrbViewModel:
    """Drives state transitions and produces the frame to render."""

    state: OrbState = OrbState.STANDBY
    previous_state: OrbState = OrbState.STANDBY
    transition: float = 1.0
    transition_elapsed: float = 0.0
    transition_duration: float = 0.35
    elapsed: float = 0.0
    low_resource: bool = False
    compact: bool = False
    tray: bool = False
    scene: OrbScene = field(default_factory=OrbScene)

    def set_state(self, state, transition_duration: float = 0.35) -> bool:
        state = OrbState(state) if not isinstance(state, OrbState) else state
        if state == self.state:
            return False
        self.previous_state = self.state
        self.state = state
        self.transition = 0.0
        self.transition_elapsed = 0.0
        self.transition_duration = transition_duration
        return True

    def advance(self, delta_seconds: float) -> None:
        delta = max(0.0, float(delta_seconds))
        self.elapsed += delta
        if self.transition < 1.0:
            self.transition_elapsed += delta
            self.transition = transition_progress(self.transition_elapsed, self.transition_duration)

    def eased(self) -> float:
        return self.transition

    def parameters(self) -> OrbParameters:
        params = OrbParameters.for_state(
            self.state, self.low_resource, self.previous_state, self.eased()
        )
        if self.compact or self.tray:
            params.radius = COMPACT_SCALE
            params.particle_count = int(params.particle_count * COMPACT_PARTICLE_RATIO)
        return params

    def mixed_palette(self) -> Dict[str, Tuple[int, int, int]]:
        current = PALETTES[self.state]
        previous = PALETTES[self.previous_state]
        if previous == current or self.eased() >= 1.0:
            return dict(current)
        return {
            name: lerp_color(previous.get(name, current[name]), current[name], self.eased())
            for name in current
        }

    def frame(self, width: int, height: int):
        """Return ``(background, particles, glow_center)``."""
        palette = self.mixed_palette()
        params = self.parameters()
        particles = self.scene.particles(self.elapsed, params, width, height, palette, self.low_resource)
        glow = self.scene.core_glow(width, height, self.elapsed, params.pulse)
        return palette.get("background", (8, 10, 22)), particles, glow


# ---------------------------------------------------------------------------
# Qt widget (created lazily so this module imports without PySide6)
# ---------------------------------------------------------------------------


def create_orb_widget(parent=None, low_resource: bool = False):
    """Build the :class:`OrbView` widget.  Requires PySide6 (Windows only)."""
    from PySide6.QtCore import Qt, QTimer  # type: ignore
    from PySide6.QtGui import QColor, QPainter, QRadialGradient  # type: ignore
    from PySide6.QtWidgets import QWidget  # type: ignore

    class OrbView(QWidget):
        """Painter-based particle orb with click-to-wake behaviour."""

        clicked = None  # callable(OrbView)

        def __init__(self, outer_parent=None) -> None:
            super().__init__(outer_parent)
            self.model = OrbViewModel(low_resource=low_resource)
            self._tick = 0
            self._last_time = 0.0
            self.setMinimumSize(180, 180)
            self.setCursor(Qt.PointingHandCursor)

            timer = QTimer(self)
            timer.timeout.connect(self._animate)
            self._timer = timer

        # -- animation ---------------------------------------------------------

        def _animate(self) -> None:
            current = QTimer.currentTime() / 1000.0
            delta = 0.0 if self._last_time == 0.0 else current - self._last_time
            self._last_time = current
            self._tick += 1
            self.model.advance(min(delta, 0.05))
            self.update()

        def start(self) -> None:
            self._timer.start(33)

        def stop(self) -> None:
            self._timer.stop()

        def set_state(self, state) -> bool:
            return self.model.set_state(state)

        def set_low_resource(self, enabled: bool) -> None:
            self.model.low_resource = bool(enabled)
            self.update()

        def set_compact(self, enabled: bool) -> None:
            self.model.compact = bool(enabled)
            self.update()

        def set_tray(self, enabled: bool) -> None:
            self.model.tray = bool(enabled)
            self.update()

        # -- painting ---------------------------------------------------------

        def paintEvent(self, _event) -> None:  # noqa: N802
            width, height = self.width(), self.height()
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            background, particles, glow = self.model.frame(width, height)
            painter.fillRect(0, 0, width, height, QColor(*background))
            painter.setCompositionMode(QPainter.CompositionMode_Screen)

            palette = self.model.mixed_palette()
            glow_color = palette.get("glow", (60, 100, 220))
            cx, cy, radius = glow
            if radius > 1:
                gradient = QRadialGradient(cx, cy, radius, cx, cy, radius * 2.2)
                gradient.setColorAt(0.0, QColor(glow_color[0], glow_color[1], glow_color[2], 70))
                gradient.setColorAt(1.0, QColor(glow_color[0], glow_color[1], glow_color[2], 0))
                painter.fillRect(0, 0, width, height, gradient)

            painter.setPen(Qt.NoPen)
            factor = 1.6 if not self.model.low_resource else 1.2
            for particle in particles:
                size = particle.size * factor
                color = QColor(
                    particle.color[0], particle.color[1], particle.color[2], int(particle.alpha * 255)
                )
                painter.setBrush(color)
                painter.drawEllipse(
                    int(particle.x - size / 2), int(particle.y - size / 2), int(size), int(size)
                )
            painter.end()

        # -- interaction -------------------------------------------------------

        def mousePressEvent(self, event) -> None:  # noqa: N802
            if event.button() == Qt.LeftButton and self.clicked is not None:
                self.clicked(self)
            super().mousePressEvent(event)

    widget = OrbView(parent)
    widget.start()
    return widget


__all__ = [
    "OrbState",
    "STATE_LABELS",
    "PALETTES",
    "PARTICLE_COUNTS",
    "STATE_MOTION",
    "COMPACT_SCALE",
    "Particle",
    "OrbParameters",
    "OrbScene",
    "OrbViewModel",
    "create_orb_widget",
    "transition_progress",
    "lerp_color",
]
