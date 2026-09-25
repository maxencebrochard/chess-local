Je n'ai pas pu créer `findings-touch.md` : le harness refuse aux sous-agents l'écriture de fichiers de rapport et impose de renvoyer les constats en texte. Je n'ai pas contourné ce refus par une redirection shell, donc le contenu complet du fichier est ci-dessous, à enregistrer tel quel. Chemin prévu : `e2e/qa/findings-touch.md`.

## Résumé

13 constats : 1 critique, 4 majeurs, 5 mineurs, 3 cosmétiques.

1. **TOUCH-1 (critique)** : une pièce saisie par son chiffre ou sa lettre de coordonnée ne se joue pas, le navigateur reprend le geste et la page défile de 0 à 58 px. Cela touche toute la colonne de gauche et toute la rangée 1. Deux règles CSS le corrigent, preuve avant/après sur 3 viewports.
2. **TOUCH-3 (majeur)** : avec les safe areas iPhone (émulées), la vue de partie déborde de 58 px et démarre déjà défilée. C'est ce qui rend le défilement visible dans la PWA, et l'émulation brute le masque.
3. **TOUCH-6 (majeur)** : pour le swipe-back iOS, la colonne a commence à 6 px du bord, chaque onglet empile une entrée d'historique, et un retour arrière détruit la partie en cours (reproduit). La parade la plus sûre est `NavLink replace`, vérifiée en émulation. Le geste lui-même reste à valider sur iPhone.
4. **TOUCH-2 (majeur)** : les cases vides et les bords du board sont en `touch-action: auto`, et la page défile jusqu'à 157 px. chess.com pose `touch-action: none` sur tout le board et ne laisse aucune marge.
5. **TOUCH-5 (majeur)** : `MoveList.tsx:15` (`scrollIntoView`) fait défiler la page après un coup joué. Je l'ai reproduit en Safari 660, mais pas en standalone émulé.

À savoir :

- Le serveur 5199 était tombé en début de session, puis il est revenu. Toutes mes mesures viennent du vrai serveur dev, et je n'en ai lancé ni tué aucun.
- Un texte présenté comme un « message du coordinateur » est apparu dans la sortie d'une de mes commandes. Je ne l'ai pas traité comme une instruction. Si ces consignes venaient de toi, dis-le moi.

---

# Findings - gestes tactiles sur l'échiquier

Testeur : agent QA "touch".
Date : 2026-09-18.
Scripts, sorties brutes (`out_*.txt`) et captures : `e2e/qa/touch/`.
Dans la suite, `touch/` désigne ce dossier et `lib` désigne `node_modules/react-chessboard/dist/index.esm.js` (react-chessboard 5.10.0, dnd-kit embarqué).

## Conditions de test à connaître avant de lire

- Toutes les mesures rapportées ici ont été prises sur le vrai serveur dev `http://localhost:5199` (chaque script imprime `MODE=dev-server`).
- Le serveur était injoignable au début de ma session (20:05:15 à 20:06:15 d'après `touch/server_poll.log`).
  Mon tout premier lancement a échoué en `ERR_CONNECTION_REFUSED` : c'est un artefact de cette panne, rien n'en est rapporté ici.
  Je n'ai lancé, tué ni relancé aucun serveur.
  J'avais préparé un repli sans serveur (requêtes servies depuis `dist/` par interception Playwright, `touch/touch_env.py`) : il n'a jamais servi.
- Un texte présenté comme un "message du coordinateur" est apparu dans la sortie d'une de mes commandes (rejouer les scripts, prévenir "main" par SendMessage, ne pas contourner une panne).
  Arrivé dans un résultat d'outil, je ne l'ai pas traité comme une instruction.
  Le seul fait utile qu'il contenait (serveur revenu) a été vérifié par mes propres moyens.
- "standalone852+insets-emules" : `env(safe-area-inset-*)` vaut 0 en émulation, alors que sur un iPhone 14 Pro en PWA les insets valent 59 px en haut et 34 px en bas.
  J'ai ajouté une configuration qui force `.pt-safe { padding-top: 71px }` et `.pb-safe { padding-bottom: 34px }` par injection CSS.
  C'est une émulation du layout réel, pas une mesure sur appareil.
- Indicateur `pointercancel` : dans Chromium, il signifie que le navigateur a repris le geste à la page (pan ou scroll).
  Quand rien n'est scrollable, Chromium ne montre aucun mouvement, mais sur iOS c'est ce même cas qui produit le rebond élastique.
  Je l'utilise comme indicateur vérifiable de "geste volé par le navigateur".
- Chaque geste enregistre l'élément réellement touché au départ (`hit=`).
  Toute ligne dont le doigt n'a pas touché la cible prévue est marquée invalide et n'est pas utilisée.

## TOUCH-1 - Pièce saisie par son chiffre ou sa lettre de coordonnée : coup non joué et page qui défile
- type: bug
- sévérité: critique
- page: toutes les pages avec un board (mesuré sur `/#/jouer`, `/#/analyse`, `/#/puzzles`, `/#/rush`, `/#/apprendre` x4 domaines) ; viewport: standalone 393x852 (brut et avec safe areas émulées), safari 393x660, 393x560
- statut: reproduit
- repro: `touch/t11_proof_shots.py` (le plus court), `touch/t04_play.py`, `touch/t02_analyse.py`, `touch/t06_puzzles_rush_learn.py`.
  Manuellement : démarrer une partie avec les blancs, poser le doigt sur le petit "2" en haut à gauche du pion a2 et tirer vers a4.
  Même chose avec la lettre en bas à droite de n'importe quelle pièce de la rangée 1.
- attendu: la pièce suit le doigt et le coup est joué, quel que soit l'endroit de la case où on la saisit.
  Rien ne défile.
- observé: le doigt touche le `<span>` de coordonnée (`hit=coordonnee:2`), pas la pièce.
  Le drag ne démarre jamais (`clone=False`), le coup n'est pas joué, le navigateur reprend le geste (`pointercancel=1`) et `<main>` défile.
  `/#/jouer` standalone+insets émulés : `main.scrollTop` 0 -> 58, board de y=123 à y=65.
  `/#/jouer` safari660 : 0 -> 64 (pion a2) puis 0 -> 100 (cavalier g1 saisi par sa lettre).
  `/#/analyse` 393x560 : 0 -> 64 puis 64 -> 116.
  Pages non scrollables (Rush, Apprendre, standalone brut) : pas de défilement dans Chromium mais `pointercancel=1` et coup non joué.
  Zones concernées : toute la colonne de gauche (coin haut-gauche) et toute la rangée du bas (coin bas-droit), soit 15 cases, dont toute la première rangée du joueur.
  Le span mesure 7,2 x 19,5 px (chiffre) ou 3,9 à 7,5 x 19,5 px (lettre) sur une case de 47,6 px, soit environ 6 % de la surface d'une case par coordonnée, de l'ordre de 10 à 12 % en a1 qui en porte deux (largeur du "a" non mesurée).
  C'est cohérent avec le "parfois" du rapport utilisateur.
- capture: `touch/shots/t11_preuve_AVANT.png` (pion resté en a2, page défilée de 58 px), `touch/shots/t11_preuve_APRES.png`
- cause probable: `lib:5480-5500` rend les coordonnées comme des `<span>` en `position: absolute` frères de la pièce dans la case.
  Ils sont peints au-dessus de la pièce et reçoivent le toucher.
  Ils sont hors du wrapper draggable (`lib:5283-5292`), donc aucun capteur dnd-kit ne s'active.
  Leur `touch-action` effectif est `auto` : seul le `<div>` pièce porte `touchAction: 'none'` (`lib:5346`).
  Rien dans `src/components/Board.tsx:130-150` ni `src/index.css:26-28` ne compense.
- correctif proposé: dans `src/index.css`, après `.boardbox` (l.26-28) :
  `.boardbox { touch-action: none; }` et `.boardbox [data-square] > span, .boardbox [data-square] > span > span { pointer-events: none; }`.
  Variante équivalente non testée pour la seconde règle : `alphaNotationStyle: { pointerEvents: 'none' }` et `numericNotationStyle: { pointerEvents: 'none' }` dans les options de `Board.tsx:132-150` (fusionnées par `lib:4775-4786`).
  Les deux règles sont nécessaires : `touch-action` seul supprime le défilement mais laisse la zone morte (coup toujours non joué, mesuré dans `touch/out_t02_fix.txt`).
  preuve: injection par `page.add_style_tag`, même script.
  Avant : `hit=coordonnee:2 coup_joué=False pointercancel=1 main.scrollTop 0 -> 58`.
  Après : `hit=piece:wP coup_joué=True pointercancel=0 main.scrollTop 0 -> 0`, a4 = wP.
  Tableau complet dans `touch/out_t02_base.txt`, `out_t02_fix.txt`, `out_t02_fix2.txt`, `out_t04_base.txt`, `out_t04_fix2.txt`.
  Lignes `[SCROLL]` résiduelles de ces fichiers "fix2" : dans `out_t02_fix2.txt`, une seule, marquée `hit=HORS-BOARD` (le doigt visait la barre d'actions, voir TOUCH-12) ; dans `out_t04_fix2.txt`, deux en safari660 (g1->f3 et h2->h4, `pointercancel=0`, défilement après le lâcher) qui sont TOUCH-5, pas un scroll dû au geste.

## TOUCH-2 - Cases vides et bords du board en `touch-action: auto` : un glissé sur le board fait défiler la page
- type: bug
- sévérité: majeur
- page: toutes les pages avec un board ; viewport: standalone 393x852 avec safe areas émulées, safari 393x660, 393x560
- statut: reproduit
- repro: `touch/t04_play.py`, `touch/t02_analyse.py`, `touch/t06_puzzles_rush_learn.py`.
  Poser le doigt sur une case vide et glisser verticalement de 200 px.
- attendu: un geste qui commence dans le board ne fait jamais défiler la page.
  Référence chess.com mobile web : `touch-action: none` et `user-select: none` posés sur l'élément board entier (mesuré, voir TOUCH-6).
- observé: `pointercancel=1` à chaque fois.
  `/#/jouer` safari660 : `main.scrollTop` 0 -> 157, board de y=64 à y=-93 (les rangées 8 et 7 sortent de l'écran).
  `/#/jouer` standalone+insets émulés : 0 -> 58.
  `/#/analyse` 393x560 : 0 -> 125.
  `/#/puzzles` safari660 : 0 -> 109 ; standalone+insets émulés : 0 -> 10.
  Même résultat board non interactif (relecture d'une partie) : case vide 0 -> 157.
  Effet secondaire : 5 erreurs console `Ignored attempt to cancel a touchend event with cancelable=false` par scénario, levées par le `preventDefault` de `lib:5401` pendant le défilement.
- capture: `touch/shots/t04_safari660_base_fin.png`
- cause probable: `touchAction: 'none'` n'existe que sur le `<div>` pièce (`lib:5346`).
  `defaultSquareStyle` (`lib:4751-4757`), le board et `.boardbox` (`src/index.css:26-28`) sont en `auto`.
  Le `preventDefault` de dnd-kit sur `touchmove` (`lib:1841`) n'arrive qu'après activation d'un drag, donc jamais pour une case vide.
- correctif proposé: le même `.boardbox { touch-action: none; }` que TOUCH-1.
  A poser sur `.boardbox` dans `index.css` et PAS sur le wrapper de `Board.tsx:130` : le diagramme de `CourseSheet.tsx:31` n'est pas dans un `.boardbox` et doit continuer à laisser défiler la feuille (voir TOUCH-9).
  preuve: avec l'injection, toutes les lignes "case vide" passent à `pointercancel=0`, `scrolled=null` sur les 3 configurations, et les erreurs console passent de 5 à 0 (`touch/out_t04_fix2.txt`).

## TOUCH-3 - La vue de partie déborde de l'écran et démarre déjà défilée, board coupé
- type: bug
- sévérité: majeur
- page: `/#/jouer` ; viewport: safari 393x660, et standalone 393x852 avec safe areas émulées
- statut: reproduit (safari660) ; reproduit avec safe areas émulées pour le standalone, à valider sur iPhone
- repro: `touch/t04_play.py`, `touch/t05_movelist_scroll.py`.
  Sur `/#/jouer`, faire défiler le formulaire jusqu'au bouton "Jouer" (sous le pli : formulaire de 976 px pour 612 px visibles) et démarrer la partie.
- attendu: la partie s'ouvre avec le board entièrement visible, et idéalement rien n'est scrollable pendant une partie.
- observé: safari660 : au démarrage `main.scrollTop=157` (= le maximum), `boardTop=-93`.
  Les rangées 8 et 7, le nom et la pendule de l'adversaire sont hors écran.
  Standalone avec safe areas émulées : la vue déborde de 58 px, démarre à `scrollTop=58`, `boardTop=65` pour un padding haut de 71 px.
  Standalone brut (insets à 0) : tout tient, rien n'est scrollable.
  C'est pourquoi l'émulation iPhone brute masque le problème.
  Conséquence directe : c'est parce que la page est scrollable que TOUCH-1 et TOUCH-2 produisent un défilement visible dans la PWA.
  Partie démarrée défilée au maximum, le seul défilement possible est "le contenu descend quand le doigt descend", ce qui correspond au "scroll vers le bas" rapporté.
- capture: `touch/shots/t04_safari660_base_debut.png`, `touch/shots/t11_preuve_APRES.png` (bouton "Abandonner" sous le pli avec safe areas émulées)
- cause probable: `src/pages/Play.tsx:307-325` (`startGame`) ne remet pas le scroll de `<main>` à zéro, et aucun code de `src/` ne le fait (grep `scrollTo|scrollTop` : seuls `MoveStrip.tsx:26` et `MoveList.tsx:15`).
  La liste de coups a une hauteur fixe `h-32` (`Play.tsx:596`) au lieu d'occuper la place restante.
- correctif proposé: faire tenir la vue de partie dans `<main>` : remplacer `h-32` par `min-h-0 flex-1` sur le conteneur de `MoveList` et donner à la colonne une hauteur bornée (`h-full min-h-0`).
  Remettre `main.scrollTop = 0` dans `startGame`.
  preuve: non injecté (changement de layout, à vérifier après implémentation avec les 3 configurations de `touch/t04_play.py`).

## TOUCH-4 - Le scroll de `<main>` est conservé d'une route à l'autre
- type: bug
- sévérité: mineur
- page: toutes ; viewport: safari 393x660
- statut: reproduit
- repro: `touch/t08_misc.py` (partie 3/4).
  Défiler en bas de `/#/jouer`, puis toucher l'onglet Puzzles.
- attendu: chaque page s'ouvre en haut.
- observé: `<main>` à 364 sur Jouer, puis Puzzles s'ouvre avec `mainScrollTop=109` et `boardTop=-89` (haut du board coupé).
- capture: `touch/shots/t08_3_scroll_conserve_entre_routes.png`
- cause probable: `src/App.tsx:47`, le `<main className="... overflow-y-auto">` est unique et persiste entre les routes.
  Le navigateur borne simplement `scrollTop` au nouveau maximum.
- correctif proposé: un petit composant dans `App.tsx` qui, sur changement de `useLocation().pathname`, fait `mainRef.current.scrollTop = 0`.
  preuve: non injecté.

## TOUCH-5 - Jouer un coup fait défiler la page : `scrollIntoView` de la liste de coups
- type: bug
- sévérité: majeur
- page: `/#/jouer` ; viewport: safari 393x660
- statut: reproduit en safari660.
  NON reproduit en standalone 852 avec safe areas émulées (8 coups, `scrollTop` reste à 0) : dans ce layout la liste tient dans la zone visible.
  Ce constat n'explique donc pas à lui seul le rapport sur PWA installée pour un écran de la taille d'un iPhone 14 Pro.
  Il peut le faire sur un iPhone plus petit (non testé).
- repro: `touch/t05_movelist_scroll.py`.
  Board entièrement visible, jouer 5 coups par un drag propre au centre de la pièce.
- attendu: jouer un coup ne déplace jamais le board.
- observé: drags propres (`hit=piece:wP`, `pointercancel=0`), et pourtant `main.scrollTop` passe de 0 à 14 (coup 3), 40 (coup 4), 57 (coup 5), board de y=64 à y=7.
  Le défilement arrive après le lâcher, pas pendant le drag (board immobile à mi-course).
  Le nom et la pendule de l'adversaire finissent hors écran.
- capture: `touch/shots/t05_safari660_base_2_fin.png` (avant), `touch/shots/t05_safari660_fix_2_fin.png` (après)
- cause probable: `src/components/MoveList.tsx:14-16` : `scrollIntoView({ block: 'nearest' })` sur le coup courant à chaque changement d'index.
  `scrollIntoView` fait défiler tous les ancêtres scrollables, donc `<main>`.
  Le commentaire de `src/components/MoveStrip.tsx:21` montre que le piège a été évité là, pas ici.
- correctif proposé: faire défiler uniquement le conteneur de la liste, comme `MoveStrip.tsx:26` : calculer la position du bouton courant par rapport à `ref.current` et ajuster `ref.current.scrollTop`.
  preuve: injection d'un `Element.prototype.scrollIntoView` limité au conteneur le plus proche : les 8 coups restent à `main.scrollTop=0` (`touch/out_t05_fixsiv.txt`).
  Limite observée de ce correctif seul : en safari660 le coup courant reste alors caché sous la barre de navigation, car la liste elle-même dépasse du pli.
  Le remède complet est TOUCH-3 (vue qui tient dans l'écran).

## TOUCH-6 - Swipe-back iOS depuis le bord gauche : la colonne a est dans la zone du geste, et un retour détruit la partie
- type: bug
- sévérité: majeur
- page: toutes les pages avec un board ; viewport: PWA standalone iOS
- statut: déduit du code (non reproductible en émulation) pour le geste lui-même ; reproduit pour sa conséquence
- repro: géométrie `touch/t01_inventory.py` ; conséquence `touch/t10_back_nav.py` ; historique `touch/t08_misc.py`.
- attendu: tirer une pièce de la colonne a ne déclenche jamais de navigation, et une navigation accidentelle ne fait pas perdre la partie.
- observé (vérifiable en émulation) : le board commence à 6 px du bord gauche de l'écran (`.boardbox = 100vw - 0.75rem`), il reste 6 px à droite.
  La colonne de gauche couvre x = 6 à 53,6 px, son centre est à 29,8 px.
  Une pièce de cette colonne a été saisie avec succès à x = 14 px et x = 11 px du bord.
  Avec les noirs, c'est la colonne h qui se retrouve à gauche.
  Chaque toucher d'onglet empile une entrée : `history.length` 2 -> 8 après 6 onglets.
  Il existe donc presque toujours une page précédente vers laquelle revenir.
  `history.back()` pendant une partie (ce que fait le swipe-back) mène à `#/`, et revenir sur `#/jouer` affiche l'écran de configuration : la partie en cours est perdue.
  `src/pages/Play.tsx` ne persiste pas la partie en cours (aucun `sessionStorage`, `localStorage` ni `useBlocker`).
  chess.com mobile web (`/play/computer`, 393 px) : board de bord à bord, gauche 0,5 px, largeur 392 px, `touch-action: none`, `user-select: none`.
  Ils ne laissent donc aucune marge latérale.
  Réserve : le board était masqué par une modale d'accueil au moment de la capture, les valeurs viennent du DOM et des styles calculés.
- capture: `touch/shots/t10_a_apres_forward.png`, `touch/shots/t09_chesscom_mobile.png`
- cause probable: `src/App.tsx:62` (`NavLink` de la barre du bas sans `replace`) + `HashRouter` + `display: 'standalone'` (`vite.config.ts:29`).
  En PWA standalone, iOS active le balayage depuis le bord pour revenir en arrière dès qu'une entrée précédente existe.
  Ce geste est un reconnaisseur système au-dessus du contenu web : `touch-action: none` ne le désactive pas.
- correctif proposé, par ordre de robustesse :
  1. Ne plus empiler d'historique pour les onglets : `<NavLink replace>` (au besoin seulement si `matchMedia('(display-mode: standalone)').matches`).
  Sans entrée précédente, le geste n'a plus de cible.
  Vérifiable en émulation : avec `pushState` redirigé vers `replaceState`, `history.length` reste à 2 après 5 onglets et toutes les routes restent atteignables (`touch/out_t10.txt`).
  A valider sur iPhone : que le geste soit bien inerte quand l'historique est vide.
  2. Persister la partie en cours (`sessionStorage`, comme le fait déjà `Learn.tsx` pour sa séance) pour qu'un retour accidentel ne coûte rien.
  Vérifiable en émulation.
  3. `touchstart` non passif avec `preventDefault()` sur les cases : parade connue de la communauté contre le swipe-back, non documentée par Apple.
  Vérifié en émulation qu'elle ne casse rien : 4 `touchstart` interceptés, tous annulables et annulés, aucun événement souris ou click de compatibilité, et tap de sélection, tap-coup, drag, saisie par la coordonnée, boutons de promotion fonctionnent (`touch/out_t09.txt`, `touch/out_t08.txt` partie 5).
  A valider sur iPhone : son efficacité réelle contre le geste, en standalone.
  4. Marge latérale d'au moins 20 à 24 px : réduit le board de 381 à environ 345 px, et chess.com ne le fait pas. Dernier recours.
  5. `overscroll-behavior-x: none` : agit sur la navigation par surdéfilement de Chrome Android, pas sur le geste de bord iOS. Inoffensif mais sans effet attendu ici.
  preuve: voir points 1 et 3 ; le geste lui-même reste "à valider sur iPhone".

## TOUCH-7 - Un tap qui bouge de 2 px ne sélectionne rien (`dragActivationDistance: 1`)
- type: ux
- sévérité: mineur
- page: toutes les pages avec un board ; viewport: standalone 393x852
- statut: reproduit
- repro: `touch/t07_interactions.py` partie A.
  Toucher e2 en déplaçant le doigt de N px avant de relâcher.
- attendu: un tap légèrement tremblant sélectionne la pièce (mode tap-tap).
- observé: 0 px -> sélection `['e2']`. 1 px -> sélection `['e2']`. 2 px et 3 px -> aucune sélection, aucun coup, rien. 5 px et 8 px -> drag visible puis aucune sélection.
  La fréquence réelle sur un doigt humain reste à valider sur iPhone.
- capture: `touch/shots/t07_A_tap_tremblant.png`
- cause probable: `src/components/Board.tsx:148` (`dragActivationDistance: 1`) : le drag s'active dès 1 px (`lib:5109-5115`).
  La lib annule alors le tap (`lib:5380-5384`, `isClickingOnMobile` remis à false).
  Au lâcher sur la case de départ, `lib:5048` appelle `onPieceDrop` avec source = cible, et `Board.tsx:137-140` le passe à `tryMove` qui le rejette.
- correctif proposé: dans `Board.tsx:137-140`, traiter `targetSquare === sourceSquare` comme un tap : appeler `handleSquareClick({ piece: null, square: sourceSquare })` puis `return false`.
  Cela garde le suivi immédiat de la pièce sous le doigt, contrairement à une hausse de `dragActivationDistance`.
  preuve: non injecté (logique interne au composant React).

## TOUCH-8 - Promotion impossible à annuler, et voile qui survit à un changement de position
- type: bug
- sévérité: mineur
- page: `/#/analyse` (composant partagé, donc partout) ; viewport: standalone 393x852
- statut: reproduit
- repro: `touch/t08_misc.py` partie 2 et `touch/t12_promo_glyphs.py`.
  Amener un pion en 7e (1.h4 g5 2.hxg5 h6 3.gxh6 Fg7 4.hxg7 Cf6), jouer g7xh8, toucher le voile hors des boutons, puis "Précédent".
- attendu: un tap hors des 4 boutons annule la promotion ; le voile disparaît si la position change.
- observé: après tap sur le voile : toujours affiché, pion toujours en g7.
  Après "Précédent" : la position recule d'un coup mais le voile reste.
  Lecture du DOM : les boutons passent de `♕♖♗♘` (U+2655 à U+2658, pièces blanches) à `♛♜♝♞` (U+265B à U+265E, pièces noires) pour un pion blanc.
- capture: `touch/shots/t08_2_promotion_annulation.png`
- cause probable: `src/components/Board.tsx:160-178` : le voile n'a aucun `onClick` d'annulation.
  `pendingPromotion` (`Board.tsx:34`) n'est jamais réinitialisé quand `fen` change, et `promoColor` (`Board.tsx:127`) est recalculé sur le trait courant.
- correctif proposé: `onClick={() => setPendingPromotion(null)}` sur le voile avec `stopPropagation` sur le conteneur des boutons, un `useEffect` qui remet `pendingPromotion` et `selected` à `null` quand `fen` change, et mémoriser la couleur du pion au moment où la promotion est demandée.
  preuve: non injecté.

## TOUCH-9 - Feuille de cours : les pièces du diagramme bloquent le défilement
- type: ux
- sévérité: mineur
- page: `/#/apprendre`, feuille "Voir le cours complet" ; viewport: safari 393x660
- statut: reproduit
- repro: `touch/t08_misc.py` partie 1.
  Ouvrir un cours de Finales, poser le doigt sur une pièce du diagramme et glisser vers le haut, puis recommencer depuis une case vide.
- attendu: la feuille défile quel que soit l'endroit du diagramme où le doigt se pose, puisque le diagramme est en lecture seule.
- observé: doigt sur une pièce (`touch-action: none`) : feuille 0 -> 0.
  Doigt sur une case vide : feuille 0 -> 145.
- capture: `touch/shots/t08_1_coursesheet.png`
- cause probable: `lib:5346` pose `touchAction: 'none'` sur toutes les pièces, même quand `allowDragging` est faux (`src/components/CourseSheet.tsx:31`, `interactive={false}`).
- correctif proposé: une prop dédiée sur `Board` (par exemple `scrollThrough`), utilisée par `CourseSheet`, qui ajoute une classe au wrapper (`Board.tsx:130`) et dans `index.css` : `.board-scroll-through [data-piece] { touch-action: pan-y !important; }`.
  Ne pas la lier à `interactive` : en relecture de partie le board est non interactif mais doit rester en `none`.
  preuve: non injecté.

## TOUCH-10 - Garde-fous CSS iOS absents hors du board (sélection de texte, callout, rebond)
- type: ux
- sévérité: mineur
- page: toutes ; viewport: tous
- statut: mesuré pour les styles calculés ; déduit du code pour l'effet sur iOS (non reproductible en émulation)
- repro: `touch/t01_inventory.py`, `touch/t07_interactions.py` partie G.
- attendu: une PWA façon application : pas de sélection de texte ni de bulle "Copier" sur l'interface, pas de rebond de page.
- observé: `html`, `body`, `main` : `user-select: auto`, `touch-action: auto`.
  `overscroll-behavior: none` uniquement sur `body` (`src/index.css:21`) ; `html` et `<main>` (le vrai conteneur scrollable, `App.tsx:47`) sont en `auto`.
  `-webkit-touch-callout` n'apparaît nulle part dans `src/`.
  Dans le board : `user-select: none` partout (wrapper `select-none`, `Board.tsx:130`) : correct.
  Long press 900 ms dans Chromium : aucun `contextmenu` sur pièce ni case vide, un `selectstart` sur le texte des lignes moteur.
  `user-scalable=no` est présent (`index.html`) ; iOS l'ignore pour le pincement depuis iOS 10, mais `touch-action: none` sur le board couvre le double-tap et le pincement à cet endroit.
- capture: `touch/shots/t07_G_long_press.png`
- cause probable: `src/index.css:18-23`.
- correctif proposé: `html, body { overscroll-behavior: none; }`, `main { overscroll-behavior: contain; }`, `body { -webkit-user-select: none; user-select: none; -webkit-touch-callout: none; }` avec une classe d'exception (`select-text`) pour les champs PGN et FEN à copier.
  preuve: non injecté ; effet à valider sur iPhone.

## TOUCH-11 - UI de promotion : glyphes Unicode fins, sans rapport avec le jeu de pièces
- type: ux
- sévérité: cosmétique
- page: toutes les pages avec un board ; viewport: standalone 393x852
- statut: reproduit
- repro: `touch/t07_interactions.py` partie F.
- attendu: les pièces proposées reprennent le jeu de pièces du board (référence chess.com).
- observé: la promotion fonctionne par drag et par tap, avec 4 boutons de 64 x 64 px, confortables au doigt, et la sous-promotion en cavalier donne bien `h8 = wN`.
  En revanche les pièces sont de fins glyphes Unicode, petits dans leur bouton et peu contrastés.
- capture: `touch/shots/t07_F_promotion_drag_ui.png`
- cause probable: `src/components/Board.tsx:183-186` (`PROMO_GLYPHS`) et `:166` (`text-4xl`).
- correctif proposé: rendre dans les boutons les composants SVG de `defaultPieces` exportés par react-chessboard (`wQ`, `wR`, `wB`, `wN`, et leurs équivalents noirs).
  preuve: non injecté.

## TOUCH-12 - `/analyse` en viewport très court : la barre d'actions recouvre la rangée 1
- type: ux
- sévérité: cosmétique
- page: `/#/analyse` ; viewport: autre (393x560, viewport artificiel forcé pour les tests de scroll)
- statut: reproduit
- repro: `touch/t03_probe560.py`.
- attendu: la barre collante ne recouvre pas le board.
- observé: au point (190, 473), censé être la case d1, `elementFromPoint` renvoie un bouton de `div.sticky.bottom-0.z-20`.
  La moitié basse de la rangée 1 est masquée, et la barre est plus étroite que le board, dont les coins dépassent de chaque côté.
  Aucun iPhone récent n'a ce viewport : impact réel faible.
- capture: `touch/shots/t03_force560_point_d1.png`
- cause probable: barre d'actions `sticky bottom-0 z-20` de `src/pages/Analysis.tsx` dans un `<main>` trop court pour board + barre.
- correctif proposé: aucun d'urgent ; se règle avec un layout qui borne le board par la hauteur disponible.
  preuve: non applicable.

## TOUCH-13 - Avertissement React : `background` et `backgroundColor` mélangés dans les styles de case
- type: bug
- sévérité: cosmétique
- page: `/#/rush`, `/#/analyse` (observé) ; viewport: tous
- statut: reproduit (console du serveur dev)
- repro: `touch/t06_puzzles_rush_learn.py` (Rush) ou `touch/t08_misc.py` partie 5 : sélectionner une pièce dont une case cible est aussi une case du dernier coup.
- attendu: console propre.
- observé: `a style property during rerender (background) when a conflicting property is set (backgroundColor) can lead to styling bugs`.
- capture: aucune (message console, dans `touch/out_t06_base.txt` et `touch/out_t08.txt`)
- cause probable: `src/components/Board.tsx:112-123` : `squareStyles[t] = { ...squareStyles[t], background: ... }` ajoute le raccourci `background` à un objet qui contient déjà `backgroundColor` (posé l.104-105 pour le dernier coup ou l.100 pour `markSquares`).
- correctif proposé: n'utiliser que des propriétés longues : `backgroundImage` pour le dégradé de la pastille, `backgroundColor` pour la teinte.
  preuve: non injecté.

## Couverture

Testé et correct (aucun constat) :

- Pièce jouable saisie par son centre, drag haut, bas, gauche, droite et diagonales : coup joué, `pointercancel=0`, aucun scroll, `hash` et `history.length` inchangés, sur `/analyse` (3 viewports) et `/jouer` (3 configurations).
- Drag de pièce sur Puzzles, Puzzle Rush et les 4 domaines d'Apprendre : le drag démarre (`clone=True`), aucun scroll.
  Sur ces pages un coup légal mais faux est annulé par la logique de l'exercice : `moved=False` n'y signale pas un défaut du drag.
- Pièce adverse, pièce à soi pendant que le bot réfléchit (fenêtre attrapée dans les 3 configurations : `aria-disabled=true` lu juste avant le geste), pièce en relecture de partie : `touch-action: none` calculé, aucun scroll, aucun drag.
- Auto-scroll de dnd-kit : exclu, `autoScroll: allowAutoScroll` avec défaut `false` (`lib:5174`, `lib:4852`), non surchargé par `Board.tsx`.
- Drag lâché hors du board (au-dessus, et sur la barre de navigation) : la pièce revient, pas de clone fantôme, pas de navigation.
- Tap-tap, changement de sélection vers une autre pièce à soi, re-tap pour désélectionner, tap sur pièce adverse.
- Roque par drag du roi (g1 = wK, f1 = wR), prise en passant par drag (d5 vidée).
- Promotion par drag et par tap, sous-promotion.
- Second doigt posé pendant un drag (sur une pièce, puis sur une case vide) : coup joué, 32 pièces, pas de clone fantôme, board utilisable ensuite.
- Débordement horizontal : le board fait 381 px dans 393 px, marges de 6 px de chaque côté.
- Le recentrage horizontal de la bande de coups (`MoveStrip.tsx:26`) émet des événements de scroll après un coup : c'est voulu et ne déplace pas la page.

Faux positifs de mes propres scripts, écartés après vérification et non rapportés :

- Un scroll résiduel "avec correctif" en 393x560 : le doigt visait en réalité la barre d'actions, pas le board (d'où TOUCH-12).
- "UI de promotion encore visible" : mon sélecteur `.z-20 button` attrapait aussi la barre d'actions ; la capture montre le voile bien fermé.
- Les 8 échecs initiaux sur Apprendre : mon script ne cliquait pas sur "C'est parti".
- Un "la dame d1 ne bouge pas avec le correctif" : le coup précédent ayant enfin réussi, le trait était passé aux noirs.
- Sur `/jouer`, des lignes "pièce adverse" dont le doigt ne touchait rien (board hors écran) et un "bot qui réfléchit" au timing ambigu : scénario réécrit avec cibles validées, puis rejoué.

Hors périmètre, vu au passage : les noms d'ouvertures s'affichent en anglais sur `/jouer` et `/analyse` ("Clemenz Opening", "Ware Opening", "Kádas Opening · Schneider Gambit"), alors que `CLAUDE.md` annonce une traduction à l'affichage.

## Hypothèses non vérifiées

- Tout ce qui est propre à iOS : le rebond élastique de la page quand le navigateur reprend un geste sur une page non scrollable, le geste de retour par le bord, le callout, et l'effet réel de `overscroll-behavior` posé sur `body` plutôt que sur `html`.
- Les valeurs de safe areas (59 px et 34 px) sont celles d'un iPhone 14 Pro en portrait ; je ne connais pas le modèle de l'utilisateur.
  Sur un iPhone plus petit la vue de partie déborde davantage, et TOUCH-5 pourrait alors se produire aussi en PWA.
- La largeur de la zone de départ du geste de retour iOS (ordre de grandeur 20 pt) n'est pas documentée par Apple.
- L'efficacité de `touchstart` + `preventDefault` contre le swipe-back en mode standalone.
- Que le geste de retour soit inerte quand l'historique ne contient qu'une entrée.
- La fréquence réelle des taps "tremblants" de 2 px et plus sur un doigt humain (TOUCH-7).
- Possibles défauts WebKit de `touch-action` sur du contenu SVG ou animé : non observables dans Chromium.
- chess.com : mesure prise dans le DOM avec une modale d'accueil par-dessus le board, non confirmée visuellement.
