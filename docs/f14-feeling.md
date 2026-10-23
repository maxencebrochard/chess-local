# Ressenti F14 : observations et mesures

Étude initiale du 15 octobre 2026, complétée le 17 octobre avec la référence fournie par Max.
Le fichier actuel mesure 85,920 s, 60 images/s, 1206 × 1234 (ffprobe) ; sa piste AAC mono à 44 100 Hz commence à 26,667 ms.
Les extractions intermédiaires audio et vidéo restent dans /private/tmp/claude-501/chess-video/, hors dépôt.
Max a précisé le 17 octobre que la vidéo ne vient pas de chess.com et a autorisé la reprise des sons et du design.
Les MP3 finaux et les SVG redessinés Atelier sont distribués avec cette provenance dans leurs LICENSES.md.
Aucun asset officiel chess.com n’est ajouté.

## Méthode et limites de l’étude initiale

FFmpeg a décodé la piste mono à 44 100 Hz ; son début est décalé de 27,642 ms dans le conteneur, décalage pris en compte pour le rapprochement avec les images.
48 événements isolés ont été extraits séparément, avec une marge de silence avant et après, puis classés en croisant les positions et les gestes.
Une vue toutes les 100 ms et des planches à 60 images/s autour de chaque événement ont servi à examiner le soulèvement, la pose et les refus.
La vidéo est une page Analyse : les deux couleurs sont manipulées au doigt, ce n'est pas une partie contre un bot.
Elle ne permet donc pas de mesurer une animation automatique de réponse adverse ni une latence physique entre le doigt, le haut-parleur et l'écran.
Le point de contact est inféré du disque de visée, le doigt lui-même n'étant pas enregistré.
Sur les poses légales examinées, le changement de taille et le début sonore sont dans la même fenêtre d'une image, soit environ 17 ms de précision ; ce n'est pas une mesure matérielle de latence.
Le son du roque contient deux contacts, le son de promotion est déclenché après le choix.
Plusieurs tentatives hors tour produisent le son grave de refus, distinct du son de prise.

`python3 scripts/measure-sounds.py fichiers...` mesure les fichiers avec la même méthode (numpy et ffmpeg requis).
La durée active est délimitée par une enveloppe RMS de 1 ms, au seuil de -40 dB sous son maximum ; ce n'est ni la durée du conteneur MP3 ni celle de sa queue inaudible.
Cela explique notamment les 42 ms actifs des coups simples malgré une impression sonore et une fenêtre d'extraction plus longues.
L'attaque est l'instant du maximum de cette enveloppe ; T50 est l'instant de 50 % d'énergie ; la décroissance indiquée est T95 - T05.
Le centroïde et les bandes sont pondérés par l'énergie, avec des bandes 0-500, 500-2000, 2000-6000 et 6000-22050 Hz.
RMS et crêtes sont en dBFS numériques, pas en dB acoustiques : le volume du téléphone et le traitement de l'enregistrement restent inconnus.
Les références ci-dessous sont les médianes par catégorie.
Le retour en arrière à environ 39,33 s sonne dans la référence ; la navigation arrière de ChessLocal reste volontairement muette conformément au contrat F10 et à ses suites.

## Comparaison historique de la synthèse (15 octobre)

Les fichiers « après » sont exclusivement issus de la synthèse originale de `scripts/synthesize-moves.py`, sans entrée audio externe.
Les notifications de début, fin, temps bas, réussite et échec d'exercice restent celles de Kenney.

| Type | Version | Durée active ms | Attaque ms | T50 ms | T95-T05 ms | RMS dBFS | Crête dBFS | Centroïde Hz | Bandes % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Coup blanc | Référence | 41.9 | 1.0 | 2.4 | 9.9 | -14.5 | 0.0 | 841 | 21.3 / 77.0 / 1.7 / 0.0 |
| Coup blanc | Avant | 96.8 | 0.0 | 3.1 | 24.4 | -16.0 | -0.9 | 306 | 87.0 / 12.8 / 0.2 / 0.0 |
| Coup blanc | Après | 42.9 | 2.0 | 3.0 | 10.9 | -14.9 | -0.5 | 831 | 18.7 / 79.5 / 1.8 / 0.0 |
| Coup noir / retour | Référence | 44.9 | 2.0 | 3.4 | 11.1 | -15.1 | 0.0 | 917 | 17.3 / 80.6 / 2.1 / 0.0 |
| Coup noir / retour | Avant | 97.8 | 0.0 | 3.0 | 24.9 | -16.2 | -1.0 | 328 | 85.6 / 14.3 / 0.2 / 0.0 |
| Coup noir / retour | Après | 44.9 | 2.0 | 3.0 | 9.9 | -15.6 | -0.5 | 877 | 17.9 / 80.1 / 2.0 / 0.0 |
| Prise | Référence | 110.7 | 10.0 | 11.0 | 24.4 | -14.7 | 0.0 | 1852 | 12.1 / 60.9 / 25.8 / 1.2 |
| Prise | Avant | 179.6 | 1.0 | 3.5 | 48.7 | -18.2 | -1.0 | 233 | 99.2 / 0.7 / 0.0 / 0.0 |
| Prise | Après | 110.7 | 7.0 | 14.1 | 27.2 | -15.9 | -0.5 | 1751 | 11.5 / 61.2 / 26.0 / 1.3 |
| Roque | Référence | 157.6 | 93.3 | 93.8 | 102.7 | -18.6 | 0.0 | 1329 | 33.3 / 57.2 / 3.9 / 5.6 |
| Roque | Avant | 262.4 | 90.8 | 90.4 | 101.4 | -19.3 | -1.0 | 261 | 89.9 / 10.1 / 0.0 / 0.0 |
| Roque | Après | 155.6 | 91.8 | 94.0 | 103.4 | -18.7 | -0.5 | 1344 | 33.0 / 57.4 / 3.9 / 5.8 |
| Échec | Référence | 46.9 | 14.0 | 14.5 | 6.5 | -13.7 | 0.0 | 2245 | 1.1 / 66.4 / 22.5 / 10.0 |
| Échec | Avant | 96.8 | 0.0 | 3.2 | 24.2 | -15.8 | -0.9 | 437 | 79.4 / 18.6 / 2.0 / 0.0 |
| Échec | Après | 35.9 | 14.0 | 12.7 | 11.1 | -14.4 | -0.6 | 2429 | 2.0 / 63.9 / 23.0 / 11.2 |
| Promotion | Référence | 102.8 | 59.9 | 65.6 | 55.3 | -17.3 | 0.0 | 989 | 15.1 / 79.1 / 5.7 / 0.0 |
| Promotion | Avant | 320.3 | 0.0 | 61.0 | 202.1 | -15.4 | -0.9 | 449 | 68.8 / 31.1 / 0.0 / 0.0 |
| Promotion | Après | 100.8 | 60.9 | 63.2 | 67.4 | -17.4 | -0.5 | 1036 | 15.2 / 79.1 / 5.7 / 0.0 |
| Refus | Référence | 186.6 | 15.0 | 34.2 | 54.6 | -19.2 | -2.8 | 449 | 64.5 / 35.3 / 0.1 / 0.0 |
| Refus | Avant | 102.8 | 0.0 | 11.3 | 60.1 | -17.4 | -3.7 | 996 | 52.8 / 32.2 / 14.0 / 1.0 |
| Refus | Après | 179.6 | 24.9 | 30.9 | 51.0 | -19.7 | -3.3 | 492 | 63.9 / 36.0 / 0.1 / 0.0 |

| Type | Écart absolu durée avant → après (ms) | Écart centroïde avant → après (Hz) | Écart RMS avant → après (dB) |
|---|---:|---:|---:|
| Coup blanc | 54.9 → 1.0 | 535.0 → 10.0 | 1.5 → 0.4 |
| Coup noir / retour | 52.9 → 0.0 | 589.0 → 40.0 | 1.1 → 0.5 |
| Prise | 68.9 → 0.0 | 1619.0 → 101.0 | 3.5 → 1.2 |
| Roque | 104.8 → 2.0 | 1068.0 → 15.0 | 0.8 → 0.1 |
| Échec | 49.9 → 11.0 | 1808.0 → 184.0 | 2.1 → 0.7 |
| Promotion | 217.5 → 2.0 | 540.0 → 47.0 | 1.9 → 0.1 |
| Refus | 83.8 → 7.0 | 547.0 → 43.0 | 1.8 → 0.5 |

La proximité de ces mesures ne prouve pas une identité perceptive : les phases, résonances fines et textures sont originales.
La crête des nouveaux coups est volontairement proche de -0,5 dBFS avant encodage pour garder une marge ; la référence atteint souvent 0 dBFS.
L'échec reste un peu plus court et sa décroissance diffère ; les prises ont une attaque légèrement anticipée et un RMS inférieur à la référence.
La synthèse demeure donc une approximation documentée, pas une copie ni une promesse d'identité sonore.

## Écarts visuels et comportementaux

| Aspect | Vidéo | ChessLocal avant | Travail réalisé |
|---|---|---|---|
| Pièce saisie | Environ 1,5 à 2 tailles de case, au-dessus de la cible | Clone à 1,2, centré sur le contact, fantôme à 50 % | Clone tactile à 1,7, dessin décalé de 0,85 case vers le haut, ombre légère, source masquée |
| Case visée | Grand disque gris translucide d'environ deux cases | Cadre blanc de 3 px | Disque tactile de deux cases, gris dérivé de `surface-3`, centré sur la case sous le doigt |
| Coups légaux | Points gris discrets pendant la saisie | Points après un tap seulement, plus gros | Sélection dès le début du glissé, points réduits, anneaux de prise conservés |
| Dernier coup | Départ et arrivée jaunes | Déjà jaunes | Teintes existantes conservées, vérifiées par la suite touch |
| Pose légale | Pièce revenue à sa taille normale à la pose | Déjà immédiate | Comportement de la bibliothèque conservé, aucun coup ni son pendant le glissé |
| Refus | Pièce ramenée avec un son grave | Retour instantané, son plus aigu | Retour de 120 ms et impact synthétique grave, position inchangée |
| Clic-clic | Déplacement court vers la cible | Animé en 80 ms | Animé en 120 ms ; réduction des animations respectée |
| Réponse adverse automatique | Non observable dans cette vidéo d'analyse | Animée en 80 ms | Même animation partagée de 120 ms ; déclenchement sonore existant conservé |
| Son à la pose | Pas de décalage visible à la précision de l'enregistrement | Déjà à la pose dans la reproduction E2E | Aucun délai ajouté ; tests du bon type, de l'unicité et d'un départ pendant l'événement de pose |
| Timbre et volumes | Impacts secs, prise plus brillante, refus plus grave | Impacts bois Kenney nettement plus graves pour les coups légaux | Sept synthèses originales mesurées ci-dessus ; notifications Kenney conservées |
| Souris | Hors référence | Clone centré à 1,2, cadre blanc | Géométrie souris conservée et vérifiée à 1440 × 900 |

Le check E2E exige que le son démarre pendant la diffusion de l'événement de fin de geste qui joue le coup (`window.event` relevé par l'espion audio), une fois tous les sons décodés.
Ce critère ne dépend pas de la charge de la machine : un son repoussé à une tâche ultérieure (setTimeout, image suivante, fin d'animation) échoue, même quelques millisecondes plus tard.
Un budget de 250 ms (80 ms pour le coup d'un puzzle) reste un filet contre un long travail synchrone ajouté avant le son.
Depuis le 23 octobre 2026, il se compte depuis le début de la diffusion de l'événement (premier écouteur, posé par l'espion en capture sur la fenêtre), et non plus depuis son horodatage navigateur (`timeStamp`).
L'écart entre les deux est l'attente de l'événement dans la file du thread principal : elle ne dépend que de la charge de la machine, pas du code du geste.
Sous un gate parallèle, le check du puzzle a relevé 117,6 ms alors que le travail du geste mesure quelques millisecondes (6,4 ms sous `E2E_CPU_RATE=4`) ; un thread principal occupé 150 ms juste avant le relâchement donne « file 149,7 ms, geste 1,4 ms ».
Le budget est en temps CPU de la page : il est multiplié par `E2E_CPU_RATE`, qui ralentit d'autant le travail du geste.
Le détail du check affiche les deux durées (« file » et « geste ») pour chaque son.
Il ne garantit pas une latence acoustique sur iPhone.
L'espion Web Audio mesure séparément le délai futur passé à `start()` et exige moins de 80 ms, afin qu'une programmation retardée ne profite pas du budget de 250 ms.
Aucun appel haptique n'est ajouté : `navigator.vibrate` n'est pas disponible dans Safari iOS et aucune technique fiable vérifiée sur cet appareil n'est disponible ici.
La vérification navigateur utilise Chromium avec contexte iPhone 14 Pro standalone et émulation des restrictions audio WebKit ; une validation tactile et acoustique sur iPhone physique reste nécessaire.

## Preuves par mutations

Chaque mutation a été appliquée temporairement à l'implémentation, exécutée seule, puis retirée avant le gate final.

| Mutation | Échecs constatés |
|---|---|
| Échelle tactile à 1, décalage nul, cible figée sur la source, points supprimés, animation de retour supprimée | Taille, soulèvement, cible intermédiaire et finale, coups légaux tactile et souris, retour animé |
| `AudioBufferSourceNode.start()` programmé 200 ms plus tard | Timing du coup tactile et souris, clic-clic adverse, prise, roque, échec et promotion |
| `E2E_MUTATION=sound-sync` : 300 ms de travail synchrone avant chaque son, dans le geste (23 octobre 2026) | Budget du geste pour le coup tactile et souris, le clic-clic adverse, la prise, le roque, l'échec, la promotion et le puzzle |
| Tous les coups remplacés par `game-start` | Typage de chaque son, tactile et souris |
| Pose légale refusée | Pièce non jouée à la pose et absence de son attendu |
| Pièce source cachée après refus | Pièce non visible au retour |
| Son au début du drag et coup joué au survol | Silence pendant le glissé et absence de coup avant la pose |

## Inventaire des événements

Les numéros correspondent à l'ordre temporel des 48 sons extraits, avec le début de la fenêtre de détection corrigé de l'horodatage audio.
« Blanc » et « noir » désignent ici la couleur jouée dans Analyse, pas une personne ou un moteur distinct.

| N° | Temps s | Catégorie |
|---|---:|---|
| 1 | 1.348 | Coup blanc |
| 2 | 2.318 | Coup noir / retour |
| 3 | 3.278 | Coup blanc |
| 4 | 6.628 | Coup noir / retour |
| 5 | 7.298 | Coup blanc |
| 6 | 8.168 | Prise |
| 7 | 8.748 | Prise |
| 8 | 12.468 | Prise |
| 9 | 13.008 | Prise |
| 10 | 13.988 | Coup noir / retour |
| 11 | 14.868 | Coup blanc |
| 12 | 17.718 | Refus |
| 13 | 18.448 | Refus |
| 14 | 19.578 | Coup noir / retour |
| 15 | 20.568 | Roque |
| 16 | 27.318 | Refus |
| 17 | 28.048 | Refus |
| 18 | 28.768 | Refus |
| 19 | 35.328 | Refus |
| 20 | 36.128 | Refus |
| 21 | 37.758 | Coup noir / retour |
| 22 | 39.328 | Coup noir / retour (retour de navigation) |
| 23 | 43.238 | Coup noir / retour |
| 24 | 44.438 | Coup blanc |
| 25 | 46.108 | Prise |
| 26 | 48.288 | Prise |
| 27 | 49.068 | Prise |
| 28 | 50.578 | Coup blanc |
| 29 | 51.338 | Prise |
| 30 | 51.788 | Prise |
| 31 | 52.918 | Coup noir / retour |
| 32 | 53.598 | Échec |
| 33 | 56.838 | Coup noir / retour |
| 34 | 60.478 | Coup blanc |
| 35 | 62.508 | Coup noir / retour |
| 36 | 62.988 | Prise |
| 37 | 66.468 | Coup noir / retour |
| 38 | 68.228 | Coup blanc |
| 39 | 69.918 | Refus |
| 40 | 70.748 | Refus |
| 41 | 72.228 | Refus |
| 42 | 72.818 | Refus |
| 43 | 75.078 | Coup noir / retour |
| 44 | 76.808 | Coup blanc |
| 45 | 77.958 | Roque |
| 46 | 79.548 | Prise |
| 47 | 81.878 | Coup noir / retour |
| 48 | 83.108 | Promotion |

## Validation historique (15 octobre)

`npm ci` a été exécuté avec Node 22.21.1 en tête du PATH.
`npm run check` est vert (oxlint et TypeScript).
Le gate de production a exécuté les suites une par une, via `e2e/run.py`, avec serveur et build temporaires gérés par le lanceur.

| Suite | Résultat |
|---|---|
| feeling | 30 checks réussis |
| touch | 63 checks réussis |
| pieces_sons | 74 checks réussis |
| audio_settings | 9 checks réussis |
| puzzles | 79 checks réussis |
| play_lifecycle | 84 checks réussis |

Commande : `npm run test:e2e -- --suite feeling --suite touch --suite pieces_sons --suite audio_settings --suite puzzles --suite play_lifecycle`.
Les captures ChessLocal pendant le geste sont `e2e/shots/f14_drag_tactile.png` et `e2e/shots/f14_drag_souris.png` (gitignorées).
Une seconde génération des sons produit exactement les mêmes empreintes SHA-256 ; les notifications Kenney sont inchangées.
Les six familles de mutations ont chacune donné un code de sortie non nul, puis ont été retirées.

## Reprise autorisée du 17 octobre 2026

Les comparaisons historiques ci-dessus décrivent la synthèse remplacée, pas les nouveaux MP3.
`scripts/extract-video-sounds.py` découpe les événements à 1,32 s (blanc), 2,29 s (noir), 8,13 s (prise), 20,53 s (roque), 53,56 s (échec), 83,07 s (promotion) et 17,68 s (refus).
Les fenêtres incluent le début de l’impact ; le silence est rogné à 0,2 % de la crête, la composante continue retirée, et deux fondus de bord évitent les clics artificiels.
La crête PCM est normalisée à -1 dBFS, puis encodée en MP3 mono 128 kbit/s.
Les notifications Kenney sont inchangées (comparaison octet par octet avec HEAD).
Le début actif des MP3 est compris entre 0,05 et 4,83 ms ; la queue de fichier conserve la décroissance faible, distincte de la durée active.

Mesures des MP3 distribués avec `python3 scripts/measure-sounds.py public/sounds/*.mp3` :

| Son | Durée active ms | Attaque ms | T50 ms | Décroissance ms | RMS dBFS | Crête dBFS | Centroïde Hz |
|---|---:|---:|---:|---:|---:|---:|---:|
| Coup blanc | 41,9 | 1,0 | 2,1 | 9,9 | -16,0 | -1,5 | 826 |
| Coup noir | 43,9 | 2,0 | 3,1 | 11,5 | -16,6 | -1,5 | 917 |
| Prise | 104,8 | 10,0 | 10,6 | 24,4 | -16,1 | -1,3 | 1862 |
| Roque | 168,6 | 94,8 | 94,8 | 102,6 | -20,4 | -1,4 | 1313 |
| Échec | 47,9 | 14,0 | 14,6 | 6,6 | -15,7 | -1,3 | 2242 |
| Promotion | 102,8 | 64,9 | 65,0 | 56,7 | -18,9 | -1,4 | 989 |
| Refus | 186,6 | 34,9 | 34,6 | 54,6 | -17,9 | -1,4 | 450 |

Ces impacts ne sont pas périodiques : le centroïde décrit leur brillance, pas une hauteur musicale fondamentale.
Le roque conserve ses deux contacts espacés d’environ 95 ms.

### Dessin et centrage

L’image de repos comporte des cases de 150,75 px.
Les silhouettes ont un socle large (environ 56 % de case), un contour proche de 2 % de case, des blancs presque purs et des noirs anthracite avec ombre latérale.
Atelier reprend ces proportions et les détails distinctifs : fente ouverte du fou, couronne à quatre pointes, croix du roi et deux ouvertures, profil courbe du cavalier.
`scripts/draw-atelier.py` conserve les tracés vectoriels sur une grille 100 × 100, sans bitmap ni source officielle chess.com.
Le jeu reste sélectionnable avec les six anciens jeux.
La migration persist ne donne Atelier qu’aux stockages sans jeu ; un jeu enregistré est conservé, sauf le Celtique implicite des stockages v0 qui devient Wikimedia comme avant.
Tous les autres choix et données sont préservés.

La reproduction initiale iPhone standalone montre des centres Wikimedia décalés de 4,3 à 8,4 % de case vers le haut alors que le transform de `.board-piece` est nul.
La cause est la marge interne des SVG, pas `--piece-lift`.
`PieceIcon` compense le centre de la boîte alpha supérieure à 127, mesurée à 512 px par `scripts/center-pieces.py`.
Le conteneur de glissé reste inchangé ; les douze pièces de chacun des sept jeux sont contrôlées.
L’oracle des SVG intégrés retire le transform CSS de sa copie avant rasterisation, sinon il compterait deux fois la correction.

### Audio : preuve et limites

Le diagnostic de la version déployée sans `--live` et la reproduction locale ne montrent pas de silence au premier glissé avec l’émulation des contraintes WebKit.
Ils montrent en revanche des coups obsolètes rejoués après un chargement lent (test rouge avant correction).
`playMoveSound` abandonne désormais un son de coup encore en attente dès qu’un coup plus récent est demandé, ou plus d’une seconde après la pose ; les notifications conservent leur comportement.
Les sons sont téléchargés et décodés dès le démarrage, sans geste : seule la reprise du contexte attend le premier toucher, et le premier coup ne dépend plus d’un téléchargement lancé par son propre geste.
Les échiquiers dont le propriétaire renvoie le coup accepté (analyse, puzzles, exercices, entraîneur d’ouvertures, cours, séances d’Apprendre, continuation contre le moteur) le font sonner dans le geste de pose, avant le rendu React ; un coup faux reste muet.
Le déverrouillage dans le geste, les reprises après arrière-plan, le volume, BASE_URL et le service worker sont contrôlés par les suites audio et PWA existantes.
Le silence observé sur l’appareil de Max ne peut pas être attribué avec certitude à cette cause sans essai acoustique sur cet iPhone.

### Cadrage au lancement de Jouer

La revue de la capture 393 × 660 a révélé un défaut distinct du centre des silhouettes : le défilement de la configuration était conservé au passage en partie.
Le test `piece_viewport` le reproduit avant correction avec un plateau à y = -81 px, contre y = 52 px en standalone 393 × 852.
`Play` remet le conteneur principal en haut à l’entrée dans l’état `playing`, après mise en page ; aucun défilement n’est imposé lors des coups suivants.

## Validation de la reprise (17 octobre 2026)

Toutes les commandes E2E sont passées par le verrou partagé à trois places, avec Node 22.21.1 et Playwright 1.56.0.
Le build de production tourne sous `/chess-local/` ; les API chess.com utilisent la fixture, sans `--live`.

| Suite de production | Checks réussis (dernier passage) | Code de sortie |
|---|---:|---:|
| piece_centers | 330 | 0 |
| piece_viewport | 6 | 0 |
| feeling | 30 | 0 |
| pieces_sons | 90 | 0 |
| audio_settings | 16 | 0 |
| touch | 63 | 0 |
| premove | 78 | 0 |
| edge_navigation | 193 | 0 |
| all_buttons | 96 | 0 |
| upgrade | 989 | 0 |
| backup | 228 | 0 |
| pwa | 53 | 0 |
| play_lifecycle | 84 | 0 |

`feeling` passe aussi en développement : 30 checks, code 0.
`npm run check` et `git diff --check` passent.
Le premier lot de production comptait 267 checks de centrage ; l’extension aux erreurs sauvegardées et à la révision porte cette suite à 330.
La dernière correction de cadrage est revérifiée avec `piece_viewport`, `pieces_sons`, `play_lifecycle` et `all_buttons` (276 checks, code 0).
Les cinq notifications sont identiques octet par octet à HEAD ; une régénération des 12 SVG et des sept impacts laisse les 24 empreintes SVG/MP3 identiques.

Captures relues dans `e2e/shots/` : `atelier_planche.png`, `centres_atelier.png`, `centres_atelier_attaque_att-05ejA.png`, `centres_atelier_apprendre_roque_grec-schema.png`, `f10_jouer_atelier_660.png`, `f10_jouer_atelier_852.png`, `f10_jouer_atelier_1440.png`, `f10_reglages_pieces_bas_852.png`, `f14_drag_tactile.png` et `plateau_depart_660.png`.
Comparaison visuelle avec `rest.png`, `contact.png`, `castle.png`, `check.png` et la capture iPhone de Max, conservées hors dépôt.
Les silhouettes restent lisibles sur cases claires et foncées, les pièces au repos sont centrées, et le plateau au lancement reste entier dans les deux hauteurs mobiles.
Le contrôle acoustique et tactile sur un iPhone physique reste à effectuer ; les tests navigateur ne permettent pas de conclure sur le commutateur silencieux ou l’état matériel du téléphone de Max.
