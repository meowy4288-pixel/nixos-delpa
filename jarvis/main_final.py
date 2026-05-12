#!/usr/bin/env python3
import os
import sys
import time
import json
import threading
import subprocess
import importlib.util
from pathlib import Path
from pynput import keyboard
from vosk import Model, KaldiRecognizer
import wave

os.environ['DISPLAY'] = ':0'

SAMPLE_RATE = 16000
AUDIO_FILE = "/tmp/jarvis_cmd.wav"
MODEL_PATH = os.path.expanduser("~/vosk-model-en-us-0.22-lgraph")
KEYWORDS_FILE = Path(__file__).parent / "keywords.txt"
BRANCHES_DIR = Path(__file__).parent / "branches"
PIPER = os.path.expanduser("~/.local/bin/piper")
VOICE = os.path.expanduser("~/jarvis-voices/en_US-amy-medium.onnx")

with open(KEYWORDS_FILE) as f:
    KEYWORDS = [line.strip().lower() for line in f if line.strip()]

print(f"JARVIS ready. Keywords: {KEYWORDS}")

is_recording = False
record_process = None
should_exit = False
tap_times = []
PRESS_THRESHOLD = 0.3
TAP_WINDOW = 2.5

print("Loading Vosk model...")
vosk_model = Model(MODEL_PATH)
print("Vosk model loaded.")


def speak(text):
    def _speak():
        cmd = f'echo "{text}" | {PIPER} --model {VOICE} --output-raw | aplay -r 22050 -f S16_LE -t raw 2>/dev/null'
        os.system(cmd)
    print(f"[JARVIS] {text}")
    threading.Thread(target=_speak, daemon=True).start()


def recognize_vosk():
    if not os.path.exists(AUDIO_FILE):
        return None, None, 0

    file_size = os.path.getsize(AUDIO_FILE)
    if file_size < 5000:
        return None, None, 0

    rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    rec.SetGrammar(json.dumps(KEYWORDS))

    wf = wave.open(AUDIO_FILE, 'rb')
    recognized = []

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if result.get('text'):
                recognized.append(result['text'])

    final = json.loads(rec.FinalResult())
    if final.get('text'):
        recognized.append(final['text'])

    wf.close()

    if recognized:
        text = recognized[-1].lower()
        print(f"Recognized: '{text}'")

        if text in KEYWORDS:
            print(f"Matched: '{text}'")
            return text, None, 0.95

        words = text.split()
        for kw in sorted(KEYWORDS, key=len, reverse=True):
            kw_words = kw.split()
            match_len = len(kw_words)
            for i in range(len(words) - match_len + 1):
                if " ".join(words[i:i + match_len]) == kw:
                    args = " ".join(words[i + match_len:])
                    ngrams = [kw] + kw_words
                    if args and all(a not in kw for a in args.split()):
                        print(f"Matched: '{kw}' args='{args}'")
                        return kw, args, 0.95
                    print(f"Matched: '{kw}'")
                    return kw, args, 0.95

        return None, text, 0.6

    return None, None, 0


def execute_branch(command, args=None):
    global should_exit
    filename = command.replace(" ", "_") + ".py"
    module_path = BRANCHES_DIR / filename

    if not module_path.exists():
        print(f"Branch not found: {command}")
        speak("Command not found")
        return

    try:
        spec = importlib.util.spec_from_file_location(f"branches.{command}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if args:
            module.run(args)
        else:
            module.run()

        if command == "exit":
            should_exit = True
            speak("Goodbye")
        else:
            confirmations = {
                "copy": "Copied",
                "paste": "Pasted",
                "browser": "Opening browser",
                "scroll up": "Scrolling up",
                "scroll down": "Scrolling down",
                "sleep": "Goodnight",
                "stop": "Stopped",
            }
            speak(confirmations.get(command, f"{command} done"))
    except Exception as e:
        print(f"Error: {e}")
        speak("Command failed")


def process_audio():
    print("Processing...")
    command, args, conf = recognize_vosk()

    if command:
        print(f"Command: '{command}' args='{args}'")
        execute_branch(command, args)
    else:
        print("No command recognized")


press_time = 0


def on_press(key):
    global is_recording, record_process, press_time
    if key == keyboard.Key.shift_r and not is_recording and not should_exit:
        press_time = time.time()
        is_recording = True
        print("\nRecording...")

        if os.path.exists(AUDIO_FILE):
            os.unlink(AUDIO_FILE)

        record_process = subprocess.Popen([
            "arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav", AUDIO_FILE
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def on_release(key):
    global is_recording, record_process, press_time, tap_times, should_exit
    if key == keyboard.Key.shift_r and is_recording and not should_exit:
        is_recording = False
        hold_time = time.time() - press_time

        if record_process:
            record_process.terminate()
            record_process.wait()
            record_process = None

        if hold_time < PRESS_THRESHOLD:
            now = time.time()
            tap_times = [t for t in tap_times if now - t < TAP_WINDOW]
            tap_times.append(now)
            if len(tap_times) >= 3:
                tap_times = []
                print("Triple tap detected. Resetting...")
                subprocess.run(["systemctl", "--user", "restart", "jarvis.service"],
                               capture_output=True)
            return

        print("Processing...")
        threading.Thread(target=process_audio).start()


def main():
    global should_exit
    print("\n" + "=" * 50)
    print("JARVIS - Right Shift Push-to-Talk")
    print("=" * 50 + "\n")

    speak("JARVIS ready")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        while not should_exit:
            time.sleep(0.1)
        listener.stop()

    print("JARVIS stopped")


if __name__ == "__main__":
    main()
