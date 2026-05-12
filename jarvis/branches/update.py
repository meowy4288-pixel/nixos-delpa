def run(args=None):
    import subprocess, os, time
    path = os.path.expanduser("~/jarvis/AGENTS.md")
    date = time.strftime("%Y-%m-%d %H:%M")
    with open(path, "a") as f:
        f.write(f"\n### Context requested {date}\n- User requested context save.\n")
    piper = os.path.expanduser("~/.local/bin/piper")
    voice = os.path.expanduser("~/jarvis-voices/en_US-amy-medium.onnx")
    os.system(f'echo "Context noted" | {piper} --model {voice} --output-raw | aplay -r 22050 -f S16_LE -t raw 2>/dev/null')
