"""Mesure comparable de WAV/MP3 : python3 scripts/measure-sounds.py fichiers...

Prérequis : numpy et ffmpeg.
Ne conserve aucune copie des fichiers analysés.
Les bornes actives utilisent une enveloppe RMS de 1 ms à -40 dB de son maximum.
Les bandes et le centroïde sont pondérés par l'énergie du spectre.
"""

import json
import subprocess
import sys

import numpy as np


def measure(path):
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            "44100",
            "-",
        ]
    )
    x = np.frombuffer(raw, dtype="<f4").astype(float)
    hop = 44
    env = np.sqrt(
        np.mean(np.pad(x, (0, (-len(x)) % hop)).reshape(-1, hop) ** 2, axis=1)
    )
    active = np.flatnonzero(env > env.max() * 0.01)
    a, b = active[0] * hop, min(len(x), (active[-1] + 1) * hop)
    x = x[a:b]
    energy = np.cumsum(x * x)
    t = [np.searchsorted(energy, energy[-1] * q) / 44.1 for q in (0.05, 0.5, 0.95)]
    spectrum = abs(np.fft.rfft(x)) ** 2
    freq = np.fft.rfftfreq(len(x), 1 / 44100)
    bands = [
        100 * float(spectrum[(freq >= lo) & (freq < hi)].sum() / spectrum.sum())
        for lo, hi in [(0, 500), (500, 2000), (2000, 6000), (6000, 22051)]
    ]
    return dict(
        duration_ms=round(len(x) / 44.1, 1),
        attack_ms=round((np.argmax(env) * hop - a) / 44.1, 1),
        t50_ms=round(t[1], 1),
        decay_ms=round(t[2] - t[0], 1),
        rms_db=round(float(20 * np.log10(np.sqrt(np.mean(x * x)))), 1),
        peak_db=round(float(20 * np.log10(abs(x).max())), 1),
        centroid_hz=round(float((freq * spectrum).sum() / spectrum.sum())),
        bands_pct=[round(v, 1) for v in bands],
    )


if __name__ == "__main__":
    print(json.dumps({p: measure(p) for p in sys.argv[1:]}, indent=2))
