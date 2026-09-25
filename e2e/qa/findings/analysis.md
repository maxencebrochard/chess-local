Le fichier `findings-analysis.md` n'a pas été écrit : l'outil Write refuse les fichiers de rapport `.md` pour un sous-agent. Je n'ai pas contourné le blocage, donc le contenu complet est ci-dessous, prêt à être enregistré tel quel dans `e2e/qa/findings-analysis.md`.

## Résumé

38 constats : 2 critiques, 12 majeurs, 22 mineurs, 2 cosmétiques. Tous ont été observés après la remise en route du serveur (seule de la lecture de code avait eu lieu avant la panne).

1. ANA-1 (critique) : un PGN collé avec header `[FEN]` donne un écran blanc ; il faut tuer la PWA. Cause : `Analysis.tsx:187` force `START_FEN`, et il n'y a aucun error boundary.
2. ANA-2 / ANA-3 (critique / majeur) : un bilan en cours n'est jamais invalidé. Jouer un coup pendant le calcul puis taper le graphe donne un écran blanc ; réimporter une partie plaque l'ancien bilan sur la nouvelle (`Analysis.tsx:238-262`).
3. ANA-9 (majeur) : les fautes de l'adversaire vont dans « Mes erreurs », avec le libellé « Partie analysée ». Cause : `runReview` garde en closure la couleur et le libellé du premier rendu (`Analysis.tsx:122,139,344`).
4. ANA-5 (majeur) : un nom d'ouverture long décale l'échiquier de 14 px vers la gauche en 393x852 (x = -8, colonne a rognée). Cause : `Analysis.tsx:622,643`.
5. ANA-11 (majeur) : la classe « Brillant » ne peut jamais sortir (`review.ts:161-163`). Le sacrifice de dame du mat de Legal sort « Meilleur ».

`popeye232` charge 30 parties en 1,3 s. Le plantage de `e2e/test_all_buttons.py` ligne 255 est donc un artefact de la panne du serveur dev, pas un bug de l'Import.

---

# Findings QA - Analyse, Archive, Import chess.com

- Scripts : `e2e/qa/analysis/`, abrégé `A/` ci-dessous.
- Captures : `A/shots/`.
- Viewport par défaut : iPhone 14 Pro émulé, PWA standalone 393x852, tactile.
- Profondeur de bilan `fast` partout, sauf ANA-2, ANA-3 et ANA-7 où `deep` a servi à garder le bilan ouvert assez longtemps pour interagir.

## ANA-1 - Un PGN avec header FEN fait planter toute l'app (écran blanc)
- type: bug
- sévérité: critique
- page: /#/analyse ; viewport: 393x852 (tous)
- statut: reproduit (2 fois)
- repro: `A/t2_import.py`. Options > Importer PGN ou FEN, coller un PGN avec `[SetUp "1"]` et `[FEN "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"]` suivi de `3... Nf6 4. Ng5 d5`, puis Charger.
- attendu: la partie se charge depuis la position custom (chess.com et lichess le font), ou au pire un message d'erreur.
- observé: `pageerror: Invalid move: Nf6`. React démonte tout l'arbre et `body` est vide. Naviguer vers `/#/` par le hash ne restaure rien : il faut recharger la page, donc tuer la PWA sur iPhone.
- capture: A/shots/t2_02_pgn_fen.png
- cause probable: `src/pages/Analysis.tsx:187` : `loadPgn` force `setStartFen(START_FEN)` alors que `c.history()` vient d'une position custom. Le `useMemo` de `viewFen` (`Analysis.tsx:60-64`) rejoue alors `Nf6` depuis la position initiale et lève. Aucun error boundary dans `src/App.tsx:47-59`.
- correctif proposé: dans `loadPgn`, `setStartFen(c.header().FEN ?? START_FEN)` (`reviewGame` gère déjà `customStart`, `src/lib/review.ts:99`). Ajouter un error boundary autour de `<Routes>` avec un bouton « Recharger ».

## ANA-2 - Jouer un coup pendant un bilan en cours, puis taper le graphe : écran blanc
- type: bug
- sévérité: critique
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 A/t4_concurrency.py variation`. Charger 230 demi-coups, lancer Bilan, pendant le calcul taper le 10e coup de la bande puis jouer a2-a3, attendre le résumé, taper le graphe à 90 % de sa largeur.
- attendu: le bilan est annulé ou ignoré dès que la ligne change, jamais appliqué à une autre liste de coups.
- observé: la partie est tronquée à 11 coups, mais le bilan des 230 coups d'origine s'affiche quand même. Le tap sur le graphe donne `pageerror: Cannot read properties of undefined (reading 'san')` et un écran blanc.
- capture: A/shots/t4_variation_summary.png, A/shots/t4_variation_after_graph_tap.png
- cause probable: `Analysis.tsx:238-262` : `runReview` fait `setReview(result)` sans vérifier que `moves` est toujours la partie analysée, et rien n'annule `reviewGame`. Le board reste interactif pendant le bilan (`Analysis.tsx:635`). `EvalGraph.tsx:31` renvoie un index jusqu'à 229, puis `viewFen` lit `moves[i].san` hors bornes (`Analysis.tsx:62`).
- correctif proposé: donner un jeton à chaque bilan (`reviewRunId` en ref, incrémenté par `loadPgn`, `loadFen`, `handleMove` et au démontage) et ignorer le résultat si le jeton a changé. Passer un `AbortSignal` à `reviewGame` pour sortir de la boucle `review.ts:104`. Rendre le board non interactif tant que `reviewProgress !== null`, et borner `viewIndex` dans `viewFen`.

## ANA-3 - Importer une autre partie pendant un bilan : l'ancien bilan est plaqué sur la nouvelle partie
- type: bug
- sévérité: majeur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 A/t4_concurrency.py reimport`. Lancer le bilan de la longue partie, puis Options > Importer la partie courte `1. e4 e5 2. Nf3 ...`.
- attendu: le bilan en cours est annulé, et le bouton Bilan redevient disponible pour la nouvelle partie.
- observé: le bouton Bilan reste grisé 100 s. Le résumé affiche ensuite 26,6 / 26,7 (précisions de l'ancienne partie) sur la partie de 14 coups. En revue guidée, la bulle dit « c4 est un coup théorique » alors que le coup affiché est e4.
- capture: A/shots/t4_reimport_summary.png, A/shots/t4_reimport_guided.png
- cause probable: même cause que ANA-2 (`Analysis.tsx:238-262`, aucune invalidation du bilan en vol).
- correctif proposé: même jeton d'annulation que ANA-2.

## ANA-4 - Un seul coup exploratoire après le bilan détruit la suite de la partie et tout le bilan
- type: ux
- sévérité: majeur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t9_variation_after_review.py`. Faire le bilan de la partie de référence, fermer le résumé, aller sur 4.Nxe5, jouer ...d6 au board.
- attendu: chess.com crée une variante, garde la ligne principale et le bilan, et propose de revenir à la partie.
- observé: la bande passe de 14 à 8 coups, le graphe et la carte de précision disparaissent. Aucune confirmation, aucun retour possible. Même comportement en analyse libre (`A/t1_free.py` : 3.Bb5 perdu après ...Nf6 joué au coup 2).
- capture: A/shots/t9_after_exploratory_move.png, A/shots/t1_03_variation.png
- cause probable: `Analysis.tsx:229-231` : `setMoves([...kept, move])` tronque la ligne, puis `setReview(null)`.
- correctif proposé: conserver la ligne principale dans un état séparé (`mainline`) et jouer les coups exploratoires dans une `variation` affichée au-dessus de la bande, avec un bouton « Revenir à la partie ». Ne jamais jeter `review` tant que la ligne principale existe.

## ANA-5 - Un nom d'ouverture long décale l'échiquier hors de l'écran
- type: bug
- sévérité: majeur
- page: /#/analyse ; viewport: 393x852 et 393x660
- statut: reproduit
- repro: `A/t7b_landscape.py` (première partie). Importer `1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7`.
- attendu: bandeau tronqué avec ellipse, board centré (x = 6 px).
- observé: le bandeau fait 409 px de large et le board se retrouve à x = -8 px. La colonne a est rognée, les numéros de rangées sont coupés, une marge vide apparaît à droite. `main.scrollWidth` vaut 401 pour 393 de large, donc la page devient scrollable horizontalement. Le cas est très fréquent : la plupart des parties chess.com ont un nom d'ouverture de cette longueur.
- capture: A/shots/t7b_standalone_long_opening.png, A/shots/t7_safari_01_opening.png
- cause probable: `Analysis.tsx:622` : la colonne `flex flex-col` n'a pas de largeur et prend le `max-content` du bandeau `truncate` (`Analysis.tsx:643`). `justify-center` la recentre ensuite en débordant.
- correctif proposé: mettre la classe `boardbox` sur la colonne (`Analysis.tsx:622`) et `w-full` sur le conteneur du board, ou `w-0 min-w-full` sur le bandeau.

## ANA-6 - Liste de l'archive cassée sur mobile : lignes de 190 à 256 px, texte écrasé sur 90 px
- type: bug
- sévérité: majeur
- page: /#/archive ; viewport: 393x852
- statut: reproduit
- repro: `A/t5_archive.py` (jouer 3 parties courtes, ouvrir l'archive).
- attendu: une ligne compacte par partie (chess.com : environ 64 px, 8 à 10 parties par écran).
- observé: lignes de 192 à 256 px, 3 parties par écran. Le bloc d'infos est comprimé à environ 90 px et se replie sur 5 à 7 lignes. Le résultat « 0-1 » des parties locales se coupe en « 0- / 1 ». Le ✕ part seul sur une deuxième ligne, en bas à gauche.
- capture: A/shots/t5_01_list.png
- cause probable:
  - `src/pages/Archive.tsx:54-56` : `flex-wrap` avec un bloc d'infos `flex-1` (base 0) qui rétrécit au lieu de forcer le retour à la ligne des boutons ;
  - `Archive.tsx:55` : `w-6` trop étroit pour « 0-1 » ;
  - `Archive.tsx:37` : `p-6` fixe, soit 48 px perdus en largeur.
- correctif proposé: sur mobile, ligne 1 = résultat + infos (`min-w-0 basis-full` ou grille `grid-cols-[2rem_1fr]`), ligne 2 = actions alignées à droite dans un seul conteneur. `p-3 md:p-6`, `w-8`, et « 1-0 » en `text-sm` pour les parties locales.

## ANA-7 - Bilan sur mobile : aucune progression affichée, aucune annulation
- type: ux
- sévérité: majeur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 A/t4_concurrency.py progress` (230 demi-coups, profondeur `deep`, 90 s).
- attendu: chess.com affiche une barre de progression avec pourcentage et permet de quitter.
- observé: pendant 90 s, l'écran montre seulement « Calcul… », une barre d'éval figée à « 0,00 » et le bouton Bilan grisé. Il n'y a ni pourcentage ni bouton Annuler ; le pourcentage n'existe que dans le bouton desktop.
- capture: A/shots/t4_progress_3s.png
- cause probable: `Analysis.tsx:803` affiche `Analyse… {reviewProgress}%` dans un bloc `hidden md:flex`. La barre mobile (`Analysis.tsx:847-852`) n'a que `disabled`.
- correctif proposé: overlay plein écran pendant le bilan (coach + barre de progression + « Annuler ») branché sur `reviewProgress`, avec l'annulation de ANA-2.

## ANA-8 - Import chess.com : « Actualiser » ne fait rien si le pseudo n'a pas changé, blocage après une erreur réseau
- type: bug
- sévérité: majeur
- page: /#/import ; viewport: 393x852
- statut: reproduit
- repro: `A/t6_chesscom.py` et `A/t6b_chesscom_errors.py`. Charger `hikaru`, taper Actualiser : 0 requête. Passer hors ligne (`ctx.set_offline(True)`), Actualiser avec `magnuscarlsen` : message d'erreur. Revenir en ligne et retaper Actualiser.
- attendu: chaque tap relance le chargement.
- observé: 0 requête réseau, le message « Pas de connexion » reste affiché, liste vide. Seule issue : modifier le pseudo ou quitter la page.
- capture: A/shots/t6b_03_back_online.png
- cause probable: `src/pages/Import.tsx:106` ne fait que `setChesscomUsername(...)`. Le chargement dépend de l'effet `Import.tsx:61-63`, qui ne se relance pas quand la valeur est identique.
- correctif proposé: dans le `onClick`, appeler `setChesscomUsername(v)` puis `void loadGames(v)` directement, et garder l'effet pour le seul montage. Ajouter un bouton « Réessayer » dans le bandeau d'erreur.

## ANA-9 - Les fautes de l'adversaire sont enregistrées dans « Mes erreurs », avec un libellé générique
- type: bug
- sévérité: majeur
- page: /#/analyse (depuis /#/import et /#/archive) ; viewport: tous
- statut: reproduit
- repro: `A/t6_chesscom.py` : bilan d'une partie où hikaru a les blancs, puis lecture de la table Dexie `mistakes`. `A/t5b_archive_black.py` pour le libellé depuis l'archive.
- attendu: seules les fautes de la couleur revue sont stockées, avec le libellé de la partie.
- observé: entrée `{trait: 'b', san: 'b5', cls: 'mistake', label: 'Partie analysée'}`. C'est une faute de l'adversaire (noirs), et le libellé « chess.com · Hikaru vs Snorlax » est perdu.
- capture: sortie console du script (pas de capture utile)
- cause probable: `Analysis.tsx:122` et `Analysis.tsx:139` appellent, via `setTimeout`, le `runReview` du premier rendu. Sa closure voit `reviewColor = null` et `gameMeta = null` (`Analysis.tsx:344` et `350`). Les dépendances du `useCallback` (`Analysis.tsx:262`) ne listent ni l'un ni l'autre.
- correctif proposé: passer la couleur et le libellé en arguments (`runReview(pgn, { color, label })`, puis `recordMistakes(result, color, label)`), ou les lire dans des refs.

## ANA-10 - « Moteur : désactivé » n'arrête pas Stockfish
- type: perf
- sévérité: majeur
- page: /#/analyse ; viewport: tous
- statut: reproduit
- repro: `A/t1b_engine_mate.py` et `A/t1c_uci_proof.py` avec `?debug-uci`. Jouer e4, Options > Moteur, Fermer, puis relever la barre d'éval toutes les 700 ms.
- attendu: commande UCI `stop`, barre d'éval figée ou neutre, CPU au repos (batterie iPhone).
- observé: moteur « désactivé », la barre d'éval continue de bouger (+0,34, +0,35, +0,41 en 4 s). Le journal UCI est bien actif (32 messages avant la coupure, dernier `go infinite`) et ne contient aucun `stop` ensuite, même après un nouveau coup. La recherche infinie continue donc sur l'ancienne position. Même défaut en revue guidée quand on coupe « Afficher ».
- capture: A/shots/t1b_engine_off_bar.png
- cause probable: `Analysis.tsx:151-155` : la branche « coupé » fait `setLines([])` puis `return` sans `engine.stop()`, et `engine.onLines` reste branché sur `setLines`. Déduit du code : après un coup joué moteur coupé, `evalCp` (`Analysis.tsx:283-285`) applique le signe du nouveau trait à l'éval de l'ancienne position, donc la barre s'inverse.
- correctif proposé: dans cette branche, `engineRef.current?.stop()` et `engine.onLines = null` avant `setLines([])`.

## ANA-11 - La classe « Brillant » ne peut jamais être attribuée
- type: bug
- sévérité: majeur
- page: /#/analyse (bilan) ; viewport: tous
- statut: reproduit
- repro: `A/t8_coach.py` : bilan du mat de Legal `1. e4 e5 2. Nf3 d6 3. Bc4 Bg4 4. Nc3 g6 5. Nxe5 Bxd1 6. Bxf7+ Ke7 7. Nd5#`.
- attendu: 5.Nxe5 (sacrifice de dame, meilleur coup) est « Brillant » sur chess.com.
- observé: 5.Nxe5 classé « Meilleur », compteur Brillant à 0 / 0.
- capture: A/shots/t8_01_legal_nxe5.png
- cause probable: `src/lib/review.ts:161-163` compare le matériel du joueur avant et juste après son propre coup. Un coup ne fait jamais perdre de matériel à celui qui le joue, donc `balBefore - balAfter2 >= 2` est toujours faux.
- correctif proposé: mesurer le sacrifice après la meilleure réponse adverse. Jouer `evals[i + 1].lines[0].pv[0]` sur `replayAfter`, puis comparer le bilan matériel à `balBefore` (seuil 2), en gardant les autres conditions.

## ANA-12 - Résumé du bilan : les pseudos longs se chevauchent et deviennent illisibles
- type: bug
- sévérité: majeur
- page: /#/analyse (résumé) ; viewport: 393x852, 393x660, 1440x900
- statut: reproduit
- repro: `A/t7_visual.py safari` : PGN avec `[White "MagnusCarlsenTheGreatestOfAllTime"]` et `[Black "xX_LongPseudoDeLaMortQuiTue_Xx"]`. Des pseudos réels de la liste hikaru dépassent déjà la colonne (« Chessable-teacherr », « OhanyanEminChess »).
- attendu: pseudo tronqué avec ellipse, comme chess.com.
- observé: les deux noms se superposent au-dessus des cartes de précision.
- capture: A/shots/t7_safari_05_summary.png, A/shots/t7_desktop_05_summary.png
- cause probable: `src/components/ReviewSummary.tsx:48-49` : `w-24 text-center` sans `truncate`.
- correctif proposé: ajouter `truncate` et `title={whiteName}`, plus une pastille blanche ou noire devant le nom pour rappeler la couleur.

## ANA-13 - Revue guidée sur petit écran : la 1re rangée passe sous la barre d'actions, et le board saute de 22 px en mode Réessayer
- type: bug
- sévérité: majeur
- page: /#/analyse (guidé) ; viewport: 393x660 (équivalent iPhone SE en standalone) ; le saut du board se produit aussi en 393x852
- statut: reproduit
- repro: `python3 A/t7_visual.py safari` : bilan, Démarrer, avancer jusqu'à 5.Nxf7, Réessayer.
- attendu: board entièrement visible et immobile, surtout quand on doit jouer un coup (chess.com garde le board fixe et fait varier la bulle).
- observé: en guidé, le bas du board est à 583 px, exactement au bord de la barre d'actions, et la bande de coups passe sous le pli (zone scrollable 534 pour 491 visibles). En Réessayer, la bulle passe de 94 à 116 px et le board descend de 202 à 224 px. La rangée 1 passe alors à moitié sous la barre : impossible de jouer O-O sans scroller.
- capture: A/shots/t7_safari_06_guided.png, A/shots/t7_safari_07_retry.png, A/shots/t3b_08_retry_found.png
- cause probable: `Analysis.tsx:506-573` : bulle, board et bande sont dans la même zone scrollable. La bulle de retry (`Analysis.tsx:509-531`) est plus haute que le `min-h-[42px]` de `src/components/CoachBubble.tsx:35`.
- correctif proposé: réserver une hauteur fixe à la bulle (par exemple `h-[120px] overflow-y-auto`), et dimensionner le board guidé avec `min(100vw - 0.75rem, 100dvh - hauteur des zones fixes)`.

## ANA-14 - Paysage 852x393 : layout desktop appliqué au téléphone, contrôles rognés, revue guidée inutilisable
- type: bug
- sévérité: majeur
- page: /#/analyse ; viewport: 852x393
- statut: reproduit
- repro: `A/t7b_landscape.py` (seconde partie).
- attendu: layout paysage à deux colonnes (board à gauche, panneau à droite), ou orientation verrouillée.
- observé: le breakpoint `md` (768) s'active. La nav latérale prend 176 px, le board 299 px, et le panneau de 384 px dépasse (bord droit à 856 px). « Copier PGN » et ⇅ sont rognés, « Bilan de partie » est écrasé sur 39 px de large (3 lignes). En revue guidée, seules 2,5 rangées du board sont visibles (board de 202 à 501 px, barre d'actions à 316 px).
- capture: A/shots/t7_landscape_00_start.png, A/shots/t7b_landscape_guided.png
- cause probable: `src/App.tsx:26` et `Analysis.tsx:599,665` basculent sur la largeur seule. La vue guidée (`Analysis.tsx:490-506`) est une colonne unique.
- correctif proposé: conditionner le layout desktop à `md` et à une hauteur minimale (`@media (min-width: 768px) and (min-height: 500px)`), et prévoir une variante `landscape:flex-row` pour la vue guidée.

## ANA-15 - « Moment clé » s'arrête sur presque tous les coups
- type: ux
- sévérité: mineur
- page: /#/analyse (après bilan, vue non guidée) ; viewport: 393x852
- statut: reproduit
- repro: `A/t3b_guided.py` : depuis 4.Nxe5, « Moment clé → » mène à 4...Qg5 (« Meilleur »).
- attendu: chess.com ne retient que gaffes, erreurs, occasions manquées, brillants et très bons coups.
- observé: tout coup `best` ou `excellent` est un moment clé.
- capture: A/shots/t3b_04_blunder_nonguided_scrolled.png
- cause probable: `Analysis.tsx:321-324` inclut `severity === 'praise'`, et `src/lib/coach.ts:103-110` donne `praise` à `best` et `excellent`.
- correctif proposé: filtrer sur la classe (`blunder`, `missedWin`, `miss`, `mistake`, `brilliant`, `great`) plutôt que sur la sévérité.

## ANA-16 - Textes du coach : faute d'accord, « 1e coup », SAN anglais brut, mat en 1 non signalé
- type: bug
- sévérité: mineur
- page: /#/analyse (bilan) ; viewport: tous
- statut: reproduit (`A/t8_coach.py`, dont un appel direct à `coachComments` et `coachSummary` servis par Vite, et `A/t3_review.py`)
- repro: voir scripts.
- attendu: français correct, figurines partout, le mat forcé comme information principale.
- observé:
  - « La dame peut maintenant être capturé. » (faute d'accord).
  - « La partie a basculé au 1e coup : f3. » (« 1er » attendu).
  - Résumé réel : « La partie a basculé au 5e coup : Nxf7. » en SAN anglais, alors que tout le reste est en figurines.
  - 7.Be2, qui autorise le mat en 1, est classé « Erreur » avec « Le cavalier peut maintenant être capturé. Il fallait jouer ♕e2. », sans un mot sur le mat.
  - 5...Bxd1 (prise de la dame) : « Ça abandonne le fou. ».
- capture: A/shots/t8_00_coach_summary_card.png, A/shots/t3_05_guided_13.png
- cause probable:
  - `coach.ts:123` : participe invariable ;
  - `coach.ts:313-314` : `${moveNo}e` et `.san` sans `figurine()` ;
  - `coach.ts:121-126` : pas de test `missedMate` dans la branche `mistake` ;
  - `coach.ts:49-72` : `hungPiece` ignore le matériel que le coup vient de gagner ;
  - `review.ts:176-180` : seuils en points de win% seuls, donc une position déjà perdue ne peut plus produire de gaffe.
- correctif proposé: table genre par pièce (`capturé` ou `capturée`), `moveNo === 1 ? '1er' : moveNo + 'e'`, et `figurine(san, color)` dans le résumé. Tester `missedMate` en premier dans `mistake` et `inaccuracy`, et classer en gaffe tout coup qui laisse un mat forcé quand il n'y en avait pas. Dans `hungPiece`, soustraire la valeur de la pièce capturée par le coup joué.

## ANA-17 - Notation et langue incohérentes : SAN anglais dans les lignes moteur et l'explorer, noms d'ouvertures en anglais ou à moitié traduits
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: tous
- statut: reproduit
- repro: `A/t1_free.py`.
- attendu: figurines partout (la bande de coups et le coach les utilisent), ouvertures en français.
- observé: lignes moteur « Nf6 O-O Nxe4 », explorer « Nxe5 / Petrov's Defense: Modern Attack », libellé desktop « Nxf7 : Gaffe ». Le bandeau est à moitié traduit : « Partie italienne · Blackburne-Kostić Gambit », « Partie espagnole · Closed, Breyer Defense, Zaitsev Hybrid », « Partie anglaise · Great Snake Variation ».
- capture: A/shots/t1_08_explorer.png, A/shots/t3b_10_lines.png, A/shots/t7_desktop_07_review_panel.png
- cause probable:
  - `Analysis.tsx:418-429` : `sanLine` sans `figurine` ;
  - `Analysis.tsx:835-836` : SAN brut et `b.openings[0].name` sans `openingFr` ;
  - `Analysis.tsx:658` : libellé desktop ;
  - couverture partielle de `src/lib/openingNames.ts`.
- correctif proposé: appliquer `figurine()` en alternant la couleur à partir du trait dans `sanLine` et dans l'explorer, et `openingFr()` dans l'explorer. Traduire aussi les suffixes génériques (`Gambit`, `Variation`, `Defense`, `Attack`, `Closed`, `Open`).

## ANA-18 - « Charger » avec un champ vide efface la partie en cours sans prévenir
- type: bug
- sévérité: mineur
- page: /#/analyse (modale Import) ; viewport: 393x852
- statut: reproduit
- repro: `A/t2_import.py` : jouer e4 e5, Options > Importer, laisser vide (ou des espaces), Charger.
- attendu: bouton désactivé, ou message « Colle un PGN ou une FEN ».
- observé: la modale se ferme et la partie est remise à zéro (0 coup), sans erreur.
- capture: aucune (état identique à la position de départ)
- cause probable: `Analysis.tsx:893-897` : `loadPgn('')` réussit avec chess.js (partie vide).
- correctif proposé: `disabled={!importText.trim()}` sur le bouton, et refuser un PGN sans coup ni header FEN.

## ANA-19 - Export : le PGN copié perd tous les en-têtes et le résultat, pas d'export FEN, aucun retour visuel
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t2_import.py` : importer un PGN avec `White "Alice"`, `Black "Bob"`, `Result "1-0"`, puis Options > Copier le PGN.
- attendu: en-têtes et résultat conservés, action « Copier la FEN » (présente sur chess.com), toast « Copié ».
- observé: le presse-papiers contient `[White "?"] [Black "?"] [Result "*"] ... 4. Ba4 Nf6 *`. Il n'y a aucune action FEN, et la feuille se ferme sans confirmation (`A/t9_variation_after_review.py`).
- capture: A/shots/t9_after_copy.png
- cause probable: `Analysis.tsx:264-273` reconstruit un `Chess` neuf sans reporter les headers, et `Analysis.tsx:869-872` n'affiche rien après `writeText`.
- correctif proposé: mémoriser `c.header()` dans `loadPgn` et le réinjecter dans `currentPgn`. Ajouter un `SheetBtn « Copier la FEN »` (`viewFen`) et un toast de 1,5 s.

## ANA-20 - Réessayer : le bon coup trouvé n'apparaît pas sur l'échiquier
- type: ux
- sévérité: mineur
- page: /#/analyse (guidé, Réessayer) ; viewport: 393x852
- statut: reproduit
- repro: `A/t3b_guided.py` : sur 5.Nxf7, Réessayer, jouer Bxf7+ en drag.
- attendu: chess.com laisse le coup joué sur le board, surligné en vert.
- observé: la bulle dit « Trouvé ! », mais le fou revient en c4 et f7 porte toujours le pion noir. Avec « Solution » déjà affichée, la bulle répète « ♗xf7+ était exactement le coup. La solution était ♗xf7+. ».
- capture: A/shots/t3b_08_retry_found.png
- cause probable: `Analysis.tsx:542` : `fen={retry ? retry.baseFen : viewFen}` quel que soit `retry.status`. `Analysis.tsx:514` ajoute la phrase solution même en `found`.
- correctif proposé: stocker `fenAfterTry` dans `RetryState`, l'afficher en `checking` et `found` avec un `markSquares` vert, et masquer la phrase solution quand `status === 'found'`.

## ANA-21 - Couper le moteur fait remonter l'échiquier de 44 px
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t1_free.py` : Options > Moteur.
- attendu: board immobile (le commentaire du code le promet pour l'arrivée des lignes).
- observé: le y du board passe de 98 px à 54 px.
- capture: A/shots/t1_06_engine_off.png
- cause probable: `Analysis.tsx:604-612` : le bloc de hauteur fixe `h-[38px]` est lui-même conditionné par `engineOn`.
- correctif proposé: toujours rendre le bloc, et y afficher « Moteur désactivé » quand `!engineOn`.

## ANA-22 - Import chess.com : pseudo invalide mémorisé, Entrée inactive, clavier iOS non configuré, bouton actif pendant le chargement
- type: ux
- sévérité: mineur
- page: /#/import ; viewport: 393x852
- statut: reproduit
- repro: `A/t6_chesscom.py`, `A/t6b_chesscom_errors.py`.
- attendu: la touche « Aller » du clavier lance la recherche, il n'y a ni majuscule ni correction automatique, et un pseudo n'est mémorisé que s'il existe.
- observé:
  - Entrée : 0 requête.
  - Attributs `autocapitalize`, `autocorrect`, `spellcheck`, `enterkeyhint` absents.
  - `zz_qa_nobody_98765` (404) est écrit dans `localStorage`, le champ « lien de partie » s'affiche et le bouton devient « Actualiser ».
  - Le bouton reste cliquable pendant « Chargement… ».
- capture: A/shots/t6b_00_unknown_user.png, A/shots/t6_01_loading.png
- cause probable: `Import.tsx:98-112` : pas de `<form onSubmit>`, pas d'attributs sur l'input, `setChesscomUsername` appelé avant validation.
- correctif proposé: envelopper dans un `<form>`, ajouter `autoCapitalize="none" autoCorrect="off" spellCheck={false} enterKeyHint="go"`, ne persister le pseudo qu'après un `fetchRecentGames` réussi, et mettre `disabled={loading}`.

## ANA-23 - Liste chess.com : un pseudo long masque le classement et la couleur, cadence en anglais
- type: ux
- sévérité: mineur
- page: /#/import ; viewport: 393x852
- statut: reproduit
- repro: `A/t6_chesscom.py` (hikaru).
- attendu: couleur toujours visible, cadence en français, comme chess.com.
- observé:
  - « vs Chessable-teacherr (283… » : classement tronqué, « Blancs / Noirs » disparu.
  - Cadence brute : « blitz », « rapid », « daily ».
  - Placeholder du lien coupé : « …ou colle un lien de partie (Partager → Cc ».
  - Ni le nombre de coups ni le motif de fin ne sont affichés.
  - Aucun onglet de la nav basse n'est actif sur cette page, et il n'y a pas de bouton retour.
- capture: A/shots/t6_02_list.png
- cause probable:
  - `Import.tsx:149-154` : nom, classement et couleur dans un seul `truncate` ;
  - `Import.tsx:157` : `g.timeClass` brut ;
  - `Import.tsx:119` : placeholder trop long.
- correctif proposé: pastille de couleur (blanche ou noire) à gauche du nom, `truncate` sur le nom seul, classement en `shrink-0`. Table `bullet | blitz | rapid → rapide | daily → différé`, et placeholder « Lien de partie chess.com ».

## ANA-24 - Archive : suppression immédiate, sans confirmation ni annulation
- type: ux
- sévérité: mineur
- page: /#/archive ; viewport: 393x852
- statut: reproduit
- repro: `A/t5_archive.py` : taper ✕ (6 lignes puis 5, aucun dialogue).
- attendu: confirmation, ou toast « Partie supprimée - Annuler ».
- observé: suppression définitive dans Dexie au premier tap, sur une cible de 28x36 px. Les ratings associés ne sont pas recalculés.
- capture: A/shots/t5_05_after_delete.png
- cause probable: `Archive.tsx:24-27` et `Archive.tsx:77`.
- correctif proposé: suppression différée de 5 s avec toast « Annuler », cible de 44 px, `aria-label="Supprimer la partie"`.

## ANA-25 - Quitter l'onglet Analyse perd la partie chargée et le bilan
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `python3 A/t4_concurrency.py leave` : charger 230 coups, lancer le bilan, taper Archive puis Analyse.
- attendu: l'analyse en cours est restaurée (chess.com garde l'onglet).
- observé: 0 coup, position de départ, bilan perdu. Aucune erreur console ; le moteur redémarre proprement (lignes correctes après e4).
- capture: A/shots/t4_leave_back.png
- cause probable: tout l'état vit dans des `useState` de `Analysis.tsx:37-57`, démontés à chaque changement de route.
- correctif proposé: persister `{pgn, startFen, viewIndex, orientation, review}` dans `sessionStorage` (même modèle que `Learn.tsx`), et restaurer au montage quand `location.state` et `?game` sont absents.

## ANA-26 - Numérotation fausse depuis une FEN où les noirs ont le trait
- type: bug
- sévérité: mineur
- page: /#/analyse ; viewport: tous
- statut: reproduit
- repro: `A/t2_import.py` : FEN `... b KQkq - 3 3`, jouer ...Nf6.
- attendu: « 3... ♞f6 » (le PGN exporté dit bien `3. ... Nf6`).
- observé: la bande affiche « 1. ♞f6 », et le bandeau indique « Position de départ » pour une position custom.
- capture: A/shots/t2_03_fen_black_first.png
- cause probable:
  - `src/components/MoveStrip.tsx:35` numérote `i / 2 + 1` sans tenir compte de `startTurn` ni du numéro de coup de la FEN ;
  - `src/components/MoveList.tsx:19-21,35` : même défaut, plus la couleur des figurines ;
  - `Analysis.tsx:644` : « Position de départ » dès que `moves.length === 0`.
- correctif proposé: passer `startMoveNumber` et `startTurn` aux deux composants, et afficher « Position personnalisée » quand `startFen !== START_FEN`.

## ANA-27 - Mobile : pas d'aller au début ni à la fin, chevrons minuscules
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t1_free.py`, `A/t2_import.py` (partie de 230 coups).
- attendu: chess.com propose l'appui long sur ‹ et › pour aller au début et à la fin.
- observé: seuls Précédent et Suivant existent, donc 230 taps pour revenir au début (ou scroller la bande). Les glyphes ‹ et › font environ 8 px, contre environ 24 px pour ⚙ et ★.
- capture: A/shots/t1_01_ruy.png
- cause probable: `Analysis.tsx:845-856` : ⏮ et ⏭ n'existent que dans le bloc desktop (`Analysis.tsx:789-795`).
- correctif proposé: appui long sur Précédent et Suivant (début et fin), et icônes SVG de 24 px à la place des caractères.

## ANA-28 - Deux bilans de la même partie donnent des résultats différents
- type: bug
- sévérité: mineur
- page: /#/analyse ; viewport: tous
- statut: reproduit
- repro: `A/t3_review.py` puis `A/t3b_guided.py` sur la même partie de référence, profondeur `fast`.
- attendu: résultat stable (chess.com est déterministe pour une partie donnée).
- observé: précisions 54,0 / 96,6 puis 51,1 / 90,9. L'Elo noir estimé vaut 2550, puis 1950, puis 2250. 4.Nxe5 sort « Bon » puis « Imprécision ».
- capture: A/shots/t3_02_summary.png, A/shots/t3b_04_blunder_nonguided_scrolled.png
- cause probable: `review.ts:109` enchaîne des `engine.search` sur un moteur dont la table de hachage contient encore l'analyse infinie précédente. L'Elo repose sur l'ACPL de 4 coups hors théorie (`review.ts:267-268`).
- correctif proposé: envoyer `ucinewgame` puis `isready` avant un bilan (nouvelle méthode `Engine.newGame()` sous `exclusive()`), et masquer le « Classement de la partie » sous 10 coups hors théorie par camp.

## ANA-29 - Vue post-bilan non guidée : le commentaire du coach et « Réessayer » sont sous le pli
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t3b_guided.py` (fermer le résumé, taper 5.Nxf7).
- attendu: chess.com place la bulle du coach au-dessus du board, toujours visible.
- observé: la page fait 1041 px pour 804 visibles, dans cet ordre : board, bandeau, graphe, bande, carte précision, carte coach. Lire le commentaire de chaque coup impose de scroller, ce qui sort le board de l'écran. L'avatar change aussi (🧑‍🏫 ici, visages ronds en guidé).
- capture: A/shots/t3b_03_blunder_nonguided.png, A/shots/t3b_04_blunder_nonguided_scrolled.png
- cause probable: ordre des blocs dans `Analysis.tsx:710-787`.
- correctif proposé: sur mobile, placer la carte coach avant la carte précision, replier cette dernière dans un `<details>` « Statistiques », et réutiliser `CoachBubble`.

## ANA-30 - Modale « Importer PGN ou FEN » : bord à bord, centrée, sans bouton de fermeture
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852, 393x660
- statut: reproduit (géométrie)
- repro: `A/t2_import.py`.
- attendu: feuille basse cohérente avec « Options », marges, boutons « Coller » et « Annuler ».
- observé: bbox x = 0, largeur 393 (coins arrondis collés aux bords), centrée verticalement (y de 277 à 575). La fermeture ne se fait que par tap extérieur. La modale est en `z-30` alors qu'Options est en `z-40`.
- capture: A/shots/t2_00_modal.png
- cause probable: `Analysis.tsx:882-883` : `w-[520px]` sans `max-w` ni marge, `items-center`.
- correctif proposé: `w-full max-w-[520px] mx-3`, `items-end md:items-center` avec `rounded-t-2xl` sur mobile, et boutons « Coller » (`navigator.clipboard.readText`) et « Annuler ».

## ANA-31 - `?game=<id>` inconnu : aucun message, l'URL garde ses paramètres
- type: ux
- sévérité: mineur
- page: /#/analyse?game=99999&review=1 ; viewport: 393x852
- statut: reproduit
- repro: `A/t8_coach.py`.
- attendu: message « Partie introuvable (supprimée ?) » et URL nettoyée.
- observé: position de départ muette, hash inchangé.
- capture: aucune
- cause probable: `Analysis.tsx:133-134` : `if (!saved) return` avant `setParams({})`.
- correctif proposé: afficher un bandeau d'erreur et appeler `setParams({}, { replace: true })` dans tous les cas.

## ANA-32 - Le sélecteur de promotion ne peut pas être annulé
- type: ux
- sévérité: mineur
- page: /#/analyse ; viewport: 393x852
- statut: reproduit
- repro: `A/t8_coach.py` : FEN `8/P6k/8/8/8/8/8/K7 w - - 0 1`, a7-a8, taper hors du sélecteur.
- attendu: chess.com annule la promotion au tap extérieur (ou avec ✕).
- observé: le sélecteur reste affiché, il faut choisir une pièce. La sous-promotion en cavalier fonctionne (`wN` en a8).
- capture: A/shots/t8_02_promo.png
- cause probable: `src/components/Board.tsx:160-178` : l'overlay n'a pas de `onClick`.
- correctif proposé: `onClick={() => setPendingPromotion(null)}` sur l'overlay et `stopPropagation` sur le conteneur des 4 boutons.

## ANA-33 - Desktop : pas de navigation au clavier
- type: a11y
- sévérité: mineur
- page: /#/analyse ; viewport: 1440x900
- statut: reproduit
- repro: `python3 A/t7_visual.py desktop` : ArrowLeft, le coup courant reste ♘xf7.
- attendu: ← et → pour précédent et suivant, ↑ et ↓ pour début et fin, `f` pour retourner (chess.com, lichess).
- observé: aucune touche gérée.
- capture: A/shots/t7_desktop_07_review_panel.png
- cause probable: aucun listener `keydown` dans `Analysis.tsx`.
- correctif proposé: `useEffect` avec un listener `keydown` sur `window`, ignoré si la cible est un `input` ou un `textarea`, actif aussi en vue guidée.

## ANA-34 - Boutons à glyphe seul sans nom accessible, graphe d'éval inaccessible au clavier
- type: a11y
- sévérité: mineur
- page: /#/analyse, /#/archive ; viewport: tous
- statut: déduit du code
- repro: lecture du code.
- attendu: `aria-label` sur chaque bouton icône, et un rôle sur le graphe.
- observé: « ← » (`Analysis.tsx:492-497`), « ✕ » (`ReviewSummary.tsx:33-35`, `Archive.tsx:77`), l'interrupteur moteur (`Analysis.tsx:670-675`) et ⏮ ◀ ▶ ⏭ n'ont ni `aria-label` ni `title`. `EvalGraph.tsx:37-43` est un `<svg>` cliquable sans `role` ni `tabIndex`.
- capture: aucune
- cause probable: voir lignes citées.
- correctif proposé: `aria-label` (« Retour au résumé », « Fermer le bilan », « Supprimer la partie »), `role="switch" aria-checked` sur l'interrupteur, `role="slider"` avec `aria-valuenow` et gestion des flèches sur le graphe.

## ANA-35 - En dev (StrictMode), chaque partie terminée est archivée deux fois et le classement est appliqué deux fois
- type: bug
- sévérité: mineur
- page: /#/jouer puis /#/archive ; viewport: tous (localhost uniquement)
- statut: reproduit en dev, NON reproduit en prod
- repro: `A/t5b_archive_black.py` : 1 partie jouée donne 2 lignes sur localhost:5199, et 1 ligne sur `https://maxencebrochard.github.io/chess-local`.
- attendu: 1 enregistrement.
- observé: doublons stricts (même date, même PGN), classement 800 puis 764 après une seule défaite. Cela fausse les suites E2E qui comptent les lignes de l'archive ou lisent le classement.
- capture: A/shots/t5_01_list.png
- cause probable: `src/pages/Play.tsx:190-227` : effets de bord (`db.games.add`, `applyRating`) dans la fonction passée à `setStatus`, que StrictMode (`src/main.tsx:13`) invoque deux fois.
- correctif proposé: sortir le bloc async du updater. Tester un `statusRef.current !== 'playing'`, passer le statut à `over`, puis exécuter la sauvegarde une seule fois.

## ANA-36 - Cosmétique : séparateur décimal, vocabulaire, libellés d'éval, tirets cadratins, bulle vide
- type: ux
- sévérité: cosmétique
- page: /#/analyse, /#/import ; viewport: tous
- statut: reproduit
- repro: `A/t3_review.py`, `A/t1b_engine_mate.py`, `A/t5b_archive_black.py`.
- attendu: format français cohérent.
- observé:
  - Précisions « 54.0 » et « 54.9 % » avec un point, alors que les évals utilisent la virgule (« +0,34 »).
  - « Milieu de jeu » dans le tableau, « milieu de partie » dans la bulle juste au-dessus.
  - Mat pour les noirs affiché « (M1 (adv.)) » : parenthèses imbriquées, et « adv. » n'a pas de sens en analyse libre (chess.com : « -M1 »).
  - Barre d'éval à « 0,00 » pendant « Calcul… » et pendant tout un bilan, alors que l'éval est inconnue.
  - En revue d'une partie contre un bot, la bulle des coups adverses est vide (« ♘c3 » seul, 42 px de blanc).
  - La pastille du dernier coup est à moitié hors du graphe, et d'autres pastilles dépassent en haut.
  - Des tirets cadratins figurent dans des textes UI (quip du coach, résumé, messages d'erreur d'import).
  - L'éval est affichée deux fois en guidé (barre et badge de la bulle).
- capture: A/shots/t3_02_summary.png, A/shots/t1b_black_m1.png, A/shots/t4_progress_3s.png, A/shots/t5b_guided_opponent_move.png
- cause probable:
  - `ReviewSummary.tsx:51-52`, `Analysis.tsx:714,719`, `coach.ts:275-278` : pas de `replace('.', ',')` ;
  - `ReviewSummary.tsx:81` : « Milieu de jeu » ;
  - `Analysis.tsx:435` : « (adv.) » ;
  - `src/components/HEvalBar.tsx:12` : label par défaut « 0,00 » ;
  - `coach.ts:85` et `Analysis.tsx:533-535` : bulle vide ;
  - `EvalGraph.tsx:40` : `overflow-visible` ;
  - `coach.ts:177,275,286`, `Import.tsx:41,72`, `src/lib/chesscom.ts:22,29` : tirets cadratins.
- correctif proposé: helper `fr(n, digits)` unique pour tous les nombres, « Milieu de partie », `-M1` ou `+M1`, label « … » quand `cp === null`. Ajouter un commentaire neutre pour les coups adverses (« Noa joue ♘c3, coup théorique. »), clamper les pastilles à `r` du bord, et utiliser des tirets simples.

## ANA-37 - Trois lignes moteur calculées, deux affichées sur mobile
- type: perf
- sévérité: cosmétique
- page: /#/analyse ; viewport: 393x852
- statut: reproduit (affichage) et déduit du code (coût)
- repro: `A/t1_free.py` : 2 lignes visibles sur mobile, 3 sur desktop (`A/shots/t7_desktop_07_review_panel.png`).
- attendu: MultiPV égal au nombre de lignes affichées.
- observé: `startInfinite(viewFen, 3)` quel que soit le layout.
- capture: A/shots/t1_01_ruy.png
- cause probable: `Analysis.tsx:166` contre `Analysis.tsx:596,606`.
- correctif proposé: `multipv = isMobile ? 2 : 3` via `matchMedia('(min-width: 768px)')`, ou afficher 3 lignes sur mobile comme chess.com.

## ANA-38 - Aucun moyen de choisir la couleur revue pour un PGN collé
- type: ux
- sévérité: mineur
- page: /#/analyse (résumé et revue) ; viewport: tous
- statut: reproduit (absence d'UI) et déduit du code (conséquences)
- repro: `A/t3_review.py` : coller un PGN, Bilan. Aucun contrôle de couleur n'existe dans le résumé, la revue guidée ou Options.
- attendu: chess.com demande quel camp on jouait, ou permet de basculer ; le coach parle alors du bon camp.
- observé: `reviewColor` reste `null`. La punchline et l'humeur du coach se calent sur les blancs (« Le milieu de partie a dérapé… » décrit les 54 % des blancs, même si l'utilisateur avait les noirs). Les deux camps sont commentés, et les fautes des deux camps partent dans « Mes erreurs ».
- capture: A/shots/t3_02_summary.png
- cause probable: `Analysis.tsx:44` n'est alimenté que par `state.color` (`Analysis.tsx:118-121`) et l'archive (`Analysis.tsx:138`). Les valeurs par défaut `playerColor ?? 'w'` sont dans `coach.ts:165,267` et `ReviewSummary.tsx:28`. Le filtre `Analysis.tsx:344` est inopérant quand la couleur est `null`.
- correctif proposé: rendre les deux en-têtes de colonne du résumé tappables (Blancs / Noirs / Les deux). Le tap règle `reviewColor` et l'orientation, et `coach` se recalcule déjà sur `[review, reviewColor]`. N'écrire dans `mistakes` qu'une fois la couleur connue.

## Couverture

Testé et conforme :

- **Analyse libre**
  - Coups en tap-tap et en drag tactile CDP.
  - 2 lignes moteur sur mobile et 3 sur desktop, flèche bleue du meilleur coup.
  - Nom d'ouverture en français pour les ouvertures principales (« Partie espagnole », « Défense Petrov »).
- **Barre d'éval**
  - Signe correct au trait noir et avec le board retourné.
  - Mat pour les blancs (`M1`, 100 %), mat pour les noirs (`M1`, 0 %), `M3` et `M8` depuis une FEN au trait noir.
  - `#` et « Partie terminée. » sur mat.
  - `EvalBar` verticale desktop correcte dans les deux orientations.
- **Explorer d'ouvertures**
  - Il s'ouvre, et taper un coup le joue.
  - Rejouer le coup suivant de la ligne existante avance sans tronquer.
- **Import PGN / FEN**
  - Commentaires, variantes et NAG ignorés proprement.
  - PGN invalide et coup illégal : message clair.
  - 230 demi-coups chargés, coup courant visible (auto-scroll de la bande).
  - FEN valide et FEN à 4 champs acceptées ; FEN invalide et FEN sans rois refusées.
  - PGN exporté depuis une FEN : `SetUp`, `FEN` et `3. ... Nf6` corrects.
- **Bilan sur la partie de référence**
  - Somme des classes = 7 et 7 (115 et 115 sur 230 demi-coups), 6 coups « Théorique ».
  - 5.Nxf7 « Gaffe », 7...Nf3# « Meilleur ».
  - Graphe cliquable synchronisé : tap à 0 %, 64 % et 100 % donne e4, Nxf7, Nf3#.
  - Flèche verte « Meilleur », lignes « Afficher ».
  - Réessayer : mauvais coup refusé, bon coup accepté, Solution, Quitter, sortie par ← propre.
  - Aucune chaîne `undefined`, `NaN` ou `null`.
- **Concurrence**
  - Relancer un bilan pendant qu'un autre tourne est impossible depuis l'UI : le bouton Bilan est `disabled`, sur mobile comme sur desktop.
  - Naviguer avec Précédent pendant un bilan, ou quitter la page puis revenir : aucune erreur console, moteur fonctionnel au retour.
- **Archive**
  - État vide, ordre antichronologique, date en français, adversaire, couleur, cadence, résultat G/P.
  - « Analyser » et « Bilan » chargent la bonne partie, avec l'orientation noire et les noms « Noa » et « Moi ».
  - Export global PGN complet et valide, suppression effective.
- **Import chess.com**
  - ` Hikaru ` (espaces et majuscule) et `Magnus Carlsen` sont nettoyés ; liste de 30 parties en 1,2 s.
  - Tap sur une partie : bilan avec les bons noms et la bonne orientation.
  - Un lien collé `https://www.chess.com/game/live/...` ouvre le bilan.
  - Pseudo inexistant : « Joueur introuvable sur chess.com. ». Hors ligne : message dédié. Champ vide ou espaces : bouton désactivé.
  - `popeye232` : 30 parties chargées en 1,3 s (archives 200, puis 2026/09 200). Le plantage de `e2e/test_all_buttons.py` ligne 255 est donc un artefact de la panne du serveur dev, pas un bug de l'Import.
- **Feuilles et layout**
  - Feuille Options : fermeture au tap extérieur, fond non scrollé, boutons atteignables en 393x660.
  - Board jamais masqué par la nav basse en analyse libre (393x852 et 393x660).
  - `overflow_x = 0` partout, sauf ANA-5.
  - Desktop 1440x900 : layout propre, liste de coups lisible, coup courant surligné.
- **Console** : aucune erreur hors ANA-1 et ANA-2, plus les 404 et `ERR_INTERNET_DISCONNECTED` attendus.
- **Gestes tactiles** (domaine d'un autre agent) : une seule remarque croisée, le retour arrière depuis le résumé du bilan renvoie à `/#/import`, car les écrans du bilan ne sont pas dans l'historique.

## Hypothèses non vérifiées

- Clavier iOS : la modale d'import est centrée dans un `fixed inset-0`, donc le bouton « Charger » (y environ 515 à 555) serait sous le clavier en PWA standalone. Non vérifiable en émulation Chromium.
- `env(safe-area-inset-*)` vaut 0 en émulation. L'espacement sous la Dynamic Island et au-dessus de la barre d'accueil, pour les écrans plein écran du bilan (`fixed inset-0 pt-safe pb-safe`), n'a pas pu être contrôlé.
- `review.ts:106` utilise `chess.isGameOver()`, qui inclut la triple répétition et la règle des 50 coups. Sur un PGN OTB qui continue après une répétition, les positions suivantes seraient traitées comme terminées et le coup qui répète classé en gaffe. Non testé : ma longue partie générée évite les répétitions.
- Le bilan abandonné au démontage (`engine.quit()` pendant `reviewGame`) laisse une promesse jamais résolue. Aucune erreur observée ; la fuite mémoire est probable mais non mesurée.
- `navigator.clipboard.writeText` est appelé dans le handler de tap, donc devrait passer sur iOS. Le cas d'un refus n'est pas géré (`void`), et rien n'a été testé sur appareil réel.
- ANA-35 n'a été contrôlé en production que sur le nombre de lignes de l'archive, pas sur le delta de classement.
- L'inversion de signe de la barre d'éval après un coup joué moteur coupé (ANA-10) est déduite du code, non mesurée.
