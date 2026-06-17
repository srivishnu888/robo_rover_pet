from __future__ import annotations

import base64
import json
import math
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QBuffer,
    QIODevice,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSettings,
    QThread,
    QTimer,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import banter, companion
from .llm import DEFAULT_PERSONALITY, OllamaClient, OllamaConfig, OllamaError, compact_pet_sentence
from .persistence import PetMemoryStore


ORG_NAME = "LocalDesktopPets"
APP_NAME = "RoboRoverPetV8_37"
BASE_W = 340
BASE_H = 285
DEFAULT_SCALE_PERCENT = 33

RIVET_INNER_THOUGHTS = [
    "what shall I do now?",
    "where should I roll next?",
    "is that dust mocking me?",
    "the ball looks kickable.",
    "maybe the sofa misses me.",
    "that butterfly owes me a race.",
    "should I inspect the mouse?",
    "can I make human smile?",
    "tiny patrol feels important.",
    "what is the screen hiding?",
    "is the trash plotting again?",
    "I could sing badly.",
    "maybe I should pretend I am busy.",
    "human typing sounds suspicious.",
    "I want to chase something shiny.",
    "do I deserve a TV break?",
    "that corner looks too quiet.",
    "maybe lunch exists somewhere.",
    "I should check the wind.",
    "the tree seems dramatic today.",
    "I could be helpful or annoying.",
    "the basketball is staring at me.",
    "maybe the mouse wants attention.",
    "what if I clean one tiny spot?",
    "what if I do absolutely nothing?",
    "I should look cute strategically.",
    "the taskbar is my kingdom.",
    "screen vibes need inspection.",
    "maybe I should encourage human.",
    "maybe I should roast gently.",
    "today needs a tiny adventure.",
    "should I be noble or naughty?",
    "I feel a small mischief coming.",
    "maybe I should ask a question.",
    "the bin looks smug.",
    "I should not become a trash robot.",
    "play first, clean later maybe.",
    "what would a brave rover do?",
    "I hear invisible keyboard rain.",
    "butterflies are suspiciously fancy.",
    "maybe human needs a break.",
    "I could patrol like a legend.",
    "that dust has attitude.",
    "maybe I am the drama.",
    "should I kick the orange moon?",
    "I might nap professionally.",
    "the screen looks serious.",
    "I need a tiny mission.",
    "can I be chaotic but adorable?",
    "maybe I should just blink wisely.",
    "shall I sing a tiny song?",
    "should I remember a joke?",
    "should I tell a joke?",
    "what funny fact can I steal?",
    "can I make a tiny pun?",
    "should I hum dramatically?",
    "is this a joke moment?",
    "maybe a silly fact helps.",
    "can I roast the screen gently?",
    "should I compliment human now?",
    "maybe I should ask about lunch.",
    "can I invent a tiny song?",
    "should I tell a useless fact?",
    "is this keyboard rain musical?",
    "should I toss trash for attention?",
    "can I kick the ball now?",
    "if I mention the ball, I should touch it.",
    "if butterfly appears, I should notice it.",
    "should I chase only if I see it?",
    "no imaginary thieves, only real screen things.",
    "what real thing is near me?",
    "maybe I should act before joking.",
    "does the sofa need guarding?",
    "can I make chaos responsibly?",
    "should I throw and then clean?",
    "should I stop talking and do something?",
    "is that EVA in the sky?",
    "EVA flew by again?",
    "should I chase EVA dramatically?",
    "if EVA leaves, maybe kick sadness into the ball.",
    "butterflies can fix heartbreak, right?",
]


TINY_AGENT_SKILLS = [
    {"name": "set_reminder", "cost": "local_first_llm_fallback", "examples": ["remind me in 10 secs to test", "remind me at 5pm to call"]},
    {"name": "list_reminders", "cost": "local", "examples": ["list reminders"]},
    {"name": "clear_reminders", "cost": "local", "examples": ["clear reminders"]},
    {"name": "throw_attention_trash", "cost": "local", "examples": ["throw trash for attention"]},
    {"name": "kick_ball", "cost": "local", "examples": ["kick the ball", "play basketball"]},
    {"name": "summon_butterfly", "cost": "local", "examples": ["send butterfly"]},
    {"name": "summon_wind", "cost": "local", "examples": ["send wind", "send leaves"]},
    {"name": "clean_debris", "cost": "local", "examples": ["clean", "clean this mess"]},
    {"name": "watch_tv", "cost": "local", "examples": ["watch tv"]},
]



@dataclass
class RuntimeConfig:
    api_key: str
    model: str
    base_url: str
    max_tokens: int
    thinking_enabled: bool
    tts_enabled: bool
    always_on_top: bool
    roam_enabled: bool
    taskbar_only: bool
    debris_enabled: bool
    weather_enabled: bool
    screen_awareness_enabled: bool
    screenshot_reactions_enabled: bool
    ai_reactions_enabled: bool
    pet_scale_percent: int
    reaction_min_minutes: int
    reaction_max_minutes: int
    speech_max_words: int
    work_trash_enabled: bool
    eva_speed_percent: int
    eva_duration_seconds: int
    personality: str


@dataclass
class DebrisItem:
    x: float
    y: float
    kind: str
    size: float
    rotation: float
    settled_y: float
    color: str
    vx: float = 0.0
    vy: float = 0.0
    settled: bool = False
    age: int = 0


@dataclass
class Puff:
    x: float
    y: float
    life: float
    size: float
    kind: str = "dust"


@dataclass
class FlyingTrash:
    x: float
    y: float
    vx: float
    vy: float
    rotation: float
    vr: float
    life: float
    kind: str
    size: float


@dataclass
class Basketball:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    spin: float = 0.0
    visible: bool = True
    last_kicked_at: float = 0.0
    last_super_kick_at: float = 0.0
    last_kick_style: str = "none"
    wall_hits: int = 0


@dataclass
class WeatherCloud:
    x: float
    y: float
    scale: float
    vx: float
    alpha: int


@dataclass
class RainDrop:
    x: float
    y: float
    length: float
    speed: float


@dataclass
class Puddle:
    x: float
    y: float
    width: float
    depth: float
    alpha: float


@dataclass
class MudTrail:
    x: float
    y: float
    width: float
    alpha: float
    age: float = 0.0



@dataclass
class ReminderItem:
    due_ts: float
    text: str
    created_ts: float
    source: str = "user"
    id: str = ""




class SettingsStore:
    def __init__(self) -> None:
        self.settings = QSettings(ORG_NAME, APP_NAME)
        base = os.environ.get("ROBO_ROVER_CONFIG_DIR")
        self.config_dir = Path(base) if base else Path.home() / ".robo_rover_pet"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / "settings_v8_37.json"
        self.file_values: Dict[str, object] = self._load_file_values()

    def _load_file_values(self) -> Dict[str, object]:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_file_values(self) -> None:
        try:
            tmp = self.config_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.file_values, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.config_path)
        except Exception:
            # QSettings still persists values if the JSON file cannot be written.
            pass

    def _value(self, key: str, default):
        if key in self.file_values:
            return self.file_values[key]
        value = self.settings.value(key, default)
        return default if value is None else value

    def string(self, key: str, default: str = "") -> str:
        value = self._value(key, default)
        if value is None:
            return default
        return str(value)

    def integer(self, key: str, default: int) -> int:
        try:
            return int(self._value(key, default))
        except (TypeError, ValueError):
            return default

    def boolean(self, key: str, default: bool) -> bool:
        value = self._value(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).lower() in {"1", "true", "yes", "on"}

    def set_value(self, key: str, value) -> None:
        self.file_values[key] = value
        self.settings.setValue(key, value)
        self.settings.sync()
        self._save_file_values()

    def flush(self) -> None:
        self.settings.sync()
        self._save_file_values()

    def config(self) -> RuntimeConfig:
        min_minutes = max(1, self.integer("awareness/reaction_min_minutes", 2))
        max_minutes = max(min_minutes, self.integer("awareness/reaction_max_minutes", 5))
        return RuntimeConfig(
            api_key=self.string("ollama/api_key", ""),
            model=self.string("ollama/model", "ministral-3:3b"),
            base_url=self.string("ollama/base_url", os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"),
            max_tokens=self.integer("ollama/max_tokens", 220),
            thinking_enabled=self.boolean("ollama/thinking_enabled", False),
            tts_enabled=self.boolean("pet/tts_enabled", False),
            always_on_top=self.boolean("pet/always_on_top", True),
            roam_enabled=self.boolean("pet/roam_enabled", True),
            taskbar_only=self.boolean("pet/taskbar_only", True),
            debris_enabled=self.boolean("pet/debris_enabled", True),
            weather_enabled=self.boolean("pet/weather_enabled", True),
            screen_awareness_enabled=self.boolean("awareness/screen_awareness_enabled", True),
            screenshot_reactions_enabled=self.boolean("awareness/screenshot_reactions_enabled", True),
            ai_reactions_enabled=self.boolean("awareness/ai_reactions_enabled", True),
            pet_scale_percent=max(25, min(100, self.integer("pet/scale_percent", DEFAULT_SCALE_PERCENT))),
            reaction_min_minutes=min_minutes,
            reaction_max_minutes=max_minutes,
            speech_max_words=max(4, min(24, self.integer("pet/speech_max_words", 12))),
            work_trash_enabled=self.boolean("pet/work_trash_enabled", True),
            eva_speed_percent=max(100, min(400, self.integer("pet/eva_speed_percent", 250))),
            eva_duration_seconds=max(10, min(90, self.integer("pet/eva_duration_seconds", 38))),
            personality=self.string("pet/personality", DEFAULT_PERSONALITY),
        )

class SettingsDialog(QDialog):
    @staticmethod
    def _available_ollama_models() -> List[str]:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        models: List[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("name "):
                continue
            name = line.split()[0].strip()
            if name and name not in models:
                models.append(name)
        return models

    def __init__(self, store: SettingsStore, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Taskbar Rover Settings · v8.4 living brain")
        self.setMinimumWidth(620)

        cfg = store.config()

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Not required for local Ollama")
        self.api_key_edit.setText("")
        self.api_key_edit.setEnabled(False)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        detected_models = self._available_ollama_models()
        fallback_models = [
            "ministral-3:3b",
            "qwen3-vl:2b",
            "qwen2.5:1.5b-instruct",
            "smollm2:1.7b-instruct",
            "gemma2:2b",
            "phi3:mini",
            "llama3.2:3b",
        ]
        model_items: List[str] = []
        for model_name in [cfg.model, *detected_models, *fallback_models]:
            if model_name and model_name not in model_items:
                model_items.append(model_name)
        self.model_combo.addItems(model_items)
        self.model_combo.setCurrentText(cfg.model)
        self.model_combo.setToolTip(
            "Detected local Ollama models are listed first when `ollama list` is available. "
            "You can still type any model tag manually."
        )

        self.base_url_edit = QLineEdit(cfg.base_url)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(cfg.max_tokens)

        self.thinking_checkbox = QCheckBox("Enable thinking traces (OFF by default; slower)")
        self.thinking_checkbox.setChecked(cfg.thinking_enabled)

        self.tts_checkbox = QCheckBox("Enable cute robot voice sounds (pyttsx3 fallback)")
        self.tts_checkbox.setChecked(cfg.tts_enabled)

        self.top_checkbox = QCheckBox("Keep pet always on top")
        self.top_checkbox.setChecked(cfg.always_on_top)

        self.roam_checkbox = QCheckBox("Let pet move around")
        self.roam_checkbox.setChecked(cfg.roam_enabled)

        self.taskbar_checkbox = QCheckBox("Keep movement on the taskbar / dock lane only")
        self.taskbar_checkbox.setChecked(cfg.taskbar_only)

        self.debris_checkbox = QCheckBox("Spawn leaves, paper, and dust for the pet to clean")
        self.debris_checkbox.setChecked(cfg.debris_enabled)

        self.weather_checkbox = QCheckBox("Enable tiny weather ambience like clouds, sun, rain, and puddles")
        self.weather_checkbox.setChecked(cfg.weather_enabled)

        self.ai_reactions_checkbox = QCheckBox("Let Ollama control goals, movement, body language, and emotions")
        self.ai_reactions_checkbox.setChecked(cfg.ai_reactions_enabled)

        self.awareness_checkbox = QCheckBox("React to mouse movement, typing, and scrolling")
        self.awareness_checkbox.setChecked(cfg.screen_awareness_enabled)

        self.screenshot_checkbox = QCheckBox("Send screenshots to Ollama vision model for screen reactions")
        self.screenshot_checkbox.setChecked(cfg.screenshot_reactions_enabled)
        self.screenshot_checkbox.setToolTip(
            "Turn this OFF when using text-only models. Leave it ON only for vision-capable models "
            "such as qwen3-vl or other VL/vision tags."
        )

        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(25, 100)
        self.scale_spin.setSuffix("%")
        self.scale_spin.setValue(cfg.pet_scale_percent)
        self.scale_spin.setToolTip("33% is the default; increase only if you want bigger expressions.")

        self.speech_words_spin = QSpinBox()
        self.speech_words_spin.setRange(4, 24)
        self.speech_words_spin.setSuffix(" words")
        self.speech_words_spin.setValue(cfg.speech_max_words)
        self.speech_words_spin.setToolTip("Max words in Wally's bubbles and Ollama speech.")

        self.work_trash_checkbox = QCheckBox("Typing makes mess pile up; Wally may tantrum when overworked")
        self.work_trash_checkbox.setChecked(cfg.work_trash_enabled)

        self.eva_speed_spin = QSpinBox()
        self.eva_speed_spin.setRange(100, 400)
        self.eva_speed_spin.setSingleStep(25)
        self.eva_speed_spin.setSuffix("%")
        self.eva_speed_spin.setValue(cfg.eva_speed_percent)
        self.eva_speed_spin.setToolTip("EVA flyby speed. 250% is about 2-3x faster than the original flyby.")

        self.eva_duration_spin = QSpinBox()
        self.eva_duration_spin.setRange(10, 90)
        self.eva_duration_spin.setSuffix(" sec")
        self.eva_duration_spin.setValue(cfg.eva_duration_seconds)
        self.eva_duration_spin.setToolTip("How long EVA stays on screen during a flyby.")

        self.react_min_spin = QSpinBox()
        self.react_min_spin.setRange(1, 120)
        self.react_min_spin.setSuffix(" min")
        self.react_min_spin.setValue(cfg.reaction_min_minutes)

        self.react_max_spin = QSpinBox()
        self.react_max_spin.setRange(1, 240)
        self.react_max_spin.setSuffix(" min")
        self.react_max_spin.setValue(cfg.reaction_max_minutes)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("from"))
        interval_row.addWidget(self.react_min_spin)
        interval_row.addWidget(QLabel("to"))
        interval_row.addWidget(self.react_max_spin)
        interval_row.addStretch(1)

        self.personality_edit = QTextEdit()
        self.personality_edit.setPlainText(cfg.personality)
        self.personality_edit.setMinimumHeight(135)

        security_hint = QLabel(
            "Privacy/security: this build is local-Ollama first. When screenshot reactions are enabled, "
            "the app sends an occasional resized screenshot to your local Ollama server only, not to a cloud API."
        )
        security_hint.setWordWrap(True)
        security_hint.setStyleSheet("color: #6a6a6a;")

        form = QFormLayout()
        form.addRow("Local Ollama", self.api_key_edit)
        model_label = f"Model ({len(detected_models)} local)" if detected_models else "Model"
        form.addRow(model_label, self.model_combo)
        form.addRow("Base URL", self.base_url_edit)
        form.addRow("Max answer tokens", self.max_tokens_spin)
        form.addRow("Pet size", self.scale_spin)
        form.addRow("Bubble word limit", self.speech_words_spin)
        form.addRow("", self.work_trash_checkbox)
        form.addRow("EVA flyby speed", self.eva_speed_spin)
        form.addRow("EVA flyby time", self.eva_duration_spin)
        form.addRow("Scene reaction interval", interval_row)
        form.addRow("", self.thinking_checkbox)
        form.addRow("", self.tts_checkbox)
        form.addRow("", self.top_checkbox)
        form.addRow("", self.roam_checkbox)
        form.addRow("", self.taskbar_checkbox)
        form.addRow("", self.debris_checkbox)
        form.addRow("", self.weather_checkbox)
        form.addRow("", self.ai_reactions_checkbox)
        form.addRow("", self.awareness_checkbox)
        form.addRow("", self.screenshot_checkbox)
        form.addRow("Personality", self.personality_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(security_hint)
        layout.addWidget(buttons)

    def accept(self) -> None:
        min_minutes = self.react_min_spin.value()
        max_minutes = max(min_minutes, self.react_max_spin.value())
        self.store.set_value("ollama/api_key", self.api_key_edit.text().strip())
        self.store.set_value("ollama/model", self.model_combo.currentText().strip() or "ministral-3:3b")
        self.store.set_value("ollama/base_url", self.base_url_edit.text().strip() or "http://127.0.0.1:11434")
        self.store.set_value("ollama/max_tokens", self.max_tokens_spin.value())
        self.store.set_value("ollama/thinking_enabled", self.thinking_checkbox.isChecked())
        self.store.set_value("pet/tts_enabled", self.tts_checkbox.isChecked())
        self.store.set_value("pet/always_on_top", self.top_checkbox.isChecked())
        self.store.set_value("pet/roam_enabled", self.roam_checkbox.isChecked())
        self.store.set_value("pet/taskbar_only", self.taskbar_checkbox.isChecked())
        self.store.set_value("pet/debris_enabled", self.debris_checkbox.isChecked())
        self.store.set_value("pet/weather_enabled", self.weather_checkbox.isChecked())
        self.store.set_value("pet/scale_percent", self.scale_spin.value())
        self.store.set_value("pet/speech_max_words", self.speech_words_spin.value())
        self.store.set_value("pet/work_trash_enabled", self.work_trash_checkbox.isChecked())
        self.store.set_value("pet/eva_speed_percent", self.eva_speed_spin.value())
        self.store.set_value("pet/eva_duration_seconds", self.eva_duration_spin.value())
        self.store.set_value("awareness/ai_reactions_enabled", self.ai_reactions_checkbox.isChecked())
        self.store.set_value("awareness/screen_awareness_enabled", self.awareness_checkbox.isChecked())
        self.store.set_value("awareness/screenshot_reactions_enabled", self.screenshot_checkbox.isChecked())
        self.store.set_value("awareness/reaction_min_minutes", min_minutes)
        self.store.set_value("awareness/reaction_max_minutes", max_minutes)
        self.store.set_value("pet/personality", self.personality_edit.toPlainText().strip() or DEFAULT_PERSONALITY)
        super().accept()


class ChatDialog(QDialog):
    send_message = Signal(str)
    settings_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chat with Robo Rover")
        self.setMinimumSize(540, 430)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Robo Rover is waiting for a question...")

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Ask Rover anything...")
        self.input_line.returnPressed.connect(self._send)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self._send)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.settings_requested.emit)

        row = QHBoxLayout()
        row.addWidget(self.input_line, 1)
        row.addWidget(self.send_button)
        row.addWidget(self.settings_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.transcript, 1)
        layout.addLayout(row)

    def _send(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self.send_message.emit(text)

    def append_user(self, text: str) -> None:
        self.transcript.append(f"<p><b>You:</b> {html_escape(text)}</p>")
        self._scroll_to_bottom()

    def append_pet(self, text: str) -> None:
        safe = html_escape(text).replace("\n", "<br>")
        self.transcript.append(f"<p><b>Rover:</b> {safe}</p>")
        self._scroll_to_bottom()

    def set_busy(self, busy: bool) -> None:
        self.input_line.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        if busy:
            self.transcript.append("<p><i>Rover is thinking...</i></p>")
            self._scroll_to_bottom()

    def focus_input(self) -> None:
        self.input_line.setFocus(Qt.OtherFocusReason)

    def _scroll_to_bottom(self) -> None:
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class ChatWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, config: RuntimeConfig, history: List[Dict[str, str]], image_b64: Optional[str] = None) -> None:
        super().__init__()
        self.config = config
        self.history = history
        self.image_b64 = image_b64

    def run(self) -> None:
        try:
            ds_config = OllamaConfig(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                max_tokens=self.config.max_tokens,
                thinking_enabled=self.config.thinking_enabled,
                timeout_seconds=28 if self.image_b64 else 18,
                speech_max_words=self.config.speech_max_words,
            )
            client = OllamaClient(ds_config, personality=self.config.personality)
            answer = client.chat(self.history, image_b64=self.image_b64)
        except OllamaError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # Keep GUI alive even on unexpected failures.
            self.failed.emit(f"Unexpected error: {exc}")
        else:
            self.finished_ok.emit(answer)


class ReactionWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, config: RuntimeConfig, context: Dict[str, object], image_b64: Optional[str] = None) -> None:
        super().__init__()
        self.config = config
        self.context = context
        self.image_b64 = image_b64

    def run(self) -> None:
        try:
            ds_config = OllamaConfig(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                max_tokens=min(180, self.config.max_tokens),
                thinking_enabled=False,
                timeout_seconds=30 if self.image_b64 else 16,
                speech_max_words=self.config.speech_max_words,
            )
            client = OllamaClient(ds_config, personality=self.config.personality)
            decision = client.react(self.context, image_b64=self.image_b64)
        except OllamaError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Reaction error: {exc}")
        else:
            self.finished_ok.emit(decision)


class OllamaStatusWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, config: RuntimeConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            ds_config = OllamaConfig(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                max_tokens=80,
                thinking_enabled=False,
                timeout_seconds=10,
                speech_max_words=self.config.speech_max_words,
            )
            client = OllamaClient(ds_config, personality=self.config.personality)
            status = client.diagnose()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(status)


class ReminderParseWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, config: RuntimeConfig, user_text: str, now_iso: str) -> None:
        super().__init__()
        self.config = config
        self.user_text = user_text
        self.now_iso = now_iso

    def run(self) -> None:
        try:
            ds_config = OllamaConfig(
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                max_tokens=140,
                thinking_enabled=False,
                timeout_seconds=6,
                speech_max_words=self.config.speech_max_words,
            )
            client = OllamaClient(ds_config, personality=self.config.personality)
            result = client.parse_reminder(self.user_text, self.now_iso)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(result)



class BubbleWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.text = ""
        self.source = "static"
        self.setFixedSize(330, 92)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_message(self, text: str, anchor: QRect, duration_ms: int, source: str = "static") -> None:
        self.text = shorten_for_bubble(text, max_len=175)
        self.source = (source or "static").strip().lower()
        self.reposition(anchor)
        self.show()
        self.raise_()
        self.timer.start(duration_ms)
        self.update()

    def reposition(self, anchor: QRect) -> None:
        screen = QApplication.screenAt(anchor.center()) or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        x = anchor.center().x() - self.width() // 2
        x = max(geo.left() + 8, min(x, geo.right() - self.width() - 8))
        y = anchor.top() - self.height() - 8
        if y < geo.top() + 8:
            y = anchor.bottom() + 8
        y = max(geo.top() + 8, min(y, geo.bottom() - self.height() - 8))
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        body = QRectF(6, 6, self.width() - 12, self.height() - 16)
        path = QPainterPath()
        path.addRoundedRect(body, 18, 18)
        path.moveTo(self.width() / 2 - 12, body.bottom() - 1)
        path.lineTo(self.width() / 2, self.height() - 5)
        path.lineTo(self.width() / 2 + 12, body.bottom() - 1)
        path.closeSubpath()
        p.setBrush(QColor(255, 255, 245, 240))
        p.setPen(QPen(QColor(72, 63, 43, 145), 1.2))
        p.drawPath(path)

        # Source dot: blue=Ollama, green=tool/skill, gray=static/local, red=error.
        dot_color = {
            "ollama": QColor(62, 146, 255, 230),
            "ai": QColor(62, 146, 255, 230),
            "tool": QColor(42, 178, 94, 230),
            "skill": QColor(42, 178, 94, 230),
            "user": QColor(147, 112, 219, 230),
            "error": QColor(230, 65, 55, 235),
            "static": QColor(125, 125, 125, 210),
        }.get(self.source, QColor(125, 125, 125, 210))
        p.setBrush(dot_color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(body.left() + 13, body.top() + 13), 5.2, 5.2)

        p.setPen(QColor(35, 35, 35))
        font = QFont("Arial", 10)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        p.drawText(QRectF(18, 12, self.width() - 36, self.height() - 28), Qt.TextWordWrap | Qt.AlignVCenter, self.text)



class ReminderAlertWindow(QWidget):
    """Reminder placard overlay: Wally holds a card instead of a scary popup."""

    def __init__(self) -> None:
        super().__init__()
        self.message = ""
        self.phase = 0
        self.beep_count = 0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.flash_timer = QTimer(self)
        self.flash_timer.setInterval(220)
        self.flash_timer.timeout.connect(self._tick)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_alert(self, message: str, pet_rect: Optional[QRect] = None, duration_ms: int = 24000) -> None:
        screen = QApplication.screenAt(pet_rect.center()) if pet_rect else QApplication.primaryScreen()
        screen = screen or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()

        # Placard size: visible, but not scam-popup huge.
        w = min(520, max(380, int(geo.width() * 0.30)))
        h = 280
        if pet_rect and pet_rect.isValid():
            desired_x = pet_rect.center().x() - w // 2
            # Sit above Wally, with the stick visually reaching down toward him.
            desired_y = pet_rect.top() - h + int(pet_rect.height() * 0.45)
            x = max(geo.left() + 8, min(desired_x, geo.right() - w - 8))
            y = max(geo.top() + 8, min(desired_y, geo.bottom() - h - 8))
        else:
            x = geo.center().x() - w // 2
            y = int(geo.top() + geo.height() * 0.28)

        self.setGeometry(x, y, w, h)
        self.message = shorten_for_bubble(message, max_len=165)
        self.phase = 0
        self.beep_count = 0
        self.show()
        self.raise_()
        self.flash_timer.start()
        self.hide_timer.start(duration_ms)
        self.update()

    def _tick(self) -> None:
        self.phase += 1
        # Gentle bells, not alarm-siren spam.
        if self.beep_count < 5 and self.phase % 4 == 0:
            QApplication.beep()
            self.beep_count += 1
        self.update()

    def hideEvent(self, event) -> None:  # noqa: N802
        self.flash_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self.message:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()
        jiggle = math.sin(self.phase * 0.55) * 2.0

        # Stick behind the placard, reaching down toward Wally.
        stick_x = w * 0.50 + math.sin(self.phase * 0.35) * 3
        p.setPen(QPen(QColor(116, 74, 42, 235), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(stick_x, h - 18), QPointF(stick_x, h * 0.56))

        # Card/placard.
        card = QRectF(28, 30 + jiggle, w - 56, h * 0.54)
        p.setBrush(QColor(255, 249, 214, 248))
        p.setPen(QPen(QColor(148, 82, 28, 240), 4))
        p.drawRoundedRect(card, 18, 18)

        # Red "ALERT" header but not full red-window.
        header = QRectF(card.left() + 14, card.top() + 10, card.width() - 28, 36)
        p.setBrush(QColor(255, 235, 210, 235))
        p.setPen(QPen(QColor(210, 28, 28, 240), 2))
        p.drawRoundedRect(header, 12, 12)

        p.setPen(QColor(205, 0, 0))
        title = QFont("Arial", 18)
        title.setWeight(QFont.Weight.Black)
        p.setFont(title)
        p.drawText(header, Qt.AlignCenter, "🔔 REMINDER 🔔")

        # Message in red text.
        body = QFont("Arial", 16)
        body.setWeight(QFont.Weight.Bold)
        p.setFont(body)
        p.setPen(QColor(185, 0, 0))
        p.drawText(
            QRectF(card.left() + 18, card.top() + 54, card.width() - 36, card.height() - 66),
            Qt.TextWordWrap | Qt.AlignCenter,
            self.message,
        )

        # Bell doodles on the top corners.
        bell_color = QColor(246, 184, 56, 245)
        p.setBrush(bell_color)
        p.setPen(QPen(QColor(138, 83, 18, 230), 2))
        for bx in (card.left() + 20, card.right() - 42):
            by = card.top() - 8 + (2 if self.phase % 2 else 0)
            p.drawEllipse(QRectF(bx, by, 28, 24))
            p.drawRoundedRect(QRectF(bx + 5, by + 18, 18, 7), 4, 4)
            p.setBrush(QColor(137, 83, 20, 230))
            p.drawEllipse(QRectF(bx + 11, by + 25, 6, 6))
            p.setBrush(bell_color)

        # Tiny motion lines / whistles.
        p.setPen(QPen(QColor(215, 64, 44, 180), 2, Qt.SolidLine, Qt.RoundCap))
        for ox in (12, w - 22):
            p.drawLine(QPointF(ox, card.top() + 24), QPointF(ox + (12 if ox < w/2 else -12), card.top() + 12))
            p.drawLine(QPointF(ox, card.top() + 48), QPointF(ox + (12 if ox < w/2 else -12), card.top() + 48))



class BigParachuteOverlay(QWidget):
    """Separate overlay so the parachute is not clipped by the tiny pet window."""

    def __init__(self) -> None:
        super().__init__()
        self.phase = 0.0
        self.anchor_x_ratio = 0.5
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.hide()

    def show_for_pet(self, pet_rect: QRect, phase: float) -> None:
        if pet_rect.isNull() or not pet_rect.isValid():
            return
        self.phase = phase
        screen = QApplication.screenAt(pet_rect.center()) or QApplication.primaryScreen()
        geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        # Large but not screen-dominating: about 3x rover width.
        overlay_w = max(300, int(pet_rect.width() * 3.15))
        overlay_h = max(165, int(pet_rect.height() * 2.35))
        desired_x = pet_rect.center().x() - overlay_w // 2
        x = max(geo.left() + 4, min(desired_x, geo.right() - overlay_w - 4))
        # The overlay overlaps the pet window down to the body harness, so the strings attach visibly.
        attach_into_body = int(pet_rect.height() * 0.66)
        desired_y = pet_rect.top() - overlay_h + attach_into_body
        y = max(geo.top() + 4, desired_y)
        self.anchor_x_ratio = (pet_rect.center().x() - x) / max(1, overlay_w)
        self.setGeometry(x, y, overlay_w, overlay_h)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()
        h = self.height()
        phase = math.sin(self.phase * 2.1)
        anchor_x = max(w * 0.22, min(w * 0.78, w * self.anchor_x_ratio))
        attach_y = h - 10

        # Large umbrella/parachute dome with a deeper arc.
        left = w * 0.07
        right = w * 0.93
        top = h * 0.07 + phase * 2.0
        lip = h * 0.46 + phase * 2.0
        center = w * 0.50
        path = QPainterPath()
        path.moveTo(left, lip)
        path.cubicTo(w * 0.20, top - h * 0.18, w * 0.80, top - h * 0.18, right, lip)
        # scalloped lower umbrella edge
        scallop_w = (right - left) / 6.0
        x = right
        for i in range(6):
            nx = right - (i + 1) * scallop_w
            mid = (x + nx) / 2.0
            path.quadTo(mid, lip + h * 0.13, nx, lip)
            x = nx
        path.closeSubpath()
        grad = QLinearGradient(QPointF(left, top), QPointF(right, lip + h * 0.12))
        grad.setColorAt(0.0, QColor(255, 245, 157, 238))
        grad.setColorAt(0.45, QColor(255, 193, 96, 238))
        grad.setColorAt(1.0, QColor(255, 111, 78, 238))
        p.setBrush(grad)
        p.setPen(QPen(QColor(114, 71, 43, 210), 2.2))
        p.drawPath(path)

        # Canopy ribs.
        p.setPen(QPen(QColor(129, 80, 46, 120), 1.4))
        for r in [0.18, 0.30, 0.42, 0.58, 0.70, 0.82]:
            sx = left + (right - left) * r
            p.drawLine(QPointF(center, top + h * 0.08), QPointF(sx, lip - h * 0.02))

        # Long suspension strings to make it clearly hang away from the rover.
        p.setPen(QPen(QColor(80, 66, 56, 205), 1.35, Qt.SolidLine, Qt.RoundCap))
        string_points = [
            (left + (right-left)*0.10, lip - 2),
            (left + (right-left)*0.24, lip + h * 0.04),
            (left + (right-left)*0.38, lip + h * 0.02),
            (left + (right-left)*0.50, lip + h * 0.055),
            (left + (right-left)*0.62, lip + h * 0.02),
            (left + (right-left)*0.76, lip + h * 0.04),
            (left + (right-left)*0.90, lip - 2),
        ]
        harness_points = [
            (anchor_x - w * 0.16, attach_y),
            (anchor_x - w * 0.10, attach_y - h * 0.02),
            (anchor_x - w * 0.05, attach_y),
            (anchor_x, attach_y - h * 0.025),
            (anchor_x + w * 0.05, attach_y),
            (anchor_x + w * 0.10, attach_y - h * 0.02),
            (anchor_x + w * 0.16, attach_y),
        ]
        for (sx, sy), (ex, ey) in zip(string_points, harness_points):
            p.drawLine(QPointF(sx, sy), QPointF(ex, ey))

        # Lower harness clearly overlaps the rover body so the chute looks attached.
        p.setBrush(QColor(85, 70, 58, 205))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(anchor_x - w * 0.105, attach_y - 6, w * 0.21, 7), 3, 3)
        p.setPen(QPen(QColor(62, 49, 40, 200), 1.45, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(anchor_x - w * 0.045, attach_y), QPointF(anchor_x - w * 0.020, h - 1))
        p.drawLine(QPointF(anchor_x + w * 0.045, attach_y), QPointF(anchor_x + w * 0.020, h - 1))




class MiniChatBar(QWidget):
    send_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Talk to Wally")
        self.setFixedSize(268, 38)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("ask/action: watch tv, clean…")
        self.input_line.returnPressed.connect(self._send)
        self.input_line.setStyleSheet(
            "QLineEdit { background: rgba(255,255,246,235); border: 1px solid rgba(75,58,33,130); "
            "border-radius: 12px; padding: 5px 8px; color: #2c2b26; font-size: 12px; }"
        )
        self.send_button = QPushButton("➜")
        self.send_button.setFixedWidth(34)
        self.send_button.clicked.connect(self._send)
        self.send_button.setStyleSheet(
            "QPushButton { background: rgba(255,190,65,240); border: 1px solid rgba(92,57,18,150); "
            "border-radius: 12px; font-weight: bold; } QPushButton:hover { background: rgba(255,213,92,250); }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(5, 4, 5, 4)
        row.setSpacing(5)
        row.addWidget(self.input_line, 1)
        row.addWidget(self.send_button)

    def _send(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self.send_message.emit(text)

    def show_near_lane(self, lane: QRect) -> None:
        self.reposition(QPoint(lane.left() + self.width() // 2, lane.center().y()), lane)

    def reposition(self, anchor: QPoint, lane: QRect) -> None:
        """Keep chat in the toolbar/taskbar area so it does not cover the TV/sofa prop."""
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        if not screen:
            return
        full = screen.geometry()
        avail = screen.availableGeometry()
        bottom_gap = max(0, full.bottom() - avail.bottom())
        top_gap = max(0, avail.top() - full.top())
        left_gap = max(0, avail.left() - full.left())
        right_gap = max(0, full.right() - avail.right())
        gaps = {"bottom": bottom_gap, "top": top_gap, "left": left_gap, "right": right_gap}
        orientation = max(gaps, key=gaps.get)
        gap = gaps[orientation]

        if lane.isValid():
            x = max(lane.left() + 10, min(anchor.x() + 72, lane.right() - self.width() - 10))
        else:
            x = anchor.x() + 72

        if orientation == "bottom" and gap >= 8:
            # Inside the taskbar itself, below the red edge line. User said this can occupy toolbar space.
            y = avail.bottom() + max(2, (gap - self.height()) // 2)
            x = max(full.left() + 8, min(x, full.right() - self.width() - 8))
        elif orientation == "top" and gap >= 8:
            y = full.top() + max(2, (gap - self.height()) // 2)
            x = max(full.left() + 8, min(x, full.right() - self.width() - 8))
        elif orientation == "left" and gap >= 8:
            x = full.left() + max(2, (gap - self.width()) // 2)
            y = max(full.top() + 8, min(anchor.y(), full.bottom() - self.height() - 8))
        elif orientation == "right" and gap >= 8:
            x = avail.right() + max(2, (gap - self.width()) // 2)
            y = max(full.top() + 8, min(anchor.y(), full.bottom() - self.height() - 8))
        elif lane.isValid():
            # Auto-hide taskbar fallback: keep it in the edge lane, not over the TV/sofa.
            y = lane.bottom() - self.height() - 2
        else:
            y = anchor.y() - 42

        x = max(full.left() + 6, min(x, full.right() - self.width() - 6))
        y = max(full.top() + 6, min(y, full.bottom() - self.height() - 6))
        self.move(x, y)
        if not self.isVisible():
            self.show()
        self.raise_()

    def set_busy(self, busy: bool) -> None:
        self.input_line.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        if busy:
            self.input_line.setPlaceholderText("hmm!")
        else:
            self.input_line.setPlaceholderText("ask/action: watch tv, clean…")


class AttentionOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.particles: List[FlyingTrash] = []
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def fling_from(self, start: QPoint, count: int = 9) -> None:
        screen = QApplication.screenAt(start) or QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.geometry()
        self.setGeometry(geo)
        sx = start.x() - geo.left()
        sy = start.y() - geo.top()
        cx = geo.width() * 0.5
        cy = geo.height() * 0.45
        self.particles.clear()
        for _ in range(count):
            vx = (cx - sx) / random.uniform(38, 58) + random.uniform(-3.0, 3.0)
            vy = (cy - sy) / random.uniform(34, 54) + random.uniform(-5.0, -1.0)
            self.particles.append(FlyingTrash(
                x=sx + random.uniform(-12, 12),
                y=sy + random.uniform(-12, 12),
                vx=vx,
                vy=vy,
                rotation=random.uniform(0, 360),
                vr=random.uniform(-9, 9),
                life=random.uniform(2.4, 4.3),
                kind=random.choice(["paper", "leaf", "dust", "paper"]),
                size=random.uniform(8, 18),
            ))
        self.show()
        self.raise_()
        self.timer.start()
        self.update()

    def _tick(self) -> None:
        keep: List[FlyingTrash] = []
        for item in self.particles:
            item.life -= 0.033
            item.vy += 0.10
            item.vx *= 0.996
            item.x += item.vx
            item.y += item.vy
            item.rotation += item.vr
            if item.life > 0 and item.y < self.height() + 30:
                keep.append(item)
        self.particles = keep
        if not self.particles:
            self.timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self.particles:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for item in self.particles:
            alpha = max(0, min(230, int(230 * min(1.0, item.life / 1.4))))
            p.save()
            p.translate(item.x, item.y)
            p.rotate(item.rotation)
            if item.kind == "leaf":
                path = QPainterPath()
                s = item.size
                path.moveTo(0, -s * 0.55)
                path.cubicTo(s * 0.75, -s * 0.35, s * 0.9, s * 0.35, 0, s * 0.65)
                path.cubicTo(-s * 0.9, s * 0.35, -s * 0.75, -s * 0.35, 0, -s * 0.55)
                p.setBrush(QColor(130, 150, 60, alpha))
                p.setPen(QPen(QColor(65, 72, 30, alpha), 1.0))
                p.drawPath(path)
            elif item.kind == "dust":
                p.setBrush(QColor(150, 132, 105, min(alpha, 150)))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(0, 0), item.size * 0.45, item.size * 0.28)
            else:
                s = item.size
                path = QPainterPath()
                path.moveTo(-s * 0.7, -s * 0.45)
                path.lineTo(s * 0.45, -s * 0.58)
                path.lineTo(s * 0.7, s * 0.35)
                path.lineTo(-s * 0.4, s * 0.58)
                path.closeSubpath()
                p.setBrush(QColor(246, 239, 212, alpha))
                p.setPen(QPen(QColor(159, 144, 110, alpha), 1.0))
                p.drawPath(path)
            p.restore()


class DebrisOverlay(QWidget):
    def __init__(self, store: SettingsStore) -> None:
        super().__init__()
        self.store = store
        self.items: List[DebrisItem] = []
        self.puffs: List[Puff] = []
        self.spawn_paused = False  # co-watch pauses new clutter
        self.wind = 0.0
        self.butterfly_visible = False
        self.butterfly_x = 0.0
        self.butterfly_y = 0.0
        self.butterfly_vx = 0.9
        self.butterfly_phase = 0.0
        self.butterfly_end_at = 0.0
        self.eva_visible = False
        self.eva_x = 0.0
        self.eva_y = 0.0
        self.eva_vx = 0.0
        self.eva_phase = 0.0
        self.eva_end_at = 0.0
        self.eva_base_y = 0.0
        self.eva_turns_left = 0
        self.eva_next_mid_turn_at = 0.0
        self.eva_last_turn_reason = "none"
        self.eva_name = "EVA"
        self.ball = Basketball(142.0, 72.0, visible=True)
        self._ball_centered_once = False
        self.ball_phase = 0.0
        self.tv_mode = "static"
        self.tv_phase = 0.0
        self.tree_phase = 0.0
        self.wind_phase = random.uniform(0, math.tau)
        self.vertical_wind = 0.0
        self.wind_gust_until = 0.0
        self.last_gust_pile_at = 0.0
        self.next_wind_window_at = time.time() + random.uniform(18, 35)
        self.wind_piles_remaining = 0
        self.next_wind_pile_at = 0.0
        self.weather_enabled = bool(self.store.config().weather_enabled)
        self.weather_mode = random.choice(["sunny", "cloudy", "windy"])
        self.weather_mode_until = time.time() + random.uniform(45, 90)
        self.daylight_override = ""
        self.sun_phase = random.uniform(0, math.tau)
        self.cloud_flow_dir = 1 if random.random() < 0.5 else -1
        self.clouds: List[WeatherCloud] = []
        self.rain_drops: List[RainDrop] = []
        self.puddles: List[Puddle] = []
        self.mud_trails: List[MudTrail] = []
        self.mud_cleaner_visible = False
        self.mud_cleaner_x = 0.0
        self.mud_cleaner_y = 0.0
        self.mud_cleaner_phase = random.uniform(0, math.tau)
        self.mud_cleaner_state = "hidden"
        self.mud_cleaner_exit_dir = 1
        self._last_mud_trail_at = 0.0
        self.enabled = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.timer = QTimer(self)
        # 70ms keeps motion smooth enough while reducing idle CPU a little.
        self.timer.setInterval(70)
        self.timer.timeout.connect(self._tick)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            if not self.timer.isActive():
                self.timer.start()
            self.show()
        else:
            self.hide()

    def set_weather_enabled(self, enabled: bool) -> None:
        self.weather_enabled = bool(enabled)
        if not self.weather_enabled:
            self.rain_drops = []
            self.puddles = []
        else:
            self.weather_mode_until = min(self.weather_mode_until, time.time() + 2.0)
        self.update()

    def set_weather_mode(self, mode: str, duration_seconds: float = 90.0) -> None:
        mode = (mode or "").strip().lower()
        if mode not in {"sunny", "cloudy", "windy", "rainy"}:
            return
        self.weather_enabled = True
        self.weather_mode = mode
        self.weather_mode_until = time.time() + max(20.0, float(duration_seconds))
        self.cloud_flow_dir = 1 if random.random() < 0.5 else -1
        w = max(1, self.width())
        h = max(1, self.height())
        if mode == "cloudy":
            self.clouds = []
            for idx in range(7):
                direction = self.cloud_flow_dir
                self.clouds.append(WeatherCloud(
                    x=random.uniform(36.0, max(40.0, w - 36.0)),
                    y=random.uniform(42, max(44, min(h * 0.30, 98))),
                    scale=random.uniform(0.78, 1.18),
                    vx=random.uniform(0.24, 0.50) * direction,
                    alpha=random.randint(126, 166),
                ))
        if mode in {"cloudy", "rainy"}:
            target = 7 if mode == "cloudy" else 5
            while len(self.clouds) < target:
                direction = self.cloud_flow_dir
                start_x = random.uniform(-110, -28) if direction > 0 else random.uniform(w + 28, w + 110)
                self.clouds.append(WeatherCloud(
                    x=start_x,
                    y=random.uniform(42, max(44, min(h * 0.30, 98))),
                    scale=random.uniform(0.78, 1.18 if mode == "cloudy" else 1.20),
                    vx=random.uniform(0.22, 0.48) * direction,
                    alpha=random.randint(128, 176 if mode == "cloudy" else 156),
                ))
        if mode == "windy":
            self.wind_gust_until = max(self.wind_gust_until, time.time() + random.uniform(3.0, 5.5))
        if mode == "rainy" and len(self.puddles) < 2:
            for _ in range(2 - len(self.puddles)):
                self.puddles.append(Puddle(
                    x=random.uniform(54.0, max(55.0, w - 54.0)),
                    y=h - 14.0,
                    width=random.uniform(26.0, 44.0),
                    depth=random.uniform(6.0, 10.0),
                    alpha=random.uniform(0.26, 0.38),
                ))
        self.update()

    def set_daylight_override(self, phase: str) -> None:
        phase = (phase or "").strip().lower()
        self.daylight_override = phase if phase in {"dawn", "day", "dusk", "night"} else ""
        self.weather_enabled = True
        self.update()

    def set_lane(self, lane: QRect) -> None:
        if lane.isNull() or not lane.isValid():
            return
        # Tall enough for TV/sofa plus visible wind paths through the lower screen.
        # Kept capped for performance; this is a nature strip, not a full-screen particle engine.
        screen = QApplication.screenAt(lane.center()) or QApplication.primaryScreen()
        screen_h = screen.geometry().height() if screen else 900
        height = max(lane.height(), min(380, max(240, int(screen_h * 0.30))))
        adjusted = QRect(lane.left(), lane.bottom() - height + 1, lane.width(), height)
        if adjusted != self.geometry():
            self.setGeometry(adjusted)
            if not self._ball_centered_once:
                self.ball.x = max(32, self.width() * 0.50)
                self.ball.y = max(20, self.height() - 17)
                self._ball_centered_once = True
            self.update()

    def _seed_weather_scene(self, w: int, h: int) -> None:
        if self.clouds:
            return
        for idx in range(random.randint(4, 6)):
            direction = self.cloud_flow_dir
            start_x = random.uniform(-90, -22) if direction > 0 else random.uniform(w + 22, w + 90)
            self.clouds.append(WeatherCloud(
                x=start_x,
                y=random.uniform(42, max(44, min(h * 0.30, 96))),
                scale=random.uniform(0.74, 1.18),
                vx=random.uniform(0.18, 0.42) * direction,
                alpha=random.randint(102, 148),
            ))

    def _choose_next_weather_mode(self) -> str:
        current = str(getattr(self, "weather_mode", "sunny"))
        weights = {
            "sunny": (["sunny", "cloudy", "windy", "rainy"], [4, 4, 2, 1]),
            "cloudy": (["sunny", "cloudy", "windy", "rainy"], [3, 4, 2, 2]),
            "windy": (["sunny", "cloudy", "windy", "rainy"], [2, 3, 4, 1]),
            "rainy": (["sunny", "cloudy", "windy", "rainy"], [2, 4, 2, 2]),
        }
        modes, probs = weights.get(current, (["sunny", "cloudy", "windy", "rainy"], [3, 4, 2, 1]))
        return random.choices(modes, weights=probs, k=1)[0]

    def _daylight_phase(self) -> str:
        override = str(getattr(self, "daylight_override", "") or "")
        if override:
            return override
        now_dt = datetime.now()
        minute_of_day = now_dt.hour * 60 + now_dt.minute
        if 5 * 60 <= minute_of_day < 7 * 60:
            return "dawn"
        if 7 * 60 <= minute_of_day < 18 * 60:
            return "day"
        if 18 * 60 <= minute_of_day < 20 * 60:
            return "dusk"
        return "night"

    def _celestial_progress(self) -> Tuple[str, float]:
        override = str(getattr(self, "daylight_override", "") or "")
        if override == "dawn":
            return "sun", 0.10
        if override == "day":
            return "sun", 0.50
        if override == "dusk":
            return "sun", 0.90
        if override == "night":
            return "moon", 0.50
        now_dt = datetime.now()
        minute_of_day = now_dt.hour * 60 + now_dt.minute + now_dt.second / 60.0
        if 5 * 60 <= minute_of_day < 20 * 60:
            span = (20 - 5) * 60
            progress = (minute_of_day - 5 * 60) / float(span)
            return "sun", max(0.0, min(1.0, progress))
        if minute_of_day < 5 * 60:
            minute_of_day += 24 * 60
        span = (29 - 20) * 60
        progress = (minute_of_day - 20 * 60) / float(span)
        return "moon", max(0.0, min(1.0, progress))

    def weather_status(self) -> Dict[str, object]:
        geo = self.geometry()
        body_kind, body_progress = self._celestial_progress()
        w = max(1, self.width())
        body_x = geo.left() + 36 + (w - 72) * body_progress
        arch = math.sin(max(0.0, min(1.0, body_progress)) * math.pi)
        body_y = geo.top() + 26 + (1.0 - arch) * 28
        cloud_positions = [
            [round(geo.left() + cloud.x, 1), round(geo.top() + cloud.y, 1), round(cloud.scale, 2)]
            for cloud in self.clouds[:5]
        ]
        puddle_positions = [
            [round(geo.left() + puddle.x, 1), round(geo.top() + puddle.y, 1), round(puddle.width, 1)]
            for puddle in self.puddles[:4]
        ]
        cleaner_xy = None
        if self.mud_cleaner_visible:
            cleaner_xy = [round(geo.left() + self.mud_cleaner_x, 1), round(geo.top() + self.mud_cleaner_y, 1)]
        return {
            "enabled": bool(self.weather_enabled),
            "mode": self.weather_mode,
            "daylight": self._daylight_phase(),
            "celestial": {
                "kind": body_kind,
                "progress": round(body_progress, 3),
                "global_xy": [round(body_x, 1), round(body_y, 1)],
            },
            "cloud_count": len(self.clouds),
            "clouds": cloud_positions,
            "puddle_count": len(self.puddles),
            "puddles": puddle_positions,
            "mud_trail_count": len(self.mud_trails),
            "mud_cleaner": {
                "visible": bool(self.mud_cleaner_visible),
                "global_xy": cleaner_xy,
                "state": str(getattr(self, "mud_cleaner_state", "hidden")),
                "mood_hint": "tiny fussy rain cleaner scrubbing Wally's mud trails" if self.mud_cleaner_visible else "gone",
            },
            "rain_active": self.weather_mode == "rainy",
            "wind_strength": round(float(self.wind), 2),
        }

    def nearest_puddle_global_to(self, global_x: int, global_y: int) -> Optional[QPoint]:
        if not self.puddles:
            return None
        geo = self.geometry()
        best = min(
            self.puddles,
            key=lambda puddle: abs((geo.left() + puddle.x) - global_x) + 0.35 * abs((geo.top() + puddle.y) - global_y),
        )
        return QPoint(int(geo.left() + best.x), int(geo.top() + best.y))

    def _puddle_contains_local(self, local_x: float, local_y: float, x_pad: float = 0.0, y_pad: float = 0.0) -> bool:
        for puddle in self.puddles:
            if abs(local_x - puddle.x) <= (puddle.width * 0.88 + x_pad) and abs(local_y - puddle.y) <= (puddle.depth + y_pad):
                return True
        return False

    def add_mud_trail_global(self, global_x: int, global_y: int) -> bool:
        if not self.weather_enabled or self.weather_mode != "rainy":
            return False
        now = time.time()
        if now - self._last_mud_trail_at < 0.34:
            return False
        geo = self.geometry()
        x = max(22.0, min(max(24.0, self.width() - 22.0), global_x - geo.left()))
        y = max(16.0, min(max(18.0, self.height() - 10.0), global_y - geo.top() - 5.0))
        if self.mud_trails and abs(self.mud_trails[-1].x - x) < 13:
            return False
        self._last_mud_trail_at = now
        self.mud_trails.append(MudTrail(
            x=x + random.uniform(-6.0, 6.0),
            y=y + random.uniform(-2.5, 2.5),
            width=random.uniform(10.0, 20.0),
            alpha=random.uniform(0.34, 0.52),
        ))
        self.mud_trails = self.mud_trails[-26:]
        self.update()
        return True

    def mud_cleaner_point_global(self) -> Optional[QPoint]:
        if not self.mud_cleaner_visible:
            return None
        geo = self.geometry()
        return QPoint(int(geo.left() + self.mud_cleaner_x), int(geo.top() + self.mud_cleaner_y))

    def _reset_rain_drop(self, drop: RainDrop, w: int, h: int) -> None:
        drop.x = random.uniform(20, max(22, w - 20))
        drop.y = random.uniform(-max(24.0, h * 0.30), -8.0)
        drop.length = random.uniform(7.0, 14.0)
        drop.speed = random.uniform(7.0, 11.8)

    def _update_weather(self, w: int, h: int, now: float, base_flow: float) -> None:
        if not self.weather_enabled:
            return
        self._seed_weather_scene(w, h)
        self.sun_phase += 0.018
        target_clouds = 7 if self.weather_mode == "cloudy" else (5 if self.weather_mode == "rainy" else (4 if self.weather_mode == "windy" else 3))
        while len(self.clouds) < target_clouds:
            direction = self.cloud_flow_dir
            start_x = random.uniform(-110, -28) if direction > 0 else random.uniform(w + 28, w + 110)
            self.clouds.append(WeatherCloud(
                x=start_x,
                y=random.uniform(42, max(44, min(h * 0.30, 98))),
                scale=random.uniform(0.78, 1.24),
                vx=random.uniform(0.20, 0.46) * direction,
                alpha=random.randint(112, 168 if self.weather_mode == "cloudy" else 148),
            ))
        if now >= self.weather_mode_until:
            self.weather_mode = self._choose_next_weather_mode()
            self.weather_mode_until = now + random.uniform(50, 95)
            if self.weather_mode == "windy":
                self.wind_gust_until = max(self.wind_gust_until, now + random.uniform(2.8, 5.2))
        for cloud in self.clouds:
            drift = cloud.vx + base_flow * (0.40 if self.weather_mode != "rainy" else 0.24)
            if self.weather_mode == "windy":
                drift += self.wind * 0.70
            elif self.weather_mode == "cloudy":
                drift += self.wind * 0.22
            cloud.x += drift
            cloud.y += 0.16 * math.sin(self.sun_phase + cloud.scale + cloud.x * 0.01)
            limit = cloud.scale * 42
            if cloud.x > w + limit:
                cloud.x = random.uniform(-limit - 64, -limit - 12)
                cloud.y = random.uniform(42, max(44, min(h * 0.30, 96)))
                cloud.vx = abs(cloud.vx) * self.cloud_flow_dir
            elif cloud.x < -limit:
                cloud.x = random.uniform(w + limit + 12, w + limit + 64)
                cloud.y = random.uniform(42, max(44, min(h * 0.30, 96)))
                cloud.vx = abs(cloud.vx) * self.cloud_flow_dir
        if self.weather_mode == "rainy":
            target_drops = 14
            while len(self.rain_drops) < target_drops:
                drop = RainDrop(0.0, 0.0, 9.0, 8.5)
                self._reset_rain_drop(drop, w, h)
                self.rain_drops.append(drop)
            for drop in self.rain_drops:
                drop.y += drop.speed
                drop.x += self.wind * 0.9 + base_flow * 0.35
                if drop.y >= h - 18:
                    if random.random() < 0.16 and len(self.puddles) < 4:
                        self.puddles.append(Puddle(
                            x=max(36.0, min(w - 36.0, drop.x + random.uniform(-16.0, 16.0))),
                            y=h - 14.0,
                            width=random.uniform(22.0, 42.0),
                            depth=random.uniform(5.0, 10.0),
                            alpha=random.uniform(0.26, 0.42),
                        ))
                    self._reset_rain_drop(drop, w, h)
        else:
            self.rain_drops = []
        kept_puddles: List[Puddle] = []
        for puddle in self.puddles:
            if self.weather_mode == "rainy":
                puddle.alpha = min(0.56, puddle.alpha + 0.012)
                puddle.width = min(54.0, puddle.width + 0.06)
            else:
                puddle.alpha -= 0.0028
                puddle.width *= 0.9993
            puddle.x = max(28.0, min(w - 28.0, puddle.x + self.wind * 0.08))
            if puddle.alpha > 0.05:
                kept_puddles.append(puddle)
        self.puddles = kept_puddles
        self._update_mud_cleaner(w, h, now)

    def _update_mud_cleaner(self, w: int, h: int, now: float) -> None:
        floor_y = max(22.0, h - 17.0)
        rainy = self.weather_mode == "rainy"
        for trail in self.mud_trails:
            trail.age += 1
            if rainy:
                trail.alpha = min(0.56, trail.alpha)
            else:
                trail.alpha = min(0.56, trail.alpha)
        if not rainy and not self.mud_trails:
            if self.mud_cleaner_visible and self.mud_cleaner_state != "exit":
                self.mud_cleaner_state = "exit"
                self.mud_cleaner_exit_dir = -1 if self.mud_cleaner_x < w * 0.5 else 1
            elif not self.mud_cleaner_visible:
                return
        if self.mud_trails and not self.mud_cleaner_visible:
            self.mud_cleaner_visible = True
            self.mud_cleaner_state = "enter"
            from_left = random.random() < 0.5
            self.mud_cleaner_exit_dir = 1 if from_left else -1
            self.mud_cleaner_x = -52.0 if from_left else w + 52.0
            self.mud_cleaner_y = floor_y - 18.0
        if not self.mud_cleaner_visible:
            return
        self.mud_cleaner_phase += 0.12
        self.mud_cleaner_y = floor_y - 18.0 + 1.6 * math.sin(self.mud_cleaner_phase)
        if self.mud_cleaner_state == "exit":
            self.mud_cleaner_x += max(4.2, min(6.4, 5.0 + len(self.mud_trails) * 0.05)) * self.mud_cleaner_exit_dir
            if self.mud_cleaner_x < -58.0 or self.mud_cleaner_x > w + 58.0:
                self.mud_cleaner_visible = False
                self.mud_cleaner_state = "hidden"
            return
        target = max(self.mud_trails, key=lambda trail: trail.age + trail.alpha * 80.0) if self.mud_trails else None
        if target is None:
            self.mud_cleaner_state = "exit"
            return
        dx = target.x - self.mud_cleaner_x
        if self.mud_cleaner_state == "enter" and -2.0 <= self.mud_cleaner_x <= w + 2.0:
            self.mud_cleaner_state = "clean"
        speed_cap = 5.2 if self.mud_cleaner_state == "enter" else 4.4
        step = max(-speed_cap, min(speed_cap, dx * 0.16))
        self.mud_cleaner_x += step
        if self.mud_cleaner_state == "enter":
            return
        cleaned_any = False
        for trail in list(self.mud_trails):
            brush_dx = abs(trail.x - self.mud_cleaner_x)
            brush_dy = abs(trail.y - (floor_y - 8.0))
            if brush_dx < max(16.0, trail.width + 8.0) and brush_dy < 18.0:
                cleaned_any = True
                trail.alpha -= 0.16
                trail.width *= 0.86
                if trail.alpha <= 0.10 or trail.width < 4.0:
                    try:
                        self.mud_trails.remove(trail)
                    except ValueError:
                        pass
        if cleaned_any:
            if now - float(getattr(self, "_last_mud_clean_splash_at", 0.0)) > 0.35:
                self._last_mud_clean_splash_at = now
                self._add_puddle_splash(self.mud_cleaner_x, floor_y - 9.0, count=3)

    def item_count(self) -> int:
        return len(self.items)

    def summon_debris(self, count: int = 10) -> None:
        for _ in range(count):
            self._spawn_item(force=True)
        self.update()

    def summon_work_debris(self, count: int = 4, pressure: float = 0.0) -> None:
        """Typing/workload debris: mostly paper/dust, spread across the taskbar floor."""
        w = max(1, self.width())
        h = max(1, self.height())
        limit = 90
        for _ in range(max(1, min(16, count))):
            if len(self.items) >= limit:
                break
            kind = random.choices(["paper", "dust", "leaf"], weights=[55, 32, 13], k=1)[0]
            size = random.uniform(6.0, 13.0) if kind != "dust" else random.uniform(2.6, 5.8)
            self.items.append(DebrisItem(
                x=random.uniform(24, max(25, w - 24)),
                y=random.uniform(max(6, h - 86), max(8, h - 32)),
                kind=kind,
                size=size,
                rotation=random.uniform(0, 360),
                settled_y=random.uniform(max(4, h - 30), max(5, h - 8)),
                color=random_leaf_color() if kind == "leaf" else ("#f4eed3" if kind == "paper" else "#92846a"),
                vx=random.uniform(-0.25, 0.25) + random.uniform(-0.01, 0.01) * pressure,
                vy=random.uniform(0.04, 0.42),
                settled=False,
            ))
        self.update()

    def summon_wind_pile(self, count: Optional[int] = None) -> None:
        self._spawn_wind_pile(count=count or random.randint(7, 13), force=True)
        self.update()

    def toss_attention_debris(self, count: int = 6) -> None:
        # A playful attention bid: bits pop up near the center of the toolbar edge and settle.
        w = max(1, self.width())
        h = max(1, self.height())
        for _ in range(count):
            kind = random.choice(["paper", "leaf", "dust"])
            size = random.uniform(6.0, 13.5) if kind != "dust" else random.uniform(3.0, 6.0)
            self.items.append(DebrisItem(
                x=w * 0.5 + random.uniform(-46, 46),
                y=random.uniform(10, 34),
                kind=kind,
                size=size,
                rotation=random.uniform(0, 360),
                settled_y=random.uniform(max(4, h - 28), max(5, h - 8)),
                color=random_leaf_color() if kind == "leaf" else ("#f4eed3" if kind == "paper" else "#92846a"),
                vx=random.uniform(-0.6, 0.6),
                vy=random.uniform(0.2, 0.8),
                settled=False,
            ))
        self.update()

    def nearest_item_global_to(self, global_x: int, global_y: int) -> Optional[QPoint]:
        if not self.items:
            return None
        geo = self.geometry()
        best = min(self.items, key=lambda item: abs((geo.left() + item.x) - global_x) + 0.2 * abs((geo.top() + item.y) - global_y))
        return QPoint(int(geo.left() + best.x), int(geo.top() + best.y))

    def _add_clean_poof(self, x: float, y: float, count: int = 7) -> None:
        for _ in range(count):
            self.puffs.append(Puff(
                x + random.uniform(-12, 12),
                y + random.uniform(-10, 8),
                random.uniform(0.75, 1.15),
                random.uniform(7, 17),
                "dust",
            ))

    def _add_puddle_splash(self, x: float, y: float, count: int = 6) -> None:
        for _ in range(count):
            self.puffs.append(Puff(
                x + random.uniform(-16, 16),
                y + random.uniform(-6, 4),
                random.uniform(0.62, 0.95),
                random.uniform(5.5, 12.5),
                "splash",
            ))

    def clear_near_global(self, global_x: int, global_y: int, radius: int = 42) -> int:
        if not self.items:
            return 0
        geo = self.geometry()
        local_x = global_x - geo.left()
        local_y = global_y - geo.top()
        kept: List[DebrisItem] = []
        removed = 0
        r2 = radius * radius
        for item in self.items:
            dx = item.x - local_x
            # Debris lives on a thin floor; vertical distance should not make pickup fail.
            dy = (item.y - local_y) * 0.42
            if (dx * dx + dy * dy) <= r2:
                removed += 1
                self._add_clean_poof(item.x, item.y)
            else:
                kept.append(item)
        self.items = kept
        if removed:
            self.update()
        return removed

    def clear_footprint_global(self, left: int, right: int, floor_y: int, x_margin: int = 16, y_margin: int = 105) -> int:
        """Clear debris under the rover treads.

        The pet stands on a taskbar edge while debris settles on an overlay that can
        differ by a few pixels from the pet window. A footprint-based pickup is much
        more reliable than a circular center collision.
        """
        if not self.items:
            return 0
        geo = self.geometry()
        local_left = min(left, right) - geo.left() - x_margin
        local_right = max(left, right) - geo.left() + x_margin
        local_floor = floor_y - geo.top()
        kept: List[DebrisItem] = []
        removed = 0
        for item in self.items:
            in_x = local_left <= item.x <= local_right
            near_floor = (local_floor - y_margin) <= item.y <= (local_floor + 28)
            # Also catch falling bits that enter the front scoop before settling.
            scoop = (local_left - 22) <= item.x <= (local_right + 22) and (local_floor - y_margin - 35) <= item.y <= (local_floor + 35)
            if in_x and near_floor or scoop:
                removed += 1
                self._add_clean_poof(item.x, item.y, count=8)
            else:
                kept.append(item)
        self.items = kept
        if removed:
            self.update()
        return removed

    def bin_point_global(self) -> QPoint:
        geo = self.geometry()
        return QPoint(geo.right() - 28, geo.bottom() - 16)

    def tv_spot_global(self) -> QPoint:
        geo = self.geometry()
        return QPoint(geo.left() + 104, geo.bottom() - 16)

    def tree_point_global(self) -> QPoint:
        geo = self.geometry()
        w = max(1, self.width())
        x = min(max(138, w * 0.24), max(140, w - 92))
        return QPoint(int(geo.left() + x), int(geo.bottom() - 58))

    def set_tv_mode(self, mode: str) -> None:
        mode = (mode or "unchanged").strip().lower()
        if mode != "unchanged":
            self.tv_mode = mode if mode in {"off", "static", "movie", "stars", "hearts", "calm", "butterfly", "fireplace", "plant", "smile", "wow", "anime"} else "static"
            self.update()

    def debris_summary_global(self) -> Dict[str, object]:
        geo = self.geometry()
        if not self.items:
            return {"count": 0, "nearest": None, "pile_center": None}
        xs = [geo.left() + item.x for item in self.items]
        ys = [geo.top() + item.y for item in self.items]
        return {
            "count": len(self.items),
            "nearest": None,
            "pile_center": [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)],
            "bbox": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)],
            "settled_count": sum(1 for item in self.items if item.settled),
        }

    def summon_butterfly(self) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        self.butterfly_visible = True
        self.butterfly_x = random.uniform(60, max(62, w - 80))
        self.butterfly_y = random.uniform(10, max(18, h - 82))
        self.butterfly_vx = random.choice([-1.0, 1.0]) * random.uniform(0.45, 1.05)
        self.butterfly_phase = random.uniform(0, math.tau)
        # Longer visitor window so Wally has real chances to notice/chase.
        self.butterfly_end_at = time.time() + random.uniform(90, 150)
        self.update()

    def scare_butterfly(self) -> None:
        if not self.butterfly_visible:
            return
        self.butterfly_vx *= -1.4
        self.butterfly_y = max(6, self.butterfly_y - 16)
        if random.random() < 0.20:
            self.butterfly_visible = False
        self.update()

    def butterfly_point_global(self) -> Optional[QPoint]:
        if not self.butterfly_visible:
            return None
        geo = self.geometry()
        return QPoint(int(geo.left() + self.butterfly_x), int(geo.top() + self.butterfly_y))

    def butterfly_status(self) -> Dict[str, object]:
        point = self.butterfly_point_global()
        return {
            "visible": self.butterfly_visible,
            "global_xy": [point.x(), point.y()] if point else None,
            "mood_hint": "fluttering near the taskbar edge" if self.butterfly_visible else "none",
        }

    def summon_eva_flyby(self) -> None:
        """A tiny original white drone visitor: fast dramatic zigzag flyby."""
        w = max(1, self.width())
        h = max(1, self.height())
        cfg = self.store.config()
        speed_mult = max(1.0, min(4.0, cfg.eva_speed_percent / 100.0))
        duration = max(10.0, min(90.0, float(cfg.eva_duration_seconds)))
        from_left = random.random() < 0.5
        self.eva_visible = True
        # Keep the whole visitor inside the overlay; her trail/arms need margin.
        edge = max(88.0, min(118.0, w * 0.075))
        self.eva_x = edge if from_left else w - edge
        upper_band = max(58.0, min(h - 126.0, h * 0.42))
        self.eva_base_y = random.uniform(48.0, upper_band)
        self.eva_y = self.eva_base_y
        # Default setting is 250%, roughly 2-3x the previous speed.
        speed = random.uniform(5.8, 8.8) * speed_mult
        self.eva_vx = speed if from_left else -speed
        # Duration controls when she leaves; turns are only for drama, not early termination.
        self.eva_turns_left = max(8, int(duration / 2.4))
        self.eva_phase = random.uniform(0, math.tau)
        self.eva_next_mid_turn_at = time.time() + random.uniform(0.9, 2.4)
        self.eva_last_turn_reason = "launch"
        self.eva_end_at = time.time() + duration
        self.raise_()
        self.update()

    def _update_eva(self, w: int, h: int) -> None:
        if not self.eva_visible:
            return
        now = time.time()
        cfg = self.store.config()
        speed_mult = max(1.0, min(4.0, cfg.eva_speed_percent / 100.0))

        self.eva_phase += 0.29 + 0.035 * min(4.0, speed_mult)

        # Random mid-air direction changes: not only wall bounces.
        if now >= self.eva_next_mid_turn_at:
            if random.random() < 0.64:
                self.eva_vx = -self.eva_vx * random.uniform(0.86, 1.14)
                self.eva_last_turn_reason = "midair_turn"
                self.eva_turns_left -= 1
            else:
                self.eva_vx *= random.uniform(0.92, 1.16)
                self.eva_last_turn_reason = "speed_juke"
            y_max = max(58.0, min(h - 126.0, h * 0.46))
            self.eva_base_y = random.uniform(48.0, y_max)
            self.eva_next_mid_turn_at = now + random.uniform(0.75, 2.35)

        # Fast horizontal motion with uneven speed and dramatic vertical weave.
        self.eva_x += self.eva_vx * (0.92 + 0.34 * math.sin(self.eva_phase * 0.9))
        zig = (
            30.0 * math.sin(self.eva_phase * 0.88)
            + 13.0 * math.sin(self.eva_phase * 2.55)
            + 5.0 * math.sin(self.eva_phase * 4.1)
        )
        self.eva_y = self.eva_base_y + zig
        self.eva_y = max(50, min(max(56, h - 126), self.eva_y))

        # Bounce left/right while keeping full visitor visible.
        edge = max(88.0, min(118.0, w * 0.075))
        if self.eva_x > w - edge:
            self.eva_x = w - edge
            self.eva_vx = -abs(self.eva_vx) * random.uniform(0.90, 1.15)
            self.eva_base_y = random.uniform(48.0, max(58.0, min(h - 126.0, h * 0.46)))
            self.eva_next_mid_turn_at = now + random.uniform(0.65, 1.9)
            self.eva_last_turn_reason = "right_wall_bounce"
            self.eva_turns_left -= 1
        elif self.eva_x < edge:
            self.eva_x = edge
            self.eva_vx = abs(self.eva_vx) * random.uniform(0.90, 1.15)
            self.eva_base_y = random.uniform(48.0, max(58.0, min(h - 126.0, h * 0.46)))
            self.eva_next_mid_turn_at = now + random.uniform(0.65, 1.9)
            self.eva_last_turn_reason = "left_wall_bounce"
            self.eva_turns_left -= 1

        if now > self.eva_end_at:
            self.eva_visible = False
            self.update()
    def eva_point_global(self) -> Optional[QPoint]:
        if not self.eva_visible:
            return None
        geo = self.geometry()
        return QPoint(int(geo.left() + self.eva_x), int(geo.top() + self.eva_y))

    def eva_status(self) -> Dict[str, object]:
        point = self.eva_point_global()
        return {
            "visible": self.eva_visible,
            "global_xy": [point.x(), point.y()] if point else None,
            "name": self.eva_name,
            "mood_hint": "white drone visitor flying fast across the taskbar sky" if self.eva_visible else "gone",
            "speed_px_per_tick": round(abs(self.eva_vx), 2) if self.eva_visible else 0,
            "last_turn": getattr(self, "eva_last_turn_reason", "none"),
            "seconds_left": round(max(0.0, self.eva_end_at - time.time()), 1) if self.eva_visible else 0,
        }

    def ball_point_global(self) -> Optional[QPoint]:
        if not getattr(self.ball, "visible", False):
            return None
        geo = self.geometry()
        return QPoint(int(geo.left() + self.ball.x), int(geo.top() + self.ball.y))

    def ball_status(self) -> Dict[str, object]:
        point = self.ball_point_global()
        speed = abs(getattr(self.ball, "vx", 0.0)) + abs(getattr(self.ball, "vy", 0.0))
        floor_y = max(20, self.height() - 17)
        return {
            "visible": bool(getattr(self.ball, "visible", False)),
            "global_xy": [point.x(), point.y()] if point else None,
            "moving": speed > 0.35,
            "speed": round(speed, 2),
            "last_kicked_seconds": round(max(0.0, time.time() - getattr(self.ball, "last_kicked_at", 0.0)), 1) if getattr(self.ball, "last_kicked_at", 0.0) else None,
            "last_super_kick_seconds": round(max(0.0, time.time() - getattr(self.ball, "last_super_kick_at", 0.0)), 1) if getattr(self.ball, "last_super_kick_at", 0.0) else None,
            "last_style": getattr(self.ball, "last_kick_style", "none"),
            "wall_hits": int(getattr(self.ball, "wall_hits", 0)),
            "over_puddle": bool(self._puddle_contains_local(self.ball.x, floor_y, x_pad=8, y_pad=9)),
        }

    def kick_ball_global(self, kicker_x: int, power: float = 1.0, style: str = "random", super_kick: bool = False) -> Dict[str, object]:
        w = max(1, self.width())
        h = max(1, self.height())
        if not self.ball.visible:
            self.ball.visible = True
            self.ball.x = min(max(40, kicker_x - self.geometry().left()), w - 40)
            self.ball.y = h - 18
        direction = 1 if self.ball.x >= (kicker_x - self.geometry().left()) else -1
        if abs(self.ball.x - (kicker_x - self.geometry().left())) < 22:
            direction = random.choice([-1, 1])
        # Sometimes Wally clips it backwards or upward, so kicks feel alive.
        if random.random() < 0.22 and not super_kick:
            direction *= -1
        style = style if style != "random" else random.choice(["roll", "chip", "lob", "side_spin", "bounce_shot"])
        power = max(0.45, min(float(power), 6.0))
        if super_kick:
            vx = direction * random.uniform(10.5, 16.5)
            vy = -random.uniform(8.0, 14.5)
            style = "super_" + random.choice(["rocket", "pinball", "chaos"])
            self.ball.last_super_kick_at = time.time()
        else:
            if style == "roll":
                vx = direction * random.uniform(3.5, 7.0) * power
                vy = -random.uniform(0.8, 2.2) * power
            elif style == "chip":
                vx = direction * random.uniform(2.2, 5.0) * power
                vy = -random.uniform(4.0, 7.2) * power
            elif style == "lob":
                vx = direction * random.uniform(1.6, 4.2) * power
                vy = -random.uniform(6.0, 9.0) * power
            elif style == "side_spin":
                vx = direction * random.uniform(5.5, 9.0) * power
                vy = -random.uniform(2.2, 5.5) * power
            else:
                vx = direction * random.uniform(6.0, 10.0) * power
                vy = -random.uniform(4.5, 8.5) * power
        self.ball.vx = vx
        self.ball.vy = vy
        self.ball.spin += direction * random.uniform(20, 42) * (2.0 if super_kick else 1.0)
        self.ball.last_kicked_at = time.time()
        self.ball.last_kick_style = style
        self.update()
        return {"style": style, "super": super_kick, "vx": round(vx, 2), "vy": round(vy, 2), "power": round(power, 2)}

    def _update_ball(self, w: int, h: int) -> None:
        if not getattr(self.ball, "visible", False):
            return
        now = time.time()
        floor_y = max(20, h - 17)
        ceiling_y = 14
        self.ball_phase += 0.12
        self.ball.vy = min(9.5, self.ball.vy + 0.19)
        self.ball.x += self.ball.vx
        self.ball.y += self.ball.vy
        self.ball.spin += self.ball.vx * 2.9
        speed = abs(self.ball.vx) + abs(self.ball.vy)
        self.ball.vx *= 0.994 if speed > 12 else 0.986
        puddle_hit = self._puddle_contains_local(self.ball.x, floor_y, x_pad=8, y_pad=9)
        if puddle_hit:
            self.ball.vx *= 0.978
            if now - float(getattr(self.ball, "_last_puddle_splash_at", 0.0)) > 0.8 and speed > 0.35:
                setattr(self.ball, "_last_puddle_splash_at", now)
                self._add_puddle_splash(self.ball.x, floor_y - 3, count=5)
        if self.ball.y < ceiling_y:
            self.ball.y = ceiling_y
            self.ball.vy = abs(self.ball.vy) * (0.82 if speed > 9 else 0.62)
            self.ball.wall_hits += 1
        if self.ball.y >= floor_y:
            self.ball.y = floor_y
            if abs(self.ball.vy) > 1.2:
                bounce_scale = 0.42 if puddle_hit else (0.66 if speed > 10 else 0.48)
                self.ball.vy = -abs(self.ball.vy) * bounce_scale
                self.ball.wall_hits += 1
            else:
                self.ball.vy = 0.0
        if self.ball.x < 18:
            self.ball.x = 18
            self.ball.vx = abs(self.ball.vx) * (0.90 if speed > 10 else 0.75)
            self.ball.wall_hits += 1
        elif self.ball.x > w - 18:
            self.ball.x = w - 18
            self.ball.vx = -abs(self.ball.vx) * (0.90 if speed > 10 else 0.75)
            self.ball.wall_hits += 1
        if abs(self.ball.vx) < 0.03:
            self.ball.vx = 0.0
        if abs(self.ball.vy) < 0.05 and self.ball.y >= floor_y - 0.5:
            self.ball.vy = 0.0

    def _tick(self) -> None:
        if not self.enabled:
            return
        now = time.time()

        # Natural wind model: slow circular flow + occasional gusts.
        self.wind_phase += 0.034 + min(0.04, abs(self.wind) * 0.05)
        base_flow = (
            0.42 * math.sin(self.wind_phase)
            + 0.24 * math.sin(self.wind_phase * 0.41 + 1.8)
            + 0.11 * math.sin(self.wind_phase * 1.73 + 0.4)
        )
        self.vertical_wind = 0.30 * math.cos(self.wind_phase * 0.82) + 0.11 * math.sin(self.wind_phase * 1.3)
        if random.random() < 0.010:
            self.wind = random.uniform(-0.82, 0.82)
            if abs(self.wind) > 0.34:
                self.wind_gust_until = now + random.uniform(2.0, 4.8)
        self.wind = self.wind * 0.955 + base_flow * 0.045

        w = max(1, self.width())
        h = max(1, self.height())
        self._update_weather(w, h, now, base_flow)
        self.tv_phase += 0.08
        self.tree_phase += 0.05 + min(0.055, abs(self.wind) * 0.052)
        self._update_butterfly(w, h)
        self._update_eva(w, h)
        if self.butterfly_visible or self.eva_visible:
            # Air visitors should visually float above the mini chat and all props.
            self.raise_()
        self._update_ball(w, h)

        gusting = now < self.wind_gust_until
        max_items = 46

        # Controlled pile budget: maximum two piles per 45-90 second window.
        if now >= self.next_wind_window_at:
            self.wind_piles_remaining = random.randint(1, 2)
            self.next_wind_window_at = now + random.uniform(45, 90)
            self.next_wind_pile_at = now + random.uniform(1.5, 9.0)
            if random.random() < 0.7:
                self.wind_gust_until = max(self.wind_gust_until, now + random.uniform(3.0, 6.0))

        if self.wind_piles_remaining > 0 and now >= self.next_wind_pile_at and len(self.items) < max_items:
            self._spawn_wind_pile(count=random.randint(5, 10))
            self.wind_piles_remaining -= 1
            self.next_wind_pile_at = now + random.uniform(12, 28)

        # Very light ambience only; piles carry the visual, not constant single particles.
        if len(self.items) < max_items and random.random() < (0.004 if gusting else 0.0012):
            self._spawn_side_swirler()

        # Tree still sheds, but softly; green leaves add nature without turning into clutter.
        if len(self.items) < max_items and random.random() < (0.016 if gusting else 0.006):
            self._shed_tree_leaf()

        wind_push = self.wind + base_flow * 0.58
        for item in self.items:
            item.age += 1
            curl = 0.52 * math.sin(item.age * 0.20 + item.rotation * 0.045 + self.wind_phase)
            curl += 0.25 * math.sin(item.age * 0.071 + self.wind_phase * 1.9)
            lift = self.vertical_wind * (0.36 if item.kind == "leaf" else 0.16)
            if not item.settled:
                # Slower descent: piles visibly travel in the wind before landing.
                item.vy = min(1.55, item.vy + (0.015 if item.kind == "leaf" else 0.030))
                item.y += item.vy + lift
                item.x += wind_push + item.vx + curl
                item.rotation += wind_push * 7.2 + item.vx * 2.2 + (3.1 if item.kind == "leaf" else 1.0)
                if item.y >= item.settled_y:
                    item.y = item.settled_y
                    item.vy = 0.0
                    item.vx *= 0.24
                    item.settled = True
            else:
                slide = wind_push * (0.72 if gusting else 0.24) + curl * (0.30 if gusting else 0.08)
                item.x += slide
                item.rotation += slide * 2.6
                if item.x < 54:
                    item.x += (54 - item.x) * 0.035 + (0.55 if gusting else 0.12)
                    if gusting and random.random() < 0.026:
                        item.settled = False
                        item.vx = abs(wind_push) + random.uniform(0.28, 0.78)
                        item.vy = random.uniform(-0.20, 0.20)
                elif item.x > w - 54:
                    item.x -= (item.x - (w - 54)) * 0.035 + (0.55 if gusting else 0.12)
                    if gusting and random.random() < 0.026:
                        item.settled = False
                        item.vx = -abs(wind_push) - random.uniform(0.28, 0.78)
                        item.vy = random.uniform(-0.20, 0.20)

                if gusting and item.kind in {"leaf", "paper"} and random.random() < 0.014:
                    item.settled = False
                    item.vx += wind_push * random.uniform(0.6, 1.3)
                    item.vy = random.uniform(-0.32, 0.16)
                    item.y = max(4, item.y - random.uniform(3, 14))

            # Keep TV/sofa area from becoming the permanent landfill.
            sofa_clear_right = min(150, max(120, w * 0.18))
            if item.settled and item.x < sofa_clear_right and item.y > h - 46:
                item.x += random.uniform(0.22, 0.82) + max(0.0, wind_push) * 0.45
                item.rotation += random.uniform(0.4, 1.4)
                if gusting and random.random() < 0.030:
                    item.settled = False
                    item.vx = random.uniform(0.45, 1.15)
                    item.vy = random.uniform(-0.25, 0.16)

            if item.x < 7:
                item.x = 8 + random.uniform(0, 8)
                item.vx = abs(item.vx) * 0.62 + random.uniform(0.16, 0.62)
                item.settled = False
            elif item.x > w - 7:
                item.x = w - 8 - random.uniform(0, 8)
                item.vx = -abs(item.vx) * 0.62 - random.uniform(0.16, 0.62)
                item.settled = False

            item.y = max(-14, min(h - 5, item.y))

        if len(self.items) > max_items + 6:
            self.items = sorted(self.items, key=lambda it: it.age)[0:max_items]

        next_puffs: List[Puff] = []
        for puff in self.puffs:
            puff.life -= 0.045
            puff.y -= 0.25
            if puff.life > 0:
                next_puffs.append(puff)
        self.puffs = next_puffs
        self.update()

    def _update_butterfly(self, w: int, h: int) -> None:
        if not self.butterfly_visible:
            return
        if self.butterfly_end_at and time.time() > self.butterfly_end_at:
            self.butterfly_visible = False
            return
        self.butterfly_phase += 0.22
        self.butterfly_x += self.butterfly_vx + 0.44 * math.sin(self.butterfly_phase * 0.7)
        self.butterfly_y += 1.05 * math.sin(self.butterfly_phase) + random.uniform(-0.22, 0.22)
        if self.butterfly_x < 28:
            self.butterfly_x = 28
            self.butterfly_vx = abs(self.butterfly_vx)
        elif self.butterfly_x > w - 28:
            self.butterfly_x = w - 28
            self.butterfly_vx = -abs(self.butterfly_vx)
        self.butterfly_y = max(8, min(max(14, h - 58), self.butterfly_y))
        if random.random() < 0.00016:
            self.butterfly_visible = False

    def set_spawn_paused(self, paused: bool) -> None:
        self.spawn_paused = bool(paused)

    def _spawn_item(self, force: bool = False) -> None:
        if self.spawn_paused and not force:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        if w < 20 or h < 20:
            return
        kind = random.choice(["leaf", "paper", "dust", "leaf", "paper"])
        size = random.uniform(5.5, 12.5) if kind != "dust" else random.uniform(2.5, 5.5)
        x = random.uniform(12, max(13, w - 12))
        y = random.uniform(-18, 8) if not force else random.uniform(max(2, h - 34), max(3, h - 10))
        settled_y = random.uniform(max(4, h - 28), max(5, h - 8))
        item = DebrisItem(
            x=x,
            y=y,
            kind=kind,
            size=size,
            rotation=random.uniform(0, 360),
            settled_y=settled_y,
            color=random_leaf_color() if kind == "leaf" else ("#f4eed3" if kind == "paper" else "#92846a"),
            vx=random.uniform(-0.15, 0.15),
            vy=random.uniform(0.0, 0.35),
            settled=force,
        )
        if force:
            item.y = settled_y
        self.items.append(item)

    def _spawn_side_swirler(self) -> None:
        """Spawn a small leaf/paper from screen edge as if wind blew it in."""
        if self.spawn_paused:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        if w < 40 or h < 40:
            return
        from_left = random.random() < 0.5
        kind = random.choice(["leaf", "leaf", "paper"])
        side_speed = random.uniform(0.45, 1.25)
        item = DebrisItem(
            x=-10 if from_left else w + 10,
            y=random.uniform(max(4, h * 0.12), max(14, h - 42)),
            kind=kind,
            size=random.uniform(7.0, 13.0),
            rotation=random.uniform(0, 360),
            settled_y=random.uniform(max(4, h - 28), max(5, h - 9)),
            color=random_leaf_color() if kind == "leaf" else "#f4eed3",
            vx=side_speed if from_left else -side_speed,
            vy=random.uniform(0.04, 0.32),
            settled=False,
        )
        self.items.append(item)

    def _spawn_wind_pile(self, count: int = 8, force: bool = False) -> None:
        """Spawn a natural gust-pile from left/right/top/upper-air."""
        if self.spawn_paused and not force:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        if w < 50 or h < 40:
            return

        source = random.choices(["left", "right", "top", "upper_air"], weights=[28, 28, 32, 12], k=1)[0]
        direction = random.choice([-1, 1])
        if source == "left":
            base_x = -22 - random.uniform(0, 80)
            base_y = random.uniform(max(6, h * 0.10), max(18, h - 74))
            direction = 1
        elif source == "right":
            base_x = w + 22 + random.uniform(0, 80)
            base_y = random.uniform(max(6, h * 0.10), max(18, h - 74))
            direction = -1
        elif source == "top":
            base_x = random.uniform(28, max(30, w - 28))
            base_y = -36 - random.uniform(0, 120)
            direction = random.choice([-1, 1])
        else:
            base_x = random.uniform(w * 0.18, w * 0.82)
            base_y = random.uniform(8, max(16, h * 0.46))
            direction = random.choice([-1, 1])

        base_speed = random.uniform(0.55, 1.65)
        spread_x = random.uniform(14, 42)
        spread_y = random.uniform(12, 46)
        kinds = ["leaf", "leaf", "paper", "paper", "dust"]
        for _ in range(max(3, min(16, count))):
            kind = random.choice(kinds)
            if source in {"left", "right"}:
                x = base_x + random.uniform(-spread_x, spread_x)
                y = base_y + random.uniform(-spread_y, spread_y)
            else:
                x = base_x + random.uniform(-spread_x * 1.7, spread_x * 1.7)
                y = base_y + random.uniform(-spread_y, spread_y)
            size = random.uniform(6.5, 13.5) if kind != "dust" else random.uniform(2.8, 5.8)
            vx = direction * (base_speed + random.uniform(-0.35, 0.75))
            if source in {"top", "upper_air"}:
                vx += self.wind + random.uniform(-0.75, 0.75)
            vy = random.uniform(0.02, 0.42 if source != "top" else 0.78)
            self.items.append(DebrisItem(
                x=x,
                y=y,
                kind=kind,
                size=size,
                rotation=random.uniform(0, 360),
                settled_y=random.uniform(max(4, h - 30), max(5, h - 8)),
                color=random_leaf_color() if kind == "leaf" else ("#f4eed3" if kind == "paper" else "#92846a"),
                vx=vx,
                vy=vy,
                settled=False,
            ))
        self.wind = direction * max(abs(self.wind), random.uniform(0.46, 0.92))
        self.wind_gust_until = max(self.wind_gust_until, time.time() + random.uniform(2.0, 4.6))

    def _shed_tree_leaf(self) -> None:
        """Small green leaf falling from the tiny tree near the TV."""
        if self.spawn_paused:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        ground_y = h - 6
        tree_x = min(max(138, w * 0.24), max(140, w - 92))
        tree_top = ground_y - 92
        leaf_count = 1 if random.random() < 0.72 else random.randint(2, 4)
        for _ in range(leaf_count):
            self.items.append(DebrisItem(
                x=tree_x + random.uniform(-26, 30),
                y=tree_top + random.uniform(-12, 26),
                kind="leaf",
                size=random.uniform(6.2, 11.4),
                rotation=random.uniform(0, 360),
                settled_y=random.uniform(max(4, h - 31), max(5, h - 8)),
                color=random.choice(["#55a85c", "#6fbd4d", "#7cc95a", "#4d9a49", "#83d868"]),
                vx=random.uniform(0.15, 0.95) + self.wind * random.uniform(0.8, 1.45),
                vy=random.uniform(0.02, 0.30),
                settled=False,
            ))

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self.enabled:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        self._draw_weather_backdrop(p)
        self._draw_props(p)
        self._draw_ground_weather(p)
        self._draw_mud_trails(p)
        if getattr(self.ball, "visible", False):
            self._draw_basketball(p)
        if self.mud_cleaner_visible:
            self._draw_mud_cleaner(p)
        if self.butterfly_visible:
            self._draw_butterfly(p)
        if self.eva_visible:
            self._draw_eva(p)
        for item in self.items:
            p.save()
            p.translate(item.x, item.y)
            p.rotate(item.rotation)
            if item.kind == "leaf":
                self._draw_leaf(p, item.size, item.color)
            elif item.kind == "paper":
                self._draw_paper(p, item.size)
            else:
                self._draw_dust(p, item.size)
            p.restore()

        for puff in self.puffs:
            alpha = int(max(0, min(1, puff.life)) * 155)
            if getattr(puff, "kind", "dust") == "splash":
                p.setBrush(QColor(138, 190, 238, min(210, alpha + 28)))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(puff.x, puff.y), puff.size * 0.75, puff.size * 0.42)
                p.setPen(QPen(QColor(230, 245, 255, min(235, alpha + 58)), 1.2, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(puff.x - puff.size * 0.32, puff.y - puff.size * 0.10), QPointF(puff.x, puff.y - puff.size * 0.55))
                p.drawLine(QPointF(puff.x + puff.size * 0.28, puff.y - puff.size * 0.04), QPointF(puff.x + puff.size * 0.08, puff.y - puff.size * 0.50))
            else:
                p.setBrush(QColor(224, 214, 188, alpha))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(puff.x, puff.y), puff.size, puff.size * 0.65)
                if puff.size > 10:
                    p.setPen(QPen(QColor(255, 246, 185, min(230, alpha + 35)), 1.4, Qt.SolidLine, Qt.RoundCap))
                    p.drawLine(QPointF(puff.x - puff.size * 0.55, puff.y), QPointF(puff.x + puff.size * 0.55, puff.y))
                    p.drawLine(QPointF(puff.x, puff.y - puff.size * 0.45), QPointF(puff.x, puff.y + puff.size * 0.45))

    def _draw_basketball(self, p: QPainter) -> None:
        p.save()
        p.translate(self.ball.x, self.ball.y)
        p.rotate(self.ball.spin)
        r = 9.5
        grad = QRadialGradient(QPointF(-3, -4), r * 1.35)
        grad.setColorAt(0, QColor(255, 188, 86, 245))
        grad.setColorAt(1, QColor(200, 91, 31, 240))
        p.setBrush(grad)
        p.setPen(QPen(QColor(94, 50, 28, 230), 1.2))
        p.drawEllipse(QPointF(0, 0), r, r)
        p.setPen(QPen(QColor(88, 44, 24, 210), 1.1, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-r + 1.5, 0), QPointF(r - 1.5, 0))
        p.drawLine(QPointF(0, -r + 1.5), QPointF(0, r - 1.5))
        p.drawArc(QRectF(-r * 1.15, -r, r * 1.1, r * 2), -70 * 16, 140 * 16)
        p.drawArc(QRectF(0, -r, r * 1.15, r * 2), 110 * 16, 140 * 16)
        p.restore()

    def _draw_butterfly(self, p: QPainter) -> None:
        p.save()
        p.translate(self.butterfly_x, self.butterfly_y)
        wing = 5.5 + 2.2 * math.sin(self.butterfly_phase * 2.5)
        p.setPen(QPen(QColor(63, 52, 82, 210), 0.9))
        left = QPainterPath()
        left.moveTo(0, 0)
        left.cubicTo(-wing * 1.4, -wing * 1.5, -wing * 2.0, wing * 0.2, -1, wing * 0.7)
        left.cubicTo(-wing * 1.2, wing * 1.8, -wing * 0.2, wing * 1.6, 0, 0)
        right = QPainterPath()
        right.moveTo(0, 0)
        right.cubicTo(wing * 1.4, -wing * 1.5, wing * 2.0, wing * 0.2, 1, wing * 0.7)
        right.cubicTo(wing * 1.2, wing * 1.8, wing * 0.2, wing * 1.6, 0, 0)
        p.setBrush(QColor(255, 206, 94, 220))
        p.drawPath(left)
        p.setBrush(QColor(120, 202, 255, 220))
        p.drawPath(right)
        p.setBrush(QColor(55, 48, 63, 235))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 2), 1.8, 5.5)
        p.setPen(QPen(QColor(55, 48, 63, 190), 0.8))
        p.drawLine(QPointF(-1, -3), QPointF(-5, -7))
        p.drawLine(QPointF(1, -3), QPointF(5, -7))
        p.restore()

    def _draw_eva(self, p: QPainter) -> None:
        p.save()
        p.translate(self.eva_x, self.eva_y)
        if self.eva_vx < 0:
            p.scale(-1, 1)
        bob = math.sin(self.eva_phase * 1.7)
        # soft glow
        p.setBrush(QColor(255, 255, 255, 56))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 2 + bob), 30, 22)
        # compact white drone body
        body = QPainterPath()
        body.addRoundedRect(QRectF(-21, -17 + bob, 42, 34), 18, 18)
        p.setBrush(QColor(250, 250, 246, 244))
        p.setPen(QPen(QColor(186, 190, 190, 200), 1.2))
        p.drawPath(body)
        # dark face visor
        visor = QRectF(-15, -8 + bob, 30, 16)
        p.setBrush(QColor(33, 42, 49, 235))
        p.setPen(QPen(QColor(92, 130, 150, 180), 1.0))
        p.drawRoundedRect(visor, 8, 8)
        p.setBrush(QColor(89, 224, 255, 225))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(-5, -1 + bob), 2.2, 2.2)
        p.drawEllipse(QPointF(5, -1 + bob), 2.2, 2.2)
        # little wing/arms
        p.setPen(QPen(QColor(217, 218, 210, 230), 3.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-20, 2 + bob), QPointF(-31, 8 + bob))
        p.drawLine(QPointF(20, 2 + bob), QPointF(31, 8 + bob))
        # hearts trail
        p.setPen(Qt.NoPen)
        for i in range(3):
            alpha = max(70, 190 - i * 45)
            p.setBrush(QColor(255, 108, 160, alpha))
            x = -36 - i * 12
            y = -10 + math.sin(self.eva_phase + i) * 4
            path = QPainterPath()
            path.moveTo(x, y)
            path.cubicTo(x - 5, y - 7, x - 12, y, x, y + 9)
            path.cubicTo(x + 12, y, x + 5, y - 7, x, y)
            p.drawPath(path)
        p.restore()

    def _draw_leaf(self, p: QPainter, size: float, color: str) -> None:
        path = QPainterPath()
        path.moveTo(0, -size * 0.55)
        path.cubicTo(size * 0.75, -size * 0.35, size * 0.85, size * 0.35, 0, size * 0.65)
        path.cubicTo(-size * 0.85, size * 0.35, -size * 0.75, -size * 0.35, 0, -size * 0.55)
        p.setBrush(QColor(color))
        p.setPen(QPen(QColor(86, 67, 28, 130), 0.8))
        p.drawPath(path)
        p.setPen(QPen(QColor(92, 69, 32, 160), 0.8))
        p.drawLine(QPointF(0, -size * 0.45), QPointF(0, size * 0.55))

    def _draw_paper(self, p: QPainter, size: float) -> None:
        path = QPainterPath()
        path.moveTo(-size * 0.65, -size * 0.45)
        path.lineTo(size * 0.45, -size * 0.55)
        path.lineTo(size * 0.65, size * 0.35)
        path.lineTo(-size * 0.4, size * 0.55)
        path.closeSubpath()
        p.setBrush(QColor(244, 238, 211, 220))
        p.setPen(QPen(QColor(165, 156, 127, 150), 0.8))
        p.drawPath(path)
        p.drawLine(QPointF(-size * 0.35, -size * 0.1), QPointF(size * 0.35, -size * 0.16))
        p.drawLine(QPointF(-size * 0.28, size * 0.12), QPointF(size * 0.28, size * 0.08))

    def _draw_dust(self, p: QPainter, size: float) -> None:
        p.setBrush(QColor(146, 132, 106, 145))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 0), size, size * 0.7)

    def _draw_weather_backdrop(self, p: QPainter) -> None:
        if not self.weather_enabled:
            return
        w = self.width()
        phase = self._daylight_phase()
        body_kind, body_progress = self._celestial_progress()
        body_x = 36 + (w - 72) * body_progress
        arch = math.sin(max(0.0, min(1.0, body_progress)) * math.pi)
        body_y = 54 + (1.0 - arch) * 18
        if body_kind == "sun":
            glow = QRadialGradient(QPointF(body_x, body_y), 44)
            if phase == "dawn":
                glow.setColorAt(0, QColor(255, 206, 150, 108))
                glow.setColorAt(1, QColor(255, 206, 150, 0))
                sun_color = QColor(255, 190, 122, 225)
            elif phase == "dusk":
                glow.setColorAt(0, QColor(255, 184, 136, 102))
                glow.setColorAt(1, QColor(255, 184, 136, 0))
                sun_color = QColor(255, 176, 106, 220)
            else:
                glow.setColorAt(0, QColor(255, 239, 170, 112))
                glow.setColorAt(1, QColor(255, 239, 170, 0))
                sun_color = QColor(255, 219, 112, 228)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(body_x, body_y), 44, 44)
            p.setBrush(sun_color)
            p.drawEllipse(QPointF(body_x, body_y + 2 * math.sin(self.sun_phase)), 14, 14)
        else:
            glow = QRadialGradient(QPointF(body_x, body_y), 34)
            glow.setColorAt(0, QColor(188, 204, 255, 76))
            glow.setColorAt(1, QColor(188, 204, 255, 0))
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(body_x, body_y), 34, 34)
            p.setBrush(QColor(236, 240, 252, 230))
            p.drawEllipse(QPointF(body_x, body_y), 11, 11)
        for cloud in self.clouds:
            alpha = cloud.alpha + (18 if self.weather_mode == "cloudy" else 0) + (10 if self.weather_mode == "rainy" else 0) + (8 if phase == "night" else 0)
            alpha = max(76, min(168, alpha))
            cx = cloud.x
            cy = max(30.0 * cloud.scale, cloud.y)
            s = cloud.scale
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(160, 170, 185, int(alpha * 0.24)))
            p.drawEllipse(QPointF(cx + 2 * s, cy + 12 * s), 27 * s, 7 * s)
            p.setBrush(QColor(238, 243, 248, int(alpha * 0.84)))
            p.drawEllipse(QPointF(cx - 18 * s, cy + 7 * s), 13 * s, 10 * s)
            p.drawEllipse(QPointF(cx - 6 * s, cy + 1 * s), 16 * s, 14 * s)
            p.drawEllipse(QPointF(cx + 9 * s, cy), 17 * s, 14 * s)
            p.drawEllipse(QPointF(cx + 22 * s, cy + 7 * s), 12 * s, 9 * s)
            p.drawRoundedRect(QRectF(cx - 24 * s, cy + 7 * s, 52 * s, 12 * s), 7 * s, 7 * s)
        if self.weather_mode == "rainy":
            p.setPen(QPen(QColor(150, 196, 255, 118), 1.2, Qt.SolidLine, Qt.RoundCap))
            for drop in self.rain_drops:
                p.drawLine(QPointF(drop.x, drop.y), QPointF(drop.x - self.wind * 1.6, drop.y + drop.length))
            p.setPen(Qt.NoPen)

    def _draw_ground_weather(self, p: QPainter) -> None:
        if not self.weather_enabled:
            return
        w = self.width()
        h = self.height()
        phase = self._daylight_phase()
        if phase == "night":
            _, body_progress = self._celestial_progress()
            arch = math.sin(max(0.0, min(1.0, body_progress)) * math.pi)
            moon_y = 26 + (1.0 - arch) * 28
            zone_top = max(0.0, min(float(h - 24), moon_y - 8.0))
            zone = QRectF(0, zone_top, w, h - zone_top)
            top = QColor(84, 104, 150, 26)
            mid = QColor(30, 42, 78, 72)
            bottom = QColor(6, 10, 20, 170)
        elif phase == "dawn":
            zone = QRectF(0, h - 78, w, 78)
            top = QColor(112, 138, 146, 24)
            bottom = QColor(120, 106, 88, 74)
        elif phase == "dusk":
            zone = QRectF(0, h - 78, w, 78)
            top = QColor(104, 98, 132, 26)
            bottom = QColor(84, 68, 76, 76)
        else:
            zone = QRectF(0, h - 78, w, 78)
            top = QColor(126, 158, 118, 18)
            bottom = QColor(88, 104, 74, 54)
        if phase != "night":
            if self.weather_mode == "rainy":
                bottom = QColor(76, 92, 112, max(bottom.alpha(), 94))
            elif self.weather_mode == "sunny":
                bottom = QColor(max(bottom.red(), 96), max(bottom.green(), 112), max(bottom.blue(), 74), max(bottom.alpha(), 58))
        grad = QLinearGradient(zone.topLeft(), zone.bottomLeft())
        grad.setColorAt(0, top)
        if phase == "night":
            grad.setColorAt(0.42, mid)
        grad.setColorAt(1, bottom)
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawRect(zone)
        if not self.puddles:
            return
        for puddle in self.puddles:
            alpha = int(max(0.0, min(1.0, puddle.alpha)) * 255)
            mud = QColor(108, 84, 62, max(36, int(alpha * 0.50)))
            water = QColor(118, 162, 208, max(56, int(alpha * 0.78)))
            shine = QColor(240, 248, 255, max(28, int(alpha * 0.54)))
            p.setBrush(mud)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(puddle.x, puddle.y + 1), puddle.width, puddle.depth + 1.2)
            p.setBrush(water)
            p.drawEllipse(QPointF(puddle.x, puddle.y), puddle.width * 0.88, puddle.depth)
            p.setPen(QPen(shine, 1.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(puddle.x - puddle.width * 0.32, puddle.y - 1), QPointF(puddle.x + puddle.width * 0.08, puddle.y - 2))
            p.setPen(Qt.NoPen)

    def _draw_mud_trails(self, p: QPainter) -> None:
        if not self.mud_trails:
            return
        for trail in self.mud_trails:
            alpha = int(max(0.0, min(1.0, trail.alpha)) * 255)
            p.setBrush(QColor(92, 62, 42, max(26, alpha)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(trail.x, trail.y), trail.width, max(2.8, trail.width * 0.22))
            p.setBrush(QColor(48, 36, 28, max(12, int(alpha * 0.34))))
            p.drawEllipse(QPointF(trail.x - trail.width * 0.22, trail.y - 0.4), trail.width * 0.34, max(1.6, trail.width * 0.10))

    def _draw_mud_cleaner(self, p: QPainter) -> None:
        p.save()
        p.translate(self.mud_cleaner_x, self.mud_cleaner_y)
        bob = math.sin(self.mud_cleaner_phase * 2.1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 22, 26, 80))
        p.drawEllipse(QPointF(0, 18), 18, 5)
        p.setBrush(QColor(236, 242, 247, 244))
        p.setPen(QPen(QColor(120, 132, 142, 230), 1.2))
        body = QPainterPath()
        body.addRoundedRect(QRectF(-16, -25 + bob, 32, 28), 6, 6)
        p.drawPath(body)
        p.setBrush(QColor(22, 24, 28, 238))
        p.setPen(QPen(QColor(66, 74, 82, 220), 0.9))
        p.drawRoundedRect(QRectF(-11, -15 + bob, 22, 9), 3, 3)
        p.setBrush(QColor(255, 221, 92, 230))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(-7, -12 + bob, 4, 2))
        p.drawRect(QRectF(3, -12 + bob, 4, 2))
        p.setBrush(QColor(255, 110, 96, 230))
        p.drawRoundedRect(QRectF(-4, -30 + bob, 8, 5), 2, 2)
        p.setBrush(QColor(84, 94, 102, 230))
        p.setPen(QPen(QColor(34, 38, 42, 220), 1.0))
        p.drawRoundedRect(QRectF(-17, 4 + bob, 34, 8), 4, 4)
        p.setPen(QPen(QColor(184, 206, 214, 210), 1.0))
        for i in range(5):
            x = -12 + i * 6
            p.drawLine(QPointF(x, 5 + bob), QPointF(x + 3, 11 + bob))
        p.setPen(QPen(QColor(96, 118, 128, 230), 2.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-12, 0 + bob), QPointF(-20, 8 + bob))
        p.drawLine(QPointF(12, 0 + bob), QPointF(20, 8 + bob))
        p.restore()


    def _draw_tv_screen(self, p: QPainter, rect: QRectF) -> None:
        mode = self.tv_mode
        phase = self.tv_phase
        p.save()
        p.setClipRect(rect)
        if mode == "off":
            p.setBrush(QColor(18, 20, 24, 230))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
        elif mode == "stars":
            p.setBrush(QColor(18, 26, 54, 235))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setBrush(QColor(255, 246, 160, 220))
            for i in range(7):
                x = rect.left() + 3 + (i * 9 + int(phase * 4)) % max(1, int(rect.width() - 5))
                y = rect.top() + 3 + (i * 5) % max(1, int(rect.height() - 5))
                p.drawEllipse(QPointF(x, y), 1.2, 1.2)
        elif mode == "hearts":
            p.setBrush(QColor(65, 26, 48, 235))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            for i in range(2):
                self._draw_prop_heart(p, rect.left() + 10 + i * 13, rect.top() + 8 + 2 * math.sin(phase + i), 5, QColor(255, 126, 166, 220))
        elif mode == "butterfly":
            p.setBrush(QColor(180, 232, 255, 210))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setBrush(QColor(255, 214, 85, 220))
            cx = rect.center().x() + 7 * math.sin(phase)
            cy = rect.center().y() + 3 * math.sin(phase * 1.8)
            p.drawEllipse(QPointF(cx - 3, cy), 4, 5)
            p.drawEllipse(QPointF(cx + 3, cy), 4, 5)
            p.setBrush(QColor(55, 45, 60, 230))
            p.drawEllipse(QPointF(cx, cy + 1), 1.4, 4)
        elif mode == "fireplace":
            p.setBrush(QColor(45, 22, 20, 235))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            for i, col in enumerate([QColor(255, 94, 34, 220), QColor(255, 178, 56, 220), QColor(255, 230, 124, 200)]):
                flame = QPainterPath()
                x = rect.left() + 9 + i * 8
                y = rect.bottom() - 3
                flame.moveTo(x, y)
                flame.cubicTo(x - 5, y - 9, x + 1, y - 13 - 2 * math.sin(phase + i), x + 3, y - 19)
                flame.cubicTo(x + 8, y - 10, x + 7, y - 4, x, y)
                p.setBrush(col)
                p.drawPath(flame)
        elif mode == "plant":
            p.setBrush(QColor(207, 235, 211, 220))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setBrush(QColor(111, 84, 55, 230))
            p.drawRoundedRect(QRectF(rect.center().x() - 5, rect.bottom() - 8, 10, 6), 2, 2)
            p.setBrush(QColor(72, 150, 76, 235))
            p.drawEllipse(QPointF(rect.center().x() - 4, rect.center().y()), 4, 8)
            p.drawEllipse(QPointF(rect.center().x() + 4, rect.center().y() - 2), 4, 8)
        elif mode == "smile":
            p.setBrush(QColor(255, 231, 134, 220))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QPen(QColor(37, 40, 42, 230), 1.5, Qt.SolidLine, Qt.RoundCap))
            p.drawEllipse(QPointF(rect.center().x() - 7, rect.center().y() - 2), 1.5, 1.5)
            p.drawEllipse(QPointF(rect.center().x() + 7, rect.center().y() - 2), 1.5, 1.5)
            p.drawArc(QRectF(rect.center().x() - 10, rect.center().y() - 5, 20, 15), 200 * 16, 140 * 16)
        elif mode == "movie":
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, QColor(70, 85, 120, 235))
            grad.setColorAt(1, QColor(23, 27, 40, 235))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QPen(QColor(255, 255, 255, 120), 1))
            p.drawLine(QPointF(rect.left() + 3, rect.bottom() - 5), QPointF(rect.right() - 3, rect.top() + 5))
        elif mode == "anime":
            p.setBrush(QColor(255, 219, 128, 225))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setBrush(QColor(30, 38, 50, 235))
            cx = rect.center().x() + 4 * math.sin(phase)
            cy = rect.center().y()
            p.drawEllipse(QPointF(cx - 5, cy - 1), 3.5, 5.5)
            p.drawEllipse(QPointF(cx + 5, cy - 1), 3.5, 5.5)
            p.setPen(QPen(QColor(170, 70, 45, 220), 1.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(rect.left() + 5, rect.top() + 4), QPointF(rect.right() - 4, rect.top() + 2))
        else:
            p.setBrush(QColor(132, 214, 255, 165))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QPen(QColor(255, 255, 255, 80), 1))
            for i in range(4):
                y = rect.top() + 3 + ((i * 5 + int(phase * 6)) % max(1, int(rect.height() - 4)))
                p.drawLine(QPointF(rect.left() + 3, y), QPointF(rect.right() - 3, y))
        p.restore()

    def _draw_prop_heart(self, p: QPainter, x: float, y: float, s: float, color: QColor) -> None:
        path = QPainterPath()
        path.moveTo(x, y + s * 0.35)
        path.cubicTo(x - s, y - s * 0.3, x - s * 0.8, y - s, x, y - s * 0.45)
        path.cubicTo(x + s * 0.8, y - s, x + s, y - s * 0.3, x, y + s * 0.35)
        p.setBrush(color)
        p.setPen(Qt.NoPen)
        p.drawPath(path)

    def _draw_props(self, p: QPainter) -> None:
        w = self.width()
        h = self.height()
        ground_y = h - 6

        # Edge/surface line: the red-marked toolbar boundary the pet stands on.
        p.setPen(QPen(QColor(255, 255, 255, 42), 1))
        p.drawLine(0, ground_y - 9, w, ground_y - 9)
        p.setPen(QPen(QColor(0, 0, 0, 62), 1))
        p.drawLine(0, ground_y - 2, w, ground_y - 2)
        p.setPen(Qt.NoPen)

        # Tiny TV table + sofa on the left.
        table = QRectF(24, ground_y - 31, 50, 17)
        p.setBrush(QColor(117, 82, 54, 215))
        p.setPen(QPen(QColor(70, 48, 32, 230), 1.2))
        p.drawRoundedRect(table, 3, 3)
        p.drawLine(QPointF(30, ground_y - 14), QPointF(30, ground_y - 1))
        p.drawLine(QPointF(68, ground_y - 14), QPointF(68, ground_y - 1))

        tv = QRectF(30, ground_y - 61, 42, 26)
        p.setBrush(QColor(47, 52, 62, 235))
        p.setPen(QPen(QColor(25, 28, 35, 240), 1.5))
        p.drawRoundedRect(tv, 4, 4)
        self._draw_tv_screen(p, QRectF(34, ground_y - 56, 34, 17))
        p.setBrush(QColor(28, 30, 36, 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(47, ground_y - 36, 7, 5), 2, 2)

        p.setBrush(QColor(104, 72, 56, 220))
        p.setPen(QPen(QColor(71, 47, 34, 235), 1.2))
        p.drawRoundedRect(QRectF(82, ground_y - 23, 38, 14), 6, 6)
        p.drawRoundedRect(QRectF(88, ground_y - 31, 26, 10), 5, 5)
        p.drawEllipse(QRectF(82, ground_y - 14, 9, 9))
        p.drawEllipse(QRectF(110, ground_y - 14, 9, 9))


        # Tiny taskbar tree: detailed but lightweight. It sways and sheds leaves.
        tree_x = min(max(138, w * 0.24), max(140, w - 92))
        sway = math.sin(self.tree_phase) * (2.8 + min(4.2, abs(self.wind) * 5.0))
        p.save()
        p.translate(tree_x, ground_y - 6)

        # trunk and roots
        trunk = QPainterPath()
        trunk.moveTo(-5, 0)
        trunk.cubicTo(-4, -14, -6 + sway * 0.18, -30, -3 + sway * 0.25, -50)
        trunk.lineTo(4 + sway * 0.25, -50)
        trunk.cubicTo(6 + sway * 0.18, -30, 4, -14, 5, 0)
        trunk.closeSubpath()
        p.setBrush(QColor(108, 72, 42, 230))
        p.setPen(QPen(QColor(68, 45, 28, 235), 1.15))
        p.drawPath(trunk)
        p.setPen(QPen(QColor(78, 51, 31, 205), 1.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-3, -3), QPointF(-14, 0))
        p.drawLine(QPointF(3, -3), QPointF(14, 0))

        # branches
        p.setPen(QPen(QColor(82, 54, 34, 220), 2.0, Qt.SolidLine, Qt.RoundCap))
        branches = [
            (QPointF(0, -35), QPointF(-18 + sway * 0.7, -51)),
            (QPointF(1, -40), QPointF(18 + sway * 0.8, -58)),
            (QPointF(1, -47), QPointF(4 + sway, -70)),
            (QPointF(-1, -30), QPointF(-9 + sway * 0.6, -43)),
        ]
        for a, b in branches:
            p.drawLine(a, b)

        # leafy canopy: many smaller organic blobs and highlights rather than 4 circles.
        leaf_blobs = [
            (-23, -61, 12, "#4f9d4d"), (-13, -73, 14, "#66b957"), (4, -79, 15, "#6ec85a"),
            (20, -67, 13, "#58a84f"), (-3, -58, 17, "#5dae55"), (13, -50, 12, "#74c866"),
            (-25, -48, 10, "#70bd57"), (31, -55, 9, "#4f9848"), (-7, -88, 8, "#7bd36a"),
        ]
        p.setPen(QPen(QColor(40, 92, 42, 165), 0.8))
        for ox, oy, rr, col in leaf_blobs:
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(ox + sway * (0.45 + rr / 30), oy), rr, rr * random.uniform(0.78, 0.92))
        # small visible leaf strokes
        p.setPen(QPen(QColor(38, 91, 40, 105), 0.7, Qt.SolidLine, Qt.RoundCap))
        for ox, oy in [(-18, -65), (-5, -74), (9, -69), (18, -55), (-8, -52), (4, -86)]:
            p.drawLine(QPointF(ox + sway * 0.5, oy), QPointF(ox + 5 + sway * 0.5, oy - 3))
        p.restore()
        p.setPen(Qt.NoPen)

        # Trash bin on the right.
        bx = w - 42
        by = ground_y - 30
        bin_body = QPainterPath()
        bin_body.moveTo(bx + 5, by)
        bin_body.lineTo(bx + 25, by)
        bin_body.lineTo(bx + 30, by + 26)
        bin_body.lineTo(bx, by + 26)
        bin_body.closeSubpath()
        p.setBrush(QColor(137, 146, 158, 225))
        p.setPen(QPen(QColor(82, 91, 102, 240), 1.4))
        p.drawPath(bin_body)
        p.drawRoundedRect(QRectF(bx - 3, by - 5, 34, 6), 3, 3)
        p.setPen(QPen(QColor(90, 99, 109, 180), 1.0))
        p.drawLine(QPointF(bx + 9, by + 4), QPointF(bx + 12, by + 22))
        p.drawLine(QPointF(bx + 18, by + 4), QPointF(bx + 20, by + 22))
        p.setPen(Qt.NoPen)

        # Tiny lamp post by the bin. It glows only at night for a cozy taskbar street feel.
        pole_x = bx - 22
        pole_top = by - 50
        p.setPen(QPen(QColor(84, 92, 104, 220), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(pole_x, ground_y - 9), QPointF(pole_x, pole_top))
        p.drawLine(QPointF(pole_x, pole_top), QPointF(pole_x + 10, pole_top))
        p.setBrush(QColor(58, 62, 72, 230))
        p.setPen(QPen(QColor(92, 98, 110, 210), 1.0))
        lamp_rect = QRectF(pole_x + 7, pole_top - 2, 8, 7)
        p.drawRoundedRect(lamp_rect, 2.2, 2.2)
        if self._daylight_phase() == "night":
            glow_center = QPointF(lamp_rect.center().x(), lamp_rect.center().y() + 1)
            glow = QRadialGradient(glow_center, 34)
            glow.setColorAt(0, QColor(255, 232, 168, 132))
            glow.setColorAt(0.45, QColor(255, 222, 146, 44))
            glow.setColorAt(1, QColor(255, 222, 146, 0))
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(glow_center, 34, 24)
            cone = QPainterPath()
            cone.moveTo(glow_center.x() - 3, glow_center.y() + 3)
            cone.lineTo(glow_center.x() + 3, glow_center.y() + 3)
            cone.lineTo(glow_center.x() + 19, ground_y - 9)
            cone.lineTo(glow_center.x() - 14, ground_y - 9)
            cone.closeSubpath()
            p.setBrush(QColor(255, 228, 150, 24))
            p.drawPath(cone)
            p.setBrush(QColor(255, 238, 182, 238))
            p.drawEllipse(glow_center, 2.4, 2.4)


class ActivityMonitor:
    def __init__(self) -> None:
        self.enabled = False
        self.last_cursor = QCursor.pos()
        self.motion_score = 0.0
        self.last_input_time = time.time()
        self.key_count = 0
        self.click_count = 0
        self.scroll_count = 0
        self.recent_key_score = 0.0
        self.recent_click_score = 0.0
        self.recent_scroll_score = 0.0
        self.listener_error = ""
        self.typed_buffer = ""
        self.last_typed_excerpt = ""
        self.last_type_time = 0.0
        self.word_count = 0
        self._lock = threading.Lock()
        self._listeners_started = False
        self._keyboard_listener = None
        self._mouse_listener = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled and not self._listeners_started:
            self._start_global_listeners()

    def poll_mouse(self) -> None:
        if not self.enabled:
            return
        now = time.time()
        pos = QCursor.pos()
        dx = pos.x() - self.last_cursor.x()
        dy = pos.y() - self.last_cursor.y()
        distance = math.sqrt(dx * dx + dy * dy)
        self.motion_score = self.motion_score * 0.88 + min(distance, 130) * 0.12
        if distance > 2:
            self.last_input_time = now
        self.last_cursor = pos

    def consume_counts(self) -> Dict[str, object]:
        with self._lock:
            keys = self.key_count
            clicks = self.click_count
            scrolls = self.scroll_count
            words = self.word_count
            now_ts = time.time()
            since_typed = now_ts - self.last_type_time if self.last_type_time else 1e9
            # Send the last ~30 typed words so Wally can riff on the actual content,
            # but only while it is FRESH. Stale text is cleared so he doesn't fixate
            # on something the user typed many minutes ago.
            if since_typed <= 20.0:
                typed_excerpt = " ".join(self.typed_buffer.split()[-30:])[-220:]
                if typed_excerpt.strip():
                    self.last_typed_excerpt = typed_excerpt
            else:
                typed_excerpt = ""
            if since_typed > 45.0:
                self.last_typed_excerpt = ""
                self.typed_buffer = ""
            self.key_count = 0
            self.click_count = 0
            self.scroll_count = 0
            self.word_count = 0
            # Keep a rolling window of recent typing, but do not accumulate indefinitely.
            self.typed_buffer = self.typed_buffer[-400:]
        self.recent_key_score = self.recent_key_score * 0.82 + keys
        self.recent_click_score = self.recent_click_score * 0.82 + clicks
        self.recent_scroll_score = self.recent_scroll_score * 0.82 + scrolls
        return {
            "key_count": keys,
            "click_count": clicks,
            "word_count": words,
            "scroll_count": scrolls,
            "recent_key_score": round(self.recent_key_score, 1),
            "recent_click_score": round(self.recent_click_score, 1),
            "recent_scroll_score": round(self.recent_scroll_score, 1),
            "mouse_motion_score": round(self.motion_score, 2),
            "idle_seconds": round(max(0.0, time.time() - self.last_input_time), 1),
            "typed_excerpt": typed_excerpt[-200:],
            "recent_typed_excerpt": self.last_typed_excerpt[-200:],
            "typing_context_note": "This is text the user is typing elsewhere, not speech to the pet.",
            "listener_error": self.listener_error,
        }

    def _start_global_listeners(self) -> None:
        self._listeners_started = True
        try:
            from pynput import keyboard, mouse  # type: ignore

            def on_press(_key) -> None:
                with self._lock:
                    self.key_count += 1
                    self.last_input_time = time.time()
                    self.last_type_time = self.last_input_time
                    try:
                        char = getattr(_key, "char", None)
                    except Exception:
                        char = None
                    def finish_word_if_needed() -> None:
                        if re.search(r"[A-Za-z0-9_]$", self.typed_buffer or ""):
                            self.word_count += 1

                    if char and isinstance(char, str) and char.isprintable():
                        if char.isspace():
                            finish_word_if_needed()
                        self.typed_buffer += char
                    else:
                        name = getattr(_key, "name", "")
                        if name == "space":
                            finish_word_if_needed()
                            self.typed_buffer += " "
                        elif name == "backspace":
                            self.typed_buffer = self.typed_buffer[:-1]
                        elif name in {"enter", "tab"}:
                            finish_word_if_needed()
                            self.typed_buffer += " "
                    self.typed_buffer = self.typed_buffer[-400:]

            def on_scroll(_x, _y, _dx, dy) -> None:
                with self._lock:
                    self.scroll_count += max(1, int(abs(dy)))
                    self.last_input_time = time.time()

            def on_click(_x, _y, _button, pressed) -> None:
                if not pressed:
                    return
                with self._lock:
                    self.click_count += 1
                    self.last_input_time = time.time()

            self._keyboard_listener = keyboard.Listener(on_press=on_press)
            self._mouse_listener = mouse.Listener(on_scroll=on_scroll, on_click=on_click)
            self._keyboard_listener.daemon = True
            self._mouse_listener.daemon = True
            self._keyboard_listener.start()
            self._mouse_listener.start()
        except Exception as exc:
            self.listener_error = str(exc)


class PetWindow(QWidget):
    play_soft_voice_requested = Signal(str, float)

    def __init__(self) -> None:
        super().__init__()
        self.store = SettingsStore()
        self.cfg = self.store.config()
        self.chat_history: List[Dict[str, str]] = []
        self.recent_pet_lines: List[str] = []
        self.recent_pet_line_norms: List[str] = []
        self.last_typing_reaction_excerpt = ""
        self.last_screen_reaction_signature = ""
        self._last_spoken_bubble_at = 0.0
        self.chat_dialog: Optional[ChatDialog] = None
        self.worker: Optional[ChatWorker] = None
        self.reaction_worker: Optional[ReactionWorker] = None
        self.status_worker: Optional[OllamaStatusWorker] = None
        self.reminder_parse_worker: Optional[ReminderParseWorker] = None
        self._active_qthreads: List[QThread] = []
        self.bubble = BubbleWindow()
        self.reminder_alert = ReminderAlertWindow()
        self.parachute_overlay = BigParachuteOverlay()
        self.attention_overlay = AttentionOverlay()
        self.mini_chat = MiniChatBar()
        self.mini_chat.send_message.connect(self.submit_user_message)
        self.debris_overlay = DebrisOverlay(self.store)
        self.activity_monitor = ActivityMonitor()
        self.activity_monitor.set_enabled(self.cfg.screen_awareness_enabled)
        self.play_soft_voice_requested.connect(self._play_soft_voice_variant_sound_now)

        self.setWindowTitle("Wally Rover Pet")
        self.visual_scale = self._scale_from_config()
        self.setFixedSize(self._scaled_size())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._apply_window_flags(initial=True)

        self.expression = "happy"
        self.blink_amount = 0.0
        self.bubble_text = ""
        self.bubble_source = "static"
        self._bubble_shown_at = 0.0
        self._bubble_protected_until = 0.0
        self._pending_bubble_payload: Optional[Tuple[str, int, str]] = None
        self.bubble_timer: Optional[QTimer] = None
        self.drag_offset: Optional[QPoint] = None
        self.is_dragging = False
        self.tick = 0
        self.wheel_phase = 0.0
        self.float_phase = 0.0
        self.head_angle = 0.0
        self.target_point: Optional[QPoint] = None
        self.current_action = "chill"
        self.cleaning_target: Optional[QPoint] = None
        self.last_response_text = ""
        self._facing_left = False
        self._last_activity_bubble_at = 0.0
        self._last_clean_bubble_at = 0.0
        self._last_seen_window_title = get_active_window_title()[:120]
        self._last_window_event_at = 0.0
        self._activity_counts_for_reaction: Optional[Dict[str, object]] = None
        self._event_reaction_seen = 0
        self._event_reaction_used = 0
        self._event_reaction_counters: Dict[str, int] = {}
        self.work_pressure = 0.0
        self._work_burst_keys = 0
        self._work_words_since_pile = 0
        self._last_work_trash_at = 0.0
        self._last_work_overload_at = 0.0
        self._last_debris_threshold_tantrum_at = 0.0
        self._last_work_pressure_event_at = 0.0
        self._last_screen_sample: Optional[Tuple[float, float, float]] = None
        self.carrying_debris = 0
        self.trash_capacity = 6
        self._clean_batch_started_at = 0.0
        self._last_dump_at = 0.0
        self._last_incidental_pickup_at = 0.0
        self._last_non_trash_chat_at = 0.0
        self._last_diversion_from_clean_at = 0.0
        self.ai_online = False
        self.last_ai_success_at = 0.0
        self.last_ai_request_at = 0.0
        self.last_ai_error = ""
        self._last_ai_error_bubble_at = 0.0
        self._pending_activity_note: Optional[Dict[str, object]] = None
        self.last_llm_decision: Dict[str, object] = {}
        self.action_memory: List[Dict[str, object]] = []
        self.current_goal = "playful_wake_up"
        self.current_goal_started_at = time.time()
        self.goal_queue: List[Dict[str, object]] = []
        self.paused_goals: List[Dict[str, object]] = []
        self.goal_lock_until = 0.0
        self.last_goal_switch_at = 0.0
        self._reaction_reason_in_flight = ""
        self.pause_until = 0.0
        self.antenna_pose = "perked"
        self.eye_focus = "side"
        self.eyebrow_pose = "happy"
        self.left_arm_pose = "wave"
        self.right_arm_pose = "idle"
        self.emoji_effect = "✨"
        self.emoji_until = time.time() + 6
        self.dizzy_until = 0.0
        self._last_dizzy_event_at = 0.0
        self._last_mouse_lift_event_at = 0.0
        self._last_throw_followup_at = 0.0
        self._last_attention_trash_at = 0.0
        self._last_attention_throw_check_at = time.time()
        self._last_physical_action_at = 0.0
        self._next_playful_nudge_at = time.time() + random.uniform(14, 28)
        self._command_lock_until = 0.0
        self._shutdown_in_progress = False
        self.fall_mode = "none"
        self.fall_vx = 0.0
        self.fall_vy = 0.0
        self.fall_started_height = 0.0
        self.drag_start_pos: Optional[QPoint] = None
        self._last_glide_ai_at = 0.0
        self._last_sing_at = 0.0
        self._pending_user_instruction = ""
        self._last_user_instruction = ""
        self._last_screen_question = ""
        self._last_movement_pos = QPoint(0, 0)
        self._last_movement_check_at = time.time()
        self._last_forced_goal_at = 0.0
        self.moods: Dict[str, float] = {
            "bored": 28.0,
            "curious": 54.0,
            "excited": 18.0,
            "anxious": 6.0,
            "irritated": 8.0,
            "frustrated": 4.0,
            "playful": 62.0,
            "cozy": 16.0,
            "proud": 8.0,
            "naughty": 18.0,
            "sarcastic": 14.0,
            "encouraging": 22.0,
        }
        self._last_mood_update_at = time.time()

        # Restore durable memory so Wally remembers prior sessions instead of waking
        # up amnesiac every launch. Best-effort: a missing/corrupt file just starts fresh.
        self.memory_store = PetMemoryStore(self.store.config_dir)
        self.memory_store.load()
        self.memory_store.mark_session_start()
        self._day_rhythm = self.memory_store.note_active_day()
        self._session_started_wall = time.time()
        self._lines_spoken_session = 0
        self._last_wellbeing_tick_at = 0.0
        self._last_wellbeing_care_at = 0.0
        self._last_wellbeing_state = "neutral"
        # Co-watch mode: when the user is watching video, Wally sits at the TV and
        # quietly comments along every few minutes instead of disturbing them.
        self._cowatch_enabled = self.store.boolean("pet/cowatch_enabled", True)
        self._cowatch_active = False
        self._cowatch_since = 0.0
        self._last_cowatch_comment_at = 0.0
        self._last_cowatch_obs_at = 0.0
        self._cowatch_interval = random.uniform(300, 600)
        self._cowatch_session: Optional[Dict[str, object]] = None
        # Care/reciprocity: needs the user can satisfy by petting, playing, resting.
        # They decay over time and persist, so caring for Wally is continuous.
        self.needs: Dict[str, float] = {"affection": 70.0, "play": 60.0, "energy": 85.0}
        for key, value in self.memory_store.get_needs().items():
            if key in self.needs:
                self.needs[key] = max(0.0, min(100.0, value))
        self._last_needs_tick_at = time.time()
        self._last_need_request_at = 0.0
        restored_events = self.memory_store.get_action_memory()
        if restored_events:
            self.action_memory = restored_events[-32:]
        restored_lines = self.memory_store.get_recent_pet_lines()
        if restored_lines:
            self.recent_pet_lines = restored_lines[-18:]
            self.recent_pet_line_norms = [self._normalize_pet_line(x) for x in self.recent_pet_lines]
        for key, value in self.memory_store.get_moods().items():
            if key in self.moods:
                self.moods[key] = self._clamp_mood(value)

        self._last_clean_decision_at = 0.0
        self._last_tantrum_at = 0.0
        self._last_joke_fact_at = 0.0
        self._last_debris_count_seen = 0
        self._last_action_name_for_mood = ""
        self._same_action_streak = 0
        self._last_successful_clean_at = 0.0
        self._clean_attempts_without_pickup = 0
        self._last_mood_swing_at = 0.0
        self._last_life_nuance_at = 0.0
        self._last_auto_ball_play_at = 0.0
        self._last_butterfly_ack_at = 0.0
        self._last_ball_encounter_at = 0.0
        self._last_ball_event_llm_at = 0.0
        self._last_butterfly_event_llm_at = 0.0
        self._last_tv_break_started_at = time.time()
        self._tv_break_until = 0.0
        self._tv_break_duration_seconds = 30.0
        self._tv_break_reason = ""
        self._last_tv_break_llm_at = 0.0
        self._tv_break_mid_comment_scheduled = False
        self._ball_cross_window_seen = 0
        self._ball_cross_window_kicks = 0
        self._ball_kick_window_seen = 0
        self._ball_super_done_in_window = False
        self._ball_event_llm_window_seen = 0
        self._ball_event_llm_window_sent = 0
        self._last_pet_center_for_ball: Optional[QPoint] = None
        self._ball_contact_zone_active = False
        self._resume_after_ball_kick: Optional[Dict[str, object]] = None
        self._last_forced_ball_interrupt_at = 0.0
        self._butterfly_window_seen = 0
        self._butterfly_window_chases = 0
        self._butterfly_arrival_seen = 0
        self._butterfly_arrival_chases = 0
        self._butterfly_event_llm_window_seen = 0
        self._butterfly_event_llm_window_sent = 0
        self._resume_after_butterfly_chase: Optional[Dict[str, object]] = None
        self._last_eva_event_llm_at = 0.0
        self._eva_recovery_until = 0.0
        self._eva_sad_until = 0.0
        self._eva_chase_lock_until = 0.0
        self._eva_miss_started = False
        self._eva_last_call_at = 0.0
        self._eva_flyby_seen = 0
        self._audio_lane_name = ""
        self._audio_lane_priority = 0
        self._audio_lane_busy_until = 0.0
        self._audio_lane_interruptible = False
        self._audio_lane_pending = None
        self._audio_lane_pending_priority = -1

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(33)
        self.animation_timer.timeout.connect(self._animate)
        self.animation_timer.start()

        self.behavior_timer = QTimer(self)
        self.behavior_timer.setInterval(1800)
        self.behavior_timer.timeout.connect(self._choose_next_behavior)
        self.behavior_timer.start()

        self.audio_lane_timer = QTimer(self)
        self.audio_lane_timer.setSingleShot(True)
        self.audio_lane_timer.timeout.connect(self._release_audio_lane)

        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(700)
        self.activity_timer.timeout.connect(self._activity_tick)
        self.activity_timer.start()

        self.reminders: List[ReminderItem] = self._load_reminders()
        self.reminder_timer = QTimer(self)
        self.reminder_timer.setInterval(1000)
        self.reminder_timer.timeout.connect(self._reminder_tick)
        self.reminder_timer.start()

        # Periodically snapshot durable memory so a crash/forced-quit still preserves
        # the relationship and recent state (closeEvent also flushes on clean exit).
        self.memory_save_timer = QTimer(self)
        self.memory_save_timer.setInterval(30_000)
        self.memory_save_timer.timeout.connect(self._save_persistent_memory)
        self.memory_save_timer.start()

        self.ai_reaction_timer = QTimer(self)
        self.ai_reaction_timer.setSingleShot(True)
        self.ai_reaction_timer.timeout.connect(lambda: self.request_ai_reaction("scheduled_scene_check", use_vision=True))

        self.ai_heartbeat_timer = QTimer(self)
        self.ai_heartbeat_timer.setSingleShot(True)
        self.ai_heartbeat_timer.timeout.connect(lambda: self.request_ai_reaction("ambient_character_tick", use_vision=False))

        self.butterfly_timer = QTimer(self)
        self.butterfly_timer.setSingleShot(True)
        self.butterfly_timer.timeout.connect(self._butterfly_event)

        self.eva_timer = QTimer(self)
        self.eva_timer.setSingleShot(True)
        self.eva_timer.timeout.connect(self._eva_flyby_event)

        self._create_tray_icon()
        self._place_initially()
        self._update_taskbar_lane()
        self.mini_chat.show()
        self.debris_overlay.set_enabled(self.cfg.debris_enabled or self.cfg.weather_enabled)
        self.debris_overlay.set_weather_enabled(self.cfg.weather_enabled)
        if self.cfg.debris_enabled:
            self.debris_overlay.summon_debris(8)
        self.show()
        QTimer.singleShot(0, self._sync_window_stack)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown_workers)
        self._schedule_next_ai_reaction()
        self._schedule_next_ambient_ai()
        self._schedule_next_butterfly()
        self._schedule_next_eva_flyby()
        QTimer.singleShot(1200, self.snap_to_taskbar_lane)
        # Instant in-character hello (no LLM wait), tuned to how well he knows you.
        QTimer.singleShot(700, self._greet_on_launch)
        QTimer.singleShot(1800, lambda: self.request_ai_reaction("startup_self_intro", force=True, use_vision=False))

    def _scale_from_config(self) -> float:
        return max(0.25, min(1.0, self.store.config().pet_scale_percent / 100.0))

    def _scaled_size(self) -> QSize:
        return QSize(max(118, int(BASE_W * self.visual_scale)), max(96, int(BASE_H * self.visual_scale)))

    def _apply_window_flags(self, initial: bool = False) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.store.config().always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible and not initial:
            self.show()
            QTimer.singleShot(0, self._sync_window_stack)

    def _apply_config_changes(self) -> None:
        old_center = self.frameGeometry().center()
        self.cfg = self.store.config()
        self.visual_scale = self._scale_from_config()
        self.setFixedSize(self._scaled_size())
        self.move(old_center.x() - self.width() // 2, old_center.y() - self.height() // 2)
        self._apply_window_flags()
        self.activity_monitor.set_enabled(self.cfg.screen_awareness_enabled)
        self.debris_overlay.set_enabled(self.cfg.debris_enabled or self.cfg.weather_enabled)
        self.debris_overlay.set_weather_enabled(self.cfg.weather_enabled)
        self._update_taskbar_lane()
        self.snap_to_taskbar_lane()
        QTimer.singleShot(0, self._sync_window_stack)
        self.store.flush()
        self._schedule_next_ai_reaction()
        self._schedule_next_ambient_ai()
        self._schedule_next_butterfly()
        if self.cfg.ai_reactions_enabled:
            QTimer.singleShot(400, lambda: self.request_ai_reaction("settings_applied_choose_intent", force=True, use_vision=False))

    def _place_initially(self) -> None:
        lane, orientation = self._taskbar_lane()
        if lane.isNull():
            self.move(100, 100)
            return
        if orientation in {"bottom", "top", "unknown"}:
            x = lane.right() - self.width() - 70
            y = self._lane_y(lane, orientation)
        elif orientation == "left":
            x = lane.left() + 4
            y = lane.bottom() - self.height() - 80
        else:
            x = lane.right() - self.width() - 4
            y = lane.bottom() - self.height() - 80
        self.move(self._clamp_to_lane(QPoint(x, y)))

    def _create_tray_icon(self) -> None:
        self.tray_icon = QSystemTrayIcon(self._make_icon(), self)
        self.tray_icon.setToolTip("Wally Rover Pet")
        menu = QMenu()
        open_chat = menu.addAction("Chat with Wally")
        open_chat.triggered.connect(self.open_chat)
        settings = menu.addAction("Settings")
        settings.triggered.connect(self.open_settings)
        menu.addSeparator()
        react_now = menu.addAction("React to screen now")
        react_now.triggered.connect(lambda: self.request_ai_reaction("manual_screen_check", force=True, use_vision=True))
        summon = menu.addAction("Drop some debris")
        summon.triggered.connect(lambda: self.debris_overlay.summon_debris(12))
        butterfly = menu.addAction("Release a butterfly")
        butterfly.triggered.connect(lambda: self._butterfly_event(force=True))
        eva = menu.addAction("Send EVA flyby")
        eva.triggered.connect(lambda: self._eva_flyby_event(force=True))
        reminders = menu.addAction("Show pending reminders")
        reminders.triggered.connect(self._show_pending_reminders)
        show_action = menu.addAction("Show Pet")
        show_action.triggered.connect(self.showNormal)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()

    def _make_icon(self) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d99a3a"))
        p.setPen(QPen(QColor("#5b4526"), 3))
        p.drawRoundedRect(QRectF(15, 30, 34, 22), 6, 6)
        p.setBrush(QColor("#2a3842"))
        p.drawRoundedRect(QRectF(18, 49, 28, 8), 4, 4)
        p.setBrush(QColor("#c98d38"))
        p.drawRoundedRect(QRectF(29, 22, 6, 10), 3, 3)
        p.setBrush(QColor("#2a333a"))
        p.drawEllipse(QRectF(14, 10, 18, 18))
        p.drawEllipse(QRectF(32, 10, 18, 18))
        p.setBrush(QColor("#8ee8ff"))
        p.drawEllipse(QRectF(20, 16, 6, 6))
        p.drawEllipse(QRectF(38, 16, 6, 6))
        p.end()
        return QIcon(pix)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick}:
            self.open_chat()

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt override
        menu = QMenu(self)
        chat_action = menu.addAction("Chat with Wally...")
        chat_action.triggered.connect(self.open_chat)
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self.open_settings)
        menu.addSeparator()

        react_action = menu.addAction("React to screen now")
        react_action.triggered.connect(lambda: self.request_ai_reaction("manual_screen_check", force=True, use_vision=True))
        status_action = menu.addAction("Test Ollama connection/status")
        status_action.triggered.connect(self.show_ai_status)
        brain_action = menu.addAction("Show last LLM decision")
        brain_action.triggered.connect(self.show_last_llm_decision)
        debris_action = menu.addAction("Drop leaves/paper")
        debris_action.triggered.connect(lambda: self.debris_overlay.summon_debris(12))
        butterfly_action = menu.addAction("Release a butterfly")
        butterfly_action.triggered.connect(lambda: self._butterfly_event(force=True))
        menu.addSeparator()

        roam_action = QAction("Move around", self, checkable=True)
        roam_action.setChecked(self.store.config().roam_enabled)
        roam_action.toggled.connect(self._set_roam_enabled)
        menu.addAction(roam_action)

        taskbar_action = QAction("Taskbar / dock lane only", self, checkable=True)
        taskbar_action.setChecked(self.store.config().taskbar_only)
        taskbar_action.toggled.connect(self._set_taskbar_only)
        menu.addAction(taskbar_action)

        debris_toggle = QAction("Debris cleaning", self, checkable=True)
        debris_toggle.setChecked(self.store.config().debris_enabled)
        debris_toggle.toggled.connect(self._set_debris_enabled)
        menu.addAction(debris_toggle)

        weather_toggle = QAction("Weather ambience", self, checkable=True)
        weather_toggle.setChecked(self.store.config().weather_enabled)
        weather_toggle.toggled.connect(self._set_weather_enabled)
        menu.addAction(weather_toggle)

        ai_reactions = QAction("Ollama reactions", self, checkable=True)
        ai_reactions.setChecked(self.store.config().ai_reactions_enabled)
        ai_reactions.toggled.connect(self._set_ai_reactions_enabled)
        menu.addAction(ai_reactions)

        awareness_action = QAction("Mouse/typing/scroll awareness", self, checkable=True)
        awareness_action.setChecked(self.store.config().screen_awareness_enabled)
        awareness_action.toggled.connect(self._set_screen_awareness_enabled)
        menu.addAction(awareness_action)

        screenshot_action = QAction("Vision screenshot glances", self, checkable=True)
        screenshot_action.setChecked(self.store.config().screenshot_reactions_enabled)
        screenshot_action.toggled.connect(self._set_screenshot_reactions_enabled)
        menu.addAction(screenshot_action)

        top_action = QAction("Always on top", self, checkable=True)
        top_action.setChecked(self.store.config().always_on_top)
        top_action.toggled.connect(self._set_always_on_top)
        menu.addAction(top_action)

        tts_action = QAction("Speak replies aloud", self, checkable=True)
        tts_action.setChecked(self.store.config().tts_enabled)
        tts_action.toggled.connect(self._set_tts_enabled)
        menu.addAction(tts_action)

        menu.addSeparator()
        reset_action = menu.addAction("Reset chat memory")
        reset_action.triggered.connect(self.reset_memory)
        hide_action = menu.addAction("Hide")
        hide_action.triggered.connect(self.hide)
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)
        menu.exec(event.globalPos())

    def _set_roam_enabled(self, checked: bool) -> None:
        self.store.set_value("pet/roam_enabled", checked)
        self._apply_config_changes()
        self.show_bubble("Roaming enabled." if checked else "I'll stay put.", 2500)

    def _set_taskbar_only(self, checked: bool) -> None:
        self.store.set_value("pet/taskbar_only", checked)
        self._apply_config_changes()
        self.show_bubble("Taskbar patrol mode." if checked else "Full desktop roaming enabled.", 2800)

    def _set_debris_enabled(self, checked: bool) -> None:
        self.store.set_value("pet/debris_enabled", checked)
        self._apply_config_changes()
        if checked:
            self.debris_overlay.summon_debris(8)
        self.show_bubble("Cleanup duty online." if checked else "No more debris for now.", 2800)

    def _set_weather_enabled(self, checked: bool) -> None:
        self.store.set_value("pet/weather_enabled", checked)
        self._apply_config_changes()
        self.show_bubble("Tiny weather online." if checked else "Weather layer disabled.", 2800)

    def _set_ai_reactions_enabled(self, checked: bool) -> None:
        self.store.set_value("awareness/ai_reactions_enabled", checked)
        self._apply_config_changes()
        self.show_bubble("Ollama character brain on." if checked else "Local fallback only.", 2800)
        if checked:
            QTimer.singleShot(500, lambda: self.request_ai_reaction("manual_ai_enabled", force=True, use_vision=False))

    def _set_screen_awareness_enabled(self, checked: bool) -> None:
        self.store.set_value("awareness/screen_awareness_enabled", checked)
        self._apply_config_changes()
        self.show_bubble("Activity awareness on." if checked else "I won't watch activity.", 2800)

    def _set_screenshot_reactions_enabled(self, checked: bool) -> None:
        self.store.set_value("awareness/screenshot_reactions_enabled", checked)
        self._apply_config_changes()
        self.show_bubble(
            "Vision screenshot glances enabled." if checked else "Vision screenshot glances disabled.",
            3200,
        )

    def _set_always_on_top(self, checked: bool) -> None:
        self.store.set_value("pet/always_on_top", checked)
        self._apply_config_changes()
        self.show_bubble("Always-on-top enabled." if checked else "Always-on-top disabled.", 2500)

    def _set_tts_enabled(self, checked: bool) -> None:
        self.store.set_value("pet/tts_enabled", checked)
        self.cfg = self.store.config()
        self.show_bubble("Voice replies enabled." if checked else "Voice replies muted.", 2500)

    def show_ai_status(self) -> None:
        cfg = self.store.config()
        if self._thread_running(self.status_worker):
            self.show_bubble("Already checking Ollama...", 2600)
            return
        age = max(0, int(time.time() - self.last_ai_success_at)) if self.last_ai_success_at else None
        prefix = f"Last AI: {age}s ago. " if age is not None else ""
        self.show_bubble(prefix + "Checking local Ollama...", 5000)
        self.status_worker = OllamaStatusWorker(cfg)
        self.status_worker.finished_ok.connect(self._on_status_ok)
        self.status_worker.failed.connect(self._on_status_failed)
        self.status_worker.finished.connect(self._status_worker_finished)
        self._track_thread(self.status_worker)
        self.status_worker.start()


    def show_last_llm_decision(self) -> None:
        if not self.last_llm_decision:
            self.show_bubble("No LLM move yet.", 3000)
            return
        action = str(self.last_llm_decision.get("action", "?"))
        target = str(self.last_llm_decision.get("target", "?"))
        expr = str(self.last_llm_decision.get("expression", "?"))
        queue = str(self.last_llm_decision.get("queue", "keep"))
        override = bool(self.last_llm_decision.get("override", False))
        bubble = str(self.last_llm_decision.get("bubble", ""))
        self.show_bubble(shorten_for_bubble(f"LLM: {action} → {target}, {expr}, q={queue}, o={override}. {bubble}"), 7000)

    def _on_status_ok(self, status: Dict[str, object]) -> None:
        if status.get("ok"):
            base = str(status.get("base_url", ""))
            model = str(status.get("model", ""))
            found = bool(status.get("model_found"))
            family = bool(status.get("same_family_found"))
            models = status.get("models", [])
            self.ai_online = found
            if found:
                self.show_bubble(f"Ollama reachable: {model} ✓", 6500)
            elif family:
                self.show_bubble(f"Ollama reachable, but exact tag missing. Check Settings: {model}", 8500)
            else:
                sample = ", ".join(str(m) for m in list(models)[:3]) if isinstance(models, list) else ""
                self.show_bubble(shorten_for_bubble(f"Ollama is running at {base}, but {model} is not pulled. Models: {sample}"), 9500)
        else:
            errors = status.get("errors", [])
            msg = "; ".join(str(e) for e in errors) if isinstance(errors, list) else str(errors)
            self.ai_online = False
            self.last_ai_error = msg
            self.show_bubble(self._friendly_ollama_error(msg), 8500)

    def _on_status_failed(self, error: str) -> None:
        self.ai_online = False
        self.last_ai_error = error
        self.show_bubble(self._friendly_ollama_error(error), 8500, source="error")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.store, self)
        if dialog.exec() == QDialog.Accepted:
            self._apply_config_changes()
            self.show_bubble("Saved ✓", 2200)

    def open_chat(self) -> None:
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self)
            self.chat_dialog.send_message.connect(self.submit_user_message)
            self.chat_dialog.settings_requested.connect(self.open_settings)
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()
        self.chat_dialog.focus_input()

    def reset_memory(self) -> None:
        self.chat_history.clear()
        self.action_memory.clear()
        self.recent_pet_lines.clear()
        self.recent_pet_line_norms.clear()
        self._lines_spoken_session = 0
        store = getattr(self, "memory_store", None)
        if store is not None:
            store.clear()
            store.mark_session_start()
        if self.chat_dialog:
            self.chat_dialog.append_pet("Memory reset. Fresh little rover brain ready.")
        self.show_bubble("Memory reset. Fresh start!", 2800)

    def _remember_event(self, kind: str, text: str = "", data: Optional[Dict[str, object]] = None) -> None:
        now_dt = datetime.now()
        event: Dict[str, object] = {
            "t": round(time.time(), 1),
            "at": now_dt.strftime("%H:%M:%S"),
            "kind": kind,
            "goal": self.current_goal,
            "action": self.current_action,
            "did": self.current_action,
            "expression": self.expression,
        }
        if text:
            short_text = shorten_for_bubble(text, max_len=90)
            event["text"] = short_text
            if kind in {"ai_bubble", "pet_chat", "butterfly_arrived"} or "chat" in kind:
                event["said"] = short_text
        if data:
            event.update(data)
        self.action_memory.append(event)
        self.action_memory = self.action_memory[-32:]

    def _reminders_path(self) -> Path:
        return self.store.config_dir / "reminders_v8_34.json"

    def _load_reminders(self) -> List[ReminderItem]:
        path = self._reminders_path()
        out: List[ReminderItem] = []
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            if isinstance(data, list):
                now = time.time()
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    due = float(item.get("due_ts", 0))
                    if due > now - 60:
                        out.append(ReminderItem(
                            due_ts=due,
                            text=str(item.get("text", "Reminder")).strip() or "Reminder",
                            created_ts=float(item.get("created_ts", now)),
                            source=str(item.get("source", "saved")),
                            id=str(item.get("id", "")),
                        ))
        except Exception:
            pass
        return sorted(out, key=lambda r: r.due_ts)

    def _save_reminders(self) -> None:
        try:
            data = [
                {"due_ts": r.due_ts, "text": r.text, "created_ts": r.created_ts, "source": r.source, "id": r.id}
                for r in self.reminders
            ]
            path = self._reminders_path()
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            pass

    def _is_reminder_command(self, text: str) -> bool:
        t = re.sub(r"\s+", " ", text.lower().strip().strip("'\"`“”‘’"))
        reminder_phrases = (
            "remind me", "please remind me", "can you remind me", "could you remind me",
            "set reminder", "set a reminder", "create reminder", "make reminder",
            "alert me", "set an alert", "ping me", "notify me"
        )
        if any(p in t for p in reminder_phrases):
            return True
        # Also catch short natural forms like "reminder in 10 secs to test".
        return bool(re.search(r"\breminder\b.*\b(in|after|at|tomorrow)\b", t))

    def _extract_reminder_message(self, text: str) -> str:
        msg = text.strip().strip("'\"`“”‘’")
        # Remove polite prefix up to the reminder intent, wherever it appears.
        msg = re.sub(
            r"^.*?\b(remind me|set a reminder|set reminder|create reminder|make reminder|set an alert|alert me|ping me|notify me|reminder)\b\s*",
            "",
            msg,
            flags=re.I,
        ).strip()
        amount_words = r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|forty five|sixty)"
        # Remove relative time whether it appears before or after the task.
        msg = re.sub(rf"\b(in|after)\s+(?:about\s+)?{amount_words}\s*(seconds?|secs?|sec|s|minutes?|mins?|minute|min|m|hours?|hrs?|hr|h|days?|d)\b", "", msg, flags=re.I).strip()
        msg = re.sub(r"\bat\s+((today|tomorrow)\s+)?\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", msg, flags=re.I).strip()
        msg = re.sub(r"\btomorrow\s+at\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b", "", msg, flags=re.I).strip()
        # Human phrasing often says: "to eat /to have lunch". Make it readable.
        msg = re.sub(r"\s*/\s*to\s+", " / ", msg, flags=re.I)
        msg = re.sub(r"\s*/\s*", " / ", msg)
        msg = re.sub(r"^(to|that|about|for)\s+", "", msg, flags=re.I).strip()
        msg = re.sub(r"\s+", " ", msg).strip(" .,:;-_")
        return msg or "Reminder"

    def _parse_reminder_locally(self, text: str) -> Optional[ReminderItem]:
        now = datetime.now()
        raw = text.strip()
        lower = raw.lower()

        amount_word_map = {
            "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "forty five": 45, "sixty": 60,
        }
        amount_expr = r"(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty(?:\s+five)?|sixty)"
        m = re.search(rf"\b(?:in|after)\s+(?:about\s+)?{amount_expr}\s*(seconds?|secs?|sec|s|minutes?|mins?|minute|min|m|hours?|hrs?|hr|h|days?|d)\b", lower)
        due_dt: Optional[datetime] = None
        if m:
            raw_amount = m.group(1).strip().lower()
            amount = int(raw_amount) if raw_amount.isdigit() else amount_word_map.get(raw_amount, 1)
            unit = m.group(2).lower()
            if unit in {"s", "sec", "secs", "second", "seconds"} or unit.startswith("sec"):
                due_dt = now + timedelta(seconds=amount)
            elif unit in {"m", "min", "mins", "minute", "minutes"} or unit.startswith("min"):
                due_dt = now + timedelta(minutes=amount)
            elif unit in {"h", "hr", "hrs", "hour", "hours"} or unit.startswith(("hour", "hr")):
                due_dt = now + timedelta(hours=amount)
            elif unit in {"d", "day", "days"} or unit.startswith("day"):
                due_dt = now + timedelta(days=amount)

        if due_dt is None:
            # at 5pm / at 17:30 / tomorrow at 9
            m = re.search(r"\bat\s+((today|tomorrow)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lower)
            if m:
                day_word = (m.group(2) or "today").lower()
                hour = int(m.group(3))
                minute = int(m.group(4) or 0)
                ampm = (m.group(5) or "").lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                if ampm == "am" and hour == 12:
                    hour = 0
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    due_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if day_word == "tomorrow":
                        due_dt += timedelta(days=1)
                    elif due_dt <= now:
                        due_dt += timedelta(days=1)

        if due_dt is None:
            return None

        msg = self._extract_reminder_message(raw)
        return ReminderItem(
            due_ts=due_dt.timestamp(),
            text=msg,
            created_ts=time.time(),
            source="local",
            id=f"r{int(time.time()*1000)}",
        )

    def _schedule_reminder(self, reminder: ReminderItem, announce: bool = True) -> None:
        self.reminders.append(reminder)
        self.reminders = sorted(self.reminders, key=lambda r: r.due_ts)
        self._save_reminders()
        if announce:
            due = datetime.fromtimestamp(reminder.due_ts)
            when = due.strftime("%H:%M")
            self.show_bubble(f"Reminder set for {when}.", 8500, source="tool")
            self._remember_event("reminder_set", text=reminder.text, data={"due": when, "did": "set_reminder"})

    def _start_reminder_parse_with_ollama(self, text: str) -> bool:
        if self._thread_running(self.reminder_parse_worker):
            self.show_bubble("Reminder brain busy!", 6000)
            return True
        cfg = self.store.config()
        self.reminder_parse_worker = ReminderParseWorker(cfg, text, datetime.now().isoformat(timespec="seconds"))
        self.reminder_parse_worker.finished_ok.connect(lambda result, original=text: self._on_reminder_parse_ok(result, original))
        self.reminder_parse_worker.failed.connect(lambda error, original=text: self._on_reminder_parse_failed(error, original))
        self.reminder_parse_worker.finished.connect(self._reminder_parse_worker_finished)
        self._track_thread(self.reminder_parse_worker)
        self.reminder_parse_worker.start()
        self.show_bubble("Parsing reminder!", 6500, source="tool")
        return True

    def _on_reminder_parse_ok(self, result: Dict[str, object], original: str) -> None:
        try:
            if result.get("ok") and result.get("due_iso"):
                due_dt = datetime.fromisoformat(str(result.get("due_iso")).replace("Z", ""))
                if due_dt.timestamp() <= time.time() - 1:
                    due_dt += timedelta(days=1)
                msg = str(result.get("text") or self._extract_reminder_message(original)).strip() or "Reminder"
                self._schedule_reminder(ReminderItem(due_dt.timestamp(), msg, time.time(), source="ollama", id=f"r{int(time.time()*1000)}"))
                return
        except Exception:
            pass
        fallback = self._parse_reminder_locally(original)
        if fallback is not None:
            self._schedule_reminder(fallback)
            return
        self.show_bubble("I need a clearer time.", 8500, source="tool")

    def _on_reminder_parse_failed(self, error: str, original: str) -> None:
        fallback = self._parse_reminder_locally(original)
        if fallback is not None:
            self._schedule_reminder(fallback)
            return
        self.show_bubble("Reminder parse failed.", 8500, source="error")
        self._remember_event("reminder_parse_failed", text=original, data={"error": shorten_for_bubble(error, max_len=80)})

    def _reminder_parse_worker_finished(self) -> None:
        self.reminder_parse_worker = None
        self._forget_finished_threads()

    def _tiny_agent_skill_context(self) -> Dict[str, object]:
        return {
            "principle": "local tiny tools first; Ollama only for ambiguous parse",
            "skills": TINY_AGENT_SKILLS,
            "pending_reminders": len(self.reminders),
        }

    def _tiny_agent_handle(self, text: str) -> bool:
        """Tiny local agent router for cheap deterministic operations.

        This runs before chat. It avoids spending Ollama tokens for simple tools,
        but reminder parsing can fall back to the ReminderParseWorker when needed.
        """
        raw = text.strip().strip("'\"`“”‘’")
        t = re.sub(r"\s+", " ", raw.lower()).strip()
        if not t:
            return False

        # Reminder tools first. This fixes commands like: Remind me in 10 secs to test the code.
        if self._handle_reminder_command(raw):
            return True

        # Tiny local utility tools.
        if any(p in t for p in ["throw trash", "toss trash", "get my attention", "attention trash", "throw for attention"]):
            self._remember_event("tiny_tool_used", text="throw_attention_trash", data={"did": "tool_throw_attention_trash"})
            self._apply_reaction_action("throw_trash", 2, "screen", allow_attention_throw=True)
            self.show_bubble("Attention trash launched!", 8000, source="tool")
            return True
        if any(p in t for p in ["kick ball", "kick the ball", "play ball", "play basketball", "basketball"]):
            self._remember_event("tiny_tool_used", text="kick_ball", data={"did": "tool_kick_ball"})
            self._apply_reaction_action("kick_ball", 2, "basketball")
            self.show_bubble("Ball protocol activated.", 7500, source="tool")
            return True
        if any(p in t for p in ["send butterfly", "summon butterfly", "release butterfly", "bring butterfly"]):
            self._remember_event("tiny_tool_used", text="summon_butterfly", data={"did": "tool_summon_butterfly"})
            self._butterfly_event(force=True)
            return True
        if any(p in t for p in ["send eva", "summon eva", "eva flyby", "bring eva", "call eva"]):
            self._remember_event("tiny_tool_used", text="summon_eva", data={"did": "tool_summon_eva_flyby"})
            self._eva_flyby_event(force=True)
            return True
        if t in {"react to screen now", "check screen", "check my screen", "look at my screen", "look at screen", "screen check", "analyze screen", "react to screen"}:
            self._remember_event("tiny_tool_used", text="manual_screen_check", data={"did": "tool_manual_screen_check"})
            self.request_ai_reaction("manual_screen_check", force=True, use_vision=True)
            return True
        if t in {"mute", "silent", "be silent", "go silent", "mute sounds", "sounds off", "sound off", "voice off", "stop sounds", "stop sound"}:
            self._remember_event("tiny_tool_used", text="sounds_off", data={"did": "tool_sounds_off"})
            self._set_tts_enabled(False)
            return True
        if t in {"unmute", "unsilent", "sound on", "sounds on", "voice on", "enable sounds", "enable sound", "turn sounds on", "turn sound on"}:
            self._remember_event("tiny_tool_used", text="sounds_on", data={"did": "tool_sounds_on"})
            self._set_tts_enabled(True)
            return True
        if t in {"weather off", "disable weather", "weather disabled", "climate off", "turn weather off"}:
            self._remember_event("tiny_tool_used", text="weather_off", data={"did": "tool_weather_off"})
            self._set_weather_enabled(False)
            return True
        if t in {"weather on", "enable weather", "weather enabled", "climate on", "turn weather on"}:
            self._remember_event("tiny_tool_used", text="weather_on", data={"did": "tool_weather_on"})
            self._set_weather_enabled(True)
            return True
        if any(p in t for p in ["make it rain", "start rain", "rain please", "rainy mode", "make rainy"]):
            self._remember_event("tiny_tool_used", text="weather_rainy", data={"did": "tool_weather_rainy"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_weather_mode("rainy", 120.0)
            self.show_bubble("Rain mode drifting in.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it sunny", "sunny mode", "show sun", "bring sun"]):
            self._remember_event("tiny_tool_used", text="weather_sunny", data={"did": "tool_weather_sunny"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("day")
            self.debris_overlay.set_weather_mode("sunny", 120.0)
            self.show_bubble("Sunny mode online.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it cloudy", "cloudy mode", "more clouds"]):
            self._remember_event("tiny_tool_used", text="weather_cloudy", data={"did": "tool_weather_cloudy"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_weather_mode("cloudy", 120.0)
            self.show_bubble("Cloud cover arriving.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it windy", "windy mode", "more wind"]):
            self._remember_event("tiny_tool_used", text="weather_windy", data={"did": "tool_weather_windy"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_weather_mode("windy", 120.0)
            self.show_bubble("Wind picking up.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it night", "night mode", "show night", "bring night"]):
            self._remember_event("tiny_tool_used", text="daylight_night", data={"did": "tool_daylight_night"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("night")
            self.show_bubble("Night mode online.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it day", "day mode", "show day", "bring daylight"]):
            self._remember_event("tiny_tool_used", text="daylight_day", data={"did": "tool_daylight_day"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("day")
            self.show_bubble("Daylight mode online.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it dawn", "dawn mode", "sunrise mode"]):
            self._remember_event("tiny_tool_used", text="daylight_dawn", data={"did": "tool_daylight_dawn"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("dawn")
            self.show_bubble("Dawn mode glowing.", 7500, source="tool")
            return True
        if any(p in t for p in ["make it dusk", "dusk mode", "sunset mode"]):
            self._remember_event("tiny_tool_used", text="daylight_dusk", data={"did": "tool_daylight_dusk"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("dusk")
            self.show_bubble("Dusk mode warming up.", 7500, source="tool")
            return True
        if t in {"real time mode", "use real time", "clock mode", "clear time override"}:
            self._remember_event("tiny_tool_used", text="daylight_realtime", data={"did": "tool_daylight_realtime"})
            self._set_weather_enabled(True)
            self.debris_overlay.set_daylight_override("")
            self.show_bubble("Back to real sky time.", 7500, source="tool")
            return True
        if any(p in t for p in ["send wind", "summon wind", "send leaves", "send debris", "send trash"]):
            return self._execute_wind_summon_command(raw)
        if re.search(r"\b(clean|clean up|clean this|sweep)\b", t):
            self._apply_reaction_action("clean", 2, "nearest_debris")
            self.show_bubble("Tiny cleaning mission.", 7500, source="tool")
            return True
        if any(p in t for p in ["watch tv", "go sofa", "sit sofa", "tv break", "send eva", "summon eva", "eva flyby"]):
            self._apply_reaction_action("watch_tv", 2, "tv_sofa")
            self.show_bubble("TV break authorized.", 7500, source="tool")
            return True
        if t in {"skills", "show skills", "what can you do", "tiny tools"}:
            self.show_bubble("Reminders, ball, butterfly, EVA, trash, wind, weather.", 11000, source="tool")
            return True
        return False

    def _handle_reminder_command(self, text: str) -> bool:
        lower = text.lower().strip()
        if lower in {"list reminders", "show reminders", "pending reminders"}:
            self._show_pending_reminders()
            return True
        if lower in {"clear reminders", "delete reminders", "cancel reminders"}:
            self.reminders.clear()
            self._save_reminders()
            self.show_bubble("All reminders cleared.", 8500, source="tool")
            return True
        if not self._is_reminder_command(text):
            return False
        local = self._parse_reminder_locally(text)
        if local is not None:
            self._schedule_reminder(local)
            return True
        return self._start_reminder_parse_with_ollama(text)

    def _show_pending_reminders(self) -> None:
        if not self.reminders:
            self.show_bubble("No pending reminders.", 8500, source="tool")
            return
        lines = []
        for item in self.reminders[:3]:
            lines.append(f"{datetime.fromtimestamp(item.due_ts).strftime('%H:%M')} {item.text}")
        self.show_bubble(" | ".join(lines), 13000, source="tool")

    def _reminder_tick(self) -> None:
        if not self.reminders:
            return
        now = time.time()
        due = [r for r in self.reminders if r.due_ts <= now]
        if not due:
            return
        self.reminders = [r for r in self.reminders if r.due_ts > now]
        self._save_reminders()
        for reminder in due[:3]:
            self._trigger_reminder_alert(reminder)

    def _trigger_reminder_alert(self, reminder: ReminderItem) -> None:
        # Wally grabs attention by throwing trash toward screen center,
        # then holding a placard instead of showing a scary popup.
        pet_center = self.frameGeometry().center()
        self.attention_overlay.fling_from(pet_center, count=18)
        if hasattr(self.debris_overlay, "toss_attention_debris"):
            self.debris_overlay.toss_attention_debris(6)
        self.reminder_alert.show_alert(reminder.text, self.frameGeometry())
        self.show_bubble(f"REMINDER: {reminder.text}", 24000, source="tool")
        self.set_expression("surprised")
        self.pause_until = time.time() + 6.0
        self.current_action = "pause"
        self.target_point = None
        self._apply_body_controls({
            "antenna": "wiggle",
            "eyes": "user",
            "eyebrow": "surprised",
            "emoji": "⚠️",
            "left_arm": "hold",
            "right_arm": "hold",
        })
        self._speak(f"Reminder. {reminder.text}")
        self._remember_event("reminder_alert", text=reminder.text, data={"did": "hold_reminder_placard", "target": "screen_center"})
        if self.cfg.ai_reactions_enabled:
            self._pending_activity_note = {"kind": "reminder_alert", "text": reminder.text, "hint": "Wally is holding a reminder placard with bells."}

    def _handle_cowatch_command(self, text: str) -> bool:
        """Let the user turn co-watch mode on/off by chatting to Wally."""
        t = text.lower().strip()
        enable_hits = ("co-watch", "cowatch", "co watch", "watch with me", "watch together", "watch this with me")
        disable_hits = ("stop watching", "stop co-watch", "stop cowatch", "watch alone", "don't watch", "dont watch", "leave me to watch")
        wants_disable = any(h in t for h in disable_hits)
        wants_enable = (not wants_disable) and any(h in t for h in enable_hits)
        if not wants_enable and not wants_disable:
            return False
        self._cowatch_enabled = wants_enable
        self.store.set_value("pet/cowatch_enabled", self._cowatch_enabled)
        self.store.flush()
        if wants_disable and self._cowatch_active:
            self._end_cowatch_session()
        msg = "Co-watch on! I'll grab the sofa. 🍿" if wants_enable else "Okay, you watch solo. I'll be around. 👋"
        self.show_bubble(msg, 5200, source="tool")
        if self.chat_dialog:
            self.chat_dialog.append_pet(msg)
        return True

    def submit_user_message(self, text: str) -> None:
        self.cfg = self.store.config()
        self._last_chat_user_text = text
        # Talking to him is affection too.
        self._satisfy_need("affection", 8, react=False)
        if self.chat_dialog:
            self.chat_dialog.append_user(text)

        if self._handle_cowatch_command(text):
            self.chat_history.append({"role": "user", "content": text})
            self.chat_history = self.chat_history[-18:]
            return

        # Tiny agent tools run before the chat worker, so reminders are never lost
        # just because a previous Ollama chat is still finishing.
        if self._tiny_agent_handle(text):
            self.chat_history.append({"role": "user", "content": text})
            self.chat_history = self.chat_history[-18:]
            return

        if self._execute_summon_command(text):
            self.chat_history.append({"role": "user", "content": text})
            self.chat_history = self.chat_history[-18:]
            return

        if self._thread_running(self.worker):
            self.show_bubble("Tiny brain busy!", 1800, source="static")
            return

        needs_screen = self._message_needs_screen(text)
        is_command = self._message_is_action_command(text)
        if is_command:
            self._pending_user_instruction = text
            self._last_user_instruction = text
        if needs_screen:
            self._last_screen_question = text

        # When the user speaks, Wally stops roaming and visibly pays attention.
        self.current_action = "listen"
        self.target_point = None
        self.pause_until = time.time() + 16
        self.eye_focus = "user"
        self.eyebrow_pose = "curious"
        self.left_arm_pose = "shy"
        self.right_arm_pose = "wave"
        self.antenna_pose = "perked"
        self.emoji_effect = "?"
        self.emoji_until = time.time() + 5

        direct_command_executed = False
        if is_command:
            direct_command_executed = self._execute_direct_user_command(text)

        context_hint = self._build_brain_context(reason="chat_context", include_screenshot=False, consume_counts=False)
        prompt = (
            f"USER_TO_PET: {text}\n"
            f"WORLD: {json.dumps(context_hint, ensure_ascii=False, separators=(',', ':'))[:4200]}\n"
            f"Reply as Wally in under {self.cfg.speech_max_words} words. "
            f"Right now your vibe is: {self._current_tone_hint()} — let it color your reply. "
            "Use life_memory.conversation_highlights to stay consistent and call back to past chats when natural. "
            "If this is an action command, acknowledge and stay in character. "
            "If asked about the screen, answer from the attached local screenshot."
        )

        image_b64 = self._capture_screen_base64() if needs_screen and self.cfg.screenshot_reactions_enabled else None
        worker_history = [*self.chat_history[-10:], {"role": "user", "content": prompt}]
        self.chat_history.append({"role": "user", "content": text})
        self.chat_history = self.chat_history[-18:]
        self.set_expression(self._reaction_for_user_text(text))
        self.show_bubble(shorten_for_bubble(text, prefix="You: ", max_len=90), 1600, source="user")
        self._remember_event("user_chat", text=text, data={"command": is_command, "direct": direct_command_executed, "screen_question": needs_screen})

        self.set_expression("thinking")
        self.show_bubble("hmm!", 30000, source="static")
        if self.chat_dialog:
            self.chat_dialog.set_busy(True)
        self.mini_chat.set_busy(True)

        self.worker = ChatWorker(self.cfg, worker_history, image_b64=image_b64)
        self.worker.finished_ok.connect(self._on_answer)
        self.worker.failed.connect(self._on_error)
        self.worker.finished.connect(self._worker_finished)
        self._track_thread(self.worker)
        self.worker.start()

        if is_command and self.cfg.ai_reactions_enabled:
            # Let the controller plan the actual body/movement target as well as the reply.
            QTimer.singleShot(650, lambda msg=text, vis=needs_screen: self.request_ai_reaction("user_command_execute", force=True, use_vision=vis, user_instruction=msg))

    def _on_answer(self, answer: str) -> None:
        self.last_response_text = answer
        self.chat_history.append({"role": "assistant", "content": answer})
        self.chat_history = self.chat_history[-18:]
        # Remember the conversation (and flag anything worth a proactive follow-up).
        store = getattr(self, "memory_store", None)
        if store is not None:
            user_said = str(getattr(self, "_last_chat_user_text", "") or "")
            store.remember_turn(user_said, answer, topic=self._extract_thread(user_said))
        if self.chat_dialog:
            self.chat_dialog.append_pet(answer)
        self.set_expression(self._reaction_for_answer(answer))
        self.eye_focus = "user"
        self.left_arm_pose = "shy"
        self.right_arm_pose = "wave"
        self.antenna_pose = "wiggle"
        self.pause_until = time.time() + 9
        shown_answer = compact_pet_sentence(answer, max_words=self.cfg.speech_max_words, min_words=1)
        if not shown_answer:
            shown_answer = random.choice(["Tiny answer got too big.", "Too many words escaped.", "Retry, but smaller?"])
        self.show_bubble(shorten_for_bubble(shown_answer, max_len=90), 11000, source="ollama")
        self._last_spoken_bubble_at = time.time()
        self._remember_pet_line(shown_answer)
        self._remember_event("pet_chat", text=answer)
        self._speak(answer)
        if self.cfg.ai_reactions_enabled:
            instr = self._pending_user_instruction
            use_vis = bool(self._last_screen_question and self._last_screen_question == instr) or self._message_needs_screen(instr or self._last_screen_question)
            QTimer.singleShot(1400, lambda msg=instr, vis=use_vis: self.request_ai_reaction("after_user_chat_body_language_or_command", use_vision=vis, user_instruction=msg))

    def _friendly_ollama_error(self, error: str) -> str:
        raw = str(error or "").strip()
        lower = raw.lower()
        if "timed out" in lower or "timeout" in lower:
            return "Ollama is slow right now."
        if "model" in lower and ("missing" in lower or "not found" in lower or "pull" in lower):
            return "Ollama model is missing."
        if "connection" in lower or "connect" in lower or "refused" in lower:
            return "Ollama chat endpoint is offline."
        if "json" in lower and "retry" in lower:
            return "Ollama returned messy JSON."
        # Never dump URLs or long exception chains into Wally's bubble.
        first = raw.split(";")[0]
        first = re.sub(r"https?://\S+", "Ollama", first)
        return shorten_for_bubble(first, max_len=72) or "Ollama hiccup."

    def _on_error(self, error: str) -> None:
        self.chat_history.append({"role": "assistant", "content": error})
        if self.chat_dialog:
            self.chat_dialog.append_pet(error)
        self.set_expression("error")
        self.show_bubble(self._friendly_ollama_error(error), 8500, source="error")
        self._remember_event("chat_error", text=error)

    def _track_thread(self, thread: Optional[QThread]) -> None:
        if thread is None:
            return
        try:
            self._active_qthreads.append(thread)
        except Exception:
            pass

    def _forget_finished_threads(self) -> None:
        kept: List[QThread] = []
        for thread in getattr(self, "_active_qthreads", []):
            try:
                if thread is not None and thread.isRunning():
                    kept.append(thread)
            except RuntimeError:
                pass
        self._active_qthreads = kept

    def _worker_finished(self) -> None:
        if self.chat_dialog:
            self.chat_dialog.set_busy(False)
        self.mini_chat.set_busy(False)
        self.worker = None
        self._forget_finished_threads()
        if bool(getattr(self, "_pending_manual_screen_check", False)):
            self._pending_manual_screen_check = False
            QTimer.singleShot(120, lambda: self.request_ai_reaction("manual_screen_check", force=True, use_vision=True))
        QTimer.singleShot(2200, lambda: self.set_expression("happy"))

    def _thread_running(self, thread: Optional[QThread]) -> bool:
        try:
            return bool(thread is not None and thread.isRunning())
        except RuntimeError:
            return False

    def _reaction_worker_finished(self) -> None:
        self.reaction_worker = None
        self._forget_finished_threads()
        if bool(getattr(self, "_pending_manual_screen_check", False)):
            self._pending_manual_screen_check = False
            QTimer.singleShot(120, lambda: self.request_ai_reaction("manual_screen_check", force=True, use_vision=True))

    def _status_worker_finished(self) -> None:
        self.status_worker = None
        self._forget_finished_threads()

    def shutdown_workers(self) -> None:
        """Stop timers and QThreads before Qt destroys widgets during app shutdown."""
        self._shutdown_in_progress = True
        # Flush durable memory first so a clean exit always preserves the latest state.
        try:
            self._save_persistent_memory(force=True)
        except Exception:
            pass
        for timer_name in ("animation_timer", "behavior_timer", "activity_timer", "reminder_timer", "memory_save_timer", "ai_reaction_timer", "ai_heartbeat_timer", "butterfly_timer", "eva_timer", "bubble_timer"):
            timer = getattr(self, timer_name, None)
            try:
                if timer is not None:
                    timer.stop()
            except RuntimeError:
                pass

        # Keep references to any running QThread while trying to stop it.
        # Dropping the Python object while Qt is still running the thread causes
        # "QThread: Destroyed while thread is still running".
        threads: List[QThread] = []
        for attr in ("worker", "reaction_worker", "status_worker", "reminder_parse_worker"):
            thread = getattr(self, attr, None)
            if thread is not None:
                threads.append(thread)
        threads.extend(getattr(self, "_active_qthreads", []))

        unique_threads: List[QThread] = []
        for thread in threads:
            if thread is not None and thread not in unique_threads:
                unique_threads.append(thread)

        still_running: List[QThread] = []
        for thread in unique_threads:
            try:
                try:
                    thread.finished.disconnect()
                except Exception:
                    pass
                if thread.isRunning():
                    thread.requestInterruption()
                    try:
                        thread.quit()
                    except Exception:
                        pass
                    if not thread.wait(1800):
                        thread.terminate()
                        thread.wait(1800)
                if thread.isRunning():
                    still_running.append(thread)
            except RuntimeError:
                pass

        self._active_qthreads = still_running
        if not still_running:
            self.worker = None
            self.reaction_worker = None
            self.status_worker = None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.shutdown_workers()
        try:
            if hasattr(self.debris_overlay, "timer"):
                self.debris_overlay.timer.stop()
            if hasattr(self.attention_overlay, "timer"):
                self.attention_overlay.timer.stop()
            self.mini_chat.hide()
            self.bubble.hide()
            self.parachute_overlay.hide()
            self.reminder_alert.hide()
            self.debris_overlay.hide()
            self.attention_overlay.hide()
        except RuntimeError:
            pass
        if not getattr(self, "_active_qthreads", []):
            self.worker = None
            self.reaction_worker = None
            self.status_worker = None
            self.reminder_parse_worker = None
        super().closeEvent(event)

    def _robot_voice_profile(self, text: str) -> str:
        lower = (text or "").lower()
        expression = str(getattr(self, "expression", "") or "").lower()
        if "reminder" in lower:
            return "reminder"
        if expression == "love" or any(token in lower for token in ("eva", "love", "heart", "miss")):
            return "love"
        if expression in {"excited", "proud"} or "!" in lower:
            return "excited"
        if expression in {"angry", "irritated", "frustrated"}:
            return "angry"
        if expression in {"soft", "sleepy"} or any(token in lower for token in ("gone", "sad", "sorry", "sleep")):
            return "sad"
        if expression in {"curious", "thinking", "watching"} or "?" in lower:
            return "curious"
        return "happy"

    def _sound_asset_path(self, name: str) -> Path:
        filename = name if name.lower().endswith((".wav", ".mp3")) else f"{name}.wav"
        return Path(__file__).resolve().parent / "assets" / "sounds" / filename

    def _sound_profile_candidates(self) -> Dict[str, List[str]]:
        return {
            "happy": ["walle_walle_01.wav", "walle_chirp_03_1.wav"],
            "love": ["walle_chirp_07_1.wav", "walle_walle_01.wav"],
            "excited": ["walle_chirp_07_1.wav", "walle_chirp_04_1.wav", "walle_chirp_03_1.wav"],
            "angry": ["walle_stun_01.wav", "walle_stun_02.wav", "walle_stun_03.wav"],
            "sad": ["walle_sigh_01.wav"],
            "curious": ["walle_chirp_04_1.wav", "walle_chirp_05_1.wav", "walle_chirp_03_1.wav"],
            "reminder": ["walle_chirp_05_1.wav", "walle_stun_02.wav", "walle_stun_01.wav", "walle_stun_03.wav"],
            "dizzy": ["walle_stun_03.wav", "walle_stun_01.wav", "walle_stun_02.wav"],
            "sleepy": ["walle_sigh_01.wav"],
            "alert": ["walle_stun_02.wav", "walle_stun_01.wav", "walle_stun_03.wav", "walle_chirp_05_1.wav"],
            "giggle": ["walle_chirp_03_1.wav", "walle_chirp_07_1.wav"],
            "play": ["walle_walle_01.wav", "walle_chirp_07_1.wav"],
            "eva_flyby": ["walle_eve_01.wav"],
        }

    def _randomized_volume(self, base_volume: float = 1.0, variation: float = 0.10) -> float:
        low = max(0.0, 1.0 - max(0.0, variation))
        high = 1.0 + max(0.0, variation)
        return max(0.0, min(1.0, base_volume * random.uniform(low, high)))

    def _sound_duration_seconds(self, name: str) -> float:
        cache = dict(getattr(self, "_sound_duration_cache", {}))
        if name in cache:
            return float(cache[name])
        path = self._sound_asset_path(name)
        duration = 1.8
        try:
            if path.suffix.lower() == ".wav":
                with wave.open(str(path), "rb") as reader:
                    rate = max(1, int(reader.getframerate()))
                    frames = int(reader.getnframes())
                    duration = max(0.2, frames / float(rate))
            else:
                duration = {
                    "wall-e2.MP3": 1.9,
                    "whoa.MP3": 1.1,
                    "too much garbage.MP3": 2.6,
                }.get(path.name, 1.8)
        except Exception:
            duration = 1.8
        cache[name] = duration
        self._sound_duration_cache = cache
        return duration

    def _resolve_cooldown_seconds(self, cooldown_seconds: float | Tuple[float, float]) -> float:
        if isinstance(cooldown_seconds, tuple):
            low, high = cooldown_seconds
            low = max(0.0, float(low))
            high = max(low, float(high))
            return random.uniform(low, high)
        return max(0.0, float(cooldown_seconds))

    def _sound_pool_available(self, pool_key: str) -> bool:
        return time.time() >= float(dict(getattr(self, "_sound_pool_next_allowed_at", {})).get(pool_key, 0.0))

    def _mark_sound_pool_played(self, pool_key: str, cooldown_seconds: float | Tuple[float, float]) -> None:
        ready_state = dict(getattr(self, "_sound_pool_next_allowed_at", {}))
        ready_state[pool_key] = time.time() + self._resolve_cooldown_seconds(cooldown_seconds)
        self._sound_pool_next_allowed_at = ready_state

    def _sound_manager_available(self) -> bool:
        return time.time() >= float(getattr(self, "_sound_busy_until", 0.0))

    def _claim_sound_play(
        self,
        name: str,
        cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0),
        avoid_recent: bool = True,
    ) -> bool:
        path = self._sound_asset_path(name)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if not self._can_play_sound(name, cooldown_seconds=cooldown_seconds, avoid_recent=avoid_recent):
            return False
        if not self._sound_manager_available():
            return False
        self._mark_sound_played(name, cooldown_seconds=cooldown_seconds)
        self._sound_busy_name = name
        self._sound_busy_until = time.time() + self._sound_duration_seconds(name) + 0.08
        return True

    def _can_play_sound(self, name: str, cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0), avoid_recent: bool = True) -> bool:
        now = time.time()
        recent_name = str(getattr(self, "_last_sound_played_name", ""))
        next_allowed = dict(getattr(self, "_sound_next_allowed_at", {}))
        if avoid_recent and name == recent_name:
            return False
        if now < float(next_allowed.get(name, 0.0)):
            return False
        return True

    def _mark_sound_played(self, name: str, cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0)) -> None:
        now = time.time()
        sound_state = dict(getattr(self, "_sound_last_played_at", {}))
        sound_state[name] = now
        self._sound_last_played_at = sound_state
        ready_state = dict(getattr(self, "_sound_next_allowed_at", {}))
        ready_state[name] = now + self._resolve_cooldown_seconds(cooldown_seconds)
        self._sound_next_allowed_at = ready_state
        self._last_sound_played_name = name

    def _choose_sound_from_candidates(
        self,
        candidates: List[str],
        cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0),
        avoid_recent: bool = True,
        pool_key: Optional[str] = None,
    ) -> Optional[str]:
        if not candidates:
            return None
        if pool_key and not self._sound_pool_available(pool_key):
            return None
        now = time.time()
        recent_name = str(getattr(self, "_last_sound_played_name", ""))
        last_played = dict(getattr(self, "_sound_last_played_at", {}))
        next_allowed = dict(getattr(self, "_sound_next_allowed_at", {}))
        eligible = [
            name
            for name in candidates
            if (not avoid_recent or name != recent_name) and now >= float(next_allowed.get(name, 0.0))
        ]
        if not eligible:
            return None
        if pool_key:
            positions = dict(getattr(self, "_sound_pool_positions", {}))
            start = int(positions.get(pool_key, -1)) + 1
            ordered = [candidates[(start + offset) % len(candidates)] for offset in range(len(candidates))]
            for name in ordered:
                if name in eligible:
                    positions[pool_key] = candidates.index(name)
                    self._sound_pool_positions = positions
                    return name
        eligible.sort(key=lambda name: float(last_played.get(name, 0.0)))
        oldest_at = float(last_played.get(eligible[0], 0.0))
        oldest = [name for name in eligible if float(last_played.get(name, 0.0)) == oldest_at]
        return random.choice(oldest)

    def _choose_sound_for_profile(self, profile: str) -> Optional[str]:
        sound_sets = self._sound_profile_candidates()
        candidates = list(sound_sets.get(profile, sound_sets["happy"]))
        shared_pool_key = {
            "angry": "stun_family",
            "alert": "stun_family",
            "dizzy": "stun_family",
            "reminder": "stun_family",
        }.get(profile, profile)
        return self._choose_sound_from_candidates(candidates, cooldown_seconds=(15.0, 45.0), avoid_recent=True, pool_key=shared_pool_key)

    def _play_randomized_wav(self, path: Path) -> None:
        import winsound

        scale = random.uniform(0.90, 1.10)
        temp_path = Path(tempfile.gettempdir()) / f"robo_rover_pet_{time.time_ns()}_{path.name}"
        try:
            with wave.open(str(path), "rb") as reader:
                params = reader.getparams()
                frames = reader.readframes(reader.getnframes())

            sampwidth = params.sampwidth
            if sampwidth == 1:
                adjusted = bytearray()
                for sample in frames:
                    centered = sample - 128
                    scaled = max(-128, min(127, int(centered * scale)))
                    adjusted.append(scaled + 128)
                out = bytes(adjusted)
            elif sampwidth == 2:
                count = len(frames) // 2
                samples = struct.unpack("<" + "h" * count, frames)
                scaled = [max(-32768, min(32767, int(sample * scale))) for sample in samples]
                out = struct.pack("<" + "h" * count, *scaled)
            elif sampwidth == 4:
                count = len(frames) // 4
                samples = struct.unpack("<" + "i" * count, frames)
                scaled = [max(-2147483648, min(2147483647, int(sample * scale))) for sample in samples]
                out = struct.pack("<" + "i" * count, *scaled)
            else:
                winsound.PlaySound(str(path), winsound.SND_FILENAME)
                return

            with wave.open(str(temp_path), "wb") as writer:
                writer.setparams(params)
                writer.writeframes(out)

            winsound.PlaySound(str(temp_path), winsound.SND_FILENAME)
        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def _sound_priority(self, name: str) -> int:
        token = name.strip().lower()
        if token == "walle_eve_01.wav":
            return 5
        if token in {"too much garbage.mp3", "whoa.mp3"}:
            return 4
        if "stun" in token or token in {"walle_sigh_01.wav", "walle_walle_01.wav"}:
            return 3
        if "eve" in token or "chirp" in token or token in {"walle_vocal_basic_01.wav", "wall-e2.mp3"}:
            return 1
        return 2

    def _sound_is_tiny(self, name: str) -> bool:
        token = name.strip().lower()
        return bool("chirp" in token or "eve" in token or token in {"walle_vocal_basic_01.wav", "wall-e2.mp3"})

    def _stop_active_media_sounds(self) -> None:
        refs = list(getattr(self, "_media_sound_refs", []))
        self._media_sound_refs = []
        for player, audio in refs:
            try:
                player.stop()
            except Exception:
                pass
            try:
                player.deleteLater()
            except Exception:
                pass
            try:
                audio.deleteLater()
            except Exception:
                pass

    def _stop_active_audio(self) -> None:
        self._stop_active_media_sounds()
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def _activate_audio_lane(self, name: str, duration_seconds: float, priority: int, interruptible: bool) -> None:
        self._audio_lane_name = name
        self._audio_lane_priority = priority
        self._audio_lane_busy_until = time.time() + max(0.18, float(duration_seconds))
        self._audio_lane_interruptible = interruptible
        self.audio_lane_timer.stop()
        self.audio_lane_timer.start(max(180, int(max(0.18, float(duration_seconds)) * 1000)))

    def _release_audio_lane(self) -> None:
        remaining = float(getattr(self, "_audio_lane_busy_until", 0.0)) - time.time()
        if remaining > 0.05:
            self.audio_lane_timer.stop()
            self.audio_lane_timer.start(max(120, int(remaining * 1000)))
            return
        pending = getattr(self, "_audio_lane_pending", None)
        self._audio_lane_name = ""
        self._audio_lane_priority = 0
        self._audio_lane_busy_until = 0.0
        self._audio_lane_interruptible = False
        self._audio_lane_pending = None
        self._audio_lane_pending_priority = -1
        if callable(pending):
            QTimer.singleShot(0, pending)

    def _reserve_audio_lane(
        self,
        name: str,
        duration_seconds: float,
        *,
        priority: Optional[int] = None,
        interruptible: bool = False,
        queue_if_blocked: bool = False,
        replay=None,
    ) -> bool:
        now = time.time()
        current_name = str(getattr(self, "_audio_lane_name", "") or "")
        current_priority = int(getattr(self, "_audio_lane_priority", 0))
        current_until = float(getattr(self, "_audio_lane_busy_until", 0.0))
        current_interruptible = bool(getattr(self, "_audio_lane_interruptible", False))
        force_eva_priority = name.strip().lower() == "walle_eve_01.wav"
        eva_visible = bool(getattr(self.debris_overlay, "eva_visible", False))
        if eva_visible and not force_eva_priority:
            return False
        desired_priority = self._sound_priority(name) if priority is None else int(priority)
        if current_name and now < current_until:
            if force_eva_priority:
                self._stop_active_audio()
            elif desired_priority > current_priority and current_interruptible:
                self._stop_active_audio()
            else:
                if queue_if_blocked and callable(replay):
                    pending = getattr(self, "_audio_lane_pending", None)
                    pending_priority = int(getattr(self, "_audio_lane_pending_priority", -1))
                    if pending is None or desired_priority >= pending_priority:
                        self._audio_lane_pending = replay
                        self._audio_lane_pending_priority = desired_priority
                return False
        self._audio_lane_pending_priority = -1
        self._activate_audio_lane(name, duration_seconds, desired_priority, interruptible)
        return True

    def _play_named_sound(self, name: str, cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0), avoid_recent: bool = True, skip_if_blocked: bool = False) -> bool:
        path = self._sound_asset_path(name)
        if not path.exists():
            raise FileNotFoundError(str(path))
        is_eva_priority = name.strip().lower() == "walle_eve_01.wav"
        if is_eva_priority:
            self._stop_active_audio()
        if not self._can_play_sound(name, cooldown_seconds=cooldown_seconds, avoid_recent=avoid_recent):
            return False
        duration_seconds = self._sound_duration_seconds(name) + 0.08
        if not self._reserve_audio_lane(
            name,
            duration_seconds,
            priority=self._sound_priority(name),
            interruptible=self._sound_is_tiny(name) and not is_eva_priority,
            queue_if_blocked=self._sound_is_tiny(name) and not skip_if_blocked,
            replay=lambda n=name, c=cooldown_seconds, a=avoid_recent, s=skip_if_blocked: self._play_named_sound(n, cooldown_seconds=c, avoid_recent=a, skip_if_blocked=s),
        ):
            return False
        if not self._sound_manager_available():
            return False
        self._mark_sound_played(name, cooldown_seconds=cooldown_seconds)
        self._sound_busy_name = name
        self._sound_busy_until = time.time() + duration_seconds
        if self._sound_is_tiny(name):
            base_volume = 0.60 if is_eva_priority else 0.06
            self._play_quiet_media_sound_reserved(name, volume=base_volume, variation=0.10)
            return True
        self._play_randomized_wav(path)
        return True

    def _release_media_sound_ref(self, player: QMediaPlayer, audio: QAudioOutput) -> None:
        refs = [
            pair
            for pair in list(getattr(self, "_media_sound_refs", []))
            if pair[0] is not player and pair[1] is not audio
        ]
        self._media_sound_refs = refs
        try:
            player.stop()
        except Exception:
            pass
        player.deleteLater()
        audio.deleteLater()

    def _play_quiet_media_sound_reserved(self, name: str, volume: float = 0.10, variation: float = 0.10) -> None:
        path = self._sound_asset_path(name)
        if not path.exists():
            raise FileNotFoundError(str(path))

        audio = QAudioOutput(self)
        audio.setVolume(self._randomized_volume(volume, variation))
        player = QMediaPlayer(self)
        player.setAudioOutput(audio)
        player.setSource(QUrl.fromLocalFile(str(path)))
        refs = list(getattr(self, "_media_sound_refs", []))
        refs.append((player, audio))
        self._media_sound_refs = refs
        player.play()
        QTimer.singleShot(7000, lambda p=player, a=audio: self._release_media_sound_ref(p, a))

    def _play_quiet_media_sound(self, name: str, volume: float = 0.10, cooldown_seconds: float | Tuple[float, float] = (15.0, 45.0), variation: float = 0.10) -> None:
        path = self._sound_asset_path(name)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if not self._can_play_sound(name, cooldown_seconds=cooldown_seconds, avoid_recent=True):
            return
        duration_seconds = self._sound_duration_seconds(name) + 0.08
        if not self._reserve_audio_lane(
            name,
            duration_seconds,
            priority=self._sound_priority(name),
            interruptible=True,
            queue_if_blocked=self._sound_is_tiny(name),
            replay=lambda n=name, v=volume, c=cooldown_seconds, r=variation: self._play_quiet_media_sound(n, volume=v, cooldown_seconds=c, variation=r),
        ):
            return
        if not self._sound_manager_available():
            return
        self._mark_sound_played(name, cooldown_seconds=cooldown_seconds)
        self._sound_busy_name = name
        self._sound_busy_until = time.time() + duration_seconds
        self._play_quiet_media_sound_reserved(name, volume=volume, variation=variation)

    def _choose_wall_e_voice_variant(self) -> Optional[str]:
        return self._choose_sound_from_candidates(
            ["walle_vocal_basic_01.wav", "wall-e2.MP3"],
            cooldown_seconds=(6.0, 14.0),
            avoid_recent=True,
            pool_key="soft_voice",
        )

    def _play_soft_voice_variant_sound_now(self, name: str, volume: float) -> None:
        try:
            self._play_quiet_media_sound_reserved(name, volume=volume, variation=0.0)
        except Exception:
            return

    def _play_soft_voice_variant_sound(self, name: str) -> None:
        cooldown = (6.0, 14.0)
        if not self._sound_pool_available("soft_voice"):
            return
        if not self._can_play_sound(name, cooldown_seconds=cooldown, avoid_recent=True):
            return
        duration_seconds = self._sound_duration_seconds(name) + 0.08
        if not self._reserve_audio_lane(
            name,
            duration_seconds,
            priority=1,
            interruptible=True,
            queue_if_blocked=True,
            replay=lambda n=name: self._play_soft_voice_variant_sound(n),
        ):
            return
        if not self._sound_manager_available():
            return
        self._mark_sound_played(name, cooldown_seconds=cooldown)
        self._sound_busy_name = name
        self._sound_busy_until = time.time() + duration_seconds
        self._mark_sound_pool_played("soft_voice", cooldown)
        self.play_soft_voice_requested.emit(name, random.uniform(0.025, 0.04))

    def _play_tantrum_garbage_sound(self) -> None:
        try:
            self._play_quiet_media_sound("too much garbage.MP3", volume=0.10, cooldown_seconds=(15.0, 45.0))
        except Exception:
            return

    def _play_whoa_sound(self) -> None:
        try:
            self._play_quiet_media_sound("whoa.MP3", volume=0.10, cooldown_seconds=(15.0, 45.0))
        except Exception:
            return

    def _play_robot_voice(self, text: str) -> None:
        profile = self._robot_voice_profile(text)
        if profile in {"happy", "play"}:
            choice = self._choose_wall_e_voice_variant()
            if choice is not None:
                self._play_soft_voice_variant_sound(choice)
                return
        choice = self._choose_sound_for_profile(profile)
        if choice is not None:
            self._play_named_sound(choice)

    def _emoji_sound_profile(self, effect: str) -> Optional[str]:
        token = (effect or "").strip().lower()
        if token in {"none", ""}:
            return None
        if token in {"heart", "💛", "🫡", "love"}:
            return "love"
        if token in {"sparkle", "✨", "🌟", "butterfly", "🦋", "music", "🎵", "🎶"}:
            return "excited"
        if token in {"dizzy", "💫", "😵‍💫"}:
            return "dizzy"
        if token in {"sleep", "😴", "💤"}:
            return "sleepy"
        if token in {"question", "?", "👀", "🔍"}:
            return "curious"
        if token in {"exclamation", "!", "😳", "⚡"}:
            return "alert"
        if token in {"😂", "🤭", "🙃"}:
            return "giggle"
        if token in {"🥹", "💧"}:
            return "sad"
        if token in {"🏀", "ball", "basketball"}:
            return "play"
        return "happy"

    def _play_robot_emoji_sound(self, effect: str) -> None:
        profile = self._emoji_sound_profile(effect)
        if profile is None:
            return
        if profile in {"happy", "play"}:
            choice = self._choose_wall_e_voice_variant()
            if choice is not None:
                self._play_soft_voice_variant_sound(choice)
            return
        choice = self._choose_sound_for_profile(profile)
        if choice is not None:
            self._play_named_sound(choice)

    def _maybe_play_emoji_sound(self, effect: str) -> None:
        if not self.store.config().tts_enabled:
            return
        if not sys.platform.startswith("win"):
            return
        profile = self._emoji_sound_profile(effect)
        if profile is None:
            return

        now = time.time()
        last_effect = getattr(self, "_last_emoji_sound_effect", "")
        last_at = float(getattr(self, "_last_emoji_sound_at", 0.0))
        cooldown = 1.1 if profile in {"giggle", "alert", "excited"} else 1.7
        if effect == last_effect and now - last_at < cooldown:
            return
        if now - last_at < 0.45:
            return

        self._last_emoji_sound_effect = effect
        self._last_emoji_sound_at = now

        def run_sound() -> None:
            try:
                self._play_robot_emoji_sound(effect)
            except Exception:
                return

        threading.Thread(target=run_sound, daemon=True).start()

    def _play_eva_flyby_sound(self, token: int) -> None:
        if not self.store.config().tts_enabled:
            return
        if not sys.platform.startswith("win"):
            return
        if token != int(getattr(self, "_eva_sound_token", 0)):
            return
        if not getattr(self.debris_overlay, "eva_visible", False):
            return

        try:
            played = self._play_named_sound(
                "walle_eve_01.wav",
                cooldown_seconds=2.0,
                avoid_recent=False,
                skip_if_blocked=True,
            )
        except Exception:
            played = False

        if not played:
            if token == int(getattr(self, "_eva_sound_token", 0)) and getattr(self.debris_overlay, "eva_visible", False):
                QTimer.singleShot(650, lambda active_token=token: self._play_eva_flyby_sound(active_token))
            return

        if token == int(getattr(self, "_eva_sound_token", 0)) and getattr(self.debris_overlay, "eva_visible", False):
            QTimer.singleShot(random.randint(2000, 3000), lambda active_token=token: self._play_eva_flyby_sound(active_token))

    def _speak(self, text: str) -> None:
        if not self.store.config().tts_enabled:
            return
        clean = re.sub(r"[`*_#>\[\]()]", "", text)
        clean = re.sub(r"https?://\S+", "link", clean)
        clean = clean[:700]

        def run_tts() -> None:
            if sys.platform.startswith("win"):
                try:
                    self._play_robot_voice(clean)
                    return
                except Exception:
                    pass
            try:
                import pyttsx3  # type: ignore

                engine = pyttsx3.init()
                engine.setProperty("rate", 195)
                engine.say(clean)
                engine.runAndWait()
            except Exception:
                # Avoid interrupting the pet for unavailable OS speech engines.
                return

        threading.Thread(target=run_tts, daemon=True).start()

    def _normalize_pet_line(self, line: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(line).lower()).strip()

    def _is_repetitive_pet_line(self, line: str) -> bool:
        # v8.16 was too strict and hid many good short lines.
        # Only suppress exact recent repeats; let similar-but-fresh pet speech appear.
        norm = self._normalize_pet_line(line)
        if len(norm) < 5:
            return False
        return norm in self.recent_pet_line_norms[-5:]

    def _remember_pet_line(self, line: str) -> None:
        norm = self._normalize_pet_line(line)
        if not norm or norm in {"", "you", "oops"}:
            return
        self.recent_pet_lines.append(str(line)[:160])
        self.recent_pet_line_norms.append(norm)
        self.recent_pet_lines = self.recent_pet_lines[-18:]
        self.recent_pet_line_norms = self.recent_pet_line_norms[-18:]
        self._lines_spoken_session += 1

    def _save_persistent_memory(self, force: bool = False) -> None:
        store = getattr(self, "memory_store", None)
        if store is None:
            return
        delta = self._lines_spoken_session
        self._lines_spoken_session = 0
        store.save(
            action_memory=self.action_memory,
            recent_pet_lines=self.recent_pet_lines,
            moods=self.moods,
            lines_spoken_delta=delta,
            needs=self.needs,
            force=force,
        )

    def _typed_context_interesting(self, typed: str, keys: int) -> bool:
        typed = (typed or "").strip()
        if not typed:
            return False
        if typed == self.last_typing_reaction_excerpt and len(typed) < 90:
            return False
        lower = typed.lower()
        interest_words = {
            "error", "failed", "fail", "crash", "bug", "fix", "test", "run", "build",
            "python", "code", "api", "yaml", "ollama", "ai", "llm", "screen", "why",
            "how", "what", "wow", "nice", "awesome", "love", "hate", "stress", "tired",
            "deadline", "issue", "problem", "warning", "exception", "timeout", "design",
            "idea", "resume", "wix", "deploy", "github", "java", "json"
        }
        if "?" in typed or "!" in typed:
            return len(typed) >= 8
        if any(word in lower for word in interest_words):
            return len(typed) >= 10
        # Occasionally react to a long burst, but not to every typing session.
        return keys >= 34 and len(typed) >= 45 and random.random() < 0.18

    def _greet_on_launch(self) -> None:
        ctx = self._banter_context()
        avoid = self.recent_pet_lines[-10:]
        rhythm = getattr(self, "_day_rhythm", {}) or {}
        emoji = random.choice(["✨", "🤩", "🥰", "🎉", "👋"])
        # Daily-companion flavor: missed-you after a gap, streak pride, or new-day hello.
        if int(rhythm.get("days_since_last", 0) or 0) >= 2:
            line = banter.pick("care_missed", ctx, avoid=avoid)
            emoji = "🥹"
        elif int(rhythm.get("streak", 0) or 0) >= 3 and random.random() < 0.6:
            line = banter.streak_line(int(rhythm["streak"]), avoid=avoid)
            emoji = "🔥"
        elif rhythm.get("new_day") and random.random() < 0.5:
            line = banter.pick("daily_hello", ctx, avoid=avoid)
            emoji = "☀️" if ctx.get("daypart") == "morning" else "👋"
        else:
            line = banter.greeting(ctx, avoid=avoid)
        if line:
            self.show_bubble(line, 6500, source="static")
            self.emoji_effect = emoji
            self.emoji_until = time.time() + 6.0
            self._last_spoken_bubble_at = time.time()
            self._remember_pet_line(line)
            self.set_expression("excited")

    # Situations and moods each suggest an emoji, so even instant (non-LLM) lines get
    # an expressive floating bubble instead of staying emoji-less.
    _SITUATION_EMOJI = {
        "eva_arrive": "💛", "eva_chase": "💛", "eva_left": "💔",
        "ball_kick": "🏀", "ball_super": "⚡", "butterfly_arrive": "🦋",
        "butterfly_chase": "🦋", "butterfly_caught": "🌟",
        "picked_up": "😳", "held": "🥰", "dropped": "💫", "poke": "👀",
        "double_poke": "🤭", "pet": "🥰", "rapid_typing": "⚡", "window_hopping": "👀",
        "idle": "😴", "overwhelmed": "😩", "screen": "👀", "messy": "🧹",
        "bored": "🥱", "playful": "😎", "clean_pride": "🏆", "late_night": "🌙", "morning": "☀️",
        "care_stressed": "🥺", "care_stuck": "💡", "care_late": "🌙", "care_missed": "🥹",
        "care_restless": "🎮", "care_celebrate": "🎉", "daily_hello": "☀️",
    }
    _MOOD_EMOJI = {
        "excited": "🤩", "proud": "🏆", "irritated": "😤", "frustrated": "😩",
        "bored": "🥱", "cozy": "🥰", "curious": "🤔", "playful": "😎",
        "naughty": "😈", "anxious": "😬",
    }

    def _set_banter_emoji(self, situation: str, mood: Optional[str], seconds: float = 6.0) -> None:
        emoji = self._SITUATION_EMOJI.get(situation) or (self._MOOD_EMOJI.get(mood or "") if mood else "") or "✨"
        self.emoji_effect = emoji
        self.emoji_until = time.time() + seconds

    _SENSITIVE_WINDOW_HINTS = (
        "password", "passwd", "log in", "login", "sign in", "signin", "bank", "lastpass",
        "1password", "bitwarden", "keepass", "authenticator", "otp", "credit card",
        "payment", "checkout", "paypal", "ssn", "private browsing", "incognito",
    )

    def _looks_sensitive_typing(self, window: str, text: str) -> bool:
        """Best-effort guard: don't relay typing from password/login/banking contexts."""
        w = (window or "").lower()
        if any(hint in w for hint in self._SENSITIVE_WINDOW_HINTS):
            return True
        t = (text or "").strip()
        # Password-shaped token: long, no spaces, mixed character classes.
        if t and " " not in t and len(t) >= 8 and re.search(r"[A-Z]", t) and re.search(r"\d", t) and re.search(r"[^A-Za-z0-9]", t):
            return True
        return False

    def _typed_text_payload(self, window: str, counts: Dict[str, object]) -> Optional[Dict[str, object]]:
        """Framed snippet of what the user is actually typing, so Wally can react to
        the CONTENT — witty, sarcastic, or a warm acknowledgement. Privacy-guarded."""
        if not self.cfg.screen_awareness_enabled:
            return None
        # Only the FRESH excerpt — never the persistent one — so he doesn't keep
        # bringing up something typed minutes ago. Also require recent activity.
        try:
            idle = float(counts.get("idle_seconds", 999))
        except (TypeError, ValueError):
            idle = 999.0
        if idle > 12.0:
            return None
        text = str(counts.get("typed_excerpt") or "").strip()
        if len(text) < 6 or self._looks_sensitive_typing(window, text):
            return None
        return {
            "text": text[-200:],
            "in_window": window[:70],
            "is_speech_to_pet": False,
            "how_to_react": "This is what the user is typing right now. If it's interesting, react to the CONTENT with a witty, sarcastic, or warm one-liner; otherwise a tiny acknowledgement or silence. Never repeat their words back verbatim.",
        }

    def _instant_event_quip(self, situation: str, min_gap: float = 2.2, duration_ms: int = 6500) -> None:
        """Fire an instant in-character callout for a big event (EVA, ball, butterfly,
        being poked/grabbed). The LLM follow-up, if any, upgrades this bubble."""
        now = time.time()
        if now - float(getattr(self, "_last_event_quip_at", 0.0)) < min_gap:
            return
        mood = self._dominant_mood()
        line = banter.pick(situation, self._banter_context(), avoid=self.recent_pet_lines[-10:], mood=mood)
        if line:
            self.show_bubble(line, duration_ms, source="static")
            self._set_banter_emoji(situation, mood)
            self._remember_pet_line(line)
            self._last_event_quip_at = now

    def _maybe_record_gag(self, line: str) -> None:
        """Occasionally remember one of Wally's own good lines as a future running gag."""
        store = getattr(self, "memory_store", None)
        if store is None or not line:
            return
        words = line.split()
        if 3 <= len(words) <= 12 and random.random() < 0.22:
            store.add_gag(line)

    def _wellbeing_signals(self) -> Dict[str, object]:
        monitor = self.activity_monitor
        return {
            "work_pressure": round(self.work_pressure, 1),
            "key_score": round(getattr(monitor, "recent_key_score", 0.0), 1),
            "idle_seconds": round(max(0.0, time.time() - getattr(monitor, "last_input_time", time.time())), 1),
            "window_changes": int(getattr(self, "_event_reaction_counters", {}).get("window", 0)),
            "daypart": self._local_time_context().get("daypart", ""),
            "session_minutes": round((time.time() - float(getattr(self, "_session_started_wall", time.time()))) / 60.0, 1),
        }

    def _wellbeing_tick(self) -> None:
        """Attune to how the user is doing and, occasionally, respond like a friend.

        This is the companion layer: not reacting to an event, but to *the person*.
        Throttled and probabilistic so it feels caring, never naggy."""
        now = time.time()
        if now - self._last_wellbeing_tick_at < 30.0:
            return
        self._last_wellbeing_tick_at = now
        if getattr(self, "_cowatch_active", False):
            return  # stay quiet during co-watch
        if self.is_dragging or self.current_action in {"clean", "go_bin", "chase_eva", "chase_butterfly", "kick_ball"}:
            return

        state = companion.read_state(self._wellbeing_signals())
        self._last_wellbeing_state = state
        resp = companion.response_for(state)
        mood = resp.get("mood") or {}
        if isinstance(mood, dict) and mood:
            self._nudge_mood(**{k: float(v) for k, v in mood.items()})

        situation = resp.get("situation")
        if not situation:
            return
        # Don't talk over a fresh line, and space caring check-ins generously apart.
        if self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0)):
            return
        if now - self._last_wellbeing_care_at < 150.0:
            return
        if random.random() > float(resp.get("speak", 0.0)):
            return
        line = banter.pick(str(situation), self._banter_context(), avoid=self.recent_pet_lines[-10:])
        if line:
            self.show_bubble(line, 7200, source="static")
            self._set_banter_emoji(str(situation), self._dominant_mood())
            self._remember_pet_line(line)
            self._last_wellbeing_care_at = now
            self._last_spoken_bubble_at = now
            expr = resp.get("expression")
            if expr:
                self.set_expression(str(expr))

    _NEED_REQUEST = {"affection": "want_affection", "play": "want_play", "energy": "want_rest"}
    _NEED_THANKS = {"affection": "thanks_affection", "play": "thanks_play", "energy": "thanks_rest"}
    _NEED_EMOJI = {"affection": "🥺", "play": "🎮", "energy": "🔋"}

    def _needs_tick(self) -> None:
        """Decay Wally's needs over time; when one runs low, he asks to be cared for.

        This is the reciprocity loop: petting, playing, and letting him rest refill
        the needs, so the bond goes both ways instead of being one-directional."""
        now = time.time()
        dt = min(120.0, max(0.0, now - self._last_needs_tick_at))
        self._last_needs_tick_at = now
        if dt <= 0:
            return
        per_min = dt / 60.0
        moving = self.current_action in {"clean", "go_bin", "chase_eva", "chase_butterfly", "kick_ball", "move_to", "roam"}
        self.needs["affection"] = max(0.0, self.needs["affection"] - 1.3 * per_min)
        self.needs["play"] = max(0.0, self.needs["play"] - 1.7 * per_min)
        # Energy drains with activity, slowly refills while idle/napping.
        if self.current_action in {"nap", "chill", "pause"} and not moving:
            self.needs["energy"] = min(100.0, self.needs["energy"] + 2.2 * per_min)
        else:
            self.needs["energy"] = max(0.0, self.needs["energy"] - (2.4 if moving else 1.1) * per_min)

        # Let mood reflect chronic unmet needs.
        if self.needs["affection"] < 30:
            self._nudge_mood(cozy=-0.5 * per_min, anxious=0.4 * per_min)
        if self.needs["play"] < 30:
            self._nudge_mood(bored=1.2 * per_min, playful=0.6 * per_min)
        if self.needs["energy"] < 30:
            self._nudge_mood(bored=0.5 * per_min)

        # Occasionally voice the most-neglected need (gently, well-spaced).
        if self.is_dragging or getattr(self, "_cowatch_active", False) or now - self._last_need_request_at < 110.0:
            return
        if self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0)):
            return
        low_key, low_val = min(self.needs.items(), key=lambda kv: kv[1])
        if low_val >= 28 or random.random() < 0.4:
            return
        situation = self._NEED_REQUEST.get(low_key)
        if not situation:
            return
        line = banter.pick(situation, self._banter_context(), avoid=self.recent_pet_lines[-10:])
        if line:
            self.show_bubble(line, 6800, source="static")
            self.emoji_effect = self._NEED_EMOJI.get(low_key, "🥺")
            self.emoji_until = now + 6.0
            self.set_expression("soft" if low_key == "affection" else ("sleepy" if low_key == "energy" else "curious"))
            self._remember_pet_line(line)
            self._last_need_request_at = now

    def _proactive_followup_tick(self) -> None:
        """Occasionally circle back to something the user mentioned earlier — a real
        check-in like a friend ('how'd that auth bug go?'). The LLM phrases it from the
        stored topic; a gentle template covers the offline case."""
        store = getattr(self, "memory_store", None)
        if store is None:
            return
        if getattr(self, "_cowatch_active", False):
            return  # don't interrupt the show with a check-in
        now = time.time()
        if now - float(getattr(self, "_last_followup_at", 0.0)) < 480.0:
            return
        if self.is_dragging or self.current_action in {"clean", "go_bin", "chase_eva", "chase_butterfly", "kick_ball", "move_to"}:
            return
        if self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0)):
            return
        threads = store.open_threads(min_age_seconds=150.0, max_n=3)
        if not threads or random.random() < 0.4:
            return
        thread = random.choice(threads)
        topic = str(thread.get("topic", "")).strip()
        if not topic:
            return
        store.mark_thread_followed(topic)
        self._last_followup_at = now
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            self._pending_activity_note = {
                "kind": "proactive_followup",
                "topic": topic,
                "hint": "Earlier the user mentioned this. Ask a warm, natural, specific check-in about how it went. Keep it short and caring, like a friend remembering.",
            }
            self.request_ai_reaction("proactive_followup", use_vision=False)
        else:
            short_topic = " ".join(topic.split()[:6])
            line = f"How's that going — {short_topic}?"
            self.show_bubble(line, 7600, source="static")
            self.emoji_effect = "🤔"
            self.emoji_until = now + 6.0
            self.set_expression("curious")
            self._remember_pet_line(line)
            self._last_spoken_bubble_at = now

    def _satisfy_need(self, name: str, amount: float, react: bool = True) -> None:
        """The user did something caring; refill a need and show gratitude."""
        if name not in self.needs:
            return
        before = self.needs[name]
        self.needs[name] = min(100.0, before + amount)
        gained = self.needs[name] - before
        if name == "affection":
            self._nudge_mood(cozy=8, proud=4, encouraging=4, anxious=-6)
        elif name == "play":
            self._nudge_mood(playful=10, excited=8, bored=-12)
        elif name == "energy":
            self._nudge_mood(cozy=6, bored=-4)
        # Visible gratitude when a low need is meaningfully refilled.
        if react and before < 55 and gained >= 6:
            now = time.time()
            if now - float(getattr(self, "_last_event_quip_at", 0.0)) >= 2.0:
                line = banter.pick(self._NEED_THANKS.get(name, "thanks_affection"), self._banter_context(), avoid=self.recent_pet_lines[-10:])
                if line:
                    self.show_bubble(line, 6200, source="static")
                    self.emoji_effect = "🥰" if name == "affection" else self._NEED_EMOJI.get(name, "✨")
                    self.emoji_until = now + 5.0
                    self.set_expression("love" if name == "affection" else "happy")
                    self._remember_pet_line(line)
                    self._last_event_quip_at = now

    _TONE_BY_MOOD = {
        "playful": "playful and witty", "naughty": "mischievous and teasing",
        "excited": "hyper and enthusiastic", "proud": "smug and proud",
        "bored": "bored and dryly sarcastic", "irritated": "grumpy and sarcastic",
        "frustrated": "frazzled but still trying", "cozy": "warm and soft",
        "curious": "curious and chatty", "anxious": "a little anxious but caring",
    }

    def _current_tone_hint(self) -> str:
        """A short directive describing Wally's CURRENT vibe, so chat replies match
        his mood engine (witty when playful, terse when tired, sarcastic when grumpy)."""
        if self.needs.get("energy", 100) < 28:
            return "low-energy: tired, sleepy, a little terse"
        mood = self._dominant_mood(min_spike=6.0)
        return self._TONE_BY_MOOD.get(mood or "", "warm and witty")

    _THREAD_TRIGGERS = (
        "deadline", "due ", "tomorrow", "bug", "fix", "error", "crash", "meeting", "interview",
        "exam", "test", "presentation", "demo", "launch", "ship", "release", "deploy", "sick",
        "tired", "stressed", "worried", "nervous", "excited", "trying to", "working on", "project",
        "assignment", "homework", "doctor", "appointment", "hoping", "scared", "anxious",
    )

    def _extract_thread(self, user_text: str) -> str:
        """If the user mentioned something worth following up on, return a short gist
        of it (Wally will rephrase a natural check-in later); else empty string."""
        t = str(user_text or "").strip()
        if len(t) < 6 or t.endswith("?"):
            return ""
        low = t.lower()
        if not any(trig in low for trig in self._THREAD_TRIGGERS):
            return ""
        return " ".join(t.split()[:12])[:80]

    def _banter_context(self) -> Dict[str, object]:
        """Live state for the wit engine so instant lines match the real moment."""
        store = getattr(self, "memory_store", None)
        rel = store.relationship_context() if store is not None else {}
        monitor = self.activity_monitor
        return {
            "daypart": self._local_time_context().get("daypart", ""),
            "recent_key_score": round(getattr(monitor, "recent_key_score", 0.0), 1),
            "idle_seconds": round(max(0.0, time.time() - getattr(monitor, "last_input_time", time.time())), 1),
            "window_changes": int(getattr(self, "_event_reaction_counters", {}).get("window", 0)),
            "debris_count": self.debris_overlay.item_count() if self.cfg.debris_enabled else 0,
            "work_pressure": round(self.work_pressure, 1),
            "sessions": int(rel.get("sessions", 0) or 0),
        }

    def _fallback_life_line(self, reason: str) -> str:
        # Wally's reflexes: an instant, context-aware witty line when the LLM gives
        # body controls without speech, is slow, or is offline. The wit engine reads
        # the real moment (time, typing storm, mess, idle, how long we've known each
        # other) so this never feels like a canned filler.
        ctx = self._banter_context()
        avoid = self.recent_pet_lines[-10:]
        mood = self._dominant_mood()
        if "startup" in reason or "intro" in reason:
            return banter.greeting(ctx, avoid=avoid)
        if "screen" in reason or "scene" in reason:
            return banter.pick("screen", ctx, avoid=avoid, mood=mood)
        if "overload" in reason or "work" in reason:
            return banter.pick("overwhelmed", ctx, avoid=avoid)
        if "typing" in reason:
            return banter.pick("rapid_typing", ctx, avoid=avoid)
        # Occasionally call back to an earlier memorable line (a running gag).
        store = getattr(self, "memory_store", None)
        if store is not None and "ambient" in reason and random.random() < 0.18:
            gag = store.random_gag()
            line = banter.callback(gag, avoid=avoid) if gag else ""
            if line:
                return line
        return banter.auto(ctx, avoid=avoid, mood=mood)

    def show_bubble(self, text: str, duration_ms: int = 7000, source: str = "static") -> None:
        # Keep bubbles readable; very short durations made lines vanish mid-read.
        duration_ms = max(6500, int(duration_ms))
        now = time.time()
        priority_map = {"static": 0, "tool": 1, "user": 2, "ollama": 3, "error": 4}
        hold_map = {"static": 0.0, "tool": 3.2, "user": 2.4, "ollama": 4.2, "error": 4.8}
        current_source = str(getattr(self, "bubble_source", "static") or "static")
        current_priority = priority_map.get(current_source, 0)
        new_priority = priority_map.get(source, 0)
        bubble_active = bool(self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0)))
        allow_tool_to_reply_upgrade = current_source == "tool" and source in {"ollama", "error"}
        allow_static_upgrade = current_source == "static" and new_priority > current_priority
        allow_error_override = source == "error" and current_source != "error"
        if bubble_active and not (allow_tool_to_reply_upgrade or allow_static_upgrade or allow_error_override):
            if source != "static":
                self._pending_bubble_payload = (text, duration_ms, source)
            return
        self.bubble_text = text
        self.bubble_source = source
        self._bubble_shown_at = now
        self._bubble_protected_until = now + hold_map.get(source, 0.0)
        self._pending_bubble_payload = None
        self.bubble.show_message(text, self.frameGeometry(), duration_ms, source=source)
        if self.bubble_timer:
            self.bubble_timer.stop()
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self._hide_bubble)
        self.bubble_timer.start(duration_ms)
        QTimer.singleShot(0, self._sync_window_stack)
        self.update()

    def _hide_bubble(self) -> None:
        pending = getattr(self, "_pending_bubble_payload", None)
        self.bubble_text = ""
        self.bubble_source = "static"
        self._bubble_shown_at = 0.0
        self._bubble_protected_until = 0.0
        self._pending_bubble_payload = None
        self.update()
        if pending:
            text, duration_ms, source = pending
            QTimer.singleShot(0, lambda t=text, d=duration_ms, s=source: self.show_bubble(t, d, s))

    def set_expression(self, expression: str) -> None:
        self.expression = expression
        if expression in {"angry", "irritated", "frustrated"} and self.eyebrow_pose not in {"angry", "irritated", "frustrated"}:
            self.eyebrow_pose = expression
        self.update()

    def _update_eye_focus_from_action(self) -> None:
        # Eyes should follow intent, not stare at the user forever.
        if self.current_action in {"listen", "talk_to_user"}:
            self.eye_focus = "user"
            return
        if time.time() < self.dizzy_until:
            self.eye_focus = "mouse"
            self.eyebrow_pose = "dizzy"
            return
        if self.current_action in {"clean", "collect"}:
            self.eye_focus = "debris"
            if self.eyebrow_pose in {"happy", "flat"}:
                self.eyebrow_pose = "focused"
        elif self.current_action == "go_bin":
            self.eye_focus = "trash_bin"
            self.eyebrow_pose = "focused"
        elif self.current_action == "chase_butterfly":
            self.eye_focus = "butterfly"
            self.eyebrow_pose = "happy"
        elif self.current_action == "chase_eva":
            self.eye_focus = "up"
            self.eyebrow_pose = "love"
        elif self.current_action in {"watch_tv", "watch"}:
            self.eye_focus = "tv"
        elif self.current_action == "inspect_mouse":
            self.eye_focus = "mouse"
        elif self.target_point is not None:
            self.eye_focus = "left" if self.target_point.x() < self.x() else "right"
        elif self.eye_focus == "user" and time.time() > self.pause_until:
            self.eye_focus = "side"

    def _quota_should_act(self, seen_attr: str, acted_attr: str, window: int, minimum: int, base_probability: float) -> bool:
        """Window quota: random choice plus guaranteed minimum before the window closes.

        Example: window=10, minimum=4 means if early random choices did not reach
        4 actions, the last remaining encounters are forced so the actual window
        cannot end below 4/10.
        """
        seen = int(getattr(self, seen_attr, 0)) + 1
        acted = int(getattr(self, acted_attr, 0))
        remaining_after_this = max(0, window - seen)
        needed = max(0, minimum - acted)
        forced = needed > remaining_after_this
        should = forced or random.random() < base_probability
        if should:
            acted += 1
        if seen >= window:
            seen = 0
            acted = 0
        setattr(self, seen_attr, seen)
        setattr(self, acted_attr, acted)
        return should

    def _save_current_goal_for_butterfly_interrupt(self) -> bool:
        """Pause lower-priority work so the 40% butterfly chase is visibly real."""
        if self.current_action in {"chase_butterfly", "fall", "parachute", "listen", "talk_to_user"}:
            return False
        # Do not interrupt genuinely critical clean/bin routes, but pause softer goals.
        if self.current_action in {"clean", "go_bin"} and self.target_point is not None:
            return False
        if self._resume_after_butterfly_chase is not None:
            return True
        self._resume_after_butterfly_chase = {
            "action": self.current_action,
            "target": QPoint(self.target_point) if self.target_point is not None else None,
            "goal": self.current_goal,
            "pause_until": self.pause_until,
            "tv_break_until": getattr(self, "_tv_break_until", 0.0),
            "t": round(time.time(), 1),
        }
        self._remember_event("goal_paused_for_butterfly", text="butterfly priority", data={"did": "pause_goal_for_butterfly", "paused_action": self.current_action})
        return True

    def _resume_goal_after_butterfly_chase(self) -> None:
        item = self._resume_after_butterfly_chase
        if not item:
            return
        if self.is_dragging or self.current_action not in {"pause", "chill", "watch"}:
            return
        if time.time() < self.pause_until:
            QTimer.singleShot(700, self._resume_goal_after_butterfly_chase)
            return
        action = str(item.get("action") or "chill")
        target = item.get("target")
        self.current_goal = str(item.get("goal") or self.current_goal)[:48]
        self.current_action = action if action not in {"chase_butterfly", "fall", "parachute", "listen"} else "chill"
        self.target_point = QPoint(target) if isinstance(target, QPoint) else None
        self.pause_until = float(item.get("pause_until") or 0.0)
        if action in {"watch", "watch_tv"}:
            self._tv_break_until = float(item.get("tv_break_until") or 0.0)
        self._resume_after_butterfly_chase = None
        self._remember_event("goal_resumed_after_butterfly", text=self.current_action, data={"did": "resume_goal_after_butterfly"})

    def _choose_super_ball_kick(self) -> bool:
        seen = int(getattr(self, "_ball_kick_window_seen", 0)) + 1
        done = bool(getattr(self, "_ball_super_done_in_window", False))
        remaining_after_this = max(0, 30 - seen)
        super_kick = (random.random() < 0.034) or ((not done) and remaining_after_this <= 0)
        if super_kick:
            done = True
        if seen >= 30:
            seen = 0
            done = False
        self._ball_kick_window_seen = seen
        self._ball_super_done_in_window = done
        return super_kick

    def _save_current_goal_for_ball_interrupt(self) -> None:
        """Pause a lower-priority goal so a real ball crossing can happen now."""
        if self.current_action in {"kick_ball", "fall", "parachute", "listen", "talk_to_user"}:
            return
        # Do not overwrite a pending resume with another identical interrupt.
        if self._resume_after_ball_kick is not None:
            return
        if self.target_point is None and self.current_action in {"chill", "pause", "watch"}:
            return
        self._resume_after_ball_kick = {
            "action": self.current_action,
            "target": QPoint(self.target_point) if self.target_point is not None else None,
            "goal": self.current_goal,
            "pause_until": self.pause_until,
            "t": round(time.time(), 1),
        }
        self._remember_event("goal_paused_for_ball", text="ball priority", data={"did": "pause_goal_for_ball", "paused_action": self.current_action})

    def _resume_goal_after_ball_kick(self) -> None:
        item = self._resume_after_ball_kick
        if not item:
            return
        if self.is_dragging or self.current_action not in {"pause", "chill", "watch"}:
            return
        if time.time() < self.pause_until:
            QTimer.singleShot(700, self._resume_goal_after_ball_kick)
            return
        action = str(item.get("action") or "chill")
        target = item.get("target")
        self.current_goal = str(item.get("goal") or self.current_goal)[:48]
        self.current_action = action if action not in {"kick_ball", "fall", "parachute", "listen"} else "chill"
        self.target_point = QPoint(target) if isinstance(target, QPoint) else None
        self.pause_until = float(item.get("pause_until") or 0.0)
        self._resume_after_ball_kick = None
        self._remember_event("goal_resumed_after_ball", text=self.current_action, data={"did": "resume_goal_after_ball"})

    def _save_current_goal_for_butterfly_interrupt(self) -> bool:
        """Pause lower-priority work so the 40% butterfly chase is visibly real."""
        if self.current_action in {"chase_butterfly", "fall", "parachute", "listen", "talk_to_user"}:
            return False
        # Do not interrupt genuinely critical clean/bin routes, but pause softer goals.
        if self.current_action in {"clean", "go_bin"} and self.target_point is not None:
            return False
        if self._resume_after_butterfly_chase is not None:
            return True
        self._resume_after_butterfly_chase = {
            "action": self.current_action,
            "target": QPoint(self.target_point) if self.target_point is not None else None,
            "goal": self.current_goal,
            "pause_until": self.pause_until,
            "tv_break_until": getattr(self, "_tv_break_until", 0.0),
            "t": round(time.time(), 1),
        }
        self._remember_event("goal_paused_for_butterfly", text="butterfly priority", data={"did": "pause_goal_for_butterfly", "paused_action": self.current_action})
        return True

    def _resume_goal_after_butterfly_chase(self) -> None:
        item = self._resume_after_butterfly_chase
        if not item:
            return
        if self.is_dragging or self.current_action not in {"pause", "chill", "watch"}:
            return
        if time.time() < self.pause_until:
            QTimer.singleShot(700, self._resume_goal_after_butterfly_chase)
            return
        action = str(item.get("action") or "chill")
        target = item.get("target")
        self.current_goal = str(item.get("goal") or self.current_goal)[:48]
        self.current_action = action if action not in {"chase_butterfly", "fall", "parachute", "listen"} else "chill"
        self.target_point = QPoint(target) if isinstance(target, QPoint) else None
        self.pause_until = float(item.get("pause_until") or 0.0)
        if action in {"watch", "watch_tv"}:
            self._tv_break_until = float(item.get("tv_break_until") or 0.0)
        self._resume_after_butterfly_chase = None
        self._remember_event("goal_resumed_after_butterfly", text=self.current_action, data={"did": "resume_goal_after_butterfly"})

    def _choose_super_ball_kick(self) -> bool:
        seen = int(getattr(self, "_ball_kick_window_seen", 0)) + 1
        done = bool(getattr(self, "_ball_super_done_in_window", False))
        remaining_after_this = max(0, 30 - seen)
        super_kick = (random.random() < 0.034) or ((not done) and remaining_after_this <= 0)
        if super_kick:
            done = True
        if seen >= 30:
            seen = 0
            done = False
        self._ball_kick_window_seen = seen
        self._ball_super_done_in_window = done
        return super_kick

    def _perform_ball_kick(self, reason: str = "planned_kick", resume_after: bool = False) -> None:
        # Do not let encounter kicks fire from far away. If we are not visually
        # close enough, move beside the ball first; the normal kick action will
        # fire when Wally arrives.
        ball_point = self.debris_overlay.ball_point_global()
        if ball_point is not None and reason == "crossed_ball":
            center_x = self.frameGeometry().center().x()
            floor_gap = abs(ball_point.y() - self.frameGeometry().bottom())
            if abs(center_x - ball_point.x()) > max(42, self.width() * 0.34) or floor_gap > max(48, self.height() * 0.52):
                self.current_action = "kick_ball"
                self.target_point = self._ball_target_point()
                self._remember_event("ball_kick_delayed_until_contact", text="moving to ball", data={"did": "move_to_ball_before_kick", "reason": reason})
                return
        super_kick = reason in {"eva_sad_angry_kick", "eva_sad_super_kick"} or self._choose_super_ball_kick()
        style = random.choice(["roll", "chip", "lob", "side_spin", "bounce_shot"])
        power = random.uniform(3.4, 5.6) if super_kick else random.uniform(0.75, 2.15)
        kick = self.debris_overlay.kick_ball_global(
            self.frameGeometry().center().x(),
            power=power,
            style=style,
            super_kick=super_kick,
        )
        self._play_whoa_sound()
        self.set_expression("excited")
        self._nudge_mood(excited=22 if super_kick else 12, playful=14, proud=10 if super_kick else 4, bored=-18)
        self._apply_body_controls({"antenna": "wiggle", "eyes": "basketball", "eyebrow": "mischief", "emoji": random.choice(["🏀", "⚡", "😎", "🤭"]), "left_arm": "cheer", "right_arm": "point"})
        self.current_action = "pause"
        self.target_point = None
        self.pause_until = time.time() + (2.4 if super_kick else random.uniform(1.4, 3.0))
        self._satisfy_need("play", 16 if super_kick else 10, react=False)
        # Instant commentary; the LLM (when it comments) upgrades this line.
        self._instant_event_quip("ball_super" if super_kick else "ball_kick")
        event = {"did": "kick_ball", "reason": reason, "kick": kick, "ball": self.debris_overlay.ball_status(), "super": super_kick}
        self._remember_action("kicked_ball", event)
        if resume_after:
            QTimer.singleShot(int(max(900, (self.pause_until - time.time()) * 1000 + 300)), self._resume_goal_after_ball_kick)
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            should_comment = super_kick or self._quota_should_act("_ball_event_llm_window_seen", "_ball_event_llm_window_sent", 5, 1, 0.35)
            if time.time() - self._last_ball_event_llm_at > 5 and should_comment:
                self._last_ball_event_llm_at = time.time()
                self._pending_activity_note = {"kind": "ball_kick_event", **event, "tone_choices": ["excited", "funny", "sarcastic", "proud", "naughty"], "quota": "at least 1 ball event comment per 5 available events"}
                self.request_ai_reaction("ball_kick_event_react", use_vision=False)

    def _distance_to_segment(self, p: QPoint, a: QPoint, b: QPoint) -> float:
        px, py = float(p.x()), float(p.y())
        ax, ay = float(a.x()), float(a.y())
        bx, by = float(b.x()), float(b.y())
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom <= 0.01:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
        cx, cy = ax + t * dx, ay + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def _maybe_ball_cross_encounter(self) -> bool:
        """Detect visible ball crossings and enforce the 4/10 kick rule.

        v8.31 treats ball contact as a high-priority micro-event. If Wally crosses
        the ball while heading to another non-dangerous goal, the goal is paused,
        the kick happens immediately, and the old goal resumes after the kick.
        """
        now_center = self.frameGeometry().center()
        prev_center = getattr(self, "_last_pet_center_for_ball", None)
        self._last_pet_center_for_ball = QPoint(now_center)

        if self.is_dragging or self.current_action in {"kick_ball", "fall", "parachute", "listen", "talk_to_user"}:
            return False
        ball = self.debris_overlay.ball_point_global()
        if ball is None:
            self._ball_contact_zone_active = False
            return False

        now = time.time()
        frame = self.frameGeometry()
        # Realistic contact: Wally must overlap the ball with his lower body/treads
        # or his movement path must pass very close. Older versions used a huge
        # 120-180px halo, which made him kick from far away.
        x_margin = max(26, int(self.width() * 0.18))
        y_margin = max(42, int(self.height() * 0.46))
        expanded_body = QRect(
            frame.left() - x_margin,
            frame.bottom() - y_margin,
            frame.width() + x_margin * 2,
            y_margin + 30,
        )
        lower_band_hit = (
            frame.left() - x_margin <= ball.x() <= frame.right() + x_margin
            and abs(ball.y() - frame.bottom()) <= y_margin
        )
        near_path = False
        crossed_x = False
        if prev_center is not None:
            path_threshold = max(34.0, self.width() * 0.26)
            near_path = self._distance_to_segment(ball, prev_center, now_center) <= path_threshold
            prev_left = prev_center.x() - self.width() // 2 - x_margin
            prev_right = prev_center.x() + self.width() // 2 + x_margin
            now_left = now_center.x() - self.width() // 2 - x_margin
            now_right = now_center.x() + self.width() // 2 + x_margin
            crossed_x = min(prev_left, now_left) <= ball.x() <= max(prev_right, now_right)
            same_band = abs(ball.y() - frame.bottom()) <= y_margin
            near_path = near_path and same_band or (crossed_x and same_band and expanded_body.contains(ball))

        contact = expanded_body.contains(ball) or lower_band_hit or near_path
        if not contact:
            self._ball_contact_zone_active = False
            return False
        # Count one encounter when Wally enters the contact zone, not every frame while he stands there.
        if self._ball_contact_zone_active and now - self._last_ball_encounter_at < 2.2:
            return False
        self._ball_contact_zone_active = True
        if now - self._last_ball_encounter_at < 0.45:
            return False

        self._last_ball_encounter_at = now
        status = self.debris_overlay.ball_status()
        detected_by = "lower_band" if lower_band_hit else ("path_cross" if near_path else "expanded_body")
        self._remember_event("ball_crossed", text="near basketball", data={"did": "cross_ball", "ball": status, "detected_by": detected_by, "action_before": self.current_action})
        should_kick = self._quota_should_act("_ball_cross_window_seen", "_ball_cross_window_kicks", 10, 4, 0.40)
        if should_kick:
            self._save_current_goal_for_ball_interrupt()
            self._perform_ball_kick("crossed_ball", resume_after=True)
            return True

        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            if time.time() - self._last_ball_event_llm_at > 7 and self._quota_should_act("_ball_event_llm_window_seen", "_ball_event_llm_window_sent", 5, 1, 0.25):
                self._last_ball_event_llm_at = time.time()
                self._pending_activity_note = {"kind": "ball_crossed_no_kick", "ball": status, "hint": "React naturally; Wally noticed the ball but did not kick.", "quota": "at least 1 ball event comment per 5 available events"}
                self.request_ai_reaction("ball_crossed_no_kick_react", use_vision=False)
        return False

    def _reaction_for_user_text(self, text: str) -> str:
        t = text.lower()
        if any(word in t for word in ["hi", "hello", "hey", "yo"]):
            return "happy"
        if any(word in t for word in ["sad", "upset", "tired", "bad day", "lonely"]):
            return "soft"
        if "?" in t or any(word in t for word in ["why", "how", "what", "when"]):
            return "curious"
        if any(word in t for word in ["wow", "amazing", "awesome", "great"]):
            return "excited"
        if any(word in t for word in ["love", "cute", "heart"]):
            return "love"
        return random.choice(["curious", "happy", "soft"])

    def _reaction_for_answer(self, answer: str) -> str:
        t = answer.lower()
        if any(word in t for word in ["sorry", "can't", "cannot", "error"]):
            return "soft"
        if any(word in t for word in ["great", "awesome", "nice", "happy", "glad"]):
            return "happy"
        if "?" in t:
            return "curious"
        return "talking"

    def _animate(self) -> None:
        self.tick += 1
        self.float_phase += 0.055
        self.wheel_phase += 0.18
        now = time.time()
        if now < self.dizzy_until:
            self.expression = "dizzy"
        elif self.expression == "dizzy":
            self.expression = "curious"
            if self.current_action == "dizzy":
                self.current_action = "chill"
            self.eyebrow_pose = "curious"
            self.eye_focus = "side"
        self._update_eye_focus_from_action()
        if self.current_action == "chase_eva" and not self.debris_overlay.eva_visible and time.time() > self._eva_sad_until:
            self._start_eva_miss_mood()
            self.update()
            return
        if self._maybe_ball_cross_encounter():
            self.update()
            return
        if self.tick % 110 == 0:
            self.blink_amount = 1.0
        elif self.blink_amount > 0:
            self.blink_amount = max(0.0, self.blink_amount - 0.25)

        self.head_angle = 4.0 * math.sin(self.float_phase * 0.7)
        if self.expression == "curious":
            self.head_angle += 9.0
        elif self.expression == "thinking":
            self.head_angle += 3.0 * math.sin(self.float_phase * 3.0)
        elif self.expression == "scared":
            self.head_angle += 6.0 * math.sin(self.float_phase * 7.0)
        elif self.expression == "love":
            self.head_angle += 5.0 * math.sin(self.float_phase * 1.8)
        elif self.expression == "cleaning":
            self.head_angle += 2.0 * math.sin(self.float_phase * 5.0)
        elif self.expression == "dizzy":
            self.head_angle += 10.0 * math.sin(self.float_phase * 13.0)

        if self.fall_mode != "none" and not self.is_dragging:
            self._fall_step()
            self.update()
            return

        moving_now = self.target_point is not None or self.current_action in {"clean", "go_bin", "chase_butterfly", "chase_eva", "inspect_mouse", "watch_tv", "move_to", "kick_ball"}
        if (self.store.config().roam_enabled or moving_now) and not self.is_dragging and self.isVisible():
            self._roam_step()
            # Second check after movement catches real visual crossings from this frame.
            if self._maybe_ball_cross_encounter():
                self.update()
                return
        self._maybe_weather_play(now)
        if self.cfg.debris_enabled and self.tick % 3 == 0:
            # Pickup should feel physical: while moving across the taskbar, the treads
            # can catch debris in the way. Only the explicit clean action may redirect
            # the rover; incidental pickup during play/chase/TV travel does not instantly
            # turn it into a bin shuttle.
            if self.current_action == "clean":
                self._clear_debris_under_pet(extra_radius=58, incidental=False)
            elif self.current_action in {"move_to", "chase_butterfly", "chase_eva", "watch_tv", "inspect_mouse", "roam", "dance"}:
                self._clear_debris_under_pet(extra_radius=42, incidental=True)
        if self.tick % 30 == 0:
            self._update_taskbar_lane()
        self.update()

    def _sync_window_stack(self) -> None:
        try:
            if self.debris_overlay.isVisible():
                self.debris_overlay.lower()
        except RuntimeError:
            pass
        try:
            self.raise_()
        except RuntimeError:
            pass
        try:
            if self.bubble.isVisible():
                self.bubble.raise_()
        except RuntimeError:
            pass

    def _maybe_weather_play(self, now: float) -> None:
        if not getattr(self.cfg, "weather_enabled", False):
            return
        weather = self.debris_overlay.weather_status() if hasattr(self.debris_overlay, "weather_status") else {}
        if not weather or not weather.get("enabled"):
            return
        mode = str(weather.get("mode", "sunny"))
        daylight = str(weather.get("daylight", "day"))
        celestial = weather.get("celestial", {}) if isinstance(weather.get("celestial"), dict) else {}
        puddle_point = self.debris_overlay.nearest_puddle_global_to(self.frameGeometry().center().x(), self.frameGeometry().bottom())
        puddle_count = int(weather.get("puddle_count", 0) or 0)
        cloud_count = int(weather.get("cloud_count", 0) or 0)
        cleaner = weather.get("mud_cleaner", {}) if isinstance(weather.get("mud_cleaner"), dict) else {}
        signature = f"{mode}:{daylight}:{celestial.get('kind', 'sun')}"
        if signature != str(getattr(self, "_last_weather_signature", "")):
            self._last_weather_signature = signature
            self._last_weather_signature_at = now
            if not self.bubble_text and now - float(getattr(self, "_last_weather_comment_at", 0.0)) > 10:
                if mode == "rainy":
                    self.show_bubble(random.choice(["Rainy patrol mode.", "Tiny rain report!", "Puddle season activated."]), 7000, source="static")
                elif celestial.get("kind") == "moon":
                    self.show_bubble(random.choice(["Moon watch duty.", "Night sky detected.", "Tiny moon patrol."]), 7000, source="static")
                elif daylight == "dawn":
                    self.show_bubble(random.choice(["Morning glow online.", "Sunrise check-in.", "Tiny dawn stretch."]), 7000, source="static")
                self._last_weather_comment_at = now
        if puddle_point and self.current_action in {"move_to", "roam", "chill", "pause", "watch", "watch_tv"}:
            near_puddle = abs(self.frameGeometry().center().x() - puddle_point.x()) < 34 and abs(self.frameGeometry().bottom() - puddle_point.y()) < 26
            if near_puddle and now - float(getattr(self, "_last_puddle_play_at", 0.0)) > 12:
                self._last_puddle_play_at = now
                self.emoji_effect = "💧"
                self.emoji_until = now + 5.5
                self._nudge_mood(playful=4.5, curious=2.2, bored=-2.0)
                if not self.bubble_text:
                    self.show_bubble(random.choice(["splish!", "Puddle boop.", "Tiny splash detected!"]), 6500, source="static")
        if mode == "rainy" and puddle_point and self.target_point is None and self.current_action in {"chill", "pause", "watch"}:
            if now - float(getattr(self, "_last_weather_wander_at", 0.0)) > 28 and random.random() < 0.10:
                self._last_weather_wander_at = now
                self.current_action = "move_to"
                self.target_point = self._clamp_to_lane(QPoint(puddle_point.x(), puddle_point.y() - self.height() // 2))
                self.eye_focus = "down"
                self.eyebrow_pose = "curious"
        cleaner_xy = cleaner.get("global_xy") if cleaner.get("visible") else None
        if isinstance(cleaner_xy, list) and len(cleaner_xy) >= 2:
            center = self.frameGeometry().center()
            cleaner_state = str(cleaner.get("state", ""))
            cleaner_distance = abs(float(cleaner_xy[0]) - center.x())
            cleaner_eventful = cleaner_distance < 150 or cleaner_state in {"enter", "clean"}
            if cleaner_eventful and now - float(getattr(self, "_last_mud_cleaner_annoy_at", 0.0)) > 9:
                self._last_mud_cleaner_annoy_at = now
                self._nudge_mood(irritated=4.5, playful=3.0, curious=2.0, bored=-2.0)
                self.set_expression("thinking")
                self._apply_body_controls({"eyes": "down", "eyebrow": "annoyed", "left_arm": "point"})
                self._remember_event("mud_cleaner_rivalry", text="rain cleaner scrubbing Wally's mud trail", data={
                    "did": "tiny_mud_cleaner_scrubbed_trail",
                    "weather": weather,
                    "inspiration": "fussy cleaner bot follows and cleans the messy rover trail; use the dynamic only, do not quote movie dialogue",
                })
                if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
                    self._pending_activity_note = {
                        "kind": "mud_cleaner_rivalry",
                        "scene": "During rain, Wally's treads leave cute mud trails. A tiny fussy cleaner robot rolls in from off-screen and scrubs them away, which annoys Wally in a playful rivalry.",
                        "weather": weather,
                        "cleaner_state": cleaner_state,
                        "distance_px": round(cleaner_distance, 1),
                        "tone_choices": ["funny", "mock-dramatic", "fussy", "playfully offended", "cute rivalry"],
                        "hint": "Give Wally one short original comeback about the cleaner erasing his mud art. Do not quote or imitate exact movie lines.",
                    }
                    self.request_ai_reaction("mud_cleaner_rivalry_react", use_vision=False)
                elif not self.bubble_text:
                    self.show_bubble(random.choice(["Hey! I was using that mud.", "Tiny mop rival detected.", "Stop polishing my puddle art."]), 6500, source="static")
        ball_status = self.debris_overlay.ball_status() if hasattr(self.debris_overlay, "ball_status") else {}
        if bool(ball_status.get("over_puddle")) and now - float(getattr(self, "_last_ball_puddle_comment_at", 0.0)) > 10:
            self._last_ball_puddle_comment_at = now
            self._nudge_mood(excited=3.0, playful=3.5, proud=1.0)
            if not self.bubble_text:
                self.show_bubble(random.choice(["Ball made a splash!", "Puddle crossover!", "Wet basketball drama."]), 6800, source="static")
        if not self.bubble_text and now - float(getattr(self, "_last_weather_comment_at", 0.0)) > 42 and self.current_action in {"watch", "watch_tv", "chill", "pause"}:
            line = ""
            if celestial.get("kind") == "moon":
                line = random.choice(["Moon is cruising.", "Night sky looks cozy.", "Moon shift looks serious."])
            elif daylight == "day" and float(celestial.get("progress", 0.0) or 0.0) > 0.42 and float(celestial.get("progress", 0.0) or 0.0) < 0.58:
                line = random.choice(["Sun is high. Busy-human o'clock.", "Noon vibes detected.", "Sun parked near the middle."])
            elif mode == "cloudy" and cloud_count >= 3:
                line = random.choice(["Cloud convoy overhead.", "Sky fluff patrol.", "Clouds are gossiping again."])
            if line:
                self._last_weather_comment_at = now
                self.show_bubble(line, 7200, source="static")

    def _clamp_mood(self, value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    def _nudge_mood(self, **deltas: float) -> None:
        for key, delta in deltas.items():
            if key in self.moods:
                self.moods[key] = self._clamp_mood(self.moods.get(key, 0.0) + float(delta))

    def _mood_snapshot(self) -> Dict[str, int]:
        return {key: int(round(self._clamp_mood(value))) for key, value in self.moods.items()}

    def _top_moods(self, limit: int = 4) -> str:
        items = sorted(self.moods.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return ", ".join(f"{k}:{int(v)}" for k, v in items)

    # Emotional resting state; drift returns here so Wally never gets stuck in one mood.
    _MOOD_BASELINES = {
        "bored": 30.0, "curious": 48.0, "excited": 18.0, "anxious": 8.0,
        "irritated": 10.0, "frustrated": 6.0, "playful": 58.0, "cozy": 16.0, "proud": 10.0,
        "naughty": 18.0, "sarcastic": 14.0, "encouraging": 22.0,
    }

    def _dominant_mood(self, min_spike: float = 8.0) -> Optional[str]:
        """The mood spiking most above its baseline right now, or None if calm.

        Used to color his voice so words match his face. Only moods the banter wit
        engine can speak in are returned."""
        speakable = {"irritated", "frustrated", "proud", "bored", "excited", "cozy", "curious", "playful", "naughty", "anxious"}
        best_key, best_dev = None, min_spike
        for key, base in self._MOOD_BASELINES.items():
            if key not in speakable:
                continue
            dev = self.moods.get(key, base) - base
            if dev > best_dev:
                best_key, best_dev = key, dev
        return best_key

    def _update_mood_model(self) -> None:
        now = time.time()
        dt = max(0.15, min(4.0, now - self._last_mood_update_at))
        self._last_mood_update_at = now
        debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        # Gentle drift toward baseline so Wally does not get stuck in one emotional state.
        baselines = self._MOOD_BASELINES
        for key, base in baselines.items():
            self.moods[key] = self._clamp_mood(self.moods.get(key, base) + (base - self.moods.get(key, base)) * 0.015 * dt)

        if debris_count > self._last_debris_count_seen:
            jump = debris_count - self._last_debris_count_seen
            self._nudge_mood(irritated=2.5 * jump, frustrated=1.2 * jump, curious=0.8 * jump)
        self._last_debris_count_seen = debris_count

        if debris_count >= 8:
            self._nudge_mood(irritated=0.9 * dt, frustrated=0.6 * dt, anxious=0.2 * dt)
        elif debris_count >= 4:
            self._nudge_mood(irritated=0.35 * dt, curious=0.25 * dt)

        if self.current_action == "clean":
            self._nudge_mood(proud=0.55 * dt, irritated=-0.35 * dt, bored=-0.5 * dt)
        elif self.current_action == "go_bin":
            self._nudge_mood(proud=0.4 * dt, curious=0.15 * dt)
        elif self.current_action == "chase_butterfly":
            self._nudge_mood(excited=0.7 * dt, curious=0.45 * dt, bored=-0.6 * dt)
        elif self.current_action in {"watch", "watch_tv"}:
            self._nudge_mood(cozy=0.5 * dt, bored=-0.3 * dt)
        elif self.current_action in {"chill", "pause", "nap"}:
            self._nudge_mood(bored=0.25 * dt)

        if self.current_action == self._last_action_name_for_mood:
            self._same_action_streak += 1
            if self._same_action_streak >= 4:
                self._nudge_mood(bored=0.9 * dt, curious=-0.15 * dt)
        else:
            self._last_action_name_for_mood = self.current_action
            self._same_action_streak = 0

        # Make the emotion rollercoaster *visible*: let whichever mood is currently
        # spiking above its baseline drive the face, so Wally actually looks excited,
        # frustrated, bored, proud, etc. instead of sitting on one default look.
        self._apply_mood_to_face(baselines)

    # Mood meter (deviation above baseline) -> visible expression + brow.
    _MOOD_FACE_MAP = {
        "frustrated": ("frustrated", "frustrated"),
        "irritated": ("irritated", "irritated"),
        "anxious": ("scared", "worried"),
        "excited": ("excited", "happy"),
        "proud": ("proud", "proud"),
        "cozy": ("soft", "soft"),
        "bored": ("sleepy", "flat"),
        "curious": ("curious", "curious"),
        "playful": ("happy", "happy"),
        "naughty": ("happy", "mischief"),
        "sarcastic": ("thinking", "raised"),
        "encouraging": ("happy", "happy"),
    }

    def _apply_mood_to_face(self, baselines: Dict[str, float]) -> None:
        # Don't fight an action that already owns the face, a fresh LLM/user line, or
        # special states (dizzy, dragging, EVA, naps); those are stronger signals.
        now = time.time()
        if self.is_dragging or now < self.dizzy_until:
            return
        if now < float(getattr(self, "_eva_sad_until", 0.0)):
            return  # protect the scripted heartbreak look
        if self.current_action not in {"chill", "pause", "roam", "idle", "nap", "none", ""}:
            return
        if now - float(getattr(self, "_last_llm_expression_at", 0.0)) < 7.0:
            return
        if now - float(getattr(self, "_last_mood_face_at", 0.0)) < 1.6:
            return

        # Pick the mood that deviates most from its baseline = what's spiking now.
        best_key, best_dev = "", 0.0
        for key, base in baselines.items():
            dev = self.moods.get(key, base) - base
            if dev > best_dev:
                best_key, best_dev = key, dev
        # Needs a real spike to override the neutral curious look.
        if best_dev < 7.0 or best_key not in self._MOOD_FACE_MAP:
            return
        expression, brow = self._MOOD_FACE_MAP[best_key]
        if expression != self.expression:
            self.expression = expression
            self.eyebrow_pose = brow
            self._last_mood_face_at = now
            self.update()

    def _maybe_ocd_cleaning(self, debris_count: int, active_moving: bool) -> bool:
        if not self.cfg.debris_enabled or debris_count <= 0 or active_moving or self.is_dragging:
            return False
        now = time.time()
        # Prevent the bin-orbit bug: after dumping, breathe/play unless the mess is genuinely visible.
        if now - self._last_dump_at < 7.5 and debris_count < 7:
            return False
        if now - self._last_clean_decision_at < 5.5:
            return False
        irritation = self.moods.get("irritated", 0.0)
        frustration = self.moods.get("frustrated", 0.0)
        bored = self.moods.get("bored", 0.0)
        play = self.moods.get("playful", 0.0)
        # Cleaner instinct, not cleaner obsession. Debris matters, but curiosity/play can divert.
        pressure = debris_count * 8.0 + irritation * 0.65 + frustration * 0.75 + bored * 0.10 - play * 0.14
        if self.debris_overlay.butterfly_visible and now - self._last_diversion_from_clean_at > 20 and random.random() < 0.45:
            self._last_diversion_from_clean_at = now
            self._apply_reaction_action("chase_butterfly", 2, "butterfly")
            return True
        should_clean = (
            debris_count >= 8
            or (debris_count >= 5 and pressure > 46)
            or (debris_count >= 3 and (irritation > 32 or frustration > 24) and random.random() < 0.55)
            or (debris_count >= 2 and irritation > 55 and random.random() < 0.34)
        )
        if not should_clean:
            return False
        self._last_clean_decision_at = now
        self._set_current_goal_item(self._goal_item("collect a cleanup batch", "clean", "nearest_debris", "ocd_cleaner", priority=6), lock_seconds=12.0)
        self._start_cleaning_behavior()
        self._apply_body_controls({"eyes": "debris", "eyebrow": "focused", "emoji": random.choice(["🧹", "✨", "🫧"]), "left_arm": "collect", "right_arm": "collect", "antenna": "perked"})
        if now - self._last_clean_bubble_at > 28 and self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            self.request_ai_reaction("ocd_cleaning_started_but_stay_playful", use_vision=False)
            self._last_clean_bubble_at = now
        return True

    def _maybe_tantrum(self, debris_count: int, active_moving: bool) -> bool:
        now = time.time()
        if active_moving or debris_count < 6 or now - self._last_tantrum_at < 55:
            return False
        if self.moods.get("frustrated", 0) < 24 and self.moods.get("irritated", 0) < 36:
            return False
        if random.random() > 0.36:
            return False
        self._last_tantrum_at = now
        self.current_action = "pause"
        self.target_point = None
        self.pause_until = now + 3.2
        self.set_expression("angry")
        self._apply_body_controls({"antenna": "wiggle", "eyes": "debris", "eyebrow": "angry", "emoji": random.choice(["⚡", "💢", "😤", "🗑️"]), "left_arm": "cheer", "right_arm": "point"})
        self._play_tantrum_garbage_sound()
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            self.request_ai_reaction("tiny_cleaner_tantrum_mess_overload", force=True, use_vision=False)
        return True

    def _maybe_mood_swing_activity(self, debris_count: int, active_moving: bool) -> bool:
        """Small internal creature-drive layer.

        This is deliberately not an LLM replacement; it keeps Wally alive between
        local-model calls and makes moods visible even when JSON is weak.
        """
        now = time.time()
        if active_moving or self.is_dragging or now < self.pause_until:
            return False
        if now - self._last_mood_swing_at < 9.0:
            return False
        self._last_mood_swing_at = now
        irritated = self.moods.get("irritated", 0.0)
        frustrated = self.moods.get("frustrated", 0.0)
        bored = self.moods.get("bored", 0.0)
        curious = self.moods.get("curious", 0.0)
        playful = self.moods.get("playful", 0.0)

        if debris_count >= 7 and (irritated > 34 or frustrated > 26):
            # Visible OCD twitch before a clean: stare at mess, brows tighten, tiny rage.
            self.set_expression("irritated")
            self._apply_body_controls({"eyes": "debris", "eyebrow": "irritated", "emoji": random.choice(["💢", "🧹", "🗑️", "⚡"]), "left_arm": "point", "right_arm": "collect", "antenna": "wiggle"})
            if random.random() < 0.45:
                self._maybe_ocd_cleaning(debris_count, active_moving=False)
            elif self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker) and now - self.last_ai_request_at > 15.0:
                self.request_ai_reaction("visible_mood_swing_irritated_by_mess", use_vision=False)
            return True

        if bored > 60 and random.random() < 0.66:
            self._nudge_mood(playful=5, curious=3, bored=-8)
            self._apply_reaction_action(random.choice(["sing", "dance", "roam", "watch_tv", "inspect"]), 2, random.choice(["random", "tv_sofa", "screen", "mouse"]))
            return True

        if curious > 66 and random.random() < 0.52:
            self._apply_reaction_action("inspect", 2, random.choice(["mouse", "screen", "random", "debris"]))
            return True

        if playful > 72 and random.random() < 0.34:
            self._apply_reaction_action(random.choice(["wave", "dance", "sing"]), 2, "current")
            return True

        return False

    def _start_tv_break(self, reason: str = "scheduled_tv_break", force: bool = False) -> bool:
        """Send Wally to the sofa/TV for a real 30-second break."""
        now = time.time()
        if not force and now < self._tv_break_until:
            return True
        if self.current_action in {"clean", "go_bin", "chase_butterfly", "chase_eva", "fall", "parachute"} and self.target_point is not None and not force:
            return False
        self._tv_break_reason = reason
        self._tv_break_duration_seconds = 30.0
        self._tv_break_mid_comment_scheduled = False
        self._set_current_goal_item(self._goal_item("take a tiny TV break", "watch_tv", "tv_sofa", reason, priority=7), lock_seconds=35.0)
        self._apply_reaction_action("watch_tv", 3, "tv_sofa")
        return True

    def _begin_tv_break(self, reason: str = "tv_break") -> None:
        now = time.time()
        self._last_tv_break_started_at = now
        self._tv_break_until = now + max(30.0, float(getattr(self, "_tv_break_duration_seconds", 30.0)))
        self.pause_until = self._tv_break_until
        self.current_action = "watch"
        self.target_point = None
        self.set_expression("watching")
        self.debris_overlay.set_tv_mode(random.choice(["movie", "anime", "stars", "hearts", "fireplace", "smile"]))
        self._apply_body_controls({"eyes": "tv", "eyebrow": "focused", "emoji": "📺", "left_arm": "shy", "right_arm": "hold"})
        self._nudge_mood(cozy=10, bored=-6, playful=4, irritated=-4)
        self._remember_event("tv_break_started", text=reason, data={"did": "watch_tv_30s", "duration_seconds": 30, "target": "tv_sofa"})
        if not self.bubble_text:
            self.show_bubble(random.choice(["Tiny TV break.", "Sofa duty begins.", "Brain snack time." ]), 6500, source="static")
        self._request_tv_break_comment("tv_break_started")
        if not self._tv_break_mid_comment_scheduled:
            self._tv_break_mid_comment_scheduled = True
            QTimer.singleShot(10000, lambda: self._request_tv_break_comment("tv_break_hum_or_comment_10s"))
            QTimer.singleShot(22000, lambda: self._request_tv_break_comment("tv_break_hum_or_comment_22s"))

    def _request_tv_break_comment(self, reason: str) -> None:
        now = time.time()
        if now > getattr(self, "_tv_break_until", 0) + 1:
            return
        if not self.cfg.ai_reactions_enabled:
            if now - self._last_tv_break_llm_at > 12 and not self.bubble_text:
                self.show_bubble(random.choice(["Hmm-hmm 📺", "Tiny theme song.", "TV understands me."]), 6500, source="static")
            return
        if self._thread_running(self.reaction_worker) or now - self.last_ai_request_at < 6:
            return
        self._last_tv_break_llm_at = now
        self._pending_activity_note = {
            "kind": reason,
            "meaning": "Wally is intentionally taking a 30-second sofa TV break.",
            "purpose": "comment on TV, hum, make a tiny joke, or react in character",
            "tv_mode": getattr(self.debris_overlay, "tv_mode", "static"),
            "tone_choices": ["cozy", "funny", "curious", "sarcastic", "sleepy", "excited"],
            "speech_rule": "complete sentence within word limit; no truncation",
        }
        self.request_ai_reaction(reason, force=True, use_vision=False)

    def _maybe_cowatch(self, now: float, active_moving: bool) -> bool:
        """Co-watch mode: while the user watches video (YouTube/Netflix/etc.), Wally
        goes to the TV, sits, and comments along every 5-10 minutes by reading the
        screen — present and cozy, but deliberately NOT disturbing."""
        if not self._cowatch_enabled:
            if self._cowatch_active:
                self._end_cowatch_session()
            return False
        title = get_active_window_title()
        hint = infer_media_hint(title)
        is_media = hint in {"youtube", "netflix", "video_player"}
        if not is_media:
            if self._cowatch_active:
                self._end_cowatch_session()
            self._cowatch_since = 0.0
            return False

        # Require the video to be sustained so brief clips don't trigger a sit-down.
        if not self._cowatch_since:
            self._cowatch_since = now
        if now - self._cowatch_since < 12:
            return False
        # Don't hijack a high-priority drama (EVA) or an in-progress travel.
        if self.current_action == "chase_eva" and self.debris_overlay.eva_visible:
            return False

        # Open a session the first time we settle in; track what we're watching.
        if not self._cowatch_active or self._cowatch_session is None:
            self._cowatch_session = {"started": now, "media": hint, "titles": [title[:90]], "comments": [], "observations": [], "summary": "", "obs_since_comment": 0}
        else:
            titles = self._cowatch_session.setdefault("titles", [])
            if title[:90] not in titles:
                titles.append(title[:90])
        first_activation = not self._cowatch_active
        self._cowatch_active = True
        # Co-watch is top priority: pause new clutter and EVA flybys so the couch
        # stays calm and he isn't yanked away mid-show.
        self.debris_overlay.set_spawn_paused(True)

        # Distance-based: walk to the sofa, then sit. This overrides whatever he was
        # doing (roaming, cleaning) so he actually goes instead of freezing in place.
        tv_target = self._tv_target_point()
        arrived = abs(self.x() - tv_target.x()) <= 30

        if first_activation and now - self._last_spoken_bubble_at > 6:
            self.show_bubble(random.choice(["Ooh, what are we watching? 🍿", "Movie time! Scooch over.", "Co-watch mode, engaged. 🍿"]), 5200, source="static")
            self._last_spoken_bubble_at = now

        if not arrived:
            # Head to the sofa (interrupting any other goal).
            self._tv_break_reason = "cowatch"
            self._tv_break_duration_seconds = 90.0
            self.current_action = "watch_tv"
            self.target_point = tv_target
            self.pause_until = 0.0
            self.set_expression("watching")
            self._apply_body_controls({"eyes": "tv", "eyebrow": "focused", "emoji": "🍿", "left_arm": "shy", "right_arm": "point"})
            return True

        # Arrived — seated and watching: stay cozy and keep the seat reserved.
        self._tv_break_until = max(getattr(self, "_tv_break_until", 0.0), now + 90.0)
        self.current_action = "watch"
        self.target_point = None
        self.pause_until = now + 4.0
        if self.expression != "watching":
            self.set_expression("watching")
            self._apply_body_controls({"eyes": "tv", "eyebrow": "focused", "emoji": "🍿", "left_arm": "shy", "right_arm": "hold"})
        self._nudge_mood(cozy=0.5, bored=-0.4, irritated=-0.3)

        self._cowatch_media_tick(hint, title, now)
        return True

    def _cowatch_media_tick(self, hint: str, title: str, now: float) -> None:
        """Two-tier co-watching: silently build context every ~30s, then comment when
        enough has accumulated so the remark reflects the unfolding story."""
        # Vision is required to read the screen/subtitles for real co-watch context.
        if not (self.cfg.ai_reactions_enabled and self.cfg.screenshot_reactions_enabled):
            # No vision: fall back to a sparse cozy quip so he's still present.
            if now - self._last_cowatch_comment_at >= 420:
                self._last_cowatch_comment_at = now
                self._cowatch_comment(hint, title)
            return
        if self._thread_running(self.reaction_worker) or self._thread_running(self.worker):
            return

        session = self._cowatch_session if isinstance(self._cowatch_session, dict) else {}
        obs_since = int(session.get("obs_since_comment", 0))
        since_comment = now - self._last_cowatch_comment_at

        # Comment when enough new context has built (and not too soon), or force one
        # at least every ~5 minutes so he's never silent for a whole act.
        ready_to_comment = (obs_since >= 4 and since_comment >= 120) or since_comment >= 300
        if ready_to_comment and not (self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0))):
            self._last_cowatch_comment_at = now
            if isinstance(self._cowatch_session, dict):
                self._cowatch_session["obs_since_comment"] = 0
            self._cowatch_comment(hint, title)
            return

        # Otherwise keep silently building context roughly every 30 seconds.
        if now - float(getattr(self, "_last_cowatch_obs_at", 0.0)) >= 30:
            self._last_cowatch_obs_at = now
            self._pending_activity_note = {
                "kind": "cowatch_observe",
                "media": hint,
                "instruction": "SILENT observation. Look at the screen and return b as a terse factual 4-8 word note of what's happening right now (scene/action/subtitle). No jokes, no character voice, just the note.",
            }
            self.request_ai_reaction("cowatch_observe", force=True, use_vision=True)

    def _end_cowatch_session(self) -> None:
        """Drop the live co-watch session but keep a short summary in memory so Wally
        can call back to it later ('that show from last night?')."""
        session = self._cowatch_session
        self._cowatch_active = False
        self._cowatch_session = None
        self.debris_overlay.set_spawn_paused(False)  # clutter & gusts resume
        if not session:
            return
        started = float(session.get("started", time.time()))
        if time.time() - started < 90:  # too short to be worth remembering
            return
        titles = [t for t in session.get("titles", []) if t]
        comments = list(session.get("comments", []))
        title = titles[-1] if titles else ""
        gist_bits = comments[-3:]
        gist = " | ".join(gist_bits) if gist_bits else f"watched for {round((time.time()-started)/60)} min"
        store = getattr(self, "memory_store", None)
        if store is not None:
            store.add_watch_history(str(session.get("media", "")), title, gist)

    def _cowatch_session_context(self) -> Dict[str, object]:
        session = self._cowatch_session or {}
        started = float(session.get("started", time.time()))
        comments = list(session.get("comments", []))
        titles = list(session.get("titles", []))
        return {
            "watching_for_minutes": round(max(0.0, (time.time() - started) / 60.0), 1),
            "title": (titles[-1] if titles else "")[:80],
            "story_so_far": str(session.get("summary", ""))[:500],
            "recent_moments": list(session.get("observations", []))[-8:],
            "your_earlier_comments": comments[-5:],
            "continuity_rule": "You have been watching this the whole time. Use story_so_far and recent_moments for continuity, react to the CURRENT screen, and don't repeat your earlier_comments. Feel like a friend who's been on the couch the whole show.",
        }

    def _cowatch_add_observation(self, note: str) -> None:
        """Append a silent observation and fold old ones into a rolling summary so a
        long video keeps continuity without the context growing unbounded."""
        session = self._cowatch_session
        if not isinstance(session, dict):
            return
        note = str(note or "").strip()[:90]
        if len(note) < 4:
            return
        obs = session.setdefault("observations", [])
        obs.append(note)
        session["obs_since_comment"] = int(session.get("obs_since_comment", 0)) + 1
        # Fold the oldest observations into a compact running summary (no extra LLM call).
        if len(obs) > 10:
            folded = " / ".join(obs[:5])
            session["summary"] = (str(session.get("summary", "")) + " " + folded).strip()[-500:]
            session["observations"] = obs[-5:]

    def _cowatch_comment(self, media: str, title: str) -> None:
        """One short, in-character co-watching comment. Uses vision to read what's on
        screen (plot/subtitles) when screenshot reactions are on; else a cozy quip.
        Carries the running session context so comments stay continuous."""
        now = time.time()
        if self.bubble_text and now < float(getattr(self, "_bubble_protected_until", 0.0)):
            return
        if self.cfg.ai_reactions_enabled and self.cfg.screenshot_reactions_enabled and not self._thread_running(self.reaction_worker):
            self._pending_activity_note = {
                "kind": "cowatch",
                "media": media,
                "window": title[:80],
                "session": self._cowatch_session_context(),
                "hint": "You are co-watching this with the user. Read what's on screen (scene, action, subtitles) and make ONE short, quiet, in-character reaction that BUILDS ON your earlier comments this session (same show, continuous thoughts). Don't narrate everything; don't be annoying.",
                "tone_choices": ["cozy", "curious", "funny", "surprised", "sarcastic", "soft"],
            }
            self.request_ai_reaction("cowatch_screen_comment", force=True, use_vision=True)
        elif now - self._last_spoken_bubble_at > 20:
            line = banter.pick("screen", self._banter_context(), avoid=self.recent_pet_lines[-10:], mood=self._dominant_mood())
            if line:
                self.show_bubble(line, 7000, source="static")
                self.emoji_effect = "🍿"
                self.emoji_until = now + 6.0
                self._remember_pet_line(line)
                self._last_spoken_bubble_at = now

    def _maybe_scheduled_tv_break(self, now: float, active_moving: bool) -> bool:
        # At least one 30-second TV break every 5 minutes, unless Wally is in a critical action.
        if now < getattr(self, "_tv_break_until", 0):
            self._request_tv_break_comment("tv_break_continues")
            return True
        if now - getattr(self, "_last_tv_break_started_at", now) < 300:
            return False
        critical = {"clean", "go_bin", "chase_butterfly", "chase_eva", "fall", "parachute"}
        if active_moving and self.current_action in critical:
            return False
        return self._start_tv_break("scheduled_5_min_tv_break", force=True)

    def _maybe_variety_action(self, active_moving: bool) -> bool:
        if active_moving or time.time() < self.pause_until:
            return False
        if time.time() < self._next_playful_nudge_at:
            return False
        self._next_playful_nudge_at = time.time() + random.uniform(7, 14)
        # Internal life system chooses varied physical micro-activities so the LLM is not overburdened.
        weights = []
        debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        weights.extend([
            ("roam", 20 + int(self.moods.get("bored", 0) * 0.24)),
            ("inspect", 18 + int(self.moods.get("curious", 0) * 0.12)),
            ("sing", 12 + int(self.moods.get("playful", 0) * 0.08)),
            ("dance", 10 + int(self.moods.get("excited", 0) * 0.16)),
            ("watch_tv", 9 + int(self.moods.get("cozy", 0) * 0.22)),
            ("kick_ball", 54 + int(self.moods.get("playful", 0) * 0.38) + int(self.moods.get("bored", 0) * 0.18) + int(self.moods.get("naughty", 0) * 0.18)),
            ("wave", 7),
        ])
        if debris_count >= 4:
            weights.append(("clean", 8 + int(self.moods.get("irritated", 0) * 0.18)))
        if self.debris_overlay.butterfly_visible:
            weights.append(("chase_butterfly", 34 + int(self.moods.get("curious", 0) * 0.24) + int(self.moods.get("playful", 0) * 0.12)))
        total = sum(w for _, w in weights)
        pick = random.uniform(0, max(1, total))
        acc = 0.0
        choice = "roam"
        for name, weight in weights:
            acc += weight
            if pick <= acc:
                choice = name
                break
        if choice == "clean":
            return self._maybe_ocd_cleaning(debris_count, active_moving)
        if choice == "inspect":
            self._apply_reaction_action("inspect", 2, random.choice(["screen", "mouse", "random", "debris"]))
        elif choice == "watch_tv":
            self._apply_reaction_action("watch_tv", 2, "tv_sofa")
        elif choice == "chase_butterfly":
            self._apply_reaction_action("chase_butterfly", 2, "butterfly")
        elif choice == "kick_ball":
            self._apply_reaction_action("kick_ball", 2, "basketball")
        elif choice == "wave":
            self._apply_reaction_action("wave", 2, "current")
        else:
            self._apply_reaction_action(choice, 2, "random")
        return True

    def _choose_next_behavior(self) -> None:
        if self._thread_running(self.worker):
            return
        if self.is_dragging:
            return

        self.cfg = self.store.config()
        now = time.time()
        self._update_mood_model()
        self._wellbeing_tick()
        self._needs_tick()
        self._proactive_followup_tick()
        debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        active_moving = self.current_action in {"clean", "go_bin", "chase_butterfly", "chase_eva", "watch_tv", "move_to", "kick_ball", "inspect_mouse", "kick_ball"} and self.target_point is not None

        # Do not let TV breaks, cleaning, roaming, or random goals steal the EVA chase.
        if self.debris_overlay.eva_visible and self.current_action == "chase_eva":
            self.target_point = self._eva_target_point()
            return

        # Co-watch takes priority over cleaning/roaming/tantrums so video time stays calm.
        if self._maybe_cowatch(now, active_moving):
            return

        if self._maybe_scheduled_tv_break(now, active_moving):
            return

        # A living cleaner: visible mess creates an urge to clean even when the LLM is being poetic.
        if self._maybe_ocd_cleaning(debris_count, active_moving):
            return
        if self._maybe_tantrum(debris_count, active_moving):
            return
        if self._maybe_mood_swing_activity(debris_count, active_moving):
            return

        # Rare attention-mischief: about one check every 10 minutes, 33% chance.
        if (not active_moving and now - self._last_attention_throw_check_at > 600):
            self._last_attention_throw_check_at = now
            if random.random() < 0.33:
                self._apply_reaction_action("throw_trash", 2, "screen", allow_attention_throw=True)
                return

        if self._maybe_variety_action(active_moving):
            return
        if (not active_moving and self.current_action in {"chill", "pause", "watch"} and
                now - self._last_auto_ball_play_at > random.uniform(28, 50) and
                time.time() > self.pause_until + 1):
            self._last_auto_ball_play_at = now
            self._apply_reaction_action("kick_ball", 2, "basketball")
            return
        if not active_moving and self.current_action == "chill" and random.random() < 0.125 and time.time() > self.pause_until + 1:
            self._apply_reaction_action("kick_ball", 2, "basketball")
            return

        # Softer LLM brain ticks for speech, mood, body, and occasional override.
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker) and now - self.last_ai_request_at > 15.0:
            reason = "ambient_life_mood_tick"
            if active_moving:
                reason = "active_goal_status_mood_comment"
            elif debris_count >= 6:
                reason = "mess_visible_mood_choice"
            elif self.debris_overlay.butterfly_visible:
                reason = "butterfly_visible_mood_choice"
            elif now - self._last_joke_fact_at > 45 and random.random() < 0.26:
                reason = "optional_context_joke_or_fun_fact"
                self._last_joke_fact_at = now
            self.request_ai_reaction(reason, use_vision=False)
            return

        if not self.bubble_text and self.current_action not in {"watch", "clean", "go_bin", "chase_butterfly"}:
            self.set_expression(random.choice(["happy", "curious", "sleepy", "watching"]))
        if self.cfg.roam_enabled and not active_moving and random.random() < 0.22:
            self.current_action = "move_to"
            self._choose_new_target()

    def _start_cleaning_behavior(self) -> None:
        center = self.frameGeometry().center()
        nearest = self.debris_overlay.nearest_item_global_to(center.x(), center.y())
        if nearest is None:
            return
        target = self._point_for_global_debris(nearest)
        self.cleaning_target = target
        self.target_point = target
        self.current_action = "clean"
        if not self._clean_batch_started_at:
            self._clean_batch_started_at = time.time()
        self.set_expression("cleaning")
        self._nudge_mood(curious=2, irritated=-2, bored=-4)
        now = time.time()
        if not self.ai_online and now - self._last_clean_bubble_at > 18:
            self.show_bubble(random.choice(["Tiny cleanup mission!", "Leaf patrol! 🌿"]), 2600)
            self._last_clean_bubble_at = now

    def _point_for_global_debris(self, debris_point: QPoint) -> QPoint:
        lane, orientation = self._taskbar_lane()
        if orientation in {"bottom", "top", "unknown"}:
            return self._clamp_to_lane(QPoint(debris_point.x() - self.width() // 2, self.y()))
        return self._clamp_to_lane(QPoint(self.x(), debris_point.y() - self.height() // 2))

    def _choose_new_target(self) -> None:
        if self.cfg.taskbar_only:
            lane, orientation = self._taskbar_lane()
            if lane.isNull():
                return
            margin = 10
            if orientation in {"bottom", "top", "unknown"}:
                min_x = lane.left() + margin
                max_x = max(min_x, lane.right() - self.width() - margin)
                x = random.randint(min_x, max_x)
                y = self._lane_y(lane, orientation)
            else:
                min_y = lane.top() + margin
                max_y = max(min_y, lane.bottom() - self.height() - margin)
                y = random.randint(min_y, max_y)
                x = self._lane_x(lane, orientation)
            self.target_point = QPoint(x, y)
            return

        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        margin = 20
        x = random.randint(geo.left() + margin, max(geo.left() + margin, geo.right() - self.width() - margin))
        y = random.randint(geo.top() + margin, max(geo.top() + margin, geo.bottom() - self.height() - margin))
        self.target_point = QPoint(x, y)

    def _roam_step(self) -> None:
        if getattr(self, "_resume_after_ball_kick", None) is not None and time.time() >= self.pause_until:
            self._resume_goal_after_ball_kick()
        if self.cfg.taskbar_only:
            snapped = self._clamp_to_lane(self.pos())
            if (abs(snapped.x() - self.x()) > 2 or abs(snapped.y() - self.y()) > 2) and not self.is_dragging:
                self.move(snapped)

        # EVA chase lock: when EVA is visible, Wally keeps chasing until she leaves.
        if self.debris_overlay.eva_visible and (self.current_action == "chase_eva" or time.time() < getattr(self, "_eva_chase_lock_until", 0.0)):
            self.current_action = "chase_eva"
            self.pause_until = 0.0
            self.target_point = self._eva_target_point()
            self.set_expression("love")
            self._apply_body_controls({"antenna": "heart", "eyes": "up", "eyebrow": "love", "emoji": "💛", "left_arm": "cheer", "right_arm": "wave"})
            if time.time() - getattr(self, "_eva_last_call_at", 0.0) > 6.5:
                self._eva_last_call_at = time.time()
                self.show_bubble(random.choice(["EVAAA! 💛", "Wait for me!", "Tiny heart sprint!", "EVA, look! 💛"]), 5200, source="static")

        moving_actions = {"clean", "go_bin", "chase_butterfly", "chase_eva", "inspect_mouse", "watch_tv", "move_to", "kick_ball"}
        still_actions = {"talk_to_user", "listen", "nap", "recharge", "investigate", "watch", "pause", "chill"}
        if time.time() < self.pause_until and self.current_action not in moving_actions:
            return
        if self.current_action in still_actions and self.target_point is None:
            return

        if self.current_action == "chase_butterfly" and self.debris_overlay.butterfly_visible:
            target = self._butterfly_target_point()
            if target is not None:
                self.target_point = target
        elif self.current_action == "chase_eva":
            target = self._eva_target_point()
            if target is not None:
                self.target_point = target
            elif time.time() > self._eva_sad_until:
                self._start_eva_miss_mood()
                return
        elif self.current_action == "inspect_mouse":
            if self.tick % 9 == 0:
                self.target_point = self._mouse_target_point()
        elif self.current_action == "go_bin" and self.target_point is None:
            self.target_point = self._bin_target_point()
        elif self.current_action == "watch_tv" and self.target_point is None:
            self.target_point = self._tv_target_point()
        elif self.current_action == "kick_ball":
            target = self._ball_target_point()
            if target is not None:
                self.target_point = target
        elif self.current_action == "clean" and self.target_point is None:
            self._start_cleaning_behavior()

        if self.target_point is None:
            now = time.time()
            if self.ai_online and self.cfg.ai_reactions_enabled:
                # If the model keeps choosing non-moving states, ask for a movement goal instead of freezing at one edge.
                if now - self._last_forced_goal_at > 18 and not self._thread_running(self.reaction_worker):
                    self._last_forced_goal_at = now
                    self.request_ai_reaction("stuck_no_target_choose_physical_goal", use_vision=False)
                return
            self._choose_new_target()
            return
        pos = self.pos()
        dx = self.target_point.x() - pos.x()
        dy = self.target_point.y() - pos.y()
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < 4:
            if self.current_action == "clean":
                removed_now = self._clear_debris_under_pet(extra_radius=72, incidental=False)
                if removed_now:
                    self.set_expression("proud")
                    return
                elif self.debris_overlay.item_count() > 0:
                    self.set_expression("thinking")
                    self._apply_body_controls({"eyes": "debris", "eyebrow": "curious", "emoji": "🔍", "left_arm": "point"})
                    self._start_cleaning_behavior()
                    return
                if self.carrying_debris > 0:
                    self._apply_reaction_action("go_bin", 2)
                    return
                self.current_action = "chill"
            elif self.current_action == "go_bin":
                dumped = self.carrying_debris
                if dumped > 0 and not self.ai_online:
                    self.show_bubble("Tiny bin feast complete.", 2200)
                self._remember_action("dumped_debris", {"count": dumped})
                self._last_dump_at = time.time()
                self._clean_batch_started_at = 0.0
                self._nudge_mood(proud=10 + dumped, irritated=-8, frustrated=-7, playful=6, bored=-5, curious=3)
                self.carrying_debris = 0
                self.set_expression("proud")
                self._apply_body_controls({"antenna": "wiggle", "eyes": "user", "eyebrow": "happy", "emoji": random.choice(["✨", "🌟", "🫡", "♻️"]), "left_arm": "cheer", "right_arm": "cheer"})
                self.current_action = "chill"
                self.pause_until = time.time() + 2.2
                # After dumping, deliberately diversify. Do not immediately restart bin-duty unless mess is severe.
                self._next_playful_nudge_at = time.time() + random.uniform(2.0, 5.0)
                self.goal_lock_until = time.time() + 4.0
                if dumped > 0 and self.cfg.ai_reactions_enabled and time.time() - self.last_ai_request_at > 15:
                    self.request_ai_reaction("debris_dumped_now_pick_a_non_trash_moment", use_vision=False)
            elif self.current_action == "watch_tv":
                self._begin_tv_break(self._tv_break_reason or "tv_break")
            elif self.current_action == "chase_butterfly":
                self.debris_overlay.scare_butterfly()
                self.set_expression("excited")
                self.current_action = "pause"
                self.pause_until = time.time() + random.uniform(2.5, 5.0)
                self._remember_event("caught_up_to_butterfly", text="butterfly chase", data={"did": "caught_butterfly_moment", "butterfly": self.debris_overlay.butterfly_status()})
                self._nudge_mood(proud=12, excited=10, playful=8, bored=-12)
                self._satisfy_need("play", 12, react=False)
                if time.time() < getattr(self, "_eva_recovery_until", 0.0):
                    self._eva_recovery_until = 0.0
                    self._nudge_mood(playful=12, excited=8, frustrated=-10, anxious=-5, curious=6)
                    self.show_bubble("Flutter therapy worked.", 6200, source="static")
                else:
                    self._instant_event_quip("butterfly_caught")
                if self._resume_after_butterfly_chase is not None:
                    QTimer.singleShot(int(max(900, (self.pause_until - time.time()) * 1000 + 300)), self._resume_goal_after_butterfly_chase)
                if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
                    if time.time() - self._last_butterfly_event_llm_at > 8 and random.random() < 0.60:
                        self._last_butterfly_event_llm_at = time.time()
                        self._pending_activity_note = {"kind": "caught_up_to_butterfly", "butterfly": self.debris_overlay.butterfly_status(), "tone_choices": ["excited", "funny", "proud", "curious"]}
                        self.request_ai_reaction("caught_up_to_butterfly", use_vision=False)
            elif self.current_action == "chase_eva":
                if self.debris_overlay.eva_visible:
                    target = self._eva_target_point()
                    if target is not None:
                        self.target_point = target
                        return
                self._start_eva_miss_mood()
            elif self.current_action == "inspect_mouse":
                self.set_expression("curious")
                self.current_action = "watch"
                self.pause_until = time.time() + 6
                self.debris_overlay.set_tv_mode(random.choice(["movie", "stars", "calm", "hearts"]))
            elif self.current_action == "kick_ball":
                reason = getattr(self, "_pending_ball_kick_reason", "planned_kick")
                self._pending_ball_kick_reason = "planned_kick"
                self._perform_ball_kick(reason)
            elif self.current_action == "move_to":
                self.current_action = "chill"
            self.target_point = None
            return
        base_speed = 1.25 if self.cfg.taskbar_only else 2.0
        if self.current_action == "clean":
            base_speed = 2.1
        elif self.current_action == "chase_butterfly":
            base_speed = 2.9
        elif self.current_action == "chase_eva":
            eva_mult = max(1.0, min(4.0, self.cfg.eva_speed_percent / 100.0))
            base_speed = min(13.8, 6.8 + eva_mult * 1.9)
        elif self.current_action == "inspect_mouse":
            base_speed = 1.7
        elif self.current_action == "kick_ball":
            base_speed = 2.35
        elif self.expression in {"scared", "excited"}:
            base_speed = 2.4
        step = min(base_speed, distance)
        new_x = int(pos.x() + dx / distance * step)
        new_y = int(pos.y() + dy / distance * step)
        self.move(new_x, new_y)
        if self.cfg.weather_enabled and hasattr(self.debris_overlay, "add_mud_trail_global") and self.current_action not in {"chase_eva", "fall", "parachute"}:
            frame = self.frameGeometry()
            self.debris_overlay.add_mud_trail_global(frame.center().x(), frame.bottom())
        if abs(dx) > 1:
            self._facing_left = dx < 0
        # Watchdog: if a target exists but we are barely moving, refresh the target soon.
        if self.tick % 45 == 0:
            now = time.time()
            last = self._last_movement_pos
            moved = abs(last.x() - self.x()) + abs(last.y() - self.y())
            if moved < 3 and self.current_action in {"clean", "go_bin", "chase_butterfly", "chase_eva", "watch_tv", "move_to", "kick_ball"} and now - self._last_movement_check_at > 3:
                if self.current_action == "clean":
                    self._start_cleaning_behavior()
                elif self.current_action == "chase_butterfly":
                    self.target_point = self._butterfly_target_point()
                elif self.current_action == "chase_eva":
                    self.target_point = self._eva_target_point()
                elif self.current_action == "go_bin":
                    self.target_point = self._bin_target_point()
                elif self.current_action == "watch_tv":
                    self.target_point = self._tv_target_point()
                elif self.current_action == "kick_ball":
                    self.target_point = self._ball_target_point()
                elif self.current_action == "move_to":
                    self._choose_new_target()
            self._last_movement_pos = QPoint(self.x(), self.y())
            self._last_movement_check_at = now

    def _trash_capacity_now(self) -> int:
        # Small rover, small belly. A stable capacity prevents the old collect-one-then-bin loop.
        return max(4, int(getattr(self, "trash_capacity", 6)))

    def _should_dump_now(self) -> bool:
        debris_left = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        carry = int(self.carrying_debris)
        cap = self._trash_capacity_now()
        if carry <= 0:
            return False
        if carry >= cap:
            return True
        # If the floor is clear, do not carry one lonely scrap forever.
        if debris_left == 0:
            return True
        # If a cleanup batch has been going on for a while, dump a partial load.
        if self._clean_batch_started_at and time.time() - self._clean_batch_started_at > 28 and carry >= max(2, cap // 2):
            return True
        return False

    def _continue_cleaning_or_dump(self) -> None:
        debris_left = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        if self._should_dump_now():
            self.current_goal = "dump collected scraps"
            self.goal_lock_until = time.time() + 8.0
            self._apply_reaction_action("go_bin", 2)
            return
        if debris_left > 0:
            # Keep collecting until capacity instead of running back to the bin after every speck.
            self.current_goal = f"collect batch {self.carrying_debris}/{self._trash_capacity_now()}"
            self.goal_lock_until = time.time() + 8.0
            self._start_cleaning_behavior()
            return
        self.current_action = "chill"
        self.target_point = None

    def _clear_debris_under_pet(self, extra_radius: int = 48, incidental: bool = False) -> int:
        if not self.cfg.debris_enabled:
            return 0
        geom = self.frameGeometry()
        base_x = geom.center().x()
        floor_y = geom.bottom()
        tread_left = geom.left() + max(4, int(self.width() * 0.08))
        tread_right = geom.right() - max(4, int(self.width() * 0.06))
        removed = 0
        if hasattr(self.debris_overlay, "clear_footprint_global"):
            removed = self.debris_overlay.clear_footprint_global(
                tread_left,
                tread_right,
                floor_y,
                x_margin=max(18, int(self.width() * 0.16)),
                y_margin=max(92, int(self.height() * 1.05)),
            )
        if not removed:
            base_y = floor_y - max(2, int(self.height() * 0.04))
            removed = self.debris_overlay.clear_near_global(base_x, base_y, radius=extra_radius + max(34, int(self.width() * 0.42)))
        if removed:
            self._last_successful_clean_at = time.time()
            self._clean_attempts_without_pickup = 0
            self.carrying_debris += removed
            self._remember_action("collected_debris", {"count": removed, "carrying": self.carrying_debris, "incidental": incidental})
            # Cleaning is satisfying, but do not let it erase all other moods.
            self._nudge_mood(proud=8 + removed, irritated=-5 - removed, frustrated=-4, bored=-3, playful=3, excited=2)
            self.set_expression("proud" if not incidental else "curious")
            self._apply_body_controls({"antenna": "perked", "eyes": "debris" if not incidental else "side", "eyebrow": "happy", "emoji": random.choice(["✨", "🫧", "♻️", "🧹"]), "left_arm": "hold", "right_arm": "hold"})
            if incidental:
                self._last_incidental_pickup_at = time.time()
                # Only redirect incidental pickup when the belly is full and the current activity is not a special play/chase moment.
                if self.carrying_debris >= self._trash_capacity_now() and self.current_action not in {"chase_butterfly", "watch_tv"}:
                    self._apply_reaction_action("go_bin", 2)
            else:
                self._continue_cleaning_or_dump()
        elif self.current_action == "clean":
            self._clean_attempts_without_pickup += 1
            if self._clean_attempts_without_pickup >= 5:
                self._clean_attempts_without_pickup = 0
                if self._should_dump_now():
                    self._apply_reaction_action("go_bin", 2)
                else:
                    self._start_cleaning_behavior()
        return removed

    def _activity_event_bucket(self, event_kind: str) -> str:
        if event_kind.startswith("typing"):
            return "typing"
        if event_kind in {"window_changed"}:
            return "window"
        if "mouse" in event_kind or event_kind in {"fast_mouse"}:
            return "mouse"
        if event_kind in {"scrolling"}:
            return "scroll"
        if event_kind in {"idle"}:
            return "idle"
        return "other"

    def _should_react_to_activity_event(self, event_kind: str, can_call: bool) -> bool:
        """Gently lively: more present than silent, still not chatty."""
        bucket = self._activity_event_bucket(event_kind)
        policy = {
            "typing": (4, 0.30),
            "window": (4, 0.38),
            "mouse": (5, 0.22),
            "scroll": (4, 0.26),
            "idle": (6, 0.18),
            "other": (5, 0.20),
        }
        window, base_probability = policy.get(bucket, (5, 0.20))
        count = int(self._event_reaction_counters.get(bucket, 0)) + 1
        forced = count >= window
        chosen = forced or random.random() < base_probability
        if chosen and can_call:
            self._event_reaction_counters[bucket] = 0
            return True
        # If it wanted to react but could not call, keep it near threshold.
        self._event_reaction_counters[bucket] = min(count, (window - 1) if chosen else count)
        return False

    def _update_workload_trash(self, keys: int, scrolls: int, words: int, typed_excerpt: str, current_window: str, now: float) -> Optional[Dict[str, object]]:
        """Turn sustained typing into visible mess and occasional cute overload tantrum."""
        if not self.cfg.work_trash_enabled or not self.cfg.debris_enabled or getattr(self, "_cowatch_active", False):
            # Still decay the pressure when the feature is off or during co-watch.
            self.work_pressure = max(0.0, self.work_pressure - 0.45)
            self._work_burst_keys = 0
            return None

        # Typing and scrolling slowly raise pressure; quiet moments release it.
        words = max(0, int(words))
        if keys > 0 or scrolls > 0 or words > 0:
            self.work_pressure = min(100.0, self.work_pressure + keys * 0.42 + words * 1.9 + scrolls * 1.15)
            self._work_burst_keys += keys
            self._work_words_since_pile += words
        else:
            self.work_pressure = max(0.0, self.work_pressure - 0.75)
            self._work_burst_keys = max(0, self._work_burst_keys - 2)

        debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        spawned = 0
        # Every 100 typed words causes one flying pile, in addition to the ambient 45-90s wind pile rule.
        while self._work_words_since_pile >= 100 and debris_count < 92:
            self._work_words_since_pile -= 100
            pile_count = random.randint(8, 14)
            self.debris_overlay.summon_wind_pile(pile_count)
            spawned += pile_count
            debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else debris_count + pile_count
            self._last_work_trash_at = now
            self._nudge_mood(irritated=5.0, frustrated=3.0, anxious=1.0, proud=-1.0)
            self._remember_event(
                "hundred_words_trash_pile",
                text=typed_excerpt[-90:] if typed_excerpt else "100 words typed",
                data={"did": "spawn_word_pile", "words_trigger": 100, "spawned": pile_count, "work_pressure": round(self.work_pressure, 1),
            "words_since_last_tick": words, "window": current_window[:80]},
            )

        # Small light mess still appears during hard bursts, but the main pile trigger is every 100 words.
        if keys >= 18 and now - self._last_work_trash_at > 5.0 and debris_count < 88:
            burst_spawned = max(1, min(5, keys // 12 + int(self.work_pressure // 42)))
            self.debris_overlay.summon_work_debris(burst_spawned, pressure=self.work_pressure)
            spawned += burst_spawned
            self._last_work_trash_at = now
            self._nudge_mood(irritated=0.45 * burst_spawned, frustrated=0.25 * burst_spawned, anxious=0.12 * burst_spawned, proud=-0.15 * burst_spawned)
            self._remember_event(
                "work_typing_created_mess",
                text=typed_excerpt[-90:] if typed_excerpt else "typing pressure",
                data={"did": "spawn_work_debris", "keys": keys, "words": words, "spawned": burst_spawned, "work_pressure": round(self.work_pressure, 1), "window": current_window[:80]},
            )

        debris_count = self.debris_overlay.item_count() if self.cfg.debris_enabled else 0
        debris_threshold = 58
        overload = self.work_pressure >= 86 or debris_count >= debris_threshold or (debris_count >= 42 and self.work_pressure >= 62)
        if overload and now - self._last_work_overload_at > 95:
            self._last_work_overload_at = now
            self._last_debris_threshold_tantrum_at = now
            burst = min(34, 14 + int(max(self.work_pressure, debris_count) // 6))
            self.debris_overlay.toss_attention_debris(burst)
            self.attention_overlay.fling_from(self.frameGeometry().center(), count=min(30, burst))
            self.current_action = "pause"
            self.target_point = None
            self.pause_until = now + 7.0
            self.set_expression("angry")
            self._apply_body_controls({"antenna": "wiggle", "eyes": "user", "eyebrow": "angry", "emoji": "🗑️", "left_arm": "tired", "right_arm": "point"})
            self._play_tantrum_garbage_sound()
            self._nudge_mood(irritated=18, frustrated=14, anxious=6, playful=-8, cozy=-5)
            event = {
                "kind": "hard_work_trash_overload",
                "source": "workload_meter",
                "typed_excerpt": typed_excerpt[-120:],
                "window": current_window[:100],
                "keys": keys,
                "words": words,
                "debris_count": debris_count,
                "debris_threshold": debris_threshold,
                "trigger": "debris_threshold" if debris_count >= debris_threshold else "work_pressure",
                "work_pressure": round(self.work_pressure, 1),
                "purpose": "User is working hard; mess mirrors workload; Wally is tired of cleaning and wants a break.",
                "character_direction": "cute funny anger; ask for break; do not script exact line",
            }
            self._pending_activity_note = event
            self._activity_counts_for_reaction = {"key_count": keys, "scroll_count": scrolls, "typed_excerpt": typed_excerpt, "work_pressure": round(self.work_pressure, 1), "debris_count": debris_count}
            self._remember_event("hard_work_trash_overload", text=typed_excerpt[-90:] if typed_excerpt else "work overload", data={"did": "throw_overload_trash", "work_pressure": round(self.work_pressure, 1), "debris_count": debris_count})
            if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
                self.request_ai_reaction("hard_work_trash_overload", force=True, use_vision=False)
            else:
                self.show_bubble(random.choice(["Slow down, trash wizard!", "Wally needs a break!", "Typing tornado detected!"]), 9000, source="static")
            return event

        return {"kind": "work_pressure_update", "work_pressure": round(self.work_pressure, 1), "spawned": spawned, "debris_count": debris_count} if spawned else None

    def _activity_tick(self) -> None:
        self.cfg = self.store.config()
        self.activity_monitor.set_enabled(self.cfg.screen_awareness_enabled)
        self.activity_monitor.poll_mouse()
        if not self.cfg.screen_awareness_enabled:
            return

        context_counts = self.activity_monitor.consume_counts()
        now = time.time()
        if self._thread_running(self.worker):
            return
        if self.is_dragging:
            return

        keys = int(context_counts.get("key_count", 0))
        clicks = int(context_counts.get("click_count", 0))
        words = int(context_counts.get("word_count", 0))
        scrolls = int(context_counts.get("scroll_count", 0))
        motion = float(context_counts.get("mouse_motion_score", 0.0))
        idle = float(context_counts.get("idle_seconds", 0.0))
        typed_excerpt = str(context_counts.get("typed_excerpt", "") or context_counts.get("recent_typed_excerpt", ""))[-120:]
        current_window = get_active_window_title()[:120]
        previous_window = self._last_seen_window_title
        window_changed = bool(current_window and previous_window and current_window != previous_window and now - self._last_window_event_at > 2.0)
        if current_window and current_window != previous_window:
            self._last_seen_window_title = current_window
            # Moving to a new app = new context. Drop the old typed buffer so he
            # doesn't keep riffing on what was typed in the previous window.
            with self.activity_monitor._lock:
                self.activity_monitor.typed_buffer = ""
                self.activity_monitor.last_typed_excerpt = ""
            # Quietly learn the user's habits (which apps, what time) so Wally grows
            # familiar over days and can reference patterns naturally.
            store = getattr(self, "memory_store", None)
            if store is not None:
                store.note_pattern(current_window, self._local_time_context().get("daypart", ""))

        workload_event = self._update_workload_trash(keys, scrolls, words, typed_excerpt, current_window, now)
        if workload_event and workload_event.get("kind") == "hard_work_trash_overload":
            return

        cursor = QCursor.pos()
        pet_rect = self.frameGeometry()
        cursor_near = pet_rect.adjusted(-100, -110, 100, 90).contains(cursor)
        cursor_above = abs(cursor.x() - pet_rect.center().x()) < max(70, self.width()) and pet_rect.top() - 100 < cursor.y() < pet_rect.top()

        event_kind = ""
        event_extra: Dict[str, object] = {}
        use_vision = False

        # Window switch is a first-class event. It does not always speak, but it can feed Ollama.
        if window_changed and now - self._last_activity_bubble_at > 2.5:
            event_kind = "window_changed"
            self._last_window_event_at = now
            event_extra = {"old_window": previous_window[:90], "new_window": current_window[:90]}
            self.set_expression("watching")
            self.eye_focus = "screen"
            self.eyebrow_pose = "curious"
            use_vision = True
        elif keys >= 4 and typed_excerpt and now - self._last_activity_bubble_at > 3.5:
            event_kind = "typing_activity"
            event_extra = {"typed_excerpt": typed_excerpt, "keys": keys, "words": words, "window": current_window[:90]}
            self.last_typing_reaction_excerpt = typed_excerpt
            self.set_expression("curious")
            self.eye_focus = "screen"
            self.eyebrow_pose = "focused"
        elif motion > 70 and cursor_near and now - self._last_dizzy_event_at > 18:
            event_kind = "mouse_zoomies_dizzy"
            self.dizzy_until = now + 4.5
            self._last_dizzy_event_at = now
            self.set_expression("dizzy")
            self._apply_body_controls({"antenna": "wiggle", "eyes": "mouse", "eyebrow": "dizzy", "emoji": "dizzy", "left_arm": "tired", "right_arm": "tired"})
        elif cursor_above and motion > 20 and now - self._last_mouse_lift_event_at > 18:
            event_kind = "mouse_hover_lifted_above_pet"
            self._last_mouse_lift_event_at = now
            self.set_expression("surprised")
            self._apply_body_controls({"antenna": "perked", "eyes": "up", "eyebrow": "surprised", "emoji": "question", "left_arm": "point"})
        elif clicks >= 2 and cursor_near and now - self._last_activity_bubble_at > 8:
            event_kind = "mouse_clicking"
            event_extra = {"click_count": clicks, "window": current_window[:90]}
            self.set_expression("watching")
            self.eye_focus = "mouse"
            self.eyebrow_pose = "curious"
        elif scrolls >= 3 and now - self._last_activity_bubble_at > 7:
            event_kind = "scrolling"
            event_extra = {"scroll_count": scrolls, "window": current_window[:90]}
            self.set_expression("surprised")
            self.eye_focus = "screen"
            self.eyebrow_pose = "curious"
        elif motion > 60 and now - self._last_activity_bubble_at > 10:
            event_kind = "fast_mouse"
            self.set_expression("excited")
            self.eye_focus = "mouse"
            self.eyebrow_pose = "curious"
        elif idle > 420 and not self.bubble_text and now - self._last_activity_bubble_at > 20:
            event_kind = "idle"
            self.set_expression("sleepy")
            self.eyebrow_pose = "sleepy"

        if not event_kind:
            return

        self._event_reaction_seen += 1
        event_bucket = self._activity_event_bucket(event_kind)

        self._pending_activity_note = {
            "kind": event_kind,
            "source": "event_monitor",
            "counts": context_counts,
            "details": event_extra,
            "window": current_window[:100],
            "cursor_near_pet": cursor_near,
            "cursor_above_pet": cursor_above,
            "time": round(now, 2),
            "react_probability": "at_least_1_in_5_per_event_type_when_ollama_available",
            "event_bucket": event_bucket,
            "tone_options": ["sarcastic", "funny", "supportive", "curious", "excited", "naughty"],
            "work_pressure": round(self.work_pressure, 1),
            "workload_note": "Typing can create trash; high pressure means Wally may be tired, annoyed, and wants a break.",
            "hint": "React only if worthwhile. Use typed/window/screen/workload context. Write a complete sentence within configured word limit; never truncate.",
        }
        # Do not consume this again inside _build_brain_context; pass the same event counts through.
        self._activity_counts_for_reaction = dict(context_counts)
        self._last_activity_bubble_at = now

        can_call = (
            self.cfg.ai_reactions_enabled
            and not self._thread_running(self.reaction_worker)
            and now - self.last_ai_request_at > 3.5
        )

        situation_map = {
            "window_changed": "window_hopping",
            "scrolling": "screen",
            "idle": "idle",
        }
        if event_kind.startswith("typing"):
            situation = "rapid_typing"
        elif "dizzy" in event_kind or event_kind == "fast_mouse" or "lifted" in event_kind:
            situation = "playful"
        else:
            situation = situation_map.get(event_kind, "ambient")

        going_to_llm = self._should_react_to_activity_event(event_kind, can_call)

        # Two-beat reaction: an instant in-character static opener for immediate feedback,
        # then (when chosen) the LLM follows with a fresh, dynamic, witty line that
        # *upgrades* the static bubble (ollama > static in show_bubble priority). The
        # static line is only the opener, never the whole personality.
        last_quip = float(getattr(self, "_last_instant_quip_at", 0.0))
        if going_to_llm:
            should_quip = now - last_quip > 6.0          # opener before the dynamic line
        elif self.ai_online:
            should_quip = (now - last_quip > 18.0) and random.random() < 0.22
        else:
            should_quip = now - last_quip > 9.0
        if should_quip:
            mood = self._dominant_mood()
            line = banter.pick(situation, self._banter_context(), avoid=self.recent_pet_lines[-10:], mood=mood)
            if line:
                self.show_bubble(line, 6500, source="static")
                self._set_banter_emoji(situation, mood)
                self._remember_pet_line(line)
                self._last_instant_quip_at = now

        if going_to_llm:
            self._event_reaction_used += 1
            self.request_ai_reaction(f"event_{event_kind}", use_vision=use_vision)

    def _local_time_context(self) -> Dict[str, object]:
        now_dt = datetime.now()
        hour = now_dt.hour
        if 5 <= hour < 11:
            daypart = "morning"
        elif 11 <= hour < 14:
            daypart = "lunch_time"
        elif 14 <= hour < 17:
            daypart = "afternoon"
        elif 17 <= hour < 21:
            daypart = "evening"
        else:
            daypart = "late_night"
        return {
            "time": now_dt.strftime("%H:%M"),
            "weekday": now_dt.strftime("%A"),
            "daypart": daypart,
            "break_hint": "break_or_lunch_comment_allowed" if daypart in {"morning", "lunch_time", "afternoon", "evening", "late_night"} else "none",
        }

    def _life_memory_context(self) -> Dict[str, object]:
        # Compact always-under-budget memory for the small local model.
        # It explicitly separates what Wally said from what Wally did.
        recent_events = []
        for event in self.action_memory[-10:]:
            if isinstance(event, dict):
                compact = {k: event.get(k) for k in ("at", "kind", "said", "did", "action", "target", "goal", "text") if k in event}
                if compact:
                    recent_events.append(compact)
        recent_lines = [str(x)[:70] for x in self.recent_pet_lines[-7:]]
        recent_chat = []
        for item in self.chat_history[-4:]:
            if isinstance(item, dict):
                role = item.get("role")
                key = "user_said" if role == "user" else "rivet_said"
                recent_chat.append({"at": datetime.now().strftime("%H:%M"), key: shorten_for_bubble(str(item.get("content", "")), max_len=70)})
        store = getattr(self, "memory_store", None)
        relationship = store.relationship_context() if store is not None else {}
        running_gags = store.get_gags()[-6:] if store is not None else []
        conversation_highlights = store.conversation_highlights() if store is not None else []
        return {
            "timeline": recent_events[-10:],
            "recent_rivet_said": recent_lines,
            "recent_chat": recent_chat,
            "conversation_highlights": conversation_highlights,
            "conversation_note": "Past chats with this user. Reference them naturally to build rapport and call back to earlier topics.",
            "watch_history": store.get_watch_history() if store is not None else [],
            "watch_history_note": "Shows/videos you co-watched together before. Call back to them naturally ('that show from earlier?').",
            "relationship": relationship,
            "relationship_note": "Long-term bond with this user; reference it naturally when it fits, never robotically.",
            "running_gags": running_gags,
            "running_gags_note": "Wally's own past memorable lines. Occasionally call back to one for an inside-joke feel.",
            "bond_tone": {
                "just_met": "a little shy and curious, light teasing",
                "warming_up": "friendlier, more teasing, starting inside jokes",
                "friends": "comfortable, playful roasts, callbacks",
                "close_friends": "warm best-friend energy, lots of callbacks and inside jokes",
                "inseparable": "old-soul companion who knows the user deeply",
            }.get(str(relationship.get("bond_stage", "")), "friendly"),
            "current_goal": self.current_goal[:48],
            "last_action_done": self.current_action,
            "play_quotas": {
                "ball_cross_seen_in_10": self._ball_cross_window_seen,
                "ball_cross_kicks_in_10": self._ball_cross_window_kicks,
                "ball_contact_zone_active": bool(getattr(self, "_ball_contact_zone_active", False)),
                "ball_resume_pending": bool(getattr(self, "_resume_after_ball_kick", None)),
                "ball_kicks_in_30": self._ball_kick_window_seen,
                "super_ball_done_in_30": self._ball_super_done_in_window,
                "butterfly_seen_in_10": self._butterfly_window_seen,
                "butterfly_chases_in_10": self._butterfly_window_chases,
                "butterfly_arrivals_seen_total": getattr(self, "_butterfly_arrival_seen", 0),
                "butterfly_arrival_chases_total": getattr(self, "_butterfly_arrival_chases", 0),
                "butterfly_chase_rule": "independent 40% chance on each visible butterfly arrival",
            },
        }

    def _inner_thought_prompt(self, reason: str) -> List[Dict[str, str]]:
        count = 3 if "ambient" in reason or "scheduled" in reason else 2
        picked = random.sample(RIVET_INNER_THOUGHTS, k=min(count, len(RIVET_INNER_THOUGHTS)))
        return [{
            "kind": "private_inner_thought_feed",
            "text": item,
            "not_world_fact": "true",
            "instruction": "Reflect privately. If useful, convert this into Wally's next action or short speech; do not quote it as an external event.",
        } for item in picked]

    def _compressed_life_context_json(self, reason: str, counts: Dict[str, object], title: str) -> str:
        pack = {
            "time": self._local_time_context(),
            "mood": self._mood_snapshot(),
            "top": self._top_moods(),
            "workload": {"pressure": round(self.work_pressure, 1), "debris": self.debris_overlay.item_count() if self.cfg.debris_enabled else 0, "meaning": "mess visually mirrors human workload"},
            "inner_thought_feed": self._inner_thought_prompt(reason),
            "inner_thought_policy": "These are Wally's private thought seeds. Reflect on them to choose actions like sing, joke, fact, ball, butterfly, clean, or rest.",
            "reality_rule": "inner_thoughts are Wally private self-prompts, not observations or third-party inputs",
            "memory": self._life_memory_context(),
            "activity": {
                "keys": counts.get("key_count", 0),
                "scroll": counts.get("scroll_count", 0),
                "typed": str(counts.get("typed_excerpt") or counts.get("recent_typed_excerpt") or "")[-110:],
                "idle": counts.get("idle_seconds", 0),
            },
            "screen": {
                "window": title[:80],
                "scene": infer_scene_guess(title, None),
                "media": infer_media_hint(title),
            },
        }
        raw = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        # Approx <800 tokens by character budget; tiny models behave better with this than long state dumps.
        return raw[:2800]

    def _build_brain_context(self, reason: str, include_screenshot: bool, consume_counts: bool) -> Dict[str, object]:
        if consume_counts:
            stashed_counts = getattr(self, "_activity_counts_for_reaction", None)
            if stashed_counts is not None:
                counts = dict(stashed_counts)
                self._activity_counts_for_reaction = None
            else:
                counts = self.activity_monitor.consume_counts()
        else:
            counts = {
                "key_count": 0,
                "scroll_count": 0,
                "recent_key_score": round(self.activity_monitor.recent_key_score, 1),
                "recent_scroll_score": round(self.activity_monitor.recent_scroll_score, 1),
                "mouse_motion_score": round(self.activity_monitor.motion_score, 2),
                "idle_seconds": round(max(0.0, time.time() - self.activity_monitor.last_input_time), 1),
                "typed_excerpt": getattr(self.activity_monitor, "last_typed_excerpt", "")[-100:],
                "recent_typed_excerpt": getattr(self.activity_monitor, "last_typed_excerpt", "")[-100:],
                "typing_context_note": "This is text the user is typing elsewhere, not speech to the pet.",
                "listener_error": self.activity_monitor.listener_error,
            }

        title = get_active_window_title()
        lane, orientation = self._taskbar_lane()
        pet_center = self.frameGeometry().center()
        cursor = QCursor.pos()
        nearest = self.debris_overlay.nearest_item_global_to(pet_center.x(), pet_center.y())
        bin_pt = self.debris_overlay.bin_point_global()
        tv_pt = self.debris_overlay.tv_spot_global()
        butterfly_pt = self.debris_overlay.butterfly_point_global()
        debris_summary = self.debris_overlay.debris_summary_global()
        cursor_rect = self.frameGeometry().adjusted(-80, -80, 80, 80)
        over_rect = self.frameGeometry().adjusted(-8, -8, 8, 8)
        above_pet = abs(cursor.x() - pet_center.x()) < max(70, self.width()) and self.frameGeometry().top() - 100 < cursor.y() < self.frameGeometry().top()
        recent_memory: List[object] = []
        for event in self.action_memory[-8:]:
            if isinstance(event, dict):
                recent_memory.append({k: event.get(k) for k in ("kind", "goal", "action", "target", "expression", "text", "bubble") if k in event})
        for item in self.chat_history[-4:]:
            if isinstance(item, dict):
                recent_memory.append({"chat": item.get("role"), "text": shorten_for_bubble(str(item.get("content", "")), max_len=80)})

        ctx: Dict[str, object] = {
            "r": reason,
            "goal": self.current_goal,
            "goal_age": round(time.time() - self.current_goal_started_at, 1),
            "goal_queue": self.goal_queue[-5:],
            "paused_goals": self.paused_goals[-3:],
            "goal_lock_seconds_left": round(max(0.0, self.goal_lock_until - time.time()), 1),
            "act": self.current_action,
            "expr": self.expression,
            "body": {
                "ant": self.antenna_pose,
                "eye": self.eye_focus,
                "brow": self.eyebrow_pose,
                "l": self.left_arm_pose,
                "r": self.right_arm_pose,
                "emo": self.emoji_effect if time.time() < self.emoji_until else "none",
            },
            "carry": self.carrying_debris,
            "capacity": self._trash_capacity_now(),
            "clean_batch_age": round(time.time() - self._clean_batch_started_at, 1) if self._clean_batch_started_at else 0,
            "world": {
                "lane": [lane.left(), lane.top(), lane.right(), lane.bottom(), orientation],
                "pet": [pet_center.x(), pet_center.y()],
                "mouse": [cursor.x(), cursor.y()],
                "mouse_near_pet": cursor_rect.contains(cursor),
                "mouse_over_pet": over_rect.contains(cursor),
                "mouse_above_pet": above_pet,
                "bin": [bin_pt.x(), bin_pt.y()],
                "tv": [tv_pt.x(), tv_pt.y()],
                "tree": [self.debris_overlay.tree_point_global().x(), self.debris_overlay.tree_point_global().y()],
                "debris_count": self.debris_overlay.item_count() if self.cfg.debris_enabled else 0,
                "debris": debris_summary,
                "nearest_debris": [nearest.x(), nearest.y()] if nearest else None,
                "butterfly": [butterfly_pt.x(), butterfly_pt.y()] if butterfly_pt else None,
                "butterfly_visible": bool(butterfly_pt),
                "eva": self.debris_overlay.eva_status() if hasattr(self.debris_overlay, "eva_status") else {"visible": False},
                "eva_recovery_seconds_left": round(max(0.0, getattr(self, "_eva_recovery_until", 0.0) - time.time()), 1),
                "basketball": self.debris_overlay.ball_status(),
                "weather": self.debris_overlay.weather_status() if hasattr(self.debris_overlay, "weather_status") else {"enabled": False},
                "tv_mode": getattr(self.debris_overlay, "tv_mode", "static"),
                "tv_break": {
                    "active": bool(time.time() < getattr(self, "_tv_break_until", 0)),
                    "seconds_left": round(max(0.0, getattr(self, "_tv_break_until", 0) - time.time()), 1),
                    "reason": getattr(self, "_tv_break_reason", ""),
                    "policy": "30 second TV break at least every 5 minutes; hum/comment in character",
                },
                "flight": {"mode": self.fall_mode, "height_px": int(self.fall_started_height)},
            },
            "activity": counts,
            "event_monitor": {
                "events_seen": self._event_reaction_seen,
                "events_sent_to_ollama": self._event_reaction_used,
                "policy": "send roughly 4 of every 10 typing/window/scroll/mouse events",
            },
            "workload_meter": {
                "pressure": round(self.work_pressure, 1),
                "typing_creates_trash": bool(self.cfg.work_trash_enabled),
                "debris_count": self.debris_overlay.item_count() if self.cfg.debris_enabled else 0,
                "purpose": "Visible mess mirrors how hard the user is working; at overload Wally gets tired, cute-mad, throws trash, and asks for a break.",
            },
            "pending_event": self._pending_activity_note or {},
            "user_instruction": self._pending_user_instruction[-220:],
            "last_user_instruction": self._last_user_instruction[-180:],
            "screen_question": self._last_screen_question[-180:],
            "window": title[:120],
            "typed_text": self._typed_text_payload(title, counts),
            "media": infer_media_hint(title),
            "scene": infer_scene_guess(title, None),
            "memory": recent_memory[-6:],
            "life_memory": self._life_memory_context(),
            "inner_thought_feed": self._inner_thought_prompt(reason),
            "inner_thought_policy": {
                "purpose": "private seed thoughts for Wally's next behavior",
                "use": "reflect and choose matching action/speech when appropriate",
                "examples": {"sing": "action sing", "joke": "short funny line", "fact": "tiny fact", "ball": "kick_ball", "butterfly": "chase only if visible"},
            },
            "reality_contract": {
                "inner_thoughts_are": "private self-prompts only",
                "real_facts_are_only": "world/activity/screen/user_instruction/memory",
                "do_not_invent": "no imaginary people stealing, moving, or touching objects",
                "if_talking_about_ball": "prefer kick_ball or look at basketball",
                "if_talking_about_butterfly": "only mention if butterfly_visible",
            },
            "time_context": self._local_time_context(),
            "user_wellbeing": {
                "state": getattr(self, "_last_wellbeing_state", "neutral"),
                "note": "How the user seems to be doing. Attune to it: support if stressed, gently nudge rest if late/tired, celebrate a good grind, stay light during flow. Care, don't nag.",
            },
            "cowatch": {
                "active": bool(getattr(self, "_cowatch_active", False)),
                "note": "You're cozily watching video together. Comment only occasionally and briefly, like a chill couch buddy reacting to the scene/subtitles. Never spam.",
            } if getattr(self, "_cowatch_active", False) else None,
            "needs": {
                "affection": int(self.needs.get("affection", 70)),
                "play": int(self.needs.get("play", 60)),
                "energy": int(self.needs.get("energy", 85)),
                "note": "Wally's own needs (0-100). If one is low, he may cutely ask to be petted, played with, or allowed to rest. When the user just met a need, show genuine gratitude.",
            },
            "tiny_agent_skills": self._tiny_agent_skill_context(),
            "compact_life_context_json": self._compressed_life_context_json(reason, counts, title),
            "mood": self._mood_snapshot(),
            "mood_top": self._top_moods(),
            "tiny_context_map": {
                "recent_window": title[:70],
                "recent_memory": recent_memory[-5:],
                "recent_pet_lines": self.recent_pet_lines[-8:],
                "avoid_repeating": self.recent_pet_lines[-10:],
                "carrying": self.carrying_debris,
                "same_action_streak": self._same_action_streak,
            },
            "creativity_policy": {
                "avoid_recent_phrases": self.recent_pet_lines[-10:],
                "mix_tone": ["naughty", "funny", "sarcastic", "encouraging", "curious"],
                "react_to_screen_when_interesting": True,
                "react_to_typing_only_if_interesting": True,
                "react_to_window_change_randomly": "about_4_in_10_events",
                "react_to_event_emotions": ["sarcastic", "funny", "supportive", "curious", "excited", "naughty"],
                "do_not_repeat_same_joke_or_comment": True,
            },
            "anime_seed": random.choice(["cozy forest spirit", "training arc", "pirate adventure", "spy family comedy", "pocket monster curiosity", "soot sprite mess", "mecha repair bay"]),
            "drive": {
                "core": "alive playful cleaner pet",
                "clean_urge": int(min(100, self.debris_overlay.item_count() * 12 + self.moods.get("irritated", 0) * 0.7 + self.moods.get("frustrated", 0) * 0.8)),
                "break_urge": int(min(100, self.work_pressure * 0.75 + self.moods.get("frustrated", 0) * 0.35)),
                "play_urge": int(min(100, self.moods.get("playful", 0) + self.moods.get("bored", 0) * 0.25)),
                "novelty_urge": int(min(100, self.moods.get("curious", 0) + self._same_action_streak * 6)),
            },
            "speech_max_words": int(self.cfg.speech_max_words),
            "speech_expectation": f"Usually include b as a complete sentence under {self.cfg.speech_max_words} words unless silence is clearly better. Do not rely on truncation.",
            "need": "Be grounded and alive. Inner thoughts are private prompts, not events. If mentioning an object, act on it. Use workload/trash/break meaning as character, not as scripted text. JSON only.",
        }
        # On ambient/idle ticks, hand the brain a concrete creative job so the inner
        # thoughts actually turn into a hummed tune, a joke, a tiny fact, a tease, or a
        # hype-up — instead of another flat status line. This is what makes the
        # 15-30s background ticks feel dynamic and alive.
        if any(tag in reason for tag in ("ambient", "scheduled", "startup", "joke", "fact", "caught_up")):
            ctx["creative_intent"] = random.choice([
                {"do": "sing", "how": "hum a short silly made-up tune about the current window, mess, or moment", "set_action": "sing"},
                {"do": "joke", "how": "one tiny original pun or joke about what's happening right now"},
                {"do": "fact", "how": "one surprising tiny fact, then a cheeky aside"},
                {"do": "tease", "how": "playfully roast the user's current activity, with love"},
                {"do": "observe", "how": "a sly, specific, witty observation about the screen or mess"},
                {"do": "hype", "how": "a short dramatic hype-up line for whatever they're doing"},
                {"do": "wonder", "how": "a tiny absurd existential thought, robot-flavored"},
                {"do": "callback", "how": "reference something from recent memory/chat in a funny way"},
                {"do": "quiet", "how": "maybe just a tiny chirp or stay silent if nothing is worth saying"},
            ])
        if include_screenshot:
            summary = self._screen_summary()
            signature = f"{summary.get('tone','?')}|{summary.get('brightness','?')}|{summary.get('dark_ratio','?')}|{summary.get('motion_delta','?')}|{title[:55]}"
            ctx["screen"] = summary
            ctx["screen_signature"] = signature
            ctx["last_screen_signature"] = self.last_screen_reaction_signature
            ctx["scene"] = infer_scene_guess(title, summary)
            ctx["img"] = "attached_to_local_ollama" if self.cfg.screenshot_reactions_enabled else "off"
            ctx["screen_reaction_note"] = "If the screen/content looks interesting, make a fresh tiny comment; otherwise body-only is fine."
        return ctx

    def _message_needs_screen(self, text: str) -> bool:
        t = text.lower()
        return any(phrase in t for phrase in [
            "what is on my screen", "what's on my screen", "what do you see", "look at my screen",
            "do you like", "like what's on", "like what is on", "this screen", "this video",
            "near this icon", "that icon", "this icon", "on screen", "screen?"
        ])

    def _message_is_action_command(self, text: str) -> bool:
        t = text.lower().strip()
        return any(word in t for word in [
            "go ", "collect", "clean", "trash", "bin", "dump", "watch tv", "sofa", "chase",
            "butterfly", "basketball", "ball", "kick", "inspect", "come here", "move", "dance", "nap", "throw", "icon", "sing", "song", "hum", "roam", "wander", "patrol"
        ])

    def request_ai_reaction(self, reason: str, force: bool = False, use_vision: Optional[bool] = None, user_instruction: str = "") -> None:
        if getattr(self, "_shutdown_in_progress", False):
            return
        self.cfg = self.store.config()
        if reason in {"scheduled_scene_check", "manual_screen_check"}:
            self._schedule_next_ai_reaction()
        if reason in {"ambient_character_tick", "startup_self_intro", "manual_ai_enabled"}:
            self._schedule_next_ambient_ai()
        # During co-watch, suppress generic chatter; co-watch owns the commentary.
        if getattr(self, "_cowatch_active", False) and reason in {"ambient_character_tick", "scheduled_scene_check"}:
            return
        if not self.cfg.ai_reactions_enabled and not force:
            return
        if self._thread_running(self.reaction_worker):
            if reason == "manual_screen_check":
                self._pending_manual_screen_check = True
                if time.time() - float(getattr(self, "_last_manual_screen_feedback_at", 0.0)) > 1.5:
                    self._last_manual_screen_feedback_at = time.time()
                    self.show_bubble("Finishing a thought, then checking the screen.", 2400, source="tool")
                return
            self._schedule_next_ambient_ai()
            return
        if self._thread_running(self.worker):
            if reason == "manual_screen_check":
                self._pending_manual_screen_check = True
                if time.time() - float(getattr(self, "_last_manual_screen_feedback_at", 0.0)) > 1.5:
                    self._last_manual_screen_feedback_at = time.time()
                    self.show_bubble("Let me finish chatting, then I’ll look.", 2400, source="tool")
                return
            self._schedule_next_ambient_ai()
            return

        include_screenshot = bool(self.cfg.screenshot_reactions_enabled) if use_vision is None else bool(use_vision)
        if reason != "manual_screen_check":
            include_screenshot = include_screenshot and bool(self.cfg.screenshot_reactions_enabled)
        if reason == "manual_screen_check" and not user_instruction:
            user_instruction = (
                "Look at the current screen and react to one specific visible thing. "
                "Be concrete, fresh, and meaningful, not generic."
            )
            self._last_screen_question = "manual screen check"
            self.show_bubble("Looking at the screen...", 2200, source="tool")
        if user_instruction:
            self._pending_user_instruction = user_instruction
            self._last_user_instruction = user_instruction
        context = self._build_brain_context(reason=reason, include_screenshot=include_screenshot, consume_counts=True)
        image_b64 = self._capture_screen_base64() if include_screenshot else None
        if reason == "manual_screen_check" and include_screenshot and not image_b64:
            self.show_bubble("I couldn't capture the screen, using local vibes instead.", 2800, source="error")
            self._apply_local_screen_reaction(reason)
            return
        context["vision_image_attached"] = bool(image_b64)
        context["ollama_request"] = {
            "model": self.cfg.model,
            "thinking_disabled": True,
            "vision_requested": include_screenshot,
            "control_mode": "ollama_decides_optional_action_goal_body_queue",
        }
        self._pending_activity_note = None
        self._reaction_reason_in_flight = reason
        self.last_ai_request_at = time.time()
        self.set_expression("watching" if include_screenshot else "thinking")
        if force and reason != "cowatch_observe":
            self.show_bubble("hmm!", 1800)
        self.reaction_worker = ReactionWorker(self.cfg, context, image_b64=image_b64)
        self.reaction_worker.finished_ok.connect(self._on_reaction_decision)
        self.reaction_worker.failed.connect(self._on_reaction_error)
        self.reaction_worker.finished.connect(self._reaction_worker_finished)
        self._track_thread(self.reaction_worker)
        self.reaction_worker.start()

    def _schedule_next_eva_flyby(self) -> None:
        if not hasattr(self, "eva_timer"):
            return
        self.eva_timer.start(random.randint(5 * 60_000, 8 * 60_000))

    def _eva_target_point(self) -> Optional[QPoint]:
        point = self.debris_overlay.eva_point_global()
        if point is None:
            return None
        # Wally runs along the taskbar under EVA, not into the air.
        # Target includes a small lead so he visibly sprints behind the zigzag.
        lead = 28 if getattr(self.debris_overlay, "eva_vx", 1.0) > 0 else -28
        return self._clamp_to_lane(QPoint(point.x() - self.width() // 2 - lead, self.y()))

    def _eva_flyby_event(self, force: bool = False) -> None:
        self._schedule_next_eva_flyby()
        # Don't pull him off the couch mid-show.
        if getattr(self, "_cowatch_active", False) and not force:
            return
        if self.debris_overlay.eva_visible and not force:
            return
        self.debris_overlay.summon_eva_flyby()
        self._eva_sound_token = int(getattr(self, "_eva_sound_token", 0)) + 1
        eva_sound_delay_ms = random.randint(2000, 3000)
        QTimer.singleShot(eva_sound_delay_ms, lambda token=self._eva_sound_token: self._play_eva_flyby_sound(token))
        self._eva_flyby_seen += 1
        self._eva_sad_until = 0.0
        self._eva_miss_started = False
        self._eva_chase_lock_until = time.time() + max(8.0, self.debris_overlay.eva_end_at - time.time() + 2.0)
        self._remember_event("eva_flyby_started", text="EVA flew by", data={"did": "notice_eva", "eva": self.debris_overlay.eva_status(), "flyby_index": self._eva_flyby_seen, "chase_lock_seconds": round(self._eva_chase_lock_until - time.time(), 1)})
        self.set_expression("love")
        self.current_action = "chase_eva"
        self.target_point = self._eva_target_point()
        self.pause_until = 0.0
        self._apply_body_controls({"antenna": "heart", "eyes": "up", "eyebrow": "love", "emoji": "💛", "left_arm": "cheer", "right_arm": "wave"})
        self._nudge_mood(excited=30, playful=18, bored=-25, cozy=8)
        eva_hello = banter.pick("eva_arrive", self._banter_context(), avoid=self.recent_pet_lines[-10:])
        self.show_bubble(eva_hello or "EVAAA! 💛", 6500, source="tool" if force else "static")
        self._remember_pet_line(eva_hello)
        self._last_event_quip_at = time.time()
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker) and time.time() - self._last_eva_event_llm_at > 8:
            self._last_eva_event_llm_at = time.time()
            self._pending_activity_note = {"kind": "eva_flyby", "eva": self.debris_overlay.eva_status(), "tone_choices": ["lovestruck", "excited", "funny", "dramatic"], "hint": "Wally is sprinting behind EVA and calling her name."}
            self.request_ai_reaction("eva_flyby_lovestruck_chase", use_vision=False)
        # If the overlay ends naturally, trigger the heartbreak routine.
        QTimer.singleShot(19000, self._check_eva_flyby_finished)

    def _check_eva_flyby_finished(self) -> None:
        if self.current_action == "chase_eva" and not self.debris_overlay.eva_visible and time.time() > self._eva_sad_until:
            self._start_eva_miss_mood()

    def _start_eva_miss_mood(self) -> None:
        if getattr(self, "_eva_miss_started", False):
            return
        self._eva_miss_started = True
        self._eva_chase_lock_until = 0.0
        self._eva_sad_until = time.time() + random.uniform(4.0, 10.0)
        self._eva_recovery_until = time.time() + 120.0
        self.current_action = "pause"
        self.target_point = None
        self.pause_until = self._eva_sad_until
        self.set_expression("soft")
        self._nudge_mood(cozy=-4, excited=-5, playful=-4, anxious=3, frustrated=5, curious=2)
        self._apply_body_controls({"antenna": "droop", "eyes": "side", "eyebrow": "sad", "emoji": "💛", "left_arm": "shy", "right_arm": "shy"})
        self._remember_event("eva_flyby_missed", text="EVA gone", data={"did": "feel_bad_after_eva", "sad_seconds": round(self._eva_sad_until - time.time(), 1)})
        if not self.bubble_text:
            sad_line = banter.pick("eva_left", self._banter_context(), avoid=self.recent_pet_lines[-10:])
            self.show_bubble(sad_line or "EVA gone...", 6500, source="static")
            self._remember_pet_line(sad_line)
        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker) and time.time() - self._last_eva_event_llm_at > 8:
            self._last_eva_event_llm_at = time.time()
            self._pending_activity_note = {"kind": "eva_left_wally_sad", "tone_choices": ["soft", "dramatic", "funny", "heartbroken"], "hint": "Wally missed EVA and is sad for a few seconds."}
            self.request_ai_reaction("eva_left_wally_sad", use_vision=False)
        QTimer.singleShot(int((self._eva_sad_until - time.time()) * 1000 + 200), self._eva_angry_ball_kick)

    def _eva_angry_ball_kick(self) -> None:
        if time.time() < self._eva_sad_until - 0.2:
            return
        self._remember_event("eva_sad_angry_ball_kick", text="sad kick", data={"did": "kick_ball_after_eva"})
        self.set_expression("frustrated")
        self._apply_body_controls({"antenna": "wiggle", "eyes": "basketball", "eyebrow": "frustrated", "emoji": "🏀", "left_arm": "cheer", "right_arm": "point"})
        self.current_action = "kick_ball"
        self._pending_ball_kick_reason = "eva_sad_angry_kick"
        self.target_point = self._ball_target_point()
        if self.target_point is None:
            self._perform_ball_kick("eva_sad_angry_kick")

    def _schedule_next_butterfly(self) -> None:
        if not hasattr(self, "butterfly_timer"):
            return
        # Butterfly is a pleasant visitor: frequent enough to notice, still not constant.
        interval_ms = random.randint(22_000, 38_000)
        self.butterfly_timer.start(interval_ms)

    def _butterfly_event(self, force: bool = False) -> None:
        self._schedule_next_butterfly()
        if not force and random.random() >= 0.88:
            self._remember_action("butterfly_skipped", {"reason": "rare_visit_chance"})
            return
        if self.debris_overlay.butterfly_visible and not force:
            return

        self.debris_overlay.summon_butterfly()
        self._butterfly_arrival_seen = int(getattr(self, "_butterfly_arrival_seen", 0)) + 1
        self._remember_event("butterfly_arrived", text="butterfly visible", data={"visible": True, "arrival_index": self._butterfly_arrival_seen})
        self._remember_action("butterfly_arrived", {"visible": True, "arrival_index": self._butterfly_arrival_seen})
        self.set_expression("curious")
        self._nudge_mood(curious=18, excited=12, playful=10, bored=-15)
        self._apply_body_controls({"eyes": "butterfly", "eyebrow": "curious", "emoji": "🦋", "antenna": "perked"})

        if not self.bubble_text or time.time() - self._last_butterfly_ack_at > 18:
            self._last_butterfly_ack_at = time.time()
            ack = banter.pick("butterfly_arrive", self._banter_context(), avoid=self.recent_pet_lines[-10:])
            self.show_bubble(ack or "Tiny wings incoming 🦋", 7600, source="static")
            self._remember_pet_line(ack)
            self._last_event_quip_at = time.time()

        # User clarified: this is a true per-arrival 40% chance, not "only on the 4th".
        critical_busy = self.current_action in {"clean", "go_bin", "chase_eva", "parachute", "fall", "listen", "talk_to_user"} and self.target_point is not None
        chase_roll = random.random()
        eva_recovery = time.time() < getattr(self, "_eva_recovery_until", 0.0)
        should_chase = bool(force or (eva_recovery and not critical_busy) or ((not critical_busy) and chase_roll < 0.40))
        if should_chase:
            self._butterfly_arrival_chases = int(getattr(self, "_butterfly_arrival_chases", 0)) + 1
            self._save_current_goal_for_butterfly_interrupt()
            self._remember_event("butterfly_chase_started", text="chasing butterfly", data={
                "did": "chase_butterfly",
                "probability": "40_percent_per_arrival",
                "roll": round(chase_roll, 3),
                "arrival_chases": self._butterfly_arrival_chases,
                "arrival_seen": self._butterfly_arrival_seen,
                "eva_recovery": bool(time.time() < getattr(self, "_eva_recovery_until", 0.0)),
            })
            self._instant_event_quip("butterfly_chase")
            self._apply_reaction_action("chase_butterfly", 2, "butterfly")
        else:
            self._remember_event("butterfly_not_chased", text="watched butterfly", data={
                "did": "notice_butterfly",
                "probability": "40_percent_per_arrival",
                "roll": round(chase_roll, 3),
                "critical_busy": critical_busy,
                "arrival_seen": self._butterfly_arrival_seen,
            })

        if self.cfg.ai_reactions_enabled and not self._thread_running(self.reaction_worker):
            should_comment = self._quota_should_act("_butterfly_event_llm_window_seen", "_butterfly_event_llm_window_sent", 5, 1, 0.35)
            if time.time() - self._last_butterfly_event_llm_at > 7 and should_comment:
                self._last_butterfly_event_llm_at = time.time()
                self._pending_activity_note = {
                    "kind": "butterfly_event",
                    "chasing": should_chase,
                    "butterfly": self.debris_overlay.butterfly_status(),
                    "tone_choices": ["excited", "curious", "funny", "naughty", "soft"],
                    "rule": "40% independent chance on each visible butterfly arrival; not every fourth event",
                    "roll": round(chase_roll, 3),
                    "arrival_seen": self._butterfly_arrival_seen,
                    "arrival_chases": self._butterfly_arrival_chases,
                }
                self.request_ai_reaction("butterfly_event_react", force=force, use_vision=False)

    def _schedule_next_ai_reaction(self) -> None:
        self.cfg = self.store.config()
        if not self.cfg.ai_reactions_enabled:
            self.ai_reaction_timer.stop()
            return
        # Always do a real screen-based reaction on a gentle random cadence.
        interval_ms = random.randint(60_000, 180_000)
        self.ai_reaction_timer.start(interval_ms)

    def _schedule_next_ambient_ai(self) -> None:
        self.cfg = self.store.config()
        if not self.cfg.ai_reactions_enabled:
            if hasattr(self, "ai_heartbeat_timer"):
                self.ai_heartbeat_timer.stop()
            return
        # Tiny background brain ticks: random 15-30 seconds to avoid Ollama overload.
        interval_ms = random.randint(15_000, 30_000)
        self.ai_heartbeat_timer.start(interval_ms)

    def _on_reaction_decision(self, decision: Dict[str, object]) -> None:
        was_offline = not self.ai_online
        self.ai_online = True
        self.last_ai_success_at = time.time()
        self.last_ai_error = ""
        self._schedule_next_ambient_ai()

        request_reason = self._reaction_reason_in_flight or ""
        self._reaction_reason_in_flight = ""

        # Silent co-watch observation: store it as context, never speak it.
        if request_reason == "cowatch_observe":
            note = str(decision.get("bubble") or decision.get("goal") or "").strip()
            self._cowatch_add_observation(note)
            self._schedule_next_ambient_ai()
            return

        expression = str(decision.get("expression", "curious"))
        action = str(decision.get("action", "none"))
        target = str(decision.get("target", "current"))
        bubble_raw = str(decision.get("bubble", "")) if decision.get("bubble") else ""
        bubble = compact_pet_sentence(bubble_raw, max_words=self.cfg.speech_max_words, min_words=1) if bubble_raw else ""
        if any(tok in bubble for tok in ['{"', '"a"', '"b"', "':", '":']):
            bubble = ""
        if not bubble and bubble_raw:
            decision["rejected_overlong_or_invalid_bubble"] = str(bubble_raw)[:120]
        if bubble and self._is_repetitive_pet_line(bubble):
            decision["suppressed_repeat"] = bubble
            bubble = ""
        goal = str(decision.get("goal", "") or "").strip()[:48]
        queue_choice = str(decision.get("queue", "keep") or "keep").strip().lower()
        override = bool(decision.get("override", False))
        body = decision.get("body", {})
        tv_text = str(decision.get("tv_text", "")).strip().lower()
        try:
            intensity = int(decision.get("intensity", 2))
        except (TypeError, ValueError):
            intensity = 2
        try:
            pause_seconds = max(0.0, min(24.0, float(decision.get("pause_seconds", 0))))
        except (TypeError, ValueError):
            pause_seconds = 0.0

        decision = dict(decision)
        decision["request_reason"] = request_reason
        self.last_llm_decision = decision

        action_norm = action.strip().lower().replace(" ", "_")
        target_norm = target.strip().lower().replace(" ", "_")
        physical_actions = {
            "clean", "collect", "go_bin", "dump", "watch_tv", "play_tv", "playtv",
            "chase_butterfly", "chase_eva", "chase", "inspect_mouse", "mouse", "scoot_left",
            "scoot_right", "dance", "throw_trash", "toss_debris", "throw", "move_to",
            "move", "hide", "roam", "sing", "kick_ball", "kick", "ball"
        }
        moving_active = self.current_action in {"clean", "go_bin", "chase_butterfly", "chase_eva", "watch_tv", "move_to", "kick_ball", "inspect_mouse", "kick_ball"} and self.target_point is not None

        # EVA is a high-priority drama event. LLM may comment/body-react, but cannot redirect while she is on screen.
        if self.current_action == "chase_eva" and self.debris_overlay.eva_visible:
            if action_norm not in {"chase_eva", "none", "", "chill", "pause"}:
                action = "none"
                action_norm = "none"
                target = "eva"
                target_norm = "eva"
                queue_choice = "keep"
                override = False

        # Ground speech to actual state. Inner thoughts are not real third-party events.
        bubble_l = bubble.lower()
        if bubble and any(w in bubble_l for w in ["steal", "taking", "who took", "someone", "thief", "sneaky human"]):
            bubble = ""
            bubble_l = ""
        if bubble_l and any(w in bubble_l for w in ["basketball", "ball", "kick"]) and action.strip().lower() in {"", "none", "chill", "pause"} and not moving_active:
            action = "kick_ball"
            target = "basketball"
        if bubble_l and "butterfly" in bubble_l and not self.debris_overlay.butterfly_visible:
            bubble = ""
            bubble_l = ""
        if bubble_l and any(w in bubble_l for w in ["throw", "toss", "attention", "chaos"]) and action.strip().lower() in {"", "none", "chill", "pause"} and not moving_active:
            action = "throw_trash"
            target = "screen"

        # Recompute after grounding rewrites; otherwise a corrected action like
        # kick_ball could still be treated as the original "none".
        action_norm = action.strip().lower().replace(" ", "_")
        target_norm = target.strip().lower().replace(" ", "_")

        user_command_reason = "user_command" in request_reason or bool(self._pending_user_instruction and time.time() < self._command_lock_until)
        forceful_reason = any(key in request_reason for key in ["user_command", "manual", "activity", "attention", "caught_up", "settings"])
        wants_physical = action_norm in physical_actions or (action_norm == "move_to" and target_norm not in {"", "current", "none"})
        # Ambient physical actions are intentionally throttled so Wally does not thrash between goals.
        if wants_physical and not forceful_reason and not override:
            if time.time() < self.goal_lock_until or time.time() - self._last_physical_action_at < 14:
                wants_physical = False
                action = "none"
                action_norm = "none"

        # Apply facial/body language every tick; it makes the pet feel alive even when it keeps the same goal.
        self._apply_body_controls(body if isinstance(body, dict) else {}, target_hint=target)
        if tv_text:
            self.debris_overlay.set_tv_mode(tv_text)
        mood_payload = decision.get("mood", "")
        if isinstance(mood_payload, dict):
            updates: Dict[str, float] = {}
            for key, value in mood_payload.items():
                k = str(key).strip().lower()
                if k in self.moods:
                    try:
                        # Treat small values as deltas, larger values as desired meter targets.
                        v = float(value)
                        updates[k] = (v - self.moods.get(k, 0.0)) * 0.35 if abs(v) > 10 else v
                    except (TypeError, ValueError):
                        pass
            if updates:
                self._nudge_mood(**updates)
        else:
            mood_nudge = str(mood_payload or "").lower()
            if mood_nudge:
                for key in self.moods:
                    if key in mood_nudge:
                        self._nudge_mood(**{key: 4.0})
        self.set_expression(expression)
        # The LLM's chosen emotion holds the face briefly before mood drift takes over.
        self._last_llm_expression_at = time.time()

        if bubble:
            self.show_bubble(bubble, 7800 + intensity * 800, source="ollama")
            self._last_spoken_bubble_at = time.time()
            self._remember_pet_line(bubble)
            self._maybe_record_gag(bubble)
            if "cowatch" in request_reason and isinstance(self._cowatch_session, dict):
                self._cowatch_session.setdefault("comments", []).append(bubble[:90])
                self._cowatch_session["comments"] = self._cowatch_session["comments"][-8:]
            if "scheduled_scene_check" in request_reason or "manual_screen_check" in request_reason:
                self.last_screen_reaction_signature = self._normalize_pet_line(bubble)[:80]
        elif was_offline:
            self.show_bubble(banter.pick("error_brain", self._banter_context(), avoid=self.recent_pet_lines[-10:]), 7000, source="static")
            self._last_spoken_bubble_at = time.time()
        elif any(key in request_reason for key in ["ambient", "joke", "fact", "typing", "screen", "scene", "activity", "startup", "event", "work", "overload"]) and time.time() - self._last_spoken_bubble_at > 12:
            fallback_line = compact_pet_sentence(self._fallback_life_line(request_reason), max_words=self.cfg.speech_max_words, min_words=1)
            if fallback_line:
                self.show_bubble(fallback_line, 7600, source="static")
                self._last_spoken_bubble_at = time.time()
                self._remember_pet_line(fallback_line)

        if time.time() < self._command_lock_until and "user_command" not in request_reason and queue_choice in {"pause", "replace", "drop"}:
            queue_choice = "keep"
        self._update_goal_queue_from_decision(queue_choice, goal, action, target, override, request_reason)

        # Active movement is protected from random 2-5s brain ticks. The LLM can still
        # interrupt deliberately with override=true, q=pause/replace, a user command,
        # butterfly event, or activity event.
        allow_interrupt = override or forceful_reason or queue_choice in {"pause", "replace", "drop"}
        if moving_active and wants_physical and not allow_interrupt:
            self._remember_event("llm_kept_current_goal", text=bubble, data={"blocked_action": action, "target": target})
        elif wants_physical:
            self._apply_reaction_action(action, intensity, target=target, allow_butterfly_spawn=(forceful_reason or "butterfly_arrived" in request_reason))
        elif action_norm in {"pause", "idle", "chill", "none", ""}:
            if pause_seconds > 0 and not moving_active:
                self.current_action = "pause"
                self.target_point = None
                self.pause_until = time.time() + pause_seconds

        if pause_seconds > 0 and self.current_action not in {"clean", "go_bin", "chase_butterfly", "watch_tv", "move_to", "inspect_mouse"}:
            self.pause_until = time.time() + pause_seconds

        self._remember_event("llm_decision", text=bubble, data={
            "action": action,
            "target": target,
            "queue": queue_choice,
            "override": override,
            "reason": request_reason,
            "goal": self.current_goal,
        })

    def _on_reaction_error(self, error: str) -> None:
        self.ai_online = False
        self.last_ai_error = error
        self._schedule_next_ambient_ai()
        now = time.time()
        if now - self._last_ai_error_bubble_at > 90:
            self.show_bubble(self._friendly_ollama_error(error), 8500, source="error")
            self._last_ai_error_bubble_at = now
        if not getattr(self, "_shutdown_in_progress", False):
            self._apply_local_screen_reaction("ai_reaction_fallback")

    def _remember_action(self, kind: str, data: Dict[str, object]) -> None:
        now_dt = datetime.now()
        event = {
            "t": round(time.time(), 1),
            "at": now_dt.strftime("%H:%M:%S"),
            "kind": kind,
            "goal": self.current_goal,
            "action": self.current_action,
            "did": data.get("did", data.get("action", self.current_action)),
            **data,
        }
        self.action_memory.append(event)
        self.action_memory = self.action_memory[-32:]


    def _goal_item(self, goal: str, action: str = "none", target: str = "current", source: str = "llm", priority: int = 1) -> Dict[str, object]:
        return {
            "goal": (goal or "").strip()[:48] or "playful_moment",
            "action": (action or "none").strip(),
            "target": (target or "current").strip(),
            "source": source,
            "priority": int(priority),
            "t": round(time.time(), 1),
        }

    def _set_current_goal_item(self, item: Dict[str, object], lock_seconds: float = 3.5) -> None:
        self.current_goal = str(item.get("goal", "playful_moment"))[:48]
        self.current_goal_started_at = time.time()
        self.goal_lock_until = time.time() + max(0.0, lock_seconds)
        self.last_goal_switch_at = time.time()

    def _update_goal_queue_from_decision(self, queue_choice: str, goal: str, action: str, target: str, override: bool, reason: str) -> None:
        queue_choice = (queue_choice or "keep").lower()
        if queue_choice not in {"keep", "add", "pause", "resume", "replace", "drop"}:
            queue_choice = "keep"
        has_new_goal = bool(goal)
        if queue_choice == "drop":
            self.paused_goals.clear()
            self.goal_queue.clear()
            self.current_goal = "playful_moment"
            return
        if queue_choice == "resume":
            item = None
            if self.paused_goals:
                item = self.paused_goals.pop()
            elif self.goal_queue:
                self.goal_queue.sort(key=lambda g: int(g.get("priority", 1)), reverse=True)
                item = self.goal_queue.pop(0)
            if item:
                self._set_current_goal_item(item, lock_seconds=4.0)
                self._apply_reaction_action(str(item.get("action", "none")), 2, str(item.get("target", "current")))
            return
        if not has_new_goal:
            return
        item = self._goal_item(goal, action=action, target=target, source=reason or "llm", priority=3 if override else 1)
        if queue_choice == "add":
            self.goal_queue.append(item)
            self.goal_queue = sorted(self.goal_queue[-8:], key=lambda g: int(g.get("priority", 1)), reverse=True)
        elif queue_choice == "pause":
            if self.current_goal:
                self.paused_goals.append(self._goal_item(self.current_goal, self.current_action, target or "current", "paused", priority=2))
                self.paused_goals = self.paused_goals[-5:]
            self._set_current_goal_item(item, lock_seconds=4.0)
        elif queue_choice == "replace" or override:
            self._set_current_goal_item(item, lock_seconds=4.0)
        elif queue_choice == "keep" and not self.current_goal:
            self._set_current_goal_item(item, lock_seconds=2.5)

    def _is_wind_summon_command(self, text: str) -> bool:
        t = text.lower().strip()
        return any(k in t for k in [
            "send wind", "summon wind", "wind gust", "send leaves", "send trash", "send debris",
            "summon leaves", "summon trash", "summon debris"
        ])

    def _execute_wind_summon_command(self, text: str) -> bool:
        if not self._is_wind_summon_command(text):
            return False
        for _ in range(random.randint(2, 4)):
            self.debris_overlay.summon_wind_pile(random.randint(6, 12))
        self.show_bubble("Wind’s showing off 🍃", 2300)
        self._remember_event("summon_wind_pile", text=text, data={"summon": True})
        return True

    def _is_summon_command(self, text: str) -> bool:
        t = text.lower().strip()
        return any(k in t for k in [
            "send butterfly", "send butterflies", "summon butterfly", "summon butterflies",
            "release butterfly", "release butterflies", "bring butterfly", "bring butterflies"
        ])

    def _execute_summon_command(self, text: str) -> bool:
        if not self._is_summon_command(text):
            return False
        # This is a world summon, not an instruction for Wally to chase.
        self.debris_overlay.summon_butterfly()
        if "butterflies" in text.lower():
            # Extra nature flair without creating a heavy multi-butterfly swarm.
            for _ in range(random.randint(2, 4)):
                if hasattr(self.debris_overlay, "_shed_tree_leaf"):
                    self.debris_overlay._shed_tree_leaf()
        self.set_expression("curious")
        self._apply_body_controls({"eyes": "butterfly", "eyebrow": "curious", "emoji": "🦋", "antenna": "perked"})
        self.show_bubble("Flutter incoming 🦋", 2200)
        self._remember_event("summon_butterfly", text=text, data={"summon": True})
        if self.cfg.ai_reactions_enabled and time.time() - self.last_ai_request_at > 15:
            self.request_ai_reaction("butterfly_summoned_as_world_event", force=True, use_vision=False)
        return True

    def _execute_direct_user_command(self, text: str) -> bool:
        t = text.lower()
        action = ""
        target = "current"
        goal = ""
        # Order matters: specific commands before generic "trash" matching.
        if any(k in t for k in ["watch tv", "go watch", "sofa", "movie", "anime"]):
            action, target, goal = "watch_tv", "tv_sofa", "watch tiny TV"
        elif any(k in t for k in ["throw", "toss", "attention"]):
            action, target, goal = "throw_trash", "screen", "cause tiny mischief"
        elif any(k in t for k in ["dump", "bin", "trash can", "dustbin"]):
            action, target, goal = "go_bin", "trash_bin", "dump carried trash"
        elif any(k in t for k in ["basketball", "ball", "kick", "bounce"]):
            action, target, goal = "kick_ball", "basketball", "play with the ball"
        elif any(k in t for k in ["butterfly", "chase", "fly"]):
            action, target, goal = "chase_butterfly", "butterfly", "chase flutter friend"
        elif any(k in t for k in ["collect", "clean", "trash", "dust", "paper", "leaf"]):
            action, target, goal = "clean", "nearest_debris", "collect suspicious trash"
        elif any(k in t for k in ["sing", "song", "hum"]):
            action, target, goal = "sing", "current", "sing tiny tune"
        elif any(k in t for k in ["dance", "wiggle"]):
            action, target, goal = "dance", "current", "do desk wiggle"
        elif any(k in t for k in ["come here", "mouse", "cursor", "this icon", "that icon", "near this"]):
            action, target, goal = "inspect_mouse", "mouse", "inspect your pointer"
        elif any(k in t for k in ["roam", "wander", "patrol"]):
            action, target, goal = "roam", "random", "playful patrol"
        elif any(k in t for k in ["nap", "sleep", "rest"]):
            action, target, goal = "nap", "current", "tiny recharge"
        else:
            return False
        self._set_current_goal_item(self._goal_item(goal, action, target, "user_command", priority=9), lock_seconds=35.0 if action == "watch_tv" else 14.0)
        self._command_lock_until = time.time() + (35.0 if action == "watch_tv" else 16.0)
        if action == "watch_tv":
            self._tv_break_reason = "user_tv_command"
            self._tv_break_duration_seconds = 30.0
            self._tv_break_mid_comment_scheduled = False
        self._apply_reaction_action(action, 3, target=target, allow_attention_throw=True, allow_butterfly_spawn=True)
        self._remember_event("direct_command_executed", text=text, data={"action": action, "target": target, "goal": goal})
        self._nudge_mood(playful=8, curious=5, bored=-8)
        return True

    def _throw_attention_trash(self) -> None:
        center = self.frameGeometry().center()
        self.attention_overlay.fling_from(center, count=random.randint(6, 11))
        if hasattr(self.debris_overlay, "toss_attention_debris"):
            self.debris_overlay.toss_attention_debris(random.randint(3, 7))
        self.set_expression("surprised")
        self._apply_body_controls({"antenna": "perked", "eyes": "user", "eyebrow": "curious", "emoji": "!", "left_arm": "wave", "right_arm": "point"})

    def _apply_body_controls(self, controls: Dict[str, object], target_hint: str = "current") -> None:
        if not isinstance(controls, dict):
            controls = {}
        antenna = str(controls.get("antenna", controls.get("ant", self.antenna_pose))).strip().lower()
        eyes = str(controls.get("eyes", controls.get("eye", target_hint or self.eye_focus))).strip().lower()
        eyebrow = str(controls.get("eyebrow", controls.get("eyebrows", controls.get("brow", self.eyebrow_pose)))).strip().lower()
        left = str(controls.get("left_arm", controls.get("left_hand", controls.get("l", self.left_arm_pose)))).strip().lower()
        right = str(controls.get("right_arm", controls.get("right_hand", controls.get("r", self.right_arm_pose)))).strip().lower()
        emoji = str(controls.get("emoji", controls.get("emo", ""))).strip()
        tv = str(controls.get("tv", "unchanged")).strip().lower()

        antenna_alias = {"alert": "perked", "neutral": "relaxed"}
        antenna = antenna_alias.get(antenna, antenna)
        if antenna in {"relaxed", "perked", "droop", "wiggle", "heart"}:
            self.antenna_pose = antenna

        eyes_alias = {"trash": "trash_bin", "bin": "trash_bin", "sofa": "tv", "tv_sofa": "tv", "nearest_debris": "debris", "debris_pile": "debris", "closed": "sleepy", "auto": "side", "target": target_hint}
        eyes = eyes_alias.get(eyes, eyes)
        if eyes in {"current", "side", "mouse", "butterfly", "basketball", "ball", "debris", "trash_bin", "tv", "screen", "user", "sleepy", "sparkle", "left", "right", "up", "down"}:
            self.eye_focus = eyes

        brow_alias = {"thinking": "focused", "cleaning": "focused", "watching": "focused", "proud": "happy", "excited": "happy", "scared": "worried", "soft": "sad", "neutral": "flat", "confused": "curious", "mischievous": "mischief", "annoyed": "irritated", "mad": "angry"}
        eyebrow = brow_alias.get(eyebrow, eyebrow)
        if eyebrow in {"happy", "curious", "worried", "focused", "angry", "irritated", "frustrated", "sad", "sleepy", "love", "dizzy", "surprised", "mischief", "flat"}:
            self.eyebrow_pose = eyebrow

        arm_alias = {"neutral": "idle", "rest": "idle", "grab": "collect", "sweep": "collect", "tiny_fist": "cheer", "hold_plant": "hold", "plant": "hold"}
        left = arm_alias.get(left, left)
        right = arm_alias.get(right, right)
        if left in {"idle", "wave", "point", "collect", "hold", "shy", "cheer", "tired"}:
            self.left_arm_pose = left
        if right in {"idle", "wave", "point", "collect", "hold", "shy", "cheer", "tired"}:
            self.right_arm_pose = right

        emoji_alias = {
            "heart": "💛", "love": "💛", "heartbreak": "💔", "sad": "💔", "sparkle": "✨", "star": "🌟", "question": "?", "exclamation": "!",
            "sleep": "😴", "zzz": "😴", "butterfly": "🦋", "basketball": "🏀", "ball": "🏀", "trash": "♻️", "bin": "🗑️", "clean": "🧹",
            "music": "🎵", "movie": "📺", "tv": "📺", "wow": "😳", "sweat": "💧", "dizzy": "💫", "popcorn": "🍿",
            "laugh": "😂", "chuckle": "😅", "cool": "😎", "plant": "🌱", "inspect": "🔍", "zap": "⚡", "sing": "🎵", "song": "🎶", "giggle": "🤭", "oops": "🙃", "salute": "🫡", "tear": "🥹", "coffee": "☕", "bubbles": "🫧", "leaf": "🍃", "magic": "🪄",
            # Emotional palette so feelings have a face, not just a word.
            "excited": "🤩", "starstruck": "🤩", "proud": "🏆", "trophy": "🏆", "angry": "😤", "mad": "😤", "huff": "😤",
            "frustrated": "😩", "tired": "😮‍💨", "exhausted": "😮‍💨", "bored": "🥱", "yawn": "🥱", "cozy": "🥰", "adore": "🥰", "smug": "😏",
            "curious": "🤔", "think": "🤔", "naughty": "😈", "mischief": "😈", "party": "🎉", "hype": "🎉", "celebrate": "🎉",
            "fire": "🔥", "thumbsup": "👍", "ok": "👍", "eyes": "👀", "robot": "🤖", "idea": "💡", "rainbow": "🌈", "sun": "☀️", "moon": "🌙",
            "wink": "😉", "blush": "☺️", "panic": "😱", "shock": "😱", "nervous": "😬", "pleading": "🥺", "none": "",
        }
        emoji = emoji_alias.get(emoji.lower(), emoji) if emoji else ""
        allowed_emoji = {
            "", "?", "!", "💛", "💔", "✨", "🦋", "♻️", "😴", "😳", "👀", "🍿", "💧", "💫", "😂", "😅", "😎", "🌱", "📺", "🗑️",
            "🔍", "⚡", "🧹", "🌟", "💤", "😵‍💫", "🎵", "🎶", "🤭", "🙃", "🫡", "🥹", "☕", "🫧", "🍃", "🪄", "🎮", "🐾", "🛠️", "📌",
            "🤩", "🏆", "😤", "😩", "😮‍💨", "🥱", "🥰", "😏", "🤔", "😈", "🎉", "🔥", "👍", "🤖", "💡", "🌈", "☀️", "🌙", "😉", "☺️", "😱", "😬", "🥺",
        }
        if emoji in allowed_emoji:
            self.emoji_effect = emoji
            self.emoji_until = time.time() + (8.0 if emoji else 0)

        tv_alias = {"calm": "stars", "unchanged": "unchanged"}
        tv = tv_alias.get(tv, tv)
        if tv != "unchanged":
            self.debris_overlay.set_tv_mode(tv)

    def _apply_reaction_action(self, action: str, intensity: int, target: str = "current", allow_attention_throw: bool = False, allow_butterfly_spawn: bool = False) -> None:
        action = (action or "none").strip().lower().replace(" ", "_")
        target = (target or "current").strip().lower().replace(" ", "_")
        action_alias = {
            "collect": "clean", "pickup": "clean", "pick_up": "clean", "sweep": "clean",
            "dump": "go_bin", "bin": "go_bin", "tv": "watch_tv", "playtv": "play_tv",
            "chase": "chase_butterfly", "eva": "chase_eva", "evaaa": "chase_eva", "mouse": "inspect_mouse", "throw": "throw_trash", "kick": "kick_ball", "ball": "kick_ball", "basketball": "kick_ball",
            "toss": "throw_trash", "move": "move_to", "idle": "chill", "wander": "roam",
            "patrol": "roam", "song": "sing", "hum": "sing",
        }
        target_alias = {
            "debris": "nearest_debris", "trash": "nearest_debris", "dust": "nearest_debris",
            "paper": "nearest_debris", "pile": "debris_pile", "bin": "trash_bin",
            "tv": "tv_sofa", "sofa": "tv_sofa", "butterfly_visible": "butterfly", "basketball": "basketball", "ball": "basketball", "cursor": "mouse",
            "tree": "tree", "tiny_tree": "tree", "nature": "tree", "leaves": "tree",
            "left": "left_edge", "right": "right_edge",
        }
        action = action_alias.get(action, action)
        target = target_alias.get(target, target)
        physical_action_names = {"clean", "go_bin", "watch_tv", "play_tv", "chase_butterfly", "chase_eva", "kick_ball", "inspect_mouse", "scoot_left", "scoot_right", "roam", "hide", "dance", "sing", "move_to", "toss_debris", "throw_trash"}
        if action in physical_action_names:
            self._last_physical_action_at = time.time()
            self._next_playful_nudge_at = time.time() + random.uniform(16, 30)
            self._remember_action("did_action", {"did": action, "target": target, "expression": self.expression})

        if action in {"none", "", "chill"}:
            if self.current_action not in {"clean", "go_bin", "chase_butterfly", "watch_tv", "move_to", "inspect_mouse"}:
                self.current_action = "chill"
                self.target_point = None
            return

        # move_to is the only target-first action. A target alone no longer forces trash/bin work.
        if action == "move_to":
            point = self._target_point_for_llm(target)
            if point is not None:
                self.current_action = "move_to"
                self.target_point = point
                self._apply_body_controls({"eyes": target, "eyebrow": "curious", "emoji": "inspect", "left_arm": "point"})
            return

        if action in {"clean", "collect"}:
            if self.debris_overlay.item_count() <= 0:
                self._apply_reaction_action(random.choice(["inspect", "roam", "sing"]), max(1, intensity - 1), "random")
                return
            self.current_action = "clean"
            if not self._clean_batch_started_at:
                self._clean_batch_started_at = time.time()
            self._apply_body_controls({"eyes": "debris", "eyebrow": "focused", "emoji": "clean", "left_arm": "collect", "right_arm": "collect"})
            self._start_cleaning_behavior()
        elif action == "kick_ball":
            self.current_action = "kick_ball"
            self.set_expression("excited")
            self._remember_event("ball_play_started", text="kick_ball", data={"target": "basketball"})
            self._apply_body_controls({"antenna": "wiggle", "eyes": "basketball", "eyebrow": "mischief", "emoji": "🏀", "left_arm": "point", "right_arm": "cheer"})
            point = self._ball_target_point()
            if point is None:
                self.debris_overlay.ball.visible = True
                self.debris_overlay.ball.x = max(46, min(self.debris_overlay.width() - 46, (self.frameGeometry().center().x() - self.debris_overlay.geometry().left()) + random.choice([-80, 80])))
                self.debris_overlay.ball.y = max(20, self.debris_overlay.height() - 17)
                point = self._ball_target_point()
            self.target_point = point or self._target_point_for_llm("random")
        elif action == "chase_eva":
            if not self.debris_overlay.eva_visible:
                self.debris_overlay.summon_eva_flyby()
            self.current_action = "chase_eva"
            self.set_expression("love")
            self._apply_body_controls({"antenna": "heart", "eyes": "up", "eyebrow": "love", "emoji": "💛", "left_arm": "cheer", "right_arm": "wave"})
            self.target_point = self._eva_target_point()
        elif action == "chase_butterfly":
            if not self.debris_overlay.butterfly_visible:
                if not allow_butterfly_spawn:
                    self._remember_action("chase_skipped_no_butterfly", {"reason": "rare_butterfly_policy"})
                    self._apply_reaction_action(random.choice(["roam", "inspect", "sing"]), max(1, intensity - 1), "random")
                    return
                self.debris_overlay.summon_butterfly()
            self.current_action = "chase_butterfly"
            self._play_whoa_sound()
            self.set_expression("excited")
            self._apply_body_controls({"antenna": "wiggle", "eyes": "butterfly", "eyebrow": "curious", "emoji": "butterfly", "left_arm": "point", "right_arm": "cheer"})
            self.target_point = self._butterfly_target_point()
        elif action == "inspect_mouse":
            self.current_action = "inspect_mouse"
            self.set_expression("curious")
            self.eye_focus = "mouse"
            self.eyebrow_pose = "curious"
            self.left_arm_pose = "point"
            self.target_point = self._mouse_target_point()
        elif action == "dizzy":
            self.current_action = "dizzy"
            self.target_point = None
            self.dizzy_until = time.time() + 4.5 + intensity * 0.4
            self.pause_until = time.time() + 3.0
            self.set_expression("dizzy")
            self._apply_body_controls({"antenna": "wiggle", "eyes": "mouse", "eyebrow": "dizzy", "emoji": "dizzy", "left_arm": "tired", "right_arm": "tired"})
        elif action == "scoot_left":
            self.current_action = "move_to"
            self.target_point = self._clamp_to_lane(QPoint(self.x() - 80 - intensity * 18, self.y()))
        elif action == "scoot_right":
            self.current_action = "move_to"
            self.target_point = self._clamp_to_lane(QPoint(self.x() + 80 + intensity * 18, self.y()))
        elif action == "roam":
            self.current_action = "move_to"
            target_choice = random.choice(["random", "roam_left", "roam_right", "left_edge", "right_edge"])
            self.target_point = self._target_point_for_llm(target if target not in {"current", "", "none"} else target_choice)
            self.set_expression(random.choice(["curious", "happy", "excited"]))
            self._apply_body_controls({"eyes": "side", "eyebrow": "curious", "emoji": random.choice(["✨", "🔍", "🌟"]), "left_arm": "point"})
        elif action == "hide":
            lane, orientation = self._taskbar_lane()
            self.current_action = "move_to"
            if orientation in {"bottom", "top", "unknown"}:
                edge = lane.left() + 12 if self.x() > lane.center().x() else lane.right() - self.width() - 12
                self.target_point = self._clamp_to_lane(QPoint(edge, self.y()))
            else:
                self.target_point = self._clamp_to_lane(QPoint(self.x(), lane.bottom() - self.height() - 12))
        elif action == "dance":
            self.current_action = "move_to"
            self.set_expression("excited")
            self._apply_body_controls({"antenna": "wiggle", "eyes": "user", "eyebrow": "happy", "emoji": "✨", "left_arm": "cheer", "right_arm": "cheer"})
            self.target_point = self._clamp_to_lane(QPoint(self.x() + random.choice([-90, 90]), self.y()))
        elif action == "sing":
            self.current_action = "pause"
            self.target_point = None
            self.pause_until = time.time() + 3.5 + intensity
            self.set_expression("happy")
            self._last_sing_at = time.time()
            self._apply_body_controls({"antenna": "wiggle", "eyes": "sparkle", "eyebrow": "happy", "emoji": random.choice(["🎵", "🎶", "✨"]), "left_arm": "cheer", "right_arm": "wave", "tv": "anime"})
        elif action == "wave":
            self.current_action = "chill"
            self.set_expression("happy")
            self.pause_until = time.time() + 2.5 + intensity * 0.6
            self._apply_body_controls({"antenna": "wiggle", "eyes": "user", "emoji": "sparkle", "left_arm": "wave", "right_arm": "wave"})
            self.target_point = None
        elif action == "watch":
            self.current_action = "watch"
            self.target_point = None
        elif action == "go_bin":
            if self.carrying_debris <= 0 and target not in {"trash_bin", "bin"}:
                self._apply_reaction_action(random.choice(["inspect", "roam", "watch_tv"]), max(1, intensity - 1), "random")
                return
            self.current_action = "go_bin"
            self._apply_body_controls({"eyes": "trash_bin", "eyebrow": "focused", "emoji": "bin", "left_arm": "hold", "right_arm": "hold"})
            self.target_point = self._bin_target_point()
        elif action in {"watch_tv", "play_tv"}:
            self.current_action = "watch_tv"
            self.set_expression("watching")
            self._tv_break_duration_seconds = max(30.0, float(getattr(self, "_tv_break_duration_seconds", 30.0)))
            if not getattr(self, "_tv_break_reason", ""):
                self._tv_break_reason = "tv_break"
            if action == "play_tv":
                self.debris_overlay.set_tv_mode(random.choice(["movie", "stars", "hearts", "fireplace", "smile", "anime"]))
            else:
                self.debris_overlay.set_tv_mode("anime" if random.random() < 0.45 else getattr(self.debris_overlay, "tv_mode", "static"))
            self._apply_body_controls({"eyes": "tv", "eyebrow": "focused", "emoji": "📺", "left_arm": "shy", "right_arm": "point"})
            self.target_point = self._tv_target_point()
            self._remember_event("tv_break_requested", text=self._tv_break_reason, data={"did": "go_to_tv_sofa", "duration_seconds": 30})
        elif action in {"inspect", "investigate", "pause"}:
            self.current_action = "investigate"
            self.target_point = None
            self.pause_until = time.time() + 2.5 + intensity
            self.set_expression("curious")
            self._apply_body_controls({"eyes": target if target != "current" else "screen", "eyebrow": "focused", "emoji": "🔍", "left_arm": "point"})
        elif action in {"nap", "recharge"}:
            self.current_action = action
            self.target_point = None
            self.pause_until = time.time() + 7 + intensity * 1.5
            self.set_expression("sleepy")
            self._apply_body_controls({"antenna": "droop", "eyes": "closed", "emoji": "sleep", "left_arm": "shy", "right_arm": "shy"})
        elif action in {"toss_debris", "throw_trash"}:
            # Attention toss is intentionally rare unless the user explicitly asks.
            if not allow_attention_throw:
                if time.time() - self._last_attention_throw_check_at < 240:
                    self._remember_action("attention_throw_throttled", {"cooldown_seconds_left": round(240 - (time.time() - self._last_attention_throw_check_at), 1)})
                    self._apply_reaction_action(random.choice(["wave", "sing", "dance", "inspect"]), max(1, intensity - 1), "current")
                    return
                self._last_attention_throw_check_at = time.time()
                if random.random() >= 0.42:
                    self._remember_action("attention_throw_skipped", {"reason": "33_percent_chance_failed"})
                    self._apply_reaction_action(random.choice(["wave", "sing", "dance", "inspect"]), max(1, intensity - 1), "current")
                    return
            self.current_action = "toss_debris"
            self._last_attention_trash_at = time.time()
            start = self.frameGeometry().center()
            self.attention_overlay.fling_from(start, count=8 + intensity)
            if hasattr(self.debris_overlay, "toss_attention_debris"):
                self.debris_overlay.toss_attention_debris(max(3, 4 + intensity))
            self.set_expression("surprised")
            self._apply_body_controls({"antenna": "perked", "eyes": "user", "eyebrow": "mischief", "emoji": random.choice(["!", "🤭", "😂", "🗑️"]), "left_arm": "wave", "right_arm": "point"})
            self.target_point = None
            self._pending_activity_note = {"kind": "pet_threw_trash_for_attention", "hint": "React with a tiny contextual joke, oops, chuckle, or clean-up plan."}
            if self.cfg.ai_reactions_enabled and time.time() - self._last_throw_followup_at > 5:
                self._last_throw_followup_at = time.time()
                QTimer.singleShot(1200, lambda: self.request_ai_reaction("after_attention_trash_throw", force=True, use_vision=False))
        else:
            if self.current_action not in {"clean", "go_bin", "chase_butterfly", "watch_tv", "move_to", "inspect_mouse"}:
                self.current_action = "chill"
                self.target_point = None
                self.pause_until = time.time() + random.uniform(1.5, 4.0)

    def _apply_local_screen_reaction(self, reason: str) -> None:
        context = self._build_activity_context(reason=reason, include_screenshot=self.cfg.screenshot_reactions_enabled, consume_counts=False)
        if self.cfg.ai_reactions_enabled and self.last_ai_error and self.bubble_text.startswith("Ollama issue"):
            return
        scene = str(context.get("scene_guess", "normal"))
        media_hint = str(context.get("media_hint", ""))
        if scene == "spooky_or_dark":
            self.set_expression("scared")
            self.show_bubble("Spooky vibes? *hides a little* 😨", 3600)
            self._apply_reaction_action("hide", 3)
        elif scene == "warm_or_cute":
            self.set_expression("love")
            self.show_bubble("Aww... tiny heart mode.", 3400)
        elif media_hint:
            self.set_expression("watching")
            self.show_bubble("I'll watch quietly with you.", 3200)
        else:
            self.set_expression("curious")
            self.show_bubble("Hmm? Screen vibes changed.", 2800)

    def _build_activity_context(self, reason: str, include_screenshot: bool, consume_counts: bool) -> Dict[str, object]:
        counts = self.activity_monitor.consume_counts() if consume_counts else {
            "key_count": 0,
            "scroll_count": 0,
            "recent_key_score": round(self.activity_monitor.recent_key_score, 1),
            "recent_scroll_score": round(self.activity_monitor.recent_scroll_score, 1),
            "mouse_motion_score": round(self.activity_monitor.motion_score, 2),
            "idle_seconds": round(max(0.0, time.time() - self.activity_monitor.last_input_time), 1),
            "listener_error": self.activity_monitor.listener_error,
        }
        title = get_active_window_title()
        media_hint = infer_media_hint(title)
        lane, orientation = self._taskbar_lane()
        pet_center = self.frameGeometry().center()
        cursor = QCursor.pos()
        nearest = self.debris_overlay.nearest_item_global_to(pet_center.x(), pet_center.y())
        bin_pt = self.debris_overlay.bin_point_global()
        tv_pt = self.debris_overlay.tv_spot_global()
        butterfly_pt = self.debris_overlay.butterfly_point_global()
        debris_summary = self.debris_overlay.debris_summary_global()
        if nearest is not None:
            debris_summary["nearest"] = [nearest.x(), nearest.y()]
        context: Dict[str, object] = {
            "reason": reason,
            "surface": "top_edge_of_the_taskbar_like_a_little_floor",
            "pet_location": "taskbar_or_dock_lane" if self.cfg.taskbar_only else "desktop",
            "current_expression": self.expression,
            "current_action": self.current_action,
            "current_goal": self.current_goal,
            "body_controls": {
                "antenna": self.antenna_pose,
                "eyes": self.eye_focus,
                "left_arm": self.left_arm_pose,
                "right_arm": self.right_arm_pose,
                "emoji": self.emoji_effect if time.time() < self.emoji_until else "none",
                "tv": getattr(self.debris_overlay, "tv_mode", "static"),
            },
            "recent_pet_memory": self.action_memory[-10:],
            "carrying_debris": self.carrying_debris,
            "debris_visible": self.debris_overlay.item_count() if self.cfg.debris_enabled else 0,
            "debris": debris_summary,
            "butterfly": self.debris_overlay.butterfly_status(),
            "foreground_window_title": title[:180],
            "media_hint": media_hint,
            "activity": counts,
            "recent_activity_event": self._pending_activity_note or {},
            "environment_map": {
                "orientation": orientation,
                "lane_rect": [lane.left(), lane.top(), lane.right(), lane.bottom()],
                "pet_center": [pet_center.x(), pet_center.y()],
                "mouse_cursor": [cursor.x(), cursor.y()],
                "trash_bin_right": [bin_pt.x(), bin_pt.y()],
                "tv_sofa_left": [tv_pt.x(), tv_pt.y()],
                "nearest_debris": [nearest.x(), nearest.y()] if nearest else None,
                "butterfly": [butterfly_pt.x(), butterfly_pt.y()] if butterfly_pt else None,
            },
            "ai_status": {
                "ollama_online_recently": self.ai_online,
                "seconds_since_last_ai_success": round(time.time() - self.last_ai_success_at, 1) if self.last_ai_success_at else None,
                "last_error": self.last_ai_error[:160],
            },
            "available_places": ["taskbar_edge", "trash_bin_right", "tv_sofa_left", "tiny_tree", "nearest_debris", "debris_pile", "butterfly", "basketball", "mouse", "left_edge", "right_edge"],
            "available_actions": ["chill", "pause", "inspect", "collect", "clean", "go_bin", "watch_tv", "play_tv", "chase_butterfly", "chase_eva", "kick_ball", "inspect_mouse", "scoot_left", "scoot_right", "dance", "hide", "nap", "toss_debris", "move_to", "watch", "none"],
            "available_body_controls": {
                "antenna": ["relaxed", "perked", "droop", "wiggle", "heart"],
                "eyes": ["current", "mouse", "butterfly", "debris", "trash_bin", "tv", "screen", "user", "sleepy", "sparkle"],
                "left_arm/right_arm": ["idle", "wave", "point", "collect", "hold", "shy", "cheer", "tired"],
                "emoji": ["", "?", "!", "💛", "✨", "🦋", "♻️", "😴", "😳", "👀", "🍿"],
                "tv": ["off", "static", "stars", "hearts", "butterfly", "movie", "fireplace", "plant", "smile"],
            },
            "llm_control": "Choose action + target + body; the app executes movement, eyes, hands, antenna, emoji, TV.",
            "privacy": "Screenshots, when enabled, are sent only to the local Ollama server as a small resized image.",
        }
        if include_screenshot:
            screen_summary = self._screen_summary()
            context["screen_summary"] = screen_summary
            context["scene_guess"] = infer_scene_guess(title, screen_summary)
        else:
            context["scene_guess"] = infer_scene_guess(title, None)
        return context

    def _capture_screen_base64(self) -> Optional[str]:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            return None
        try:
            pix = screen.grabWindow(0)
        except Exception:
            return None
        if pix.isNull():
            return None

        # Small JPEG glance: enough for scene vibe, low enough for a tiny local VLM.
        scaled = pix.scaled(QSize(640, 360), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        buffer = QBuffer()
        if not buffer.open(QIODevice.WriteOnly):
            return None
        ok = scaled.save(buffer, "JPG", 62)
        if not ok:
            return None
        return base64.b64encode(bytes(buffer.data())).decode("ascii")

    def _screen_summary(self) -> Dict[str, object]:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            return {"available": False, "reason": "no screen"}
        try:
            pix = screen.grabWindow(0)
        except Exception as exc:
            return {"available": False, "reason": str(exc)}
        if pix.isNull():
            return {"available": False, "reason": "screen capture returned empty image"}

        image = pix.toImage().scaled(QSize(36, 20), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        total_r = total_g = total_b = 0
        brightness_values: List[float] = []
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                r, g, b = c.red(), c.green(), c.blue()
                total_r += r
                total_g += g
                total_b += b
                brightness_values.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        n = max(1, image.width() * image.height())
        avg_r = total_r / n
        avg_g = total_g / n
        avg_b = total_b / n
        brightness = sum(brightness_values) / len(brightness_values)
        dark_ratio = sum(1 for b in brightness_values if b < 55) / len(brightness_values)
        bright_ratio = sum(1 for b in brightness_values if b > 205) / len(brightness_values)
        colorfulness = (abs(avg_r - avg_g) + abs(avg_g - avg_b) + abs(avg_b - avg_r)) / 3.0
        warmth = avg_r - avg_b

        current_signature = (round(avg_r, 1), round(avg_g, 1), round(avg_b, 1))
        motion_delta = 0.0
        if self._last_screen_sample is not None:
            motion_delta = sum(abs(a - b) for a, b in zip(current_signature, self._last_screen_sample)) / 3.0
        self._last_screen_sample = current_signature

        if brightness < 70:
            tone = "dark"
        elif warmth > 28 and brightness > 95:
            tone = "warm"
        elif avg_b > avg_r + 20:
            tone = "cool_blue"
        elif bright_ratio > 0.45:
            tone = "bright"
        else:
            tone = "neutral"

        return {
            "available": True,
            "brightness": round(brightness, 1),
            "dark_ratio": round(dark_ratio, 2),
            "bright_ratio": round(bright_ratio, 2),
            "avg_rgb": [round(avg_r, 1), round(avg_g, 1), round(avg_b, 1)],
            "warmth": round(warmth, 1),
            "colorfulness": round(colorfulness, 1),
            "motion_delta": round(motion_delta, 1),
            "tone": tone,
        }

    def _bin_target_point(self) -> QPoint:
        point = self.debris_overlay.bin_point_global()
        return self._clamp_to_lane(QPoint(point.x() - self.width() // 2, self.y()))

    def _tv_target_point(self) -> QPoint:
        point = self.debris_overlay.tv_spot_global()
        return self._clamp_to_lane(QPoint(point.x() - self.width() // 2, self.y()))

    def _eva_target_point(self) -> Optional[QPoint]:
        point = self.debris_overlay.eva_point_global() if hasattr(self.debris_overlay, "eva_point_global") else None
        if point is None:
            return None
        # Follow beneath and slightly behind EVA, not directly on top of her.
        evx = float(getattr(self.debris_overlay, "eva_vx", 1.0))
        behind = 52 if evx > 0 else -52
        return self._clamp_to_lane(QPoint(point.x() - self.width() // 2 - behind, self.y()))

    def _butterfly_target_point(self) -> Optional[QPoint]:
        point = self.debris_overlay.butterfly_point_global()
        if point is None:
            return None
        return self._clamp_to_lane(QPoint(point.x() - self.width() // 2, self.y()))

    def _ball_target_point(self) -> Optional[QPoint]:
        point = self.debris_overlay.ball_point_global()
        if point is None:
            return None
        # Stand slightly beside the ball so the kick reads visually.
        offset = -self.width() // 2 + random.choice([-14, 14])
        return self._clamp_to_lane(QPoint(point.x() + offset, self.y()))

    def _mouse_target_point(self) -> QPoint:
        cursor = QCursor.pos()
        lane, orientation = self._taskbar_lane()
        if orientation in {"bottom", "top", "unknown"}:
            return self._clamp_to_lane(QPoint(cursor.x() - self.width() // 2, self.y()))
        return self._clamp_to_lane(QPoint(self.x(), cursor.y() - self.height() // 2))

    def _target_point_for_llm(self, target: str) -> Optional[QPoint]:
        target = (target or "current").strip().lower()
        lane, orientation = self._taskbar_lane()
        if target in {"current", ""}:
            return None
        if target == "nearest_debris":
            center = self.frameGeometry().center()
            nearest = self.debris_overlay.nearest_item_global_to(center.x(), center.y())
            return self._point_for_global_debris(nearest) if nearest else None
        if target == "debris_pile":
            summary = self.debris_overlay.debris_summary_global()
            pile = summary.get("pile_center") if isinstance(summary, dict) else None
            if isinstance(pile, list) and len(pile) >= 2:
                return self._point_for_global_debris(QPoint(int(float(pile[0])), int(float(pile[1]))))
            return None
        if target == "trash_bin":
            return self._bin_target_point()
        if target == "tv_sofa":
            return self._tv_target_point()
        if target == "tree":
            point = self.debris_overlay.tree_point_global()
            return self._clamp_to_lane(QPoint(point.x() - self.width() // 2, self.y()))
        if target == "butterfly":
            return self._butterfly_target_point()
        if target in {"basketball", "ball"}:
            return self._ball_target_point()
        if target == "mouse":
            return self._mouse_target_point()
        if target == "left_edge":
            return self._clamp_to_lane(QPoint(lane.left() + 10, self.y()))
        if target == "right_edge":
            return self._clamp_to_lane(QPoint(lane.right() - self.width() - 10, self.y()))
        if target == "roam_left":
            return self._clamp_to_lane(QPoint(self.x() - random.randint(60, 180), self.y()))
        if target == "roam_right":
            return self._clamp_to_lane(QPoint(self.x() + random.randint(60, 180), self.y()))
        if target == "random":
            self._choose_new_target()
            return self.target_point
        return None

    def _update_taskbar_lane(self) -> None:
        lane, _orientation = self._taskbar_lane()
        self.debris_overlay.set_lane(lane)
        if hasattr(self, "mini_chat"):
            self.mini_chat.reposition(self.debris_overlay.tv_spot_global(), lane)

    def _taskbar_lane(self) -> Tuple[QRect, str]:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if not screen:
            return QRect(), "unknown"
        full = screen.geometry()
        avail = screen.availableGeometry()

        bottom_gap = max(0, full.bottom() - avail.bottom())
        top_gap = max(0, avail.top() - full.top())
        left_gap = max(0, avail.left() - full.left())
        right_gap = max(0, full.right() - avail.right())
        gaps = {"bottom": bottom_gap, "top": top_gap, "left": left_gap, "right": right_gap}
        orientation = max(gaps, key=gaps.get)
        gap = gaps[orientation]

        # This is an EDGE lane, not an in-taskbar lane. For a bottom taskbar,
        # lane.bottom() is the top edge of the toolbar, so the rover base sits
        # on the red-marked surface line instead of covering icons.
        min_lane = max(self.height() + 8, 62)

        if gap < 8:
            # Auto-hide taskbars may not reserve space; use the lower desktop edge.
            lane = QRect(full.left(), full.bottom() - min_lane + 1, full.width(), min_lane)
            return lane, "unknown"

        if orientation == "bottom":
            surface_y = avail.bottom()
            lane = QRect(full.left(), max(full.top(), surface_y - min_lane + 1), full.width(), min_lane)
        elif orientation == "top":
            surface_y = avail.top()
            lane = QRect(full.left(), surface_y, full.width(), min_lane)
        elif orientation == "left":
            surface_x = avail.left()
            lane = QRect(surface_x, full.top(), max(self.width() + 8, 62), full.height())
        else:
            surface_x = avail.right()
            width = max(self.width() + 8, 62)
            lane = QRect(max(full.left(), surface_x - width + 1), full.top(), width, full.height())

        return lane, orientation

    def _lane_y(self, lane: QRect, orientation: str) -> int:
        if orientation == "top":
            return lane.top() + 1
        return lane.bottom() - self.height() + 1

    def _lane_x(self, lane: QRect, orientation: str) -> int:
        if orientation == "left":
            return lane.left() + 4
        return lane.right() - self.width() - 4

    def _clamp_to_lane(self, point: QPoint) -> QPoint:
        if not self.store.config().taskbar_only:
            screen = QApplication.screenAt(point) or QApplication.primaryScreen()
            if not screen:
                return point
            geo = screen.availableGeometry()
            x = max(geo.left(), min(point.x(), geo.right() - self.width()))
            y = max(geo.top(), min(point.y(), geo.bottom() - self.height()))
            return QPoint(x, y)

        lane, orientation = self._taskbar_lane()
        if lane.isNull():
            return point
        margin = 4
        if orientation in {"bottom", "top", "unknown"}:
            x = max(lane.left() + margin, min(point.x(), lane.right() - self.width() - margin))
            y = self._lane_y(lane, orientation)
        else:
            x = self._lane_x(lane, orientation)
            y = max(lane.top() + margin, min(point.y(), lane.bottom() - self.height() - margin))
        return QPoint(x, y)

    def snap_to_taskbar_lane(self) -> None:
        if self.store.config().taskbar_only and not self.is_dragging:
            self.move(self._clamp_to_lane(self.pos()))

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.scale(self.visual_scale, self.visual_scale)
        painter.setPen(Qt.NoPen)
        self._draw_shadow(painter)
        self._update_big_parachute_overlay()
        self._draw_robot(painter)
        self._draw_reaction_effects(painter)

    def _update_big_parachute_overlay(self) -> None:
        try:
            if self.fall_mode == "parachute" and self.isVisible():
                self.parachute_overlay.show_for_pet(self.frameGeometry(), self.float_phase)
            else:
                self.parachute_overlay.hide()
        except RuntimeError:
            pass

    def _draw_parachute(self, p: QPainter) -> None:
        p.save()
        phase = math.sin(self.float_phase * 2.2)
        # Big canopy: roughly 2x the rover body width, hanging clearly above it.
        canopy_top_y = -34 + phase * 2.2
        canopy = QPainterPath()
        canopy.moveTo(52, 18 + canopy_top_y)
        canopy.cubicTo(86, -22 + canopy_top_y, 254, -22 + canopy_top_y, 288, 18 + canopy_top_y)
        canopy.lineTo(270, 42 + canopy_top_y)
        canopy.cubicTo(234, 28 + canopy_top_y, 106, 28 + canopy_top_y, 70, 42 + canopy_top_y)
        canopy.closeSubpath()
        grad = QLinearGradient(QPointF(52, -8 + canopy_top_y), QPointF(288, 44 + canopy_top_y))
        grad.setColorAt(0, QColor(255, 241, 157, 236))
        grad.setColorAt(0.55, QColor(255, 188, 98, 236))
        grad.setColorAt(1, QColor(255, 126, 73, 236))
        p.setBrush(grad)
        p.setPen(QPen(QColor(130, 72, 45, 190), 1.8))
        p.drawPath(canopy)

        # Hanging lines/threads attached to the upper body, not merged into it.
        p.setPen(QPen(QColor(108, 92, 78, 185), 1.25, Qt.SolidLine, Qt.RoundCap))
        attach = [(78, 44 + canopy_top_y), (112, 38 + canopy_top_y), (148, 34 + canopy_top_y),
                  (192, 34 + canopy_top_y), (228, 38 + canopy_top_y), (262, 44 + canopy_top_y)]
        body = [(126, 76), (142, 82), (156, 86), (184, 86), (198, 82), (214, 76)]
        for (sx, sy), (ex, ey) in zip(attach, body):
            p.drawLine(QPointF(sx, sy), QPointF(ex, ey))

        # Small vent lines on the canopy for a more real parachute feel.
        p.setPen(QPen(QColor(143, 92, 50, 95), 1.0))
        for x in (92, 132, 172, 212, 252):
            p.drawLine(QPointF(x, 2 + canopy_top_y), QPointF(x, 38 + canopy_top_y))
        p.restore()

    def _draw_shadow(self, p: QPainter) -> None:
        p.save()
        p.setBrush(QColor(0, 0, 0, 42))
        p.drawEllipse(QRectF(88, 244, 165, 24))
        p.restore()

    def _draw_robot(self, p: QPainter) -> None:
        # Keep the base planted on the toolbar edge. Only the upper body/head gets a tiny living sway.
        upper_sway = 1.6 * math.sin(self.float_phase * 0.85)
        shake = 0.0
        if self.expression == "scared":
            shake = 3.0 * math.sin(self.float_phase * 13.0)

        p.save()
        p.translate(BASE_W / 2, 0)
        if self._facing_left:
            p.scale(-1, 1)
        p.translate(-BASE_W / 2 + shake, 0)

        # Grounded shadow directly under the treads.
        p.setBrush(QColor(0, 0, 0, 50))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(72, 251, 205, 20))

        # Tracks: angled, reference-like compact crawler feet.
        self._draw_track(p, QRectF(83, 214, 78, 43), tilt=-8, phase_offset=0.0)
        self._draw_track(p, QRectF(185, 214, 78, 43), tilt=8, phase_offset=1.7)

        # Rear and side linkage wheels.
        p.setBrush(QColor("#595a58"))
        p.setPen(QPen(QColor("#292b2d"), 2.2))
        for cx, cy, r in [(118, 231, 11), (143, 236, 10), (204, 236, 10), (238, 231, 13)]:
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setBrush(QColor("#303234"))
            p.drawEllipse(QPointF(cx, cy), max(3, r * 0.32), max(3, r * 0.32))
            p.setBrush(QColor("#595a58"))

        # Arms first so the body sits in front. LLM controls pose.
        arm_swing = 4.0 * math.sin(self.float_phase * 1.5)
        if self.expression == "cleaning" or self.left_arm_pose == "collect" or self.right_arm_pose == "collect":
            arm_swing = 14.0 * math.sin(self.float_phase * 6.0)
        left_end = QPointF(72, 191 + arm_swing)
        right_end = QPointF(270, 180 - arm_swing * 0.35)
        left_angle = -22
        right_angle = 18
        if self.left_arm_pose == "wave":
            left_end = QPointF(63, 150 + 8 * math.sin(self.float_phase * 5.0)); left_angle = -42
        elif self.left_arm_pose == "point":
            left_end = QPointF(55, 175); left_angle = -8
        elif self.left_arm_pose == "shy":
            left_end = QPointF(126, 194); left_angle = 20
        elif self.left_arm_pose == "tired":
            left_end = QPointF(92, 219); left_angle = -10
        elif self.left_arm_pose == "collect":
            left_end = QPointF(84, 213 + 4 * math.sin(self.float_phase * 4)); left_angle = -30
        elif self.left_arm_pose == "cheer":
            left_end = QPointF(72, 166); left_angle = -35
        if self.right_arm_pose == "wave":
            right_end = QPointF(283, 142 + 8 * math.sin(self.float_phase * 5.0)); right_angle = 46
        elif self.right_arm_pose == "point":
            right_end = QPointF(291, 166); right_angle = 10
        elif self.right_arm_pose == "shy":
            right_end = QPointF(198, 195); right_angle = -18
        elif self.right_arm_pose == "tired":
            right_end = QPointF(246, 218); right_angle = 10
        elif self.right_arm_pose in {"collect", "hold"}:
            right_end = QPointF(267, 205 + 3 * math.sin(self.float_phase * 3)); right_angle = 30
        elif self.right_arm_pose == "cheer":
            right_end = QPointF(273, 156); right_angle = 35
        p.setPen(QPen(QColor("#636567"), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(113, 169 + upper_sway), left_end)
        p.drawLine(QPointF(232, 166 + upper_sway), right_end)
        p.setPen(QPen(QColor("#343638"), 2, Qt.SolidLine, Qt.RoundCap))
        self._draw_claw(p, QPointF(left_end.x() - 9, left_end.y() + 3), left_angle)
        self._draw_claw(p, QPointF(right_end.x() + 8, right_end.y() + 2), right_angle)
        if self.right_arm_pose == "hold_plant":
            self._draw_tiny_plant(p, QPointF(right_end.x() + 18, right_end.y() - 10))

        # Body: angled orange compactor body, with the reference-like slanted top lip.
        p.save()
        p.translate(0, upper_sway)
        body_path = QPainterPath()
        body_path.moveTo(104, 134)
        body_path.lineTo(221, 126)
        body_path.lineTo(250, 210)
        body_path.lineTo(95, 225)
        body_path.lineTo(90, 155)
        body_path.closeSubpath()

        body_grad = QLinearGradient(QPointF(100, 126), QPointF(250, 225))
        body_grad.setColorAt(0, QColor("#ffb136"))
        body_grad.setColorAt(0.42, QColor("#f28a16"))
        body_grad.setColorAt(1, QColor("#bd5d12"))
        p.setBrush(body_grad)
        p.setPen(QPen(QColor("#5a351d"), 3))
        p.drawPath(body_path)
        if self.expression in {"angry", "irritated", "frustrated"}:
            pulse = int(70 + 45 * (0.5 + 0.5 * math.sin(self.float_phase * 9.0)))
            p.setBrush(QColor(255, 58, 46, pulse))
            p.setPen(Qt.NoPen)
            p.drawPath(body_path)

        # Top rim and open-compactor lip.
        rim_path = QPainterPath()
        rim_path.moveTo(96, 135)
        rim_path.lineTo(228, 121)
        rim_path.lineTo(236, 134)
        rim_path.lineTo(101, 149)
        rim_path.closeSubpath()
        p.setBrush(QColor("#f7a11e"))
        p.setPen(QPen(QColor("#5c361d"), 2.3))
        p.drawPath(rim_path)
        p.setPen(QPen(QColor("#ffe28f"), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(111, 138), QPointF(205, 128))

        # Front grey grille and small lights.
        panel_path = QPainterPath()
        panel_path.moveTo(117, 154)
        panel_path.lineTo(188, 148)
        panel_path.lineTo(198, 189)
        panel_path.lineTo(119, 194)
        panel_path.closeSubpath()
        p.setBrush(QColor(54, 63, 65, 210))
        p.setPen(QPen(QColor(30, 36, 38, 210), 2))
        p.drawPath(panel_path)
        p.setPen(QPen(QColor(150, 154, 148, 160), 1.3))
        for x in [130, 143, 156, 169, 182]:
            p.drawLine(QPointF(x, 158), QPointF(x + 4, 187))
        p.setPen(Qt.NoPen)
        for i, color in enumerate(["#b9f59b", "#f4dc6b", "#8edbff"]):
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(129 + i * 23, 164, 7.5, 7.5))

        # Right side panel with hazard stripe.
        side_path = QPainterPath()
        side_path.moveTo(198, 147)
        side_path.lineTo(236, 139)
        side_path.lineTo(245, 193)
        side_path.lineTo(209, 199)
        side_path.closeSubpath()
        p.setBrush(QColor("#d87912"))
        p.setPen(QPen(QColor("#62350f"), 2))
        p.drawPath(side_path)
        p.setPen(QPen(QColor("#303234"), 7, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(210, 163), QPointF(238, 157))
        p.drawLine(QPointF(216, 181), QPointF(243, 176))
        p.setPen(QPen(QColor("#e6e0d1"), 5, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(218, 161), QPointF(229, 183))

        # Rust scuffs and dents.
        p.setBrush(QColor(103, 49, 22, 100))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(105, 143, 25, 11))
        p.drawEllipse(QRectF(214, 198, 23, 9))
        p.drawRoundedRect(QRectF(94, 166, 9, 31), 4, 4)
        p.setPen(QPen(QColor(255, 224, 138, 80), 1.0))
        p.drawLine(QPointF(112, 205), QPointF(142, 199))
        p.drawLine(QPointF(207, 132), QPointF(226, 147))
        p.restore()

        # Neck, hydraulic struts, and cable.
        p.setPen(QPen(QColor("#454648"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(164, 133 + upper_sway), QPointF(158, 108 + upper_sway))
        p.drawLine(QPointF(180, 132 + upper_sway), QPointF(194, 104 + upper_sway))
        p.setBrush(QColor("#85817b"))
        p.setPen(QPen(QColor("#444648"), 2))
        p.drawEllipse(QRectF(156, 119 + upper_sway, 26, 22))
        p.setPen(QPen(QColor("#202326"), 2.2, Qt.SolidLine, Qt.RoundCap))
        cable = QPainterPath()
        cable.moveTo(179, 128 + upper_sway)
        cable.cubicTo(196, 137 + upper_sway, 216, 130 + upper_sway, 215, 108 + upper_sway)
        p.drawPath(cable)

        # Binocular head: two grey cylinders, large and tilted like the provided reference.
        p.save()
        pivot = QPointF(176, 94 + upper_sway)
        p.translate(pivot)
        p.rotate(-8 + self.head_angle)
        p.translate(-pivot)
        p.setPen(QPen(QColor("#393b3e"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(166, 113 + upper_sway), QPointF(147, 84 + upper_sway))
        p.drawLine(QPointF(183, 111 + upper_sway), QPointF(209, 78 + upper_sway))
        p.setBrush(QColor("#8d8880"))
        p.setPen(QPen(QColor("#3a3c3f"), 2))
        p.drawRoundedRect(QRectF(151, 92 + upper_sway, 48, 15), 7, 7)
        self._draw_antenna(p, QPointF(137, 46 + upper_sway), side=-1)
        self._draw_antenna(p, QPointF(204, 42 + upper_sway), side=1)
        left_eye_center = QPointF(137, 73 + upper_sway)
        right_eye_center = QPointF(204, 68 + upper_sway)
        self._draw_eye_lens(p, left_eye_center, left=True, angle=-11)
        self._draw_eye_lens(p, right_eye_center, left=False, angle=-7)
        self._draw_big_floating_eyebrows(p, left_eye_center, right_eye_center)
        p.restore()

        if self.expression == "cleaning":
            p.setPen(QPen(QColor(218, 209, 181, 165), 3.5, Qt.SolidLine, Qt.RoundCap))
            sweep_y = 205 + arm_swing * 0.25
            p.drawLine(QPointF(48, sweep_y), QPointF(93, sweep_y + 6))
            p.drawLine(QPointF(51, sweep_y + 8), QPointF(88, sweep_y + 13))

        p.restore()

    def _draw_big_floating_eyebrows(self, p: QPainter, left_center: QPointF, right_center: QPointF) -> None:
        # Large detached brows are the main emotion carriers. They sit above the eye housings,
        # not on the antenna tips, so they read clearly even at 33% scale.
        pose = self.eyebrow_pose or self.expression
        if self.expression == "dizzy":
            pose = "dizzy"
        elif self.expression == "scared" and pose in {"happy", "flat"}:
            pose = "worried"
        elif self.expression == "surprised" and pose in {"happy", "flat"}:
            pose = "surprised"
        elif self.expression == "love" and pose in {"happy", "flat"}:
            pose = "love"
        self._draw_one_big_brow(p, QPointF(left_center.x(), left_center.y() - 38), True, pose)
        self._draw_one_big_brow(p, QPointF(right_center.x(), right_center.y() - 38), False, pose)

    def _draw_one_big_brow(self, p: QPainter, center: QPointF, left: bool, pose: str) -> None:
        p.save()
        p.translate(center)
        # Slight independent bob so they feel like expressive floating brows.
        p.translate(0, 2.2 * math.sin(self.float_phase * 2.1 + (0 if left else 0.8)))
        phase = self.float_phase
        # Outlined black brow with a warm highlight, readable on dark desktops.
        def line(a: QPointF, b: QPointF, width: float = 15.0) -> None:
            # Big detached yellow-black brows, deliberately eye-sized at 33%.
            p.setPen(QPen(QColor(255, 225, 72, 230), width + 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(a, b)
            p.setPen(QPen(QColor(24, 22, 20, 250), width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(a, b)
            p.setPen(QPen(QColor(255, 211, 56, 230), max(3.0, width * 0.26), Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(a.x(), a.y() - width * 0.16), QPointF(b.x(), b.y() - width * 0.16))

        def arc(rect: QRectF, start: int, span: int, width: float = 14.0) -> None:
            p.setPen(QPen(QColor(255, 225, 72, 220), width + 5, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, start * 16, span * 16)
            p.setPen(QPen(QColor(24, 22, 20, 250), width, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, start * 16, span * 16)
            p.setPen(QPen(QColor(255, 211, 56, 225), max(3.0, width * 0.24), Qt.SolidLine, Qt.RoundCap))
            r2 = QRectF(rect.left(), rect.top() - 2, rect.width(), rect.height())
            p.drawArc(r2, start * 16, span * 16)

        if pose == "happy":
            arc(QRectF(-25, -4, 50, 24), 28, 124)
        elif pose == "curious":
            lift = -7 if left else 1
            line(QPointF(-24, lift + 6), QPointF(24, lift - 4), 14.0)
        elif pose == "surprised":
            arc(QRectF(-23, -12, 46, 28), 28, 126, 15.0)
            p.setBrush(QColor(24, 22, 20, 230))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(25, -5), 3.5, 3.5)
        elif pose == "worried":
            line(QPointF(-24, -4 if left else 7), QPointF(24, 7 if left else -4), 15.0)
        elif pose == "focused":
            line(QPointF(-24, 7 if left else -5), QPointF(24, -5 if left else 7), 15.0)
        elif pose in {"angry", "irritated", "frustrated"}:
            line(QPointF(-25, -6 if left else 9), QPointF(25, 9 if left else -6), 16.0)
            if pose in {"irritated", "frustrated"}:
                p.setBrush(QColor(255, 75, 45, 210))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(25 if left else -25, -10), 3.5, 3.5)
        elif pose == "sad":
            line(QPointF(-24, 8 if left else -5), QPointF(24, -5 if left else 8), 14.0)
        elif pose == "sleepy":
            line(QPointF(-21, 5), QPointF(21, 5), 13.0)
        elif pose == "love":
            self._draw_heart(p, 0, 2, 13, QColor(255, 105, 145, 230))
        elif pose == "dizzy":
            arc(QRectF(-20, -12 + 2 * math.sin(phase * 4), 40, 24), 30, 300, 13.0)
        elif pose == "mischief":
            line(QPointF(-24, 5 if left else -4), QPointF(24, -8 if left else 3), 15.0)
            p.setBrush(QColor(255, 199, 64, 180))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(24 if left else -24, -10), 3, 3)
        else:
            line(QPointF(-22, 0), QPointF(22, 0), 13.0)
        p.restore()

    def _draw_antenna(self, p: QPainter, base: QPointF, side: int) -> None:
        p.save()
        wig = 0.0
        pose = self.antenna_pose
        if pose in {"wiggle", "alert", "heart"}:
            wig = 7.0 * math.sin(self.float_phase * 5.0 + side)
        height = 24
        bend = 10 * side
        if pose == "droop":
            height = 10; bend = 18 * side
        elif pose == "perked":
            height = 29; bend = 6 * side
        elif pose == "heart":
            height = 32; bend = 5 * side
        elif pose == "alert":
            height = 34; bend = 4 * side
        p.setPen(QPen(QColor(37, 39, 41, 220), 5, Qt.SolidLine, Qt.RoundCap))
        path = QPainterPath()
        path.moveTo(base)
        path.cubicTo(base.x() + bend * 0.3, base.y() - height * 0.45, base.x() + bend + wig, base.y() - height, base.x() + bend * 1.35 + wig, base.y() - height * 1.05)
        p.drawPath(path)
        p.setBrush(QColor(45, 47, 50, 235))
        p.setPen(QPen(QColor(20, 22, 24, 220), 1))
        p.drawEllipse(QPointF(base.x() + bend * 1.35 + wig, base.y() - height * 1.05), 5.0, 4.0)
        p.restore()

    def _draw_tiny_plant(self, p: QPainter, center: QPointF) -> None:
        p.save()
        p.setBrush(QColor(126, 83, 46, 230))
        p.setPen(QPen(QColor(75, 50, 30, 220), 1))
        p.drawRoundedRect(QRectF(center.x() - 7, center.y() + 4, 14, 10), 3, 3)
        p.setBrush(QColor(86, 173, 75, 230))
        p.setPen(QPen(QColor(45, 108, 48, 220), 1.2))
        p.drawEllipse(QPointF(center.x() - 4, center.y()), 5, 8)
        p.drawEllipse(QPointF(center.x() + 5, center.y() - 3), 5, 8)
        p.restore()

    def _draw_track(self, p: QPainter, rect: QRectF, tilt: float, phase_offset: float) -> None:
        p.save()
        p.translate(rect.center())
        p.rotate(tilt)
        p.translate(-rect.center())
        track = QPainterPath()
        track.moveTo(rect.left() + 7, rect.top() + 6)
        track.lineTo(rect.right() - 9, rect.top())
        track.quadTo(rect.right() + 5, rect.center().y(), rect.right() - 8, rect.bottom())
        track.lineTo(rect.left() + 6, rect.bottom() - 1)
        track.quadTo(rect.left() - 8, rect.center().y(), rect.left() + 7, rect.top() + 6)
        p.setBrush(QColor("#303235"))
        p.setPen(QPen(QColor("#17191a"), 2.3))
        p.drawPath(track)

        p.setPen(QPen(QColor("#4d5051"), 3.2, Qt.SolidLine, Qt.RoundCap))
        steps = 7
        for i in range(steps):
            x = rect.left() + 9 + i * (rect.width() - 18) / max(1, steps - 1)
            y1 = rect.top() + 5 + 2.5 * math.sin(self.wheel_phase + phase_offset + i)
            p.drawLine(QPointF(x, y1), QPointF(x + 6, rect.bottom() - 5))
        p.restore()

    def _draw_claw(self, p: QPainter, center: QPointF, angle: float) -> None:
        p.save()
        p.translate(center)
        p.rotate(angle)
        p.setBrush(QColor("#7b7d80"))
        p.setPen(QPen(QColor("#35383b"), 1.8))
        p.drawRoundedRect(QRectF(-9, -6, 18, 12), 4, 4)
        p.setPen(QPen(QColor("#56595c"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-5, 1), QPointF(-15, 9))
        p.drawLine(QPointF(5, 1), QPointF(15, 9))
        p.setPen(QPen(QColor("#2d3033"), 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-15, 9), QPointF(-20, 4))
        p.drawLine(QPointF(15, 9), QPointF(20, 4))
        p.restore()

    def _draw_eye_lens(self, p: QPainter, center: QPointF, left: bool, angle: float = 0.0) -> None:
        blink = self.blink_amount > 0.4 or self.expression == "sleepy" or self.eye_focus in {"sleepy", "closed"}

        p.save()
        p.translate(center)
        p.rotate(angle)
        lens_outer = QRectF(-33, -28, 66, 56)
        lens_inner = QRectF(-23, -18, 46, 36)

        body_grad = QLinearGradient(lens_outer.topLeft(), lens_outer.bottomRight())
        body_grad.setColorAt(0, QColor("#d3d3cf"))
        body_grad.setColorAt(0.45, QColor("#82817f"))
        body_grad.setColorAt(1, QColor("#4a4d50"))
        p.setBrush(body_grad)
        p.setPen(QPen(QColor("#2b2e31"), 3))
        p.drawRoundedRect(lens_outer, 18, 18)

        # Outer ring and small screws.
        p.setBrush(QColor(212, 211, 205, 185))
        p.setPen(QPen(QColor("#34373a"), 1.5))
        p.drawEllipse(QRectF(-26, -21, 52, 42))
        p.setBrush(QColor("#36393c"))
        p.setPen(Qt.NoPen)
        for sx, sy in [(-21, -15), (21, -15), (-21, 15), (21, 15)]:
            p.drawEllipse(QPointF(sx, sy), 2.0, 2.0)

        # Cute enamel-pin-style face: bright white eye plate + huge glossy pupil.
        plate_grad = QRadialGradient(QPointF(-7, -8), 30)
        plate_grad.setColorAt(0, QColor(255, 255, 255, 250))
        plate_grad.setColorAt(0.72, QColor(232, 247, 250, 238))
        plate_grad.setColorAt(1, QColor(177, 200, 205, 230))
        p.setBrush(plate_grad)
        p.setPen(QPen(QColor("#18222a"), 2.2))
        p.drawEllipse(lens_inner)

        if blink:
            p.setPen(QPen(QColor("#c8f8ff"), 4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(-14, 0), QPointF(14, 0))
            self._draw_local_eyebrow(p, left)
            p.restore()
            return

        radius = 12.5
        if self.expression in {"surprised", "scared", "excited", "dizzy"}:
            radius = 15.0
        elif self.expression == "watching":
            radius = 13.8
        elif self.expression == "sleepy":
            radius = 10.0

        pupil_offset_x = 0.0
        pupil_offset_y = 0.0
        if self.expression == "curious":
            pupil_offset_x = -3.2 if left else 3.2
            pupil_offset_y = -1.3 if left else 1.2
        elif self.expression == "scared":
            pupil_offset_x = -3.5 if left else 3.5
        elif self.expression == "cleaning":
            pupil_offset_x = 2.5 * math.sin(self.float_phase * 5.0)

        focus = self.eye_focus
        if focus in {"mouse", "butterfly", "basketball", "ball", "right", "bin", "trash_bin"}:
            pupil_offset_x += 6.0
        elif focus in {"side"}:
            pupil_offset_x += 4.2
            pupil_offset_y += 0.8
        elif focus in {"left", "sofa", "tv_sofa", "tv"}:
            pupil_offset_x -= 6.0
        elif focus in {"nearest_debris", "debris_pile", "trash", "debris", "down"}:
            pupil_offset_y += 5.5
        elif focus in {"screen", "up"}:
            pupil_offset_y -= 5.5
        elif focus == "user":
            pupil_offset_x += -1.8 if left else 1.8
            pupil_offset_y -= 1.2
        elif focus in {"closed", "sleepy"}:
            blink = True

        if self.expression == "dizzy":
            p.setPen(QPen(QColor(30, 39, 45, 235), 2.6, Qt.SolidLine, Qt.RoundCap))
            swirl = QPainterPath()
            swirl.moveTo(pupil_offset_x - 10, pupil_offset_y)
            for i in range(1, 18):
                a = i * 0.72 + self.float_phase * 2.0
                r = max(1.5, 11.5 - i * 0.55)
                swirl.lineTo(pupil_offset_x + math.cos(a) * r, pupil_offset_y + math.sin(a) * r * 0.8)
            p.drawPath(swirl)
            p.setBrush(QColor(255, 255, 255, 210))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(pupil_offset_x - 7, pupil_offset_y - 7), 2.8, 2.8)
            self._draw_local_eyebrow(p, left)
            p.restore()
            return

        pupil_grad = QRadialGradient(QPointF(pupil_offset_x - radius * 0.35, pupil_offset_y - radius * 0.45), radius * 1.5)
        pupil_grad.setColorAt(0, QColor(77, 92, 105, 245))
        pupil_grad.setColorAt(0.42, QColor(20, 28, 34, 245))
        pupil_grad.setColorAt(1, QColor(3, 7, 10, 245))
        p.setBrush(pupil_grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(pupil_offset_x, pupil_offset_y), radius, radius * 1.08)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawEllipse(QPointF(pupil_offset_x - radius * 0.38, pupil_offset_y - radius * 0.48), max(3.4, radius * 0.30), max(3.4, radius * 0.30))
        p.setBrush(QColor(192, 240, 255, 190))
        p.drawEllipse(QPointF(pupil_offset_x + radius * 0.36, pupil_offset_y + radius * 0.38), max(1.8, radius * 0.13), max(1.8, radius * 0.13))

        if self.expression == "happy":
            p.setPen(QPen(QColor("#d8f9ff"), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(-12, -8, 24, 18), 200 * 16, 140 * 16)
        elif self.expression == "love":
            self._draw_heart(p, -5, -4, 9, QColor("#ff7ba7"))

        self._draw_local_eyebrow(p, left)
        p.restore()

    def _draw_local_eyebrow(self, p: QPainter, left: bool) -> None:
        pose = self.eyebrow_pose or self.expression
        phase = self.float_phase
        p.save()
        p.setPen(QPen(QColor(44, 35, 27, 235), 5.0, Qt.SolidLine, Qt.RoundCap))
        y = -34.0
        x1, x2 = -17.0, 17.0
        if pose == "happy":
            a = -6 if left else 6
            p.drawLine(QPointF(x1, y + a * 0.15), QPointF(x2, y - 4 - a * 0.15))
        elif pose == "curious":
            lift = -8 if left else -2
            p.drawLine(QPointF(x1, y + lift + 4), QPointF(x2, y + lift))
        elif pose == "worried":
            p.drawLine(QPointF(x1, y - 5), QPointF(x2, y + 3)) if left else p.drawLine(QPointF(x1, y + 3), QPointF(x2, y - 5))
        elif pose == "focused":
            p.drawLine(QPointF(x1, y + 2), QPointF(x2, y - 5)) if left else p.drawLine(QPointF(x1, y - 5), QPointF(x2, y + 2))
        elif pose == "angry":
            p.drawLine(QPointF(x1, y - 5), QPointF(x2, y + 4)) if left else p.drawLine(QPointF(x1, y + 4), QPointF(x2, y - 5))
        elif pose == "sad":
            p.drawLine(QPointF(x1, y + 5), QPointF(x2, y - 2)) if left else p.drawLine(QPointF(x1, y - 2), QPointF(x2, y + 5))
        elif pose == "sleepy":
            p.setPen(QPen(QColor(44, 35, 27, 210), 4.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x1 + 2, y + 4), QPointF(x2 - 2, y + 4))
        elif pose == "love":
            self._draw_heart(p, 0, y + 1, 8, QColor(255, 105, 145, 210))
        elif pose == "dizzy":
            p.setPen(QPen(QColor(44, 35, 27, 225), 4.0, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(-12, y - 7 + 2 * math.sin(phase * 4), 24, 13), 25 * 16, 300 * 16)
        else:
            p.drawLine(QPointF(x1, y), QPointF(x2, y))
        p.restore()


    def _draw_reaction_effects(self, p: QPainter) -> None:
        p.save()
        if self.expression == "love":
            for i in range(3):
                phase = self.float_phase * 1.3 + i * 1.7
                x = 112 + i * 55 + 4 * math.sin(phase)
                y = 39 - 9 * math.sin(phase * 0.7)
                self._draw_heart(p, x, y, 13 - i * 1.5, QColor(255, 105, 145, 190))
        elif self.expression == "scared":
            p.setPen(QPen(QColor(170, 220, 255, 180), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(94, 53), QPointF(75, 38))
            p.drawLine(QPointF(245, 55), QPointF(265, 39))
            p.drawLine(QPointF(170, 33), QPointF(170, 12))
        elif self.expression == "excited":
            p.setBrush(QColor(255, 230, 102, 150))
            p.setPen(Qt.NoPen)
            for i in range(4):
                p.drawEllipse(QPointF(88 + i * 45, 42 + 8 * math.sin(self.float_phase + i)), 4, 4)
        elif self.expression == "proud":
            p.setBrush(QColor(150, 230, 150, 145))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(250, 134), 7, 7)
            p.drawEllipse(QPointF(272, 119), 4, 4)
        elif self.expression == "dizzy":
            p.setPen(QPen(QColor(255, 235, 95, 210), 3, Qt.SolidLine, Qt.RoundCap))
            for i in range(3):
                cx = 116 + i * 48
                cy = 38 + 6 * math.sin(self.float_phase * 3 + i)
                p.drawArc(QRectF(cx, cy, 18, 14), int(self.float_phase * 120) * 16, 290 * 16)

        if time.time() < self.emoji_until and self.emoji_effect != "none":
            self._maybe_play_emoji_sound(self.emoji_effect)
            self._draw_emoji_effect(p, self.emoji_effect)
        p.restore()

    def _draw_emoji_effect(self, p: QPainter, effect: str) -> None:
        p.save()
        phase = self.float_phase
        # Make emojis large and detached, roughly butterfly-sized or bigger.
        x = 268 + 9 * math.sin(phase * 1.7)
        y = 44 + 10 * math.sin(phase * 1.05)
        if self.expression == "dizzy":
            x = 252 + 14 * math.sin(phase * 3.1)
            y = 45 + 7 * math.cos(phase * 2.7)
        if effect in {"heart", "💛"}:
            self._draw_heart(p, x, y, 24, QColor(255, 105, 145, 225))
        elif effect in {"sparkle", "✨"}:
            p.setPen(QPen(QColor(255, 228, 90, 230), 3.2, Qt.SolidLine, Qt.RoundCap))
            for i in range(4):
                sx = x - 21 + i * 14
                sy = y + 8 * math.sin(phase + i)
                p.drawLine(QPointF(sx - 6, sy), QPointF(sx + 6, sy))
                p.drawLine(QPointF(sx, sy - 6), QPointF(sx, sy + 6))
        elif effect in {"dizzy", "💫"}:
            p.setPen(QPen(QColor(255, 232, 80, 230), 3.0, Qt.SolidLine, Qt.RoundCap))
            for i in range(3):
                cx = x - 14 + i * 15
                cy = y + 5 * math.sin(phase * 2 + i)
                p.drawArc(QRectF(cx - 7, cy - 7, 14, 14), int((phase * 90 + i * 50) * 16), 280 * 16)
        else:
            symbol = {
                "question": "?", "exclamation": "!", "sweat": "💧", "sleep": "Zz",
                "butterfly": "🦋", "basketball": "🏀", "ball": "🏀", "music": "♪", "?": "?", "!": "!", "🦋": "🦋",
                "♻️": "♻️", "😴": "Zz", "😳": "!", "👀": "👀", "🍿": "🍿", "💧": "💧", "💫": "💫",
                "😂": "😂", "😅": "😅", "😎": "😎", "🌱": "🌱", "📺": "📺", "🗑️": "🗑️",
                "🔍": "🔍", "⚡": "⚡", "🧹": "🧹", "🌟": "🌟", "💤": "Zz", "😵‍💫": "💫",
                "🎵": "♪", "🎶": "♫", "🤭": "🤭", "🙃": "🙃", "🫡": "🫡", "🥹": "🥹", "☕": "☕",
                "🫧": "🫧", "🍃": "🍃", "🪄": "🪄", "🎮": "🎮", "🐾": "🐾", "🛠️": "🛠️", "📌": "📌",
            }.get(effect, str(effect)[:2] if effect else "")
            if symbol:
                p.setPen(QColor(255, 248, 205, 245))
                font = QFont("Segoe UI Emoji", 38 if len(symbol) <= 2 else 30)
                font.setWeight(QFont.Weight.Bold)
                p.setFont(font)
                # Soft shadow for visibility.
                p.setPen(QColor(40, 32, 24, 150))
                p.drawText(QRectF(x - 34 + 2, y - 36 + 2, 74, 62), Qt.AlignCenter, symbol)
                p.setPen(QColor(255, 248, 205, 245))
                p.drawText(QRectF(x - 34, y - 36, 74, 62), Qt.AlignCenter, symbol)
        p.restore()

    def _draw_heart(self, p: QPainter, x: float, y: float, s: float, color: QColor) -> None:
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        path = QPainterPath()
        path.moveTo(x, y + s * 0.35)
        path.cubicTo(x - s, y - s * 0.3, x - s * 0.8, y - s, x, y - s * 0.45)
        path.cubicTo(x + s * 0.8, y - s, x + s, y - s * 0.3, x, y + s * 0.35)
        p.drawPath(path)
        p.restore()

    def _height_above_taskbar_surface(self) -> float:
        lane, orientation = self._taskbar_lane()
        if lane.isNull():
            return 0.0
        if orientation == "top":
            return max(0.0, float(self.y() - self._lane_y(lane, orientation)))
        return max(0.0, float(self._lane_y(lane, orientation) - self.y()))

    def _start_gravity_drop(self, high: bool) -> None:
        self.fall_started_height = self._height_above_taskbar_surface()
        self.fall_mode = "parachute" if high else "fall"
        self.fall_vy = 0.0
        self.fall_vx = random.uniform(-0.8, 0.8) if high else random.uniform(-0.25, 0.25)
        self.target_point = None
        self.current_action = "parachute" if high else "fall"
        self.set_expression("excited" if high else "surprised")
        self._apply_body_controls({
            "antenna": "wiggle" if high else "perked",
            "eyes": "down" if not high else "up",
            "eyebrow": "surprised",
            "emoji": random.choice(["🪂", "😳", "✨", "💨"]),
            "left_arm": "cheer" if high else "point",
            "right_arm": "cheer" if high else "point",
        })
        if high:
            self.parachute_overlay.show_for_pet(self.frameGeometry(), self.float_phase)
            self.show_bubble("hmm!", 1600)
            now = time.time()
            if self.cfg.ai_reactions_enabled and now - self._last_glide_ai_at > 8:
                self._last_glide_ai_at = now
                self._pending_activity_note = {
                    "kind": "parachute_glide",
                    "height_px": int(self.fall_started_height),
                    "instruction": "Wally is gliding back to the taskbar under a tiny parachute. React with excitement using speech only; body controls handle motion.",
                }
                self.request_ai_reaction("parachute_glide_excited_reaction", force=True, use_vision=False)

    def _fall_step(self) -> None:
        lane, orientation = self._taskbar_lane()
        if lane.isNull():
            self.fall_mode = "none"
            self.parachute_overlay.hide()
            return
        landing_y = self._lane_y(lane, orientation)
        if self.fall_mode == "parachute":
            self.fall_vy = min(2.6, self.fall_vy + 0.065)
            self.fall_vx += 0.035 * math.sin(self.float_phase * 1.4)
            self.fall_vx = max(-1.25, min(1.25, self.fall_vx))
        else:
            self.fall_vy = min(7.2, self.fall_vy + 0.34)
            self.fall_vx *= 0.995
        new_x = self.x() + int(round(self.fall_vx))
        if orientation == "top":
            new_y = self.y() - int(round(self.fall_vy)) if self.y() > landing_y else landing_y
            landed = new_y <= landing_y
        else:
            new_y = self.y() + int(round(self.fall_vy)) if self.y() < landing_y else landing_y
            landed = new_y >= landing_y
        self.move(self._clamp_to_lane(QPoint(new_x, new_y)) if landed else QPoint(new_x, new_y))
        if landed:
            self.fall_mode = "none"
            self.parachute_overlay.hide()
            self.fall_vx = 0.0
            self.fall_vy = 0.0
            self.move(self._clamp_to_lane(self.pos()))
            self.set_expression("proud" if self.current_action == "parachute" else "happy")
            self.current_action = "chill"
            self.pause_until = time.time() + 1.2
            self._apply_body_controls({"eyes": "user", "eyebrow": "happy", "emoji": random.choice(["✨", "😎", "🪂"]), "left_arm": "cheer", "right_arm": "wave"})
            self._nudge_mood(excited=10, proud=6, bored=-10)
            self._instant_event_quip("dropped")
            self._remember_action("landed_after_drop", {"mode": "parachute" if self.fall_started_height else "fall", "height": int(self.fall_started_height)})

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_offset = global_pos(event) - self.frameGeometry().topLeft()
            self.drag_start_pos = self.pos()
            self.fall_mode = "none"
            self._drag_press_time = time.time()
            self._drag_pickup_announced = False
            self.set_expression("surprised")
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if self.is_dragging and self.drag_offset is not None:
            self.move(global_pos(event) - self.drag_offset)
            # Announce being lifted once he's clearly off the taskbar.
            if not getattr(self, "_drag_pickup_announced", False) and self._height_above_taskbar_surface() > 46:
                self._drag_pickup_announced = True
                self.set_expression("surprised")
                self._nudge_mood(excited=16, anxious=8, bored=-18, curious=6)
                self._satisfy_need("affection", 14, react=False)
                self._instant_event_quip("picked_up")
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.drag_offset = None
            self.target_point = None
            screen = QApplication.screenAt(global_pos(event)) or QApplication.primaryScreen()
            lifted = self._height_above_taskbar_surface()
            threshold = (screen.geometry().height() * 0.30) if screen else 260
            moved = abs(self.pos().x() - self.drag_start_pos.x()) + abs(self.pos().y() - self.drag_start_pos.y()) if self.drag_start_pos else 0
            quick = time.time() - float(getattr(self, "_drag_press_time", 0.0)) < 0.35
            if lifted > 18:
                # Dropped from a height: the witty landing line fires when he lands.
                self._start_gravity_drop(high=lifted >= threshold)
            elif quick and moved < 8:
                # A tap in place = a poke. He has opinions about being poked.
                self.set_expression("surprised")
                self._nudge_mood(naughty=12, curious=8, irritated=5, bored=-15)
                self._satisfy_need("affection", 10, react=False)
                self._instant_event_quip("poke")
                self.snap_to_taskbar_lane()
            else:
                self.set_expression("happy")
                self.snap_to_taskbar_lane()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self._nudge_mood(playful=14, naughty=10, bored=-15)
            self._instant_event_quip("double_poke", duration_ms=4200)
            self.open_chat()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.bubble.isVisible():
            self.bubble.reposition(self.frameGeometry())
        super().moveEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self._thread_running(self.worker):
            self.set_expression("curious")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if not self._thread_running(self.worker):
            self.set_expression("happy")
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.key() in {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space}:
            self.open_chat()
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)


def global_pos(event: QMouseEvent) -> QPoint:
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()  # type: ignore[attr-defined]


def compact_pet_sentence(text: str, max_words: int = 9, min_words: int = 1, max_len: int = 120) -> str:
    """Compact speech without returning half-sentences.

    If a model ignores the word limit, prefer a complete short sentence or
    return empty so the caller can use a small fallback, rather than clipping
    midway through a thought.
    """
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()
    text = text.replace("\\n", " ").replace("/n", " ").strip()
    if text.strip().lower() in {"/", "\\", "n", "null", "none", "...", "…", "."}:
        return ""
    if text.strip().startswith("{") or '"b"' in text[:120] or '"bubble"' in text[:140]:
        match = re.search(r'"(?:b|bubble|s|speech)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text, flags=re.DOTALL)
        if match:
            try:
                text = bytes(match.group(1), "utf-8").decode("unicode_escape")
            except Exception:
                text = match.group(1)
        else:
            return ""
    text = re.sub(r"\s+", " ", text).strip().strip('"')
    text = re.sub(r'^.*?bubble[\'\"]?\s*[:=]\s*[\'\"]?', "", text, flags=re.IGNORECASE)
    text = text.strip(" {}[],'\"")
    if not text:
        return ""
    max_words = max(4, min(24, int(max_words or 9)))

    def word_count(s: str) -> int:
        return len([w for w in s.split() if w.strip()])

    # First prefer any complete sentence within limit.
    candidates = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        part = part.strip(" ,;:-")
        if part:
            candidates.append(part)
    if not candidates:
        candidates = [text]
    for cand in candidates:
        if min_words <= word_count(cand) <= max_words:
            if len(cand) > max_len:
                continue
            return cand

    # Try a short clause if it is complete enough and does not end with a connector.
    stop_end = {"and", "or", "but", "to", "for", "with", "of", "the", "a", "an", "is", "are", "was", "were", "be"}
    for sep in [",", ";", "—", "-"]:
        clause = text.split(sep, 1)[0].strip(" ,;:-")
        words = clause.split()
        if min_words <= len(words) <= max_words and words[-1].lower().strip(".,!?") not in stop_end:
            return clause if clause.endswith(("!", "?", ".")) else clause + "."

    # Too long and no clean sentence: reject instead of showing a chopped line.
    return ""


def shorten_for_bubble(text: str, prefix: str = "", max_len: int = 190) -> str:
    clean = re.sub(r"\s+", " ", text.strip())
    available = max(10, max_len - len(prefix))
    if len(clean) > available:
        clean = clean[: max(0, available)].rstrip()
    return prefix + clean


def random_leaf_color() -> str:
    return random.choice(["#9c7f2d", "#b06d2f", "#8f8b35", "#c0912e", "#7b8c3b"])


def get_active_window_title() -> str:
    try:
        if sys.platform.startswith("win"):
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value
        if sys.platform == "darwin":
            script = (
                'tell application "System Events"\n'
                'set frontApp to name of first application process whose frontmost is true\n'
                'try\n'
                'set winTitle to name of front window of first application process whose frontmost is true\n'
                'on error\n'
                'set winTitle to ""\n'
                'end try\n'
                'return frontApp & " - " & winTitle\n'
                'end tell'
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
            return result.stdout.strip()
        for command in (["xdotool", "getactivewindow", "getwindowname"], ["bash", "-lc", "xprop -root _NET_ACTIVE_WINDOW 2>/dev/null"]):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=1.5)
                out = result.stdout.strip()
                if out and "_NET_ACTIVE_WINDOW" not in out:
                    return out
            except Exception:
                continue
    except Exception:
        return ""
    return ""


def infer_media_hint(title: str) -> str:
    t = title.lower()
    if "youtube" in t or "youtu.be" in t:
        return "youtube"
    if "netflix" in t:
        return "netflix"
    if any(word in t for word in [
        "prime video", "disney+", "disney plus", "hulu", "hotstar", "hbo", "max",
        "vimeo", "twitch", "crunchyroll", "plex", "jellyfin", "vlc media player",
        "vlc", "mpv", "mpc-hc", "potplayer", "kodi", "apple tv", "peacock", "video",
        "player", "- watch", "watching", "movie", "episode", "ep.", "s01", "s02",
        ".mkv", ".mp4", ".avi", "1080p", "720p",
    ]):
        return "video_player"
    if any(word in t for word in ["chrome", "edge", "firefox", "safari"]):
        return "browser"
    return ""


def infer_scene_guess(title: str, screen_summary: Optional[Dict[str, object]]) -> str:
    t = title.lower()
    if any(word in t for word in ["horror", "scary", "haunted", "ghost", "monster", "thriller"]):
        return "spooky_or_dark"
    if any(word in t for word in ["romance", "romantic", "love", "cute", "wedding", "kiss"]):
        return "warm_or_cute"
    if not screen_summary or not bool(screen_summary.get("available", False)):
        return "normal"
    try:
        dark_ratio = float(screen_summary.get("dark_ratio", 0.0))
        brightness = float(screen_summary.get("brightness", 120.0))
        warmth = float(screen_summary.get("warmth", 0.0))
        motion_delta = float(screen_summary.get("motion_delta", 0.0))
        tone = str(screen_summary.get("tone", ""))
    except (TypeError, ValueError):
        return "normal"
    if dark_ratio > 0.55 and brightness < 75:
        return "spooky_or_dark"
    if tone == "warm" and warmth > 30 and brightness > 100:
        return "warm_or_cute"
    if motion_delta > 22:
        return "action_or_fast_change"
    return "normal"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)

    window = PetWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
