# Licences des jeux de pièces

Aucun de ces fichiers ne vient de chess.com.
Les jeux historiques sont sous licence libre ; Atelier bénéficie de l’autorisation explicite ci-dessous.
Celtique, Fantasy et Spatial viennent du dépôt de lichess (`lichess-org/lila`, dossier `public/piece/`, commit `a91b325e63cc2a69956558e0348237794b943d35` du 2026-10-06), dont `COPYING.md` donne l'auteur et la licence de chaque jeu.
Chessnut vient directement du dépôt de son auteur (commit `2b8eaf14a31edad7e9deb53b1473e1d4857868a9`), fichiers copiés octet pour octet : la version de lichess est retouchée, et l'Apache 2.0 exige alors une mention de modification dans chaque fichier.

| Dossier | Nom dans l'app | Auteur | Licence | Source amont | Modifications |
|---|---|---|---|---|---|
| `wikimedia/` | Wikimedia | jurgenwesterhof, d’après Cburnett | [CC BY-SA 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/), [texte légal](https://creativecommons.org/licenses/by-sa/3.0/legalcode) | [Chess_Pieces_Sprite.svg](https://commons.wikimedia.org/wiki/File:Chess_Pieces_Sprite.svg), [SVG original 270×90](https://upload.wikimedia.org/wikipedia/commons/b/b2/Chess_Pieces_Sprite.svg) | Découpage vectoriel en 12 SVG par `scripts/split-wikimedia.py`, suppression du décalage de chaque pièce dans le sprite ; tracés et styles inchangés, aucune rastérisation. Les fichiers dérivés restent sous CC BY-SA 3.0. Licence et auteurs vérifiés sur Commons le 15 octobre 2026. |
| `celtique/` | Celtique | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art (jeu « celtic ») | Couleurs des dégradés remplacées par des gris neutres : `#7f899b` → `#8b8886`, `#1c1c2f` → `#2b2927` (noirs), `#bfd3d7` → `#cfccc6` (blancs). Tracés inchangés. |
| `fantasy/` | Fantasy | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art | Aucune. |
| `spatial/` | Spatial | Maurizio Monge | MIT, voir `LICENSE-MIT-chess-art.txt` | https://github.com/maurimo/chess-art | Aucune. |
| `chessnut/` | Chessnut | Alexis Luengas, avis amont « Copyright 2015 Alexis Luengas » (fichier `COPYRIGHT.txt` du dépôt, copié tel quel dans `chessnut/` ; le dépôt n'a pas de fichier NOTICE) | Apache 2.0, voir `LICENSE-Apache-2.0-chessnut.txt` (texte amont, identique) | https://github.com/LexLuengas/chessnut-pieces | Aucune (fichiers identiques à l'amont). |

Le jeu « Classique » de l'app n'est pas dans ce dossier : ce sont les pièces intégrées à la bibliothèque `react-chessboard` 5.10.0 (dépendance npm, licence MIT, copyright 2022 Ryan Gregory), rendues telles quelles.
Ces dessins sont les pièces SVG standard de Wikimedia Commons (catégorie « SVG chess pieces/Standard transparent », les douze fichiers `Chess_<pièce><couleur>t45.svg`, 2006), œuvre de l'utilisateur Cburnett, publiée par lui sous quatre licences au choix : GFDL, CC BY-SA 3.0, BSD 3 clauses et GPL.
L'app les reprend sous la BSD 3 clauses (permissive, attribution requise : la voici, texte dans `LICENSE-BSD-3-Clause-cburnett.txt`).
`react-chessboard` les cite dans l'en-tête de son `src/pieces.tsx` sous la CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/, source https://commons.wikimedia.org/w/index.php?curid=1499810) ; l'attribution que cette licence exige est donnée ici et dans le README.

Jeux écartés exprès : ceux sous CC BY-NC-SA (clause non commerciale, donc pas libres), ceux marqués « freeware » ou sans licence, et les jeux copyleft (GPL, AGPL) dès qu'un équivalent permissif existait.

## Atelier (défaut)

Provenance : extrait d'une vidéo fournie par Max (2026-10-17), réutilisation autorisée par Max.
Max précise que cette vidéo ne provient pas de l’application chess.com.
Les douze silhouettes sont redessinées en SVG par `scripts/draw-atelier.py` : contours, volumes et ombres latérales repris de l’image au repos, sans bitmap embarqué.
Cette autorisation ne constitue pas une déclaration CC0 et ne modifie pas les licences des autres jeux.
Les marges de tous les jeux sont compensées au rendu grâce à `scripts/center-pieces.py`, sans modification des fichiers tiers.
