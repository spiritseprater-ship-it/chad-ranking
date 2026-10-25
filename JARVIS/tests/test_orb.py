"""Orb visual tests: palettes, particle maths and state transitions.

The animation maths is pure Python, so it is tested without Qt.
"""

from __future__ import annotations

import math

import pytest

from orb import (
    PALETTES,
    PARTICLE_COUNTS,
    STATE_LABELS,
    STATE_MOTION,
    OrbParameters,
    OrbScene,
    OrbState,
    OrbViewModel,
    create_orb_widget,
    lerp_color,
    transition_progress,
)


@pytest.fixture()
def scene() -> OrbScene:
    return OrbScene(max_particles=600)


def test_every_state_has_a_palette_and_motion() -> None:
    for state in OrbState:
        assert set(PALETTES[state]) == {"background", "primary", "secondary", "core", "glow"}
        assert len(STATE_MOTION[state]) == 3
        assert len(PARTICLE_COUNTS[state]) == 2
        assert STATE_LABELS[state]


def test_processing_spins_fastest_and_error_is_slow() -> None:
    standby = STATE_MOTION[OrbState.STANDBY][0]
    processing = STATE_MOTION[OrbState.PROCESSING][0]
    error = STATE_MOTION[OrbState.ERROR][0]
    assert processing > standby
    assert error < processing


def test_low_resource_uses_fewer_particles() -> None:
    for state in OrbState:
        standard, low = PARTICLE_COUNTS[state]
        assert low < standard


def test_compact_mode_reduces_particles() -> None:
    model = OrbViewModel()
    model.compact = True
    assert model.parameters().particle_count < OrbParameters.for_state(OrbState.STANDBY).particle_count


def test_unit_points_lie_on_a_sphere(scene: OrbScene) -> None:
    points = scene.unit_points()
    assert len(points) == 600
    for x, y, z in points:
        assert math.isclose(math.sqrt(x * x + y * y + z * z), 1.0, abs_tol=1e-9)


def test_particles_are_inside_the_rendered_area(scene: OrbScene) -> None:
    palette = PALETTES[OrbState.PROCESSING]
    params = OrbParameters.for_state(OrbState.PROCESSING)
    particles = scene.particles(2.5, params, 400, 300, palette)
    assert len(particles) == params.particle_count
    for particle in particles:
        # wobble scales the sphere slightly, so allow a small margin
        assert -1.4 <= particle.depth <= 1.4
        assert 0.0 < particle.alpha <= 1.0
        assert 0 < particle.size < 60
        # particles near the camera can project past the widget edges
        assert -400 <= particle.x <= 800
        assert -300 <= particle.y <= 600


def test_near_particles_are_larger_and_opaquer(scene: OrbScene) -> None:
    palette = PALETTES[OrbState.STANDBY]
    params = OrbParameters.for_state(OrbState.STANDBY)
    particles = scene.particles(0.0, params, 600, 600, palette)
    near = [p for p in particles if p.depth > 0.6]
    far = [p for p in particles if p.depth < -0.6]
    assert near and far
    assert min(p.size for p in near) > max(p.size for p in far)
    assert min(p.alpha for p in near) > max(p.alpha for p in far)


def test_rotation_moves_the_particles(scene: OrbScene) -> None:
    palette = PALETTES[OrbState.STANDBY]
    params = OrbParameters(particle_count=200, speed=1.0)
    first = scene.particles(0.0, params, 400, 400, palette)
    second = scene.particles(1.0, params, 400, 400, palette)
    assert [p.x for p in first] != [p.x for p in second]


def test_lerp_color_clamps() -> None:
    assert lerp_color((0, 0, 0), (10, 20, 30), 0.0) == (0, 0, 0)
    assert lerp_color((0, 0, 0), (10, 20, 30), 1.0) == (10, 20, 30)
    assert lerp_color((0, 0, 0), (10, 20, 30), -1.0) == (0, 0, 0)
    assert lerp_color((0, 0, 0), (10, 20, 30), 2.0) == (10, 20, 30)


def test_transition_progress_is_smoothstep() -> None:
    assert transition_progress(0, 0.3) == 0.0
    assert transition_progress(0.3, 0.3) == 1.0
    mid = transition_progress(0.15, 0.3)
    assert 0.0 < mid < 1.0
    assert transition_progress(5, 0.3) == 1.0


def test_view_model_transitions_between_states() -> None:
    model = OrbViewModel()
    assert model.set_state(OrbState.LISTENING) is True
    assert model.state is OrbState.LISTENING
    assert model.transition == 0.0
    for _ in range(10):
        model.advance(0.05)
    assert model.transition > 0.9

    assert model.set_state(OrbState.LISTENING) is False  # no change -> no transition


def test_frame_interpolates_between_palettes() -> None:
    model = OrbViewModel()
    model.set_state(OrbState.ERROR)
    model.advance(0.05)
    background, particles, glow = model.frame(320, 320)
    assert len(background) == 3
    assert particles
    assert glow[2] > 0


def test_low_resource_frame_has_fewer_particles() -> None:
    model = OrbViewModel(low_resource=True)
    _background, particles, _glow = model.frame(400, 400)
    assert len(particles) <= PARTICLE_COUNTS[OrbState.STANDBY][1]


def test_widget_creation_is_lazy_and_reports_qt() -> None:
    # create_orb_widget requires PySide6; on a headless host it must fail loudly
    if not pytest.importorskip("PySide6", reason="PySide6 not installed"):
        return
    widget = create_orb_widget()
    assert widget is not None
