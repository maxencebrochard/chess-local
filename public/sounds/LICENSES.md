# Licences des sons

Aucun de ces sons ne vient de chess.com ni de lichess.
Tous sont dérivés des packs « Impact Sounds » (1.0) et « Interface Sounds » de Kenney (https://kenney.nl), publiés sous Creative Commons Zero 1.0 (domaine public, https://creativecommons.org/publicdomain/zero/1.0/).
L'attribution n'est pas obligatoire ; merci quand même à Kenney.
Textes de licence fournis par Kenney avec chaque pack : `LICENSE-Kenney-CC0.txt`.

Ils sont produits par `scripts/make-sounds.sh`, qui télécharge les packs (empreintes SHA-256 vérifiées), mixe, coupe le silence de tête, normalise la crête et encode en MP3 mono.
Les sons dérivés sont placés eux aussi sous CC0 1.0.

| Fichier | Événement | Source Kenney | Traitement |
|---|---|---|---|
| `move-self.mp3` | coup joué | Impact Sounds `impactWood_light_002` | crête -1 dBFS |
| `move-opponent.mp3` | coup adverse | Impact Sounds `impactWood_light_000` | crête -1 dBFS |
| `capture.mp3` | prise | Impact Sounds `impactWood_medium_002` | crête -1 dBFS |
| `castle.mp3` | roque | `impactWood_light_001` + `impactWood_light_003` à 90 ms | mixés |
| `move-check.mp3` | échec | `impactWood_light_002` + Interface `glass_006` à -6 dB | mixés |
| `promote.mp3` | promotion | `impactWood_light_002` + Interface `confirmation_001` à 40 ms, -4 dB | mixés |
| `game-start.mp3` | début de partie | Interface `question_004` | crête -4 dBFS |
| `game-end.mp3` | fin de partie | Interface `confirmation_004` | crête -4 dBFS |
| `low-time.mp3` | temps bas | Interface `tick_004` doublé à 160 ms | crête -4 dBFS |
| `illegal.mp3` | coup illégal | Interface `error_004` | crête -4 dBFS |
| `success.mp3` | puzzle réussi | Interface `confirmation_002` | crête -4 dBFS |
| `fail.mp3` | puzzle raté | Interface `error_006` | crête -4 dBFS |

Historique : jusqu'à cette version, le dossier contenait des MP3 du set « standard » de lichess, que le `COPYING.md` de lila classe comme non libres ; ils ont été retirés.
