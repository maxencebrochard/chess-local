"""Extrait les impacts de la vidéo autorisée par Max le 17 octobre 2026.

Usage : python3 scripts/extract-video-sounds.py /private/tmp/claude-501/chess-video/reference.mov
Les découpes intermédiaires restent dans le dossier temporaire de la vidéo.
Seuls les MP3 nettoyés sont écrits dans public/sounds.
"""
from pathlib import Path
import subprocess
import sys
import numpy as np

source = Path(sys.argv[1]).resolve()
work = Path('/private/tmp/claude-501/chess-video').resolve()
if source.parent != work:
    raise SystemExit('La source doit rester dans /private/tmp/claude-501/chess-video/')
out = Path(__file__).resolve().parents[1] / 'public/sounds'
# Fenêtres isolées, relevées en croisant images et piste audio.
events = {'move-self': (1.32, .18), 'move-opponent': (2.29, .18),
          'capture': (8.13, .26), 'castle': (20.53, .30),
          'move-check': (53.56, .20), 'promote': (83.07, .28), 'illegal': (17.68, .32)}
for name, (start, duration) in events.items():
    raw = work / (name + '.f32')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(source), '-ss', str(start),
                    '-t', str(duration), '-ac', '1', '-ar', '44100', '-f', 'f32le', str(raw)], check=True)
    samples = np.fromfile(raw, dtype='<f4')
    samples -= samples.mean()
    peak = np.max(np.abs(samples))
    active = np.flatnonzero(np.abs(samples) > peak * .002)
    samples = samples[max(0, active[0]-44):min(len(samples), active[-1]+221)]
    # Fondu de bord de 0,5 ms et queue de 3 ms, crête avec marge de 1 dB.
    samples[:22] *= np.linspace(0, 1, 22)
    samples[-132:] *= np.linspace(1, 0, 132)
    samples *= 10 ** (-1/20) / np.max(np.abs(samples))
    samples.astype('<f4').tofile(raw)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', '44100', '-ac', '1',
                    '-i', str(raw), '-codec:a', 'libmp3lame', '-b:a', '128k',
                    '-map_metadata', '-1', str(out / (name + '.mp3'))], check=True)
    print(f'{name}: {len(samples)/44.1:.1f} ms, crête PCM -1 dBFS')
