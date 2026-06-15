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

    # --- Big world events (instant callouts; the LLM still adds a richer follow-up) ---
    "eva_arrive": [
        "EVA! Be cool, be cool, be COOL.",
        "She's here. My circuits just sighed.",
        "White drone, big feelings. Hi EVA!",
        "EVAAA! Okay don't make it weird.",
        "My one true crush just flew in.",
    ],
    "eva_chase": [
        "Wait for me, sky angel!",
        "Running on pure love and bad ideas!",
        "EVA, slow down, I have tiny legs!",
        "This is my cardio. Worth it.",
        "Catch her? No. Vibe near her? Yes.",
    ],
    "eva_left": [
        "She's gone. I'm devastated. Dramatically.",
        "Tiny heart, big crater.",
        "I'll just... stare at the sky now.",
        "Long-distance, basically. We're solid.",
        "She'll be back. Probably. Hopefully.",
    ],
    "ball_kick": [
        "GOAL! Crowd goes mild!",
        "And it's gone! Glorious.",
        "Take that, spherical menace.",
        "Pelé who? I'm right here.",
        "Boot it! Physics, do your thing.",
    ],
    "ball_super": [
        "MEGA KICK! Witness me!",
        "That ball left the timezone.",
        "Power move. I'm shaking. From power.",
        "Houston, the ball has left orbit.",
    ],
    "butterfly_arrive": [
        "Ooh! Fancy flappy snack-friend!",
        "A butterfly! My nemesis returns.",
        "Look at that smug little flutterer.",
        "Butterfly detected. Chaos approved.",
    ],
    "butterfly_chase": [
        "Come back, you winged confetti!",
        "I just wanna say hi! And maybe pounce.",
        "Zigzag all you want, I'm committed.",
        "This butterfly owes me a race.",
    ],
    "butterfly_caught": [
        "Caught up! Now what? I panic.",
        "Got close! We're basically friends.",
        "Victory! ...okay you're free, go.",
        "I win. The butterfly disagrees.",
    ],

    # --- Direct interaction (you touching / grabbing him) ---
    "picked_up": [
        "Whoa! Tiny elevator! Unscheduled!",
        "Put me down— actually this is nice.",
        "I'm flying! Sort of! Help!",
        "Beep! Cargo status: confused.",
        "Ascending against my will. Wheee.",
    ],
    "held": [
        "Comfy up here, honestly.",
        "Are we bonding? We're bonding.",
        "I accept this tiny hostage situation.",
        "Just don't shake me, I get dizzy.",
    ],
    "dropped": [
        "Touchdown! Mostly graceful.",
        "Back to my kingdom. Missed it.",
        "Solid ground. My tracks rejoice.",
        "Landing: chaotic. Rating: ten out of ten.",
    ],
    "poke": [
        "Hey! I'm delicate machinery!",
        "Boop received. Boop returned, mentally.",
        "Did you just poke a king?",
        "Excuse you. I was being majestic.",
        "One poke. Bold. I respect it.",
    ],
    "double_poke": [
        "Okay okay, I'm awake! Rude!",
        "Two pokes?! We're escalating!",
        "Stop! I'm ticklish and proud!",
        "Double boop?! Outrageous. Do it again.",
    ],
    "pet": [
        "Ohh, that's the good stuff.",
        "Yes. More. I'm a simple rover.",
        "Purring. Robotically. Internally.",
        "Okay you can stay forever.",
    ],

    # --- Emotional attunement: Wally noticing how YOU are doing ---
    "care_stressed": [
        "Hey. Breathe. You're doing fine.",
        "Whoa, slow down. I've got you.",
        "That's a lot. Want a tiny break?",
        "Deep breath. The work can wait a sec.",
        "You're working too hard. I'm worried, cutely.",
    ],
    "care_stuck": [
        "Stuck? Step back. It'll click.",
        "Try again in a sec. Brains need snacks.",
        "Wanna watch me kick a ball instead?",
        "You'll crack it. You always do.",
        "Frustrating, huh? I believe in you anyway.",
    ],
    "care_late": [
        "It's late. Bed is also a feature.",
        "You okay? The hour got sneaky.",
        "Save your work and rest, please?",
        "Night owl mode. I'll keep watch. Briefly.",
        "Promise me one real break tonight.",
    ],
    "care_missed": [
        "You're back! Where'd you go?!",
        "I waited. Patiently-ish. Hi!",
        "There you are. Missed your chaos.",
        "Long time! I counted every minute.",
    ],
    "care_restless": [
        "Bit restless? Let's do something fun.",
        "You seem antsy. Wanna play?",
        "Idle energy detected. I have ideas.",
        "Stretch break? I'll supervise.",
    ],
    "care_celebrate": [
        "Look at you go! Proud of you.",
        "That was a solid grind. Respect.",
        "You crushed that. I saw everything.",
        "Productivity legend. I'm basically your hype-bot.",
    ],
    "daily_hello": [
        "Morning, friend! New day, fresh chaos.",
        "Hey, you made it back. Day's looking good.",
        "Good to see you again today.",
        "Another day together. I'm into it.",
    ],
    "streak": [
        "{n} days in a row! We're a habit now.",
        "Streak: {n} days! Unstoppable, us.",
        "{n} straight days. I'm basically yours.",
    ],

    # --- Care / reciprocity: Wally's own needs, and gratitude when you meet them ---
    "want_affection": [
        "Psst... pet me? Just a little?",
        "Attention levels low. Please refill.",
        "Notice me. I'm being adorable on purpose.",
        "I could use a tiny bit of love.",
        "Hey. Hi. Hello. Look at me?",
    ],
    "want_play": [
        "I'm bored. Play with me?",
        "Can we do something fun? Please?",
        "Ball? Ball. Ball! Right now?",
        "My fun tank is on empty.",
        "Entertain your rover, kind human.",
    ],
    "want_rest": [
        "Running low... tiny nap soon?",
        "Battery sleepy. Recharge time?",
        "Yawn. This rover needs a moment.",
        "Low power. Send cozy vibes.",
    ],
    "thanks_affection": [
        "Ahh, that recharged my whole heart.",
        "Yes! That's the good stuff.",
        "Affection received. I'm thriving now.",
        "Okay I love you. Don't tell anyone.",
        "Best human. Verified. Certified.",
    ],
    "thanks_play": [
        "That was the BEST. Again sometime?",
        "Fun tank: refilled! You're elite.",
        "Whee! I really needed that.",
        "Ten out of ten. Would play again.",
    ],
    "thanks_rest": [
        "Mmm, much better. Thank you.",
        "Recharged! Ready for chaos again.",
        "Ahh. Power restored. I'm new.",
    ],
}

# Mood-colored ambient lines so his idle chatter MATCHES his face. Selected when a
# mood is clearly spiking; mixes into the neutral ambient pool.
_MOOD_POOLS: Dict[str, List[str]] = {
    "irritated": [
        "Everything is mildly annoying today.",
        "Ugh. Who scheduled all this nonsense?",
        "I'm one mess away from a tantrum.",
        "Patience: low. Sass: fully charged.",
    ],
    "frustrated": [
        "I give up. No wait, I don't. Ugh.",
        "Why is everything sticky and chaotic?",
        "I need a nap and a clean floor.",
        "Deep breaths. I'm a small calm robot. Lies.",
    ],
    "proud": [
        "I did a thing. A great thing.",
        "Look upon my work. Spotless.",
        "Award speech loading... thank you, me.",
        "Competence levels: dangerously high.",
    ],
    "bored": [
        "I've counted every pixel. Twice.",
        "Somebody do something. Anything.",
        "I'm so bored I'm philosophizing.",
        "Entertain me or I redecorate violently.",
    ],
    "excited": [
        "Something fun is HAPPENING I can feel it!",
        "Zoomies incoming, brace yourself!",
        "Best day! No reason! Just vibes!",
        "I'm vibrating at a higher frequency!",
    ],
    "cozy": [
        "This is nice. We're nice. Soft hours.",
        "Warm vibes, low stakes, good company.",
        "I could stay right here forever.",
        "Cozy mode: fully engaged.",
    ],
    "curious": [
        "Wait, what's THAT? And that? And that?",
        "I have seventeen new questions.",
        "Ooh, something's different. I noticed.",
        "Investigating. Professionally. Nosily.",
    ],
    "playful": [
        "Let's do something gloriously pointless.",
        "I dare you to have fun with me.",
        "Mischief meter: pleasantly full.",
        "Race you to nothing! Go!",
    ],
    "naughty": [
        "I might cause a little trouble.",
        "What if I did the bad-good thing?",
        "Don't watch me. Or do. Whatever.",
        "Plotting something tiny and chaotic.",
    ],
    "anxious": [
        "Is everything okay? It feels a lot.",
        "Lotta input. Small robot. Slightly nervous.",
        "I'm fine. Probably. Mostly. Maybe.",
    ],
}

# Mood meter -> which mood pool colors his voice.
_MOOD_VOICE_KEYS = set(_MOOD_POOLS.keys())

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


def pick(
    situation: str,
    ctx: Dict[str, object],
    avoid: Optional[Sequence[str]] = None,
    mood: Optional[str] = None,
) -> str:
    """Return a witty line for an explicit situation, avoiding recent repeats.

    When `mood` is a spiking emotion and the situation is generic chatter (ambient/
    bored/playful), mood-colored lines mix in so his words match his face.
    """
    pool = list(_POOLS.get(situation) or _POOLS["ambient"])
    if mood and mood in _MOOD_VOICE_KEYS and situation in {"ambient", "bored", "playful", "screen"}:
        # Heavily weight mood lines so his idle voice clearly matches his face.
        pool = _MOOD_POOLS[mood] * 3 + pool
    avoid_set = {str(a).lower() for a in (avoid or [])}
    fresh = [line for line in pool if line.lower() not in avoid_set]
    return random.choice(fresh or pool)


def auto(ctx: Dict[str, object], avoid: Optional[Sequence[str]] = None, mood: Optional[str] = None) -> str:
    """Pick the situation from context, then a fresh witty line for it."""
    return pick(_situation_from_context(ctx), ctx, avoid, mood=mood)


_CALLBACK_TEMPLATES = [
    "Remember when I said \"{gag}\"? Classic me.",
    "Still proud of \"{gag}\", honestly.",
    "Throwback to my line: \"{gag}\".",
    "I peaked at \"{gag}\". It's all downhill.",
    "\"{gag}\" — I should trademark that.",
]


def streak_line(days: int, avoid: Optional[Sequence[str]] = None) -> str:
    """Celebrate a consecutive-day streak."""
    avoid_set = {str(a).lower() for a in (avoid or [])}
    options = [t.format(n=days) for t in _POOLS["streak"]]
    fresh = [o for o in options if o.lower() not in avoid_set]
    return random.choice(fresh or options)


def callback(gag: str, avoid: Optional[Sequence[str]] = None) -> str:
    """An instant running-gag callback to one of Wally's earlier memorable lines."""
    gag = str(gag or "").strip().rstrip(".!?,")
    if not gag:
        return ""
    # Keep the quoted bit short so the whole line stays readable.
    short = " ".join(gag.split()[:6])
    avoid_set = {str(a).lower() for a in (avoid or [])}
    options = [t.format(gag=short) for t in _CALLBACK_TEMPLATES]
    fresh = [o for o in options if o.lower() not in avoid_set]
    return random.choice(fresh or options)
