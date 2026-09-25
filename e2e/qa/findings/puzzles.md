Je n'ai pas pu créer `findings-puzzles.md` : l'outil Write refuse les fichiers de rapport écrits par un subagent et demande de renvoyer le contenu en texte. Je n'ai pas contourné ce blocage, le livrable complet est donc ci-dessous, prêt à être enregistré tel quel au chemin demandé.

## Synthèse

26 constats : 0 critique, 6 majeurs, 14 mineurs, 6 cosmétiques. Aucune `pageerror`, et une seule erreur console sur toute la campagne (PUZ-7).

1. **PUZ-1, majeur.** En Rush, trois coups faux rapides sur le même puzzle coûtent les 3 vies en moins de 200 ms, et un coup faux suivi du bon donne à la fois une vie perdue et un point (`PuzzleRush.tsx:82-100`).
2. **PUZ-2, majeur.** « Le bon coup était » affiche toujours `moves[1]` : après une erreur au 2e coup ou sur une sous-promotion, il montre le coup que je venais de jouer (`Puzzles.tsx:163`, `:210-213`).
3. **PUZ-3, majeur.** La série 🔥 et le puzzle courant sont perdus au retour d'analyse, au rechargement et au changement d'onglet (`Puzzles.tsx:17`, `:44-50`).
4. **PUZ-6, majeur.** Un coup faux ne produit aucun retour visuel sur l'échiquier : `c.undo()` est appelé avant `setFen`, donc le « flash » annoncé en commentaire n'existe pas (`PuzzlePlayer.tsx:72-80`).
5. **PUZ-4 et PUZ-5, majeurs.** En 393x660, aucun bouton d'action n'est visible sans scroller. « Passer » est gratuit et c'est le seul CTA vert pendant la résolution.

Les scripts sont dans `e2e/qa/puzzles/` et les captures dans son sous-dossier `shots/`.

---

# Constats QA - Puzzles classés et Puzzle Rush

Cible : `/#/puzzles` et `/#/rush`, serveur dev `http://localhost:5199` (build dev, React StrictMode actif).
`QA/` désigne `e2e/qa/puzzles/` et les captures sont dans `QA/shots/`.
Tous les scripts ont été lancés après la remise en service du serveur : aucun constat ne date de la panne.
Les puzzles ont été réellement résolus, au tap-tap et au drag tactile CDP, la solution étant lue dans les props React du `PuzzlePlayer` monté.

## PUZ-1 - Rush : plusieurs coups faux sur le même puzzle coûtent plusieurs vies
- type: bug
- sévérité: majeur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t06_rush_survival.py`, bloc « double erreur ».
  Lancer Survie, jouer 3 fois de suite le même coup faux avec des taps espacés de 30 ms.
- attendu: une seule vie perdue par puzzle, board verrouillé dès l'erreur, puis puzzle suivant (chess.com).
- observé: `{'score': 0, 'strikes': 3}` en moins de 200 ms sur un seul puzzle, puis écran « Terminé 0 ».
  Variante : un coup faux puis le bon coup dans la fenêtre donne `strikes: 1` et `score: 1` pour le même puzzle.
  La fenêtre dure 400 ms (300 ms pour la 3e erreur).
- capture: QA/shots/t06_triple_strike.png
- cause probable: `src/pages/PuzzleRush.tsx:82-100` : `handleComplete` n'a aucun garde par puzzle, et le puzzle suivant n'arrive qu'après `setTimeout(..., 400)`.
  `src/components/PuzzlePlayer.tsx:72-80` et `:102` : après un coup faux le board reste `interactive`, car `done` ne passe à `true` que sur succès.
- correctif proposé: dans `handleComplete`, ignorer l'appel si `resolvedRef.current === puzzle.id`, sinon y écrire `puzzle.id`.
  Ajouter une prop `lockOnFail` à `PuzzlePlayer` qui coupe `interactive` dès le premier coup faux (Rush uniquement).

## PUZ-2 - « Le bon coup était » affiche le mauvais coup
- type: bug
- sévérité: majeur
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t02_solve.py` (bloc D) et `python3 QA/t04_special.py under`.
  Puzzle `1Tkhb` (`d4d2 e7d7 d5c6 d7d2`) : jouer e7d7 (correct), attendre d5c6, jouer d7d8 (faux).
- attendu: la solution du coup raté, en notation lisible (« Txd2 »), pièce de promotion comprise.
- observé: « Le bon coup était e7→d7 », soit le coup que je venais de trouver, au lieu de d7→d2.
  Puzzle `0D1rh` (solution `g2g1n`) : en promouvant en dame, le texte dit « g2→g1 », exactement le coup joué, sans mention du cavalier.
  Le format est de l'UCI brut alors que le reste de l'app affiche du SAN en figurines.
- capture: QA/shots/t02_D_failed_step3.png, QA/shots/t04_underpromo_failed.png
- cause probable: `src/pages/Puzzles.tsx:163` et `:210-213` : `formatUci` lit toujours `puzzle.moves[1]` et tronque à 4 caractères.
- correctif proposé: utiliser `puzzle.moves[stepIndex]` (`stepIndex` vaut déjà l'index du coup attendu au moment de l'échec).
  Rejouer `moves.slice(0, stepIndex)` dans un `Chess(puzzle.fen)` pour afficher le SAN, promotion incluse.

## PUZ-3 - Série 🔥 et puzzle courant perdus au retour d'analyse, au rechargement et au changement d'onglet
- type: bug
- sévérité: majeur
- page: /#/puzzles puis /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t02_solve.py` (bloc F) et `python3 QA/t05_chain.py`.
  Résoudre un puzzle (série 1), « Analyser avec Stockfish », puis « ← Retour à l'exercice ».
- attendu: retour sur le même puzzle dans son état résolu, série intacte.
- observé: puzzle `1BUfN` avant, puzzle `48Xi9` après, série 1 -> 0.
  Après `page.reload()` avec une série de 3 : Elo 895 conservé, série 3 -> 0.
  Aller sur Accueil puis revenir donne aussi un nouveau puzzle, sans pénalité pour celui abandonné.
- capture: QA/shots/t02_F_before_analyse.png, QA/shots/t02_F_after_return.png, QA/shots/t05_after_reload.png
- cause probable: `src/pages/Puzzles.tsx:17` : `streak` est un `useState(0)` jamais persisté.
  `src/pages/Puzzles.tsx:44-50` : le montage tire toujours un nouveau puzzle et ignore `state.restore` envoyé par `src/pages/Analysis.tsx:625`.
- correctif proposé: calculer la série au montage depuis `db.puzzleAttempts` (succès consécutifs par date décroissante), sans changer le schéma.
  Avant `navigate('/analyse')`, stocker `{puzzle, phase, ratingDelta}` dans `sessionStorage` et le restaurer sur `state.restore`, comme `Learn.tsx`.

## PUZ-4 - Onglet Safari 393x660 : aucun bouton d'action visible sans scroller
- type: ux
- sévérité: majeur
- page: /#/puzzles ; viewport: 393x660
- statut: reproduit
- repro: `python3 QA/t08_visual.py`, section `tab660`.
- attendu: « Suivant » et « Indice » atteignables sans scroller (chess.com garde la barre d'action collée en bas).
- observé: `main` fait 612 px de haut pour un contenu de 721 px en cours et 797 px en résolu ou raté.
  Indice et Passer sont à y=605, Suivant et Réessayer à y=625, donc sous la nav basse dans les trois états.
  Il faut scroller après chaque puzzle.
- capture: QA/shots/t08_tab660_solving.png, QA/shots/t08_tab660_solved.png, QA/shots/t04_longlabel_660.png
- cause probable: `src/pages/Puzzles.tsx:123-205` : deux cartes empilées (103 px et 94 px) précèdent les boutons.
  `src/index.css:26-28` : `76vh` (501 px) ne tient pas compte des panneaux, le board prend donc 381 px.
- correctif proposé: sous `md`, fusionner classement, flamme et statut en un bandeau d'une ligne (56 px), avec les boutons juste sous le board.
  Reléguer « Analyser » et « Puzzle Rush » sous la ligne de flottaison.
  Budget visé : 20+381+12+56+12+52 = 533 px pour 612 disponibles.

## PUZ-5 - « Passer » est gratuit et c'est le CTA vert principal pendant la résolution
- type: ux
- sévérité: majeur
- page: /#/puzzles ; viewport: tous
- statut: reproduit
- repro: `python3 QA/t05_chain.py` : 5 taps sur « Passer ».
- attendu: sur chess.com, un puzzle classé ne s'évite pas sans perte de points, et l'action principale n'est pas de passer.
- observé: Elo 895 -> 895, tentatives en base 10 -> 10 : aucun coût, aucune trace, le puzzle peut donc revenir.
  Le seul gros bouton vert pendant la résolution est « Passer ».
  On peut ne garder que les puzzles faciles et gonfler son Elo.
- capture: QA/shots/t01_after_first_move.png
- cause probable: `src/pages/Puzzles.tsx:185-187` : `pickPuzzle(rating)` est appelé sans `score(false)` en phase `solving`.
- correctif proposé: en résolution, rendre « Passer » secondaire et lui faire appeler `score(false)` avant `pickPuzzle`.
  Réserver le vert à « Suivant ».

## PUZ-6 - Coup faux : aucun retour visuel sur l'échiquier (Puzzles et Rush)
- type: ux
- sévérité: majeur
- page: /#/puzzles et /#/rush ; viewport: tous
- statut: reproduit
- repro: `python3 QA/t02_solve.py` (bloc C), capture 60 ms après le coup faux.
- attendu: chess.com joue le coup, marque la case en rouge avec une pastille ✗, puis revient en arrière.
- observé: 60 ms après le coup faux, le placement est déjà celui d'avant : la pièce revient sans rien montrer.
  Le seul signal est le panneau « ✗ Raté » sous le board.
  En Rush, le seul signal est une croix grise qui rougit avant le changement de puzzle.
  Le son `Error.mp3` est bien joué (`QA/t09_sounds.py`).
- capture: QA/shots/t02_C_wrong_t60ms.png, QA/shots/t06_survie_after_wrong_150ms.png
- cause probable: `src/components/PuzzlePlayer.tsx:72-80` : `c.undo()` est appelé avant `setFen(c.fen())`.
  Le commentaire « Flash du mauvais coup » ne correspond donc à aucun comportement.
- correctif proposé: afficher la position après le coup faux avec `markSquares` rouge et `badge` `blunder` (props déjà supportées, `src/components/Board.tsx:25-27`).
  Faire `undo` après 600 ms, board verrouillé pendant ce délai.

## PUZ-7 - Surlignage de la case d'arrivée perdu quand on reprend au tap la pièce qui vient de jouer
- type: bug
- sévérité: mineur
- page: /#/puzzles et /#/rush (Board partagé) ; viewport: tous
- statut: reproduit
- repro: `python3 QA/t04_special.py recapture` (puzzle `12ejQ`, amorce f6e5, solution f3e5).
- attendu: cases de départ et d'arrivée en jaune quel que soit le geste.
- observé: au tap-tap, seule `f3` est jaune, et React logue l'erreur « Removing background backgroundColor ... conflicting property ».
  Au drag, `e5` et `f3` sont jaunes, sans erreur.
  13,9 % des puzzles (16 640 sur 120 000) commencent par une reprise sur la case d'arrivée de l'amorce.
  C'est la seule erreur console de la campagne.
- capture: QA/shots/t04_recapture_tap.png, QA/shots/t04_recapture_drag.png, QA/shots/t02_A_solved.png
- cause probable: `src/components/Board.tsx:115-122` : le raccourci `background` de la pastille est fusionné avec le `backgroundColor` du dernier coup.
  Au rendu suivant, React retire `background`, ce qui efface aussi `background-color`.
- correctif proposé: n'utiliser que des propriétés longues (`backgroundImage` pour les pastilles, `backgroundColor` pour les teintes).

## PUZ-8 - « ✓ Trouvé ! Continue… » ne dure que 340 ms et fait sauter les boutons de 36 px
- type: ux
- sévérité: mineur
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t03_feedback_hint.py`, sonde toutes les 25 ms.
- attendu: encouragement lisible jusqu'au coup suivant, sans déplacer les contrôles.
- observé: message visible de 0,015 s à 0,331 s, le bouton Indice passe de y=605 à y=641 puis revient.
  Un tap sur « Indice » à ce moment a manqué sa cible dans mon script.
- capture: QA/shots/t03_trouve_flash.png
- cause probable: `src/pages/Puzzles.tsx:117` repasse `midFeedback` à `false` dès la réponse adverse, jouée 350 ms plus tard (`PuzzlePlayer.tsx:94`).
  `src/pages/Puzzles.tsx:145-147` : le message est une ligne ajoutée au-dessus du texte.
- correctif proposé: ne remettre `midFeedback` à `false` qu'au prochain coup du joueur.
  Afficher le message à la place de « Trouve le meilleur coup. ».

## PUZ-9 - Saut de 20 px des CTA entre états
- type: ux
- sévérité: cosmétique
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t02_solve.py` (mesures `boxes`) et `python3 QA/t04_special.py label`.
- attendu: « Suivant » toujours au même endroit.
- observé: Suivant est à y=605 en résolu et à y=625 en raté.
  Avec le puzzle `0wsXe` (libellé de thèmes de 67 caractères), il est aussi à y=625 en résolu.
- capture: QA/shots/t02_C_failed.png, QA/shots/t04_longlabel_852.png
- cause probable: `src/pages/Puzzles.tsx:157` et `:163` : la hauteur de la carte est dictée par le texte.
- correctif proposé: `min-h` de deux lignes, ou texte d'échec court (« Solution : Df2# ») et thèmes en `truncate`.

## PUZ-10 - Rush : chrono compté en ticks, en pause quand l'app est suspendue
- type: bug
- sévérité: mineur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t07_rush_timed.py` : `page.clock.fast_forward(60_000)` en plein rush 3 min.
- attendu: chrono basé sur l'heure réelle.
- observé: horloge 2:54 -> 2:53 après 60 s sautées.
  En PWA iOS, changer d'app suspend le JS : le chrono s'arrête et on réfléchit gratuitement.
  Sous charge, 180 ticks durent plus de 180 s.
- capture: QA/shots/t07_3min_running.png
- cause probable: `src/pages/PuzzleRush.tsx:47-60` : `setInterval` de 1000 ms qui décrémente `timeLeft`.
- correctif proposé: mémoriser `endAtRef = Date.now() + MODE_MS[m]` dans `start()`.
  Rafraîchir toutes les 250 ms avec `Math.max(0, endAt - Date.now())`, et recalculer sur `visibilitychange`.

## PUZ-11 - Rush : égaler son record affiche « 🏆 Nouveau record ! »
- type: bug
- sévérité: mineur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t06_rush_survival.py` : deux runs Survie à 6, puis un run à 2.
- attendu: « Nouveau record » seulement si le score est strictement supérieur.
- observé: run 1 (6) : « Nouveau record ! ».
  Run 2 (6) : « Nouveau record ! ».
  Run 3 (2) : « Terminé ».
- capture: QA/shots/t06_done_run2_tie.png
- cause probable: `src/pages/PuzzleRush.tsx:136` teste `score >= best[mode]`, alors que `best` est rechargé à chaque changement de `state` (`:38-45`) et peut déjà contenir le run courant.
- correctif proposé: figer `prevBestRef.current = best[m]` dans `start()` et tester `score > prevBestRef.current`.

## PUZ-12 - Rush : quitter par la nav basse perd le run sans confirmation ni sauvegarde
- type: ux
- sévérité: mineur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t06_rush_survival.py`, dernier bloc : score 1 en cours, tap « Accueil », retour arrière.
- attendu: confirmation, ou au minimum enregistrement du score.
- observé: retour sur le menu du Rush, `rushScores` inchangé (8 lignes avant, 8 après), aucune alerte.
- capture: QA/shots/t06_menu_records.png
- cause probable: `src/pages/PuzzleRush.tsx` : tout l'état vit dans des `useState`, sans nettoyage au démontage ni bloqueur de navigation.
- correctif proposé: un cleanup d'effet qui enregistre le score si `stateRef.current === 'running'`.
  Mieux : masquer la nav basse pendant un run.

## PUZ-13 - Rush : bouton « ✕ » de 36 px, sans confirmation, identique aux croix de vies
- type: ux
- sévérité: mineur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t07_rush_timed.py` : mesure du bouton puis tap.
- attendu: cible d'au moins 44 px, action destructive confirmée, icône distincte.
- observé: le bouton fait 36 x 64 px, collé à « ✗✗✗ », avec un glyphe quasi identique : il ressemble à une 4e vie.
  Un tap termine le run (« Terminé 0 »).
- capture: QA/shots/t07_3min_red.png
- cause probable: `src/pages/PuzzleRush.tsx:173-176`.
- correctif proposé: `min-w-11`, icône 🏳 ou libellé « Stop », confirmation en deux taps, bouton sorti du bandeau des vies.

## PUZ-14 - Rush : scores écrits en double (effet de bord dans un updater d'état)
- type: bug
- sévérité: mineur
- page: /#/rush ; viewport: tous
- statut: reproduit en dev (StrictMode), déduit du code pour la prod
- repro: `python3 QA/t06_rush_survival.py` : un run terminé par 3 erreurs, puis lecture d'IndexedDB.
- attendu: une ligne `rushScores` par run.
- observé: deux lignes par run terminé sur 3 erreurs (`id 1` et `id 2`, à 1 ms d'écart).
  Une seule ligne quand le run finit au chrono (`QA/t07_rush_timed.py`).
  En production, StrictMode ne double pas les updaters, mais React ne garantit pas qu'un updater n'est appelé qu'une fois.
- capture: aucune (sortie console)
- cause probable: `src/pages/PuzzleRush.tsx:74-80` : `db.rushScores.add` est exécuté dans l'updater de `setState`.
  `:90-98` : `setTimeout(finish, 300)` est lancé dans l'updater de `setStrikes`.
  `:50-56` : `finish()` est appelé dans l'updater de `setTimeLeft`.
- correctif proposé: utiliser `stateRef` et `strikesRef`, faire les effets de bord hors des updaters, avec le garde `if (stateRef.current !== 'running') return`.

## PUZ-15 - Sélecteur de promotion impossible à annuler, en glyphes Unicode
- type: ux
- sévérité: mineur
- page: /#/puzzles et /#/rush (Board partagé) ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t04_special.py promo` (puzzle `012tD`) : tap c2 puis d1, tap dans un coin du board, puis Escape.
- attendu: un tap hors du sélecteur annule, avec les pièces du jeu, sur la colonne de promotion.
- observé: le sélecteur reste après un tap hors boutons et après Escape.
  Un pion lâché par erreur sur la dernière rangée force donc une promotion, et un échec de puzzle classé.
  Les pièces sont des glyphes de texte gris clair pour les deux camps, centrés au milieu du board.
  Le reste fonctionne : dame au tap et au drag, sous-promotion exigée, mat alternatif par promotion en tour.
- capture: QA/shots/t04_promo_dialog.png
- cause probable: `src/components/Board.tsx:160-178` (overlay sans `onClick`) et `:183-186` (`PROMO_GLYPHS`).
- correctif proposé: `onClick={() => setPendingPromotion(null)}` sur l'overlay et `stopPropagation` sur la boîte.
  Utiliser les SVG des pièces, placés sur la case d'arrivée.

## PUZ-16 - Indice : non progressif, sans pénalité, confondu avec le dernier coup
- type: ux
- sévérité: mineur
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t03_feedback_hint.py`, bloc 3.
- attendu: chess.com : premier indice = pièce à jouer dans une couleur dédiée, second = coup montré, et plus de gain d'Elo.
- observé: le 1er, le 2e et le 3e tap donnent le même résultat : seule la case de départ (`d3`) est teintée.
  La teinte est le jaune du dernier coup et remplace son surlignage.
  Puzzle résolu avec un indice à chaque coup : 832 -> 852 (+20), série incrémentée.
  Pendant les 500 ms avant l'amorce, le bouton est actif mais sans effet.
- capture: QA/shots/t03_hint1.png, QA/shots/t03_hint_solved.png
- cause probable: `src/pages/Puzzles.tsx:169-176` (un seul niveau, aucun lien avec `score`) et `src/components/PuzzlePlayer.tsx:105` (l'indice réutilise `lastMove`).
- correctif proposé: passer l'indice par `markSquares` (bleu) en conservant `lastMove`.
  Au second tap, tracer une flèche via `arrows`.
  Ajouter `hintUsed`, qui plafonne le gain à 0.
  Désactiver le bouton tant que `stepIndex === 0`.

## PUZ-17 - Après un échec, la solution est dévoilée en même temps que « Réessayer », et le board reste jouable
- type: ux
- sévérité: mineur
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t02_solve.py`, bloc C.
- attendu: chess.com propose « Réessayer » ou « Solution », et la solution n'apparaît que sur demande.
- observé: « Le bon coup était h4→f2. Tu peux réessayer sans enjeu. » s'affiche aussitôt : réessayer perd son intérêt.
  Sans toucher « Réessayer », le bon coup joué sur le board fait passer le panneau de « ✗ Raté » à « ✓ Résolu ! », avec « 815 -17 » toujours affiché en rouge.
  L'Elo n'est débité qu'une fois, même avec 3 coups faux en rafale (`QA/t10_double_score.py`).
- capture: QA/shots/t02_C_failed.png, QA/shots/t02_C_play_after_fail.png
- cause probable: `src/pages/Puzzles.tsx:160-165` et `src/components/PuzzlePlayer.tsx:102`.
- correctif proposé: en état raté, proposer « Réessayer », « Voir la solution » (rejouée sur le board) et « Suivant ».
  Afficher « Résolu au 2e essai » après un second essai réussi.

## PUZ-18 - PWA réelle (encoche 59 px, barre d'accueil 34 px) : scroll parasite de 10 px et « Analyser » coupé par la nav
- type: ux
- sévérité: mineur
- page: /#/puzzles ; viewport: 393x852 avec safe-areas injectées par CSS
- statut: reproduit en simulation
- repro: `python3 QA/t08_visual.py`, section `safe852`.
- attendu: écran de résolution sans scroll, boutons entiers.
- observé: `main` fait 770 px de haut.
  Le contenu fait 780 px en cours (scroll parasite de 10 px, « Puzzle Rush » rogné de 2 px), 836 px en résolu et 856 px en raté.
  « Suivant » et « Réessayer » restent visibles (bas à y=736).
  « Analyser » est coupé en deux par la nav, et « Puzzle Rush » est hors écran.
  Le Rush tient sans scroll dans tous ses états.
- capture: QA/shots/t08_safe852_solving.png, QA/shots/t08_safe852_failed.png
- cause probable: le même empilement que PUZ-4, ajouté à `pt-safe` (`src/App.tsx:47`, `src/index.css:36-38`).
- correctif proposé: le bandeau compact de PUZ-4 règle aussi ce cas.
  À défaut, retirer « Puzzle Rush » de cet écran (il est déjà sur l'accueil) pour gagner 56 px.

## PUZ-19 - Un échiquier détaché reste en mémoire pour chaque puzzle touché
- type: perf
- sévérité: mineur
- page: /#/puzzles ; viewport: 393x852
- statut: reproduit (build dev)
- repro: `python3 QA/t05c_leak_solve.py tap`, `QA/t05d_leak_bisect.py`, `QA/t05e_leak_nohandle.py`.
  La mesure est faite en CDP après `HeapProfiler.collectGarbage`.
- attendu: nombre de noeuds DOM et de listeners stable d'un puzzle à l'autre.
- observé: sur 20 puzzles résolus, noeuds 570 -> 9 691, listeners 279 -> 1 968, heap 65,6 -> 69,3 Mo, pour un DOM vivant autour de 500 noeuds.
  Soit environ 440 noeuds et 85 listeners retenus par puzzle, inchangés après 4 s de repos.
  Il suffit de sélectionner une pièce (tap ou clic souris) avant de changer de puzzle.
  60 « Passer » sans toucher le board ne montrent aucune croissance (626 -> 624 noeuds).
  Ce n'est pas un artefact de handle Playwright : le scénario `no_touch_but_handle` donne +8 noeuds par puzzle.
  La latence « Suivant » est stable à 133 ms, et il n'y a aucune répétition sur 10 tirages.
- capture: aucune (mesures console)
- cause probable: `src/pages/Puzzles.tsx:110` et `src/pages/PuzzleRush.tsx:152` : la `key` remonte un `<Chessboard>` complet à chaque puzzle (react-chessboard 5.10.0, @dnd-kit/core 6.3.1).
  Le détenteur exact de la référence n'est pas identifié.
- correctif proposé: retirer la `key` et réinitialiser `PuzzlePlayer` par un effet sur `[puzzle.id, attempt]`.
  Revérifier sur un build de prod.

## PUZ-20 - Analyse ouverte depuis un puzzle : « Retour à l'exercice » et « M1 (adv.) » pour le mat du joueur
- type: ux
- sévérité: cosmétique
- page: /#/analyse depuis /#/puzzles ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t02_solve.py`, bloc F (puzzle `1BUfN`, joueur Noirs).
- attendu: « ← Retour au puzzle » et une évaluation lisible du point de vue du joueur.
- observé: l'ouverture est correcte : position clé après l'amorce, orientation Noirs, solution navigable, flèche du meilleur coup, bouton retour.
  Le libellé dit « Retour à l'exercice ».
  Le moteur affiche « (M1 (adv.)) Ng3# » alors que c'est le joueur qui mate.
  Les lignes du moteur sont en SAN anglais, à côté d'une liste de coups en figurines.
- capture: QA/shots/t02_F_analyse.png
- cause probable: `src/pages/Analysis.tsx:628` (libellé fixe) et `:435` (`m < 0` signifie mat pour les Noirs, pas pour l'adversaire).
- correctif proposé: passer `returnLabel` dans le state de navigation (`src/pages/Puzzles.tsx:94-103`).
  Remplacer « (adv.) » par le camp (« M1 pour les Noirs »).

## PUZ-21 - Thèmes affichés en identifiants anglais bruts
- type: ux
- sévérité: mineur
- page: /#/puzzles ; viewport: tous
- statut: reproduit
- repro: résoudre n'importe quel puzzle et lire la carte de statut.
- attendu: libellés français, comme pour les ouvertures.
- observé: « endgame, mate, mateIn2 », « discoveredAttack, discoveredCheck, doubleBishopMate, kingsideAttack ».
  La base contient 73 thèmes distincts.
- capture: QA/shots/t02_A_solved.png, QA/shots/t04_longlabel_852.png
- cause probable: `src/pages/Puzzles.tsx:79-82` : les thèmes sont joints tels quels.
- correctif proposé: un dictionnaire `src/lib/puzzleThemes.ts` sur le modèle d'`openingNames.ts`.
  Afficher 2 thèmes en pastilles.

## PUZ-22 - Rush : écarts fonctionnels avec chess.com
- type: ux
- sévérité: mineur
- page: /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t06_rush_survival.py` et `python3 QA/t07_rush_timed.py`.
- attendu: référence chess.com Puzzle Rush.
- observé: par priorité.
  1. Aucune indication du trait : avant l'amorce, seule l'orientation renseigne le camp.
  2. Pas de pastilles de progression : un compteur et trois croix, là où chess.com empile une tuile verte ou rouge par puzzle, avec son Elo.
  3. L'écran de fin est vide aux trois quarts : ni liste des puzzles, ni revue des ratés, ni Elo max, ni lien vers l'analyse.
  4. Le chrono démarre au tap sur le mode (3:00, puis 2:59 à 1,06 s), avant l'amorce et sans décompte.
  5. Le passage en rouge sous 30 s est correct, mais `sounds.lowTime` n'est jamais appelé.
  6. 480 px restent vides sous le bandeau.
- capture: QA/shots/t06_survie_running.png, QA/shots/t06_done_run1.png, QA/shots/t07_3min_red.png
- cause probable: `src/pages/PuzzleRush.tsx:133-147` et `:149-178`.
- correctif proposé: tenir un `history: {id, rating, ok}[]`, affiché en pastilles pendant le run et en grille cliquable vers `/analyse` à la fin.
  Ajouter un bandeau « Trait aux… », un décompte 3-2-1 et le son `lowTime` à 10 s.

## PUZ-23 - État de chargement minimal
- type: ux
- sévérité: cosmétique
- page: /#/puzzles et /#/rush ; viewport: 393x852
- statut: reproduit
- repro: `python3 QA/t01_load.py` et la fin de `python3 QA/t05_chain.py` (CPU bridé).
- attendu: squelette de page, et libellé de chargement sur le menu du Rush.
- observé: un texte gris « Chargement… » en haut à gauche d'un écran vide.
  À froid : 0,5 à 0,95 s en local, 1,33 s à CPU x4, 2,17 s à CPU x6.
  Heap après chargement : 65,5 Mo.
  Sur `/rush`, les boutons sont grisés sans explication.
- capture: QA/shots/t01_loading.png
- cause probable: `src/pages/Puzzles.tsx:84` et `src/pages/PuzzleRush.tsx:119-120`.
- correctif proposé: un `Board` vide et des cartes en `animate-pulse`.
  Sur `/rush`, afficher « Chargement des puzzles… » sous le titre.

## PUZ-24 - Rush : chrono non centré, rayons hétérogènes, « 1 puzzles résolus »
- type: ux
- sévérité: cosmétique
- page: /#/rush et /#/puzzles ; viewport: 393x852 et 1440x900
- statut: reproduit
- repro: `python3 QA/t07_rush_timed.py`, puis lire la capture.
- attendu: tuiles alignées, un seul rayon par famille de composants, accords corrects.
- observé: « 0:29 » est collé en haut de sa tuile de 64 px, alors que le score et les croix sont centrés.
  Le bouton « ✕ », « Indice » et « Réessayer » sont en `rounded` (4 px), à côté de cartes `rounded-lg` et d'un CTA `rounded-xl`.
  On lit « 1 puzzles résolus » et « 1 résolus ».
- capture: QA/shots/t07_3min_red.png, QA/shots/t08_desk_rush_done.png, QA/shots/t01_after_first_move.png
- cause probable: `src/pages/PuzzleRush.tsx:156`, `:173`, `:138`, `:162`, et `src/pages/Puzzles.tsx:172`, `:180`.
- correctif proposé: ajouter `flex items-center justify-center` sur la tuile du chrono.
  Passer ces boutons par `Cta variant="secondary"`.
  Accorder le pluriel selon le score.

## PUZ-25 - Paysage 852x393 : trait sombre de 1 px au milieu de l'échiquier
- type: ux
- sévérité: cosmétique
- page: /#/puzzles et /#/rush ; viewport: 852x393
- statut: reproduit
- repro: `python3 QA/t08_visual.py`, section `land`.
- attendu: cases jointives.
- observé: une ligne sombre de 1 px CSS (y=606-608 en pixels physiques) entre les rangées 5 et 4, sur une case sur deux.
  Elle est absente en portrait (381 px) et en desktop (640 px).
  Le reste du paysage est propre : nav latérale, tous les boutons visibles, aucun débordement.
- capture: QA/shots/t08_land_line_zoom.png, QA/shots/t08_land_failed.png
- cause probable: `src/index.css:26-28` : la largeur est fractionnaire (`76vh` = 298,68 px, soit 37,335 px par case), d'où des écarts d'arrondi.
  381 px et 640 px sont des entiers et n'ont pas de trait.
- correctif proposé: `width: round(down, min(100vw - 0.75rem, 76vh, 640px), 8px);`, avec la règle actuelle en repli.

## PUZ-26 - Coordonnées masquées par les pièces
- type: ux
- sévérité: cosmétique
- page: toutes les pages avec board ; viewport: 393x852
- statut: reproduit
- repro: toute capture avec une pièce sur la première rangée ou la colonne de gauche.
- attendu: lettres et chiffres lisibles dans le coin de la case.
- observé: « b » est sous le socle du roi, « c » sous la tour, et le « 4 » disparaît sous une dame.
- capture: QA/shots/t01_after_first_move.png, QA/shots/t02_C_failed.png
- cause probable: les styles de notation par défaut de react-chessboard ne sont pas surchargés (`src/components/Board.tsx:132-150`).
- correctif proposé: surcharger les styles de notation (10 px, collés au coin), à vérifier dans l'API de la v5.

## Couverture

Testé et conforme :
- Chargement des 120 000 puzzles : état « Chargement… » visible, jamais d'écran blanc, puzzle prêt en moins de 1 s.
- Puzzle adapté à l'Elo : 10 tirages entre -101 et +67 points d'écart, aucune répétition.
- Trait annoncé exact, board orienté côté joueur (Blancs et Noirs), amorce jouée à 500 ms avec surlignage.
- Solutions multi-coups au tap-tap et au drag tactile, réponse adverse automatique, puzzle de 12 demi-coups avec promotion finale résolu en 5,4 s.
- Mat alternatif accepté (`b3g8` au lieu de `f8g8`, tour au lieu de dame), sous-promotion exigée respectée.
- Elo cohérent : +14 à +25 en réussite, -14 à -26 en échec, un seul débit par puzzle, réessai sans effet sur l'Elo.
- Persistance de l'Elo et des tentatives après rechargement, accueil à jour.
- Sons Capture, Move, Error et Confirmation joués aux bons moments.
- Rush : les 3 modes démarrent, pas de chrono en Survie, 3 erreurs terminent le run, difficulté croissante (439, 491, 646, 665, 723, 802), chrono jusqu'à 0 sans valeur négative, record enregistré et affiché, Rejouer et Menu.
- Aucun débordement horizontal, board jamais sous la nav basse, desktop 1440x900 propre.
- Console : aucune `pageerror`, une seule erreur (PUZ-7).

## Hypothèses non vérifiées

- PUZ-19 : le détenteur de l'échiquier détaché n'est pas identifié (capteurs dnd-kit ou rétention propre au build dev de React 19).
  Je n'ai pas mesuré sur un build de prod, faute de pouvoir lancer un second serveur.
- PUZ-14 : le doublon n'a été observé qu'en dev avec StrictMode, son absence en prod est déduite.
- PUZ-18 : les safe-areas (59 et 34 px) sont injectées par CSS, pas mesurées sur un iPhone.
- PUZ-10 : la suspension iOS est simulée par `page.clock.fast_forward`.
- En paysage sur un iPhone réel, la nav latérale n'a pas de `padding-left: env(safe-area-inset-left)` (`src/App.tsx:26`) et passerait sous l'encoche.
- Le premier son (amorce, sans geste utilisateur) est probablement muet sur iOS tant que l'`AudioContext` est suspendu (`src/lib/sounds.ts:34-36`).
- Geste tactile : un tap sur « Indice » a manqué sa cible à cause du saut de layout de PUZ-8.
  Je n'ai pas creusé le scroll pendant un drag, couvert par un autre agent.
