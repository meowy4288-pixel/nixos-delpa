def run(args=None):
    import subprocess
    subprocess.Popen(["firefox", "--new-tab", "https://github.com"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
