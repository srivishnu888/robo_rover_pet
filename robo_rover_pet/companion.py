"""Emotional attunement — Wally reading how the *user* is doing.

This is what turns a reactive desktop toy into a companion: instead of only
reacting to events (typing, windows, EVA), Wally infers the user's well-being from
their behavior and responds like a friend who cares — encouraging during a grind,
protective when overwhelmed, gentle late at night, playful when they're restless,
celebratory after a productive stretch, and quietly out of the way during deep flow.

read_state() is pure and testable: it maps live activity signals to a well-being
state plus a suggested caring response (a banter situation, mood nudges, and whether
Wally should actually speak or stay respectfully quiet).
"""

from __future__ import annotations

from typing import Dict, Optional


# State -> caring response. `situation` is a banter pool key (None = stay quiet),
# `mood` are mood-meter nudges, `speak` is the base chance Wally voices it.
_RESPONSES: Dict[str, Dict[str, object]] = {
    "overwhelmed": {"situation": "care_stressed", "mood": {"anxious": 10, "encouraging": 12, "playful": -6}, "speak": 0.7, "expression": "soft"},
    "stuck":       {"situation": "care_stuck",    "mood": {"encouraging": 12, "curious": 6, "frustrated": -6}, "speak": 0.5, "expression": "curious"},
    "fatigued":    {"situation": "care_late",     "mood": {"cozy": 12, "encouraging": 8, "excited": -8}, "speak": 0.6, "expression": "sleepy"},
    "restless":    {"situation": "care_restless", "mood": {"playful": 12, "bored": -10}, "speak": 0.45, "expression": "curious"},
    "celebrate":   {"situation": "care_celebrate","mood": {"proud": 14, "excited": 10, "encouraging": 8}, "speak": 0.6, "expression": "proud"},
    "flow":        {"situation": None,            "mood": {"encouraging": 4, "cozy": 3}, "speak": 0.06, "expression": None},
    "neutral":     {"situation": None,            "mood": {}, "speak": 0.0, "expression": None},
}


def read_state(signals: Dict[str, object]) -> str:
    """Infer the user's well-being from live activity signals."""
    pressure = float(signals.get("work_pressure", 0) or 0)
    keys = float(signals.get("key_score", 0) or 0)
    idle = float(signals.get("idle_seconds", 0) or 0)
    switches = float(signals.get("window_changes", 0) or 0)
    daypart = str(signals.get("daypart", ""))
    session_min = float(signals.get("session_minutes", 0) or 0)
    recent_idle_bursts = float(signals.get("idle_burst_score", 0) or 0)

    # Overwhelmed: high sustained pressure, often with frantic app-switching.
    if pressure >= 72 or (pressure >= 55 and switches >= 4):
        return "overwhelmed"

    # Fatigued: long late-night session.
    if daypart == "late_night" and session_min >= 40:
        return "fatigued"

    # Stuck: typing in bursts but thrashing between windows / pausing a lot.
    if switches >= 5 and keys < 8 and recent_idle_bursts >= 2:
        return "stuck"

    # Celebrate: a long, steady, productive stretch that just eased off.
    if session_min >= 50 and pressure <= 35 and keys < 6 and idle < 40:
        return "celebrate"

    # Restless: present but fidgety — low real work, frequent small switches.
    if idle < 25 and keys < 4 and switches >= 3:
        return "restless"

    # Flow: steady moderate work, not thrashing — leave them be.
    if 4 <= keys <= 30 and switches <= 1 and idle < 20:
        return "flow"

    return "neutral"


def response_for(state: str) -> Dict[str, object]:
    return dict(_RESPONSES.get(state, _RESPONSES["neutral"]))
