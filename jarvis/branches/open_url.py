import subprocess

SITES = {
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://reddit.com",
    "maps": "https://maps.google.com",
    "chatgpt": "https://chat.openai.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "whatsapp": "https://web.whatsapp.com",
}


def open_site(name):
    url = SITES.get(name)
    if url:
        subprocess.Popen(["firefox", "--new-tab", url],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
