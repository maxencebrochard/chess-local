# Licences des jeux de pièces

Aucun de ces fichiers ne vient de chess.com.
Tous sont des œuvres sous licence libre permissive.
Celtique, Fantasy et Spatial viennent du dépôt de lichess (`lichess-org/lila`, dossier `public/piece/`, commit `a91b325e63cc2a69956558e0348237794b943d35` du 2026-10-06), dont `COPYING.md` donne l'auteur et la licence de chaque jeu.
Chessnut vient directement du dépôt de son auteur (commit `2b8eaf14a31edad7e9deb53b1473e1d4857868a9`), fichiers copiés octet pour octet : la version de lichess est retouchée, et l'Apache 2.0 exige alors une mention de modification dans chaque fichier.

| Dossier | Nom dans l'app | Auteur | Licence | Source amont | Modifications |
|---|---|---|---|---|---|
| `celtique/` | Celtique (défaut) | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art (jeu « celtic ») | Couleurs des dégradés remplacées par des gris neutres : `#7f899b` → `#8b8886`, `#1c1c2f` → `#2b2927` (noirs), `#bfd3d7` → `#cfccc6` (blancs). Tracés inchangés. |
| `fantasy/` | Fantasy | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art | Aucune. |
| `spatial/` | Spatial | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art | Aucune. |
| `chessnut/` | Chessnut | Alexis Luengas (auteur ; le dépôt amont ne porte aucun avis de copyright, ni fichier NOTICE) | Apache 2.0, voir `LICENSE-Apache-2.0-chessnut.txt` (texte amont, identique) | https://github.com/LexLuengas/chessnut-pieces | Aucune (fichiers identiques à l'amont). |

Le jeu « Classique » de l'app n'est pas dans ce dossier : ce sont les pièces intégrées à la bibliothèque `react-chessboard` (dépendance npm), utilisées telles quelles.

Jeux écartés exprès : ceux sous CC BY-NC-SA (clause non commerciale, donc pas libres), ceux marqués « freeware » ou sans licence, et les jeux copyleft (GPL, AGPL) dès qu'un équivalent permissif existait.
