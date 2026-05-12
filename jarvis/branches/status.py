def run(args=None):
    import subprocess, os

    mem = subprocess.run(["free", "-h"], capture_output=True, text=True)
    mem_line = mem.stdout.split("\n")[1].split()
    used = mem_line[2]
    avail = mem_line[6]

    uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
    up = uptime.stdout.strip().replace("up ", "")

    load = subprocess.run(["cat", "/proc/loadavg"], capture_output=True, text=True)
    load1 = load.stdout.split()[0]

    text = f"System status. Memory: {used} used, {avail} available. Uptime: {up}. Load: {load1}."
    piper = os.path.expanduser("~/.local/bin/piper")
    voice = os.path.expanduser("~/jarvis-voices/en_US-amy-medium.onnx")
    cmd = f'echo "{text}" | {piper} --model {voice} --output-raw | aplay -r 22050 -f S16_LE -t raw 2>/dev/null'
    os.system(cmd)
    print(f"[JARVIS] {text}")
