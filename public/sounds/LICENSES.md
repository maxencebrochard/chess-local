# Licences des sons

Aucun de ces sons ne vient de chess.com ni de lichess.
Les notifications sont dérivées des packs « Impact Sounds » (1.0) et « Interface Sounds » de Kenney (https://kenney.nl), publiés sous Creative Commons Zero 1.0 (domaine public, https://creativecommons.org/publicdomain/zero/1.0/).
L'attribution n'est pas obligatoire ; merci quand même à Kenney.
Textes de licence fournis par Kenney avec chaque pack : `LICENSE-Kenney-CC0.txt`.

Les notifications sont produites par `scripts/make-sounds.sh`, qui télécharge les packs (empreintes SHA-256 vérifiées), mixe, coupe le silence de tête, normalise la crête et encode en MP3 mono.
Les sons dérivés sont placés eux aussi sous CC0 1.0.

| Fichier | Événement | Source | Traitement |
|---|---|---|---|
| `move-self.mp3` | coup joué | synthèse originale CC0 | bruit filtré, impact court |
| `move-opponent.mp3` | coup adverse | synthèse originale CC0 | impact légèrement différent |
| `capture.mp3` | prise | synthèse originale CC0 | impact plus long, davantage d'aigus |
| `castle.mp3` | roque | synthèse originale CC0 | deux contacts espacés de 90 ms |
| `move-check.mp3` | échec | synthèse originale CC0 | clic bref plus aigu |
| `promote.mp3` | promotion | synthèse originale CC0 | deux contacts espacés de 60 ms |
| `game-start.mp3` | début de partie | Interface `question_004` | crête -4 dBFS |
| `game-end.mp3` | fin de partie | Interface `confirmation_004` | crête -4 dBFS |
| `low-time.mp3` | temps bas | Interface `tick_004` doublé à 160 ms | crête -4 dBFS |
| `illegal.mp3` | coup illégal | synthèse originale CC0 | résonance grave, crête -3,3 dBFS |
| `success.mp3` | puzzle réussi | Interface `confirmation_002` | crête -4 dBFS |
| `fail.mp3` | puzzle raté | Interface `error_006` | crête -4 dBFS |

Historique : jusqu'à cette version, le dossier contenait des MP3 du set « standard » de lichess, que le `COPYING.md` de lila classe comme non libres ; ils ont été retirés.

Les sept sons de coup et de refus sont des créations originales dédiées au domaine public sous CC0 1.0 : https://creativecommons.org/publicdomain/zero/1.0/.
Leur source complète est `scripts/synthesize-moves.py` (Python 3, numpy, ffmpeg/libmp3lame), également appelé par `scripts/make-sounds.sh`.
Le générateur ne lit aucun son : il combine un bruit pseudo-aléatoire reproductible, quatre bandes de résonance et des enveloppes décroissantes.
Les observations de référence portent exclusivement sur des mesures agrégées de durée, de volume et de spectre, documentées dans `docs/f14-feeling.md`.
Aucune forme d'onde, image ou autre ressource chess.com n'est distribuée.
