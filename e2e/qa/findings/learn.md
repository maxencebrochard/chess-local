Le fichier `findings-learn.md` n'existe pas : l'outil Write a refusé de l'écrire (« Subagents should return findings as text, not write report files ») et je n'ai pas contourné ce refus via Bash. Le contenu complet est ci-dessous, au format demandé, prêt à être enregistré à `e2e/qa/findings-learn.md`. Aucun script n'avait tourné pendant la panne du serveur, donc rien à rejouer.

Résumé : 28 constats, soit 2 critiques, 5 majeurs, 15 mineurs et 6 cosmétiques. Les cinq plus importants :
1. **LEARN-1** : une finale « gagne » est validée sans mat. Trois va-et-vient de dame (ou les premiers coups légaux venus) donnent « ✓ Réussi ! (+14 à +26) ».
2. **LEARN-2** : la finale « L'opposition de base » est une nulle théorique. Les meilleurs coups y donnent « ✗ Raté (-14) » à chaque fois.
3. **LEARN-3** : la séance est perdue au rechargement (F5) et au retour arrière depuis /analyse. Seul le bouton « ← Retour à l'exercice » la restaure.
4. **LEARN-4** : les lignes classiques de repli sont des variantes obscures. « Défense sicilienne » enseigne 2.b4 (gambit de l'aile), et Caro-Kann et Scandinave ne sont jamais proposées.
5. **LEARN-5/6/7** : des diagrammes et leçons sont faux (le diagramme du cours « Mater avec la dame » est un pat, la leçon « Roi devant le pion » conseille un coup illégal), et un puzzle reste jouable après « Raté » sans solution affichée.

Les trous connus (a) à (d) de la suite E2E sont couverts par `s1_course_sheet.py` : dans les 4 domaines, le bon cours s'affiche avec un contenu non vide, et la fermeture est réellement vérifiée.

---

# Findings QA - Apprendre (`/#/apprendre`)

`$L` = `e2e/qa/learn`.
Scripts : `$L/*.py` et `$L/static_audit.mjs`. Captures : `$L/shots/`. Logs : `$L/logs/` (s4 à s9).
Les Elo sont lus dans Dexie avant et après, pas seulement dans l'UI.

## LEARN-1 - Finales « gagne cette position » validées sans mater
- type: bug
- sévérité: critique
- page: /#/apprendre (Finales) ; viewport: 393x852, 393x660, 1440x900
- statut: reproduit (5 fois, 3 viewports)
- repro: `python3 $L/s2_endgames_a.py` (scénario `eg_kq_shuffle`). Sur « Mat roi + dame », jouer Da2, Da1+, Da2 sans bouger le roi blanc. Variante : `s2_endgames_b.py eg_kr_shuffle`.
- attendu: l'entraînement de finales de chess.com exige le mat (ou la promotion) sur l'échiquier. Un va-et-vient ne valide jamais.
- observé:
  - « ✓ Réussi ! (+14) » au 3e coup, position 8/8/5k2/8/8/8/Q7/4K3, sans mat.
  - Roi + tour : 9 coups de tour sans but, roi blanc jamais bougé, puis « Réussi (+20) ».
  - Dans `s7_auto.py`, jouer le premier coup légal venu donne « Réussi (+26) ».
  - Même avec les meilleurs coups, le verdict tombe au 3e coup : le joueur ne donne jamais le mat dans « Mat roi + dame ». « Roi devant le pion » est aussi validé au 3e coup, avant la promotion.
- capture: `$L/shots/eg_kq_shuffle_end.png`, `eg_kq_best_end.png`, `eg_kr_shuffle_end.png`, `s8_desktop_verdict.png`
- cause probable: `src/pages/Learn.tsx:491-498`. Le succès est déclaré dès que `cpPlayer >= 600` sur 6 évaluations consécutives (une par demi-coup, donc 3 coups). Avec roi + dame contre roi, l'éval vaut au moins 600 dès la position initiale.
- correctif proposé:
  - Ajouter `goal: 'mate' | 'promote' | 'hold'` dans `endgames.json`.
  - Pour `mate`, ne déclarer le succès que sur `isCheckmate()`. Pour `promote`, à la promotion avec éval conservée.
  - Garder l'éval seulement pour détecter l'échec (avantage lâché) et pour un plafond de coups, avec message.

## LEARN-2 - « L'opposition de base » est une nulle théorique : exercice impossible
- type: bug / contenu
- sévérité: critique
- page: /#/apprendre (Finales, `kp-opposition-1`) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s2_endgames_b.py eg_kpopp_best` (meilleurs coups de Stockfish natif) et `python3 $L/static_endgames.py`.
- attendu: une position annoncée « gagne cette position » doit être gagnante avec le trait indiqué.
- observé:
  - Pour 8/8/8/4k3/8/4K3/4P3/8 trait aux Blancs, Stockfish 18 natif donne 0,00 à profondeur 59. La même position trait aux Noirs est mat en 21.
  - Dans l'app : 1.Rd3 Rd5 2.Re3 Re5 donne « ✗ Raté (-14) », Elo 800 vers 786. Le joueur perd de l'Elo quoi qu'il joue.
  - La légende du cours affirme « Kd3 ou Kf3 gagne le terrain de côté ; e5 face au roi serait une faute », ce qui est faux. De plus e5 est occupée par le roi noir.
- capture: `$L/shots/eg_kpopp_best_end.png`, `s10_course_kp-opposition-1.png`
- cause probable:
  - `src/data/endgames.json:6` (FEN) et `src/data/courses.json:59` (même FEN, légende fausse).
  - `Learn.tsx:494-497` : éval inférieure ou égale à 80 sur 4 demi-coups donne « Raté ».
- correctif proposé:
  - Remplacer la FEN par `8/8/4k3/8/8/4K3/4P3/8 w - - 0 1` dans les deux fichiers (1.Re4 prend l'opposition, mat en 19 vérifié au Stockfish natif).
  - Réécrire la légende en notation française.

## LEARN-3 - Séance perdue au rechargement et au retour arrière depuis /analyse
- type: bug
- sévérité: majeur
- page: /#/apprendre et /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s6_mistakes.py`.
  - (a) En séance, phase jeu, recharger la page.
  - (b) Depuis un verdict, taper « Analyser », puis faire `history.back()` au lieu du bouton « ← Retour à l'exercice ».
- attendu: reprise de la séance (item, phase, résultats). chess.com reprend une leçon en cours. Sur iPhone en PWA, le rechargement arrive dès qu'iOS purge l'app en arrière-plan. Le retour arrière correspond au swipe-back (détail chez l'agent gestes).
- observé:
  - Dans les deux cas : retour à l'accueil Apprendre, `sessionStorage['learn-session-v1']` effacé, items restants et récap perdus.
  - Par le bouton « ← Retour à l'exercice », la restauration fonctionne, y compris en double aller-retour (item, phase et `scoredItems` corrects).
- capture: `$L/shots/s6_after_reload.png`, `s6_history_back.png`
- cause probable:
  - `Learn.tsx:72-89` ne restaure que si `location.state.restore` est présent.
  - Au montage avec `session === null`, l'effet `:92-99` exécute `removeItem`.
- correctif proposé:
  - Restaurer dès qu'une séance stockée existe au montage, sans drapeau.
  - Ne supprimer la clé que sur ✕, « Terminer » et fin de séance.

## LEARN-4 - Lignes classiques de repli = variantes obscures, 2 classiques jamais servies
- type: contenu / bug
- sévérité: majeur
- page: /#/apprendre (Ouvertures, archive vide) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s4_openings.py` (log `$L/logs/s4.log`).
- attendu: lignes principales, comme dans les cours d'ouvertures de chess.com. Une défense devrait se driller côté noir.
- observé:
  - « Défense sicilienne » = gambit de l'aile, variante Carlsbad (1.e4 c5 2.b4 cxb4 3.a3 bxa3). Après un autre coup, message « Pas la ligne : ici, la théorie joue b4 ». La ligne attendue est `b2b4`, donc 2.Cf3 est refusé lui aussi.
  - « Défense française » = gambit Diemer-Duhm accepté (3.c4 dxe4).
  - « Gambit dame » = contre-gambit Salvio (2...c5 3.dxc5 d4).
  - Les 8 lignes sont jouées côté blanc, y compris les défenses.
  - Caro-Kann et Scandinave ne sortent jamais avec une archive vide.
- capture: `$L/shots/s4_wrong_2_c7c5.png`, `s4_lesson_2.png`
- cause probable:
  - `src/lib/repertoire.ts:66-67` prend la ligne la plus courte, d'au moins 6 demi-coups, dont le nom commence par la famille.
  - `:69` fixe `playerColor: 'w'`.
  - `src/lib/learn.ts:133` fait `pick(lines.slice(0, 6))` sur 8 classiques.
- correctif proposé:
  - Remplacer `CLASSICS` par 8 lignes explicites `{ name, uci, playerColor }` : Giuoco Piano, Espagnole Morphy, Sicilienne ouverte, Française Cc3, Gambit dame refusé orthodoxe, Londres, Caro-Kann classique côté noir, Scandinave Dxd5 côté noir.
  - Tirer parmi toutes les lignes.

## LEARN-5 - Diagrammes et légendes de cours faux
- type: contenu
- sévérité: majeur
- page: feuille de cours (`?`) ; viewport: 393x852
- statut: reproduit (rendu capturé et positions vérifiées avec python-chess)
- repro: `python3 $L/s10_content_shots.py` et `node $L/static_audit.mjs`.
- attendu: un diagramme qui illustre le thème, avec une légende exacte.
- observé:
  - (a) `kq-mate` (`courses.json:29`) : 7k/5Q2/6K1 trait aux Noirs est un pat (0 coup légal, pas d'échec). La légende dit « Position finale type : la dame mate [...] ici c'est PAT si la dame était en g6 ». Le cours sur le pat montre donc un pat en le présentant comme le modèle.
  - (b) `skewer` (`:189`) : légende de brouillon (« Après Ta2xe1+? ... non : ici Te1 enfile déjà... »). Il n'y a pas de tour en a2, aucune enfilade, et les Noirs matent en 1 (Dc2# ou Da1#).
  - (c) `rookEndgame` (`:327`) : « Ta2 derrière le pion d2 : il est figé pour toujours ». La tour est sur la même rangée que le pion, pas derrière, et Rxd2 ou Txd2 le gagne immédiatement.
  - (d) `discoveredAttack` (`:199`) : la flèche c1 vers c8 pointe une case vide (le roi noir est en e8). La légende dit « la tour c1 cloue la colonne », terme impropre. Les deux flèches se superposent sur la colonne c.
  - (e) `opposition-distant` (`:109`) : « Trois cases entre les rois » alors qu'il y en a 2 (b4 et b5). C'est un cours sur le comptage.
  - (f) `kp-opposition-1` : voir LEARN-2.
- capture: `$L/shots/s10_course_kq-mate.png`, `s10_course_skewer.png`, `s1_Tactiques_sheet_top.png`
- cause probable: données `src/data/courses.json` aux lignes citées.
- correctif proposé:
  - (a) FEN `7k/8/5QK1/8/8/8/8/8 w` avec flèche f6 vers g7 (« Dg7 mat »).
  - (b) Par exemple `4k3/8/8/8/8/8/8/4K2R`... non : mettre une vraie enfilade, par exemple roi noir e8 et dame noire e1 remplacés par une position où une tour blanche donne échec sur la colonne et ramasse la pièce derrière le roi.
  - (c) `3k4/8/8/8/8/8/3p4/3RK3` avec légende adaptée, ou tour en d8 derrière un pion blanc.
  - (d) Dame noire en c8.
  - (e) Écrire « Deux cases ».
  - Ajouter au E2E ou au lint un contrôle chess.js : pas de pat ni de mat involontaire, case de départ des flèches occupée.

## LEARN-6 - Puzzle encore jouable après « Raté », sans solution
- type: bug / ux
- sévérité: majeur
- page: /#/apprendre (Tactiques, Stratégie) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s3_tactics.py`. À l'item 2, jouer un coup faux, puis taper le bon coup sous le bandeau « ✗ Raté ».
- attendu: chess.com fige l'échiquier, montre le bon coup (ou propose « Solution ») et permet « Réessayer ».
- observé:
  - Le mauvais coup revient en arrière sans aucun retour visuel.
  - « ✗ Raté (-26) » s'affiche, mais le board reste interactif : le bon coup Fxg4+ est accepté et l'adversaire répond Dxg4+, sous le bandeau « Raté ».
  - Le bon coup n'est jamais montré. Le seul accès à la solution est « Analyser ».
- capture: `$L/shots/s3_item2_fail.png`, `s3_item2_fail_then_move.png`
- cause probable: `src/components/PuzzlePlayer.tsx:72-81`. La branche « faux » appelle `onComplete(false)` sans `setDone(true)`, alors que `interactive={!done}` (`:102`).
- correctif proposé:
  - Exécuter `setDone(true)` sur échec.
  - Dans `PuzzleExercise`, afficher après échec une flèche sur `puzzle.moves[stepIndex]` et une bulle « Le bon coup était ... ».

## LEARN-7 - La leçon « Roi devant le pion » conseille un coup illégal
- type: contenu
- sévérité: majeur
- page: /#/apprendre (Finales, `kp-king-front`) ; viewport: tous
- statut: reproduit (python-chess : `e4e5` illégal ; le meilleur coup joué dans l'app est 1.e3)
- repro: lire la bulle de leçon de `kp-king-front`, puis essayer Re5 sur le board.
- attendu: un conseil jouable.
- observé:
  - La leçon dit « Monte le roi en e5 d'abord, le pion attendra », mais le roi noir en e6 contrôle e5.
  - Le coup gagnant le plus net est le coup d'attente 1.e3.
  - La légende du cours dit « monter le roi d'abord », même contresens.
- capture: `$L/shots/eg_kpfront_best_start.png`
- cause probable: `src/data/endgames.json:7` et `src/data/courses.json:69`.
- correctif proposé: « Les rois se font face et c'est à toi de jouer : pousse e3 pour rendre le trait et reprendre l'opposition, puis contourne avec le roi. »

## LEARN-8 - Delta Elo périmé après « Réessayer »
- type: bug
- sévérité: mineur
- page: séance, barre de verdict ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s3_tactics.py`. Rater l'item 2 (« ✗ Raté (-26) »), taper « Réessayer », puis résoudre.
- attendu: « ✓ Réussi ! » sans delta, ou avec la mention « non classé ».
- observé:
  - Affichage « ✓ Réussi ! (-26) ».
  - Il n'y a pas de double comptage : l'Elo en base (796) et le nombre de lignes `learnSessions` (2) sont inchangés.
- capture: `$L/shots/s3_item2_retry_success.png`
- cause probable: `Learn.tsx:148-152`. `retryItem` ne remet pas `ratingDelta` à `null`, et `finishItem` (`:141`) ne le recalcule pas pour un réessai.
- correctif proposé: appeler `setRatingDelta(null)` dans `retryItem`, et aussi dans `nextItem`.

## LEARN-9 - Après « Analyser » puis retour : finale réinitialisée, delta disparu, éval 0,00
- type: bug
- sévérité: mineur
- page: /#/apprendre vers /#/analyse et retour ; viewport: 393x852
- statut: reproduit
- repro: fin de `python3 $L/s7_auto.py`.
- attendu: retrouver la position finale et le verdict complet.
- observé:
  - Avant l'aller-retour : {Rf6, Da2, Re1} et « Réussi (+14) ».
  - Après retour : position initiale {Re5, De2, Re1}, « ✓ Réussi ! » sans delta, éval « 0,00 ».
  - /analyse reçoit la position de départ de la finale, pas la partie jouée.
- capture: `$L/shots/s7_eg_back.png`, `s7_eg_analyse.png`
- cause probable:
  - `StoredSession` (`Learn.tsx:26-32`) ne stocke ni la position jouée ni `ratingDelta`.
  - `analyseItem` (`:161`) n'envoie que `endgame.fen`.
- correctif proposé:
  - Remonter le PGN de l'exercice dans l'état de séance et le persister.
  - L'envoyer à /analyse (`pgn`).
  - Réhydrater `chessRef` et `ratingDelta` à la restauration.

## LEARN-10 - Barre de verdict cassée à 393 px
- type: bug visuel
- sévérité: mineur
- page: séance, phases succès et échec ; viewport: 393x852 et 393x660
- statut: reproduit (mesuré)
- repro: `python3 $L/s3_tactics.py` (sortie `geom`) et `s8_viewports.py`.
- attendu: une seule ligne, avec des marges symétriques de 12 px.
- observé:
  - Le bloc verdict mesure 84 px de haut pour une hauteur de ligne de 28 px : « ✓ », « Réussi » et « ! » sont sur 3 lignes.
  - « ✗ Raté (-26) » passe sur 2 lignes.
  - Le bouton « Suivant » finit à x=391 sur 393, soit 2 px du bord contre 12 px à gauche, et son ombre est rognée.
  - La barre mesure 100 px à 660 de haut.
  - Rendu correct à 1440 de large.
- capture: `$L/shots/eg_kq_best_end.png`, `s3_item1_success.png`
- cause probable: `Learn.tsx:395-425`. Le span de verdict peut rétrécir dans un flex sans `whitespace-nowrap`, et la somme des largeurs (Réessayer 76, Analyser 66, Suivant 112, gaps) dépasse 369 px.
- correctif proposé:
  - Ajouter `whitespace-nowrap shrink-0` sur le verdict et le delta.
  - Passer « Suivant » en `px-4`, avec `gap-1` à droite.
  - Ou passer sur 2 rangées : verdict et delta, puis actions.

## LEARN-11 - Barre d'éval des finales : « 0,00 » sur position gagnée, « +100,00 » pour un mat
- type: bug visuel
- sévérité: mineur
- page: /#/apprendre (Finales) ; viewport: tous
- statut: reproduit
- repro: ouvrir n'importe quelle finale « gagne », puis jouer un coup.
- attendu: l'éval réelle dès l'affichage, et « M8 » pour un mat, comme sur chess.com.
- observé:
  - « 0,00 » et barre à 50 % sur roi + tour contre roi, jusqu'au premier coup.
  - Ensuite « +100,00 », ou « +56,42 », « +81,15 ».
- capture: `$L/shots/s1_Finales_play_after_close.png`, `eg_kq_best_end.png`, `s8_desktop_verdict.png`
- cause probable:
  - `Learn.tsx:461` : `useState(0)`.
  - `:488` convertit un mat en ±10000 cp.
  - `:550` passe `mate={null}` à `HEvalBar`.
- correctif proposé:
  - Initialiser `liveCp` à `null` et lancer `evalAndCheck` au montage.
  - Garder `scoreMate` dans l'état et le passer à `HEvalBar`.
  - Plafonner l'affichage à ±10.

## LEARN-12 - Paysage 852x393 : échiquier coupé
- type: bug visuel
- sévérité: mineur
- page: séance, phase jeu ; viewport: 852x393
- statut: reproduit (mesuré)
- repro: `python3 $L/s8_viewports.py` (bloc `landscape`).
- attendu: l'échiquier entier est visible, sans scroll.
- observé:
  - Board en y=140, hauteur 299, donc bas à 439 alors que la hauteur visible est 393. Les rangées 1 et 2, qui portent les pièces du joueur, sont sous la ligne de flottaison.
  - Le conteneur défile : 439 px de contenu pour 393 visibles.
  - Le manifest ne verrouille pas l'orientation.
- capture: `$L/shots/s8_landscape_play.png`
- cause probable: `.boardbox` vaut `76vh` (`src/index.css:26-28`) sans déduire l'en-tête, le bandeau et la barre d'éval (140 px).
- correctif proposé:
  - En paysage, passer en 2 colonnes (board à gauche, consigne et verdict à droite) avec une largeur `min(100dvh - 24px, ...)`.
  - Ou ajouter `orientation: 'portrait'` au manifest.

## LEARN-13 - « Je vérifie… » fait sauter le board de 28 px
- type: bug visuel
- sévérité: mineur
- page: /#/apprendre (Mes erreurs) ; viewport: 393x852
- statut: reproduit (échantillonnage par frame)
- repro: `python3 $L/s9_misc.py` (bloc 3).
- attendu: aucun saut de layout. Le drill d'ouverture réserve déjà sa hauteur de message.
- observé: le haut du board passe de 104 à 132 px, puis revient à 104 (11 frames, 146 ms ici, plus long quand le moteur est chargé).
- capture: aucune (mesure : tops observés = [104, 132])
- cause probable: `Learn.tsx:702`. Le `<p>` est inséré conditionnellement au-dessus du board.
- correctif proposé: réserver la hauteur du `<p>` (`min-h` constant, texte vide sinon), ou afficher le message en surimpression sous le board.

## LEARN-14 - Taille et position du board différentes selon le domaine
- type: bug visuel
- sévérité: mineur
- page: séance, phase jeu ; viewport: 393x852
- statut: reproduit (mesuré)
- repro: `python3 $L/s9_misc.py` (bloc 2).
- attendu: même taille et même position d'échiquier partout, sans saut entre exercices.
- observé:
  - Tactiques et Stratégie : x=6, y=64, largeur 381.
  - Finales : x=12, y=140, largeur 369.
  - Ouvertures : y=146.
  - Mes erreurs : y=104.
  - Les puzzles n'ont aucun bandeau de consigne : ni trait, ni thème, ni niveau.
- capture: `$L/shots/s3_item1_success.png` contre `s1_Finales_play_after_close.png`
- cause probable:
  - `Learn.tsx:443` : `px-1`, sans bandeau.
  - `:546`, `:630`, `:697` : `px-3` avec un ou deux bandeaux.
- correctif proposé:
  - Un gabarit commun : bandeau de consigne, zone de message de hauteur fixe, board.
  - Pour les puzzles, un bandeau « Trait aux Noirs · Fourchette ».

## LEARN-15 - Textes du drill : genre fautif et bandeau tronqué
- type: contenu
- sévérité: mineur
- page: /#/apprendre (Ouvertures) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s4_openings.py`.
- attendu: un français correct, et le camp à jouer toujours lisible.
- observé:
  - Leçon : « ... les 3 premiers coups de la Gambit dame refusé », « de la Système de Londres ».
  - Bandeau : « Défense sicilienne - les 3 premiers coups, côté … ». Tronqué pour 3 lignes sur 4 (contenu de 384 à 399 px pour 369 disponibles) : le camp disparaît.
- capture: `$L/shots/s4_wrong_2_c7c5.png`, `s4_end_4.png`, `s4_lesson_4.png`
- cause probable: `Learn.tsx:373` (« de la » codé en dur) et `:631` (`truncate`).
- correctif proposé:
  - Écrire « Objectif : dérouler les N premiers coups ({nom}) ».
  - Bandeau sur 2 lignes : le nom, puis « N coups · côté blanc ».

## LEARN-16 - Drill réussi, +33 Elo, alors que la solution a été montrée
- type: ux
- sévérité: mineur
- page: /#/apprendre (Ouvertures) ; viewport: 393x852
- statut: reproduit
- repro: `s4_openings.py`, ligne idx=2. Une faute : flèche et texte du bon coup affichés, puis « ✓ Réussi ! (+33) », Elo de 800 à 833.
- attendu: pas d'Elo gagné sur un coup révélé.
- observé: avec 3 coups à trouver, un tiers de la réponse est donné et le gain reste plein.
- capture: `$L/shots/s4_end_2.png`
- cause probable: `Learn.tsx:580` (`onFinish(faults <= 1)`).
- correctif proposé: succès classé seulement si `faults === 0`. Avec 1 faute : « Réussi avec aide », non classé.

## LEARN-17 - Figurine incohérente pour un même coup
- type: contenu
- sévérité: cosmétique
- page: /#/apprendre (Mes erreurs) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s6_mistakes.py`.
- attendu: la même figurine partout pour un même coup.
- observé:
  - La leçon affiche « tu avais joué ♝e2 » (figurine noire pour un coup blanc).
  - Le bandeau de jeu affiche « ♗e2 ».
  - La figurine est nettement plus petite que le texte dans la bulle.
- capture: `$L/shots/s6_mistake_lesson.png`, `s6_back_1.png`
- cause probable: `Learn.tsx:374` appelle `figurine(playedSan)` sans couleur (défaut `'b'`), alors que `:700` passe `moverColor`.
- correctif proposé: passer `new Chess(fenBefore).turn()` aussi en `:374`.

## LEARN-18 - Notation anglaise dans 6 légendes de cours
- type: contenu
- sévérité: mineur
- page: feuille de cours ; viewport: tous
- statut: reproduit (lecture des données et rendu)
- repro: `node $L/static_audit.mjs`, ou ouvrir les cours concernés.
- attendu: notation française partout (R, D, T, F, C).
- observé:
  - « Kd3 ou Kf3 » (`courses.json:59`), « Ke4 » (`:69`), « Kh8 » (`:89`), « Ke3 », « Kf5 » (`:99`), « Kb4 » (`:109`).
  - « Ra3+ » (`:129`) se lit « Roi a3 » en notation française.
  - Les autres légendes sont en français (Th8, Tb4, Cf3).
- capture: `$L/shots/s10_course_kp-opposition-1.png`
- cause probable: données.
- correctif proposé: remplacer K par R et R par T, et ajouter un test regex `\b[KQNB][a-h][1-8]` sur `courses.json`.

## LEARN-19 - « Séance » ne choisit pas le domaine le plus faible ; ✕ abandonne sans confirmation
- type: ux
- sévérité: mineur
- page: /#/apprendre ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s7_auto.py` (Tactiques forcé à 1500, Finales à 600).
- attendu: prioriser le domaine faible (promesse « adaptées à ton niveau »), et demander confirmation avant d'abandonner.
- observé:
  - Ordre constant endgame, tactic, opening, strategy, endgame. Tactiques (1500) est servi en 2e.
  - ✕ en plein exercice : retour immédiat à l'accueil, rien d'enregistré, aucune pénalité.
  - Une finale qui tourne mal peut donc être quittée avant les 4 évaluations mauvaises, sans perte d'Elo.
- capture: `$L/shots/s7_end_zero.png`
- cause probable:
  - `learn.ts:66-80` : tourniquet par ancienneté dans `learnSessions`, compté par item et non par séance.
  - `Learn.tsx:232` : fermeture directe.
- correctif proposé:
  - Pondérer par `min(Elo)` parmi les domaines non travaillés récemment.
  - Sur ✕ en phase `play` : feuille « Abandonner ? (compte comme raté) ».

## LEARN-20 - Pas d'Indice, leçon sans échiquier, fin de séance sans bilan
- type: ux
- sévérité: mineur
- page: séance ; viewport: 393x852
- statut: reproduit pour l'UI ; déduit du code pour le câblage
- repro: parcourir une séance (captures `s1_*_lesson.png`, `s3_end_screen.png`).
- attendu, référence chess.com:
  - un bouton Indice sur les puzzles ;
  - l'échiquier visible pendant la consigne ;
  - un récap de fin avec le delta Elo de la séance et la liste des items.
- observé:
  - `PuzzlePlayer` accepte `hintSquare` mais Learn ne le passe jamais.
  - La phase « leçon » est un écran vide à 60 % (la bulle seule, centrée), puis tout l'écran change.
  - L'écran de fin montre « 2/3 réussis · classement 815 », sans delta ni détail.
- capture: `$L/shots/s1_Finales_lesson.png`, `s3_end_screen.png`
- cause probable: `Learn.tsx:376-392` (leçon), `:197-219` (fin), `:445` (pas de `hintSquare`).
- correctif proposé:
  - Afficher le board figé sous la bulle dès la leçon (le CTA devient « C'est parti » sous le board).
  - Bouton 💡 qui surligne la case de départ et rend l'item non classé.
  - Écran de fin : « +18 Elo » et pastilles ✓/✗ par item, avec « Revoir ».

## LEARN-21 - Parties réelles absentes du répertoire si la ligne reconnue fait moins de 6 demi-coups
- type: ux
- sévérité: mineur
- page: /#/jouer puis /#/apprendre (Ouvertures) ; viewport: 393x852
- statut: reproduit (2 parties réelles contre Noa, abandon au 5e coup : 0 ligne) ; seed Dexie pour le cas positif
- repro: `python3 $L/s5_repertoire.py` (log `$L/logs/s5.log`).
- attendu: des drills issus des parties du joueur.
- observé:
  - 1.e4 e6 2.Cf3 d5 3.Fc4... et 1.e3 e5... donnent 0 entrée dans `buildDrillLines()`.
  - Avec 2 parties Caro-Kann injectées (Noirs, perdues), le drill fonctionne : priorité à la ligne la plus perdue, board orienté côté noir, verdict et Elo corrects.
- capture: `$L/shots/s5_drill_play.png`
- cause probable: `repertoire.ts:58` filtre sur la longueur de la ligne du livre d'ouvertures, pas sur celle de la partie.
- correctif proposé: quand la ligne reconnue est courte, la prolonger par la continuation théorique la plus fréquente (`bookContinuations`), ou basculer sur la ligne principale de la famille.

## LEARN-22 - Puzzles hors niveau quand aucun puzzle n'est proche de l'Elo
- type: bug
- sévérité: mineur
- page: Tactiques, Stratégie
- statut: déduit du code et des données (`public/puzzles.json`)
- repro: Elo Tactiques inférieur ou égal à 550 et thème `trappedPiece` (minimum 730), `intermezzo` (minimum 778) ou `attraction` (minimum 686).
- attendu: les puzzles les plus proches de l'Elo du joueur.
- observé: quand rien n'est dans la fenêtre, `near()` renvoie tous les puzzles du thème, jusqu'à 2800.
- capture: aucune
- cause probable: `learn.ts:55-58`.
- correctif proposé: en repli, trier par `|rating - elo|` et garder les 50 plus proches.

## LEARN-23 - Cours : 1 id inatteignable, 16 cours sans diagramme, 14 diagrammes sans flèche, orientation figée
- type: contenu
- sévérité: mineur
- page: feuille de cours
- statut: reproduit (`node $L/static_audit.mjs`)
- repro: `node $L/static_audit.mjs`.
- attendu: chaque cours accessible, avec un diagramme fléché et orienté comme l'exercice.
- observé:
  - Couverture : 15 finales sur 15, 20 thèmes sur 20, 16 cartes sur 16 et Ouvertures ont un cours, avec des appariements cohérents.
  - `discoveredCheck` n'est jamais résolu : `find` s'arrête sur `discoveredAttack`. Le repli `?? item.card.id` est du code mort.
  - Carte `s-passed-pawn` : thèmes `advancedPawn, promotion`, donc cours « La promotion ». Acceptable.
  - Schéma correct partout : titres, intros, 2 sections et 3 ou 4 points clés non vides, FEN valides.
  - 16 cours sans diagramme : mats en 1, 2 et 3, pièce en prise, sacrifice, déviation, attraction, promotion, pièce piégée, intermezzo, défense, roi exposé, finales de pions, zugzwang, coup tranquille, échec à la découverte.
  - Le diagramme est toujours vu côté blanc, alors que `kp-square`, `rook-pawn-corner` et `philidor` se jouent côté noir : la position est retournée entre le cours et l'exercice.
- capture: `$L/shots/s10_course_mateIn1.png`, `s10_course_philidor.png` contre `s10_play_philidor.png`
- cause probable:
  - `Learn.tsx:347`.
  - `CourseSheet.tsx:32` (`orientation="w"`).
  - Données.
- correctif proposé:
  - Champ `course` explicite sur les cartes.
  - `diagram.orientation`.
  - Un diagramme fléché par cours.

## LEARN-24 - Cibles tactiles sous 44 pt, pas de libellé accessible
- type: a11y
- sévérité: mineur
- page: séance et feuille ; viewport: 393x852
- statut: reproduit (mesuré)
- repro: `python3 $L/s9_misc.py` (bloc 2) et `s1_course_sheet.py`.
- attendu: cibles d'au moins 44x44 pt et libellés accessibles.
- observé:
  - `?` : 36x36. ✕ de séance : 30x44. ✕ de feuille : 34x40. « Voir le cours complet » : 32 px de haut. Réessayer et Analyser : 42 px.
  - Le ✕ n'a ni `aria-label` ni `title`.
- capture: `$L/shots/s1_Finales_lesson.png`
- cause probable: `Learn.tsx:231-236`, `:244-250`, `:381-386` et `CourseSheet.tsx:23`.
- correctif proposé: `min-h-11 min-w-11` et `aria-label="Quitter la séance"` ou `"Fermer le cours"`.

## LEARN-25 - Erreur console React (mélange `background` et `backgroundColor`)
- type: bug
- sévérité: mineur
- page: tout board avec coups légaux affichés ; vu en Tactiques et Finales
- statut: reproduit (4 occurrences dans `s3`, 3 dans `s7`)
- repro: taper une pièce dont une case cible est aussi une case du dernier coup.
- attendu: une console propre.
- observé: « Removing background backgroundColor : a style property during rerender when a conflicting property is set... ».
- capture: aucune
- cause probable: `src/components/Board.tsx:104-105` (`backgroundColor`) puis `:117-121` (`background` sur la même case).
- correctif proposé: n'utiliser que `background` partout (couleur incluse dans le raccourci).

## LEARN-26 - Tirets cadratins et anglicismes dans l'UI et les cours
- type: contenu
- sévérité: cosmétique
- page: tous les textes d'Apprendre
- statut: reproduit
- repro: lire les bandeaux de séance et les cours.
- attendu: tiret simple partout (consigne globale du propriétaire) et termes français usuels.
- observé:
  - Tirets cadratins en `Learn.tsx:372`, `:548`, `:632`, `:699`, et dans une vingtaine de phrases de `courses.json` et `strategy.json`.
  - « La boxe à distance de cavalier », « La dame boxe le roi » : faux ami (la technique s'appelle « la boîte »).
  - « contre-attaque flashy ».
  - « épinglés » : le terme échiquéen est « cloués ».
- capture: `$L/shots/s10_course_kq-mate.png`
- cause probable: données et chaînes en dur.
- correctif proposé: remplacer par « - » ou « : », et écrire « la boîte », « tape-à-l'œil », « cloués ».

## LEARN-27 - `md:w-[min(56vh,520px)]` sans effet (écrasé par `.boardbox`)
- type: bug
- sévérité: cosmétique
- page: séance ; viewport: 1440x900
- statut: reproduit (board mesuré à 640 px alors que la classe vise 504)
- repro: `python3 $L/s8_viewports.py` (bloc `desktop`).
- attendu: que la classe `md:w-[...]` soit appliquée ou supprimée.
- observé: tout tient à 900 de haut. À 800 de haut ou moins, le verdict passe sous la ligne de flottaison (76vh + 140 + 68).
- capture: `$L/shots/s8_desktop_verdict.png`
- cause probable: `.boardbox` est hors `@layer` (`src/index.css:26`) et bat les utilitaires Tailwind 4, qui sont dans un layer (`Learn.tsx:444`, `:552`, `:639`, `:704`).
- correctif proposé: mettre `.boardbox` dans `@layer components`, ou retirer les classes mortes et borner par `calc(100dvh - 210px)`.

## LEARN-28 - Finale à objectif nulle : 12 coups de va-et-vient, verdict sans explication
- type: ux
- sévérité: cosmétique
- page: Finales (`rook-pawn-corner`) ; viewport: 393x852
- statut: reproduit
- repro: `python3 $L/s2_endgames_b.py eg_corner_draw`.
- attendu: un message du type « Nulle par répétition : objectif atteint ».
- observé:
  - Rg8/Rh8 joués 12 fois, puis « ✓ Réussi ! (+20) » par triple répétition (demi-coup 24).
  - Aucun verdict n'indique sa raison : pat, répétition, matériel insuffisant (dame donnée : « Raté (-26) » sec), plafond de 30 ou 60 demi-coups.
  - La règle des 50 coups est inatteignable, les plafonds tombent avant.
- capture: `$L/shots/eg_corner_draw_end.png`, `eg_kq_hang_end.png`
- cause probable: `Learn.tsx:477-504`. `conclude(ok)` ne prend pas de motif.
- correctif proposé: `conclude(ok, reason)` et afficher le motif dans la barre de verdict.

## Couverture
- Feuille de cours depuis Finales, Tactiques, Stratégie et Ouvertures, en leçon et en jeu :
  - titre comparé à `courses.json` via l'item lu dans `sessionStorage` ;
  - sections et points clés présents ;
  - diagramme 320 px avec flèches visibles ;
  - scroll interne au drag tactile (le fond reste à 0, y compris en paysage où il est scrollable) ;
  - fermeture par bouton bas, par ✕ et par tap sur le fond, vérifiée par l'absence de l'overlay ;
  - board identique après fermeture ;
  - `?` ne chevauche jamais le board, aux 4 viewports.
- Finales jouées au tap et au drag tactile :
  - roi + dame (va-et-vient, dame donnée, meilleurs coups) ;
  - roi + tour ;
  - opposition de base ;
  - roi devant le pion ;
  - pion tour (nulle réussie) ;
  - défendre devant le pion (nulle ratée, -20).
  - L'Elo évolue dans le bon sens à chaque fois (K=40 vérifié).
  - Le moteur défend de façon crédible. Il a répondu en 0,1 à 0,5 s dans les scénarios de finales mesurés.
- Tactiques :
  - 3 puzzles distincts, au tap et au drag ;
  - le réessai ne recompte pas l'Elo (base et `learnSessions` vérifiés) ;
  - compteur 1/3, 2/3, 3/3 et accord « 0/3 réussi », « 2/3 réussis » corrects.
- Stratégie : carte, cours et puzzles cohérents avec le thème.
- Mes erreurs :
  - alimenté par le bilan du PGN fourni (2 fautes, côté blanc) ;
  - `solved` et `attempts` corrects ;
  - compteur à jour.
- Aller-retour Analyser simple et double restaurés par le bouton retour (séance, item, phase).
- Aucune `pageerror`, aucun `undefined` ni `NaN`. `overflow_x` vaut 0 à tous les viewports. À 393x660, le CTA et le verdict sont visibles sans scroll.

## Hypothèses non vérifiées
- `env(safe-area-inset-*)` vaut 0 en émulation : le rendu sous la Dynamic Island n'a pas été vu.
- Finales non jouées : `two-pawns`, `opposition-distant`, `active-king-draw`, `r-vs-p`, `lucena`, `philidor`, `q-vs-r`, `rr-mate`, `kp-square`. Stockfish natif confirme leur issue théorique, sauf `q-vs-r` où le binaire natif local plante. Pat sur objectif « gagne » : conclu « Raté » d'après le code, non joué. Plafond de 60 demi-coups (`cp >= 300`) non atteint : le seuil de 600 se déclenche avant.
- Après un aller-retour Analyser sur un puzzle en phase verdict, `PuzzlePlayer` se remonte. Board probablement rejouable sous « Réussi », non testé.
- Avec `reviewColor` nul (PGN collé), `Analysis.tsx:344` enregistrerait aussi les fautes de l'adversaire sous « tu avais joué ». Non observé avec ce PGN.
- Hors périmètre, à transmettre :
  - `Play.tsx:190-227` : sauvegarde et Elo exécutés dans l'updater `setStatus`. En dev (StrictMode), chaque partie est enregistrée 2 fois (vu dans `s5`).
  - /analyse affiche les lignes du moteur en notation anglaise (« Qe4+ »).
  - Les coordonnées de react-chessboard sont recouvertes par les pièces en a1, e1 et a2.
  - Swipe-back : voir LEARN-3 (b), détail chez l'agent gestes.
