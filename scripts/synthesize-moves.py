"""Impacts originaux CC0 : aucune entrée audio, uniquement du bruit et des résonances.

Reproduction : python3 scripts/synthesize-moves.py (numpy, ffmpeg avec libmp3lame).
Les paramètres décrivent une enveloppe et quatre bandes, jamais une forme d'onde tierce.
Les notifications Kenney restent produites par make-sounds.sh.
"""

from pathlib import Path
import subprocess
import tempfile
import wave

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parents[1] / "public" / "sounds"


def impact(duration, attack, decay, bands, seed, body=330):
    n = round(duration * SR)
    rng = np.random.default_rng(seed)
    frequencies = np.fft.rfftfreq(n, 1 / SR)
    signal = np.zeros(n)
    t = np.arange(n) / SR
    envelope = np.minimum(t / max(attack, 0.0001), 1) * (
        np.exp(-np.maximum(t - attack, 0) / decay) + 0.025 * np.exp(-t / (decay * 4))
    )
    envelope *= np.minimum((duration - t) / 0.005, 1)
    # Résonances larges : bois grave, claquement médium, frottement et clic aigu.
    for weight, (lo, hi, center, width) in zip(
        bands,
        [
            (40, 500, body, 160),
            (500, 2000, 880, 420),
            (2000, 6000, 3900, 1400),
            (6000, 18000, 8500, 2200),
        ],
    ):
        spectrum = np.fft.rfft(rng.normal(size=n))
        spectrum *= np.exp(-0.5 * ((frequencies - center) / width) ** 2) * (
            (frequencies >= lo) & (frequencies < hi)
        )
        band = np.fft.irfft(spectrum, n)
        band *= envelope
        signal += band / np.sqrt(np.mean(band * band)) * np.sqrt(weight)
    return signal


def synthesize():
    quiet = [0.215, 0.768, 0.017, 0]
    other = [0.173, 0.806, 0.021, 0]
    capture = [0.12, 0.61, 0.258, 0.012]
    configs = {
        "move-self": (0.075, 0.00094, 0.00634, quiet, 860, -0.5),
        "move-opponent": (0.078, 0.00155, 0.00745, other, 2700, -0.5),
        "capture": (0.15, 0.00909, 0.01659, capture, 8517, -0.5),
        "move-check": (0.08, 0.01367, 0.00446, [0.011, 0.664, 0.225, 0.10], 7079, -0.5),
        "illegal": (0.23, 0.02932, 0.02910, [0.645, 0.354, 0.001, 0], 3760, -3.3),
    }
    signals = {
        name: (impact(d, a, t, b, s, body=180 if name == "illegal" else 330), peak)
        for name, (d, a, t, b, s, peak) in configs.items()
    }
    # Deux contacts pour le roque ; deux impacts plus rapprochés pour la promotion.
    for name, delay, bands, seed, decay, ratio in [
        ("castle", 0.09, [0.33, 0.574, 0.039, 0.057], 3202, 0.00954, 0.451),
        ("promote", 0.06, [0.15, 0.793, 0.057, 0], 7803, 0.00714, 0.480),
    ]:
        first = impact(0.09, 0.001, decay, bands, seed)
        second = impact(0.09, 0.002, decay, bands, seed + 1)
        signal = np.zeros(len(first) + round(delay * SR))
        signal[: len(first)] += first * ratio
        signal[-len(second) :] += second
        signals[name] = (signal, -0.5)
    with tempfile.TemporaryDirectory(prefix="chess-synthesis-") as tmp:
        for name, (signal, peak) in signals.items():
            signal *= 10 ** (peak / 20) / np.max(np.abs(signal))
            wav = Path(tmp) / f"{name}.wav"
            with wave.open(str(wav), "wb") as out:
                out.setparams((1, 2, SR, 0, "NONE", "not compressed"))
                out.writeframes((signal * 32767).astype("<i2").tobytes())
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(wav),
                    "-c:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(OUT / f"{name}.mp3"),
                ],
                check=True,
            )


if __name__ == "__main__":
    synthesize()
