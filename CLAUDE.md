# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

ChessLocal : clone privé de chess.com, 100 % client (aucun serveur, aucun compte).
PWA installable sur iPhone, utilisable hors ligne après la première visite.
Déployée sur GitHub Pages sous `/chess-local/`.
Toute l'UI, les commentaires de code et les messages de commit sont en français.

## Commandes

```bash
npm ci                 # requis avant tout : sans node_modules, `oxlint` et `tsc` sont introuvables
npm run dev            # Vite, http://localhost:5173
npm run build          # tsc -b && vite build
npm run check          # lint (oxlint) + typecheck (tsc -b) : à lancer avant tout commit
npm run preview        # sert dist/
```

Il n'y a pas de tests unitaires.
Les tests sont des suites E2E Playwright en Python (`e2e/test_*.py`), lancées par `e2e/run.py` :

```bash
npm run test:e2e                          # build de prod servi sous /chess-local/ (comme GitHub Pages), toutes les suites
npm run test:e2e -- --suite learn         # une seule suite, nommée d'après son fichier e2e/test_<nom>.py (cumulable : --suite learn --suite touch)
npm run test:e2e:dev                      # serveur de dev : StrictMode double les updaters et révèle les effets de bord mal placés
BASE=https://maxencebrochard.github.io/chess-local npm run test:e2e   # contre la prod déployée, sans serveur local
npm run test:e2e -- --suite all_buttons --live                        # API chess.com réelle au lieu de la fixture, hors gate
```

Prérequis hors `npm ci` : `pip install -r e2e/requirements.txt`.
Chromium vit dans `~/.local/share/chess-local/ms-playwright`, hors de `~/Library/Caches` que les nettoyages de disque vident : `e2e/run.py` y fixe `PLAYWRIGHT_BROWSERS_PATH` pour les suites et l'installe tout seul s'il manque (`PLAYWRIGHT_SKIP_BROWSER_GC=1`, environ 150 Mo, une fois).
Un `PLAYWRIGHT_BROWSERS_PATH` déjà exporté est respecté.
`e2e/run.py` démarre son propre serveur sur un port libre, vérifie que c'est bien cette app qui répond, surveille le serveur pendant les suites et l'arrête toujours.
Ne jamais lancer une suite contre un serveur démarré à la main sur un port fixe : un serveur mort ou fantôme a déjà fait chercher un bug qui n'existait pas.
Le code de sortie est la vérité : non nul dès qu'un check échoue, qu'une page lève une exception (`pageerror`) ou qu'un appel chess.com sort de la fixture.

Écrire une suite : tout passe par `e2e/helpers.py`.
`Checker` porte les checks (`check`, `appears`) et le code de sortie, `mobile_context`/`desktop_context` créent des contextes surveillés (iPhone 14 Pro tactile, `standalone=True` pour le viewport de la PWA installée), `drag_piece` fait un vrai drag TACTILE via CDP.
Un check doit pouvoir échouer : pas de `check(nom, True)`, pas d'attente nue dont l'échec interrompt la suite (utiliser `ck.appears`).
Les contextes pré-remplissent `localStorage['chess-local-settings']` au format Zustand persist (`{state: {...}, version: 1}`) avec `reviewDepth: 'fast'` et les sons coupés.
Changer la forme du store `src/store/settings.ts` impose de mettre à jour `DEFAULT_SETTINGS` dans `e2e/helpers.py`.
L'API chess.com est simulée par `e2e/fixtures/chesscom.json` (parties fictives) : tout nouvel appel réseau doit y être ajouté.
Le gate n'utilise jamais `--live`.
`test_revision.py` sème IndexedDB nativement (après `wait_schema`, l'app ayant créé le schéma de `src/lib/db.ts`), bloque le service worker et remplace `puzzles.json` par une route ; ses dates sont relatives aux jours civils locaux (midi J-n, ou minuit plus une minute pour « aujourd'hui »), jamais « il y a une heure ».
`test_pwa.py` ne tourne que sur le build local : sous-chemin, manifest, service worker, précache, puis redémarrage avec le serveur réellement tué (`set_offline` ne coupe pas le réseau du service worker).
`test_upgrade.py` (prod uniquement) est le garde-fou de continuité des données : pour chaque ancien build déployé épinglé dans `OLD_BUILDS` (tags `deployed-2026-07-20`, `deployed-2026-10-06`, `deployed-2026-10-15` et `deployed-2026-10-16`, extraits de git ; `git fetch origin tag <tag>` s'il manque), il le sert, y crée de vraies données par l'interface dans un profil persistant, bascule sur le build courant sur le même port, vérifie IndexedDB, réglages et chiffres affichés à l'identique, puis restaure une sauvegarde de l'ancien build dans le nouveau ; `E2E_MUTATION=rename-db|clear-ratings|drop-table|clear-settings` sert une copie mutée du nouveau build pour prouver que la suite passe au rouge.
Après un déploiement, ajouter le nouveau tag à `OLD_BUILDS` et retirer un build que plus aucun appareil ne porte.
Chaque lancement build dans son propre dossier temporaire, jamais dans `dist/` : deux lancements simultanés ne se gênent pas.
Les captures vont dans `e2e/shots/` (gitignoré).

Autres scripts :

- `node scripts/prepare-data.mjs` régénère `public/puzzles.json` et `src/data/openings.json`.
  Il lit `data/puzzles_full.csv` (dump lichess décompressé), absent du repo : seuls les `data/openings_*.tsv` sont versionnés.
- `python3 scripts/verify-endgame-course.py` revérifie `src/data/endgameCourse.json` contre les tables de finales lichess (réseau) et réécrit son tampon `scripts/endgame-course.verified`.
  À lancer après toute modification du cours de finales : sans tampon à jour, `scripts/check-endgame-course.mjs` (suite `endgame_course`) échoue.
- `python3 scripts/verify-attack-course.py` revérifie `src/data/attackCourse.json` (cours « Démolir le roque ») avec Stockfish 18 natif (`STOCKFISH` ou `stockfish` du PATH, mono-thread, profondeurs fixes, cache dans `~/.cache/chess-local/`) et réécrit `keeps`, `close`, `eval` et le tampon `scripts/attack-course.verified`.
  À lancer après toute modification de ce cours : sans tampon à jour, `scripts/check-attack-course.mjs` (suite `cours_roque`) échoue.
  Les deux cours partagent le moteur `src/lib/lessonCourse.ts`, la page `src/pages/LessonCourse.tsx` et les règles `scripts/course-rules.mjs`.
- `python3 scripts/prepare-mates.py` régénère `src/data/mateDrills.json` (positions « contre la montre » de /mats, vérifiées sur `tablebase.lichess.ovh`, réseau requis).
- `node scripts/prepare-mates-index.mjs` régénère `src/data/mateIndex.json` (puzzles classés par géométrie de mat avec `src/lib/mateNet.ts`) : à relancer après `prepare-data.mjs` ; la suite `mats` vérifie qu'il est à jour (`--check`).
- `python3 scripts/prepare-attacks.py` régénère `src/data/attacks.json` (banque de l'entraîneur d'attaque) : parties lichess des puzzles d'attaque (API publique, cache `data/lichess-puzzle-games.jsonl` non versionné), positions reculées avant la combinaison et triées par Stockfish natif (`STOCKFISH`, sinon celui du PATH).
  Thème, consigne et plan sont calculés par `scripts/attack_facts.py`, que la suite `attaque` réutilise ; `--relabel` les recalcule sans moteur.
- `python3 scripts/prepare-defenses.py` régénère `src/data/defenses.json` (banque de l'entraîneur de défense) : mêmes puzzles et même cache lichess que l'attaque, positions reculées de 1, 3 ou 5 demi-coups (défenseur au trait, avant le coup qui a craqué), gardées si Stockfish natif les juge défendables avec un seul bon coup et sous une vraie menace (coup nul), cache d'évals `data/defense-evals.jsonl` non versionné, clés incluant les seuils.
  `scripts/attack_facts.py` prend l'attaquant en paramètre (`att`, défaut le camp au trait) ; les phrases vues du défenseur sont dans `scripts/defense_facts.py`, que la suite `defense` réutilise ; `--relabel` les recalcule sans moteur.
  Le script affiche les rejets par critère et par catégorie ; le calibrage retenu est noté dans son docstring.
- `scripts/deploy.sh` build puis force-push `dist/` sur la branche `gh-pages`.
  Action sortante : ne pas le lancer sans demande explicite.
  Le push final est en HTTPS et échoue avec le compte GitHub par défaut de la machine ; `set -e` arrête alors le script avant `rm -rf dist/.git`, le commit reste dans `dist/`.
  Depuis `dist/`, le push peut se faire en SSH : `git push -f git@github.com:maxencebrochard/chess-local.git gh-pages`, puis `rm -rf dist/.git` depuis la racine.
  Poser ensuite le tag du déploiement, seule poignée durable sur ce commit (la branche est réécrite à chaque déploiement) : `git fetch origin gh-pages && git tag deployed-AAAA-MM-JJ FETCH_HEAD && git push origin tag deployed-AAAA-MM-JJ`.
  La date du tag est le jour UTC du `__BUILD__` (affiché en bas de `/import`), que `test_upgrade.py` recoupe.
- `?debug-uci` dans l'URL logge le trafic UCI en console.
- `node scripts/bench-bots.mjs --preset chain --games 80 --out bench.jsonl` mesure l'Elo des bots (parties bot contre bot, Bradley-Terry ancré sur Iris = 1600, IC 95 % par bootstrap).
  Il exécute la vraie `bots.ts` et la vraie classe `Engine` sur le même WASM, dans Node ; compter environ une heure.
  À relancer après tout changement de style ou d'Elo d'un bot faible.

## Architecture

Stack : React 19, Vite 8, TypeScript, Tailwind 4, Zustand (réglages), Dexie (IndexedDB), chess.js, react-chessboard, Stockfish 18 WASM.
`src/pages/` contient une page par route, `src/lib/` la logique sans React, `src/components/` les briques partagées.

### Moteur (`src/lib/engine.ts`)

Un `Engine` = un worker Stockfish (`public/engine/`, build `lite-single` mono-thread, donc pas de COOP/COEP).
Toutes les méthodes publiques passent par un mutex (chaîne de promesses) : deux `go` sans `stop` intermédiaire font trap le WASM (`unreachable`).
Ne jamais envoyer de commande UCI en dehors de `exclusive()`.
`searchId` invalide les callbacks `onLines` d'une recherche remplacée : toute nouvelle méthode de recherche doit passer par `attachInfoListener()`.
Les scores sont du point de vue du trait ; les convertir explicitement avant de les afficher côté blanc.

Chaque page crée son moteur paresseusement dans un `useRef` (`engineRef.current ??= new Engine()`) et appelle `quit()` au démontage.
`Play.tsx` en tient deux : celui du bot est bridé par `UCI_LimitStrength`/`UCI_Elo` (`src/lib/bots.ts`), celui du coach live reste à pleine force pour évaluer les coups.
Pour des recherches concurrentes ou des options différentes, créer un second `Engine` plutôt que partager le même.
Sous 1320 Elo (plancher de `UCI_Elo`), un bot a un `style` : Stockfish pleine force à profondeur fixe en MultiPV, puis tirage pondéré par la perte (`pickWeakMove`), sans jamais rater un coup qui s'impose.
Toute la décision passe par `chooseBotMove` de `bots.ts` ; les styles sont calibrés par `scripts/bench-bots.mjs`.

### `/analyse` est le hub

Les autres pages y envoient leur contenu par state de navigation :
`navigate('/analyse', { state: { pgn | fen, uci?, viewIndex?, color?, orientation?, label?, review?, returnTo?, returnLabel? } })`.
Archive et fin de partie passent par `?game=<id>` (lecture dans Dexie), avec `&review=1` pour lancer le bilan directement.
`Analysis.tsx` consomme `location.state` au montage puis fait `navigate('.', { replace: true, state: null })` pour qu'un refresh ne rejoue pas le chargement.
`returnTo` affiche un bouton retour (libellé `returnLabel`, « Retour à l'exercice » par défaut) qui navigue avec `state: { restore: true }` ; `Learn.tsx` et `Revision.tsx` restaurent alors leur séance depuis `sessionStorage`.
Partie contre Stockfish depuis une position : `components/PositionGame.tsx` (logique pure dans `lib/positionGame.ts`), utilisé par `/attaque/:id` (`pages/Attack.tsx`), `/defense/:id` (`pages/Defense.tsx`), `/finales/:id` (finales jouées jusqu'au bout, `pages/Endgames.tsx`), `/analyse/jouer` (bouton « Jouer contre le moteur » de l'analyse, `pages/PositionPlay.tsx`), `/attaques-manquees/:id` et `/defenses-ratees/:id`.
La partie en cours est rejouée depuis `localStorage['chess-local-position-game-v1']` ; les résultats des finales vont dans `learnSessions` (domaine `endgame-play`, hors Elo).
Un seul emplacement de persistance : une tentative en cours écrasée par une autre partie passe par `recordReplaced` (`lib/attempts.ts`), qui aiguille selon le préfixe de clé (`attaque:` et `defense:` notées abandonnées) ; tout appelant de `PositionGame` lui passe `onReplace={recordReplaced}`.
L'entraîneur de défense (`/defense`, `lib/defense.ts`) utilise l'objectif `hold` de `PositionGame` (prop `hold: { moves, floorCp }`, 12 coups, plancher -3) : après chaque réponse de Stockfish, l'oracle à pleine force évalue la position ; strictement sous le plancher (ou mat contre le joueur) deux tours de suite donne la fin `collapsed`, et au 12e coup une éval de confirmation d'une seconde, échiquier bloqué, décide `held` ou `collapsed`.
La partie s'arrête sur ces deux fins, sans Continuer ni Annuler ; une nulle de l'échiquier ou un gain réussissent aussi, pas de bouton Nulle ; la série sous le plancher est persistée avec la partie (`holdFall`).
Ses niveaux sont ceux de l'attaque (`LEVELS`, 2100 par défaut), mémorisés sous `localStorage['chess-local-defense']`, purgé par la réinitialisation.
Chaque tentative est une ligne `learnSessions` du domaine `defense` (format dans `db.ts` : `outcome` parmi `held | draw | win | mated | collapsed | resign | abandon`, Elo de l'attaquant dans `attackerElo`), sans Elo et ignorée par `pickNextDomain`.

### Pipeline d'évaluation

`review.ts` évalue chaque position en multipv 2 à profondeur fixe, convertit en win% (formule lichess) et classe chaque coup selon la chute de win%.
`MoveClass`, `CLASS_META` (libellés, couleurs, symboles) et les seuils vivent uniquement là.
En dépendent : `coach.ts` (commentaires post-partie générés par règles), `liveCoach.ts` (classe rapide du mode entraîneur), `ReviewSummary`, `EvalGraph`, `MoveList`.
Un bilan lancé dans Analyse écrit les fautes dans la table `mistakes`, rejouées ensuite dans Apprendre → Mes erreurs.
`kingAttack.ts` (chess.js seul) relit ces fautes pour « Mes attaques manquées » (`/attaques-manquees`) : le type d'attaque (mat, sacrifice près du roi, pion contre le roque, pièce vers le roi) est recalculé sur l'échiquier depuis `fenBefore` et `bestUci`, jamais stocké ; seules les lignes avec `color` (camp du joueur connu du bilan) comptent, `gameKey` identifie la partie.
« Mes défenses ratées » (`/defenses-ratees`, `missedDefense` du même module) relit les mêmes lignes avec `color` et une classe `mistake` ou `blunder` : sur `fenBefore`, le joueur au trait, au moins deux pièces adverses visent la zone de son roi et au moins autant que ses défenseurs (`zoneCounts`), l'adversaire a au moins trois pièces, et son roi est roqué ou au centre.
L'exercice reprend exactement celui des attaques manquées (retrouver `bestUci`, `keyMove`), noté dans le domaine `missed-defense` ; une même faute peut figurer dans les deux listes.
Le même module porte le calque « Compte les attaquants » (réglage `showAttackers`) : zone = anneau du roi de Stockfish (3x3 ramené dans b-g / 2-7), compte des seules pièces ; la suite `diagnostic_attaque` le vérifie contre un oracle python-chess.
Insights (`/insights`) réutilise `reviewGame` (paramètre `pause` pour suspendre la série quand la page est masquée), met les bilans en cache dans `reviews` (clé `chesscom:<id>` ou `local:<id>`, une profondeur par rapport) et calcule tout dans `insights.ts`, pur et testé sous Node par `test_insights.py` ; il n'écrit jamais dans `mistakes`.
L'entraîneur d'ouvertures (`/ouvertures`, `src/lib/openingTrainer.ts`) enregistre ses tentatives dans `learnSessions` avec le domaine `opening-drill` (format d'`itemId` documenté dans `db.ts`) ; `pickNextDomain` les ignore.
La révision espacée (`/revision`, `src/lib/revision.ts`) n'a pas de table : l'échéance de chaque item raté (puzzle, faute, variante `full`) se calcule depuis son historique daté (`puzzleAttempts`, `learnSessions`, `mistakes`), agrégé par jour civil local, avec une échelle de Leitner `[1, 3, 7, 21]` jours ; un item en retard de plus de 30 jours sort de la file.
Un résultat de révision s'écrit là où l'écran d'origine écrit (`scoreItem('mistakes')` + `mistakes.update`, `recordDrill`, ou le domaine `revision` pour les puzzles), jamais dans un Elo.
Le compteur de l'accueil ne charge jamais `puzzles.json` ; seule la séance le fait.

### Persistance

Base Dexie `chess-local` (`src/lib/db.ts`), actuellement en `version(3)` (table `reviews` : cache des bilans d'Insights).
Ajouter une table ou un index = nouveau bloc `db.version(n)` qui redéclare tous les stores, plus l'ajout dans `TABLES` de `backup.ts`.
La table `ratings` est unique et indexée par clé texte : cadences (`bullet`, `blitz`, `rapid`, `unlimited`), `puzzle`, et domaines d'Apprendre (`learn-endgame`, `learn-tactic`, ...).
Tous les Elo passent par `applyRating`/`eloUpdate`.
Les réglages sont dans Zustand persist (`localStorage['chess-local-settings']`).
La migration persist des réglages (version 1) est partagée avec l’import des sauvegardes : une version 0 ou absente avec `pieceSet` absent ou `celtique` donne `wikimedia`, comme une montée de version locale.
Un choix `celtique` enregistré en version 1 est conservé ; cette version persist est indépendante de la version du schéma de sauvegarde.
L’import valide ensuite les types (dont `premoves`, booléen sinon défaut) et les valeurs contre les listes réelles de l’application.
Les séances en cours d'Apprendre et de révision vivent dans `sessionStorage` (`learn-session-v1`, `revision-session-v1`) : `importBackup` et `resetApp` effacent ces deux clés, et seulement elles.
`main.tsx` demande `navigator.storage.persist()` ; iOS peut purger IndexedDB, et le périmètre des sauvegardes de `backup.ts` est décrit dans [README.md, section Features](README.md#features).

### Chemins et PWA

`base: './'` + `HashRouter` : l'app doit tourner aussi bien à la racine que sous `/chess-local/`.
Tout asset de `public/` se charge via `import.meta.env.BASE_URL` (worker moteur, sons, pièces, `puzzles.json`) ; un chemin absolu `/...` casse la prod.
Le service worker précache tout (WASM 7 Mo, puzzles 16 Mo) avec un plafond de 25 Mo par fichier dans `vite.config.ts`.
Un nouvel asset lourd ou une nouvelle extension doit être couvert par `globPatterns`.
`__BUILD__` (horodatage de build) s'affiche en bas de `/import` pour vérifier qu'un iPhone a bien la dernière version.

### Pièces et sons

Les jeux de pièces sont des SVG libres dans `public/pieces/<jeu>/` (liste dans `src/lib/pieces.ts`, réglage `pieceSet`), rendus en `<img>` par `Board` via l'option `pieces` de react-chessboard ; `classique` = pièces intégrées à la lib.
Les sons (`public/sounds/`, CC0, `scripts/make-sounds.sh` pour les notifications Kenney et `scripts/synthesize-moves.py` pour les impacts originaux sans entrée audio) passent tous par `src/lib/sounds.ts`, qui lit lui-même `playSounds` et `soundVolume` : pas de test du réglage aux appels.
`Board` porte le ressenti tactile partagé : clone à 1,7, dessin décalé de 0,85 case au-dessus du contact, disque de visée et retour animé des refus.
Le décalage vit sur `.board-piece` via `--piece-lift`, car déplacer le rectangle du clone serait compensé par le recentrage de dnd-kit.
La cible vient des callbacks de collision de react-chessboard, jamais de la position du dessin décalé.
La souris conserve son échelle 1,2 et son cadre de destination ; les animations respectent `prefers-reduced-motion`.
`e2e/test_feeling.py` vérifie la géométrie pendant le geste CDP et l'audio horodaté à la pose ; les mesures sonores et limites sont dans `docs/f14-feeling.md`.
Les conditions du son automatique de coup (`lastMove`, `silent` et anti-empilement partagé) sont documentées auprès de l'effet dans `src/components/Board.tsx`.
Une page qui joue ses sons de coup elle-même (Jouer, finales jouées) ou affiche un saut de position (réessai de l'analyse) lui passe `silent`, comme les diagrammes ; la position qui suit un `silent` reste muette.
Aucun asset de chess.com, et toute ressource ajoutée doit être sous licence libre documentée dans le `LICENSES.md` de son dossier : le dépôt est public.

### Prémouvements

`Board.allowPremove` est un opt-in explicite, avec `movableColor` obligatoire ; le propriétaire le coupe en revue d'historique, en fin de partie ou pendant une action bloquante.
`interactive` conserve son rôle de permission de jouer immédiatement ; le Board peut préparer un coup adverse quand `allowPremove` est actif même si `interactive` est faux.
Play (bot et entraîneur), PositionGame (attaque, défense, finales, analyse/jouer), EngineContinuation en mode jouer et ChronoRun l'activent ; puzzles, plans et exercices à solution unique restent exclus.
La file locale contient un seul coup non persisté, même sur ordinateur : deux cases rouges, pièce au départ, aucun son à la saisie, annulation par toucher sur une case ou Échap, remplacement par un nouveau glissé.
`lib/premove.ts` valide uniquement la géométrie : échec, occupation et obstacles sont ignorés à la saisie, car le coup adverse peut libérer une case ou offrir une prise ; les droits de roque et le sens des pions restent requis.
Après exactement un coup adverse, chess.js revalide entièrement le coup, promotion en dame, puis le Board consomme la file avant d'appeler `onMove(from, to, promotion, true)` une seule fois.
Un coup illégal est oublié sans bruit ; retour arrière, changement de position, désactivation du réglage ou changement de camp vident aussi la file.
Le quatrième argument distingue un prémouvement pour les propriétaires de pendule : Play et ChronoRun débitent 100 ms avant le coup, sans débit sur une annulation ; si le temps est insuffisant, le drapeau tombe sans jouer.
Ce coût reprend la [règle officielle vérifiée le 15 octobre 2026](https://support.chess.com/en/articles/8562432-what-are-pre-moves-and-how-do-they-work), avec une fin au drapeau simplifiée, sans affichage intermédiaire bloqué à 0,1 s.
Les modes illimités n'ont aucun débit ; le temps réel de traitement reste soumis à la pendule existante.
Les sons existants restent propriétaires de l'exécution ; le son automatique du Board exempte le prémouvement de l'anti-empilement de 60 ms pour ne pas le perdre juste après la réponse moteur.
`settings.premoves` vaut true par défaut, le merge Zustand conserve les anciens stockages sans clé et le nettoyage des sauvegardes récupère automatiquement ce défaut.
`e2e/test_premove.py` contrôle les gestes iPhone, la file, le son, les refus, la promotion, la pendule, les réglages et l'exclusion des puzzles ; `PREMOVE_CASE` permet de cibler un scénario pour les preuves par mutation.
La vidéo de référence et ses extractions ffmpeg restent exclusivement dans un dossier temporaire hors dépôt.

### Données

`public/puzzles.json` : 120 000 puzzles lichess au format compact `[id, fen, moves, rating, themes]`, hors bundle, chargés une fois par `loadPuzzles()`.
`src/data/*.json` est bundlé : `openings.json` (généré), `endgames.json`, `strategy.json`, `courses.json` (contenu d'Apprendre, écrit à la main, en français), `endgameCourse.json` (cours de finales, `#/apprendre/finales`), `attackCourse.json` (cours « Démolir le roque », `#/apprendre/roque`), `attacks.json` (généré, banque de l'entraîneur d'attaque, `#/attaque`), `defenses.json` (généré, banque de l'entraîneur de défense, `#/defense`).
Une leçon terminée est une ligne `learnSessions` `{ domain: 'course', itemId: '<slug>:<id>' }` (`finales:`, `roque:`) : les ids de leçons sont figés (`FROZEN_IDS` du contrôle).
Les noms d'ouvertures sont en anglais dans les données et traduits à l'affichage par `openingNames.ts`.

### UI

Mobile d'abord : la cible principale est la PWA iPhone en mode standalone (nav basse, `pt-safe`/`pb-safe`, hauteurs en `dvh`), avec une nav latérale à partir de `md`.
Les E2E tournent sur le device `iPhone 14 Pro` et en 1440x900.
Couleurs via les tokens Tailwind `@theme` de `src/index.css` : `surface`, `surface-2`, `surface-3`, `accent`.
`.boardbox` fixe la taille de la plupart des échiquiers ; les cours utilisent leur propre conteneur.
`main.tsx` annule le `touchstart` natif dans les 25 px des bords du viewport sur les cases `[data-board] [data-square]`, pour empêcher les gestes précédent/suivant de WebKit depuis tout échiquier sans couper les événements de react-chessboard.
`Board` porte toujours `data-board`, indépendamment de sa propriété `interactive` et des classes de mise en page : la protection couvre aussi la réflexion du moteur et les diagrammes.
La prévention reste ciblée : l'annulation globale casse les boutons et le défilement vertical près du bord ; les diagrammes de cours restent défilables depuis leur centre et l'historique n'est pas modifié.
La suite `edge_navigation` vérifie en contexte mobile standalone les contacts CDP annulés aux deux bords (dont 20 px du bord réel du viewport) et les coups par glissé sur Analyse, les exercices de `LessonCourse`, Jouer et les puzzles.
Elle vérifie aussi les coups par glissé central non annulé, le clic-clic, les boutons, le défilement du contenu et le défilement vertical depuis le centre d’un diagramme de cours.
Les contacts au bord sont aussi annulés sur les diagrammes et pendant la réflexion du moteur, quand l’échiquier est momentanément non jouable.
