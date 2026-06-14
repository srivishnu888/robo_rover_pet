# Robo Rover Pet

`Robo Rover Pet` is a virtual desktop pet built to distract you from stress, keep your desktop feeling alive, and add playful interaction to long work sessions. It lives near your taskbar, acts autonomously, comments on what you type by using a local LLM, reacts to how much work you are doing, nudges you to take breaks, helps with quick reminders, and turns your desktop into something more fun and less tense.

The pet's public project name is `Robo Rover Pet`. Inside the app, the character currently refers to itself as `Wally`, which is the rover's in-app persona.

## What It Does

- Runs as a floating autonomous desktop pet with tray icon support.
- Uses a local Ollama model to make short in-character comments about your typing and desktop activity for fun interaction.
- Reacts to mouse movement, typing, scrolling, workload pressure, and optional screenshot summaries.
- Tries to relieve stress by interrupting work with playful reactions and break nudges.
- Supports quick reminder parsing and local reminder alerts.
- Opens a mini chat and a larger chat window for commands and conversation.
- Performs playful actions like watching TV, kicking a basketball, chasing butterflies, singing, dancing, and cleaning debris.
- Stores settings locally in `~/.robo_rover_pet/settings_v8_33.json`.

## Requirements

- Python 3.10+
- Ollama installed locally
- A local Ollama model, default: `ministral-3:3b`
- Desktop OS supported by Qt
  - Windows is the most directly supported path in the current code
  - macOS and Linux may work, but may require permissions or extra desktop utilities

## Python Dependencies

Runtime dependencies from [requirements.txt](requirements.txt):

- `PySide6`
- `requests`
- `pynput` for global typing/scroll awareness

Optional:

- `pyttsx3` for spoken pet replies

Build dependency from [requirements-build.txt](requirements-build.txt):

- `pyinstaller`

## Quick Start

### Standard Run

```powershell
cd C:\Projects\research\robo_rover_pet\robo_rover_pet
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
ollama pull ministral-3:3b
ollama serve
python run.py
```

### Install As a Local Python App

This repo now includes Python packaging metadata, so you can install it like an app:

```powershell
cd C:\Projects\research\robo_rover_pet\robo_rover_pet
python -m pip install .
robo-rover-pet
```

If you want isolated global installation, `pipx` is the cleanest option:

```powershell
pipx install .
robo-rover-pet
```

## Controls

- Double-click the pet: open chat
- Left-drag the pet: move it
- Drop it high above the taskbar: parachute/fall behavior
- Press `Enter`, `Space`, or double-click when focused: open chat
- Use the tray icon or right-click menu for quick actions and toggles

## Mini-Chat Commands

The app has a lightweight local command router before it falls back to Ollama chat. These commands are explicitly supported in the current codebase:

- `watch tv`
- `go sofa`
- `tv break`
- `clean`
- `clean up`
- `clean this mess`
- `kick the ball`
- `play basketball`
- `send butterfly`
- `release butterfly`
- `send butterflies`
- `send wind`
- `send leaves`
- `send debris`
- `throw trash for attention`
- `list reminders`
- `show reminders`
- `clear reminders`
- `delete reminders`
- `skills`
- `what can you do`

Reminder examples:

- `remind me in 10 secs to stretch`
- `remind me in 5 minutes to check the build`
- `remind me at 5pm to call home`
- `remind me tomorrow at 9 to send the report`

## Tray And Context Menu Actions

The tray icon and pet context menu expose actions such as:

- `Chat with Wally`
- `Settings`
- `React to screen now`
- `Test Ollama connection/status`
- `Show last LLM decision`
- `Drop leaves/paper`
- `Release a butterfly`
- `Show pending reminders`
- `Show Pet`
- `Hide`
- `Quit`

They also expose toggles for:

- roaming
- taskbar-only movement
- debris cleaning
- AI reactions
- screen awareness
- screenshot reactions
- always-on-top
- text-to-speech

## Ollama Notes

- The app is local-first and expects Ollama at `http://127.0.0.1:11434` by default.
- If Ollama is offline, some local utility behavior still works, but AI personality features, richer reactions, and model-based reminder parsing degrade or stop.
- If the selected model is missing, the code expects you to run:

```powershell
ollama pull ministral-3:3b
```

You can also switch models in settings. The UI already includes options like:

- `ministral-3:3b`
- `qwen3-vl:2b`
- `qwen2.5:1.5b-instruct`
- `smollm2:1.7b-instruct`
- `gemma2:2b`
- `phi3:mini`
- `llama3.2:3b`

## Privacy

- This project is intended for local use.
- Ollama calls are sent to your local Ollama server, not a cloud API by default.
- When screenshot reactions are enabled, the app may send an occasional resized screenshot to the local Ollama server.

## Building

### Windows

```powershell
build_windows.bat
```

### macOS / Linux

```bash
./build_macos_linux.sh
```

These build scripts use PyInstaller to produce a single-file app build.

## Project Status

This project is already fun and feature-rich, but it is still best described as an experimental desktop pet rather than a polished end-user product. The codebase contains a lot of personality and behavior logic, and the public documentation is now aligned to that reality.

## License

MIT. See [LICENSE](LICENSE).
