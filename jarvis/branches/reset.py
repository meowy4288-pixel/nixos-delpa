def run(args=None):
    import subprocess, os
    subprocess.run(["systemctl", "--user", "restart", "jarvis.service"],
                   capture_output=True)
    piper = os.path.expanduser("~/.local/bin/piper")
    voice = os.path.expanduser("~/jarvis-voices/en_US-amy-medium.onnx")
    os.system(f'echo "Resetting" | {piper} --model {voice} --output-raw | aplay -r 22050 -f S16_LE -t raw 2>/dev/null')
    print("[JARVIS] Resetting")
