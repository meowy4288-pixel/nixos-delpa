import os
import threading

PIPER = os.path.expanduser("~/.local/bin/piper")
VOICE = os.path.expanduser("~/jarvis-voices/en_US-amy-medium.onnx")


def speak(text):
    def _speak():
        cmd = f'echo "{text}" | {PIPER} --model {VOICE} --output-raw | aplay -r 22050 -f S16_LE -t raw 2>/dev/null'
        os.system(cmd)
    print(f"[JARVIS] {text}")
    threading.Thread(target=_speak, daemon=True).start()
