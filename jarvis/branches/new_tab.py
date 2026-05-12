def run(args=None):
    import subprocess
    subprocess.Popen(["firefox", "--new-tab", "about:blank"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
