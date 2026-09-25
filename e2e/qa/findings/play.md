# Constats QA - page JOUER (`/#/jouer`)

Source : subagent QA « Jouer » (son Write a été refusé par le harness, contenu enregistré par le coordinateur, tel que rendu).
Testé sur `http://localhost:5199` (dev, StrictMode actif), Chromium émulé iPhone 14 Pro tactile.
Viewports : 393x852 (standalone), 393x660 (onglet Safari), 393x759 (hauteur utile simulée iPhone 14 Pro standalone : 852 - 59 - 34), 375x667, 852x393, 1440x900.
`PLAY/` = `e2e/qa/play`, captures dans `PLAY/shots/`.
Tous les scripts ont été lancés après le retour du serveur : aucun constat ne date de la panne.

Bilan : 25 constats, 0 critique, 7 majeurs, 14 mineurs, 4 cosmétiques.

## PLAY-1 - Le bot joue encore après la fin de partie, et peut bloquer la partie suivante
- type: bug
- sévérité: majeur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit (2 fois sur 2 pour chaque variante)
- repro: `PLAY/t05_races.py` R1 et R2.
  R1 : Maximus, Blancs, Illimité, 1.e4 puis « Abandonner » pendant la réflexion du bot.
  R2 : même début, puis « Nouvelle partie », « Noirs », « Jouer » avant la fin de la réflexion (fenêtre mesurée 1,4 à 1,8 s).
- attendu: la fin de partie fige l'échiquier ; une nouvelle partie démarre toujours (chess.com).
- observé: R1 : modale « Les Noirs gagnent par abandon » avec 1 demi-coup, puis 1...c5 apparaît sur le board et dans la liste 3,5 s plus tard, alors que le PGN archivé est `1. e4 0-1`.
  R2 : le bot ne joue JAMAIS son premier coup (12 s, position de départ intacte), la partie est bloquée.
  À rythme humain lent (relance 1,8 s et 3 s après e4), R2 ne se reproduit pas.
- capture: PLAY/shots/race_resign_botmove_1.png ; PLAY/shots/race_newgame_black_1.png
- cause probable: `src/pages/Play.tsx:285` ne teste que `isGameOver()` (mat, pat, nulle), pas l'abandon ni le drapeau.
  `Play.tsx:269` : `botThinking.current` reste vrai pendant la recherche de l'ancienne partie, donc le `playBotMove()` de `startGame` (`Play.tsx:326-328`) sort aussitôt et n'est jamais relancé.
  Même chemin pour un drapeau pendant la réflexion du bot (déduit du code).
- correctif proposé: jeton de partie `gameIdRef` incrémenté dans `startGame` et `endGame`.
  Dans `playBotMove`, capturer le jeton avant les `await` et sortir s'il a changé, avant `c.move`.
  Dans `startGame`, `botThinking.current = false` et `engineRef.current?.stop()` ; appeler aussi `stop()` dans `endGame`.

## PLAY-2 - La partie démarre scrollée : haut du board et ligne adverse hors écran
- type: bug
- sévérité: majeur
- page: /#/jouer ; viewport: 393x660 et 393x759
- statut: reproduit
- repro: `PLAY/t11_autoscroll.py` : scroller jusqu'au CTA (obligatoire, voir PLAY-3), lancer une partie 10 min contre Noa.
- attendu: écran de partie ouvert en haut, board entier et pendule adverse visibles.
- observé: `<main>` garde le `scrollTop` de la configuration.
  En 660 : scrollTop 157, haut du board à y = -93 px, rangées 8 et 7 et pendule adverse invisibles.
  En 759 : scrollTop 58, ligne « Noa (400) + pendule » entièrement hors écran, board à y = 6 px.
  En 852 émulé : pas de scroll (804/804).
  L'écran de partie fait 769 px pour 711 px utiles à 759 : il ne tient pas.
- capture: PLAY/shots/game_660.png ; PLAY/shots/autoscroll_759.png
- cause probable: `src/App.tsx:47` (`<main>` scrollable partagé), `src/pages/Play.tsx:307-329` (`startGame` ne remet pas le scroll à zéro), layout `Play.tsx:564-614` trop haut.
- correctif proposé: `document.querySelector('main')?.scrollTo({ top: 0 })` dans `startGame` et au retour en `setup` (ou `useLayoutEffect` sur `status`).
  Mieux : écran de partie non scrollable sur mobile (`h-full flex-col`, board borné par la hauteur) et `MoveStrip` horizontale à la place de la `MoveList` de 128 px (chess.com mobile : coups sur une ligne).

## PLAY-3 - CTA « Jouer » sous le pli dans les deux viewports mobiles
- type: ux
- sévérité: majeur
- page: /#/jouer (configuration) ; viewport: 393x852, 393x660, 1440x900
- statut: reproduit
- repro: `PLAY/t01_setup.py`.
- attendu: CTA visible sans scroller (chess.com : bouton épinglé en bas).
- observé: CTA à y = 900..952, zone visible jusqu'à 804 (852) et 612 (660) : 148 et 340 px de scroll.
  Contenu de 976 px, dont 3 rangées de cartes bot de 104 px.
  En mode Entraîneur : y = 872..924, toujours sous le pli.
  Desktop 1440x900 : CTA à 848..900, collé au bord, ombre rognée.
  Zones tactiles toutes >= 44 px, rien de tronqué, pas de débordement horizontal.
- capture: PLAY/shots/setup_852_top.png ; PLAY/shots/setup_660_top.png ; PLAY/shots/desktop_setup.png
- cause probable: `src/pages/Play.tsx:381-457` (colonne `p-6`, cartes `p-3` empilées, CTA en fin de flux).
- correctif proposé: CTA `sticky bottom-0` avec fond et `pb-safe`.
  Cartes bot en ligne (56 px) ou carrousel d'avatars, conteneur en `p-4`.

## PLAY-4 - Partie en cours perdue sans avertissement en changeant d'onglet
- type: ux
- sévérité: majeur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t05_races.py` R3 : 2 coups contre Noa, onglet Archive, retour sur Jouer.
- attendu: chess.com conserve la partie ; au minimum une confirmation.
- observé: retour à l'écran de configuration, aucune boîte de dialogue, aucune entrée en Archive (8 avant, 8 après).
  Les choix de configuration sont aussi réinitialisés (Nina, Blancs, 10 min).
- capture: PLAY/shots/race_nav_back.png
- cause probable: état local au composant (`src/pages/Play.tsx:53-68`), démonté par le routeur (`src/App.tsx:50`).
- correctif proposé: persister la partie à chaque demi-coup (pgn, pendules, horodatage, bot, couleur, cadence, mode) et la restaurer au montage.
  Pastille « partie en cours » sur l'onglet.
  Persister le dernier bot, la couleur et la cadence dans `src/store/settings.ts`.

## PLAY-5 - Entraîneur : le commentaire sur MON coup reste moins d'une seconde
- type: ux
- sévérité: majeur
- page: /#/jouer (Entraîneur) ; viewport: 393x852 et 393x660
- statut: reproduit (2 sessions, 4 mesures)
- repro: `PLAY/t06_coach.py` (échantillonneur en page toutes les 50 ms).
- attendu: chess.com laisse le retour sur le coup du joueur jusqu'à son prochain coup.
- observé: durée avant écrasement par le commentaire du bot : 747 ms (1.e4), 403 ms (Dh5 « Pas terrible »), 331 ms (Dxf7+ « Ça fait mal »), 674 ms (1.e4 en 660).
  Le commentaire qui l'écrase est parfois vide (« ♛e7. »).
  Latence d'éval correcte (environ 200 ms).
- capture: PLAY/shots/coach_852_blunder_early.png ; PLAY/shots/coach_852_after_blunder.png
- cause probable: un seul emplacement `coachMsg` (`src/pages/Play.tsx:123`), réponse du bot en 300 à 800 ms (`Play.tsx:284`).
- correctif proposé: en mode coach, attendre `liveChain.current` puis 1,5 s avant `playBotMove`.
  Ne remplacer le message que si le bot fait une faute.

## PLAY-6 - Pendule : affichage faux et non monotone sous 10 s
- type: bug
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t04_clock.py` (1 min, texte échantillonné toutes les 50 ms).
- attendu: 0:09.9 quand il reste 9,9 s, décompte continu jusqu'à 0:00.0.
- observé: `0:10`, puis `0:10.9` ... `0:10.1`, puis `0:09.0`, puis `0:09.9` ...
  Fin : `0:01.1` puis `0:00`, jamais `0:00.x`.
  Rouge à 20 s, drapeau à 60,0 s mur, jamais de négatif : OK.
- capture: PLAY/shots/clock_tenths.png
- cause probable: `src/components/Clock.tsx:8` (`Math.ceil`) combiné à `Clock.tsx:14` (dixièmes en `floor`).
- correctif proposé: sous 10 s, `Math.floor(ms / 1000)` pour les secondes.

## PLAY-7 - Pendule à base de ticks : dérive sous charge
- type: perf
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit (charge) ; arrière-plan déduit du code
- repro: `PLAY/t09_misc.py` C : 3 min, CPU x6 via CDP, sélections répétées pendant 20 s.
- attendu: la pendule suit le temps réel.
- observé: 20,3 s de temps mur, pendule 3:00 vers 2:43 : 3,3 s offertes (16 %).
  Sans charge, aucune dérive.
- capture: aucune (mesure)
- cause probable: `src/pages/Play.tsx:171-184` retire 100 ms fixes par tick, sans horodatage.
  Un onglet en arrière-plan bridé à 1 Hz décompterait 10 fois trop lentement.
  `Play.tsx:177` : défaite au temps même si l'adversaire ne peut pas mater (chess.com : nulle).
  Seuil sonore 15 s (`Play.tsx:178`) contre rouge à 20 s (`Clock.tsx:11`).
- correctif proposé: `turnStartedAt = performance.now()` plus temps restant au début du trait, recalcul à chaque tick et sur `visibilitychange`.

## PLAY-8 - La surbrillance du dernier coup disparaît après sélection puis désélection
- type: bug
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t09_misc.py` H : 2 joueurs, 1.e4 d5, taper e4 puis retaper e4.
- attendu: d7 et d5 restent surlignées.
- observé: d5 n'est plus surlignée, d7 oui.
  Erreur console React « Removing a style property during rerender (background) when a conflicting property is set (backgroundColor) ».
  Cas courant : dès qu'une pièce peut reprendre celle qui vient de jouer.
- capture: PLAY/shots/hl_triptych.png
- cause probable: `src/components/Board.tsx:117-122` mélange `background` et `backgroundColor`.
- correctif proposé: dégradés dans `backgroundImage`, teintes dans `backgroundColor` (idem `Board.tsx:108-110`).

## PLAY-9 - Partie enregistrée en double en dev (effets de bord dans un updater)
- type: bug
- sévérité: mineur
- page: /#/jouer, /#/archive, /#/stats ; viewport: 393x852
- statut: reproduit en dev ; vérifié absent en prod
- repro: `PLAY/t03_noa.py`, `PLAY/t02_rules.py`, `PLAY/t08_prod_doublesave.py`.
- attendu: 1 partie = 1 entrée.
- observé: en dev, mat, pat, répétition et abandon créent 2 entrées identiques ; Stats affiche « 2 gagnées » pour 1 partie.
  L'Elo n'est pas doublé par chance (804, `games: 1`).
  Le drapeau ne double pas.
  Sur `https://maxencebrochard.github.io/chess-local` : 1 seule entrée.
  Conséquence : les E2E et les tests manuels en dev polluent Archive et Stats.
- capture: PLAY/shots/noa_w_archive.png ; PLAY/shots/noa_w_stats.png
- cause probable: `src/pages/Play.tsx:191-227` : `db.games.add` et `applyRating` dans l'updater de `setStatus`.
- correctif proposé: garde `endedRef`, `setStatus('over')`, sauvegarde hors updater, remise à `false` dans `startGame`.

## PLAY-10 - Abandon en un tap sans confirmation, partie de 0 coup classée (-36 Elo)
- type: ux
- sévérité: majeur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t05_races.py` R4 ; `PLAY/t04_clock.py` (drapeau sans jouer).
- attendu: chess.com : confirmation, et partie sans coup annulée sans effet Elo.
- observé: « Les Noirs gagnent par abandon, Classement : 764 (-36) », partie vide archivée avec « Bilan de la partie ».
  Même chose « au temps » sans aucun coup.
  Bouton pleine largeur de 40 px, dans la zone du pouce.
- capture: PLAY/shots/race_resign_move0.png ; PLAY/shots/clock_flag_modal.png
- cause probable: `src/pages/Play.tsx:331-335` et `Play.tsx:605-608`.
- correctif proposé: feuille de confirmation.
  Si `sans.length < 2` : « Annuler la partie », sans `applyRating` ni `db.games.add`.

## PLAY-11 - Modale de fin : pas de revanche, titre impersonnel, Bilan perdu une fois fermée
- type: ux
- sévérité: majeur
- page: /#/jouer ; viewport: 393x852, 375x667
- statut: reproduit
- repro: `PLAY/t02_rules.py` E, `PLAY/t03_noa.py`, `PLAY/t09_misc.py` S.
- attendu: chess.com : « Vous avez gagné ! », Elo, Bilan, Revanche, Nouvelle partie, croix, actions toujours accessibles sous le board.
- observé: seulement « Bilan de la partie » et « Nouvelle partie ».
  Titre « Les Blancs gagnent » même quand je gagne.
  Un tap sur le fond ferme sans croix, puis 0 bouton Bilan dans la page.
  La modale cache le roi maté (mat du fou).
  « (+0) » en vert après une défaite.
  Largeur fixe : 4,5 px de marge à 393, bord à bord à 375.
  Résultat, motif et delta Elo corrects.
- capture: PLAY/shots/noa_w_gameover_modal.png ; PLAY/shots/rules_mate_modal_local.png ; PLAY/shots/rules_mate_after_close.png ; PLAY/shots/modal_375.png
- cause probable: `src/pages/Play.tsx:466-497` et `Play.tsx:609-613`.
- correctif proposé: titre selon le point de vue.
  Bouton « Revanche » (`startGame()`), croix.
  Bilan, Revanche et Nouvelle partie dans le panneau après fermeture.
  `w-[min(24rem,calc(100vw-2rem))]`, modale ancrée en bas.
  « (0) » en gris quand le delta est nul.

## PLAY-12 - Ni pièces capturées ni avantage matériel
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: tous
- statut: reproduit (absence)
- repro: `PLAY/t03_noa.py`.
- attendu: chess.com : pièces prises et « +3 » sous chaque nom.
- observé: nom, Elo et pendule uniquement.
- capture: PLAY/shots/noa_w_move_6.png
- cause probable: `src/pages/Play.tsx:566-583`.
- correctif proposé: composant `CapturedPieces` calculé depuis `chess.board()`.

## PLAY-13 - Aucune proposition de nulle
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: tous
- statut: reproduit (absence), confirmé dans le code
- repro: toute partie.
- attendu: bouton « Nulle » (chess.com).
- observé: absent.
  Les nulles automatiques fonctionnent : pat et triple répétition.
- capture: PLAY/shots/rules_stalemate.png ; PLAY/shots/rules_threefold.png
- cause probable: `src/pages/Play.tsx:599-613`.
- correctif proposé: accord mutuel en local.
  Contre un bot, acceptation si l'éval est dans ±0,5 après le coup 30.

## PLAY-14 - Promotion : overlay non annulable, glyphes peu lisibles
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t02_rules.py` B.
- attendu: chess.com : colonne de pièces sur la case d'arrivée, annulable.
- observé: l'overlay couvre tout le board, un tap hors des boutons est sans effet.
  Glyphes Unicode fins, pion revenu en c7 pendant le choix.
  Promotion et sous-promotions fonctionnent (`cxd8=♘`, `cxd1=♜+`).
- capture: PLAY/shots/rules_promo_overlay.png
- cause probable: `src/components/Board.tsx:160-178`.
- correctif proposé: annulation au clic sur le fond.
  Colonne sur la case d'arrivée avec les SVG de pièces du board.

## PLAY-15 - Coach : bulle en anglais, phrase fausse sur le premier coup
- type: ux
- sévérité: mineur
- page: /#/jouer (Entraîneur) ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t06_coach.py`.
- attendu: français, cohérent avec le coup joué.
- observé: « Ah, French Defense. Terrain connu. », « Ah, King's Pawn Game. », alors que le bandeau de la page dit « Défense française ».
  Après 1.Cf3 : « ♘f3 - le grand classique. On prend le centre. ».
  Le reste est cohérent.
- capture: PLAY/shots/coach_660_after_e4.png
- cause probable: `src/lib/liveCoach.ts:61` (`opening.name` brut) et `liveCoach.ts:59-60`.
- correctif proposé: `openingFamilyFr(opening.name)`.
  Réserver la phrase à e4 et d4.

## PLAY-16 - Coach : la classification live n'est visible nulle part
- type: ux
- sévérité: mineur
- page: /#/jouer (Entraîneur) ; viewport: 393x852
- statut: reproduit, confirmé dans le code
- repro: `PLAY/t06_coach.py`, après Dxf7+.
- attendu: pastille de classe dans la bulle, sur la case d'arrivée et dans la liste (chess.com).
- observé: aucune pastille, sauf « livre » sur le board.
- capture: PLAY/shots/coach_852_after_blunder.png
- cause probable: `src/pages/Play.tsx:512` passe `cls` sans `headline`, or `src/components/CoachBubble.tsx:24-26` n'affiche `ClassIcon` que dans le bloc `headline`.
  `Play.tsx:532` : `classes` toutes à `null`.
  `Play.tsx:526` : badge seulement pour `book`.
- correctif proposé: `liveClasses` par demi-coup, passé à `MoveStrip` et au `badge`, plus un `headline`.

## PLAY-17 - Configuration : clé anglaise, cadence écrasée par le mode Entraîneur
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t01_setup.py`.
- attendu: libellé français, cadence bot conservée.
- observé: « Mon classement rapid : 800 ».
  Après Entraîneur puis retour : « unlimited », avec « Illimité » resté sélectionné.
  Glyphes texte minuscules pour Blancs et Noirs à côté de l'emoji Aléatoire.
- capture: PLAY/shots/setup_852_bottom.png
- cause probable: `src/pages/Play.tsx:450` et `Play.tsx:387`.
- correctif proposé: table de libellés.
  `effectiveTc` dérivé en mode coach, sans toucher `tc`.

## PLAY-18 - Zones tactiles sous 44 px en partie, bouton « premier coup » qui ne va pas au début
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t05_races.py` R5.
- attendu: 44 px minimum, accès à la position initiale.
- observé: 4 flèches de 36 px, Abandonner à 40 px.
  Le bouton « premier coup » affiche la position après 1.e4.
  Un coup tenté en consultation est refusé sans retour visuel.
  Barre d'actions du coach conforme (46 px).
- capture: PLAY/shots/hist_first.png
- cause probable: `src/pages/Play.tsx:653-659`, `Play.tsx:606`, `Play.tsx:600`.
- correctif proposé: `min-h-11`.
  `viewIndex: number | null` pour autoriser -1 comme position initiale.
  Un tap sur le board ramène au direct.

## PLAY-19 - Accessibilité : flèches sans nom, modale sans rôle ni focus
- type: a11y
- sévérité: mineur
- page: /#/jouer ; viewport: tous
- statut: reproduit (DOM)
- repro: `PLAY/t09_misc.py` A.
- attendu: `aria-label`, `role="dialog"` avec `aria-modal`, focus dans la modale, Échap.
- observé: `aria-label` nul et `title` vide sur les 4 flèches.
  Modale sans rôle, focus hors de la modale, Échap sans effet.
- capture: aucune
- cause probable: `src/pages/Play.tsx:467-468`, `Play.tsx:653-659`, `src/components/Board.tsx:164-174`.
- correctif proposé: `aria-label`, rôle de dialogue, focus sur le CTA, écouteur Échap.

## PLAY-20 - Paysage 852x393 : en mode Entraîneur le board ne tient pas
- type: ux
- sévérité: mineur
- page: /#/jouer ; viewport: 852x393
- statut: reproduit
- repro: `PLAY/t07_maximus_robust.py` L.
- attendu: board entier visible.
- observé: en mode bot, ça tient tout juste (board 299 px, y 50..349, pendule basse 357..393).
  En mode coach : board à y 154..453 pour 393 px, rangées 3 à 1 cachées.
  Liseré sombre d'1 px entre les rangées 5 et 4 (cases de 37,33 px).
- capture: PLAY/shots/landscape_coach.png ; PLAY/shots/landscape_game.png
- cause probable: `src/pages/Play.tsx:502-529` ; `src/index.css:26-28`.
- correctif proposé: deux colonnes en paysage.
  Taille du board multiple de 8 px.

## PLAY-21 - Coach en 393x660 : bande de coups rognée
- type: ux
- sévérité: cosmétique
- page: /#/jouer (Entraîneur) ; viewport: 393x660
- statut: reproduit
- repro: `PLAY/t12_coach660.py`.
- attendu: ligne de coups visible.
- observé: coups à y 541..571, barre d'actions à 549 : 22 px sur 30 masqués.
  Aucun saut de layout par ailleurs (board fixe à 154 px, bulle à 62 px).
- capture: PLAY/shots/coach_660_strip.png
- cause probable: `src/pages/Play.tsx:506-536`.
- correctif proposé: board borné par `100dvh - 330px`.

## PLAY-22 - Flèche d'indication presque invisible
- type: ux
- sévérité: cosmétique
- page: /#/jouer (Entraîneur) ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t06_coach.py`, indication Dxe7.
- attendu: flèche orange opaque ou cases surlignées (chess.com).
- observé: flèche verte translucide sur board vert, recouverte par les deux dames.
- capture: PLAY/shots/coach_852_hint_crop.png
- cause probable: `src/pages/Play.tsx:347` (`#81b64c`).
- correctif proposé: `rgba(255,170,0,0.9)` plus `markSquares` sur le départ et l'arrivée.

## PLAY-23 - Noms d'ouverture à moitié traduits
- type: ux
- sévérité: cosmétique
- page: /#/jouer ; viewport: tous
- statut: reproduit
- repro: 1.e4 e5 2.Cf3 Cf6 3.d4 ; 1.e4 a6 ; 1.Ch3.
- attendu: une seule langue.
- observé: « Défense Petrov · Modern Attack », « St. George Defense », « Amar Opening », « Ware Defense ».
- capture: PLAY/shots/noa_w_move_6.png
- cause probable: `src/lib/openingNames.ts:2-41` (38 familles, aucune variante).
- correctif proposé: règles sur les suffixes (Defense, Opening, Attack, Variation, Gambit).

## PLAY-24 - 2 joueurs local : board jamais retourné, aucune option
- type: ux
- sévérité: mineur
- page: /#/jouer (2 joueurs) ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t02_rules.py`.
- attendu: chess.com « Passer et jouer » : retournement optionnel.
- observé: orientation toujours blanche.
  Alternance, pendules, incrément et sauvegarde non classée : OK.
- capture: PLAY/shots/rules_castles.png
- cause probable: `src/pages/Play.tsx:461`.
- correctif proposé: option « retourner à chaque coup », ou mode face à face.

## PLAY-25 - Roque en posant le roi sur sa tour refusé
- type: ux
- sévérité: cosmétique
- page: /#/jouer ; viewport: 393x852
- statut: reproduit
- repro: `PLAY/t02_rules.py` A (glisser e1 sur h1).
- attendu: accepté (chess.com).
- observé: refusé.
  e1-g1 et e8-c8 fonctionnent en glisser et en tap.
- capture: PLAY/shots/rules_castles.png
- cause probable: `src/components/Board.tsx:80-82`.
- correctif proposé: remapper roi-sur-tour-amie vers la case de roque.

## Couverture
- Configuration : 9 bots, 3 couleurs, 8 cadences, 3 modes, états sélectionnés nets, zones tactiles >= 44 px, pas de débordement horizontal.
- Parties complètes contre Noa gagnées par mat avec les blancs (10 min) et les noirs (3|2), en alternant glisser tactile et tap.
  Le bot répond toujours (0,5 à 1,2 s réels), surbrillance du dernier coup correcte, échec signalé, modale correcte.
  Elo 800 vers 804 identique dans la modale, en base et dans Stats ; partie présente en Archive.
- Noirs : board retourné, coordonnées correctes, premier coup du bot après environ 1 s.
- Règles : petit et grand roque, prise en passant des deux camps, promotion et sous-promotions, coups illégaux refusés en tap et en glisser, pièce clouée, sortie d'échec, mat, pat, triple répétition.
- Pendules : décompte, bascule, incrément, rouge à 20 s, drapeau à 60,0 s, modale « au temps », pendules figées ensuite, jamais de valeur négative.
- Jouer pendant la réflexion du bot : refusé proprement.
  Double tap : désélection.
- Maximus : 4 coups en 1,4 à 1,7 s.
  5 parties enchaînées : temps stables (1,46 à 1,67 s), aucune erreur.
- Coach : aucun saut de layout, éval en environ 200 ms, Indication, badge « non classée », Annuler, fin non classée.
- Desktop 1440x900 : RAS hors PLAY-3.
- Console : aucune `pageerror` ; seule erreur : l'avertissement React de PLAY-8.

## Hypothèses non vérifiées
- Sur un vrai iPhone 14 Pro standalone, les safe areas réduisent la hauteur utile à environ 711 px : PLAY-2 devrait s'y produire. Les insets valent 0 en émulation.
- Pendule quand la PWA iOS passe en arrière-plan : `Page.setWebLifecycleState frozen` n'a pas gelé les timers en headless (0:57 vers 0:47 en 10,3 s), test non concluant.
- Coup du bot appliqué après un drapeau pendant sa réflexion : même cause que PLAY-1, non rejoué.
- Matériel insuffisant et règle des 50 coups : branchés (`Play.tsx:232-241`), non atteints en test.
- Sons : non testés (coupés par les réglages de test).
- Fuite de workers : non observable ; aucun ralentissement sur 5 parties enchaînées.
- Scroll de page pendant un glisser quand l'écran de partie est scrollable (660 et 759) : laissé à l'agent gestes tactiles.
- Safe areas latérales en paysage : non vérifiables en émulation.
