#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
MSG = HERE / "msg.txt"
FLAG = HERE / ".voice_enabled"
VOICE = HERE / "en_US-amy-medium.onnx"
PIPER = Path.home() / ".local" / "bin" / "piper"
PIDFILE = HERE / ".speakd.pid"

running = True
last_size = 0


def speak(text):
    if not FLAG.exists():
        return
    try:
        proc = subprocess.Popen(
            [str(PIPER), "--model", str(VOICE), "--output-raw"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        aplay = subprocess.Popen(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw"],
            stdin=proc.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.stdin.write(text.encode())
        proc.stdin.close()
        proc.wait()
        aplay.wait()
    except Exception as e:
        print(f"[speakd] Error: {e}", file=sys.stderr)


def signal_handler(sig, frame):
    global running
    running = False


def main():
    global running, last_size
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if not MSG.exists():
        MSG.write_text("")

    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))

    print(f"[speakd] Watching {MSG}")
    print(f"[speakd] Voice is {'ON' if FLAG.exists() else 'OFF'}")

    while running:
        try:
            if not MSG.exists():
                time.sleep(0.3)
                continue

            current_size = MSG.stat().st_size
            if current_size > last_size:
                text = MSG.read_text().strip()
                MSG.write_text("")
                last_size = 0
                if text:
                    speak(text)

            time.sleep(0.3)
        except Exception as e:
            print(f"[speakd] Error: {e}", file=sys.stderr)
            time.sleep(1)

    if PIDFILE.exists():
        PIDFILE.unlink()
    print("[speakd] Stopped")


if __name__ == "__main__":
    main()
