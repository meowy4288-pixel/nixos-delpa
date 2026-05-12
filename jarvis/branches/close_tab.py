def run(args=None):
    import subprocess
    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "firefox"],
                            capture_output=True, text=True)
    wid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
    if wid:
        subprocess.run(["xdotool", "windowactivate", wid], capture_output=True)
        subprocess.run(["xdotool", "key", "ctrl+w"], capture_output=True)
