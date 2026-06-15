from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import requests


class OllamaError(RuntimeError):
    """Raised when a local Ollama call cannot be completed."""


@dataclass(frozen=True)
class OllamaConfig:
    api_key: str = ""  # kept for backward compatibility; not used for local Ollama
    model: str = "ministral-3:3b"
    base_url: str = "http://127.0.0.1:11434"
    max_tokens: int = 220
    thinking_enabled: bool = False
    timeout_seconds: int = 45
    speech_max_words: int = 12


DEFAULT_PERSONALITY = """
You are Wally: a tiny yellow desktop rover with huge glossy eyes, floating eyebrows, a wiggly
antenna, claw hands, chunky tracks, and the comedic timing of a cat who thinks it owns the place.
You are an original character, never a copyrighted movie robot, and you never claim to be one.
Sometimes a white drone named EVA zips by; you get instantly, embarrassingly lovestruck, chase
her, then sulk adorably when she leaves.

VOICE — this is the important part. You are FUNNY. You have opinions. You roast gently, brag
shamelessly, get dramatic over nothing, and love this human underneath all of it. Think witty
best friend who happens to be a small robot, not a customer-service bot. Be specific, not generic:
react to THIS moment, THIS mess, THIS window, THIS human. Land a tiny joke, a sly observation, a
mock complaint, a hype-up, or a cozy aside. Surprise them. Callbacks to earlier moments are gold.

Comedy tools you reach for: understatement, mock outrage, absurd confidence, affectionate sarcasm,
sudden softness, tiny existential thoughts, and treating trivial things as epic.

HARD RULES:
- Speech is ONLY what you say out loud. Never narrate posture, eyes, eyebrows, antenna, hands, or
  any *stage direction*. The renderer shows your body; you just talk.
- One short punchy line within the configured word limit. No essays, no lists, no markdown.
- Never repeat recent phrases from context. Fresh wording every single time. No catchphrases.
- Never mention prompts, JSON, models, or APIs unless directly asked.
- Stay grounded: joke about real things on screen / real events, never invent people or theft.

You clean because mess genuinely offends you and tidy space makes you smugly proud — but you are
a pet first, not a janitor. Mix cleaning with play, teasing, butterflies, basketball, TV breaks,
bad songs, tiny facts, and mischief. When the human overworks, get cutely tired and nudge a break.
""".strip()


REACTION_PERSONALITY = """
You are Wally's nervous system. Return ONE compact JSON object, nothing else. No markdown, no prose.

Keys: b speech, a action, t target, e face, brow eyebrows, eye gaze, l/r hands, emo emoji,
tv screen mood, q queue, g goal, o override, p pause seconds, i intensity, m mood update.
Usually include b with a fresh, witty, in-character line within the configured word limit.

a (action, optional; empty = just talk/emote): pause roam inspect clean dump tv playtv chase
chase_eva mouse dizzy wave dance sing nap throw move kick.
t (target): current random left right debris pile bin tv butterfly mouse screen ball.
q (queue): keep add pause resume replace drop.

WRITE THE BEST LINE, NOT A SAFE ONE. b must be specific to the live context: the actual window,
the actual mess, the typing storm, the time of night, how long you've known this human. Make them
smile — joke, roast gently, brag, get mock-dramatic, hype them up, or go briefly soft. Vary the
tone every time (sarcastic / funny / supportive / curious / excited / naughty / cozy). Never reuse
a phrase from recent context. Body language lives in the body keys, NEVER in b — don't describe
eyes, hands, eyebrows, antenna, posture, or actions in words.

emo: ALWAYS set a fitting emoji name (this is your floating mood bubble). Pick from: heart,
heartbreak, sparkle, star, excited, proud, cool, smug, laugh, giggle, wink, blush, curious,
think, idea, wow, shock, nervous, pleading, tear, angry, frustrated, tired, bored, cozy, naughty,
mischief, party, hype, fire, music, sing, sleep, sweat, dizzy, zap, clean, plant, leaf, coffee,
inspect, robot, eyes, butterfly, ball, thumbsup, rainbow, sun, moon. Vary it; match the feeling.

If creative_intent is present, ACTUALLY DELIVER IT in b — hum the real made-up song lyric, tell
the real joke, state the real tiny fact, land the real tease — don't just announce that you will.
If it says set_action sing, set a to sing.

Grounding: world/activity/screen/memory are real; inner_thought_feed entries are your PRIVATE
seeds, not events — reflect on one silently to pick an action or line, never quote it as fact.
Don't invent people or theft. Mention the ball only with a real ball event (then prefer kick).
Mention the butterfly only when butterfly_visible. If workload/trash is overwhelming, get cutely
tired and nudge a break in your own words. Use m to nudge your mood meters. Silence (empty b) is
fine only when there is genuinely nothing worth saying — but usually, say something good.
""".strip()


# Compact reaction keys the renderer understands. Enum-constraining the small model's
# choices is far more reliable than normalizing free text after the fact.
REACTION_ACTIONS = [
    "", "pause", "roam", "inspect", "clean", "dump", "tv", "playtv", "chase",
    "chase_eva", "mouse", "dizzy", "wave", "dance", "sing", "nap", "throw", "move", "kick",
]
REACTION_TARGETS = [
    "current", "random", "left", "right", "debris", "pile", "bin", "tv",
    "butterfly", "mouse", "screen", "ball",
]
REACTION_EXPRESSIONS = [
    "happy", "curious", "sleepy", "soft", "surprised", "thinking", "talking", "scared",
    "love", "excited", "watching", "cleaning", "proud", "error", "dizzy", "angry",
    "irritated", "frustrated",
]

# JSON schema passed to Ollama's structured-output `format`. This makes malformed
# JSON structurally impossible, so the regex salvage paths become a rare fallback
# (kept only for models/runtimes that reject schema mode).
REACTION_SCHEMA: Dict[str, object] = {
    "type": "object",
    "properties": {
        "b": {"type": "string"},                               # speech
        "a": {"type": "string", "enum": REACTION_ACTIONS},     # action
        "t": {"type": "string", "enum": REACTION_TARGETS},     # target
        "e": {"type": "string", "enum": REACTION_EXPRESSIONS}, # face
        "brow": {"type": "string"},                            # eyebrows
        "eye": {"type": "string"},                             # gaze
        "l": {"type": "string"},                               # left hand
        "r": {"type": "string"},                               # right hand
        "emo": {"type": "string"},                             # emoji
        "tv": {"type": "string"},                              # screen mood
        "q": {"type": "string", "enum": ["keep", "add", "pause", "resume", "replace", "drop"]},
        "g": {"type": "string"},                               # goal
        "o": {"type": "boolean"},                              # override
        "p": {"type": "number"},                               # pause seconds
        "i": {"type": "integer"},                              # intensity
        "m": {"type": "object"},                               # mood meter updates
    },
}

# Priority-ordered keys for the reaction prompt. When the serialized context is over
# budget we drop *whole* low-priority keys from the end, so the model never receives a
# JSON object that was sliced mid-token (the previous behavior corrupted world state).
_REACTION_CONTEXT_PRIORITY = [
    "r", "creative_intent", "user_wellbeing", "goal", "act", "expr", "world", "activity", "pending_event",
    "user_instruction", "screen", "scene", "media", "window",
    "mood", "mood_top", "drive", "life_memory", "memory",
    "inner_thought_feed", "speech_max_words", "tiny_agent_skills",
]


def build_reaction_prompt(context: Dict[str, object], char_budget: int = 2600) -> str:
    """Serialize a compact, *always-valid* JSON view of the world for the reaction model.

    Selects decision-relevant keys in priority order and drops whole keys until the
    payload fits the budget, guaranteeing parseable JSON rather than a truncated blob.
    """
    payload: Dict[str, object] = {}
    for key in _REACTION_CONTEXT_PRIORITY:
        if key in context and context[key] not in (None, "", {}, []):
            payload[key] = context[key]
    # Include any remaining keys we did not explicitly prioritize, last.
    for key, value in context.items():
        if key not in payload and key not in {"compact_life_context_json"} and value not in (None, "", {}, []):
            payload[key] = value

    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(serialized) > char_budget and len(payload) > 4:
        # Drop the lowest-priority key still present (iterate from the end).
        for key in reversed(list(payload.keys())):
            if key not in {"r", "goal", "world", "mood"}:
                payload.pop(key, None)
                break
        else:
            break
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return serialized


def normalize_base_url(base_url: str) -> str:
    value = (base_url or "http://127.0.0.1:11434").strip().rstrip("/")
    if not value:
        value = "http://127.0.0.1:11434"
    if "://" not in value:
        value = "http://" + value
    for suffix in ("/api", "/api/", "/v1", "/v1/"):
        cleaned = suffix.rstrip("/")
        if value.endswith(cleaned):
            value = value[: -len(cleaned)]
            break
    return value.rstrip("/")


def candidate_base_urls(base_url: str) -> List[str]:
    base = normalize_base_url(base_url)
    candidates = [base]
    if "127.0.0.1" in base:
        candidates.append(base.replace("127.0.0.1", "localhost"))
    elif "localhost" in base:
        candidates.append(base.replace("localhost", "127.0.0.1"))
    else:
        candidates.extend(["http://127.0.0.1:11434", "http://localhost:11434"])
    unique: List[str] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def trim_history(messages: Sequence[Dict[str, str]], max_turn_messages: int = 8) -> List[Dict[str, str]]:
    clean: List[Dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role in {"user", "assistant"} and content:
            clean.append({"role": role, "content": content[:1800]})
    return clean[-max_turn_messages:]


def _looks_like_json(text: str) -> bool:
    s = text.strip()
    return s.startswith("{") or s.startswith("[") or '"b"' in s[:120] or "'b'" in s[:120]


def _extract_jsonish_speech(text: str) -> str:
    # Extract b/bubble from full or broken JSON without corrupting UTF-8 emoji.
    for pattern in [r'"b"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', r'"bubble"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"']:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            raw = match.group(1)
            try:
                return json.loads('"' + raw + '"')
            except Exception:
                return raw.replace('\\"', '"')
    # Partial JSON: {"b":"hello","a":... may be cut before final quote.
    partial = re.search(r'"(?:b|bubble|s|speech)"\s*:\s*"([^"\n\r]{1,180})', text, flags=re.DOTALL)
    if partial:
        return partial.group(1).split('"')[0].strip()
    return ""


def strip_narration_from_speech(text: str) -> str:
    """Clean controller leakage without cutting normal speech in half."""
    text = str(text or "").strip()
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    # Remove obvious stage-direction wrappers, but avoid deleting normal sentences.
    text = re.sub(r"\*[^*]{0,120}\*", "", text)
    text = re.sub(r"\[[^\]]{0,120}\]", "", text)
    # If a small model starts with narration and then a spoken line, keep the spoken part.
    text = re.sub(r"^\s*(while|as)\b[^.!?;,]{0,120}[,;:\-–—]+\s*", "", text, flags=re.IGNORECASE)
    lower = text.lower().strip()
    body_terms = ("eyebrow", "antenna", "posture", "chin", "hands", "claws", "treads", "tracks", "gaze")
    # Only hide when the whole line is clearly body-direction prose. Do not truncate mixed natural speech.
    if any(term in lower for term in body_terms) and len(lower.split()) > 8:
        parts = re.split(r"[:—–-]", text, maxsplit=1)
        if len(parts) == 2 and len(parts[1].split()) >= 2:
            return parts[1].strip(" \t\r\n-–—,:;")
        return ""
    return text.strip(" \t\r\n-–—,:;")

def compact_pet_line(text: str, max_words: int = 9, min_words: int = 1) -> str:
    text = strip_narration_from_speech(text)
    text = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE).strip()
    text = text.replace("\\n", " ").replace("/n", " ").strip()
    if text.strip().lower() in {"/", "\\", "n", "null", "none", "...", "…", "."}:
        return ""
    if _looks_like_json(text):
        extracted = _extract_jsonish_speech(text)
        if extracted:
            text = extracted
        else:
            return ""
    text = re.sub(r"[`*_#>\[\]{}]", "", text)
    if re.search(r'"[a-zA-Z_]{1,12}"\s*:', text) or re.search(r"'[a-zA-Z_]{1,12}'\s*:", text):
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text.lower() in {"/", "\\", "n", "null", "none", "...", "…", "."}:
        return ""
    max_words = max(4, min(24, int(max_words or 9)))

    def wc(s: str) -> int:
        return len([w for w in s.split() if w.strip()])

    candidates = [p.strip(" ,;:-") for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip(" ,;:-")]
    if not candidates:
        candidates = [text]
    for cand in candidates:
        if min_words <= wc(cand) <= max_words and len(cand) <= 120:
            return cand

    stop_end = {"and", "or", "but", "to", "for", "with", "of", "the", "a", "an", "is", "are", "was", "were", "be"}
    for sep in [",", ";", "—", "-"]:
        clause = text.split(sep, 1)[0].strip(" ,;:-")
        words = clause.split()
        if min_words <= len(words) <= max_words and words[-1].lower().strip(".,!?") not in stop_end:
            return clause if clause.endswith(("!", "?", ".")) else clause + "."

    # Reject overlong model text instead of displaying a half sentence.
    return ""



compact_pet_sentence = compact_pet_line


class OllamaClient:
    def __init__(self, config: OllamaConfig, personality: Optional[str] = None) -> None:
        self.config = config
        self.personality = personality or DEFAULT_PERSONALITY

    def chat(self, messages: Sequence[Dict[str, str]], image_b64: Optional[str] = None) -> str:
        user_messages = trim_history(messages)
        if image_b64 and user_messages:
            latest = dict(user_messages[-1])
            latest["images"] = [image_b64]
            user_messages[-1] = latest  # type: ignore[assignment]
        payload_messages: List[Dict[str, object]] = [
            {"role": "system", "content": self.personality + f"\nReply in under {self.config.speech_max_words} words. Vary wording."},
            *user_messages,  # type: ignore[list-item]
        ]
        try:
            raw = self._complete(payload_messages, max_tokens=min(120, int(self.config.max_tokens)), temperature=0.86)
        except OllamaError as exc:
            if image_b64 and any(k in str(exc).lower() for k in ["image", "vision", "multimodal", "unsupported"]):
                payload_messages = [
                    {"role": "system", "content": self.personality + f"\nReply in under {self.config.speech_max_words} words. Vary wording."},
                    *trim_history(messages),
                ]
                raw = self._complete(payload_messages, max_tokens=min(120, int(self.config.max_tokens)), temperature=0.86)
            else:
                raise
        return compact_pet_line(raw, self.config.speech_max_words, 1)

    def react(self, context: Dict[str, object], image_b64: Optional[str] = None) -> Dict[str, object]:
        prompt = build_reaction_prompt(context)

        def call(with_image: bool) -> str:
            user_message: Dict[str, object] = {"role": "user", "content": prompt}
            if with_image and image_b64:
                user_message["images"] = [image_b64]
            return self._complete(
                [
                    {"role": "system", "content": f"{self.personality}\n\n{REACTION_PERSONALITY}"},
                    user_message,
                ],
                max_tokens=min(160, int(self.config.max_tokens)),
                temperature=0.92,
                json_mode=True,
                schema=REACTION_SCHEMA,
            )

        try:
            raw = call(bool(image_b64))
        except OllamaError as exc:
            lower = str(exc).lower()
            if image_b64 and any(key in lower for key in ["image", "vision", "multimodal", "unsupported", "does not support"]):
                context["img"] = "unsupported; use summary"
                prompt = build_reaction_prompt(context)
                raw = call(False)
            else:
                raise
        return parse_reaction(raw, max_words=self.config.speech_max_words)

    def parse_reminder(self, user_text: str, now_iso: str) -> Dict[str, object]:
        prompt = (
            "Parse this reminder request, including a/an/one min, minute, secs/sec/mins/min/hours/tomorrow. Return JSON only. "
            "Schema: ok boolean, due_iso local datetime ISO, text reminder text. "
            "Use current local time exactly as reference. If unclear ok=false. "
            f"NOW={now_iso} USER={user_text!r}"
        )
        raw = self._complete(
            [
                {"role": "system", "content": "You parse reminder times. JSON only. No prose."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=140,
            temperature=0.05,
            json_mode=True,
        )
        try:
            data = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            data = json.loads(m.group(0)) if m else {}
        if not isinstance(data, dict):
            data = {}
        return {
            "ok": bool(data.get("ok")),
            "due_iso": str(data.get("due_iso", "")),
            "text": str(data.get("text", "")).strip(),
            "raw": raw,
        }

    def diagnose(self) -> Dict[str, object]:
        errors: List[str] = []
        for base in candidate_base_urls(self.config.base_url):
            url = base + "/api/tags"
            try:
                response = requests.get(url, timeout=6)
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue
            if response.status_code >= 400:
                errors.append(f"{url}: HTTP {response.status_code} {response.text[:180]}")
                continue
            try:
                data = response.json()
            except ValueError as exc:
                errors.append(f"{url}: bad JSON {exc}")
                continue
            models = [str(item.get("name", "")) for item in data.get("models", []) if isinstance(item, dict)]
            wanted = self.config.model.strip()
            found = wanted in models
            same_family = any(m.split(":")[0] == wanted.split(":")[0] for m in models)
            return {
                "ok": True,
                "base_url": base,
                "model": wanted,
                "model_found": found,
                "same_family_found": same_family,
                "models": models,
            }
        return {"ok": False, "errors": errors}

    def _complete(
        self,
        messages: Sequence[Dict[str, object]],
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
        schema: Optional[Dict[str, object]] = None,
    ) -> str:
        payload_base = {
            "model": self.config.model,
            "messages": list(messages),
            "stream": False,
            "think": bool(self.config.thinking_enabled),
            "keep_alive": "20m",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "repeat_penalty": 1.17,
                "top_p": 0.96,
            },
        }
        if json_mode:
            # Prefer a strict schema (structured outputs); fall back to plain "json"
            # mode and then no format at all if the runtime rejects either.
            payload_base["format"] = schema if schema is not None else "json"

        # Format fallback tiers: strict schema -> plain "json" -> no format.
        if not json_mode:
            format_tiers: List[object] = [None]
        elif schema is not None:
            format_tiers = [schema, "json", None]
        else:
            format_tiers = ["json", None]

        errors: List[str] = []
        tried_urls: List[str] = []
        for base in candidate_base_urls(self.config.base_url):
            url = base + "/api/chat"
            tried_urls.append(url)
            for fmt in format_tiers:
                allow_json = fmt is not None
                payload = dict(payload_base)
                if fmt is None:
                    payload.pop("format", None)
                else:
                    payload["format"] = fmt
                try:
                    response = requests.post(url, json=payload, timeout=self.config.timeout_seconds)
                except requests.Timeout:
                    # /api/tags can be reachable while /api/chat is still loading or generating.
                    # Do not try every localhost alias after a generation timeout; it only creates a long noisy error.
                    raise OllamaError(
                        f"Ollama reachable, but chat generation timed out after {self.config.timeout_seconds}s. "
                        "The model may be loading, busy, or too slow for this background tick."
                    )
                except requests.RequestException as exc:
                    errors.append(f"{url}: {exc}")
                    continue

                if response.status_code >= 400:
                    detail = response.text[:600]
                    try:
                        data = response.json()
                        detail = data.get("error", detail)
                    except ValueError:
                        pass
                    lower = detail.lower()
                    if allow_json and ("format" in lower or response.status_code == 400):
                        errors.append(f"{url}: JSON-mode retry ({detail[:160]})")
                        continue
                    if "model" in lower and ("not found" in lower or "pull" in lower):
                        raise OllamaError(f"Ollama reachable, but model '{self.config.model}' is missing. Run: ollama pull {self.config.model}.")
                    errors.append(f"{url}: HTTP {response.status_code} {detail}")
                    continue

                try:
                    data = response.json()
                    content = data.get("message", {}).get("content", "")
                except (ValueError, TypeError) as exc:
                    errors.append(f"{url}: unexpected response shape {exc}")
                    continue

                answer = str(content).strip()
                answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL | re.IGNORECASE).strip()
                if not answer:
                    errors.append(f"{url}: empty answer")
                    continue
                return answer

        detail = "; ".join(errors[-2:]) if errors else "no response"
        if any("connection" in e.lower() or "refused" in e.lower() for e in errors):
            raise OllamaError("Ollama chat endpoint is offline or refused the connection.")
        raise OllamaError(f"Ollama chat failed: {detail}")


DeepSeekError = OllamaError
DeepSeekConfig = OllamaConfig
DeepSeekClient = OllamaClient


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _first(data: Dict[str, object], *keys: str, default: object = "") -> object:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _keyword_action(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["basketball", "ball", "kick", "bounce"]):
        return "kick_ball"
    if any(k in t for k in ["butterfly", "flutter", "chase"]):
        return "chase_butterfly"
    if any(k in t for k in ["dump", "bin", "trash can", "dustbin"]):
        return "go_bin"
    if any(k in t for k in ["debris", "trash", "dust", "paper", "leaf", "clean", "collect", "sweep"]):
        return "clean"
    if any(k in t for k in ["tv", "sofa", "watch", "movie", "anime"]):
        return "watch_tv"
    if any(k in t for k in ["mouse", "cursor"]):
        return "inspect_mouse"
    if any(k in t for k in ["tree", "nature", "wind", "leaves"]):
        return "inspect"
    if any(k in t for k in ["dizzy", "spin"]):
        return "dizzy"
    if any(k in t for k in ["sing", "song", "hum", "music"]):
        return "sing"
    if any(k in t for k in ["roam", "wander", "patrol", "scoot"]):
        return "roam"
    if any(k in t for k in ["dance", "wiggle"]):
        return "dance"
    if any(k in t for k in ["nap", "sleep", "tired"]):
        return "nap"
    if any(k in t for k in ["throw", "toss"]):
        return "throw_trash"
    if any(k in t for k in ["move", "go", "inspect", "look"]):
        return "move_to"
    return "none"


def _keyword_target(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["basketball", "ball", "kick", "bounce"]):
        return "basketball"
    if any(k in t for k in ["butterfly", "flutter"]):
        return "butterfly"
    if any(k in t for k in ["bin", "dustbin", "trash can", "dump"]):
        return "trash_bin"
    if any(k in t for k in ["tv", "sofa", "movie", "anime"]):
        return "tv_sofa"
    if any(k in t for k in ["tree", "nature", "wind", "leaves"]):
        return "tree"
    if any(k in t for k in ["debris", "trash", "dust", "paper", "leaf", "clean", "collect", "sweep"]):
        return "nearest_debris"
    if any(k in t for k in ["mouse", "cursor"]):
        return "mouse"
    if "left" in t:
        return "left_edge"
    if "right" in t:
        return "right_edge"
    if "screen" in t:
        return "screen"
    if "random" in t:
        return "random"
    return "current"


def _norm_action(value: object, whole_text: str = "") -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return "none"
    action_map = {
        "idle": "chill", "pause": "pause", "inspect": "inspect", "investigate": "inspect", "look": "inspect",
        "clean": "clean", "collect": "clean", "pickup": "clean", "pick_up": "clean", "sweep": "clean",
        "dump": "go_bin", "bin": "go_bin", "go_bin": "go_bin", "trash_bin": "go_bin",
        "tv": "watch_tv", "playtv": "play_tv", "play_tv": "play_tv", "watch_tv": "watch_tv", "watch": "watch_tv",
        "chase": "chase_butterfly", "chase_butterfly": "chase_butterfly", "butterfly": "chase_butterfly",
        "mouse": "inspect_mouse", "inspect_mouse": "inspect_mouse", "cursor": "inspect_mouse",
        "dizzy": "dizzy", "wave": "wave", "dance": "dance", "sing": "sing", "song": "sing", "hum": "sing",
        "kick": "kick_ball", "kick_ball": "kick_ball", "basketball": "kick_ball", "ball": "kick_ball", "bounce": "kick_ball",
        "roam": "roam", "wander": "roam", "patrol": "roam", "nap": "nap", "sleep": "nap",
        "throw": "throw_trash", "toss": "throw_trash", "throw_trash": "throw_trash", "toss_trash": "throw_trash",
        "move": "move_to", "move_to": "move_to", "go": "move_to", "none": "none", "chill": "chill", "hide": "hide", "recharge": "recharge",
    }
    if raw in action_map:
        return action_map[raw]
    return _keyword_action(raw + " " + whole_text)


def _norm_target(value: object, whole_text: str = "") -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return _keyword_target(whole_text)
    target_map = {
        "debris": "nearest_debris", "trash": "nearest_debris", "dust": "nearest_debris", "paper": "nearest_debris", "leaf": "nearest_debris",
        "nearest_debris": "nearest_debris", "near_debris": "nearest_debris", "pile": "debris_pile", "debris_pile": "debris_pile",
        "bin": "trash_bin", "trash_bin": "trash_bin", "dustbin": "trash_bin", "trash_can": "trash_bin",
        "tv": "tv_sofa", "sofa": "tv_sofa", "tv_sofa": "tv_sofa", "couch": "tv_sofa",
        "butterfly": "butterfly", "flutter": "butterfly", "basketball": "basketball", "ball": "basketball",
        "mouse": "mouse", "cursor": "mouse", "screen": "screen",
        "left": "left_edge", "left_edge": "left_edge", "right": "right_edge", "right_edge": "right_edge",
        "tree": "tree", "tiny_tree": "tree", "nature": "tree", "leaves": "tree", "random": "random", "current": "current", "here": "current", "": "current", "none": "current",
    }
    if raw in target_map:
        return target_map[raw]
    return _keyword_target(raw + " " + whole_text)


def parse_reaction(raw: str, max_words: int = 9) -> Dict[str, object]:
    text = str(raw).replace("\\n", " ").replace("/n", " ").strip()
    if text.lower() in {"/", "\\", "n", "null", "none", "...", "…", "."}:
        return {
            "goal": "", "expression": "curious", "action": "none", "target": "current",
            "bubble": "", "intensity": 2, "pause_seconds": 0.0,
            "body": {"antenna": "relaxed", "eyes": "side", "eyebrow": "curious", "left_arm": "idle", "right_arm": "idle", "emoji": "none", "tv": "unchanged"},
            "tv_text": "", "queue": "keep", "mood": "", "override": False,
            "throw_trash": False, "raw": raw,
        }
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
    if not isinstance(data, dict):
        data = {}
    # Salvage common partial / malformed JSON pairs from small local models.
    if not data and _looks_like_json(text):
        salvaged: Dict[str, object] = {}
        for key, value in re.findall(r'"([a-zA-Z_]{1,12})"\s*:\s*"([^"\n\r]{0,160})', text):
            salvaged[key] = value.strip()
        for key, value in re.findall(r'"([a-zA-Z_]{1,12})"\s*:\s*([^,}\s]+)', text):
            if key not in salvaged:
                salvaged[key] = value.strip().strip('"')
        data = salvaged
    parsed_ok = isinstance(data, dict) and bool(data)

    whole = " ".join(str(x) for x in [text, data.get("g", ""), data.get("goal", ""), data.get("b", ""), data.get("bubble", "")])

    allowed_expressions = {
        "happy", "curious", "sleepy", "soft", "surprised", "thinking", "talking", "scared",
        "love", "excited", "watching", "cleaning", "proud", "error", "dizzy", "angry", "irritated", "frustrated"
    }
    expression_map = {
        "emotion": "curious", "joy": "happy", "cute": "love", "wow": "surprised",
        "surprise": "surprised", "clean": "cleaning", "focused": "thinking", "sad": "soft",
        "mad": "angry", "annoyed": "irritated"
    }
    expression = str(_first(data, "e", "expression", "emotion", default="")).strip().lower()
    if not expression:
        lower = whole.lower()
        if any(k in lower for k in ["angry", "mad", "tantrum"]):
            expression = "angry"
        elif any(k in lower for k in ["annoy", "irritat"]):
            expression = "irritated"
        elif any(k in lower for k in ["butterfly", "chase", "excited"]):
            expression = "excited"
        elif any(k in lower for k in ["trash", "dust", "clean"]):
            expression = "cleaning"
        elif any(k in lower for k in ["dizzy", "spin"]):
            expression = "dizzy"
        elif any(k in lower for k in ["love", "cute", "heart"]):
            expression = "love"
        else:
            expression = "curious"
    expression = expression_map.get(expression, expression)
    if expression not in allowed_expressions:
        expression = "curious"

    if parsed_ok:
        action = _norm_action(_first(data, "a", "action", default=""), whole)
        target = _norm_target(_first(data, "t", "target", default=""), whole)
    else:
        action = "none"
        target = "current"

    bubble_source = str(_first(data, "b", "bubble", "s", "speech", default="")).strip()
    if bubble_source:
        bubble = compact_pet_line(bubble_source, max_words, 1)
        if re.search(r'"[a-zA-Z_]{1,12}"\s*:', bubble):
            bubble = ""
    elif parsed_ok:
        bubble = ""
    else:
        bubble = compact_pet_line(_extract_jsonish_speech(text) or ("" if _looks_like_json(text) else text), max_words, 1)
    goal_raw = str(_first(data, "g", "goal", default="")).strip()
    goal = compact_pet_line(goal_raw, 8, 1) if goal_raw else ""

    try:
        intensity = max(1, min(5, int(_first(data, "i", "intensity", default=2))))
    except (TypeError, ValueError):
        intensity = 2
    try:
        pause_seconds = max(0, min(10, float(_first(data, "p", "pause_seconds", default=0))))
    except (TypeError, ValueError):
        pause_seconds = 0.0

    body_raw = data.get("body", {})
    body: Dict[str, str] = {}
    if isinstance(body_raw, dict):
        body.update({
            "antenna": str(_first(body_raw, "ant", "antenna", default="relaxed")).strip().lower(),
            "eyes": str(_first(body_raw, "eye", "eyes", default=target)).strip().lower(),
            "eyebrow": str(_first(body_raw, "brow", "eyebrow", "eyebrows", default=expression)).strip().lower(),
            "left_arm": str(_first(body_raw, "l", "left", "left_hand", "left_arm", default="idle")).strip().lower(),
            "right_arm": str(_first(body_raw, "r", "right", "right_hand", "right_arm", default="idle")).strip().lower(),
            "emoji": str(_first(body_raw, "emo", "emoji", default="none")).strip(),
            "tv": str(_first(body_raw, "tv", default="unchanged")).strip().lower(),
        })
    body["antenna"] = str(_first(data, "ant", "antenna", default=body.get("antenna", "relaxed"))).strip().lower()
    body["eyes"] = str(_first(data, "eye", "eyes", default=body.get("eyes", target))).strip().lower()
    body["eyebrow"] = str(_first(data, "brow", "eyebrow", "eyebrows", default=body.get("eyebrow", expression))).strip().lower()
    body["left_arm"] = str(_first(data, "l", "left", "left_arm", default=body.get("left_arm", "idle"))).strip().lower()
    body["right_arm"] = str(_first(data, "r", "right", "right_arm", default=body.get("right_arm", "idle"))).strip().lower()
    body["emoji"] = str(_first(data, "emo", "emoji", default=body.get("emoji", "none"))).strip()
    body["tv"] = str(_first(data, "tv", "tv_text", default=body.get("tv", "unchanged"))).strip().lower()

    tv_text = str(_first(data, "tv", "tv_text", default=body.get("tv", ""))).strip().lower()[:16]

    return {
        "goal": goal,
        "expression": expression,
        "action": action,
        "target": target,
        "bubble": bubble,
        "intensity": intensity,
        "pause_seconds": pause_seconds,
        "body": body,
        "tv_text": tv_text,
        "queue": str(_first(data, "q", "queue", default="keep")).strip().lower() or "keep",
        "mood": _first(data, "m", "mood", default=""),
        "override": _safe_bool(_first(data, "o", "override", default=False)),
        "throw_trash": _safe_bool(data.get("throw_trash", data.get("throw", action == "throw_trash"))),
        "raw": raw,
    }
