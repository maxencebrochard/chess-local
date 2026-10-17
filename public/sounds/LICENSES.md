# Licences des sons

Aucun de ces sons ne vient de chess.com ni de lichess.
Les notifications sont dérivées des packs « Impact Sounds » (1.0) et « Interface Sounds » de Kenney (https://kenney.nl), publiés sous Creative Commons Zero 1.0 (domaine public, https://creativecommons.org/publicdomain/zero/1.0/).
L'attribution n'est pas obligatoire ; merci quand même à Kenney.
Textes de licence fournis par Kenney avec chaque pack : `LICENSE-Kenney-CC0.txt`.

Les notifications sont produites par `scripts/make-sounds.sh`, qui télécharge les packs (empreintes SHA-256 vérifiées), mixe, coupe le silence de tête, normalise la crête et encode en MP3 mono.
Les notifications dérivées sont placées elles aussi sous CC0 1.0.

| Fichier | Événement | Source | Traitement |
|---|---|---|---|
| `move-self.mp3` | coup joué | vidéo autorisée par Max | bruit filtré, impact court |
| `move-opponent.mp3` | coup adverse | vidéo autorisée par Max | impact légèrement différent |
| `capture.mp3` | prise | vidéo autorisée par Max | impact plus long, davantage d'aigus |
| `castle.mp3` | roque | vidéo autorisée par Max | deux contacts espacés de 90 ms |
| `move-check.mp3` | échec | vidéo autorisée par Max | clic bref plus aigu |
| `promote.mp3` | promotion | vidéo autorisée par Max | deux contacts espacés de 60 ms |
| `game-start.mp3` | début de partie | Interface `question_004` | crête -4 dBFS |
| `game-end.mp3` | fin de partie | Interface `confirmation_004` | crête -4 dBFS |
| `low-time.mp3` | temps bas | Interface `tick_004` doublé à 160 ms | crête -4 dBFS |
| `illegal.mp3` | coup illégal | vidéo autorisée par Max | impact grave extrait |
| `success.mp3` | puzzle réussi | Interface `confirmation_002` | crête -4 dBFS |
| `fail.mp3` | puzzle raté | Interface `error_006` | crête -4 dBFS |

Historique : jusqu'à cette version, le dossier contenait des MP3 du set « standard » de lichess, que le `COPYING.md` de lila classe comme non libres ; ils ont été retirés.

Les sept sons de coup et de refus sont désormais extraits par `scripts/extract-video-sounds.py`.
Provenance : extrait d'une vidéo fournie par Max (2026-10-17), réutilisation autorisée par Max.
Max précise que cette vidéo ne provient pas de l’application chess.com.
Découpe isolée, suppression de composante continue, fondus aux bords, normalisation à -1 dBFS avant encodage MP3 mono 128 kbit/s.
Cette autorisation n’est pas une licence CC0 ; les notifications Kenney conservent leur licence CC0.
Le script `scripts/synthesize-moves.py` conserve l’ancienne synthèse originale, mais ne génère plus les assets actuels.
