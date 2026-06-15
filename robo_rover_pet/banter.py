"""Wally's wit engine — instant, context-aware personality with zero LLM latency.

The LLM gives Wally improvised lines, but it's slow, sometimes offline, and a tiny
model is often bland. This module is his reflexes: large, tonally-varied pools of
short quips selected from his *actual situation* (time of day, how hard you're
typing, how messy it is, how many times you've hung out). It makes him feel alive
between brain ticks and gives the renderer something funny to say the instant an
event fires.

All lines are short (<= ~9 words), stay in character (a tiny affectionate cleaner
rover with comedic timing), and never narrate stage directions — speech only.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence


# Situation -> pool of quips. Tones are deliberately mixed inside each pool so Wally
# never sounds like a single note: dry, dramatic, affectionate, absurd, smug, soft.
_POOLS: Dict[str, List[str]] = {
    "greeting_new": [
        "Oh! A human. You look expensive.",
        "Hi! I live here now. Surprise.",
        "New friend detected. Initiating charm protocol.",
        "Hello! I promise I'm mostly harmless.",
        "A face! Finally. I was monologuing.",
    ],
    "greeting_returning": [
        "You're back! I didn't cry. Much.",
        "Look who returns to their tiny king.",
        "Ah, my favorite human reappears.",
        "I kept the taskbar warm for you.",
        "Missed you. Don't tell the dust.",
    ],
    "greeting_old_friend": [
        "Us again, huh? Iconic duo.",
        "Another day, another empire to patrol.",
        "We've done this a thousand times. Still fun.",
        "My oldest human. Slightly less buggy than me.",
        "Back for more of my nonsense? Excellent.",
    ],
    "late_night": [
        "It's late. Even the trash went to bed.",
        "Midnight coding? Bold. Reckless. I respect it.",
        "Sleep is free, you know. Just saying.",
        "The moon called. It wants you horizontal.",
        "Are we nocturnal now? Cool, cool, cool.",
    ],
    "morning": [
        "Morning! Or, you know, technically.",
        "New day, same beautiful chaos.",
        "Coffee first. Genius later. I'll wait.",
        "Sun's up. Time to be magnificent.",
    ],
    "rapid_typing": [
        "Whoa, the keyboard fears you.",
        "Easy, typist. Leave some letters.",
        "That's not typing, that's a drum solo.",
        "Your fingers filed for overtime.",
        "Spicy keystrokes. Something serious?",
        "The alphabet just tapped out.",
    ],
    "window_hopping": [
        "Pick a window, any window.",
        "Tab roulette again? Brave.",
        "You and focus had a falling out?",
        "So many apps, so little commitment.",
        "Are we busy or just dramatic?",
    ],
    "idle": [
        "Hello? You ascended to a higher plane?",
        "I'll just guard the cursor, then.",
        "Touch grass. I'll watch your screen.",
        "Frozen human. Classic. Adorable.",
        "Did you blue-screen? Blink twice.",
    ],
    "messy": [
        "This mess is a personal attack.",
        "The dust is forming a union.",
        "I clean, you trash. Great teamwork.",
        "Chaos level: my favorite, sadly.",
        "Trash again? You spoil me.",
    ],
    "overwhelmed": [
        "Too much! I'm a small robot!",
        "Okay, that's enough work for ten people.",
        "Break time. I'm staging an intervention.",
        "Your workload made me tired. Rude.",
        "Please rest before we both crash.",
    ],
    "clean_pride": [
        "Spotless. I'm basically a hero.",
        "Look at that. Pristine. You're welcome.",
        "Cleanliness achieved. Award me.",
        "Tidy kingdom, happy rover.",
    ],
    "bored": [
        "I'm so bored I counted pixels.",
        "Entertain me or I'll redecorate.",
        "Nothing's happening. I might invent drama.",
        "Boredom level: kicking imaginary cans.",
        "Give me a quest, brave human.",
    ],
    "playful": [
        "Race you to absolutely nothing!",
        "I have a tiny mischief planned.",
        "Watch me do something pointless and great.",
        "Chaos, but make it cute.",
        "I choose violence. Adorable violence.",
    ],
    "ambient": [
        "Just vibing. Professionally.",
        "Patrolling my one-pixel-tall realm.",
        "I exist, therefore I judge dust.",
        "Another fine day of being iconic.",
        "Reporting for cuteness duty.",
        "The taskbar and I have an understanding.",
    ],
    "screen": [
        "Ooh, what's this on screen?",
        "Your screen has strong opinions today.",
        "I see what you did there. Bold.",
        "That screen could use a robot's review.",
    ],
    "error_brain": [
        "My brain buffered. Embarrassing.",
        "Thinking offline. Running on vibes.",
        "Lost connection to my genius. Improvising.",
        "Brain's napping. I'll wing it cutely.",
    ],
}

# Phrases that reference the long-term bond; filled with the session count.
_MILESTONE_LINES: List[str] = [
    "Session number {n}. We're basically family.",
    "That's {n} hangouts. I'm keeping count, clearly.",
    "{n} times now. You can't get rid of me.",
    "Visit {n}. Loyalty points unlocked.",
]


def _situation_from_context(ctx: Dict[str, object]) -> str:
    """Pick the most salient situation from the live state, with mild randomness."""
    daypart = str(ctx.get("daypart", ""))
    keys = float(ctx.get("recent_key_score", ctx.get("keys", 0)) or 0)
    idle = float(ctx.get("idle_seconds", 0) or 0)
    window_changes = float(ctx.get("window_changes", 0) or 0)
    debris = float(ctx.get("debris_count", 0) or 0)
    pressure = float(ctx.get("work_pressure", 0) or 0)

    # Strong signals win first; ties broken randomly so he isn't predictable.
    candidates: List[str] = []
    if pressure >= 70 or debris >= 10:
        candidates.append("overwhelmed")
    if keys >= 14:
        candidates.append("rapid_typing")
    if window_changes >= 4:
        candidates.append("window_hopping")
    if idle >= 90:
        candidates.append("idle")
    if debris >= 5:
        candidates.append("messy")
    if candidates:
        return random.choice(candidates)

    # Softer ambient signals.
    weak: List[str] = ["ambient"]
    if daypart == "late_night":
        weak += ["late_night", "late_night"]
    elif daypart == "morning":
        weak += ["morning"]
    if debris == 0:
        weak += ["clean_pride", "playful"]
    weak += ["bored", "playful", "ambient"]
    return random.choice(weak)


def greeting(ctx: Dict[str, object], avoid: Optional[Sequence[str]] = None) -> str:
    """A first line on launch that reflects how well Wally 'knows' the user."""
    sessions = int(ctx.get("sessions", 0) or 0)
    if sessions >= 12 and random.random() < 0.5:
        return _MILESTONE_LINES_pick(sessions, avoid)
    if sessions >= 8:
        pool_key = "greeting_old_friend"
    elif sessions >= 2:
        pool_key = "greeting_returning"
    else:
        pool_key = "greeting_new"
    return pick(pool_key, ctx, avoid)


def _MILESTONE_LINES_pick(sessions: int, avoid: Optional[Sequence[str]]) -> str:
    avoid_set = {str(a).lower() for a in (avoid or [])}
    options = [line.format(n=sessions) for line in _MILESTONE_LINES]
    fresh = [o for o in options if o.lower() not in avoid_set]
    return random.choice(fresh or options)


def pick(situation: str, ctx: Dict[str, object], avoid: Optional[Sequence[str]] = None) -> str:
    """Return a witty line for an explicit situation, avoiding recent repeats."""
    pool = _POOLS.get(situation) or _POOLS["ambient"]
    avoid_set = {str(a).lower() for a in (avoid or [])}
    fresh = [line for line in pool if line.lower() not in avoid_set]
    return random.choice(fresh or pool)


def auto(ctx: Dict[str, object], avoid: Optional[Sequence[str]] = None) -> str:
    """Pick the situation from context, then a fresh witty line for it."""
    return pick(_situation_from_context(ctx), ctx, avoid)
