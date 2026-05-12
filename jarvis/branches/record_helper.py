import os
import json
import wave
import subprocess
import importlib.util
from pathlib import Path

SAMPLE_RATE = 16000
AUDIO_FILE = "/tmp/jarvis_cmd_query.wav"
MODEL_PATH = os.path.expanduser("~/vosk-model-en-us-0.22-lgraph")


def record_once(timeout=3):
    if os.path.exists(AUDIO_FILE):
        os.unlink(AUDIO_FILE)

    subprocess.run([
        "arecord", "-D", "default", "-f", "S16_LE", "-r", "16000", "-c", "1",
        "-d", str(timeout), AUDIO_FILE
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not os.path.exists(AUDIO_FILE):
        return None

    size = os.path.getsize(AUDIO_FILE)
    if size < 5000:
        return None

    from vosk import Model, KaldiRecognizer
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE)

    wf = wave.open(AUDIO_FILE, 'rb')
    texts = []
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            r = json.loads(rec.Result())
            if r.get('text'):
                texts.append(r['text'])
    final = json.loads(rec.FinalResult())
    if final.get('text'):
        texts.append(final['text'])
    wf.close()

    if texts:
        return texts[-1]
    return None
