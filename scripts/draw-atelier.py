"""Redessine en SVG les silhouettes de la vidéo fournie et autorisée par Max.

Grille de 100 unités, proportions relevées sur l'image au repos (cases de 151 px).
Aucun bitmap embarqué ; les SVG sont générés, ne pas les modifier à la main.
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'public/pieces/atelier'
OUT.mkdir(exist_ok=True)
BASE = '<path d="M22 79 Q22 72 50 72 Q78 72 78 79 V88 H22 Z"/>'
SHAPES = {
 'P': '<path d="M37 35 A13 13 0 1 1 63 35 Q62 42 57 45 L65 50 L64 55 H56 Q57 66 67 73 Q75 78 75 88 H25 Q25 78 33 73 Q43 66 44 55 H36 L35 50 L43 45 Q38 41 37 35 Z"/>',
 'R': '<path d="M32 39 L28 74 H72 L68 39 Z"/><path d="M27 20 L28 34 Q29 41 36 41 H64 Q71 41 72 34 L73 20 L63 18 L61 28 H56 L55 17 H45 L44 28 H39 L37 18 Z"/>' + BASE,
 'N': '<path d="M30 75 Q32 64 42 57 Q51 51 52 43 Q46 50 39 50 L34 56 Q29 57 19 51 Q12 48 18 41 L27 29 Q29 21 35 20 L37 12 Q39 8 44 17 Q62 21 69 35 Q82 53 73 76 Z"/><path d="M35 31 Q38 25 42 29 Q43 32 35 33 Z" fill="{line}" stroke="none"/>' + BASE,
 'B': '<path d="M37 20 C29 12 39 5 44 9 Q52 12 46 20 C36 32 24 43 27 57 Q28 68 39 74 H61 Q73 64 72 51 Q70 35 59 24 Q53 36 53 50 H46 Q44 36 50 19 Z"/>' + BASE,
 'Q': '<path d="M34 74 L18 42 A8 8 0 1 1 26 39 L34 47 L33 28 A8 8 0 1 1 41 26 L50 45 L59 26 A8 8 0 1 1 67 28 L66 47 L74 39 A8 8 0 1 1 82 42 L66 74 Z"/>' + BASE,
 'K': '<path fill-rule="evenodd" d="M45 8 H55 V15 H62 V23 H55 L57 30 C82 20 94 39 84 53 L66 74 H34 L16 53 C6 39 18 20 43 30 L45 23 H38 V15 H45 Z M43 44 Q32 38 29 45 Q27 50 43 59 Z M57 44 V59 Q73 50 71 45 Q68 38 57 44 Z"/>' + BASE,
}
# Ombres latérales observées dans la vidéo : gris clair et anthracite.
SHADOWS = {
 'P': 'M54 23 Q68 36 55 45 L62 51 H53 Q53 67 68 75 Q54 71 45 57 L44 51 H53 Q65 42 54 23 Z',
 'R': 'M54 41 H68 L72 73 H62 Q62 52 54 41 Z',
 'N': 'M54 24 Q85 40 73 73 H56 Q73 49 54 24 Z',
 'B': 'M61 30 Q80 59 61 72 H49 Q70 58 61 30 Z',
 'Q': 'M75 44 L65 72 H52 Q65 61 75 44 Z',
 'K': 'M76 33 Q92 43 72 60 L63 72 H52 Q67 61 75 50 Q84 40 76 33 Z',
}
for color, fill, line, shade in [('w', '#f8f8f8', '#41413e', '#cececc'), ('b', '#4c4b49', '#292a27', '#3c3b39')]:
 for code, shape in SHAPES.items():
  # Le socle est dessiné après l'ombre pour conserver son contour continu.
  body = shape.replace(BASE, '').format(line=line)
  svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<desc>Atelier : extrait d'une vidéo fournie par Max (2026-10-17), réutilisation autorisée par Max. Redessin vectoriel. Généré par scripts/draw-atelier.py.</desc>
<g fill="{fill}" stroke="{line}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round">{body}<path d="{SHADOWS[code]}" fill="{shade}" stroke="none"/>{BASE if code != 'P' else ''}</g>
</svg>
'''
  (OUT / f'{color}{code}.svg').write_text(svg)
print('Atelier : 12 SVG redessinés depuis la référence autorisée')
