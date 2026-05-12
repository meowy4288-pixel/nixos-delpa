def run(args=None):
    import subprocess
    subprocess.Popen(["firefox", "--new-tab", "https://maps.google.com"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
