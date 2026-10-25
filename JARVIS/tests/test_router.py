"""Hybrid routing tests: local commands win, everything else goes to Gemini."""

from __future__ import annotations

import pytest

from brain import (
    ALWAYS_LOCAL_COMMANDS,
    Brain,
    Router,
    looks_like_ai_request,
    strip_wake_word,
)


@pytest.fixture()
def brain() -> Brain:
    return Brain()


@pytest.fixture()
def router(brain: Brain) -> Router:
    return Router(brain, ai_enabled=True, ai_available=True)


@pytest.fixture()
def offline_router(brain: Brain) -> Router:
    return Router(brain, ai_enabled=False, ai_available=False)


# -- new command specs ----------------------------------------------------


@pytest.mark.parametrize(
    "utterance,command",
    [
        ("cancel", "cancel_task"),
        ("cancel everything", "cancel_task"),
        ("cancel the task", "cancel_task"),
        ("stop that", "cancel_task"),
        ("abort", "cancel_task"),
        ("Check my JARVIS", "self_diagnostics"),
        ("Run self diagnostics", "self_diagnostics"),
        ("check status", "self_diagnostics"),
        ("Show task history", "task_history"),
        ("what did I ask you", "task_history"),
        ("history", "task_history"),
        ("turn on low resource mode", "low_resource_mode"),
        ("use less RAM", "low_resource_mode"),
        ("open the app", "open_app"),
        ("launch spotify", "open_app"),
        ("open youtube", "open_app"),
    ],
)
def test_task_commands_are_recognized(brain: Brain, utterance: str, command: str) -> None:
    parsed = brain.parse(utterance)
    assert parsed is not None, f"no command for {utterance!r}"
    assert parsed.command == command


def test_command_ids_are_unique(brain: Brain) -> None:
    ids = [spec.id for spec in brain.commands]
    assert len(ids) == len(set(ids))


def test_lifecycle_commands_stay_local(router: Router) -> None:
    for utterance in ("exit jarvis", "mute", "volume 40", "scroll down"):
        decision = router.route(utterance)
        assert decision.kind == "local", utterance
        assert decision.command_id in ALWAYS_LOCAL_COMMANDS


# -- routing --------------------------------------------------------------


def test_cancel_is_routed_as_a_cancel(router: Router) -> None:
    decision = router.route("cancel everything")
    assert decision.kind == "cancel"
    assert decision.command_id == "cancel_task"


def test_informational_request_goes_to_the_ai(router: Router) -> None:
    decision = router.route("what is the best laptop under 80000 rupees")
    assert decision.kind == "ai"
    assert decision.command is None


def test_open_web_request_goes_to_the_ai(router: Router) -> None:
    decision = router.route("google flights to mumbai")
    assert decision.kind == "ai"


def test_hindi_question_goes_to_the_ai(router: Router) -> None:
    assert router.route("kya mumbai mein barish ho rahi hai").kind == "ai"


def test_unknown_request_without_ai_asks_for_a_repeat(offline_router: Router) -> None:
    decision = offline_router.route("do something clever")
    assert decision.kind == "unknown"
    assert decision.command is None


def test_unknown_request_with_ai_is_handed_to_the_ai(router: Router) -> None:
    decision = router.route("do something clever")
    assert decision.kind == "ai"


def test_ai_unavailable_is_reported_in_the_reason(offline_router: Router) -> None:
    decision = offline_router.route("what is the weather")
    assert decision.kind == "unknown"
    assert "Gemini" in decision.reason


def test_wake_word_is_stripped_before_routing(router: Router) -> None:
    assert router.route("hey jarvis mute").kind == "local"
    assert router.route("jarvis, volume 30").command_id == "set_volume"


def test_wake_word_stripping_handles_extra_words() -> None:
    assert strip_wake_word("Hey Jarvis, open chrome", ["jarvis"]) == "open chrome"
    assert strip_wake_word("jarvis please", ["jarvis"]) == "please"


def test_empty_utterance_is_unknown(router: Router) -> None:
    assert router.route("").kind == "unknown"


def test_check_weather_is_not_a_diagnostic(router: Router) -> None:
    decision = router.route("check the weather in mumbai")
    assert decision.kind == "ai"


def test_diagnostics_still_works_when_ai_is_off(offline_router: Router) -> None:
    decision = offline_router.route("check my jarvis")
    assert decision.kind == "local"
    assert decision.command_id == "self_diagnostics"


def test_ai_capability_description(router: Router, offline_router: Router) -> None:
    assert "ready" in router.describe_capabilities()
    assert "not configured" in offline_router.describe_capabilities()


# -- AI request detection -------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what is the exchange rate", True),
        ("how do I set up a payment gateway", True),
        ("explain compound interest", True),
        ("kya ye sahi hai", True),
        ("open chrome", False),
        ("mute", False),
        ("volume 40", False),
    ],
)
def test_looks_like_ai_request(text: str, expected: bool) -> None:
    assert looks_like_ai_request(text) is expected
