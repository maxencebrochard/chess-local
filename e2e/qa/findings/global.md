# Findings QA - enveloppe globale de ChessLocal

Périmètre : accueil, stats/réglages, sauvegarde/restauration, navigation, responsive, PWA/hors ligne, cohérence visuelle.
Cible dev : http://localhost:5199 (HashRouter). Cible PWA : build existant `dist/` servi sur 5198 (arrêté en fin de session).
Scripts : `qa/global/*.py`. Sorties brutes : `qa/global/*.out`, `qa/global/envelope_results.json`. Captures : `qa/global/shots/`.
Abréviation des chemins de capture : `SHOTS` = `e2e/qa/global/shots`.
Abréviation des scripts : `G` = `e2e/qa/global`.
Le tiret cadratin (U+2014) est désigné par son nom dans ce fichier, jamais tapé.

## GLOB-1 - Restaurer écrase toutes les données sans confirmation
- type: bug
- sévérité: majeur
- page: /stats ; viewport: 393x852 (tous)
- statut: reproduit
- repro: `python3 G/backup.py`, bloc C.
  Injecter 10 parties + 7 classements, toucher « Restaurer », choisir `G/backup_files/valide_vide.json` (sauvegarde valide mais vide).
- attendu: une action destructive demande une confirmation qui résume le fichier (date de la sauvegarde, nombre de parties, classements) et ce qui va être remplacé.
  Idéalement un export automatique de l'état courant avant d'écraser.
- observé: aucun dialogue (`dialogs: []`, aucun `div.fixed`).
  La base passe de `games: 10, ratings: 7, puzzleAttempts: 12, rushScores: 4, mistakes: 3, learnSessions: 3` à 0 partout, message « Sauvegarde restaurée. Recharge la page. ».
  Même effet avec un fichier partiel `{"_app":"chess-local","_version":99,"games":[]}` : les 10 parties sont effacées, les autres tables restent (bloc D, cas « version future »).
- capture: SHOTS/restore_success_recharge.png
- cause probable: `src/pages/Stats.tsx:145-156` appelle `importBackup` directement dans le `onChange` du file input.
  `src/lib/backup.ts:34` fait `clear()` sur chaque table présente sans garde-fou.
- correctif proposé: dans `Stats.tsx`, parser d'abord le fichier (nouvelle fonction `inspectBackup(json)` qui valide et retourne `{date, counts}`), afficher une modale « Remplacer tes données actuelles (10 parties, 7 classements) par la sauvegarde du 18/09/2026 (2 parties) ? » avec bouton rouge « Remplacer » et « Annuler ».
  N'appeler `importBackup` qu'après confirmation.

## GLOB-2 - Après restauration : UI figée, « Recharge la page » impossible en PWA, et un réglage touché écrase les réglages restaurés
- type: bug
- sévérité: majeur
- page: /stats ; viewport: 393x852 standalone
- statut: reproduit
- repro: `python3 G/backup.py`, bloc B.
  Contexte navigateur neuf, restaurer `export.json` (thème Améthyste, profondeur Profond, coups légaux off), puis toucher le toggle « Sons » avant de recharger.
- attendu: après restauration, les cartes de stats et les réglages reflètent immédiatement la sauvegarde.
  Aucun besoin de recharger : une PWA iOS en standalone n'a ni bouton recharger ni barre d'URL.
- observé: les données sont bien en base (10 parties, 3 erreurs, 3 séances, 7 classements) mais l'écran affiche toujours « 0 gagnées » et le thème « Vert ».
  Le message demande « Recharge la page. », infaisable en standalone sans tuer l'app.
  Après un tap sur le toggle « Sons », `localStorage['chess-local-settings']` redevient `themeId=green, reviewDepth=fast` : le store Zustand en mémoire (ancien état) réécrit tout le blob et les réglages restaurés sont perdus définitivement.
- capture: SHOTS/restore_success_stale_ui.png, SHOTS/restore_success_recharge.png
- cause probable: `src/lib/backup.ts:38` écrit la chaîne dans localStorage sans réhydrater le store.
  `src/pages/Stats.tsx:14-18` ne relit Dexie qu'au montage.
  `src/pages/Stats.tsx:151` affiche le message « Recharge la page ».
- correctif proposé: après `importBackup`, appeler `useSettings.persist.rehydrate()` (API Zustand persist) puis relancer les trois lectures Dexie (extraire un `reload()` du `useEffect`).
  Remplacer le message par « Sauvegarde du JJ/MM restaurée : N parties, N classements. ».
  À défaut, faire `window.location.reload()` automatiquement juste après l'import.

## GLOB-3 - Restauration partielle silencieuse : état mixte avec une ancienne sauvegarde, succès affiché quand rien n'est restauré
- type: bug
- sévérité: majeur
- page: /stats ; viewport: tous
- statut: reproduit
- repro: `python3 G/backup.py`, blocs D et E.
  Base peuplée (3 erreurs, 3 séances Apprendre), restaurer `G/backup_files/v1_ancienne.json` (`_version: 1`, sans `mistakes` ni `learnSessions`).
  Puis restaurer `G/backup_files/non_tableaux.json` (`games: "oops"`, `ratings: {...}`).
- attendu: une restauration remplace l'état complet : une table absente d'une ancienne sauvegarde doit être vidée (ou l'utilisateur prévenu).
  Un fichier dont aucune table n'est exploitable doit être refusé.
- observé: v1 : `games: 2, ratings: 2` remplacés, mais `mistakes: 3` et `learnSessions: 3` de l'ancien état survivent.
  Résultat : « Mes erreurs » pointe vers des parties qui n'existent plus, et les classements `learn-*` sont effacés alors que l'historique des séances reste.
  Fichier « non tableaux » : message « Sauvegarde restaurée. Recharge la page. » alors que rien n'a été touché.
  `_version` n'est jamais lu (une sauvegarde `_version: 99` avec une table inconnue passe sans avertissement).
  Point positif : un réglage absent d'une ancienne sauvegarde (`reviewDepth`) retombe bien sur son défaut (« Équilibré »).
- capture: aucune (constat sur la base, voir `G/backup.out`)
- cause probable: `src/lib/backup.ts:33` `if (!Array.isArray(rows)) continue` saute la table au lieu de la vider ou d'échouer.
  `src/lib/backup.ts:28-29` ne valide que `_app`.
- correctif proposé: valider avant d'ouvrir la transaction : `_version` numérique <= version courante (sinon « Sauvegarde créée par une version plus récente de ChessLocal, mets l'app à jour. »), chaque table présente doit être un tableau.
  Dans la transaction, `clear()` toutes les tables de `TABLES`, puis `bulkAdd(rows ?? [])`.
  Refuser un fichier sans aucune table.

## GLOB-4 - Messages de restauration bruts, en anglais et en vert ; aucun retour après export
- type: ux
- sévérité: mineur
- page: /stats ; viewport: 393x852
- statut: reproduit
- repro: `python3 G/backup.py` bloc D, puis `python3 G/misc.py` pour la capture.
- attendu: message d'échec en français, en rouge, compréhensible (« Fichier illisible : ce n'est pas une sauvegarde ChessLocal. »).
  Retour visuel après un export réussi (chess.com affiche un toast).
- observé: texte brut : `Unexpected token 'b', "bonjour, j"... is not valid JSON`.
  JSON tronqué : `Expected ',' or '}' after property value in JSON at position 40 (line 1 column 41)`.
  JSON `null` : `Cannot read properties of null (reading '_app')`.
  Clés en conflit : `games.bulkAdd(): 1 of 2 operations failed. Errors: ConstraintError: Key already exists in the object store.`.
  Tous affichés avec la classe `text-accent` (vert, `rgb(129, 182, 76)`), la même couleur que le succès.
  Point positif : dans tous ces cas les données existantes sont préservées (transaction Dexie annulée).
  Export : le fichier `chesslocal-sauvegarde-2026-09-18.json` est bien téléchargé mais l'écran ne change pas du tout.
  L'input fichier n'est jamais remis à zéro : re-sélectionner le même fichier après un échec ne déclenche plus `onChange` (déduit du code).
- capture: SHOTS/restore_error_green_english.png
- cause probable: `src/pages/Stats.tsx:152-154` affiche `err.message` tel quel ; `src/pages/Stats.tsx:159` couleur unique `text-accent` ; `src/lib/backup.ts:28` `JSON.parse` non protégé ; `src/pages/Stats.tsx:129` pas de message après export.
- correctif proposé: dans `importBackup`, entourer `JSON.parse` d'un try/catch qui lève « Fichier illisible : ce n'est pas un JSON valide. », vérifier `data && typeof data === 'object'`, et convertir les erreurs Dexie en « Sauvegarde corrompue (table games), rien n'a été modifié. ».
  Dans `Stats.tsx`, état `{ kind: 'ok' | 'err', text }` rendu en `text-accent` ou `text-red-400`, `e.target.value = ''` en fin de `onChange`, message « Sauvegarde exportée (10 parties). » après export.

## GLOB-5 - Tablette portrait (768 à 1023 px) : échiquier rogné à gauche et panneau latéral hors écran sur /analyse et /jouer en partie
- type: bug
- sévérité: majeur
- page: /analyse, /jouer (partie en cours) ; viewport: 820x1180
- statut: reproduit
- repro: `python3 G/envelope.py tab820x1180` puis `python3 G/misc.py` (bloc 5).
- attendu: sur iPad portrait, board entier visible et panneau (coups, moteur, actions) accessible, comme l'app iPad chess.com qui empile board puis panneau.
- observé: /analyse : `main` fait 644 px (820 - nav 176), le contenu en demande 835 (`mainOverflowX = 191`).
  Le board va de x=25 à x=665 alors que `main` commence à x=176 : la colonne a et la moitié de la colonne b sont masquées sous la nav, inaccessibles même en scrollant (débordement négatif d'un `justify-center`).
  Le panneau Stockfish, la liste de coups et les boutons sont coupés à droite (bord droit à 1011 px pour un viewport de 820).
  /jouer en partie : board de x=119 à x=759 (57 px sous la nav), noms des joueurs tronqués (« ...(1300) »), panneau de droite presque entièrement hors écran.
- capture: SHOTS/env_tab820x1180_analyse.png, SHOTS/ingame_tab820x1180_jouer.png
- cause probable: `src/pages/Analysis.tsx:599` passe en `md:flex-row md:justify-center` dès 768 px alors que board `md:w-[min(76vh,640px)]` (`Analysis.tsx:631`) + panneau `md:w-96` (`Analysis.tsx:665`) + barre d'éval demandent environ 1080 px, plus 176 px de nav (`src/App.tsx:26`).
  Même schéma dans `src/pages/Play.tsx:517` (`md:w-[min(56vh,520px)]` borné par la hauteur seulement).
- correctif proposé: basculer la mise en page deux colonnes (et la nav latérale) à `lg:` (1024 px) au lieu de `md:`, ou borner le board par la largeur disponible : `md:w-[min(76vh,640px,calc(100vw-176px-384px-5rem))]`.
  Remplacer `md:justify-center` par `md:justify-start` + `mx-auto` sur le contenu pour qu'un débordement reste atteignable.

## GLOB-6 - /rush et /import : aucun onglet actif et aucun moyen de revenir en PWA standalone
- type: ux
- sévérité: majeur
- page: /rush, /import ; viewport: 393x852 standalone
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (bloc BACK) et `python3 G/envelope.py m393x852`.
  Accueil, toucher la tuile « Puzzle Rush », puis chercher comment revenir à l'accueil.
- attendu: chess.com mobile : tout écran secondaire a un chevron retour en haut à gauche et l'onglet parent reste allumé (Puzzle Rush garde l'onglet Problèmes actif).
- observé: sur /rush et /import, `nav a[aria-current="page"]` est vide : aucun onglet allumé, l'utilisateur ne sait plus où il est.
  Aucun lien ni bouton de retour dans `main` (0 élément « Retour », « ← », « ‹ »).
  Le retour navigateur fonctionne (`go_back` revient bien à `#/`), mais une PWA iOS standalone n'a pas de bouton retour ; seul le geste bord d'écran existe, et il est invisible.
  Même constat pour les états profonds de /rush (partie en cours) : seul « Arrêter » permet de sortir.
- capture: SHOTS/nav_rush_no_back.png, SHOTS/env_m393x852_import.png
- cause probable: `src/App.tsx:12-20` : `NAV` ne connaît ni `/rush` ni `/import`, et `NavLink` ne matche que sa propre route.
  `src/pages/PuzzleRush.tsx:109-110` et `src/pages/Import.tsx:89-90` n'ont pas d'en-tête avec retour.
- correctif proposé: ajouter dans `NAV` un champ `match: ['/puzzles', '/rush']` (et `['/analyse', '/import']`) et calculer l'état actif avec `useLocation()` plutôt qu'avec `NavLink.isActive`.
  Créer un composant `PageHeader({ title, back })` avec un chevron 44x44 px (`navigate(-1)` avec repli sur la route parente) et l'utiliser sur /rush, /import et les écrans profonds.

## GLOB-7 - Route inconnue : page blanche
- type: bug
- sévérité: mineur
- page: /#/nimporte ; viewport: tous
- statut: reproduit
- repro: `python3 G/envelope.py` ; ouvrir `http://localhost:5199/#/nimporte`.
- attendu: redirection vers l'accueil, ou écran « Page introuvable » avec un bouton « Accueil ».
- observé: `main` totalement vide (0 caractère), aucun onglet actif, 2 warnings console `No routes matched location "/nimporte"`.
  Concerne aussi tout ancien lien partagé ou raccourci iOS mal saisi (`#/imports?url=...`).
- capture: SHOTS/env_m393x852_nimporte.png
- cause probable: `src/App.tsx:48-58` : pas de `<Route path="*">`.
- correctif proposé: ajouter `<Route path="*" element={<Navigate to="/" replace />} />` en dernière route.

## GLOB-8 - Paysage iPhone (852x393) : le layout desktop s'active, le titre de l'accueil est coupé et inatteignable
- type: bug
- sévérité: mineur
- page: / et /analyse ; viewport: 852x393
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (bloc PAYSAGE) et `python3 G/envelope.py land852x393`.
- attendu: en paysage téléphone, tout le contenu reste atteignable ; chess.com verrouille le portrait hors échiquier.
  iOS ignore `orientation` du manifest, donc la PWA pivote librement.
- observé: à 852 px de large le breakpoint `md` (768) active la nav latérale et les mises en page desktop sur 393 px de haut.
  Accueil : `h1` mesuré à `top=-51, bottom=-15` avec `scrollTop` minimum 0 : le titre est entièrement hors écran et on ne peut pas scroller vers lui ; le CTA « Jouer » est sous la ligne de flottaison (bottom=457 pour 393 de haut).
  /analyse : panneau droit débordant de 4 px (« Copier PGN » et le bouton retourner coupés), bouton « Bilan de partie » écrasé sur 3 lignes.
  Board à 37 px par case (296 px) sur /puzzles, /analyse et /jouer.
- capture: SHOTS/env_land852x393_home.png, SHOTS/env_land852x393_analyse.png
- cause probable: `src/pages/Home.tsx:35` : `h-full` + `md:justify-center` sur une colonne plus haute que son conteneur : le débordement haut d'un flex centré n'est pas scrollable.
  Breakpoints uniquement en largeur (`md:`) dans `src/App.tsx:26,60`.
- correctif proposé: `Home.tsx:35` : remplacer `h-full` par `min-h-full` (le conteneur grandit avec son contenu et le centrage ne rogne plus).
  Dans `src/index.css`, définir une variante `@custom-variant desk (@media (min-width: 768px) and (min-height: 500px));` et l'utiliser à la place de `md:` pour la nav latérale et les layouts deux colonnes.

## GLOB-9 - Barre d'onglets : 7 onglets à 10 px, libellés collés à 320 px, icônes hétérogènes
- type: ux
- sévérité: mineur
- page: toutes ; viewport: 393x852 et 320x568
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (blocs TABS) et `python3 G/misc.py` (zoom).
- attendu: chess.com mobile et les HIG Apple plafonnent à 5 onglets, libellés d'environ 10 à 11 pt avec de l'air entre eux, pictos d'une même famille.
- observé: 393 px : 7 onglets de 56,1 x 47 px (cible OK, >= 44), police 10 px ; « Apprendre » occupe 50 px sur 56 (3 px de marge de chaque côté).
  320 px : onglets de 45 px, « Apprendre » fait 50 px et force son onglet à 50 px (largeurs inégales 45/50), marge nulle : on lit « PuzzlesApprendreAnalyse » d'un bloc.
  Les deux premiers onglets utilisent des glyphes texte (U+265E, U+265F) rendus en gris et plus petits que les 5 emojis couleur suivants : la barre paraît déséquilibrée et l'onglet actif « Accueil » ressort à peine.
  Hauteur de barre 48 px (chess.com : environ 56 px hors safe area).
- capture: SHOTS/tabbar_320_zoom.png, SHOTS/tabbar_393_zoom.png
- cause probable: `src/App.tsx:12-20` (7 entrées, icônes mixtes) et `src/App.tsx:67` (`text-[10px]`, `flex-1` sans `min-w-0`).
- correctif proposé: passer à 5 onglets : Accueil, Jouer, Puzzles, Apprendre, Plus.
  « Plus » ouvre une feuille avec Analyse, Archive, Stats et réglages, Import chess.com (ou les regrouper dans un écran « Profil » comme chess.com).
  Remplacer les emojis par un jeu de pictos SVG monochromes (`currentColor`) pour que l'état actif colore aussi l'icône.
  À défaut : `min-w-0` + `truncate` sur les libellés et `text-[11px]`.

## GLOB-10 - Stats : « 1 parties » et « 0 parties », incohérent avec l'accueil
- type: bug
- sévérité: mineur
- page: /stats ; viewport: tous
- statut: reproduit
- repro: `python3 G/home_stats.py` (classement bullet injecté avec `games: 1`).
- attendu: « 1 partie », « 0 partie » (en français 0 et 1 sont au singulier ; l'accueil écrit déjà « 0 partie »).
- observé: carte Bullet : « Bullet · 1 parties ». État vierge : « 0 parties », « 0 essais », alors que la tuile Archive de l'accueil affiche « 0 partie ».
- capture: SHOTS/stats_populated_393x852_top.png, SHOTS/env_m393x852_stats_full.png
- cause probable: `src/pages/Stats.tsx:46` : pluriel codé en dur ; `src/pages/Home.tsx:30` gère le singulier.
- correctif proposé: helper partagé `plural(n, 'partie')` dans `src/lib/` (singulier si `n < 2`) utilisé par `Home.tsx:30`, `Stats.tsx:46`, `Stats.tsx:57-59` et `Stats.tsx:72`.

## GLOB-11 - Stats incomplètes : classement Illimité invisible, records Rush et niveaux Apprendre absents, aucun graphe
- type: ux
- sévérité: mineur
- page: /stats et / ; viewport: tous
- statut: reproduit
- repro: `python3 G/home_stats.py` (injection de `ratings.unlimited = 822`, 4 scores Rush, `learn-endgame = 850`, `learn-tactic = 905`).
- attendu: l'écran Stats de chess.com montre chaque cadence jouée, une courbe d'évolution, le record Puzzle Rush.
  Tout ce que l'app calcule et stocke doit être visible quelque part.
- observé: bilan V/N/D exact : 3 gagnées, 2 nulles, 2 perdues pour 7 parties bot, barre à 42,9 / 28,6 / 28,6 % ; les 3 parties « 2 joueurs » sont bien exclues ; victoire avec les Noirs et nulles correctement comptées ; « 8 résolus / 12 tentés (67 %) » exact.
  Mais « 822 » n'apparaît ni sur l'accueil ni sur Stats alors que `Play.tsx:201` classe bien les parties « Illimité » (la partie illimitée gagnée compte dans le V/N/D mais son classement est invisible).
  Aucune mention des records Rush (14 / 21 / 17) ni des 4 classements Apprendre.
  `playerRatingAfter` est stocké sur chaque partie mais aucune courbe ne l'exploite.
  Le bilan V/N/D n'est pas ventilé par cadence.
  Le pseudo chess.com, pourtant un réglage du store (`chesscomUsername`), n'est pas éditable dans Réglages : son seul point d'écriture est `Import.tsx:99-111`, sur une route sans onglet (GLOB-6).
- capture: SHOTS/stats_populated_393_full.png
- cause probable: `src/pages/Stats.tsx:27-32` : liste `cats` limitée à 4 clés ; `db.rushScores` et les clés `learn-*` ne sont pas lues.
- correctif proposé: ajouter la carte « Illimité » quand `games > 0`, une ligne « Puzzle Rush : 14 / 21 / 17 », un bloc « Apprendre » (4 classements), et une sparkline par cadence à partir de `games.playerRatingAfter` trié par date (un composant SVG de 30 lignes suffit, `EvalGraph.tsx` peut servir de base).
  Ajouter dans la carte Réglages un champ « Pseudo chess.com » branché sur `setChesscomUsername`.

## GLOB-12 - Accueil : pas de série ni de progression, « 800 » affiché pour des cadences jamais jouées
- type: ux
- sévérité: mineur
- page: / ; viewport: 393x852
- statut: reproduit
- repro: `python3 G/envelope.py m393x852` (vierge) et `python3 G/home_stats.py` (peuplé).
- attendu: accueil chess.com : série quotidienne (flamme + nombre de jours), problème du jour, reprise de la dernière activité ; une cadence jamais jouée affiche « - » ou « Non classé ».
- observé: chiffres justes à l'état peuplé (8 résolus, classement 1034, 781 / 868 / 803 / 1034, « 10 parties ») et tous les CTA mènent au bon endroit (9 vérifiés).
  Mais aucune gamification : ni série de jours, ni progression du jour, ni delta de classement ; la seule « flamme » de l'app est la série de session de `Puzzles.tsx:17`, remise à zéro à chaque visite.
  État vierge : quatre « 800 » identiques, qui laissent croire à un classement établi.
  Les 4 cartes de classement mènent toutes à /stats sans ancre.
  393x852 : 268 px de vide mesurés entre le bas des tuiles (y=460) et le haut du CTA « Jouer » (y=728).
- capture: SHOTS/env_m393x852_home.png, SHOTS/home_populated_393x852.png
- cause probable: `src/pages/Home.tsx:18` : `ratings[key] ?? DEFAULT_RATING` ne distingue pas « jamais joué » ; aucune lecture de `date` dans `puzzleAttempts`, `games`, `learnSessions`.
- correctif proposé: calculer une série de jours consécutifs à partir des dates de `games`, `puzzleAttempts` et `learnSessions` (fonction pure dans `src/lib/streak.ts`) et l'afficher en tête (« 🔥 4 jours »).
  Afficher « - » quand `ratings[key]` est absent.
  Utiliser l'espace vide pour une carte « Reprendre » (dernière partie à analyser, erreurs en attente : `mistakes.solved = 0`).

## GLOB-13 - Contrastes : text-neutral-500 et text-neutral-600 sous le seuil AA, blanc sur accent à 2,41:1
- type: a11y
- sévérité: majeur
- page: toutes ; viewport: tous
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (bloc CONTRASTES, couleurs lues par `getComputedStyle` puis rendues sur canvas).
- attendu: WCAG AA : 4,5:1 pour le texte courant, 3:1 pour le texte large (>= 24 px ou 18,66 px gras).
- observé: `text-neutral-400` (161,161,161) : 5,99 sur `#262421`, 5,22 sur `#312e2b`, 4,44 sur `#3c3936` : OK sauf sur surface-3 (limite).
  `text-neutral-500` (115,115,115) : 3,26 sur `#262421`, 2,85 sur `#312e2b`, 2,42 sur `#3c3936` : échec partout ; 21 occurrences dans `src/`, dont les aides de réglages (`Stats.tsx:121,160`), les placeholders d'Import (`Import.tsx:103,120`), la couleur jouée dans Archive (`Archive.tsx:59`), le compteur « 1/3 » d'Apprendre (`Learn.tsx:238`).
  `text-neutral-600` (82,82,82) : 1,98 sur `#262421`, 1,73 sur `#312e2b` : quasi illisible ; horodatage de build (`Import.tsx:187`, 10 px) et « 100 % local · SF 18 » (`App.tsx:45`, 11 px).
  Blanc sur `#81b64c` (tous les CTA) : 2,41:1, sous le seuil même pour du texte large.
  `text-red-400` : 4,67 sur surface-2 (OK), `text-accent` : 5,61 (OK).
- capture: SHOTS/env_m393x852_stats_full.png (textes d'aide), SHOTS/env_m320x568_import.png (horodatage)
- cause probable: usage direct de la palette Tailwind neutre sans jeton « texte secondaire » validé sur les surfaces de `src/index.css:4-6`.
- correctif proposé: déclarer dans `@theme` un jeton `--color-muted` égal ou plus clair que neutral-400 (`#a1a1a1`, mesuré à 5,22:1 sur surface-2), remplacer `text-neutral-500` par `text-muted` et proscrire `text-neutral-600` pour du texte.
  CTA : foncer le fond du bouton ou passer le libellé en vert très foncé, puis re-mesurer avec le bloc CONTRASTES de `G/nav_a11y.py` jusqu'à dépasser 4,5:1 (3:1 au minimum pour les CTA en 18 px gras et plus).

## GLOB-14 - Réglages : interrupteurs sans nom accessible, états non exposés, cibles sous 44 px
- type: a11y
- sévérité: mineur
- page: /stats (et /import) ; viewport: 393x852
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (bloc CIBLES).
- attendu: cibles >= 44x44 px (HIG), interrupteurs en `role="switch"` avec `aria-checked` et libellé, choix exclusifs avec `aria-pressed` ou radiogroup.
- observé: 11 cibles sous 44 px sur /stats : toggles 44x24, pastilles de thème 68x36, boutons de profondeur 75 à 87 x 36, « Exporter tout » 130x32, « Restaurer » 108x32.
  /import : champ pseudo 241x40 et bouton « Connecter » 112x40.
  Les deux toggles n'ont ni texte, ni `aria-label`, ni `role`, ni `aria-checked` : VoiceOver annonce « bouton » sans nom ni état.
  Pastilles de thème : nom uniquement via `title`, aucun état sélectionné exposé ; boutons de profondeur : sélection uniquement visuelle (bordure).
  Toutes les autres routes : 0 cible sous 44 px hors nav.
- capture: SHOTS/env_m393x852_stats_full.png
- cause probable: `src/pages/Stats.tsx:170-181` (composant `Toggle`), `Stats.tsx:84-94` (pastilles), `Stats.tsx:110-118`, `Stats.tsx:128-139` (`py-1.5 text-sm`).
- correctif proposé: `Toggle` : `<button role="switch" aria-checked={value} aria-label={label} className="... h-8 w-14 ...">` et rendre toute la ligne cliquable (`<label>` englobant, hauteur min 44 px).
  Pastilles : `aria-label={t.name}` + `aria-pressed`, taille `h-11 w-11` par demi-case.
  Boutons secondaires de réglages : `min-h-11 px-4`.

## GLOB-15 - Import : focus clavier invisible sur les champs
- type: a11y
- sévérité: mineur
- page: /import ; viewport: 1440x900
- statut: reproduit
- repro: `python3 G/nav_a11y.py` (bloc TAB ORDER /import).
- attendu: anneau de focus visible sur tout élément focalisable (les autres contrôles de l'app gardent l'anneau natif `auto 1px`).
- observé: champ pseudo focalisé : `outline: none 0px`, aucun `box-shadow`, `:focus-visible` vrai : rien n'indique le focus.
  Ordre de tabulation par ailleurs logique sur /, /stats, /import (nav latérale puis contenu dans l'ordre visuel), anneau natif présent partout ailleurs.
  Pas de lien d'évitement : 7 tabulations de nav avant le contenu sur desktop.
- capture: SHOTS/focus_import_input_desktop.png
- cause probable: `src/pages/Import.tsx:103` et `Import.tsx:120` : classe `outline-none` sans style de remplacement.
- correctif proposé: remplacer `outline-none` par `outline-none focus-visible:ring-2 focus-visible:ring-accent`.

## GLOB-16 - Titre de document identique sur toutes les routes, avec un tiret cadratin
- type: ux
- sévérité: mineur
- page: toutes ; viewport: tous
- statut: reproduit
- repro: `python3 G/envelope.py` : `document.title` relevé sur les 10 routes x 7 viewports.
- attendu: « Jouer - ChessLocal », « Statistiques - ChessLocal », etc. : utile pour l'historique, le sélecteur d'apps iOS, les lecteurs d'écran (annonce de changement de page) et les onglets desktop.
- observé: 70 relevés sur 70 : « ChessLocal [tiret cadratin] échecs 100 % local ».
  Aucun `document.title` dans `src/`.
- capture: aucune (valeur relevée dans `G/envelope_results.json`)
- cause probable: `index.html:16` titre statique ; aucun effet de titre dans `src/App.tsx`.
- correctif proposé: petit composant `<TitleSync />` dans `HashRouter` : `useLocation()` + table route -> titre, puis `document.title = titre + ' - ChessLocal'`.
  Remplacer le tiret cadratin de `index.html:16` par un tiret simple.

## GLOB-17 - Horodatage de build : visible uniquement en bas de /import, en UTC non signalé, à 1,98:1 de contraste
- type: pwa
- sévérité: mineur
- page: /import, /stats ; viewport: tous
- statut: reproduit
- repro: `python3 G/pwa.py` (dernier bloc) : recherche de « build 20 » sur /, /stats, /import.
- attendu: chess.com affiche sa version en bas des réglages.
  L'utilisateur qui veut vérifier la mise à jour de sa PWA va dans Stats > Réglages, pas dans l'import chess.com.
- observé: présent sur /import seulement (`{'/': False, '/stats': False, '/import': True}`), route sans onglet (voir GLOB-6).
  Valeur « build 2026-09-18 16:22 » pour un build écrit à 19:22 heure locale de la machine : c'est de l'UTC (`toISOString`) sans mention, donc plusieurs heures d'écart apparent.
  Texte en 10 px `text-neutral-600` (contraste 1,98:1).
  `registerType: 'autoUpdate'` sans `virtual:pwa-register` : le nouveau service worker s'active seul (`skipWaiting` + `clientsClaim` présents dans `dist/sw.js`) mais la page ouverte n'est ni rechargée ni prévenue (déduit du code).
- capture: SHOTS/offline_import_deeplink.png (bas de page)
- cause probable: `src/pages/Import.tsx:187` seul usage de `__BUILD__` ; `vite.config.ts:11` format UTC.
- correctif proposé: déplacer (ou dupliquer) la ligne en bas de la carte Réglages de `Stats.tsx` : « Version du 18/09/2026 19:22 » via `new Date(__BUILD__).toLocaleString('fr-FR')` (stocker l'ISO complet dans `vite.config.ts:11`), en `text-neutral-400`.
  Ajouter un bouton « Rechercher une mise à jour » qui appelle `registration.update()` puis `location.reload()`.

## GLOB-18 - Import hors ligne par lien profond : erreur technique brute, doublon de messages, URL qui déborde
- type: bug
- sévérité: mineur
- page: /import?url=... ; viewport: 393x852, hors ligne
- statut: reproduit
- repro: `python3 G/pwa.py` (bloc import) : pseudo enregistré, `ctx.set_offline(True)`, ouvrir `/#/import?url=https%3A%2F%2Fwww.chess.com%2Fgame%2Flive%2F123456789`.
- attendu: un seul message propre, identique au chemin manuel : « Pas de connexion : l'import chess.com nécessite internet. ».
- observé: le chemin manuel est propre (message rouge en français).
  Le chemin lien profond affiche en plus, dans un encart gris : « Requête chess.com impossible (TypeError: Failed to fetch) [tiret cadratin] https://api.chess.com/pub/player/hikaru/games/archives ».
  L'URL n'a pas de point de césure et touche le bord droit de l'encart.
  Deux messages d'erreur simultanés pour la même cause.
  Le placeholder du champ lien est tronqué à 393 px : « ...ou colle un lien de partie (Partager -> Cc ».
- capture: SHOTS/offline_import_deeplink.png, SHOTS/offline_import.png
- cause probable: `src/pages/Import.tsx:57` : `.catch((e) => setDeepLinkStatus(e.message))` sans le test `navigator.onLine` de `Import.tsx:41` ; `src/lib/chesscom.ts:22` construit un message technique avec l'URL.
- correctif proposé: factoriser `friendlyError(e)` (test `navigator.onLine`, sinon message court sans URL) et l'utiliser dans `loadGames`, `handleLink` et l'effet du lien profond.
  Garder le détail technique en `console.warn`.
  Placeholder raccourci : « ou colle le lien d'une partie ».

## GLOB-19 - Petits écrans (320 px) : boutons rognés ou collés au bord
- type: bug
- sévérité: cosmétique
- page: /import, /stats, / ; viewport: 320x568
- statut: reproduit
- repro: `python3 G/envelope.py m320x568`.
- attendu: aucun élément coupé ; marges internes des cartes respectées.
- observé: `overflow_x` du document = 0 sur les 70 combinaisons route x viewport.
  Mais /import : `main.scrollWidth - clientWidth = 13`, le bouton « Connecter » se termine à x=333 pour 320 px de large : libellé coupé.
  /stats : le bouton « Profond » dépasse le padding droit de la carte Réglages ; « Exporter tout » et « Restaurer » passent sur deux lignes.
  / : le bouton « Résolvez ! » touche le bord droit de la carte verte (padding de 20 px consommé).
- capture: SHOTS/env_m320x568_import.png, SHOTS/env_m320x568_stats_full.png, SHOTS/env_m320x568_home.png
- cause probable: `src/pages/Import.tsx:98-111` : `flex gap-2` sans `min-w-0` sur l'input (un input a une largeur intrinsèque d'environ 20 caractères).
  `src/pages/Stats.tsx:102` : `flex gap-2` sans `flex-wrap`.
  `src/pages/Home.tsx:45-54` : `shrink-0` sur le bouton et texte long à gauche.
- correctif proposé: `min-w-0` sur les deux inputs d'Import ; `flex-wrap` sur les groupes de boutons de Stats ; sur la carte Problèmes, `flex-wrap` ou `text-base px-4` sous 360 px.

## GLOB-20 - Coordonnées de l'échiquier aux couleurs du thème « Bois » quel que soit le thème choisi
- type: bug
- sévérité: cosmétique
- page: toutes les pages avec échiquier ; viewport: tous
- statut: reproduit
- repro: `python3 G/home_stats.py` : thème Améthyste, puis /puzzles, /analyse, /rush, /jouer, feuille de cours.
- attendu: chess.com : les coordonnées prennent la couleur de la case opposée du thème actif.
- observé: le thème est bien appliqué partout (case a1 = `rgb(136, 119, 183)` sur puzzles, analyse, rush, jouer et diagramme de cours ; persistance après rechargement vérifiée pour les 4 réglages).
  Mais chiffres et lettres restent `#B58863` / `#F0D9B5` (brun et crème du thème Bois) sur fond violet, vert ou bleu : teinte étrangère et faible contraste sur les cases claires.
- capture: SHOTS/theme_purple_course.png, SHOTS/theme_purple_puzzles.png
- cause probable: `src/components/Board.tsx:144-145` ne passe que `darkSquareStyle` / `lightSquareStyle` ; react-chessboard garde ses défauts (`node_modules/react-chessboard/dist/index.esm.js:4767-4772`).
- correctif proposé: ajouter dans les options : `darkSquareNotationStyle: { color: theme.light }, lightSquareNotationStyle: { color: theme.dark }`.

## GLOB-21 - PWA : icônes avec encoches transparentes, doublons dans le précache, pas d'écran de lancement iOS
- type: pwa
- sévérité: cosmétique
- page: manifest / build ; viewport: n/a
- statut: reproduit
- repro: analyse de `dist/` (sips + PIL) ; zoom des coins composé sur fond magenta.
- attendu: icône `any` et `apple-touch-icon` pleinement opaques et carrées (iOS et Android appliquent leur propre masque) ; une entrée de précache par URL.
- observé: tailles correctes et non déformées (192x192, 512x512, 512x512 maskable, apple-touch 180x180), cavalier centré et nettement à l'intérieur de la zone sûre du maskable.
  `pwa-512.png` : 4314 pixels totalement transparents, `apple-touch-icon.png` : 649 : coins pré-arrondis mal découpés, la case claire du coin reste carrée et laisse une encoche transparente à côté.
  iOS remplit la transparence en noir ; l'encoche tombe en grande partie sous le masque iOS, mais elle est visible sur un lanceur Android ou un onglet desktop.
  `pwa-512-maskable.png` est propre (aucune encoche).
  `dist/sw.js` liste 24 entrées pour 21 URL : `pwa-192.png`, `pwa-512.png`, `pwa-512-maskable.png` en double (même révision, donc sans erreur : 21 entrées en cache mesurées).
  Aucun `apple-touch-startup-image` (0 balise mesurée).
- capture: SHOTS/icons_corner_zoom.png
- cause probable: génération des PNG dans `public/` ; `vite.config.ts:20` : le glob `png` inclut déjà les icônes que `vite-plugin-pwa` ajoute via `includeManifestIcons`.
- correctif proposé: régénérer `pwa-192.png`, `pwa-512.png` et `apple-touch-icon.png` à partir du maskable (carré plein, sans coins arrondis ni alpha).
  `includeManifestIcons: false` dans `VitePWA({...})`.

## GLOB-22 - /jouer : le CTA « Jouer » est sous la ligne de flottaison sur iPhone 14 Pro, et la cadence s'affiche en anglais
- type: ux
- sévérité: mineur
- page: /jouer ; viewport: 393x852 (et 393x660, 320x568)
- statut: reproduit
- repro: `python3 G/envelope.py m393x852` : `main.scrollHeight - clientHeight = 172` sur /jouer ; `python3 G/misc.py` pour le libellé.
- attendu: chess.com garde le bouton « Jouer » collé en bas de l'écran de configuration, toujours visible.
  Parcours principal de l'app : Accueil > « Jouer » > « Jouer ».
- observé: il faut scroller de 172 px (364 px en onglet Safari 393x660, 532 px à 320x568) pour atteindre le bouton.
  Libellé : « Mon classement rapid : 781 » (clé technique `timeClass`, donc aussi « unlimited ») alors que le reste de l'app dit « Rapide », « Illimité ».
- capture: SHOTS/env_m393x852_jouer.png, SHOTS/env_m393x852_jouer_full.png
- cause probable: `src/pages/Play.tsx:381` : page en flux normal, CTA en fin de contenu ; `src/pages/Play.tsx:450` interpole `tc.timeClass` (clé technique).
- correctif proposé: envelopper le CTA dans `<div className="sticky bottom-0 bg-surface pt-2 pb-3">` ; table `TIME_CLASS_LABEL = { bullet: 'Bullet', blitz: 'Blitz', rapid: 'Rapide', unlimited: 'Illimité' }` partagée avec `Stats.tsx` et `Home.tsx`.

## GLOB-23 - Zoom désactivé et marges de sécurité latérales absentes
- type: a11y
- sévérité: mineur
- page: toutes ; viewport: iPhone
- statut: déduit du code
- repro: lecture de `index.html:6-9` et `src/index.css:30-38`.
- attendu: ne pas interdire le zoom utilisateur (WCAG 1.4.4) ; en `viewport-fit=cover`, tenir compte des 4 marges de sécurité.
- observé: `maximum-scale=1.0, user-scalable=no` interdit le pincement pour zoomer (textes à 10 et 12 px par ailleurs).
  Seules `safe-area-inset-top` et `safe-area-inset-bottom` sont gérées : en paysage (la PWA iOS pivote, voir GLOB-8) la nav latérale de 176 px passerait sous l'encoche ou la Dynamic Island.
- capture: aucune (`env(safe-area-inset-*)` vaut 0 en émulation)
- cause probable: `index.html:8` ; `src/index.css:30-38` ; `src/App.tsx:25`.
- correctif proposé: retirer `maximum-scale` et `user-scalable=no`, et mettre `touch-action: manipulation` sur `body` (supprime le double-tap zoom sans bloquer le pincement).
  Ajouter `padding-left: env(safe-area-inset-left); padding-right: env(safe-area-inset-right)` sur le conteneur racine de `App.tsx:25`.

## GLOB-24 - Cohérence visuelle transverse : mesures, mini design system et écarts priorisés
- type: ux
- sévérité: mineur
- page: toutes ; viewport: 393x852
- statut: reproduit
- repro: `python3 G/misc.py` (bloc COHÉRENCE : styles calculés du `h1`, du conteneur de page, des rayons et des polices de boutons, route par route).
- attendu: une seule grammaire visuelle d'un écran à l'autre, comme chess.com (titres, marges, cartes et boutons identiques partout).
- observé: mesures à 393 px :
  - Titres `h1` : / 30 px / 900 ; /apprendre 24 px / 900 ; /jouer, /rush, /archive, /stats, /import 24 px / 700 ; /puzzles et /analyse sans `h1`.
    Emoji devant le titre sur /, /rush, /apprendre, /import, pas sur /jouer, /archive, /stats.
  - Marge latérale de page : 16 px (/, /apprendre, /import), 24 px (/jouer, /archive, /stats), 32 px (/rush), 8 px (/puzzles, /analyse) : le bord gauche du contenu saute de 16 à 24 à 32 px en changeant d'onglet.
  - Rayons des cartes : 12 px (/, /apprendre), 8 px (/jouer, /stats, /rush), 4 px (/archive, /import, /analyse) ; carte Problèmes 16 px.
  - Boutons primaires : deux styles concurrents.
    `Cta` (`src/components/Cta.tsx` : `rounded-xl`, `font-black`, ombre 3D) sur /, /jouer, /apprendre, /puzzles.
    Bouton plat `rounded bg-accent font-bold` codé à la main dans `Import.tsx:108`, `Play.tsx:610`, `Analysis.tsx:801`, `Analysis.tsx:899`.
  - Boutons secondaires : `Cta variant="secondary"` d'un côté, `rounded bg-surface-3 px-3 py-1.5 text-sm` (32 à 36 px de haut) de l'autre (`Stats.tsx:130,136`, `Archive.tsx:41,74`, `Import.tsx:125`).
  - Sélection : bordure verte 2 px (/jouer, /stats) contre fond `accent/20` (nav desktop) contre couleur de texte seule (nav mobile).
  - Icônes : emojis partout, avec collisions de sens : ⚡ = Blitz et Puzzle Rush (deux tuiles voisines de l'accueil) ; ♟ = onglet Jouer, tuile chess.com, titre d'Import et bouton chess.com d'Analyse ; 🧩 deux fois sur l'accueil ; 📚 = Archive, bot Iris et en-tête de cours ; 🎓 = Apprendre et mode Entraîneur ; 🔍 = Analyse et Bilan.
    ♞ et ♟ sont des glyphes texte gris, les autres des emojis couleur.
  - Vocabulaire : « Problèmes » (carte de l'accueil) contre « Puzzles » (onglet, carte de classement, Stats, Rush) sur le même écran.
    « Stats » (onglet) contre « Statistiques » (titre).
    « Mon classement rapid » (clé anglaise) contre « Rapide ».
  - Ton : tutoiement partout (« Importer tes parties », « Va jouer ! », « Trouve le meilleur coup ») sauf le bouton « Résolvez ! » de l'accueil (2e personne du pluriel).
  - Ponctuation : tiret cadratin dans 7 textes d'interface (`index.html:16`, `Import.tsx:41,72`, `Learn.tsx:372,548,632,699`) et dans 2 messages d'erreur (`chesscom.ts:22,29`), alors que le reste utilise « · », « : » ou le tiret simple (`Stats.tsx:122`).
    Espaces simples avant « : », « ! », « % » : retours à la ligne orphelins possibles (« 100 » / « % »).
  - Actions destructives sans confirmation ni annulation : restauration (GLOB-1), suppression d'une partie dans Archive (`Archive.tsx:24-27`, bouton « ✕ » sans libellé accessible), abandon d'une séance Apprendre (`Learn.tsx:232`).
  - Desktop : l'accueil est centré verticalement (`Home.tsx:35` `md:justify-center`), toutes les autres pages sont calées en haut ; sur tablette le titre de l'accueil démarre vers le milieu de l'écran.
- capture: SHOTS/env_m393x852_home.png, SHOTS/env_m393x852_jouer_full.png, SHOTS/env_m393x852_rush.png, SHOTS/env_m393x852_apprendre.png, SHOTS/env_m393x852_archive.png, SHOTS/env_m393x852_stats_full.png, SHOTS/env_m393x852_import.png, SHOTS/env_tab820x1180_home.png
- cause probable: pas de composants de mise en page partagés : chaque page recompose conteneur, titre, cartes et boutons avec des classes Tailwind locales ; seul `Cta.tsx` est mutualisé et il n'est pas utilisé partout.
- correctif proposé: mini design system en 6 règles, chacune portée par un composant ou un jeton :
  1. `Page` : un seul conteneur `mx-auto max-w-2xl px-4 pt-4 pb-6 md:px-6` pour toutes les pages de contenu ; les pages à échiquier gardent `px-2` mais alignent leur en-tête sur 16 px.
  2. `PageHeader` : `h1` unique `text-2xl font-black`, sans emoji (l'icône vit dans la nav), avec chevron retour optionnel 44x44 px (règle aussi GLOB-6). L'accueil garde son logo 30 px comme seule exception.
  3. `Card` : `rounded-xl bg-surface-2 p-4` partout (12 px) ; `rounded-lg` (8 px) pour les éléments à l'intérieur d'une carte ; plus de `rounded` 4 px hors échiquier.
  4. Boutons : uniquement `Cta` en 3 tailles (`lg` 56 px, `md` 44 px, `sm` 36 px réservé au desktop) et 3 variantes (`primary`, `secondary`, `danger`) ; hauteur minimale tactile 44 px ; supprimer les 4 boutons verts plats et les secondaires `py-1.5`.
  5. Couleurs de texte : trois jetons seulement, `text` (#e4e2e0), `muted` (>= 4,5:1 sur surface-2), `accent` ; `text-neutral-500/600` interdits (GLOB-13) ; état sélectionné unique : bordure accent 2 px + fond `accent/10`.
  6. Langue : tutoiement, vocabulaire figé dans un fichier `src/lib/labels.ts` (Puzzles, Rapide/Blitz/Bullet/Illimité, Statistiques), jamais de tiret cadratin (utiliser « : » ou « · »), espace insécable (U+00A0 ou U+202F) avant « : ; ! ? % », helper `plural()`.
  Écarts à corriger, par priorité :
  - P1 : marges latérales unifiées à 16 px (/jouer, /archive, /stats, /rush) et `h1` unifié : c'est ce qui se voit le plus en passant d'un onglet à l'autre.
  - P1 : remplacer les boutons verts plats par `Cta` (`Import.tsx:108`, `Play.tsx:610`, `Analysis.tsx:801,899`).
  - P2 : rayons à 12 px sur /jouer, /stats, /rush, /archive, /import.
  - P2 : « Problèmes » -> « Puzzles », « Résolvez ! » -> « Résoudre », libellés de cadence en français (GLOB-22), retrait des tirets cadratins.
  - P3 : pictos SVG monochromes pour la nav et les tuiles, une icône = un sens (GLOB-9).
  - P3 : confirmation ou annulation (« Partie supprimée · Annuler ») pour toute action destructive.

## Couverture
- Accueil vierge et peuplé : chiffres exacts (8 résolus, 1034, 781/868/803, 10 parties), 9 CTA vérifiés, tous mènent à la bonne route.
- Stats : V/N/D exact (3/2/2 sur 7 parties bot, parties locales exclues, victoire Noirs et nulles correctes), barre 42,9/28,6/28,6 %, 67 % puzzles.
- Réglages : thème, coups légaux, sons, profondeur écrits dans localStorage, persistés après rechargement, UI cohérente au retour ; thème appliqué sur /puzzles, /analyse, /rush, /jouer et diagramme de cours.
- Export : les 6 tables de `db.ts` sont dans `TABLES`, compteurs identiques aux données injectées, réglages inclus, nom de fichier daté ; restauration dans un contexte neuf : données et réglages reviennent après rechargement ; fichiers invalides (texte, JSON tronqué, null, tableau, autre app, clés en conflit) : données existantes préservées ; réglages corrompus dans la sauvegarde : l'app redémarre.
- Navigation : deep link et rechargement OK sur les 9 routes ; retour navigateur correct sur la chaîne des 7 onglets et depuis /rush et /import ; re-tap sur l'onglet actif ne pollue pas l'historique ; scroll remis à 0 entre onglets ; cibles de la barre d'onglets 56x47 px ; ordre de tabulation logique et anneau de focus natif présent (sauf GLOB-15).
- Responsive : `overflow_x = 0` sur 70 combinaisons (10 routes x 7 viewports) ; aucune erreur console, pageerror, requête en échec ou 404 en dehors des warnings de GLOB-7.
- PWA (build servi en 5198) : manifest complet (nom, `display: standalone`, `start_url` et `scope` relatifs, couleurs, 3 icônes aux bonnes tailles), balises iOS présentes (`apple-touch-icon`, `apple-mobile-web-app-*`, `viewport-fit=cover`), service worker activé, 21 entrées en précache dont WASM 7 Mo, `puzzles.json` 16 Mo, 6 sons, icônes (25,4 Mo).
- Hors ligne : démarrage, deep link + rechargement sur les 9 routes, puzzles chargés, Stockfish évalue dans Analyse, le bot répond dans Jouer, les 6 sons servis par le cache, import manuel : message français propre ; aucune requête en échec hors chess.com.

## Hypothèses non vérifiées
- Téléchargements en PWA iOS standalone : `backup.ts:16-24` et `Archive.tsx:13-22` utilisent un lien blob + `a.download` avec `revokeObjectURL` immédiat ; sur iOS cela peut ouvrir un aperçu plein écran sans retour, ou échouer. Non reproductible sous Chromium. Piste : `navigator.share({ files: [new File([json], nom)] })` avec repli sur le lien, et `revokeObjectURL` différé de quelques secondes.
- `navigator.storage.persist()` (`main.tsx:8`) : renvoie `false` en Chromium headless ; le comportement réel sur iOS n'a pas été observé. L'app n'affiche nulle part si la persistance est acquise ni la date de la dernière sauvegarde.
- Mise à jour : avec `autoUpdate` sans `virtual:pwa-register`, une PWA iOS reprise depuis l'arrière-plan peut rester longtemps sur l'ancien JS ; non testé faute de second build (interdit ici).
- Rendu iOS du glyphe U+265F (pion) : iOS peut le rendre en emoji couleur alors que U+265E (cavalier) reste un glyphe texte, ce qui accentuerait l'hétérogénéité de la barre d'onglets. Vu uniquement sous Chromium/macOS.
- Appui long sur les tuiles `<a>` de l'accueil : iOS peut afficher l'aperçu de lien natif dans une PWA faute de `-webkit-touch-callout: none` ; non vérifiable en émulation.
- Marges de sécurité : `env(safe-area-inset-*)` vaut 0 en émulation ; `pt-safe` / `pb-safe` n'ont été vérifiés qu'en lecture de code.
- Absence d'`apple-touch-startup-image` : flash blanc au lancement supposé, non observé.
- Parties du mode Entraîneur : enregistrées avec `mode: 'bot'` (`Play.tsx:213`), elles entrent dans le bilan V/N/D même quand elles sont non classées ; cohérence avec le compteur « N parties » des cartes non testée en jouant réellement.
- Avertissement console « The AudioContext was not allowed to start » relevé 2 fois pendant le test hors ligne de /jouer (sons activés) : origine non isolée, à recouper avec l'agent Jouer.
