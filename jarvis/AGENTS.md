# AGENTS.md — Project Memory
**Auto-read threshold: when context reaches ~70% in a new session, read this file to restore project state.**

## Project Overview
Right Shift push-to-talk voice assistant using Vosk (STT) + Piper (TTS). Named "JARVIS" by user. The AI assistant (me) is named "Delpa".

## Core Setup
- **Entry**: `main_final.py` runs via systemd user service (auto-starts on login)
- **Hotkey**: Right Shift — hold to record, release to process. Triple-tap Right Shift = reset jarvis
- **Python**: `~/jarvis-env/bin/python3` (venv with vosk, pynput, pyautogui)
- **Vosk model**: `~/vosk-model-en-us-0.22-lgraph/` (loaded once at startup)
- **Grammar**: `SetGrammar` is used with keyword list for reliable recognition
- **TTS**: Piper + `~/jarvis-voices/en_US-amy-medium.onnx`
- **Service**: `systemctl --user {start,stop,restart,enable,disable} jarvis`

## Keywords & Branches (32 total)
### System
- `exit` — kills jarvis
- `reset` — restarts systemd service
- `status` — speaks RAM, uptime, CPU load
- `update` — records 4s audio, transcribes with Vosk, appends to AGENTS.md
- `memory` — opens AGENTS.md in xed editor
- `terminal` — opens xterm
- `yes` / `no` — placeholders

### Navigation & Input
- `copy` — xdotool Ctrl+Insert (no Ctrl+C, won't SIGINT terminals)
- `paste` — xdotool Shift+Insert
- `enter`, `escape`, `tab` — pyautogui key press
- `click` — pyautogui click
- `scroll up` / `scroll down` — pyautogui scroll

### Browser (uses `firefox --new-tab URL`, works whether Firefox is open or not)
- `browser` — opens google.com
- `search` — opens google.com (no grammar so args don't pass; opens homepage)
- `new tab` / `close tab` — Firefox tab control
- `youtube`, `github`, `gmail`, `reddit`, `maps` — direct site opens

### Media & System
- `volume up` / `volume down` — pactl +/-5%
- `mute` — pactl toggle
- `stop` — playerctl stop
- `sleep` — systemctl suspend
- `lock` — xdg-screensaver lock
- `screenshot` — ImageMagick import to ~/Pictures/

## Delpa's Voice (~/opencode-voice/)
- **speakd.py** watches `msg.txt` for new content; writes to msg.txt to speak
- Toggle: `voice-on` / `voice-off`
- Start/stop: `voice-start` / `voice-stop`
- Self-contained venv with piper-tts
- Voice: `en_US-amy-medium.onnx`

## Session History
### 2026-05-11 Initial Session
- Cleaned up old jarvis experiments (whisper, openwakeword, pyaudio, etc.)
- Killed clamd (freed ~1GB RAM), killed jarvis-awake.py
- Built main_final.py: Vosk loaded once, non-blocking TTS, grammar-based recognition
- Added 12 new branches: search, volume up/down, mute, close tab, new tab, click, screenshot, lock, enter, escape, tab
- Added systemd user service for auto-start
- Changed hotkey: Caps Lock -> Insert -> Right Shift
- Created opencode-voice/ with speakd daemon for Delpa's TTS
- Added direct site keywords: youtube, github, gmail, reddit, maps
- Fixed copy/paste to use Ctrl+Insert/Shift+Insert (no SIGINT)
- Added status, memory, update, reset, terminal, opencode commands
- Added triple Right Shift tap = reset
- Cleaned old debug/test files from ~/jarvis/
- Backups in ~/backups/jarvis/

### Context requested 2026-05-12 10:47
- User requested context save.
