"""Dalek phrases for the archive: Kokoro speech -> staccato shaping -> Whisper word timing and read-back ->
30 Hz ring modulation, clipping and a metallic comb -> clips + a 60 fps loudness envelope for the dome lights.

Needs a Python with kokoro, phonemizer (espeak-ng), whisper, numpy and soundfile:
    python tools/voice/gen_voice.py            # all phrases
    python tools/voice/gen_voice.py dalek obey # re-record some, merging into voice.json
Writes out/<id>.wav and voice.json next to this script; encode to MP3 and embed in index.html's #voxData.
"""
import json
import sys
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
SR = 24000
VOICE, SPEED = "bm_george", 1.15
PITCH = -2.0       # semitones (resampled, so also ~12% slower; SPEED makes up for it): deeper; see shape()

# id -> (caption as shown in the archive, text as spoken)
PHRASES = {
    "proceed": ("PRO-CEED WITH PA-TROL", "Pro-ceed with patrol."),
    "sector": ("SEC-TOR SE-VEN... ALL CLEAR", "Sector seven. All clear."),
    "continue": ("CON-TIN-UE PA-TROL", "Continue patrol."),
    "obey1": ("I O-BEY", "I obey."),
    "scanning": ("SCAN-NING...", "Scanning."),
    "nolife": ("NO LIFE FORMS DE-TEC-TED", "No life forms detected."),
    "scansector": ("SCAN-NING SEC-TOR", "Scanning sector."),
    "analyse": ("AN-A-LYSE! AN-A-LYSE!", "Analyse! Analyse!"),
    "attack": ("AT-TACK! AT-TACK!", "Attack! Attack!"),
    "target": ("TAR-GET AC-QUIRED", "Target. Uh-quired."),
    "destroy": ("DE-STROY THEM!", "Destroy them!"),
    "dalek": ("I AM A DA-LEK", "I am a Dah-leck."),
    "obey": ("YOU WILL O-BEY!", "You will obey!"),
    "supreme": ("DA-LEKS ARE SU-PREME!", "Daleks are supreme!"),
    "identify": ("IDEN-TI-FY YOUR-SELF!", "Identify yourself!"),
    "exterminate": ("EX-TER-MIN-ATE!", "Exterminate!"),
}

# respelt lines: what Whisper should hear
PLAIN = {"proceed": "Proceed with patrol", "target": "Target acquired", "dalek": "I am a Dalek"}


def shape(x):
    """Delivery before the Dalek treatment: pitch shift (by resampling), then staccato. The phrase is cut at the
    dips between syllables with short silences inserted, and each syllable's tail is gated off, so the words
    come out punched one at a time. Whisper times the captions from this shaped (dry) take."""
    r = 2 ** (PITCH / 12)
    x = np.interp(np.arange(0, len(x) - 1, r), np.arange(len(x)), x).astype(np.float32)
    hop = int(.01 * SR)
    n = len(x) // hop
    e = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2)) for i in range(n)])
    e = np.convolve(e, np.ones(3) / 3, mode="same")
    top = e.max() + 1e-9
    peaks = [i for i in range(1, n - 1) if e[i] >= e[i - 1] and e[i] > e[i + 1] and e[i] > .22 * top]
    cuts = []
    for p0, p1 in zip(peaks, peaks[1:]):
        m = p0 + int(np.argmin(e[p0:p1 + 1]))
        if e[m] < .6 * min(e[p0], e[p1]) and (not cuts or m - cuts[-1] > 7):
            cuts.append(m)
    # gate: hold syllable bodies, drop the soft tails between them
    g = np.clip((e / top - .07) / .12, 0, 1)
    gain = np.repeat(g, hop)[:len(x)]
    gain = np.concatenate([gain, np.full(len(x) - len(gain), gain[-1] if len(gain) else 1)])
    gain = np.convolve(gain, np.ones(96) / 96, mode="same")      # ~4 ms edges
    x = x * gain
    out, last, fade = [], 0, int(.006 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    for c in cuts + [None]:
        seg = x[last:(c * hop if c is not None else len(x))].copy()
        if len(seg) > 2 * fade:
            seg[:fade] *= ramp; seg[-fade:] *= ramp[::-1]
        out.append(seg)
        if c is not None:
            out.append(np.zeros(int(.075 * SR), np.float32))    # the gap between syllables
            last = c * hop
    return np.concatenate(out).astype(np.float32)


def dalek(x):
    """The 1960s treatment, pushed harder: band-limit, 30 Hz ring modulation (fully wet), heavy soft
    clipping, a short metallic comb and a presence lift."""
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < 170) | (f > 3600)] = 0                            # radio-like band, with some chest left in
    x = np.fft.irfft(X, len(x))
    t = np.arange(len(x)) / SR
    y = x * np.sin(2 * np.pi * 30 * t)
    y = np.tanh(y / (np.max(np.abs(y)) + 1e-9) * 3.6)
    d = int(.0045 * SR)                                      # 4.5 ms comb: tinny, metallic
    y = y + 0.45 * np.concatenate([np.zeros(d), y[:-d]])
    y = y + 0.35 * np.concatenate([[0], np.diff(y)]) * 3
    return 0.89 * y / (np.max(np.abs(y)) + 1e-9)


def envelope(x, fps=60):
    hop = SR // fps
    n = int(np.ceil(len(x) / hop))
    e = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    e = e / (e.max() + 1e-9)
    return [round(float(v), 3) for v in e]


def norm(s):
    return re.sub(r"[^a-z ]", "", s.lower()).split()


def main():
    from kokoro import KPipeline
    import whisper

    pipe = KPipeline(lang_code="b")
    model = whisper.load_model("small.en")
    only = set(sys.argv[1:])                 # re-record just these ids, merging into voice.json
    meta = json.loads((HERE / "voice.json").read_text()) if only and (HERE / "voice.json").exists() else {}
    for pid, (caption, text) in PHRASES.items():
        if only and pid not in only:
            continue
        chunks = [a for _, _, a in pipe(text, voice=VOICE, speed=SPEED)]
        raw = np.concatenate([np.asarray(c, dtype=np.float32) for c in chunks])
        raw = np.concatenate([np.zeros(int(.05 * SR), np.float32), shape(raw), np.zeros(int(.12 * SR), np.float32)])
        dry = HERE / "out" / f"{pid}.dry.wav"
        sf.write(dry, raw, SR)
        words = [w for seg in model.transcribe(str(dry), word_timestamps=True, language="en")["segments"] for w in seg.get("words", [])]
        y = dalek(raw)
        wet = HERE / "out" / f"{pid}.wav"
        sf.write(wet, y, SR)
        heard = model.transcribe(str(wet), language="en")["text"].strip()
        ok = norm(heard) == norm(PLAIN.get(pid, text))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-threads", "2", "-i", str(wet), "-c:a", "libopus", "-b:a", "40k",
                        "-ac", "1", str(OUT / f"{pid}.ogg")], check=True)
        meta[pid] = {"caption": caption, "text": text, "dur": round(len(y) / SR, 3),
                     "words": [[w["word"].strip(), round(w["start"], 3), round(w["end"], 3)] for w in words],
                     "env": envelope(y), "heard": heard, "ok": ok}
        print(f"{'ok   ' if ok else 'CHECK'} {pid:12s} {len(y)/SR:4.2f}s  heard: {heard}")
    (HERE / "voice.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
