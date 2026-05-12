def run(args=None):
    import subprocess
    subprocess.Popen(["gnome-terminal"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
