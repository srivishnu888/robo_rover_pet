"""Durable, restart-surviving memory for the pet.

The live app keeps short rolling buffers in RAM (action_memory, recent_pet_lines,
moods). Before this module those were wiped on every restart, so Wally could never
build a relationship. PetMemoryStore snapshots that state to a small JSON file and
restores it on launch, and tracks a lightweight long-term "relationship" summary
(how many sessions, how long, how much he's said) that the brain can reference to
feel like it actually remembers the user.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


MEMORY_VERSION = 1


class PetMemoryStore:
    def __init__(self, config_dir: Path) -> None:
        self.path = Path(config_dir) / f"pet_memory_v{MEMORY_VERSION}.json"
        self._data: Dict[str, object] = {}
        self._last_save_at = 0.0

    # ------------------------------------------------------------------ load
    def load(self) -> Dict[str, object]:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = raw
        except Exception:
            # Corrupt or unreadable snapshot must never block startup.
            self._data = {}
        return self._data

    def get_action_memory(self) -> List[Dict[str, object]]:
        items = self._data.get("action_memory", [])
        return [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []

    def get_recent_pet_lines(self) -> List[str]:
        items = self._data.get("recent_pet_lines", [])
        return [str(x) for x in items] if isinstance(items, list) else []

    def get_moods(self) -> Dict[str, float]:
        moods = self._data.get("moods", {})
        out: Dict[str, float] = {}
        if isinstance(moods, dict):
            for key, value in moods.items():
                try:
                    out[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        return out

    def relationship(self) -> Dict[str, object]:
        rel = self._data.get("relationship", {})
        return rel if isinstance(rel, dict) else {}

    # ---------------------------------------------------------- running gags
    def get_gags(self) -> List[str]:
        gags = self._data.get("gags", [])
        return [str(x) for x in gags] if isinstance(gags, list) else []

    def add_gag(self, line: str) -> None:
        """Remember a memorable/funny line so Wally can call back to it later."""
        line = str(line or "").strip()
        if len(line) < 8 or len(line) > 90:
            return
        gags = self.get_gags()
        low = line.lower()
        if any(low == g.lower() for g in gags):
            return
        gags.append(line)
        self._data["gags"] = gags[-24:]

    def random_gag(self) -> str:
        import random as _r
        gags = self.get_gags()
        return _r.choice(gags) if gags else ""

    # ------------------------------------------------------- user patterns
    def note_pattern(self, window_title: str, daypart: str) -> None:
        """Quietly learn the user's habits: which apps, what time of day."""
        patterns = self._data.get("user_patterns")
        if not isinstance(patterns, dict):
            patterns = {"windows": {}, "dayparts": {}}
        windows = patterns.setdefault("windows", {})
        dayparts = patterns.setdefault("dayparts", {})
        key = str(window_title or "").strip()[:48]
        if key:
            windows[key] = int(windows.get(key, 0)) + 1
            if len(windows) > 60:  # keep only the busiest apps
                patterns["windows"] = dict(sorted(windows.items(), key=lambda kv: kv[1], reverse=True)[:40])
        if daypart:
            dayparts[daypart] = int(dayparts.get(daypart, 0)) + 1
        self._data["user_patterns"] = patterns

    def top_patterns(self) -> Dict[str, object]:
        patterns = self._data.get("user_patterns", {})
        if not isinstance(patterns, dict):
            return {}
        windows = patterns.get("windows", {})
        dayparts = patterns.get("dayparts", {})
        top_windows = sorted(windows.items(), key=lambda kv: kv[1], reverse=True)[:3] if isinstance(windows, dict) else []
        top_daypart = max(dayparts.items(), key=lambda kv: kv[1])[0] if isinstance(dayparts, dict) and dayparts else ""
        return {
            "favorite_apps": [w for w, _ in top_windows],
            "usual_time": top_daypart,
        }

    def relationship_context(self) -> Dict[str, object]:
        """Compact, model-friendly view of the long-term bond, for the brain context."""
        rel = self.relationship()
        first_seen = str(rel.get("first_seen_iso", "") or "")
        days_known = 0
        if first_seen:
            try:
                days_known = max(0, (datetime.now() - datetime.fromisoformat(first_seen)).days)
            except Exception:
                days_known = 0
        sessions = int(rel.get("sessions", 0) or 0)
        return {
            "sessions": sessions,
            "days_known": days_known,
            "minutes_together": int(rel.get("total_minutes", 0) or 0),
            "lines_spoken_total": int(rel.get("lines_spoken", 0) or 0),
            "returning_friend": sessions > 1,
            "bond_stage": self.bond_stage(),
            "patterns": self.top_patterns(),
        }

    def note_active_day(self) -> Dict[str, object]:
        """Track daily rhythm: returns whether this is a new day and the day streak.

        Lets Wally greet each new day, notice how long you've been gone, and build a
        consecutive-day streak — the backbone of feeling like a daily companion."""
        from datetime import date

        rel = dict(self.relationship())
        today = date.today().isoformat()
        last = str(rel.get("last_active_date", "") or "")
        streak = int(rel.get("day_streak", 0) or 0)
        days_since = 0
        new_day = last != today
        if new_day:
            if last:
                try:
                    days_since = (date.today() - date.fromisoformat(last)).days
                except Exception:
                    days_since = 0
                streak = streak + 1 if days_since == 1 else 1
            else:
                streak = 1
            rel["last_active_date"] = today
            rel["day_streak"] = streak
            rel["best_streak"] = max(int(rel.get("best_streak", 0) or 0), streak)
            self._data["relationship"] = rel
        return {"new_day": new_day, "streak": streak, "days_since_last": days_since, "best_streak": int(rel.get("best_streak", streak))}

    def bond_stage(self) -> str:
        """How close Wally feels, so his tone can grow from shy to old-friend."""
        rel = self.relationship()
        sessions = int(rel.get("sessions", 0) or 0)
        if sessions <= 1:
            return "just_met"
        if sessions <= 4:
            return "warming_up"
        if sessions <= 10:
            return "friends"
        if sessions <= 25:
            return "close_friends"
        return "inseparable"

    def mark_session_start(self) -> None:
        rel = dict(self.relationship())
        now_iso = datetime.now().isoformat(timespec="seconds")
        rel["sessions"] = int(rel.get("sessions", 0) or 0) + 1
        rel.setdefault("first_seen_iso", now_iso)
        rel["last_seen_iso"] = now_iso
        self._data["relationship"] = rel
        self._session_started_at = time.time()

    # ------------------------------------------------------------------ save
    def save(
        self,
        *,
        action_memory: List[Dict[str, object]],
        recent_pet_lines: List[str],
        moods: Dict[str, float],
        lines_spoken_delta: int = 0,
        force: bool = False,
        min_interval_seconds: float = 20.0,
    ) -> None:
        now = time.time()
        if not force and (now - self._last_save_at) < min_interval_seconds:
            return
        self._last_save_at = now

        rel = dict(self.relationship())
        rel["last_seen_iso"] = datetime.now().isoformat(timespec="seconds")
        started = getattr(self, "_session_started_at", None)
        if started is not None:
            session_minutes = (now - started) / 60.0
            rel["total_minutes"] = round(float(rel.get("total_minutes", 0) or 0) + session_minutes, 1)
            self._session_started_at = now
        if lines_spoken_delta:
            rel["lines_spoken"] = int(rel.get("lines_spoken", 0) or 0) + int(lines_spoken_delta)

        self._data = {
            "version": MEMORY_VERSION,
            "action_memory": list(action_memory)[-48:],
            "recent_pet_lines": list(recent_pet_lines)[-24:],
            "moods": {k: round(float(v), 1) for k, v in moods.items()},
            "relationship": rel,
            # Preserve accumulated long-term state (gags / learned habits) across saves.
            "gags": self.get_gags(),
            "user_patterns": self._data.get("user_patterns", {}),
        }
        try:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=0), encoding="utf-8")
            tmp.replace(self.path)  # atomic on the same filesystem
        except Exception:
            # Persistence is best-effort; never crash the pet over a failed write.
            pass

    def clear(self) -> None:
        self._data = {}
        try:
            if self.path.exists():
                self.path.unlink()
        except Exception:
            pass
