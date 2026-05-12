def run(args=None):
    import subprocess

    query = args.strip() if args else ""
    if not query:
        url = "https://google.com"
    else:
        url = f"https://google.com/search?q={query.replace(' ', '+')}"

    subprocess.Popen(["firefox", "--new-tab", url],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
