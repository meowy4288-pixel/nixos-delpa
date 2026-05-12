def run(args=None):
    import subprocess, os
    path = os.path.expanduser("~/jarvis/AGENTS.md")
    editor = os.environ.get("EDITOR", "xed")
    subprocess.Popen([editor, path],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
