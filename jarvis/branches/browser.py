def run(args=None):
    import subprocess

    url = args.strip() if args else "google.com"
    if not url.startswith("http"):
        url = "https://" + url

    subprocess.Popen(["firefox", "--new-tab", url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
